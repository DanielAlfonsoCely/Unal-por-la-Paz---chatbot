"""
Sube los PDFs del prototipo (INCLUIR 2011-2021) a una base de conocimiento de Dify
por la API de conocimiento. Corre en el Nodo 10, donde estan los PDFs.

Que hace:
  1) Busca la base "Prototipo paz INCLUIR 2011-2021"; si no existe, la crea con
     indice de alta calidad, embeddings bge-m3 y busqueda hibrida 0.7 vectorial /
     0.3 palabras clave (Top K 6).
  2) Crea los campos de metadatos (titulo, autor, director, anio, tipo, nivel, sede,
     facultad, coleccion, dewey, temas, link_repositorio, id_repositorio) si faltan.
  3) Sube cada PDF del manifiesto con fragmentos de 2048 y solapamiento de 256,
     y le pone sus metadatos (salen de la DB del prototipo).
  4) Para no inundar a Dify, mantiene como maximo --cola documentos indexandose a la vez.

Es reanudable: salta lo que ya esta en estado_subida.csv y lo que ya existe en la
base con el mismo nombre. Se puede cortar con Ctrl+C y volver a correr.

Requisitos: clave de API de conocimiento en ~/.dify_key (no se pega en el chat).

Uso (dentro de tmux y con el venv activado):
  python subir_a_dify.py --prueba          # 3 PDF al azar, para verificar todo
  python subir_a_dify.py --limite 20
  python subir_a_dify.py                   # todos
  python subir_a_dify.py --solo-estado     # solo revisa como va el indexado
  python subir_a_dify.py --reintentar      # borra los que quedaron en error y los vuelve a subir
                                           # (correrlo cuando NO haya otra carga andando)

Salidas: estado_subida.csv (una fila por PDF) e informe al final.
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import time

import pandas as pd
import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("DIFY_API", "http://localhost/v1").rstrip("/")
KEY_FILE = os.path.expanduser("~/.dify_key")
NOMBRE_BASE = "Prototipo paz INCLUIR 2011-2021"        # maximo 40 caracteres
DESCRIPCION = "575 documentos INCLUIR 2011-2021 del repositorio UNAL (prototipo)."
EMB_MODELO = "bge-m3"
EMB_PROVEEDOR = "langgenius/ollama/ollama"             # se corrige solo si Dify informa otro
DB = os.path.join(AQUI, "datos", "DB_prototipo_INCLUIR_2011-2021.xlsx")
MANIFIESTO = os.path.join(AQUI, "datos", "manifiesto_descarga.csv")
PDFS = os.path.join(AQUI, "pdfs_prototipo")
ESTADO = os.path.join(AQUI, "estado_subida.csv")
COLS_ESTADO = ["id", "archivo", "document_id", "batch", "estado", "detalle", "hora"]

SEGMENTO_MAX = 2048
SEGMENTO_SOLAPE = 256
TOP_K = 6
CAMPOS_META = {"titulo": "string", "autor": "string", "director": "string", "anio": "number",
               "tipo": "string", "nivel": "string", "sede": "string", "facultad": "string",
               "coleccion": "string", "dewey": "string", "temas": "string",
               "link_repositorio": "string", "id_repositorio": "string"}
# campo de metadato -> columna de la DB
COL_DB = {"titulo": "Título", "autor": "Autor", "director": "Director", "tipo": "Tipo",
          "nivel": "Nivel", "sede": "Sede", "facultad": "Facultad", "coleccion": "Colección",
          "dewey": "Dewey", "temas": "Temas", "link_repositorio": "Link repositorio"}

PESO_VECTOR, PESO_KEYWORD = 0.7, 0.3


def retrieval(prov):
    """Busqueda hibrida: 0.7 vectorial (bge-m3) + 0.3 palabras clave, sin reranker."""
    return {"search_method": "hybrid_search", "reranking_enable": False,
            "reranking_mode": "weighted_score",
            "weights": {"weight_type": "customized",
                        "vector_setting": {"vector_weight": PESO_VECTOR,
                                           "embedding_provider_name": prov,
                                           "embedding_model_name": EMB_MODELO},
                        "keyword_setting": {"keyword_weight": PESO_KEYWORD}},
            "top_k": TOP_K, "score_threshold_enabled": False}


# ----------------------------------------------------------------------- API
def leer_clave():
    if not os.path.exists(KEY_FILE):
        sys.exit(f"No encuentro {KEY_FILE}. Guarda ahi la clave de API de conocimiento.")
    return open(KEY_FILE, encoding="utf-8").read().strip()


S = requests.Session()


def api(metodo, ruta, reintentos=4, **kw):
    """Llama a la API. Reintenta fallos de red, 429 y 5xx. Devuelve (status, json|texto)."""
    url = BASE + ruta
    ultimo = None
    for i in range(reintentos):
        # los archivos abiertos hay que rebobinarlos antes de cada intento
        for f in (kw.get("files") or {}).values():
            try:
                f[1].seek(0)
            except Exception:
                pass
        try:
            r = S.request(metodo, url, timeout=300, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                ultimo = (r.status_code, r.text[:300])
                time.sleep(3 * (i + 1))
                continue
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, r.text[:300]
        except requests.RequestException as e:
            ultimo = ("red", f"{type(e).__name__}")
            time.sleep(3 * (i + 1))
    return ultimo[0], ultimo[1]


def proveedor_embeddings():
    """Pregunta a Dify cual es el proveedor exacto de bge-m3 (por si no es el supuesto)."""
    st, j = api("GET", "/workspaces/current/models/model-types/text-embedding")
    if st == 200 and isinstance(j, dict):
        for p in j.get("data", []):
            for m in p.get("models", []):
                if m.get("model") == EMB_MODELO:
                    return p.get("provider", EMB_PROVEEDOR)
    return EMB_PROVEEDOR


def obtener_o_crear_base():
    pagina = 1
    while True:
        st, j = api("GET", f"/datasets?page={pagina}&limit=100")
        if st != 200:
            sys.exit(f"No pude listar las bases ({st}): {j}")
        for d in j.get("data", []):
            if d.get("name") == NOMBRE_BASE:
                print(f"Base existente: {NOMBRE_BASE} ({d['id']})")
                return d["id"]
        if not j.get("has_more"):
            break
        pagina += 1
    prov = proveedor_embeddings()
    cuerpo = {"name": NOMBRE_BASE, "description": DESCRIPCION, "permission": "only_me",
              "indexing_technique": "high_quality", "embedding_model": EMB_MODELO,
              "embedding_model_provider": prov, "retrieval_model": retrieval(prov)}
    st, j = api("POST", "/datasets", json=cuerpo)
    if st not in (200, 201):
        sys.exit(f"No pude crear la base ({st}): {j}")
    print(f"Base creada: {NOMBRE_BASE} ({j['id']}) con embeddings {EMB_MODELO} [{prov}]")
    return j["id"]


def asegurar_metadatos(base_id):
    st, j = api("GET", f"/datasets/{base_id}/metadata")
    existentes = {m["name"]: m["id"] for m in (j.get("doc_metadata", []) if st == 200 else [])}
    for nombre, tipo in CAMPOS_META.items():
        if nombre in existentes:
            continue
        st, j = api("POST", f"/datasets/{base_id}/metadata", json={"name": nombre, "type": tipo})
        if st not in (200, 201):
            sys.exit(f"No pude crear el campo de metadato {nombre} ({st}): {j}")
        existentes[nombre] = j["id"]
    return existentes


def documentos_base(base_id):
    """Documentos que ya estan en la base: {nombre: (document_id, estado_indexado)}."""
    docs, pagina = {}, 1
    while True:
        st, j = api("GET", f"/datasets/{base_id}/documents?page={pagina}&limit=100")
        if st != 200:
            break
        for d in j.get("data", []):
            docs[d.get("name")] = (d.get("id"), d.get("indexing_status"))
        if not j.get("has_more"):
            break
        pagina += 1
    return docs


def borrar_con_error(base_id, docs):
    """Borra de la base los documentos que quedaron en error de indexado. Devuelve sus nombres."""
    borrados = []
    for nombre, (doc_id, est) in docs.items():
        if est == "error":
            st, j = api("DELETE", f"/datasets/{base_id}/documents/{doc_id}")
            if st in (200, 204):
                borrados.append(nombre)
            else:
                print(f"  no pude borrar {nombre[:60]} ({st}: {str(j)[:100]})")
    return borrados


def estado_indexado(base_id, batch):
    st, j = api("GET", f"/datasets/{base_id}/documents/{batch}/indexing-status")
    if st != 200:
        return None
    return j.get("data", [])


# --------------------------------------------------------------------- datos
def cargar_metadatos():
    db = pd.read_excel(DB, dtype=str).fillna("")
    meta = {}
    for _, r in db.iterrows():
        m = re.match(r"\s*(\d{4})", r.get("Año", ""))
        v = {k: r.get(col, "").strip() for k, col in COL_DB.items()}
        v["anio"] = int(m.group(1)) if m else None
        v["id_repositorio"] = r["ID"].strip()
        # Dify no acepta valores vacios: solo se mandan los campos que tienen dato
        meta[r["ID"].strip()] = {k: x for k, x in v.items() if x not in ("", None)}
    return meta


def cargar_estado():
    if not os.path.exists(ESTADO):
        return {}
    with open(ESTADO, newline="", encoding="utf-8-sig") as f:
        return {r["archivo"]: r for r in csv.DictReader(f)}


def guardar_estado(fila):
    nuevo = not os.path.exists(ESTADO) or os.path.getsize(ESTADO) == 0
    fila = {**fila, "hora": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(ESTADO, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_ESTADO)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


# --------------------------------------------------------------------- subida
def subir(base_id, ruta_pdf, nombre, prov):
    payload = {"indexing_technique": "high_quality", "doc_form": "text_model",
               "doc_language": "Spanish", "embedding_model": EMB_MODELO,
               "embedding_model_provider": prov, "retrieval_model": retrieval(prov),
               "process_rule": {"mode": "custom", "rules": {
                   "pre_processing_rules": [{"id": "remove_extra_spaces", "enabled": True},
                                            {"id": "remove_urls_emails", "enabled": False}],
                   "segmentation": {"separator": "\n\n", "max_tokens": SEGMENTO_MAX,
                                    "chunk_overlap": SEGMENTO_SOLAPE}}}}
    with open(ruta_pdf, "rb") as fh:
        st, j = api("POST", f"/datasets/{base_id}/document/create-by-file",
                    data={"data": json.dumps(payload)},
                    files={"file": (nombre, fh, "application/pdf")})
    return st, j


def poner_metadatos(base_id, doc_id, campos, valores):
    lista = []
    for nombre, valor in valores.items():
        lista.append({"id": campos[nombre], "name": nombre, "value": valor})
    st, j = api("POST", f"/datasets/{base_id}/documents/metadata",
                json={"operation_data": [{"document_id": doc_id, "metadata_list": lista,
                                          "partial_update": True}]})
    return st, j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true", help="3 PDF al azar")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--cola", type=int, default=6, help="maximo de documentos indexandose a la vez")
    ap.add_argument("--solo-estado", action="store_true")
    ap.add_argument("--reintentar", action="store_true",
                    help="borra de la base los documentos con error de indexado y los vuelve a subir")
    args = ap.parse_args()

    S.headers["Authorization"] = f"Bearer {leer_clave()}"
    base_id = obtener_o_crear_base()
    campos = asegurar_metadatos(base_id)
    prov = proveedor_embeddings()
    estado = cargar_estado()

    if args.solo_estado:
        pend = [r for r in estado.values() if r["estado"] == "subido"]
        print(f"Subidos sin confirmar: {len(pend)}")
        for r in pend:
            d = estado_indexado(base_id, r["batch"]) or []
            for x in d:
                print(f"  {r['archivo'][:60]}: {x.get('indexing_status')} "
                      f"{x.get('completed_segments')}/{x.get('total_segments')} {x.get('error') or ''}")
        return

    with open(MANIFIESTO, newline="", encoding="utf-8-sig") as f:
        filas = [r for r in csv.DictReader(f) if r["estado"] == "pendiente"]
    meta = cargar_metadatos()
    docs_base = documentos_base(base_id)
    if args.reintentar:
        malos = borrar_con_error(base_id, docs_base)
        for n in malos:
            docs_base.pop(n, None)
            estado.pop(n, None)       # que cuente como pendiente otra vez
        print(f"Documentos con error borrados para reintentar: {len(malos)}")
    en_base = set(docs_base)
    por_subir = [r for r in filas
                 if estado.get(r["nombre_destino"], {}).get("estado") not in ("subido", "completo")
                 and r["nombre_destino"] not in en_base]
    if args.prueba:
        por_subir = random.sample(por_subir, min(3, len(por_subir)))
    elif args.limite:
        por_subir = por_subir[:args.limite]
    print(f"Por subir: {len(por_subir)} (ya en la base: {len(en_base)})")

    cola, t0, n_ok, n_err = [], time.time(), 0, 0      # cola: (batch, nombre)

    def vaciar(hasta):
        """Espera a que haya <= hasta documentos indexandose; marca los completos."""
        nonlocal cola
        while len(cola) > hasta:
            siguiente = []
            for batch, nombre in cola:
                d = estado_indexado(base_id, batch) or []
                st_idx = d[0].get("indexing_status") if d else None
                if st_idx == "completed":
                    guardar_estado({"id": estado[nombre]["id"], "archivo": nombre,
                                    "document_id": estado[nombre]["document_id"], "batch": batch,
                                    "estado": "completo", "detalle": ""})
                elif st_idx == "error":
                    guardar_estado({"id": estado[nombre]["id"], "archivo": nombre,
                                    "document_id": estado[nombre]["document_id"], "batch": batch,
                                    "estado": "error_indexado", "detalle": str(d[0].get("error"))[:200]})
                    print(f"  ERROR indexando {nombre[:60]}: {d[0].get('error')}", flush=True)
                else:
                    siguiente.append((batch, nombre))
            cola = siguiente
            if len(cola) > hasta:
                time.sleep(10)

    try:
        for i, r in enumerate(por_subir, 1):
            nombre, id_ = r["nombre_destino"], r["id"]
            ruta = os.path.join(PDFS, nombre)
            if not os.path.exists(ruta):
                guardar_estado({"id": id_, "archivo": nombre, "document_id": "", "batch": "",
                                "estado": "error_subida", "detalle": "archivo_no_esta"})
                n_err += 1
                continue
            st, j = subir(base_id, ruta, nombre, prov)
            if st not in (200, 201) or not isinstance(j, dict) or "document" not in j:
                guardar_estado({"id": id_, "archivo": nombre, "document_id": "", "batch": "",
                                "estado": "error_subida", "detalle": f"{st}: {str(j)[:150]}"})
                print(f"  ERROR subiendo {nombre[:60]}: {st} {str(j)[:150]}", flush=True)
                n_err += 1
                continue
            doc_id, batch = j["document"]["id"], j.get("batch", "")
            valores = meta.get(id_, {})
            if valores:
                st_m, j_m = poner_metadatos(base_id, doc_id, campos, valores)
                if st_m != 200:
                    print(f"  aviso: metadatos de {nombre[:50]} no se guardaron ({st_m}: {str(j_m)[:100]})",
                          flush=True)
            fila = {"id": id_, "archivo": nombre, "document_id": doc_id, "batch": batch,
                    "estado": "subido", "detalle": ""}
            guardar_estado(fila)
            estado[nombre] = fila
            cola.append((batch, nombre))
            n_ok += 1
            vaciar(args.cola)
            if i % 10 == 0 or i == len(por_subir):
                resta = (len(por_subir) - i) * (time.time() - t0) / i / 60
                print(f"  {i}/{len(por_subir)} | subidos {n_ok} | errores {n_err} | "
                      f"~{resta:.0f} min restantes", flush=True)
        vaciar(0)
    except KeyboardInterrupt:
        print("\nPausado. Vuelve a correrlo para seguir (retoma solo).")
        sys.exit(0)

    print(f"\nListo. Subidos {n_ok} | errores {n_err}. Detalle en {ESTADO}")


if __name__ == "__main__":
    main()
