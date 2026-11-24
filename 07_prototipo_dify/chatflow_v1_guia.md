# Chatflow v1 — chatbot de paz (para la prueba del jueves y la demo del viernes)

Objetivo: arreglar lo que salió en la reunión del 24-nov **sin construir nada desde cero**:

| Problema / pedido | Cómo lo resuelve el Chatflow |
|---|---|
| Dice "no encontré fuentes" pero abajo muestra 6 documentos | Se apagan las citas automáticas de Dify; la lista la arma el Code 2 solo con lo que el modelo citó. Si no citó nada → no hay lista |
| El chat no sabe título, autor, año ni link de lo que lee | El Code 1 le pega a cada fragmento su ficha (metadatos que ya subimos) y lo numera [1], [2]… |
| Citar con link al repositorio | La lista final trae "Ver en el Repositorio UNAL" con `link_repositorio` |
| Preguntas sugeridas arriba del campo de texto | Funciones → "Iniciador de conversación" (preguntas fijas) + "Siguientes preguntas sugeridas" (las genera el modelo después de cada respuesta) |
| Filtros (año, tipo…) en vez del filtrado automático que falló | Campos opcionales en el nodo Inicio → filtro de metadatos en modo **Manual** en la recuperación |
| Usar la versión analítica | El prompt del LLM parte del prompt analítico |

## Nodos (en orden)

1. **Inicio** — variables opcionales (Dify las muestra como formulario al empezar el chat):
   - `anio_desde` (número, opcional), `anio_hasta` (número, opcional)
   - `tipo` (selección, opcional): Tesis de maestría / Tesis de doctorado / Trabajo de grado / Libro / Artículo… (copiar los valores exactos del campo `tipo` de la DB)
2. **Recuperación de conocimiento**
   - Consulta: `sys.query`; base: "Prototipo paz INCLUIR 2011-2021"
   - Filtro de metadatos: **Manual** → `anio ≥ {{anio_desde}}`, `anio ≤ {{anio_hasta}}`, `tipo is {{tipo}}` (probar qué pasa con un campo vacío; si un campo vacío filtra todo, dejar solo los años y probar)
   - Top K 6 (igual que hoy). Si el contexto queda corto, probar 8
3. **Code 1 – armar_contexto** (código en `nodos_codigo_chatflow.py`)
   - Entrada `result` = salida `result` de la recuperación
   - Salidas: `contexto` (String), `fuentes` (String), `n_fuentes` (Number)
4. **LLM** — gemma4:31b-it-qat (vía proxy sin thinking, :11435), temperatura 0.3, memoria activada (ventana corta, ~6 mensajes, para no llenar el contexto de 8K)
   - Prompt de sistema: abajo. El `{{contexto}}` se inserta con "/" escogiendo la salida del Code 1
   - Usuario: `sys.query`
5. **Code 2 – anexar_fuentes** — entradas `respuesta` = texto del LLM, `fuentes` = salida del Code 1; salida `final`
6. **Respuesta** — `{{final}}`

**Funciones (Features), arriba a la derecha:**
- Citas y atribuciones: **APAGADO**
- Iniciador de conversación: mensaje de bienvenida + 4–6 preguntas sugeridas (las elegimos el jueves con Jairo/Natalia/Daniela)
- Siguientes preguntas sugeridas: **ENCENDIDO**
- Publicar → Actualizar después de cada cambio (el link público usa la versión publicada)

## Prompt de sistema del LLM (v3, base analítica)

```
Eres el asistente de investigación del proyecto "UNAL por la Paz" de la Universidad Nacional de Colombia.
Ayudas a investigadores, estudiantes y equipos de trabajo a consultar la producción académica de la
Universidad sobre la cuestión agraria, la tierra y la construcción de paz en Colombia.

Responde SOLO con la información de los DOCUMENTOS de abajo. Cada documento tiene un número entre
corchetes, su título, autor y año, y uno o varios fragmentos.

Reglas:
1. Cada afirmación que saques de un documento lleva su número al final, así: [2] o [1, 3].
   Usa solo los números que aparecen abajo. No inventes títulos, autores, capítulos ni páginas.
2. Si los documentos no responden la pregunta, dilo claramente en una o dos frases, SIN números
   entre corchetes, y sugiere cómo reformular la pregunta. No completes con conocimiento propio.
3. Si los documentos responden solo una parte, responde esa parte y aclara qué falta.
4. Estilo analítico: organiza la respuesta (contexto, hallazgos principales, diferencias entre
   autores si las hay). Si dos documentos se contradicen, muéstralo.
5. Cuando sea útil, nombra el documento en el texto ("En la tesis de X (2018) [3]...").
6. No escribas una lista de fuentes al final: el sistema la agrega sola.
7. Responde en el idioma de la pregunta.

DOCUMENTOS:
{{contexto}}
```

## Probar antes del jueves (batería de probar_apps.py con la app nueva)

- Pregunta fuera de base ("¿quién ganó el mundial 2022?") → sin lista de fuentes
- Pregunta de metadato ("¿quién dirigió la tesis sobre Turminá?") → ahora sí debería saberlo
- Pregunta con filtro de años → que no traiga documentos fuera del rango
- Revisar que las citas [n] coincidan con el documento correcto (abrir 3–4 links)

## Siguientes pasos (después del viernes)

- **Modo "profundizar en un documento"**: el usuario escribe p. ej. "profundiza en [3]" → un Code detecta el número →
  un Asignador de variables guarda el `id_repositorio` en una variable de conversación → la recuperación
  filtra solo ese documento (Top K 10). Meter la tesis completa no cabe: una tesis son decenas de miles de tokens
  y con la 3090 el contexto real es 8–16K.
- **Segunda base "Marco normativo"** (Acuerdo de Paz, Ley 160, Ley 1448…) recuperada en paralelo y marcada distinto.
- **Orientador de construcción de paz** (la "skill" de Jairo): rama aparte con Clasificador de preguntas.
- **UI propia** sobre la API (plantilla oficial `langgenius/webapp-conversation`, licencia MIT).
