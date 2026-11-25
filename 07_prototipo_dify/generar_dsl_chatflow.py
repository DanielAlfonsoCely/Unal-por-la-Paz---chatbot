"""
Genera chatflow_paz_v1.yml (DSL de Dify 1.16.x, versión 0.7.0) para importar en Dify:
Studio → Crear app → Importar DSL → subir el .yml.
El código de los nodos Code se toma de nodos_codigo_chatflow.py (una sola fuente de verdad).

Después de importar, revisar en el lienzo:
  1) Nodo "Buscar en documentos": elegir la base "Prototipo paz INCLUIR 2011-2021" (el id de la base no viaja en el DSL).
  2) Nodo "Redactar respuesta": que el modelo sea gemma4:31b-it-qat (plugin Ollama).
  3) Publicar.
Uso: python generar_dsl_chatflow.py   → escribe chatflow_paz_v1.yml
"""
from pathlib import Path
import yaml

AQUI = Path(__file__).parent
partes = (AQUI / "nodos_codigo_chatflow.py").read_text(encoding="utf-8").split("def main(")
CODE1 = "def main(" + partes[1].split("# =====")[0].rstrip() + "\n"
CODE2 = "def main(" + partes[2].rstrip() + "\n"

MODELO = {"provider": "langgenius/ollama/ollama", "name": "gemma4:31b-it-qat", "mode": "chat",
          "completion_params": {"temperature": 0.3}}

PROMPT = """Eres el asistente de investigación del proyecto "UNAL por la Paz" de la Universidad Nacional de Colombia.
Ayudas a investigadores, estudiantes y equipos de trabajo a consultar la producción académica de la Universidad sobre la cuestión agraria, la tierra y la construcción de paz en Colombia.

Responde SOLO con la información de los DOCUMENTOS de abajo. Cada documento tiene un número entre corchetes, su título, autor y año, y uno o varios fragmentos.

Reglas:
1. Cada afirmación que saques de un documento lleva su número al final, así: [2] o [1, 3]. Usa solo los números que aparecen abajo. No inventes títulos, autores, capítulos ni páginas.
2. Si los documentos no responden la pregunta, dilo claramente en una o dos frases, SIN números entre corchetes, y sugiere cómo reformular la pregunta. No completes con conocimiento propio.
3. Si los documentos responden solo una parte, responde esa parte y aclara qué falta.
4. Estilo analítico: organiza la respuesta (contexto, hallazgos principales, diferencias entre autores si las hay). Si dos documentos se contradicen, muéstralo.
5. Cuando sea útil, nombra el documento en el texto ("En la tesis de X (2018) [3]...").
6. No escribas una lista de fuentes al final: el sistema la agrega sola.
7. Responde en el idioma de la pregunta.
8. Al final, en una línea aparte, escribe exactamente "SUGERENCIAS:" seguido de 3 preguntas cortas separadas por " | ". Deben ser preguntas que los DOCUMENTOS de abajo sí permiten responder (por ejemplo "Explícame...", "¿Por qué...?", "¿Qué diferencias hay entre...?"). Si no encontraste información, sugiere 3 formas más concretas de preguntar sobre el tema del proyecto.

DOCUMENTOS:
{{#code_contexto.contexto#}}"""


def nodo(id_, x, data):
    return {"id": id_, "type": "custom", "position": {"x": x, "y": 250}, "positionAbsolute": {"x": x, "y": 250},
            "sourcePosition": "right", "targetPosition": "left", "width": 244, "height": 90,
            "data": {"desc": "", "selected": False, **data}}


def arista(a, ta, b, tb):
    return {"id": f"{a}-source-{b}-target", "source": a, "sourceHandle": "source", "target": b,
            "targetHandle": "target", "type": "custom", "zIndex": 0,
            "data": {"isInIteration": False, "isInLoop": False, "sourceType": ta, "targetType": tb}}


