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
- `armar_excel_filtrados.py` arma el Excel de los candidatos para la coordinación (Resumen, Gráficas, Documentos, Cómo se filtró) y `quitar_descartados_excel.py` le quita a las gráficas los códigos Dewey descartados.
- `coocurrencia_dewey.py` ayudó a decidir las reglas condicionales (qué códigos van solos y con cuáles se acompañan).

## Octubre 2026 — Peso de los archivos

- `03_medicion_pesos/medir_pesos_total.py` consultó la API del repositorio (handle → bundles → ORIGINAL → bitstreams) para los 8.837: **52,1 GB** (44 GB en PDF). Ningún archivo se descargó; solo se midió.

## Octubre 2026 — Prueba de capacidad local (Comisión de la Verdad)

- Prueba en la torre (RX 9060 XT 16 GB): Dify + Ollama con 23 libros del Informe Final de la Comisión de la Verdad (`04_prueba_local_comision_verdad/pdfs_comision_verdad/`).
- Configuración: gemma4:12b con think apagado (proxy propio), embeddings bge-m3, búsqueda vectorial, Top K 6, chunks de 2048 con overlap 256.
- Concurrencia: con 5 preguntas a la vez ~30 s de mediana; con 10 pasa de 1 min. Sirvió como prueba de que un modelo local es viable, no como prototipo.
- Scripts: `proxy_nothink.py` (proxy que apaga el think de gemma4) y `prueba_concurrencia_ollama.py` / `prueba_concurrencia_dify.py` (N usuarios a la vez, directo a Ollama o pasando por Dify).

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

## 20 nov 2026 — Descarga de PDFs y acceso desde la torre

- Acceso SSH desde la torre Windows al Nodo 10 (Tailscale + llave `dani_ssh_torre`, alias `nodo10`).
- `07_prototipo_dify/armar_manifiesto.py`: cruza la DB de los 575 INCLUIR con `03_medicion_pesos/datos/pesos_archivos.csv` (que ya trae URL de descarga, tamaño y md5) y arma `datos/manifiesto_descarga.csv`: 598 archivos de 568 ítems, ~2,57 GB. Nombre destino "Título (año).pdf"; varios PDF por ítem → " - parte N"; choques entre ítems → " [unal-ID]".
- Quedan fuera 7 ítems: 4 restringidos (401 en la medición del 5-oct: 77684, 77719, 77889, 80285), 2 solo EPUB (77814, 81737) y 1 sin archivo (79199). Se incluyen 2 con extensión rara (53991, 79948); se confirman por la cabecera `%PDF`.
- `07_prototipo_dify/descargar_pdfs.py` (corre en el Nodo 10, dentro de tmux): descarga a `.part`, verifica `%PDF`, tamaño y md5, y recién ahí renombra. Reanudable; registra fallos en `resultados_descarga.csv`. Opciones `--prueba`, `--limite`, `--hilos`.
- Decisión: los PDFs viven solo en el Nodo 10, fuera de lo que se sincroniza (`.stignore` del Nodo 10).

## 21 nov 2026 — Dify en el Nodo 10, base de conocimiento y primeras pruebas

- Dify 1.16.1 en el Nodo 10 (`~/dify`), conectado a Ollama (gemma4:31b-it-qat y bge-m3) con `host.docker.internal` (override `extra_hosts` para `api` y `plugin_daemon`; Ollama escucha en `0.0.0.0`). Plugin de Ollama instalado desde archivo `.difypkg` (el Marketplace no respondía). Límites de subida: `UPLOAD_FILE_SIZE_LIMIT=200` y `NGINX_CLIENT_MAX_BODY_SIZE=250M` (22 PDFs pasaban de 15 MB; el mayor, 148 MB).
- `07_prototipo_dify/subir_a_dify.py`: crea (o reutiliza) la base "Prototipo paz INCLUIR 2011-2021" por la API de conocimiento y sube los 598 PDFs con máximo 6 indexándose a la vez. Reanudable (`estado_subida.csv`). Opciones `--prueba`, `--limite`, `--cola`, `--solo-estado`, `--reintentar`.
  - Config: búsqueda **híbrida 0.7 vectorial / 0.3 palabras clave**, sin reranker, Top K 6, fragmentos de 2048 con solapamiento 256, bge-m3.
  - Metadata por documento (13 campos, desde la DB): título, autor, director, año, tipo, nivel, sede, facultad, colección, dewey, temas, link e id del repositorio. Grupo y línea de investigación quedaron fuera por datos incompletos.
  - Algunos documentos fallaron al indexar por agotamiento del pool de conexiones de Dify mientras se usaba el chat al mismo tiempo. Se reintentan con `--reintentar`. Regla: no usar el chat mientras se indexa.
- Dos apps Chatbot sobre la misma base: concisa y analítica (prompts en `07_prototipo_dify/prompts_apps_dify.md`), gemma4:31b con razonamiento encendido.
  - El filtrado automático por metadata dejaba el contexto vacío en el link público: queda desactivado. Filtros elegidos por el usuario (botones) = idea a futuro con un Chatflow.
  - Primera prueba: respondió solo con el contexto y citó bien, pero tardó ~100 s (≈70 s razonando). Los fragmentos traen enlaces de imágenes del PDF que ensucian el texto.
