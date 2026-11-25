"""
Clasifica documentos (título + resumen) con un modelo local de Ollama.
Guarda cada resultado en un .jsonl apenas sale: si se corta, se vuelve a correr el mismo comando y sigue donde iba.

Ejemplos:
  # AJUSTE (100 docs de la muestra de Natalia)
  python clasificar_ia.py Muestra_clasificaci_nresultados.xlsx --clave clave_muestra_NO_COMPARTIR.xlsx --grupo AJUSTE --modelo gemma4:12b --salida ajuste_gemma12b.jsonl
  # Corrida grande, primero 2011-2021
  python clasificar_ia.py candidatos_todos_anios.csv --prioridad en_2011_2021 --modelo gemma4:31b-it-qat --think --paralelo 2 --salida total_gemma31b.jsonl
  # Solo regenerar el Excel desde el .jsonl
  python clasificar_ia.py candidatos_todos_anios.csv --salida total_gemma31b.jsonl --solo-excel
"""
import argparse, json, re, sys, threading, time, unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import prompt_clasificacion as P

ap = argparse.ArgumentParser()
ap.add_argument("entrada", help="Excel o CSV con los documentos")
ap.add_argument("--hoja", default=None, help="hoja del Excel (por defecto la primera)")
ap.add_argument("--col-id", default=None); ap.add_argument("--col-titulo", default=None)
ap.add_argument("--col-resumen", default=None); ap.add_argument("--col-link", default=None)
ap.add_argument("--clave", default=None, help="clave de la muestra (columnas N° y Grupo)")
ap.add_argument("--grupo", default=None, help="AJUSTE o EVALUACIÓN (requiere --clave)")
ap.add_argument("--prioridad", default=None, help="columna booleana: las filas verdaderas se clasifican primero (ej. en_2011_2021)")
ap.add_argument("--solo-prioridad", action="store_true", help="clasifica solo las filas de --prioridad")
ap.add_argument("--modelo", default="gemma4:31b-it-qat")
ap.add_argument("--url", default="http://localhost:11434")
ap.add_argument("--think", action="store_true", help="activa el razonamiento del modelo")
ap.add_argument("--paralelo", type=int, default=1, help="documentos a la vez (Ollama debe tener OLLAMA_NUM_PARALLEL >= este número)")
ap.add_argument("--num-ctx", type=int, default=16384)
ap.add_argument("--temperatura", type=float, default=0.0)
ap.add_argument("--semilla", type=int, default=2026)
ap.add_argument("--min-resumen", type=int, default=100)
ap.add_argument("--limite", type=int, default=None, help="clasifica solo los primeros N pendientes (para pruebas)")
ap.add_argument("--salida", required=True, help="archivo .jsonl de resultados")
ap.add_argument("--cada", type=int, default=10, help="imprime el avance cada N documentos")
ap.add_argument("--solo-excel", action="store_true")
args = ap.parse_args()

# ---------------- leer entrada ----------------
def leer(ruta, hoja=None):
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(ruta, sheet_name=hoja or 0)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(ruta, encoding=enc, sep=None, engine="python")
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"No pude leer {ruta}")

def elegir(df, dado, opciones, nombre, obligatoria=True):
    if dado:
        if dado not in df.columns: raise SystemExit(f"No existe la columna '{dado}'. Columnas: {list(df.columns)}")
        return dado
    for o in opciones:
        for c in df.columns:
            if str(c).strip().lower() == o.lower(): return c
    if obligatoria: raise SystemExit(f"No encontré la columna de {nombre}. Usa --col-{nombre}. Columnas: {list(df.columns)}")
    return None

df = leer(args.entrada, args.hoja)
c_id = elegir(df, args.col_id, ["N°", "handle", "ID", "id", "identifier"], "id")
c_ti = elegir(df, args.col_titulo, ["Título", "Titulo", "title", "dc.title"], "titulo")
c_re = elegir(df, args.col_resumen, ["Resumen", "Abstract", "abstract", "resumen", "dc.description.abstract"], "resumen")
c_li = elegir(df, args.col_link, ["Link", "Enlace", "url", "link"], "link", obligatoria=False)

