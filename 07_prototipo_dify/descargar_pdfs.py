"""
Descarga los PDFs del manifiesto (manifiesto_descarga.csv) del repositorio UNAL.
Pensado para correr en el Nodo 10, dentro de tmux.

Para cada fila con estado "pendiente":
  - baja la URL a un archivo temporal (.part),
  - verifica que empiece por %PDF, que el tamano coincida y que el md5 coincida,
  - recien ahi lo renombra a su nombre final ("Titulo (anio).pdf").
Es reanudable: si el archivo final ya existe y su md5 coincide, lo salta.
Los que fallan quedan en resultados_descarga.csv con el motivo; al volver a
correr, se reintentan solos.

Uso:
  python descargar_pdfs.py manifiesto_descarga.csv --prueba       # 5 al azar, en carpeta aparte
  python descargar_pdfs.py manifiesto_descarga.csv --limite 20
  python descargar_pdfs.py manifiesto_descarga.csv                # todos
  python descargar_pdfs.py manifiesto_descarga.csv --hilos 1      # mas suave con el servidor

Salidas: carpeta pdfs_prototipo/ y resultados_descarga.csv
"""
import argparse
import csv
import hashlib
import os
import random
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import requests

TIMEOUT = (15, 120)        # conexion, lectura entre bloques
PAUSA = 0.5                # segundos antes de cada descarga, por hilo
REINTENTOS = 4
BLOQUE = 1024 * 256

_local = threading.local()
_candado = threading.Lock()
_parar = threading.Event()


def sesion():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = "UNAL-por-la-Paz-chatbot/1.0 (descarga de PDFs del piloto)"
    return _local.s


def md5_de(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def bajar(fila, carpeta):
    """Devuelve (estado, detalle). estado: ok | ya_estaba | error"""
    destino = os.path.join(carpeta, fila["nombre_destino"])
    esperado_md5 = (fila.get("md5") or "").strip().lower()
    esperado_bytes = int(float(fila["bytes"])) if fila.get("bytes") else 0

    if os.path.exists(destino) and (not esperado_md5 or md5_de(destino) == esperado_md5):
        return "ya_estaba", ""

    parcial = destino + ".part"
    detalle = ""
    for intento in range(REINTENTOS):
        if _parar.is_set():
            return "error", "interrumpido"
        time.sleep(PAUSA)
        try:
            h = hashlib.md5()
            total = 0
            with sesion().get(fila["url"], stream=True, timeout=TIMEOUT) as r:
                if r.status_code in (401, 403, 404):
                    return "error", f"http_{r.status_code}"          # definitivo
                if r.status_code != 200:
                    detalle = f"http_{r.status_code}"
                    time.sleep(3 * (intento + 1))
                    continue
                with open(parcial, "wb") as f:
                    for b in r.iter_content(BLOQUE):
                        if _parar.is_set():
                            return "error", "interrumpido"
                        f.write(b)
                        h.update(b)
                        total += len(b)
            with open(parcial, "rb") as f:
                cabecera = f.read(5)
            if cabecera != b"%PDF-":
                detalle = "no_es_pdf"
            elif esperado_bytes and total != esperado_bytes:
                detalle = f"tamano_{total}_vs_{esperado_bytes}"
            elif esperado_md5 and h.hexdigest() != esperado_md5:
                detalle = "md5_distinto"
            else:
                os.replace(parcial, destino)
                return "ok", ""
        except (requests.RequestException, OSError) as e:
            detalle = f"red_{type(e).__name__}"
        time.sleep(3 * (intento + 1))
    if os.path.exists(parcial):
        os.remove(parcial)
    return "error", detalle


def trabajo(fila, carpeta, f_res):
    if _parar.is_set():
        return None
    estado, detalle = bajar(fila, carpeta)
    reg = {"id": fila["id"], "handle": fila["handle"], "nombre_destino": fila["nombre_destino"],
           "estado": estado, "detalle": detalle, "hora": time.strftime("%Y-%m-%d %H:%M:%S")}
    with _candado:
        nuevo = not os.path.exists(f_res) or os.path.getsize(f_res) == 0
        with open(f_res, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(reg))
            if nuevo:
                w.writeheader()
            w.writerow(reg)
    return reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifiesto")
    ap.add_argument("--salida", default="pdfs_prototipo")
    ap.add_argument("--hilos", type=int, default=2)
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--prueba", action="store_true", help="5 al azar en pdfs_prueba/")
    args = ap.parse_args()

    with open(args.manifiesto, newline="", encoding="utf-8-sig") as f:
        filas = [r for r in csv.DictReader(f) if r["estado"] == "pendiente"]
    carpeta, f_res = args.salida, "resultados_descarga.csv"
    if args.prueba:
        carpeta, f_res = "pdfs_prueba", "resultados_prueba.csv"
        filas = random.sample(filas, min(5, len(filas)))
    elif args.limite:
        filas = filas[:args.limite]
    os.makedirs(carpeta, exist_ok=True)
    print(f"A descargar: {len(filas)} PDF en ./{carpeta}/ con {args.hilos} hilo(s). "
          "Ctrl+C pausa; se puede reanudar.")

    n, t0, hechos, cuenta = len(filas), time.time(), 0, {"ok": 0, "ya_estaba": 0, "error": 0}
    ex = ThreadPoolExecutor(max_workers=max(1, args.hilos))
    futuros = {ex.submit(trabajo, fila, carpeta, f_res) for fila in filas}
    try:
        while futuros:
            listos, futuros = wait(futuros, timeout=1, return_when=FIRST_COMPLETED)
            for reg in (f.result() for f in listos):
                if reg is None:
                    continue
                hechos += 1
                cuenta[reg["estado"]] += 1
                if reg["estado"] == "error":
                    print(f"  ERROR {reg['handle']}: {reg['detalle']}", flush=True)
                if args.prueba or hechos % 25 == 0 or hechos == n:
                    resta = (n - hechos) * (time.time() - t0) / hechos / 60
                    print(f"  {hechos}/{n} | ok {cuenta['ok']} | ya estaban {cuenta['ya_estaba']} | "
                          f"errores {cuenta['error']} | ~{resta:.0f} min restantes", flush=True)
    except KeyboardInterrupt:
        _parar.set()
        print("\nPausando... vuelve a correrlo para seguir.")
        ex.shutdown(wait=True, cancel_futures=True)
        sys.exit(0)
    ex.shutdown()
    print(f"\nListo. ok {cuenta['ok']} | ya estaban {cuenta['ya_estaba']} | errores {cuenta['error']}."
          f" Detalle en {f_res}")


if __name__ == "__main__":
    main()