- `07_prototipo_dify/probar_apps.py`: batería de 12 preguntas contra las dos apps por API, una a la vez; guarda respuesta, razonamiento, tiempos y fragmentos recuperados en `datos/pruebas_apps_<etiqueta>.jsonl` y `.csv`, para comparar con y sin razonamiento.
- Pendiente: correr la batería (con y sin razonamiento), confirmar los 598 documentos disponibles, ngrok en el Nodo 10 y compartir con la coordinación.

## 24 nov 2026 — Reunión con la coordinación, ampliación del corpus y plan para la demo

- Reunión (Jairo, Natalia, Daniela): el corpus actual (575 documentos) se queda corto; la versión concisa no convenció (se usa la analítica); cuando no hay respuesta igual se mostraban los 6 fragmentos abajo (confunde); falta que el chat conozca título, autor, año y link de sus fuentes; se quiere UI propia y preguntas sugeridas. Prueba el jueves, presentación a la Vicerrectoría el viernes.
- Pregunta de Jairo ("los puntos de... con un punto de género"): son los 14 principios de la Reforma Rural Integral (punto 1 del Acuerdo). El chat no supo porque el Acuerdo no está en el corpus → idea de una segunda base "Marco normativo" (por validar con la coordinación).
- `07_prototipo_dify/chatflow_v1_guia.md` + `nodos_codigo_chatflow.py`: Chatflow que numera las fuentes con sus metadatos, deja que el modelo cite [n] y arma la lista de fuentes solo con lo citado (si no cita, no hay lista). Citas automáticas de Dify apagadas. Filtros de año/tipo en modo Manual.
- `08_ampliacion_memoria_participacion/` (correo de Natalia del 23-nov): categorías Memoria histórica/colectiva y Participación política, 2011-2021.
  - `prompt_clasificacion.py` (mem-pol-v1-2026-11-24): misma estructura que el v1 de reforma agraria (alcance, NO ENTRA, decide el foco, ante la duda POSIBLE, evidencia literal, red de términos poco ambiguos). Se usa con una copia de `06_clasificacion_ia/clasificar_ia.py` en la misma carpeta.
  - `armar_entrada_ampliacion.py`: el filtro Dewey NO aplica (se armó para tierras). Entra todo el repositorio 2011-2021 que es texto: **21.280** (8.837 pasan Dewey, van primero; 12.443 resto). Las bases de Natalia van aparte (`entrada_bases.csv`, 1.027 que no están en el repositorio; 606 sin enlace, 226 de tipo no académico, 10 posibles duplicados) y son opcionales.
  - `armar_excel_ampliacion.py`: Excel de revisión con columna Fuente.
- `09_ui_propia/PROMPT_CLAUDE_CODE.md`: especificación de la UI propia sobre la API de Dify (plantilla MIT `webapp-conversation`), para tenerla antes de la reunión del jueves.
- Ajuste (24-nov noche): no se reclasifican los INCLUIR/POSIBLE de reforma agraria (1.145 en 2011-2021, ya van al corpus) y se priorizan las facultades de sociales, humanas y artes (pedido de Natalia). `entrada_repo.csv` = 20.135: 7.905 sociales/humanas/artes (~6,6 h), 3.206 otras que pasan Dewey (~2,7 h), 9.024 resto (~7,5 h). De las bases, `entrada_bases_con_enlace.csv` = 424 con enlace (118 de revistas.unal); se clasifican de últimas.
- Chatflow v1 como DSL importable (`07_prototipo_dify/generar_dsl_chatflow.py` → `chatflow_paz_v1.yml`, formato de Dify 1.16 versión 0.7.0). Las preguntas de seguimiento las escribe el modelo al final ("SUGERENCIAS:") sobre lo que los documentos sí responden; el Code 2 las deja en `<!--sugerencias:[...]-->` para la UI propia. Sin filtros en v1.
- Nombres de las bases según Natalia: **Red Paz** (= "Base final 2010-2021"), **Legado 1** (Legado de octubre, 377 filas) y **Legado 2** (base de William Mancera, 9-nov).
- Pendiente para la DB final unida: columna con la fuente de cada documento (Repositorio UNAL / Red Paz / Legado 1 / Legado 2). No cambia la corrida del Nodo 10: se arma con los resultados.
- Bases de Natalia (25-nov, con Natalia): no se descartan las que no tienen enlace (muchas sí tienen documento aunque el link no esté en la base). Se clasifican con lo que haya (título, síntesis/resumen, temas, eje temático) usando `--min-resumen 0`. Corridas separadas: `entrada_repo.csv` (prioridad, para el viernes) y `entrada_bases.csv` (Red Paz + Legado 1 + Legado 2 ya unidas y sin repetidos, solo 2011-2021; para después).
- Corridas en el Nodo 10 (desde `08_ampliacion_memoria_participacion/datos`): repositorio → `mempol_repo_g31.jsonl` (~17 h, paralelo 2, ctx 8k); bases → `mempol_bases_g31.jsonl` (`--min-resumen 0`, ~1 h). "g31" = gemma4:31b.
- Siguientes pasos: importar y probar `chatflow_paz_v1.yml`; UI propia con Claude Code (`09_ui_propia/`) lista antes de la reunión del jueves; Excel de la ampliación; DB final con columna de fuente; base "Marco normativo"; Aluna; skill de paz (al final). Paralelo 1 / ctx 16k para la demo solo después de que termine la clasificación.

