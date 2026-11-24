"""
Código de los 2 nodos "Code" (Python 3) del Chatflow del chatbot de paz.
En Dify cada nodo Code tiene su propia función main(); copia CADA función en su nodo.

Flujo:  Inicio → Recuperación de conocimiento → [Code 1: armar_contexto] → LLM → [Code 2: anexar_fuentes] → Respuesta

Por qué así:
- El chatbot simple de Dify solo le pasa al modelo el texto de los fragmentos (sin título, autor ni link).
  Aquí el Code 1 numera cada fuente y le pega sus metadatos, así el modelo sabe QUÉ documento está leyendo.
- La lista de "Fuentes" ya no la escribe el modelo (inventaba capítulos y bibliografía): la arma el Code 2
  solo con los números [n] que el modelo citó de verdad. Si no citó nada (no encontró información), no sale lista.
- Por eso en Funciones (Features) hay que APAGAR "Citas y atribuciones": la lista de abajo con los 6 fragmentos
  que confundió a Natalia/Daniela desaparece y queda solo la nuestra.
"""

# =====================================================================
# CODE 1 — armar_contexto
# Entrada:  result  (array[object])  ← salida "result" del nodo Recuperación de conocimiento
# Salidas:  contexto (string), fuentes (string, JSON), n_fuentes (number)
# =====================================================================
def main(result: list) -> dict:
    import json

    def meta_de(item):
        m = item.get("metadata") or {}
        dm = m.get("doc_metadata") or {}          # metadatos propios (los 13 campos que subió subir_a_dify.py)
        junto = dict(m)
        junto.update(dm)
        return junto

    docs = {}      # agrupa fragmentos por documento: un número [n] por documento, no por fragmento
    orden = []
    for item in result or []:
        m = meta_de(item)
        clave = m.get("document_id") or m.get("id_repositorio") or m.get("document_name") or item.get("title")
        if clave not in docs:
            docs[clave] = {
                "titulo": m.get("titulo") or item.get("title") or m.get("document_name") or "Documento sin título",
                "autor": m.get("autor") or "",
                "anio": m.get("anio") or "",
                "tipo": m.get("tipo") or "",
                "link": m.get("link_repositorio") or "",
                "score": m.get("score") or 0,
                "fragmentos": [],
            }
            orden.append(clave)
        docs[clave]["fragmentos"].append((item.get("content") or "").strip())

    bloques, fuentes = [], []
    for n, clave in enumerate(orden, start=1):
        d = docs[clave]
        anio = str(d["anio"]).split(".")[0] if d["anio"] != "" else ""
        cabecera = f"[{n}] {d['titulo']}"
        detalles = ", ".join(x for x in [d["autor"], anio, d["tipo"]] if x)
        if detalles:
            cabecera += f" — {detalles}"
        texto = "\n...\n".join(f for f in d["fragmentos"] if f)
        bloques.append(f"{cabecera}\n{texto}")
        fuentes.append({"n": n, "titulo": d["titulo"], "autor": d["autor"], "anio": anio, "link": d["link"]})

    contexto = "\n\n========\n\n".join(bloques) if bloques else "(No se recuperó ningún documento.)"
    return {"contexto": contexto, "fuentes": json.dumps(fuentes, ensure_ascii=False), "n_fuentes": len(fuentes)}


# =====================================================================
# CODE 2 — anexar_fuentes
# Entradas: respuesta (string) ← texto del LLM;  fuentes (string) ← salida "fuentes" del Code 1
# Salida:   final (string)  → va al nodo Respuesta
# =====================================================================
def main(respuesta: str, fuentes: str) -> dict:
    import json, re

    texto = respuesta or ""
    # Si el modelo dejó un bloque de pensamiento en el texto, se quita
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()

    try:
        lista = json.loads(fuentes or "[]")
    except Exception:
        lista = []
    por_n = {f["n"]: f for f in lista}

    citados = []
    for m in re.finditer(r"\[(\d+(?:\s*,\s*\d+)*)\]", texto):
        for x in m.group(1).split(","):
            k = int(x.strip())
            if k in por_n and k not in citados:
                citados.append(k)

    # Sin citas válidas (o el modelo dijo que no encontró información) → sin lista de fuentes
    if not citados:
        return {"final": texto}

    lineas = []
    for k in citados:
        f = por_n[k]
        ref = f"**[{k}]** {f['titulo']}"
        extra = ", ".join(x for x in [f.get("autor", ""), f.get("anio", "")] if x)
        if extra:
            ref += f" ({extra})"
        if f.get("link"):
            ref += f" — [Ver en el Repositorio UNAL]({f['link']})"
        lineas.append(ref)

    return {"final": texto + "\n\n---\n**Fuentes**\n\n" + "\n\n".join(lineas)}
