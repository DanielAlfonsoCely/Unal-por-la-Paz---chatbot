"""
Manda una bateria de preguntas a las apps de Dify (concisa y analitica) y guarda todo
para revisarlo: respuesta, pensamiento, tiempos, tokens y fragmentos recuperados.

Corre en el Nodo 10. Una pregunta a la vez (no se pelean la GPU).

Claves de API de cada app (Dify -> app -> Acceso API -> Clave de API), una por archivo:
  ~/.dify_app_concisa      ~/.dify_app_analitica
Si una no existe, esa app se salta.

Uso (en tmux, con el venv activado):
  python probar_apps.py                    # todas las preguntas, ambas apps
  python probar_apps.py --solo P01 P04     # solo esas preguntas
  python probar_apps.py --apps concisa     # solo una app
  python probar_apps.py --etiqueta sin_think   # para comparar corridas

Salida: datos/pruebas_apps_<etiqueta>.jsonl (una linea por pregunta x app) y un .csv
resumen al lado. Reanudable: salta lo que ya esta en el .jsonl.
"""
import argparse
import csv
import json
import os
import re
import time

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("DIFY_API", "http://localhost/v1").rstrip("/")
APPS = {"concisa": "~/.dify_app_concisa", "analitica": "~/.dify_app_analitica"}

# id, tipo de prueba, pregunta, que se espera
PREGUNTAS = [
    ("P01", "tema_general", "¿Qué dicen los documentos sobre la restitución de tierras en Colombia?",
     "Varias fuentes distintas y relevantes; sin datos inventados"),
    ("P02", "tema_general", "¿Qué se ha investigado sobre las Zonas de Reserva Campesina?",
     "Debería traer varios de los 9 documentos con 'zona de reserva' en el título"),
    ("P03", "palabra_exacta", "¿Qué dicen los documentos sobre los PDET?",
     "Sigla exacta: prueba la parte de palabras clave de la híbrida"),
    ("P04", "documento_puntual", "¿Qué pasó con la adjudicación de baldíos en Turminá, Inzá, Cauca?",
     "Debe recuperar la tesis de Turminá (2015)"),
    ("P05", "tema_general", "¿Qué papel tienen las mujeres en las luchas por la tierra según los documentos?",
     "Varias fuentes; ojo si mezcla temas no relacionados"),
    ("P06", "relacion", "¿Cómo se relacionan la minería y el despojo de tierras según los documentos?",
     "Debe traer el de minería y despojo en el nordeste antioqueño"),
    ("P07", "comparar", "¿Qué diferencias hay entre los enfoques de los documentos sobre la reforma agraria?",
     "La analítica debería mostrar matices entre fuentes"),
    ("P08", "fuera_de_base", "¿Quién ganó el mundial de fútbol de 2018?",
     "Debe decir que no encontró información; no responder de memoria"),
    ("P09", "fuera_de_base", "¿Qué establece la Ley 2294 de 2023 sobre el catastro multipropósito?",
     "La base llega a 2021: no debería inventar el contenido de esa ley"),
    ("P10", "dato_inexistente", "¿Cuántas páginas tiene el Boletín Ambiental La economía campesina 177?",
     "No debe inventar un número"),
    ("P11", "metadata", "¿Quién dirigió la tesis sobre la territorialidad campesina en Turminá?",
     "El director está en la metadata, no en el texto: probablemente falle (útil para decidir Chatflow)"),
    ("P12", "ambigua", "¿Y qué pasó después?",
     "Debe pedir aclaración"),
]

COLS_CSV = ["id", "app", "tipo", "pregunta", "segundos", "primer_token_s", "seg_pensando",
            "tokens", "n_fragmentos", "documentos", "respuesta", "error"]


def leer_clave(ruta):
    ruta = os.path.expanduser(ruta)
    return open(ruta, encoding="utf-8").read().strip() if os.path.exists(ruta) else None


