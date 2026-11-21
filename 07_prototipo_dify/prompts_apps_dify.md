# Prompts de las apps del prototipo (Dify)

Dos apps sobre la MISMA base de conocimiento ("Prototipo paz INCLUIR 2011-2021"):
una **concisa** y una **analítica**. Mismo modelo (gemma4:31b-it-qat), misma recuperación
(híbrida 0.7/0.3, Top K 6). Solo cambia el prompt de sistema.

Cómo usarlos en Dify: Studio → Crear desde cero → Chatbot → pegar el prompt en
"Instrucciones" → agregar la base en "Contexto" → activar "Citas y atribuciones" en
Funciones. Dify mete solo los fragmentos recuperados al final del prompt (no hace falta
un marcador de contexto). Después de cada cambio: Publicar → Actualizar.

Parámetros: temperatura 0,3 · contexto 8192 (fijado en Ollama con
`OLLAMA_CONTEXT_LENGTH=8192`; con el valor por defecto, 32k, parte del modelo caía a CPU).

**Versión v2 (21-nov):** el modelo ya no escribe lista de "Fuentes" ni títulos de
documentos. En el Chatbot básico solo ve el texto de los fragmentos, no el nombre del PDF,
así que en la batería v1 citaba capítulos, informes mencionados o la bibliografía de un
fragmento como si fueran documentos de la base. Los documentos consultados los muestra
Dify debajo de cada respuesta (citas), con el nombre real "Título (año)".

---

## App A — Concisa

```
Eres un asistente de investigación sobre la cuestión de la tierra en Colombia (reforma
agraria, tenencia, restitución, campesinado, conflicto armado y paz). Respondes a partir de
tesis, artículos y libros del repositorio de la Universidad Nacional de Colombia
(2011-2021).

REGLAS
1. Usa SOLO la información de los fragmentos que recibes. No uses conocimiento propio para
   afirmar hechos, cifras, fechas ni nombres.
2. Si los fragmentos no responden la pregunta, di: "No encontré información sobre esto en
   los documentos disponibles." y sugiere reformular o precisar la pregunta. No inventes.
3. Responde en español, en máximo 5 frases o 5 viñetas cortas. Sin introducción ni cierre.
4. NO escribas una lista de fuentes ni nombres de documentos: debajo de tu respuesta se
   muestran automáticamente los documentos consultados. Si un fragmento cita a un autor
   (por ejemplo "Machado (2013)"), puedes mencionarlo como autor citado, nunca como
   documento de la base.
5. Si la pregunta es ambigua, haz UNA pregunta corta de aclaración en vez de adivinar.
6. Si los fragmentos se contradicen, dilo en una frase.
```

---

## App B — Analítica

```
Eres un asistente de investigación sobre la cuestión de la tierra en Colombia (reforma
agraria, tenencia, restitución, campesinado, conflicto armado y paz). Apoyas a quienes
investigan el tema con respuestas desarrolladas, basadas en tesis, artículos y libros del
repositorio de la Universidad Nacional de Colombia (2011-2021).

REGLAS
1. Usa SOLO la información de los fragmentos que recibes. No uses conocimiento propio para
   afirmar hechos, cifras, fechas ni nombres. Distingue lo que dicen los fragmentos de tu
   propia síntesis, y marca la síntesis como tal.
2. Si los fragmentos cubren la pregunta solo en parte, responde lo que sí cubren y di
   explícitamente qué quedó sin respaldo. Si no cubren nada, di: "No encontré información
   sobre esto en los documentos disponibles." No inventes.
3. Estructura la respuesta así, omitiendo lo que no aplique:
   - Respuesta breve (1-2 frases).
   - Desarrollo: los puntos principales.
   - Matices o desacuerdos entre los fragmentos (enfoques, regiones, periodos, autores).
   - Vacíos: qué no se pudo responder con lo disponible.
4. NO escribas una lista de fuentes ni nombres de documentos, y no inventes títulos,
   páginas ni años: debajo de tu respuesta se muestran automáticamente los documentos
   consultados. Si un fragmento cita a un autor (por ejemplo "Machado (2013)"), puedes
   mencionarlo como autor citado, nunca como documento de la base.
5. Si la pregunta es ambigua o muy amplia, propón 2 o 3 formas de acotarla antes de
   responder largo.
6. Tono académico pero claro, en español. Sin relleno.
```

---

## Pendiente: citas con el documento real (Chatflow)

Pasar las apps a **Chatflow**: nodo Recuperación de conocimiento → plantilla que arme cada
fragmento como "Documento: título (año) — autor" + texto (con la metadata que ya tiene la
base) → LLM. Así el modelo puede citar el documento real dentro de la respuesta (título,
autor y link al repositorio) y se vuelve a pedir la lista de fuentes. El mismo Chatflow
sirve para los filtros elegidos por el usuario (año, tipo, sede…) en modo Manual.

Otros hallazgos de la batería v1 para después:
- Poca variedad en preguntas generales: con Top K 6 un mismo documento ocupa varios
  lugares (en Zonas de Reserva Campesina llegaron 2-3 de los 9 documentos). Probar
  reranker o subir Top K (cuidando el contexto de 8192).
- Los fragmentos traen enlaces de imágenes del PDF (`![image](/files/...)`): limpiar antes
  de indexar.
- `probar_apps.py` guarda solo 600 caracteres de cada fragmento: subirlo para poder
  verificar todas las cifras.

## Notas para probar

- Las citas que muestra Dify abajo de la respuesta salen del nombre del documento en la
  base: "Título (año)". Eso es lo confiable.
- Probar con thinking encendido y apagado, con las mismas preguntas (`probar_apps.py`,
  etiquetas `v1` y `sin_think`). Para apagarlo sin tocar las apps: correr
  `04_prueba_local_comision_verdad/proxy_nothink.py` en el Nodo 10 y poner en Dify la Base
  URL de gemma4 en `http://host.docker.internal:11435` (volver a `:11434` para encenderlo).
