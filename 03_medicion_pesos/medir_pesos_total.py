"""
Mide el peso REAL de los archivos de TODOS los candidatos (candidatos.csv),
consultando la API del repositorio. No descarga ningún archivo: solo lee la
"ficha" de cada uno, que trae su tamaño.

Cadena por ítem (2 pasos):
  1) handle  ->  /pid/find?id=unal/76174          -> ficha del ítem (uuid, links)
  2) ítem    ->  .../bundles?embed=bitstreams      -> paquetes y sus archivos
               ORIGINAL = archivos que subió el autor (lo que pesa)
               TEXT     = texto extraído del PDF por el repositorio (si existe)
  Si el servidor no devuelve los archivos embebidos, el script los pide aparte
  por el link de cada paquete (un paso más), así que el resultado es el mismo.

Uso:
  pip install pandas requests
  python medir_pesos_total.py --prueba         # 5 ítems, para verificar
  python medir_pesos_total.py                  # todos los candidatos
  python medir_pesos_total.py --hilos 1        # más lento y más suave con el servidor
  python medir_pesos_total.py --solo-resumen   # rehace el resumen sin consultar nada

Es reanudable: guarda cada ítem apenas lo mide. Si se corta (Ctrl+C, se va la
luz, se cae internet) lo vuelves a correr y sigue donde iba; los que fallaron
por red se reintentan solos.

Salidas:
  pesos_items.csv           una fila por ítem (peso, n.º de archivos, estado)
  pesos_archivos.csv        una fila por archivo (nombre, tamaño, link de descarga)
  resumen_pesos_total.txt   estadísticas
"""
import argparse
import csv
import os
import re
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import pandas as pd
import requests

API = "https://bffrepositorio.unal.edu.co/server/api"
PAUSA = 0.2            # segundos antes de cada petición, por hilo
TIMEOUT = 30
HILOS = 3              # peticiones en paralelo (no subir mucho: es un servidor de la U)
BUNDLES_MEDIDOS = ("ORIGINAL", "TEXT")

F_ITEMS = "pesos_items.csv"
F_ARCHIVOS = "pesos_archivos.csv"
F_RESUMEN = "resumen_pesos_total.txt"
COLS_ITEMS = ["handle", "uuid", "tipo", "anio", "titulo", "estado", "n_archivos", "n_pdf",
              "bytes", "bytes_pdf", "n_texto", "bytes_texto", "bundles"]
COLS_ARCHIVOS = ["handle", "bundle", "nombre", "ext", "bytes", "bitstream_uuid", "md5",
                 "url_descarga"]
MB, GB = 1024 ** 2, 1024 ** 3

_local = threading.local()
_candado = threading.Lock()
_parar = threading.Event()


# ----------------------------------------------------------------- consulta API
def sesion():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = ("UNAL-por-la-Paz-chatbot/1.0 "
                                          "(medicion de almacenamiento)")
    return _local.s


def get(url):
    """JSON de la URL, o {'_error': código}. Reintenta fallos de red y 429/5xx."""
    for intento in range(4):
        time.sleep(PAUSA)
        espera = 3 * (intento + 1)
        try:
            r = sesion().get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 204 or (400 <= r.status_code < 500 and r.status_code != 429):
                return {"_error": r.status_code}        # definitivo: no existe / restringido
            try:                                        # 429 o 5xx: el servidor pide calma
                espera = min(120, max(espera, int(r.headers.get("Retry-After", 0))))
            except ValueError:
                pass
        except (requests.RequestException, ValueError):
            pass
        time.sleep(espera)
    return {"_error": "red"}


def con_parametros(url, extra):
    return url + ("&" if "?" in url else "?") + extra


