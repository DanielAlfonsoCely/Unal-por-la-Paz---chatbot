# Bitácora del proyecto

Registro de lo que se ha hecho, en orden. Cada vez que se haga un commit con algo nuevo, se agrega aquí una entrada corta: qué se hizo, con qué script y qué decisión salió.

---

## Septiembre 2026 — Reporte de objetos del repositorio

- La Dirección Nacional de Bibliotecas entregó el **reporte de objetos de DSpace** (corte 10 jun 2026): ~36.800 documentos del repositorio institucional con metadatos (título, autor, fechas, tipo, Dewey, resumen, etc.). Está en `fuentes/`.
- Primer análisis con años 2011–2021 (`01_analisis_reporte/filtro_fechas.py`): 21.486 documentos en ese rango. Salida: `estadisticas_2011_2021.*`.
  - El script lee `reporte.pkl`, una copia del reporte en formato pandas. Si no está, se regenera con `pd.read_excel("Reporte de Objetos Dspace 10 jun 2026.xlsx").to_pickle("reporte.pkl")`.
- Se usa el campo **Fecha del documento** (no la fecha de carga al repositorio).

## Octubre 2026 — Filtro por Dewey

- `02_filtro_dewey/filtro_dewey.py` filtra por clasificación Dewey sin tocar el reporte original:
  - Descarta centenas 0, 1, 2, 4 y 8; 3xx pasa salvo 332 y 395; 5xx/6xx solo los de la lista; algunos códigos condicionales solo pasan acompañados.
  - Basta con que un código del documento pase. Se quitan tipos que no son texto (audio, imágenes, partituras…).
  - Rescate por palabras fuertes en título/resumen (reforma agraria, restitución, baldío, campesino, despojo, PDET, Ley 1448…).
- Resultado con 2011–2021: 21.486 → **8.837 candidatos**. Sin filtro de años (`--sin-anios`): **16.132**.
- `coocurrencia_dewey.py` ayudó a decidir las reglas condicionales (qué códigos van solos y con cuáles se acompañan).

## Octubre 2026 — Peso de los archivos

- `03_medicion_pesos/medir_pesos_total.py` consultó la API del repositorio (handle → bundles → ORIGINAL → bitstreams) para los 8.837: **52,1 GB** (44 GB en PDF). Ningún archivo se descargó; solo se midió.

## Octubre 2026 — Prueba de capacidad local (Comisión de la Verdad)

- Prueba en la torre (RX 9060 XT 16 GB): Dify + Ollama con 23 libros del Informe Final de la Comisión de la Verdad (`04_prueba_local_comision_verdad/pdfs_comision_verdad/`).
- Configuración: gemma4:12b con think apagado (proxy propio), embeddings bge-m3, búsqueda vectorial, Top K 6, chunks de 2048 con overlap 256.
- Concurrencia: con 5 preguntas a la vez ~30 s de mediana; con 10 pasa de 1 min. Sirvió como prueba de que un modelo local es viable, no como prototipo.
- Pendiente de traer a esta carpeta: `proxy_nothink.py` y `prueba_concurrencia_*.py` (están en el Project).

## Octubre–noviembre 2026 — Cruce con las bases legado

- `05_cruce_natalia/cruce_natalia.py` cruzó los documentos de las bases legado contra los candidatos del repositorio. Resultado entregado en `entregables/cruce_excel_repo_unal_2excels_propios.xlsx`.

## Noviembre 2026 — Clasificación con IA

- Muestra de 300 documentos para medir la IA (`06_clasificacion_ia/muestra_clasificacion.py`): grupos AJUSTE (100) y EVALUACIÓN (200), semilla 2026. La coordinación la clasificó a mano (`fuentes/Muestra_clasificacion_Natalia.xlsx`).
- `prompt_clasificacion.py` (prompt v1-2026-11-15) + `clasificar_ia.py` (Ollama, salida estructurada, reanuda desde `.jsonl`) + `evaluar.py` (compara contra la muestra; métrica: "¿llega a revisión?").
- Clases: INCLUIR, POSIBLE (ante la duda), EXCLUIR; REVISAR = sin resumen o con menos de 100 caracteres (no pasa por el modelo).
- Criterio: lo social alrededor de la tierra (reforma agraria); no tiene que estar ligado a paz o conflicto.
- Modelo final: **gemma4:31b-it-qat** en el Nodo 10 (RTX 3090), sin think, `--paralelo 2 --num-ctx 8192`.
  - EVALUACIÓN: 14 de 15 positivos detectados; 12 de 185 de más a revisión.
- Corrida total (17–18 nov, 11 h 38 min): **INCLUIR 1.026 · POSIBLE 1.072 · EXCLUIR 13.330 · REVISAR 704**. Salida: `datos/total_g31.xlsx`.
- Decisiones: se dejan los INCLUIR con dimensión agraria "secundaria" (dan variedad al corpus); no se hace pasada por título de los REVISAR.

## Noviembre 2026 — Prototipo en Dify

- `07_prototipo_dify/armar_excel_revision.py`: Excel de revisión para la coordinación (Resumen, Cómo leer, 2011-2021, Otros años, REVISAR). Entregado en `entregables/`.
- `07_prototipo_dify/armar_db.py`: DB tentativa = los **575 INCLUIR de 2011–2021** con todas las columnas del reporte, reordenadas y renombradas, ID = número del handle.
- Plan del prototipo: gemma4:31b en dos apps de Dify sobre la misma base (una respuesta concisa y otra analítica), para que el equipo pruebe estilo de respuesta, citas y qué hace cuando no sabe. La comparación de modelos la hace el equipo técnico.
- Siguiente: script para bajar los PDFs del repositorio y subirlos a Dify por API (los PDFs viven solo en el Nodo 10).

## 19 nov 2026 — Orden del repositorio

- Se ordenó la carpeta por etapas y se empezó a usar git solo para código y documentación (`.gitignore` ignora Excels, CSV, PDFs y carpetas de datos). Los datos se sincronizan entre equipos con Syncthing.
