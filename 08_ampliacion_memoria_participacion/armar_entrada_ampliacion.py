"""
Arma UNA sola entrada (entrada_repo.csv y entrada_bases.csv) para clasificar_ia.py con todas las fuentes que pidió Natalia
(correo 23-nov-2026): repositorio + 2 bases viejas (Base final y Legado de octubre) + base de William Mancera.

- Solo 2011-2021 (en todas las fuentes).
- Repositorio: todo el reporte de 2011-2021 que sea texto (NO solo lo que pasó el filtro Dewey: ese filtro se
  armó para tierras y dejaba fuera psicología/filosofía, literatura, artes y educación, donde hay mucha memoria).
- Cada fila lleva la columna "Fuente". Si un documento está en varias fuentes se deja UNA fila y la Fuente
  las nombra todas ("Repositorio UNAL; Base William Mancera").
- Salen DOS archivos, para clasificarlos por separado (las bases de Natalia van de últimas y son opcionales):
    entrada_repo.csv   → repositorio: 1) sociales/humanas/artes  2) otras que pasan Dewey  3) resto (se clasifica en ese orden)
    entrada_bases.csv  → solo lo de las bases que NO está ya en el repositorio, con columna "Observaciones"
                         (sin enlace, tipo no académico, posible duplicado de un documento del repositorio).
- Duplicados bases↔repositorio: por handle del enlace, por título exacto y por título parecido (como en
  cruce_natalia.py: ≥92 % + año ±1 = el mismo; 85–92 % = "posible duplicado", se deja pero marcado).

Uso (en el Nodo 10, con el venv activado):
  python armar_entrada_ampliacion.py \
      --reporte "../fuentes/Reporte de Objetos Dspace 10 jun 2026 (1).xlsx" \
      --candidatos ~/prueba_nodo10/candidatos_todos_anios.csv \
      --william "../fuentes/Base_Legado_UNAL_William Mancera_....xlsx" \
      --legado "../fuentes/Base_Legado_Academico_UNAL_..._2 de octubre.xlsx" \
      --base-final "../fuentes/Base final 2010 - 2021.xlsx"
Cualquiera de las bases se puede omitir. Salida: entrada_repo.csv, entrada_bases.csv y resumen_entrada.txt
"""
import argparse, re, sys, unicodedata
from collections import Counter
import pandas as pd

ANIO_MIN, ANIO_MAX = 2011, 2021
# Natalia: estos temas se trabajan sobre todo desde ciencias sociales, humanas y artes → esas facultades van primero.
# También las colecciones generales (libros, editorial, BDF feminista, proyectos temáticos, colecciones de sede).
PRIORIDAD_COMM1 = re.compile(r"ciencias humanas|artes|ciencias econ|derecho|unijus|arquitectura$|^facultad de arquitectura|"
                             r"administraci[oó]n$|feminista|libros y cap|editorial|proyectos tem|^sede |^unal$|^general$", re.I)
TIPOS_EXCLUIDOS = {"audio", "partitura", "simulacion", "imagenes", "grabacion sonora", "presentacion",
                   "objeto de aprendizaje"}   # los mismos que filtro_dewey.py

ap = argparse.ArgumentParser()
ap.add_argument("--reporte", required=True)
ap.add_argument("--candidatos", required=True, help="candidatos_todos_anios.csv (para marcar quién pasa Dewey)")
ap.add_argument("--excluir", default=None,
                help="total_g31.xlsx de reforma agraria: sus INCLUIR y POSIBLE no se vuelven a clasificar (ya van al corpus)")