nodos = [
    nodo("inicio", 0, {"type": "start", "title": "Inicio", "variables": []}),
    nodo("recuperar", 320, {
        "type": "knowledge-retrieval", "title": "Buscar en documentos",
        "dataset_ids": [], "query_variable_selector": ["sys", "query"], "retrieval_mode": "multiple",
        "metadata_filtering_mode": "disabled",
        "multiple_retrieval_config": {
            "top_k": 6, "score_threshold": None, "reranking_enable": False, "reranking_mode": "weighted_score",
            "reranking_model": {"provider": "", "model": ""},
            "weights": {"weight_type": "customized",
                        "vector_setting": {"vector_weight": 0.7, "embedding_provider_name": "langgenius/ollama/ollama",
                                           "embedding_model_name": "bge-m3"},
                        "keyword_setting": {"keyword_weight": 0.3}}}}),
    nodo("code_contexto", 640, {
        "type": "code", "title": "Armar contexto con fuentes", "code_language": "python3", "code": CODE1,
        "variables": [{"variable": "result", "value_selector": ["recuperar", "result"], "value_type": "array[object]"}],
        "outputs": {"contexto": {"type": "string", "children": None}, "fuentes": {"type": "string", "children": None},
                    "n_fuentes": {"type": "number", "children": None}}}),
    nodo("llm", 960, {
        "type": "llm", "title": "Redactar respuesta", "model": MODELO, "variables": [],
        "context": {"enabled": False, "variable_selector": []}, "vision": {"enabled": False},
        "prompt_template": [{"id": "sistema-paz-v3", "role": "system", "text": PROMPT}],
        "memory": {"query_prompt_template": "{{#sys.query#}}", "role_prefix": {"user": "", "assistant": ""},
                   "window": {"enabled": True, "size": 6}}}),
    nodo("code_fuentes", 1280, {
        "type": "code", "title": "Agregar fuentes citadas", "code_language": "python3", "code": CODE2,
        "variables": [{"variable": "respuesta", "value_selector": ["llm", "text"], "value_type": "string"},
                      {"variable": "fuentes", "value_selector": ["code_contexto", "fuentes"], "value_type": "string"}],
        "outputs": {"final": {"type": "string", "children": None}}}),
    nodo("respuesta", 1600, {"type": "answer", "title": "Respuesta", "answer": "{{#code_fuentes.final#}}",
                             "variables": []}),
]
aristas = [arista("inicio", "start", "recuperar", "knowledge-retrieval"),
           arista("recuperar", "knowledge-retrieval", "code_contexto", "code"),
           arista("code_contexto", "code", "llm", "llm"),
           arista("llm", "llm", "code_fuentes", "code"),
           arista("code_fuentes", "code", "respuesta", "answer")]

dsl = {
    "app": {"name": "Chatbot Paz UNAL - Chatflow v1", "mode": "advanced-chat", "icon": "🕊️", "icon_type": "emoji",
            "icon_background": "#E4FBCC", "description": "Consulta documentos del repositorio UNAL con fuentes citadas",
            "use_icon_as_answer_icon": False},
    "dependencies": [], "kind": "app", "version": "0.7.0",
    "workflow": {
        "conversation_variables": [], "environment_variables": [],
        "features": {
            "file_upload": {"enabled": False},
            "opening_statement": ("Hola. Soy el asistente de investigación de UNAL por la Paz. Respondo con base en "
                                  "tesis, artículos y libros del repositorio de la Universidad Nacional (2011-2021) "
                                  "sobre tierra, conflicto y construcción de paz, y cito mis fuentes."),
            "suggested_questions": [
                "¿Qué es la Reforma Rural Integral y qué dicen las investigaciones sobre su implementación?",
                "¿Cómo se relaciona la concentración de la tierra con el conflicto armado en Colombia?",
                "¿Qué son las Zonas de Reserva Campesina?",
                "¿Qué dificultades ha tenido la restitución de tierras?",
            ],
            "suggested_questions_after_answer": {"enabled": False},
            "retriever_resource": {"enabled": False},
            "sensitive_word_avoidance": {"enabled": False}, "speech_to_text": {"enabled": False},
            "text_to_speech": {"enabled": False, "language": "", "voice": ""},
        },
        "graph": {"nodes": nodos, "edges": aristas, "viewport": {"x": 0, "y": 0, "zoom": 0.7}},
    },
}


class Bloque(str):
    pass


yaml.add_representer(Bloque, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))
for n in nodos:
    if "code" in n["data"]:
        n["data"]["code"] = Bloque(n["data"]["code"])
nodos[3]["data"]["prompt_template"][0]["text"] = Bloque(PROMPT)
(AQUI / "chatflow_paz_v1.yml").write_text(yaml.dump(dsl, allow_unicode=True, sort_keys=False, width=1000),
                                          encoding="utf-8")
print("Listo: chatflow_paz_v1.yml")