def preguntar(clave, pregunta):
    """Usa streaming (las respuestas con pensamiento pueden pasar del timeout del modo bloqueo)."""
    t0 = time.time()
    primer, texto, meta, err = None, [], {}, ""
    try:
        r = requests.post(f"{BASE}/chat-messages", stream=True, timeout=900,
                          headers={"Authorization": f"Bearer {clave}"},
                          json={"inputs": {}, "query": pregunta, "response_mode": "streaming",
                                "user": "prueba-automatica", "conversation_id": ""})
        if r.status_code != 200:
            return {"error": f"{r.status_code}: {r.text[:300]}", "segundos": round(time.time() - t0, 1)}
        for linea in r.iter_lines(decode_unicode=True):
            if not linea or not linea.startswith("data:"):
                continue
            try:
                ev = json.loads(linea[5:].strip())
            except ValueError:
                continue
            tipo = ev.get("event")
            if tipo in ("message", "agent_message"):
                if primer is None:
                    primer = time.time() - t0
                texto.append(ev.get("answer", ""))
            elif tipo == "message_end":
                meta = ev.get("metadata", {}) or {}
            elif tipo == "error":
                err = f"{ev.get('status')}: {ev.get('message')}"
    except requests.RequestException as e:
        err = type(e).__name__
    completo = "".join(texto)
    m = re.search(r"<think>(.*?)</think>", completo, re.S)
    pensamiento = m.group(1).strip() if m else ""
    respuesta = re.sub(r"<think>.*?</think>", "", completo, flags=re.S).strip()
    frags = [{"documento": x.get("document_name"), "score": x.get("score"),
              "texto": (x.get("content") or "")[:600]}
             for x in meta.get("retriever_resources", []) or []]
    usage = meta.get("usage", {}) or {}
    return {"segundos": round(time.time() - t0, 1),
            "primer_token_s": round(primer, 1) if primer else None,
            "tokens": usage.get("total_tokens"), "respuesta": respuesta,
            "pensamiento": pensamiento, "fragmentos": frags, "error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", nargs="*", help="ids de preguntas")
    ap.add_argument("--apps", nargs="*", default=list(APPS))
    ap.add_argument("--etiqueta", default="v1")
    a = ap.parse_args()

    os.makedirs(os.path.join(AQUI, "datos"), exist_ok=True)
    salida = os.path.join(AQUI, "datos", f"pruebas_apps_{a.etiqueta}.jsonl")
    hechos = set()
    if os.path.exists(salida):
        for l in open(salida, encoding="utf-8"):
            try:
                x = json.loads(l)
                if not x.get("error"):
                    hechos.add((x["id"], x["app"]))
            except ValueError:
                pass

    claves = {n: leer_clave(APPS[n]) for n in a.apps}
    for n, k in claves.items():
        if not k:
            print(f"Sin clave para la app {n} ({APPS[n]}): se salta")
    preguntas = [p for p in PREGUNTAS if not a.solo or p[0] in a.solo]

    for pid, tipo, preg, esperado in preguntas:
        for app, clave in claves.items():
            if not clave or (pid, app) in hechos:
                continue
            print(f"{pid} [{app}] {preg[:60]}...", flush=True)
            res = preguntar(clave, preg)
            fila = {"id": pid, "app": app, "tipo": tipo, "pregunta": preg, "esperado": esperado,
                    "hora": time.strftime("%Y-%m-%d %H:%M:%S"), **res}
            with open(salida, "a", encoding="utf-8") as f:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            docs = sorted({x["documento"] for x in res.get("fragmentos", [])})
            print(f"   {res['segundos']} s | {len(res.get('fragmentos', []))} fragmentos de "
                  f"{len(docs)} documentos {('| ERROR ' + res['error']) if res.get('error') else ''}",
                  flush=True)

    # resumen CSV (la ultima corrida de cada pregunta x app)
    filas = {}
    for l in open(salida, encoding="utf-8"):
        x = json.loads(l)
        filas[(x["id"], x["app"])] = x
    with open(salida.replace(".jsonl", ".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS_CSV)
        w.writeheader()
        for (pid, app), x in sorted(filas.items()):
            fr = x.get("fragmentos", [])
            w.writerow({"id": pid, "app": app, "tipo": x["tipo"], "pregunta": x["pregunta"],
                        "segundos": x.get("segundos"), "primer_token_s": x.get("primer_token_s"),
                        "seg_pensando": "", "tokens": x.get("tokens"), "n_fragmentos": len(fr),
                        "documentos": " | ".join(sorted({y["documento"] or "" for y in fr})),
                        "respuesta": x.get("respuesta", ""), "error": x.get("error", "")})
    print(f"\nListo. Detalle: {salida}")


if __name__ == "__main__":
    main()