## 24 nov 2026 (noche) — Prompt de la UI propia v2

- `09_ui_propia/PROMPT_CLAUDE_CODE.md` actualizado: identidad visual con colores de la UNAL (fondo blanco; franja verde #5F7E24 como en aluna.unal.edu.co; verde #466B3F y #94B43B, grises y rojo solo en detalles; paleta institucional 2016), logo en insignia circular arriba a la izquierda (`09_ui_propia/assets/logo-unal.png`, provisional hasta recibir el oficial de Unimedios), título central "Título por definir", frase breve y general, tipografía Ancízar con fallback, y modo demo (`DEMO_MODE`) para ver la UI sin API key de Dify.

## 25 nov 2026 — UI propia construida, Chatflow importado y UI conectada a Dify

- `09_ui_propia/`: app Next.js (hecha con Claude Code) sobre la API de Dify. Rutas del servidor `/api/*` reenvían a Dify (la API key nunca llega al navegador), streaming, citas [n] con tooltip, tarjetas de fuentes, preguntas sugeridas (de `/parameters` y del comentario `<!--sugerencias:[...]-->`), historial, aviso al pie, errores amables y modo demo (`DEMO_MODE=true`). Identidad UNAL: fondo blanco, franja verde `#5F7E24` como en aluna.unal.edu.co, logo provisional en insignia circular (`assets/logo-unal.png`, a reemplazar por el oficial de Unimedios), título "Título por definir". Textos y logo en `lib/config.ts`; colores en `app/globals.css`. Dockerfile + `docker-compose.yml` para el Nodo 10 (puerto 3000, `host.docker.internal`). `tsc` sin errores; probada en modo demo.
- `07_prototipo_dify/chatflow_paz_v1.yml` importado en Dify y probado en la vista previa (respuesta con citas y lista de fuentes con link). Se eligió la base "Prototipo paz INCLUIR 2011-2021" en el nodo de búsqueda. Solo el nodo "Redactar respuesta" usa IA; el contexto, la lista de fuentes y las sugerencias los arman los dos nodos Code (scripts). Al modelo solo le llega `[n] Título — autor, año, tipo` + fragmentos (no link, Dewey, id ni score). Pendiente a futuro: agregar director/facultad al encabezado para preguntas de metadatos; renumerar las fuentes en orden de cita.
- Dify del Nodo 10: el editor se quedaba en "Sincronizando datos" porque la colaboración en tiempo real usa un websocket a `NEXT_PUBLIC_SOCKET_URL` (por defecto `ws://localhost`, que desde la laptop apunta a la laptop). Se puso `NEXT_PUBLIC_SOCKET_URL=ws://100.103.228.104` y luego `ENABLE_COLLABORATION_MODE=false` en `~/dify/docker/.env` (se trabaja solo). Lección: tras recrear contenedores con `docker compose up -d` hay que hacer `docker compose restart nginx` (si no, 502) y volver a iniciar sesión en Dify.
- Estado de la clasificación de la ampliación (25-nov 10:10): 88,6 % (17.839/20.135), INCLUIR 548 · POSIBLE 890 · EXCLUIR 16.060 · REVISAR 341; termina hacia las 12:10.
- Siguiente: ngrok al puerto 3000 del Nodo 10 con la UI en Docker (la política de ngrok de la carpeta 07 bloquea `/` y no sirve para la UI), Excel de la ampliación, base "Marco normativo".

## 25 nov 2026 (mediodía) — UI en Docker, ngrok al 3000 y siguientes pasos

- La UI propia (09_ui_propia) quedó corriendo en Docker en el Nodo 10 (puerto 3000, contenedor `unal-paz-ui`, `host.docker.internal` hacia Dify). ngrok pasó al puerto 3000 con el mismo dominio fijo y sin policy (la anterior bloqueaba "/"). Probado desde el celular con datos móviles: funciona.
- Dify: colaboración desactivada (`ENABLE_COLLABORATION_MODE=false`). Tras recrear api/web: `docker compose restart nginx` y volver a iniciar sesión.
- Clasificación de la ampliación (Memoria histórica + Participación política, 2011-2021): 18.729/20.135 a las 10:57; INCLUIR 548 · POSIBLE 896 · EXCLUIR 16.940 · REVISAR 345. Termina ~12:10.
- Marco normativo: segunda base de conocimiento (normas, tipo "Norma") con segundo nodo de recuperación en el chatflow; lista propuesta por validar con la coordinación.
- Pendiente: Excel de la ampliación, bases de Natalia, paralelo 1 / ctx 16k para la demo, `.stignore` con node_modules y .next, logo oficial (Unimedios), título final.