def bitstreams_de(bundle):
    """Lista de archivos de un paquete, o {'_error': ...}."""
    emb = bundle.get("_embedded", {}).get("bitstreams")
    if isinstance(emb, dict):                           # vinieron embebidos
        lista = emb.get("_embedded", {}).get("bitstreams", [])
        if emb.get("page", {}).get("totalElements", len(lista)) <= len(lista):
            return lista
    url = bundle.get("_links", {}).get("bitstreams", {}).get("href")
    if not url:
        return {"_error": "sin_link"}
    url, lista = con_parametros(url, "size=100"), []
    while url:                                          # puede venir paginado
        pag = get(url)
        if "_error" in pag:
            return pag
        lista += pag.get("_embedded", {}).get("bitstreams", [])
        url = pag.get("_links", {}).get("next", {}).get("href")
    return lista


def medir(handle):
    """Devuelve (registro del ítem, lista de archivos)."""
    item = get(f"{API}/pid/find?id={handle}")
    if "_error" in item:
        return {"estado": f"item_{item['_error']}"}, []
    reg = {"uuid": item.get("uuid", ""), "_titulo_api": item.get("name", "")}
    url = item.get("_links", {}).get("bundles", {}).get("href")
    if not url:
        return {**reg, "estado": "sin_link_bundles"}, []

    url, bundles = con_parametros(url, "size=100&embed=bitstreams"), []
    while url:
        pag = get(url)
        if "_error" in pag:
            return {**reg, "estado": f"bundles_{pag['_error']}"}, []
        bundles += pag.get("_embedded", {}).get("bundles", [])
        url = pag.get("_links", {}).get("next", {}).get("href")

    archivos = []
    for b in bundles:
        if b.get("name") not in BUNDLES_MEDIDOS:
            continue
        lista = bitstreams_de(b)
        if isinstance(lista, dict):
            return {**reg, "estado": f"bitstreams_{lista['_error']}"}, []
        for f in lista:
            nombre = str(f.get("name") or "")
            ext = os.path.splitext(nombre)[1].lower().lstrip(".") or "(sin ext)"
            archivos.append({
                "handle": handle, "bundle": b["name"], "nombre": nombre, "ext": ext,
                "bytes": int(f.get("sizeBytes") or 0),
                "bitstream_uuid": f.get("uuid", ""),
                "md5": (f.get("checkSum") or {}).get("value", ""),
                "url_descarga": f.get("_links", {}).get("content", {}).get("href", "")})

    orig = [a for a in archivos if a["bundle"] == "ORIGINAL"]
    texto = [a for a in archivos if a["bundle"] == "TEXT"]
    pdfs = [a for a in orig if a["ext"] == "pdf"]
    reg.update(estado="ok", n_archivos=len(orig), n_pdf=len(pdfs),
               bytes=sum(a["bytes"] for a in orig), bytes_pdf=sum(a["bytes"] for a in pdfs),
               n_texto=len(texto), bytes_texto=sum(a["bytes"] for a in texto),
               bundles="|".join(sorted(str(b.get("name")) for b in bundles)))
    return reg, archivos


# ------------------------------------------------------------------- utilidades
def extraer_handle(valor):
    # ".../handle/unal/76174" o "unal/76174" -> "unal/76174"
    m = re.search(r"([A-Za-z0-9.]+/\d+)\s*$", str(valor).strip())
    return m.group(1) if m else None


def es_final(estado):
    """ok, o un error que no cambia al reintentar (no existe, restringido)."""
    return estado == "ok" or bool(re.search(r"_(204|4\d\d)$", str(estado)))


