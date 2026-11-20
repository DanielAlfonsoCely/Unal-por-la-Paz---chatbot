"""
Estima el peso total de los archivos (bundle ORIGINAL) de los candidatos,
consultando la API del repositorio con una MUESTRA estratificada por Tipo.

Cadena por ítem (verificada):  handle -> /pid/find -> ítem -> bundles -> ORIGINAL
                               -> bitstreams -> sizeBytes

Uso:
  pip install pandas requests
  python medir_pesos.py --prueba        # 5 ítems, para verificar que todo funciona
  python medir_pesos.py                 # muestra de 500 (por defecto)
  python medir_pesos.py --n 800         # otra cantidad

Es reanudable: guarda cada ítem en muestra_pesos.csv apenas lo mide; si lo
cortas (Ctrl+C) y lo vuelves a correr, sigue donde iba.
Salidas: muestra_pesos.csv (detalle) y resumen_pesos.txt (estadísticas).
"""
import argparse
import os
import random
import re
import sys
import time

import pandas as pd
import requests

API = "https://bffrepositorio.unal.edu.co/server/api"
PAUSA = 0.2          # segundos entre peticiones (ser amables con el servidor)
TIMEOUT = 30
SEMILLA = 42
DETALLE = "muestra_pesos.csv"

sesion = requests.Session()
sesion.headers["User-Agent"] = "UNAL-por-la-Paz-chatbot/1.0 (estimacion de almacenamiento)"


def get(url):
    time.sleep(PAUSA)
    for intento in range(3):
        try:
            r = sesion.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 401, 403):
                return {"_error": r.status_code}
        except requests.RequestException:
            pass
        time.sleep(2 * (intento + 1))
    return {"_error": "red"}


def extraer_handle(valor):
    # ".../handle/unal/76174" o "unal/76174" -> "unal/76174"
    m = re.search(r"([A-Za-z0-9.]+/\d+)\s*$", str(valor).strip())
    return m.group(1) if m else None


def medir(handle):
    """Devuelve dict con n_archivos, n_pdf, bytes, estado."""
    item = get(f"{API}/pid/find?id={handle}")
    if "_error" in item:
        return {"estado": f"item_{item['_error']}"}
    url_bundles = item.get("_links", {}).get("bundles", {}).get("href")
    if not url_bundles:
        return {"estado": "sin_link_bundles"}
    bundles = get(url_bundles)
    if "_error" in bundles:
        return {"estado": f"bundles_{bundles['_error']}"}
    original = [b for b in bundles.get("_embedded", {}).get("bundles", [])
                if b.get("name") == "ORIGINAL"]
    if not original:
        return {"estado": "ok", "n_archivos": 0, "n_pdf": 0, "bytes": 0}
    total = n = n_pdf = 0
    for b in original:
        url_bs = b["_links"]["bitstreams"]["href"]
        url_bs += ("&" if "?" in url_bs else "?") + "size=100"
        while url_bs:                                   # puede venir paginado
            bs = get(url_bs)
            if "_error" in bs:
                return {"estado": f"bitstreams_{bs['_error']}"}
            for f in bs.get("_embedded", {}).get("bitstreams", []):
                total += int(f.get("sizeBytes") or 0)
                n += 1
                n_pdf += str(f.get("name", "")).lower().endswith(".pdf")
            url_bs = bs.get("_links", {}).get("next", {}).get("href")
    return {"estado": "ok", "n_archivos": n, "n_pdf": n_pdf, "bytes": total}


def muestra_estratificada(df, col_tipo, n):
    """Proporcional por Tipo, mínimo 5 por estrato (o todos si tiene menos)."""
    grupos = df.groupby(col_tipo, dropna=False)
    partes = []
    for _, g in grupos:
        k = max(min(5, len(g)), round(n * len(g) / len(df)))
        partes.append(g.sample(n=min(k, len(g)), random_state=SEMILLA))
    return pd.concat(partes)


def fmt(b):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024 or u == "TB":
            return f"{b:,.1f} {u}"
        b /= 1024


