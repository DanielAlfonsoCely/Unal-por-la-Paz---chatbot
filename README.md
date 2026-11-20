# Unal por la Paz — chatbot

Asistente de IA (RAG) sobre material producido por la Universidad Nacional de Colombia, enfocado en reforma agraria y lo social alrededor de la tierra.

El trabajo de cada etapa está en su propia carpeta, numerada en el orden en que se hizo. La historia completa, con fechas y decisiones, está en [`docs/bitacora.md`](docs/bitacora.md).

## Estructura

| Carpeta | Qué hay |
|---|---|
| `fuentes/` | Datos de entrada que nos dieron (reporte de objetos del repositorio, bases legado, muestra clasificada a mano). |
| `01_analisis_reporte/` | Primer análisis del reporte de objetos: estadísticas 2011–2021. |
| `02_filtro_dewey/` | Filtro por clasificación Dewey y análisis de coocurrencia de códigos. |
| `03_medicion_pesos/` | Medición del peso de los archivos de los candidatos por la API del repositorio. |
| `04_prueba_local_comision_verdad/` | Prueba de capacidad local (Dify + Ollama) con los libros del Informe Final de la Comisión de la Verdad. |
| `05_cruce_natalia/` | Cruce de las bases legado contra los candidatos del repositorio. |
| `06_clasificacion_ia/` | Clasificación documento por documento con un LLM local (prompt, script, evaluación contra la muestra). |
| `07_prototipo_dify/` | Excels de revisión y DB tentativa para el prototipo en Dify. |
| `entregables/` | Excels que se entregaron al equipo. |
| `docs/` | Bitácora y documentación. |

Dentro de cada etapa, los scripts están arriba y los resultados en `datos/`.

## Qué se sube a GitHub y qué no

- **Sí**: código (`.py`) y documentación (`.md`).
- **No**: Excels, CSV, PDFs, `.jsonl`, `.pkl` y las carpetas `fuentes/`, `entregables/` y `datos/` (ver `.gitignore`). Esos archivos se sincronizan entre equipos con Syncthing.

## Entorno

Python 3 con `pandas`, `openpyxl` y `requests`. Los scripts de clasificación hablan con Ollama (`/api/chat`).
