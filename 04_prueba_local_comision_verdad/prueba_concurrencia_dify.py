"""
Prueba de concurrencia PASANDO POR DIFY (el camino real de un usuario):
pregunta -> Dify -> embedding con bge-m3 -> busqueda en la base -> proxy -> gemma4.

Simula N usuarios preguntando al mismo tiempo a la app publicada, por la API
de Dify. Cada peticion es una conversacion nueva (sin historial).

Antes de correrlo:
  1. En Dify, en la app: Publicar -> "Acceder a la referencia de la API" ->
     arriba a la derecha "Clave de API" -> crear una (empieza por "app-").
  2. Tener abierto el proxy (python proxy_nothink.py).

Uso (en la torre):
    python prueba_concurrencia_dify.py --key app-XXXXXXXX
    python prueba_concurrencia_dify.py --key app-XXXX --niveles 1 5 10 --pausa 10
    (o poner la clave en la variable DIFY_API_KEY)

Guarda dos CSV (detalle y resumen) en la carpeta "resultados" junto al script.
Solo libreria estandar.
"""
import argparse
import csv
import http.client
import json
import os
import statistics
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 30 preguntas distintas, para que cada usuario traiga fragmentos distintos
# (como en la vida real). Con los niveles 1+5+10+15+20 = 51 peticiones, a partir
# de la 31 se repiten; la columna "repetida" lo marca.
PREGUNTAS = [
    "¿Qué dice el informe sobre la concentración de la tierra en Colombia?",
    "¿Cuál fue el balance de la reforma agraria y del Incora?",
    "¿Cómo afectó el despojo de tierras a las mujeres campesinas?",
    "¿Qué dice el informe sobre el catastro multipropósito y el acceso a la tierra?",
    "¿Qué recomienda la Comisión sobre la restitución de tierras?",
    "¿Qué papel tuvo la ANUC en las luchas campesinas?",
    "¿Cómo afectó el conflicto armado a los pueblos indígenas?",
    "¿Qué dice el informe sobre el desplazamiento forzado?",
    "¿Qué responsabilidades atribuye el informe a los grupos paramilitares?",
    "¿Qué dice el informe sobre las ejecuciones extrajudiciales conocidas como falsos positivos?",
    "¿Cómo afectó el conflicto a las comunidades afrodescendientes?",
    "¿Qué dice el informe sobre el secuestro cometido por las FARC?",
    "¿Qué pasó con la Unión Patriótica según el informe?",
    "¿Cómo se relacionó el narcotráfico con el conflicto armado?",
    "¿Qué dice el informe sobre el reclutamiento de niños, niñas y adolescentes?",
    "¿Qué impactos tuvo el conflicto en los colombianos en el exilio?",
    "¿Qué dice el informe sobre la violencia sexual en el conflicto?",
    "¿Qué recomienda la Comisión para la no repetición?",
    "¿Qué papel tuvo la Fuerza Pública en las violaciones de derechos humanos?",
    "¿Qué dice el informe sobre las minas antipersonal?",
    "¿Cómo afectó el conflicto a las personas LGBTIQ+?",
    "¿Qué dice el informe sobre la desaparición forzada?",
    "¿Qué dice el informe sobre los cultivos de uso ilícito y la erradicación forzada?",
    "¿Qué papel tuvieron empresarios y terceros civiles en el conflicto?",
    "¿Qué dice el informe sobre el conflicto en el Catatumbo?",
    "¿Cómo afectó el conflicto armado a la región del Pacífico?",
    "¿Qué dice el informe sobre las masacres?",
    "¿Qué dice el informe sobre el Acuerdo de Paz de 2016?",
    "¿Qué impactos tuvo el conflicto sobre la naturaleza y el territorio?",
    "¿Qué dice el informe sobre los líderes sociales asesinados?",
]