df["_id"] = df[c_id].astype(str).str.strip()
if df["_id"].duplicated().any():
    raise SystemExit(f"Hay ids repetidos en '{c_id}' ({df['_id'].duplicated().sum()}). Usa otra columna con --col-id.")
df["_titulo"] = df[c_ti].fillna("").astype(str).str.strip()
df["_resumen"] = df[c_re].fillna("").astype(str).str.strip()

if args.grupo:
    if not args.clave: raise SystemExit("--grupo necesita --clave")
    clave = pd.read_excel(args.clave)
    ids = set(clave.loc[clave["Grupo"].astype(str).str.upper().str.startswith(args.grupo.upper()[:4]), "N°"].astype(str))
    df = df[df["_id"].isin(ids)].copy()
    print(f"Grupo {args.grupo}: {len(df)} documentos")

if args.prioridad:
    pr = df[args.prioridad].astype(str).str.lower().isin(["true", "1", "sí", "si", "verdadero"])
    df["_prio"] = pr
    if args.solo_prioridad: df = df[pr]
    df = df.sort_values("_prio", ascending=False, kind="stable")
else:
    df["_prio"] = True

# ---------------- resultados previos ----------------
salida = Path(args.salida)
hechos = {}
if salida.exists():
    for linea in salida.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            r = json.loads(linea); hechos[r["id"]] = r

# ---------------- utilidades ----------------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

RX_A = re.compile("|".join(P.NIVEL_A), re.IGNORECASE)

def llamar(titulo, resumen):
    cuerpo = {
        "model": args.modelo,
        "messages": [{"role": "system", "content": P.SISTEMA},
                     {"role": "user", "content": P.mensaje_usuario(titulo, resumen)}],
        "format": P.ESQUEMA, "stream": False, "think": bool(args.think), "keep_alive": "24h",
        "options": {"num_ctx": args.num_ctx, "temperature": args.temperatura, "seed": args.semilla},
    }
    r = requests.post(f"{args.url}/api/chat", json=cuerpo, timeout=1800)
    r.raise_for_status()
    return r.json()

def clasificar(fila):
    t0 = time.time()
    base = {"id": fila["_id"], "titulo": fila["_titulo"], "prioridad": bool(fila["_prio"]),
            "modelo": args.modelo, "think": bool(args.think), "prompt": P.VERSION_PROMPT,
            "fecha": datetime.now().isoformat(timespec="seconds")}
    if len(fila["_resumen"]) < args.min_resumen:
        return {**base, "decision_final": "REVISAR", "decision_modelo": None, "banderas": ["sin_resumen"], "segundos": 0}
    ultimo_error = None
    for intento in range(3):
        try:
            resp = llamar(fila["_titulo"], fila["_resumen"])
            contenido = resp["message"]["content"]
            m = re.search(r"\{.*\}", contenido, re.S)
            j = json.loads(m.group(0) if m else contenido)
            break
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {e}"; time.sleep(3)
    else:
        return {**base, "decision_final": "REVISAR", "decision_modelo": None, "banderas": ["error"], "error": ultimo_error,
                "segundos": round(time.time() - t0, 1)}
    banderas = []
    texto = norm(fila["_titulo"] + " " + fila["_resumen"])
    evid = [e for e in j.get("evidencia", []) if str(e).strip()]
    ok = [e for e in evid if norm(e) and norm(e) in texto]
    if len(ok) < len(evid): banderas.append("cita_no_encontrada")
    dec_m = j.get("decision")
    dec = dec_m
    terminos_a = sorted({x.group(0).lower() for x in RX_A.finditer(fila["_titulo"] + " " + fila["_resumen"])})
    if dec_m == "EXCLUIR" and terminos_a:
        dec = "POSIBLE"; banderas.append("red_nivel_A")
    if dec_m == "INCLUIR" and not ok: banderas.append("incluir_sin_evidencia")
    if resp.get("prompt_eval_count", 0) >= args.num_ctx * 0.95: banderas.append("contexto_casi_lleno")
    return {**base, **j, "decision_modelo": dec_m, "decision_final": dec, "terminos_nivel_A": terminos_a,
            "citas_ok": len(ok), "citas_total": len(evid), "banderas": banderas,
            "tokens_entrada": resp.get("prompt_eval_count"), "tokens_salida": resp.get("eval_count"),
            "pensamiento_chars": len(resp["message"].get("thinking") or ""), "segundos": round(time.time() - t0, 1)}