def resumen(df_cand, col_tipo, det):
    ok = det[det["estado"] == "ok"].copy()
    ok["mb"] = ok["bytes"] / 1024 ** 2
    lineas = [f"Candidatos totales: {len(df_cand)}",
              f"Muestra medida: {len(det)}  (ok: {len(ok)}, con error: {len(det) - len(ok)})",
              f"Errores por tipo: {det.loc[det.estado != 'ok', 'estado'].value_counts().to_dict()}",
              f"Ítems sin archivos: {(ok.n_archivos == 0).sum()} "
              f"({(ok.n_archivos == 0).mean() * 100:.1f}%)",
              f"Ítems sin PDF: {(ok.n_pdf == 0).sum()} ({(ok.n_pdf == 0).mean() * 100:.1f}%)", ""]

    # dispersión global
    s = ok["mb"]
    cv = s.std() / s.mean() if s.mean() else float("nan")
    lineas += ["== Tamaño por ítem (MB) – muestra completa ==",
               f"  media {s.mean():.2f} | mediana {s.median():.2f} | desv. {s.std():.2f} | CV {cv:.2f}",
               "  percentiles: " + " | ".join(f"p{q}: {s.quantile(q / 100):.2f}"
                                             for q in (10, 25, 50, 75, 90, 95, 99)),
               f"  mínimo {s.min():.2f} | máximo {s.max():.2f}",
               "  (CV < 0.5: tamaños parecidos, el promedio es confiable; CV > 1: muy dispersos,"
               " mirar la mediana y el intervalo)", ""]

    # por Tipo + estimación estratificada del total
    N = df_cand[col_tipo].fillna("nan").value_counts()
    ok["tipo"] = ok[col_tipo].fillna("nan")
    lineas.append("== Por Tipo ==")
    lineas.append(f"  {'Tipo':40} {'N':>6} {'n':>4} {'media MB':>9} {'mediana':>8} {'p90':>8} {'CV':>5}")
    for t, g in ok.groupby("tipo"):
        m = g["mb"]
        cvt = m.std() / m.mean() if m.mean() and len(m) > 1 else float("nan")
        lineas.append(f"  {str(t)[:40]:40} {N.get(t, 0):6} {len(m):4} {m.mean():9.2f} "
                      f"{m.median():8.2f} {m.quantile(.9):8.2f} {cvt:5.2f}")

    def total_estratificado(datos):
        tot = 0.0
        for t, n_h in N.items():
            g = datos[datos["tipo"] == t]["bytes"]
            media = g.mean() if len(g) else datos["bytes"].mean()   # estrato sin muestra
            tot += n_h * media
        return tot

    est = total_estratificado(ok)
    rng = random.Random(SEMILLA)
    boots = []
    grupos = {t: g for t, g in ok.groupby("tipo")}
    for _ in range(1000):
        remuestra = pd.concat([g.sample(n=len(g), replace=True,
                                        random_state=rng.randint(0, 10 ** 9))
                               for g in grupos.values()])
        boots.append(total_estratificado(remuestra))
    boots = pd.Series(boots)
    lineas += ["", "== ESTIMACIÓN DEL TOTAL (todos los candidatos) ==",
               f"  Total estimado: {fmt(est)}",
               f"  Intervalo 95%: {fmt(boots.quantile(.025))} – {fmt(boots.quantile(.975))}",
               "  (se estima con la media de cada Tipo × cuántos candidatos hay de ese Tipo;"
               " la mediana NO sirve para totales porque ignora los archivos grandes)"]
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--prueba", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv("candidatos.csv", dtype=str)
    col_handle = next(c for c in df.columns if c.strip().lower() == "handle")
    col_tipo = next(c for c in df.columns if c.strip().lower() == "tipo")
    df["_handle"] = df[col_handle].map(extraer_handle)
    sin_h = df["_handle"].isna().sum()
    if sin_h:
        print(f"Aviso: {sin_h} candidatos sin handle reconocible (se excluyen de la muestra)")
    print("Ejemplos de handle:", df[col_handle].dropna().head(3).tolist(),
          "->", df["_handle"].dropna().head(3).tolist())

    base = df.dropna(subset=["_handle"])
    muestra = (base.sample(n=5, random_state=SEMILLA) if args.prueba
               else muestra_estratificada(base, col_tipo, args.n))

    hechos = set()
    if os.path.exists(DETALLE) and not args.prueba:
        hechos = set(pd.read_csv(DETALLE, dtype=str)["handle"])
        print(f"Reanudando: {len(hechos)} ya medidos")

    pendientes = muestra[~muestra["_handle"].isin(hechos)]
    print(f"Por medir: {len(pendientes)} (~{len(pendientes) * 4 * PAUSA / 60 + len(pendientes) * 0.02:.0f}+ min)")
    salida = "prueba_pesos.csv" if args.prueba else DETALLE
    t0 = time.time()
    try:
        for i, (_, fila) in enumerate(pendientes.iterrows(), 1):
            r = medir(fila["_handle"])
            reg = {"handle": fila["_handle"], col_tipo: fila[col_tipo], **r}
            pd.DataFrame([reg]).to_csv(salida, mode="a", index=False,
                                       header=not os.path.exists(salida), encoding="utf-8")
            if args.prueba:
                print(f"  {fila['_handle']}: {r}")
            elif i % 25 == 0 or i == len(pendientes):
                vel = (time.time() - t0) / i
                print(f"  {i}/{len(pendientes)}  ~{(len(pendientes) - i) * vel / 60:.1f} min restantes")
    except KeyboardInterrupt:
        print("\nInterrumpido. Vuelve a correrlo para continuar.")
        sys.exit(0)

    if args.prueba:
        print("\nPrueba lista (prueba_pesos.csv). Si se ven tamaños, corre sin --prueba.")
        return
    det = pd.read_csv(DETALLE)
    det["handle"] = det["handle"].astype(str)
    det = det[det["handle"].isin(set(muestra["_handle"]))]
    for c in ("bytes", "n_archivos", "n_pdf"):
        det[c] = pd.to_numeric(det.get(c), errors="coerce").fillna(0)
    texto = resumen(base, col_tipo, det)
    print("\n" + texto)
    with open("resumen_pesos.txt", "w", encoding="utf-8") as f:
        f.write(texto)
    print("\nListo: muestra_pesos.csv y resumen_pesos.txt")


if __name__ == "__main__":
    main()