def pedir(url, key, pregunta, nivel, idx, barrera, repetida, nombre_auto):
    fila = {"modo": "dify", "nivel": nivel, "usuario": idx + 1, "pregunta": pregunta,
            "repetida": repetida, "ok": False, "error": "", "primera_palabra_s": None,
            "total_s": None, "latencia_llm_dify_s": None, "tokens_entrada": None,
            "tokens_salida": None, "tok_s_salida_aprox": None, "fuentes": None,
            "inicio_respuesta": "", "_t_ini": None, "_t_fin": None}
    u = urlparse(url)
    ruta = u.path.rstrip("/") + "/chat-messages"
    cuerpo = json.dumps({
        "inputs": {},
        "query": pregunta,
        "response_mode": "streaming",
        "conversation_id": "",
        "user": f"prueba-n{nivel}-u{idx + 1}",
        "auto_generate_name": nombre_auto,
    }).encode("utf-8")
    cabeceras = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}

    if barrera is not None:
        barrera.wait()  # todos arrancan a la vez
    t0 = time.perf_counter()
    fila["_t_ini"] = t0
    Conexion = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    conn = Conexion(u.hostname, u.port, timeout=900)
    try:
        conn.request("POST", ruta, body=cuerpo, headers=cabeceras)
        resp = conn.getresponse()
        if resp.status != 200:
            fila["error"] = f"HTTP {resp.status}: {resp.read(300)!r}"
            return fila
        texto, fin_msg = [], None
        while True:
            linea = resp.readline()
            if not linea:
                break
            linea = linea.strip()
            if not linea.startswith(b"data:"):
                continue
            try:
                d = json.loads(linea[5:])
            except ValueError:
                continue
            ev = d.get("event")
            if ev in ("message", "agent_message"):
                trozo = d.get("answer") or ""
                if trozo and fila["primera_palabra_s"] is None:
                    fila["primera_palabra_s"] = time.perf_counter() - t0
                texto.append(trozo)
            elif ev == "message_end":
                fin_msg = d
                break
            elif ev == "error":
                fila["error"] = str(d.get("message") or d)[:300]
                return fila
        fin = time.perf_counter()
        fila["_t_fin"] = fin
        fila["total_s"] = fin - t0
        if fin_msg is None:
            fila["error"] = "la respuesta termino sin message_end"
            return fila
        meta = fin_msg.get("metadata") or {}
        uso = meta.get("usage") or {}
        fila["tokens_entrada"] = uso.get("prompt_tokens")
        fila["tokens_salida"] = uso.get("completion_tokens")
        if uso.get("latency") is not None:
            fila["latencia_llm_dify_s"] = float(uso["latency"])
        fila["fuentes"] = len(meta.get("retriever_resources") or [])
        if fila["tokens_salida"] and fila["primera_palabra_s"] is not None:
            gen = fila["total_s"] - fila["primera_palabra_s"]
            if gen > 0:
                fila["tok_s_salida_aprox"] = fila["tokens_salida"] / gen
        fila["inicio_respuesta"] = "".join(texto)[:80].replace("\n", " ")
        fila["ok"] = True
    except Exception as e:
        fila["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        conn.close()
    return fila


def percentil(valores, p):
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    k = max(0, min(len(v) - 1, round(p / 100 * len(v) + 0.5) - 1))
    return v[k]


def resumir(filas, nivel):
    ok = [f for f in filas if f["ok"]]
    ttft = [f["primera_palabra_s"] for f in ok]
    tot = [f["total_s"] for f in ok]
    ini = [f["_t_ini"] for f in filas if f["_t_ini"]]
    fin = [f["_t_fin"] for f in ok if f["_t_fin"]]
    pared = (max(fin) - min(ini)) if ini and fin else None
    toks = sum(f["tokens_salida"] or 0 for f in ok)
    gen = [f["tok_s_salida_aprox"] for f in ok if f["tok_s_salida_aprox"]]
    return {
        "modo": "dify", "nivel": nivel, "ok": len(ok), "errores": len(filas) - len(ok),
        "repetidas": sum(1 for f in filas if f["repetida"]),
        "primera_palabra_p50": percentil(ttft, 50), "primera_palabra_p95": percentil(ttft, 95),
        "primera_palabra_max": max(ttft) if ttft else None,
        "total_p50": percentil(tot, 50), "total_p95": percentil(tot, 95),
        "total_max": max(tot) if tot else None,
        "duracion_nivel_s": pared,
        "tok_s_conjunto": (toks / pared) if pared else None,
        "tok_s_por_usuario_mediana": statistics.median(gen) if gen else None,
        "tokens_entrada_mediana": statistics.median([f["tokens_entrada"] for f in ok if f["tokens_entrada"]] or [0]),
        "tokens_salida_mediana": statistics.median([f["tokens_salida"] for f in ok if f["tokens_salida"]] or [0]),
    }


def correr_nivel(url, key, n, cursor, nombre_auto):
    barrera = threading.Barrier(n)
    filas = [None] * n
    hilos = []
    for i in range(n):
        pos = cursor + i
        q = PREGUNTAS[pos % len(PREGUNTAS)]
        repetida = pos >= len(PREGUNTAS)

        def trabajo(i=i, q=q, rep=repetida):
            filas[i] = pedir(url, key, q, n, i, barrera, rep, nombre_auto)

        h = threading.Thread(target=trabajo, daemon=True)
        hilos.append(h)
        h.start()
    for h in hilos:
        h.join()
    return filas


def num(x, dec=2):
    """Numero con coma decimal para que Excel en espanol lo lea bien."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "si" if x else "no"
    if isinstance(x, float):
        return f"{x:.{dec}f}".replace(".", ",")
    return x


def guardar_csv(ruta, filas):
    if not filas:
        return
    campos = [k for k in filas[0] if not k.startswith("_")]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({k: num(fila[k]) for k in campos})


def s(x):
    return "-" if x is None else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser(description="Prueba de concurrencia pasando por Dify")
    ap.add_argument("--url", default="http://localhost/v1", help="URL base de la API de Dify")
    ap.add_argument("--key", default=os.environ.get("DIFY_API_KEY", ""), help="clave de API de la app (app-...)")
    ap.add_argument("--niveles", type=int, nargs="+", default=[1, 5, 10, 15, 20])
    ap.add_argument("--pausa", type=float, default=5, help="segundos entre niveles")
    ap.add_argument("--nombre-auto", action="store_true",
                    help="dejar que Dify genere el titulo de cada conversacion (llamada extra al LLM, como en la pagina web)")
    ap.add_argument("--etiqueta", default="", help="texto para el nombre del archivo, ej. paralelo4")
    a = ap.parse_args()
    if not a.key:
        a.key = input("Pega la clave de API de la app (app-...): ").strip()

    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
    os.makedirs(carpeta, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    eti = f"_{a.etiqueta}" if a.etiqueta else ""
    ruta_det = os.path.join(carpeta, f"dify{eti}_{sello}_detalle.csv")
    ruta_res = os.path.join(carpeta, f"dify{eti}_{sello}_resumen.csv")

    print(f"Dify en {a.url} | niveles {a.niveles} | titulo automatico: {'si' if a.nombre_auto else 'no'}")
    print("Calentando (1 peticion, no cuenta)...", flush=True)
    f = pedir(a.url, a.key, "¿Qué es la Comisión de la Verdad?", 0, 0, None, False, a.nombre_auto)
    if not f["ok"]:
        print(f"Fallo el calentamiento: {f['error']}")
        print("Revisa la URL (--url), la clave (--key) y que el proxy este abierto.")
        sys.exit(1)
    print(f"  ok en {f['total_s']:.1f} s, {f['tokens_entrada']} tokens de entrada, "
          f"{f['tokens_salida']} de salida, {f['fuentes']} fragmentos\n", flush=True)

    todas, resumenes, cursor = [], [], 0
    for n in a.niveles:
        print(f"Nivel {n}: {n} peticiones a la vez...", flush=True)
        filas = correr_nivel(a.url, a.key, n, cursor, a.nombre_auto)
        cursor += n
        r = resumir(filas, n)
        todas.extend(filas)
        resumenes.append(r)
        guardar_csv(ruta_det, todas)
        guardar_csv(ruta_res, resumenes)
        print(f"  {r['ok']}/{n} ok | 1a palabra p50 {s(r['primera_palabra_p50'])} s, "
              f"p95 {s(r['primera_palabra_p95'])} s, max {s(r['primera_palabra_max'])} s | "
              f"total p50 {s(r['total_p50'])} s, max {s(r['total_max'])} s | "
              f"{s(r['tok_s_conjunto'])} tok/s en conjunto"
              f"{'  (' + str(r['repetidas']) + ' preguntas repetidas)' if r['repetidas'] else ''}", flush=True)
        for e in [x for x in filas if not x["ok"]][:3]:
            print(f"    error usuario {e['usuario']}: {e['error']}")
        if n != a.niveles[-1]:
            time.sleep(a.pausa)

    print(f"\nListo. Detalle: {ruta_det}\nResumen: {ruta_res}")


if __name__ == "__main__":
    main()