def guardar(ruta, columnas, filas):
    nuevo = not os.path.exists(ruta) or os.path.getsize(ruta) == 0
    with open(ruta, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def columna(df, *nombres):
    for n in nombres:
        for c in df.columns:
            if c.strip().lower() == n:
                return c
    return None


def tipo_limpio(t):
    """Unifica etiquetas que son lo mismo escritas distinto."""
    if pd.isna(t) or not str(t).strip() or str(t).strip().lower() == "nan":
        return "(sin tipo)"
    s = re.sub(r"\s+", " ", str(t).replace("–", "-").replace("—", "-")).strip()
    k = s.casefold()
    if k in ("otro", "otros"):
        return "Otro"
    if k == "libro completo":
        return "Libro"
    return s[0].upper() + s[1:]


def grupo(tipo):
    k = tipo.casefold()
    if k.startswith("trabajo de grado"):
        return "Tesis y trabajos de grado"
    if k.startswith(("libro", "capítulo")):
        return "Libros y capítulos"
    if k.startswith(("artículo", "revista", "boletín")):
        return "Artículos y revistas"
    return "Otros documentos"


def fmt(b):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024 or u == "TB":
            return f"{b:,.1f} {u}"
        b /= 1024


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "–"


def cargar_candidatos():
    df = pd.read_csv("candidatos.csv", dtype=str)
    c_handle, c_tipo = columna(df, "handle"), columna(df, "tipo")
    c_titulo, c_anio = columna(df, "título", "titulo"), columna(df, "anio", "año")
    if not c_handle:
        sys.exit("candidatos.csv no tiene columna 'handle'")
    base = pd.DataFrame({
        "handle": df[c_handle].map(extraer_handle),
        "tipo": (df[c_tipo] if c_tipo else pd.Series("", index=df.index)).map(tipo_limpio),
        "anio": df[c_anio].fillna("") if c_anio else "",
        "titulo": (df[c_titulo].fillna("") if c_titulo else pd.Series("", index=df.index))
        .map(lambda s: re.sub(r"\s+", " ", str(s)).strip()),
    })
    sin_h = int(base["handle"].isna().sum())
    base = base.dropna(subset=["handle"])
    dup = int(base["handle"].duplicated().sum())
    base = base.drop_duplicates("handle").reset_index(drop=True)
    return base, len(df), sin_h, dup


def cargar_medidos(ruta=F_ITEMS):
    if not os.path.exists(ruta):
        return pd.DataFrame(columns=COLS_ITEMS)
    det = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
    det = det.drop_duplicates("handle", keep="last")      # el último intento manda
    for c in ("n_archivos", "n_pdf", "bytes", "bytes_pdf", "n_texto", "bytes_texto"):
        det[c] = pd.to_numeric(det[c], errors="coerce").fillna(0).astype("int64")
    return det


# --------------------------------------------------------------------- resumen
def tabla_por(ok, col, total):
    filas = [f"  {col.capitalize():38} {'ítems':>6} {'% ítems':>8} {'peso':>10} {'% peso':>7} "
             f"{'media MB':>9} {'mediana':>8} {'p90':>8} {'máx MB':>9}"]
    orden = ok.groupby(col)["bytes"].sum().sort_values(ascending=False).index
    for k in orden:
        g = ok[ok[col] == k]
        mb = g["bytes"] / MB
        filas.append(f"  {str(k)[:38]:38} {len(g):6} {pct(len(g), len(ok)):>8} "
                     f"{fmt(g['bytes'].sum()):>10} {pct(g['bytes'].sum(), total):>7} "
                     f"{mb.mean():9.2f} {mb.median():8.2f} {mb.quantile(.9):8.2f} {mb.max():9.1f}")
    return filas


def resumen(base, n_csv, sin_h, dup):
    det = cargar_medidos()
    det = det[det["handle"].isin(set(base["handle"]))]
    todo = base.merge(det.drop(columns=["tipo", "anio", "titulo"], errors="ignore"),
                      on="handle", how="left")
    todo["estado"] = todo["estado"].fillna("pendiente")
    todo["grupo"] = todo["tipo"].map(grupo)
    ok = todo[todo["estado"] == "ok"].copy()
    L = []

    # 1. cobertura
    otros = todo.loc[~todo["estado"].isin(["ok", "pendiente"]), "estado"].value_counts()
    L += ["== 1. COBERTURA ==",
          f"  Filas en candidatos.csv: {n_csv}  (sin handle: {sin_h}, handles repetidos: {dup})",
          f"  Ítems a medir: {len(todo)}",
          f"  Medidos bien: {len(ok)} ({pct(len(ok), len(todo))})",
          f"  Pendientes: {(todo.estado == 'pendiente').sum()}",
          f"  Con error: {int(otros.sum())}  {otros.to_dict() if len(otros) else ''}",
          "    (…_401/_403 = archivo restringido o en embargo; …_404 = ya no existe;"
          " …_red = falló la conexión, se reintenta al volver a correr)", ""]
    if ok.empty:
        return "\n".join(L + ["Todavía no hay ítems medidos."])

    total, total_pdf = int(ok["bytes"].sum()), int(ok["bytes_pdf"].sum())
    mb = ok["bytes"] / MB
    con_arch = ok[ok["n_archivos"] > 0]

    # 2. totales
    L += ["== 2. PESO TOTAL (archivos originales de los ítems medidos) ==",
          f"  TOTAL: {fmt(total)}  en {int(ok['n_archivos'].sum())} archivos de "
          f"{len(con_arch)} ítems",
          f"  Solo PDF: {fmt(total_pdf)} ({pct(total_pdf, total)})   |   "
          f"otros formatos: {fmt(total - total_pdf)}"]
    for umbral in (100, 500):
        g = ok[mb > umbral]
        L.append(f"  Sin los ítems de más de {umbral} MB ({len(g)}): "
                 f"{fmt(total - g['bytes'].sum())}  (ellos solos pesan {fmt(g['bytes'].sum())})")
    L += [f"  Ítems sin ningún archivo (solo ficha): {(ok.n_archivos == 0).sum()} "
          f"({pct((ok.n_archivos == 0).sum(), len(ok))})",
          f"  Ítems con archivos pero sin PDF: {((ok.n_archivos > 0) & (ok.n_pdf == 0)).sum()}",
          f"  Ítems con más de un archivo: {(ok.n_archivos > 1).sum()} "
          f"(máximo {int(ok.n_archivos.max())} archivos en un ítem)", ""]

    # 3. dispersión
    cv = mb.std() / mb.mean() if mb.mean() else float("nan")
    L += ["== 3. TAMAÑO POR ÍTEM (MB) ==",
          f"  media {mb.mean():.2f} | mediana {mb.median():.2f} | desv. {mb.std():.2f} | CV {cv:.2f}",
          "  percentiles: " + " | ".join(f"p{q}: {mb.quantile(q / 100):.2f}"
                                        for q in (10, 25, 50, 75, 90, 95, 99)),
          f"  mínimo {mb.min():.2f} | máximo {mb.max():.2f}", "",
          f"  {'Rango':16} {'ítems':>6} {'% ítems':>8} {'peso':>10} {'% peso':>7}"]
    cortes = [(None, 0, "sin archivo"), (0, 1, "hasta 1 MB"), (1, 5, "1 – 5 MB"),
              (5, 20, "5 – 20 MB"), (20, 50, "20 – 50 MB"), (50, 100, "50 – 100 MB"),
              (100, 500, "100 – 500 MB"), (500, None, "más de 500 MB")]
    for lo, hi, nombre in cortes:
        m = (mb == 0) if lo is None else (mb > lo) & ((mb <= hi) if hi else True)
        L.append(f"  {nombre:16} {m.sum():6} {pct(m.sum(), len(ok)):>8} "
                 f"{fmt(ok.loc[m, 'bytes'].sum()):>10} {pct(ok.loc[m, 'bytes'].sum(), total):>7}")

    # 4. concentración
    orden = ok["bytes"].sort_values(ascending=False).reset_index(drop=True)
    acum = orden.cumsum()
    L += ["", "== 4. CONCENTRACIÓN (¿pocos ítems pesan casi todo?) =="]
    for p in (1, 5, 10, 20):
        k = max(1, round(len(orden) * p / 100))
        L.append(f"  El {p}% más pesado ({k} ítems) = {pct(acum.iloc[k - 1], total)} del peso")
    for p in (50, 80):
        k = int((acum >= total * p / 100).values.argmax()) + 1
        L.append(f"  El {p}% del peso está en solo {k} ítems ({pct(k, len(orden))} del total)")

    # 5-6. por grupo y por tipo
    L += ["", "== 5. POR GRUPO =="] + tabla_por(ok, "grupo", total)
    L += ["", "== 6. POR TIPO (etiquetas unificadas) =="] + tabla_por(ok, "tipo", total)

    # 7. por año
    if ok["anio"].astype(str).str.strip().any():
        L += ["", "== 7. POR AÑO DEL DOCUMENTO ==",
              f"  {'Año':6} {'ítems':>6} {'peso':>10} {'media MB':>9}"]
        for a, g in ok.groupby(ok["anio"].astype(str).str[:4]):
            L.append(f"  {a or '(s/a)':6} {len(g):6} {fmt(g['bytes'].sum()):>10} "
                     f"{g['bytes'].mean() / MB:9.2f}")

    # 8. ítems más pesados
    L += ["", "== 8. LOS 30 ÍTEMS MÁS PESADOS ==",
          f"  {'#':>2} {'MB':>9} {'arch':>4}  {'handle':13} {'tipo':28} título"]
    for i, (_, r) in enumerate(ok.sort_values("bytes", ascending=False).head(30).iterrows(), 1):
        L.append(f"  {i:2} {r['bytes'] / MB:9.1f} {int(r['n_archivos']):4}  {r['handle']:13} "
                 f"{r['tipo'][:28]:28} {r['titulo'][:70]}")

    # 9-10. archivos
    if os.path.exists(F_ARCHIVOS):
        arch = pd.read_csv(F_ARCHIVOS, dtype=str, encoding="utf-8-sig")
        arch = arch.drop_duplicates(["handle", "bundle", "bitstream_uuid"])
        arch = arch[arch["handle"].isin(set(ok["handle"]))]
        arch["bytes"] = pd.to_numeric(arch["bytes"], errors="coerce").fillna(0)
        orig = arch[arch["bundle"] == "ORIGINAL"]
        L += ["", "== 9. LOS 20 ARCHIVOS INDIVIDUALES MÁS PESADOS ==",
              f"  {'#':>2} {'MB':>9}  {'handle':13} nombre del archivo"]
        for i, (_, r) in enumerate(orig.sort_values("bytes", ascending=False).head(20).iterrows(), 1):
            L.append(f"  {i:2} {r['bytes'] / MB:9.1f}  {r['handle']:13} {str(r['nombre'])[:80]}")
        L += ["", "== 10. FORMATOS DE ARCHIVO ==",
              f"  {'ext':10} {'archivos':>8} {'% arch':>7} {'peso':>10} {'% peso':>7}"]
        ext = orig.groupby("ext")["bytes"].agg(["count", "sum"]).sort_values("sum", ascending=False)
        for e, r in ext.head(12).iterrows():
            L.append(f"  {str(e)[:10]:10} {int(r['count']):8} {pct(r['count'], len(orig)):>7} "
                     f"{fmt(r['sum']):>10} {pct(r['sum'], orig['bytes'].sum()):>7}")

    # 11. texto extraído
    con_pdf = ok[ok["n_pdf"] > 0]
    con_txt = con_pdf[con_pdf["n_texto"] > 0]
    L += ["", "== 11. TEXTO EXTRAÍDO POR EL REPOSITORIO (paquete TEXT) =="]
    if con_txt.empty:
        L.append("  Ningún ítem lo trae visible: el repositorio no lo publica o no lo genera."
                 " El texto habrá que sacarlo de los PDF.")
    else:
        t = int(con_txt["bytes_texto"].sum())
        L += [f"  Ítems con PDF que traen texto extraído: {len(con_txt)} de {len(con_pdf)} "
              f"({pct(len(con_txt), len(con_pdf))})",
              f"  Texto total: {fmt(t)}  (~{t / 4 / 1e6:,.0f} millones de tokens, "
              f"a ojo: 4 bytes por token)",
              f"  Texto por ítem: mediana {con_txt['bytes_texto'].median() / 1024:,.0f} KB | "
              f"p90 {con_txt['bytes_texto'].quantile(.9) / 1024:,.0f} KB",
              f"  El texto es {pct(t, con_txt['bytes_pdf'].sum())} del peso de esos PDF",
              f"  Ítems con PDF y SIN texto extraído: {len(con_pdf) - len(con_txt)} "
              f"(posibles PDF escaneados que necesitarían OCR; hay que confirmarlo)"]
    return "\n".join(L)


# ------------------------------------------------------------------------ main
def trabajo(fila, f_items, f_archivos):
    if _parar.is_set():
        return None
    reg, archivos = medir(fila["handle"])
    reg = {**fila, **reg}
    if not reg.get("titulo"):
        reg["titulo"] = reg.get("_titulo_api", "")
    with _candado:
        if archivos:
            guardar(f_archivos, COLS_ARCHIVOS, archivos)
        guardar(f_items, COLS_ITEMS, [reg])
    return reg


def main():
    global API
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true", help="mide solo 5 ítems al azar")
    ap.add_argument("--solo-resumen", action="store_true")
    ap.add_argument("--hilos", type=int, default=HILOS)
    ap.add_argument("--api", default=API, help=argparse.SUPPRESS)
    args = ap.parse_args()
    API = args.api.rstrip("/")
    for flujo in (sys.stdout, sys.stderr):                # tildes en la consola de Windows
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")

    base, n_csv, sin_h, dup = cargar_candidatos()
    print(f"Candidatos: {len(base)} handles únicos (ej.: {base['handle'].head(3).tolist()})")

    if args.prueba:
        f_items, f_archivos = "prueba_items.csv", "prueba_archivos.csv"
        for f in (f_items, f_archivos):
            if os.path.exists(f):
                os.remove(f)
        pendientes = base.sample(n=min(5, len(base)), random_state=int(time.time()))
    else:
        f_items, f_archivos = F_ITEMS, F_ARCHIVOS
        det = cargar_medidos()
        hechos = set(det.loc[det["estado"].map(es_final), "handle"])
        pendientes = base[~base["handle"].isin(hechos)]
        if hechos:
            print(f"Reanudando: {len(hechos)} ya medidos")

    if not args.solo_resumen and len(pendientes):
        n, t0, hechos_n, errores, acum = len(pendientes), time.time(), 0, 0, 0
        print(f"Por medir: {n} con {args.hilos} hilo(s). Ctrl+C para pausar; se puede reanudar.")
        ex = ThreadPoolExecutor(max_workers=max(1, args.hilos))
        futuros = {ex.submit(trabajo, fila, f_items, f_archivos)
                   for fila in pendientes.to_dict("records")}
        try:
            while futuros:
                # espera con tope de 1 s: así Ctrl+C también responde en Windows
                listos, futuros = wait(futuros, timeout=1, return_when=FIRST_COMPLETED)
                for reg in (f.result() for f in listos):
                    if reg is None:
                        continue
                    hechos_n += 1
                    errores += reg["estado"] != "ok"
                    acum += int(reg.get("bytes") or 0)
                    if args.prueba:
                        print(f"  {reg['handle']}: {reg['estado']} | {reg.get('n_archivos', 0)} "
                              f"archivo(s) | {fmt(int(reg.get('bytes') or 0))} | "
                              f"texto: {fmt(int(reg.get('bytes_texto') or 0))} | "
                              f"paquetes: {reg.get('bundles', '')}")
                    elif hechos_n % 100 == 0 or hechos_n == n:
                        resta = (n - hechos_n) * (time.time() - t0) / hechos_n / 60
                        print(f"  {hechos_n}/{n} ({pct(hechos_n, n)}) | {fmt(acum)} en esta corrida | "
                              f"errores: {errores} | ~{resta:.0f} min restantes", flush=True)
        except KeyboardInterrupt:
            _parar.set()
            print("\nPausando (termina las peticiones en curso)… Vuelve a correrlo para seguir.")
            ex.shutdown(wait=True, cancel_futures=True)
            sys.exit(0)
        ex.shutdown()

    if args.prueba:
        print("\nPrueba lista (prueba_items.csv, prueba_archivos.csv). "
              "Si se ven tamaños, corre sin --prueba.")
        return
    texto = resumen(base, n_csv, sin_h, dup)
    print("\n" + texto)
    with open(F_RESUMEN, "w", encoding="utf-8-sig") as f:
        f.write(texto + "\n")
    print(f"\nListo: {F_ITEMS}, {F_ARCHIVOS} y {F_RESUMEN}")


if __name__ == "__main__":
    main()