# ---------------- excel ----------------
def excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    res = [json.loads(l) for l in salida.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not res: print("No hay resultados todavía"); return
    info = df.set_index("_id")
    wb = Workbook(); ws = wb.active; ws.title = "Resultados"
    cols = ["ID", "Título", "Decisión IA", "Decisión del modelo (sin red)", "Dimensión agraria", "Ejes", "Conflicto/paz",
            "Técnico agronómico", "Colombia", "Tema central", "Motivo", "Evidencia", "Términos Nivel A", "Banderas",
            "Prioridad (2011-2021)", "Link", "Resumen"]
    ws.append(cols)
    orden = {"INCLUIR": 0, "POSIBLE": 1, "REVISAR": 2, "EXCLUIR": 3}
    for r in sorted(res, key=lambda r: (orden.get(r["decision_final"], 9), not r.get("prioridad", True))):
        link = info.at[r["id"], c_li] if (c_li and r["id"] in info.index) else ""
        resu = info.at[r["id"], "_resumen"] if r["id"] in info.index else ""
        ws.append([r["id"], r.get("titulo"), r["decision_final"], r.get("decision_modelo"), r.get("dimension_agraria"),
                   "; ".join(r.get("ejes", []) or []), "Sí" if r.get("vinculo_conflicto_paz") else ("No" if "vinculo_conflicto_paz" in r else ""),
                   "Sí" if r.get("tecnico_agronomico") else ("No" if "tecnico_agronomico" in r else ""), r.get("colombia"),
                   r.get("tema_central"), r.get("motivo"), "\n".join(r.get("evidencia", []) or []),
                   ", ".join(r.get("terminos_nivel_A", []) or []), ", ".join(r.get("banderas", [])),
                   "Sí" if r.get("prioridad", True) else "No", "" if pd.isna(link) else str(link), str(resu)[:32000]])
    anchos = [12, 45, 12, 14, 12, 30, 10, 10, 9, 40, 45, 45, 25, 20, 10, 30, 80]
    for i, a in enumerate(anchos, 1): ws.column_dimensions[ws.cell(1, i).column_letter].width = a
    for c in ws[1]: c.font = Font(name="Calibri", bold=True)
    for fila in ws.iter_rows(min_row=2):
        for c in fila: c.font = Font(name="Calibri"); c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "C2"

    s = wb.create_sheet("Resumen")
    s.append(["Resumen de la clasificación"]); s.append([])
    for grupo, sub in [("Todos", res), ("2011-2021", [r for r in res if r.get("prioridad", True)]),
                       ("Fuera de 2011-2021", [r for r in res if not r.get("prioridad", True)])]:
        if not sub or (grupo != "Todos" and not args.prioridad): continue
        cnt = Counter(r["decision_final"] for r in sub)
        s.append([grupo, "Total", len(sub)])
        for k in ["INCLUIR", "POSIBLE", "EXCLUIR", "REVISAR"]: s.append(["", k, cnt.get(k, 0)])
        s.append([])
    inc = [r for r in res if r["decision_final"] in ("INCLUIR", "POSIBLE")]
    s.append(["Ejes más frecuentes (INCLUIR y POSIBLE)"])
    for e, n in Counter(e for r in inc for e in (r.get("ejes") or [])).most_common(): s.append(["", e, n])
    s.append([]); s.append(["Términos Nivel A más frecuentes (INCLUIR y POSIBLE)"])
    for e, n in Counter(t for r in inc for t in (r.get("terminos_nivel_A") or [])).most_common(15): s.append(["", e, n])
    s.append([]); s.append(["Banderas"])
    for e, n in Counter(b for r in res for b in r.get("banderas", [])).most_common(): s.append(["", e, n])
    s.append([]); s.append(["Parámetros"])
    for k, v in [("Modelo", args.modelo), ("Think", args.think), ("Prompt", P.VERSION_PROMPT), ("Temperatura", args.temperatura),
                 ("Contexto", args.num_ctx), ("Mínimo de resumen (caracteres)", args.min_resumen), ("Entrada", args.entrada)]:
        s.append(["", k, str(v)])
    s.column_dimensions["A"].width = 30; s.column_dimensions["B"].width = 50; s.column_dimensions["C"].width = 12
    for fila in s.iter_rows():
        for c in fila: c.font = Font(name="Calibri", bold=(c.column == 1))
    destino = salida.with_suffix(".xlsx")
    wb.save(destino); print(f"Excel guardado: {destino}")

if args.solo_excel:
    excel(); sys.exit()

# ---------------- correr ----------------
pend = df[~df["_id"].isin(hechos)]
if args.limite: pend = pend.head(args.limite)
total, ya = len(df), len(hechos)
print(f"{total} documentos | ya clasificados: {ya} | por clasificar ahora: {len(pend)}")
print(f"Modelo {args.modelo} | think={args.think} | paralelo={args.paralelo} | contexto={args.num_ctx} | prompt {P.VERSION_PROMPT}")
try:
    requests.get(f"{args.url}/api/tags", timeout=10).raise_for_status()
except Exception as e:
    raise SystemExit(f"No me pude conectar a Ollama en {args.url}: {e}")

lock = threading.Lock()
conteo = Counter(r["decision_final"] for r in hechos.values())
inicio = time.time(); hechos_sesion = 0; ultimo_print = 0; ultimo_n = -1

def fmt_t(seg):
    h, m = divmod(int(seg) // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"

def avance(forzar=False):
    global ultimo_print, ultimo_n
    hechos_total = ya + hechos_sesion
    if hechos_sesion == ultimo_n: return
    if not forzar and hechos_sesion % args.cada and time.time() - ultimo_print < 60: return
    ultimo_print = time.time(); ultimo_n = hechos_sesion
    trans = time.time() - inicio
    spd = trans / hechos_sesion if hechos_sesion else 0
    faltan = (len(pend) - hechos_sesion) * spd
    print(f"[{datetime.now():%H:%M}] {hechos_total}/{total} ({100*hechos_total/total:.1f} %) | {spd:.1f} s/doc | "
          f"faltan ~{fmt_t(faltan)} | INCLUIR {conteo['INCLUIR']} · POSIBLE {conteo['POSIBLE']} · "
          f"EXCLUIR {conteo['EXCLUIR']} · REVISAR {conteo['REVISAR']}", flush=True)

with open(salida, "a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.paralelo) as ex:
    futuros = [ex.submit(clasificar, fila) for _, fila in pend.iterrows()]
    try:
        for fu in as_completed(futuros):
            r = fu.result()
            with lock:
                f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
                hechos_sesion += 1; conteo[r["decision_final"]] += 1
                if "error" in r.get("banderas", []): print(f"  ! error en {r['id']}: {r.get('error')}", flush=True)
                avance()
    except KeyboardInterrupt:
        print("\nDetenido. Lo hecho quedó guardado; vuelve a correr el mismo comando para seguir.")
        for fu in futuros: fu.cancel()
        raise SystemExit
avance(forzar=True)
print(f"Listo en {fmt_t(time.time() - inicio)}")
excel()