ap.add_argument("--william", default=None)
ap.add_argument("--legado", default=None)
ap.add_argument("--base-final", default=None)
args = ap.parse_args()


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def limpio(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    v = str(v).strip()
    return "" if v.lower() in ("nan", "none", "no hay enlace") else v


def col(df, *nombres, obligatoria=True):
    for n in nombres:
        for c in df.columns:
            if norm(c) == norm(n):
                return c
    if obligatoria:
        sys.exit(f"No encontré ninguna de {nombres}. Columnas: {list(df.columns)}")
    return None


def anio(v):
    m = re.search(r"((?:19|20)\d{2})", str(v)) if limpio(v) else None
    return int(m.group(1)) if m else None


def handle(v):
    m = re.search(r"(unal/\d+)", str(v)) if limpio(v) else None
    return m.group(1) if m else None


def armar_resumen(principal, extras):
    """Resumen = texto principal + (si es suficiente) líneas extra como Temas. Si el principal es corto,
    se deja solo el principal para que clasificar_ia.py lo mande a REVISAR igual que en la corrida agraria."""
    principal = limpio(principal)
    if len(principal) < 100:
        return principal
    extra = [f"{k}: {limpio(v)}" for k, v in extras if limpio(v)]
    return principal + ("\n\n" + "\n".join(extra) if extra else "")


filas, log = [], []

# ---------------- repositorio ----------------
print("Leyendo el reporte (1-2 min)...")
rep = pd.read_excel(args.reporte, dtype=str)
c_h, c_ti = col(rep, "handle"), col(rep, "Título", "Titulo")
c_ab, c_ti_tipo = col(rep, "Abstract"), col(rep, "Tipo")
c_fe = col(rep, "fecha del documento")
c_au = col(rep, "Autor", obligatoria=False)
c_su = col(rep, "subject", obligatoria=False)
c_c1 = col(rep, "comm_1", obligatoria=False)
rep["_anio"] = rep[c_fe].map(anio)
rep = rep[rep["_anio"].between(ANIO_MIN, ANIO_MAX)]
n_rango = len(rep)
rep = rep[~rep[c_ti_tipo].fillna("").map(lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().strip().lower()).isin(TIPOS_EXCLUIDOS)]
ya = set()
if args.excluir:
    ag = pd.read_excel(args.excluir, sheet_name="Resultados", dtype=str)
    ya = set(ag.loc[ag["Decisión IA"].isin(["INCLUIR", "POSIBLE"]), "ID"].map(handle).dropna())
    antes = len(rep)
    rep = rep[~rep[c_h].map(handle).isin(ya)]
    log.append(f"Quitados por ser INCLUIR/POSIBLE de reforma agraria (ya van al corpus): {antes - len(rep)}")
cand = pd.read_csv(args.candidatos, dtype=str, encoding="utf-8-sig")
pasa = set(cand["handle"].map(handle).dropna())
log.append(f"Repositorio {ANIO_MIN}-{ANIO_MAX}: {n_rango} filas; sin los tipos no-texto: {len(rep)}; "
           f"de ellas pasan Dewey: {sum(handle(h) in pasa for h in rep[c_h])}")
repo_por_handle, repo_por_titulo = {}, {}
for _, r in rep.iterrows():
    h = handle(r[c_h])
    if not h:
        continue
    social = bool(c_c1 and PRIORIDAD_COMM1.search(limpio(r[c_c1])))
    f = {"ID": "REPO-" + h, "Fuente": "Repositorio UNAL", "Grupo": 1 if social else (2 if h in pasa else 3),
         "Título": limpio(r[c_ti]), "Autor": limpio(r[c_au]) if c_au else "", "Año": int(r["_anio"]),
         "Tipo": limpio(r[c_ti_tipo]), "Link": f"https://repositorio.unal.edu.co/handle/{h}",
         "Resumen": armar_resumen(r[c_ab], [("Palabras clave", r[c_su] if c_su else "")])}
    repo_por_handle[h] = f
    repo_por_titulo.setdefault(norm(f["Título"]), []).append(f)
    filas.append(f)


try:
    from rapidfuzz import fuzz, process
    def parecidos(q, claves):
        return [(c, s) for c, s, _ in process.extract(q, claves, scorer=fuzz.token_sort_ratio, limit=3, score_cutoff=85)]
except ImportError:                       # sin rapidfuzz: difflib (más lento, mismo criterio)
    import difflib
    def parecidos(q, claves):
        return [(c, round(difflib.SequenceMatcher(None, q, c).ratio() * 100))
                for c in difflib.get_close_matches(q, claves, n=3, cutoff=0.85)]
claves_repo = [k for k in repo_por_titulo if len(k) >= 20]


def buscar_en_repo(titulo, a, enlace):
    """Devuelve (fila_del_repo, tipo): tipo = 'mismo' o 'posible'."""
    h = handle(enlace) if "repositorio.unal" in str(enlace) else None
    if h and h in repo_por_handle:
        return repo_por_handle[h], "mismo"
    k = norm(titulo)
    for f in repo_por_titulo.get(k, []):
        if len(k) >= 20 and (a is None or abs(f["Año"] - a) <= 1):
            return f, "mismo"
    if len(k) >= 20:
        for c, sc in parecidos(k, claves_repo):
            for f in repo_por_titulo[c]:
                if sc >= 92 and (a is None or abs(f["Año"] - a) <= 1):
                    return f, "mismo"
            return repo_por_titulo[c][0], f"posible ({sc:.0f} %)"
    return None, None


NO_ACADEMICO = re.compile(r"obra art|audiovisual|foro|taller|seminario|c[aá]tedra|diplomado|p[oó]dca|videojuego|"
                          r"obra de teatro|iniciativa|convocatoria|asignatura|evento|prensa|peri[oó]dico|noticia", re.I)
filas_bases = []


bases_por_titulo = {}


def agregar_base(nombre, prefijo, regs):
    nuevos = dup_repo = dup_base = fuera = sin_anio = 0
    for r in regs:
        if r["Año"] is None:
            sin_anio += 1; continue
        if not (ANIO_MIN <= r["Año"] <= ANIO_MAX):
            fuera += 1; continue
        en_repo, tipo = buscar_en_repo(r["Título"], r["Año"], r["Link"])
        if tipo == "mismo":
            if nombre not in en_repo["Fuente"]:
                en_repo["Fuente"] += "; " + nombre
            dup_repo += 1; continue
        obs = []
        if tipo:
            obs.append(f"Posible duplicado de {en_repo['ID']} {tipo}: {en_repo['Título'][:80]}")
        if not r["Link"]:
            obs.append("Sin enlace")
        if NO_ACADEMICO.search(r.get("Tipo", "")):
            obs.append(f"Tipo no académico: {r['Tipo']}")
        r["Observaciones"] = " | ".join(obs)
        k = norm(r["Título"])
        if len(k) < 20:                    # título corto: solo es el mismo si además coincide el año
            k = f"{k}|{r['Año']}"
        if k in bases_por_titulo:
            f = bases_por_titulo[k]
            if nombre not in f["Fuente"]:
                f["Fuente"] += "; " + nombre
            if len(r["Resumen"]) > len(f["Resumen"]):
                f["Resumen"] = r["Resumen"]
            dup_base += 1; continue
        f = {**r, "ID": f"{prefijo}-{r['_id']}", "Fuente": nombre, "Grupo": 4}
        f.pop("_id")
        bases_por_titulo[k] = f
        filas_bases.append(f); nuevos += 1
    log.append(f"{nombre}: {len(regs)} filas | fuera de {ANIO_MIN}-{ANIO_MAX}: {fuera} | sin año: {sin_anio} | "
               f"ya en el repositorio: {dup_repo} | repetidas con otra base: {dup_base} | nuevas: {nuevos}")


def leer_legado(ruta):
    df = pd.read_excel(ruta, sheet_name="Base_Legado_UNAL", dtype=str).dropna(how="all")
    regs = []
    for _, r in df.iterrows():
        t = limpio(r.get("Título del trabajo"))
        if not t:
            continue
        enlace = limpio(r.get("Enlace"))
        regs.append({"_id": limpio(r.get("ID")) or str(len(regs) + 1), "Título": t,
                     "Autor": limpio(r.get("Autor")) or limpio(r.get("Varios Autores*")),
                     "Año": anio(r.get("Año")), "Tipo": limpio(r.get("Tipo de publicación")),
                     "Link": enlace if enlace.startswith("http") else "",
                     "Resumen": armar_resumen(r.get("Síntesis del documento"),
                                              [("Tema principal", r.get("Tema principal")),
                                               ("Temas secundarios", r.get("Temas secundarios")),
                                               ("Enfoque", r.get("Enfoque"))])})
    return regs


def leer_base_final(ruta):
    df = pd.read_excel(ruta, sheet_name="Base datos", dtype=str).dropna(how="all")
    regs = []
    for i, r in df.iterrows():
        t = limpio(r.get("TITULO"))
        if not t:
            continue
        todo = " ".join(limpio(v) for v in r.values)
        ls = re.findall(r"https?://[^\s,;\"'<>]+", todo)
        resumen = " ".join(x for x in [limpio(r.get("RESUMEN")), limpio(r.get("OBJETIVO"))] if x)
        regs.append({"_id": f"fila{i + 2}", "Título": t, "Autor": limpio(r.get("AUTOR")) or limpio(r.get("COORDINADOR")),
                     "Año": anio(r.get("FECHA")), "Tipo": limpio(r.get("TIPO DE APORTE")),
                     "Link": ls[0] if ls else "",
                     "Resumen": armar_resumen(resumen, [("Eje temático", r.get("EJE TEMÁTICO")),
                                                        ("Categoría", r.get("CATEGORÍA"))])})
    return regs


# Primero William (la más nueva y completa), luego el Legado de octubre (se repite mucho con William) y la Base final
if args.william:
    agregar_base("Base William Mancera", "WM", leer_legado(args.william))
if args.legado:
    agregar_base("Base Legado (oct)", "LEG", leer_legado(args.legado))
if args.base_final:
    agregar_base("Base final 2010-2021", "BF", leer_base_final(args.base_final))

GRUPOS = {1: "1 Repositorio (sociales, humanas, artes)", 2: "2 Repositorio (otras facultades, pasa Dewey)",
          3: "3 Repositorio (resto)", 4: "4 Bases de Natalia"}
COLS = ["ID", "Grupo", "Fuente", "Título", "Autor", "Año", "Tipo", "Link", "Resumen"]
repo = pd.DataFrame(filas).sort_values("Grupo", kind="stable")
repo["Grupo"] = repo["Grupo"].map(GRUPOS)
repo[COLS].to_csv("entrada_repo.csv", index=False, encoding="utf-8-sig")
log.append(f"\nentrada_repo.csv: {len(repo)} documentos "
           f"({(repo['Resumen'].str.len() < 100).sum()} con resumen < 100 caracteres → REVISAR sin modelo)")
for g, n in repo["Grupo"].value_counts().sort_index().items():
    log.append(f"  {g}: {n}  (~{n * 3 / 3600:.1f} h a 3 s/doc)")
if filas_bases:
    b = pd.DataFrame(filas_bases)
    b["Grupo"] = b["Grupo"].map(GRUPOS)
    b[COLS + ["Observaciones"]].to_csv("entrada_bases.csv", index=False, encoding="utf-8-sig")
    log.append(f"\nentrada_bases.csv: {len(b)} documentos de las bases que no están en el repositorio")
    for o in ["Posible duplicado", "Sin enlace", "Tipo no académico"]:
        log.append(f"  con '{o}': {b['Observaciones'].str.contains(o).sum()}")
    log.append(f"  sin ninguna observación: {(b['Observaciones'] == '').sum()}")
    ce = b[b["Link"].str.startswith("http")]
    ce[COLS + ["Observaciones"]].to_csv("entrada_bases_con_enlace.csv", index=False, encoding="utf-8-sig")
    log.append(f"entrada_bases_con_enlace.csv: {len(ce)} (solo las que tienen enlace a un documento)")
texto = "\n".join(log)
print(texto)
open("resumen_entrada.txt", "w", encoding="utf-8").write(texto + "\n")
