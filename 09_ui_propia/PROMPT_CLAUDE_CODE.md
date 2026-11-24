# Prompt para Claude Code — UI propia del chatbot "UNAL por la Paz"

Copia todo lo que está debajo de la línea en Claude Code, abierto en la carpeta `09_ui_propia/` del repo
(en la laptop o la torre). Cuando funcione en local, se copia al Nodo 10 y se levanta con Docker.

---

Necesito una interfaz web propia para un chatbot de investigación que ya funciona en Dify (self-hosted, versión 1.16.1).
La UI NO reemplaza a Dify: Dify sigue siendo el backend (modelo, búsqueda en la base de conocimiento, lógica del Chatflow).
La UI solo habla con la API de Dify. Es para una demo ante la Vicerrectoría de la Universidad Nacional de Colombia
el jueves, así que tiene que verse muy profesional y funcionar sin fallas.

## Base técnica
- Parte de la plantilla oficial MIT de Dify: https://github.com/langgenius/webapp-conversation (Next.js). Clónala dentro de
  esta carpeta y modifícala; si te resulta más limpio, haz una app Next.js nueva tomando de ahí el manejo del streaming.
- La API key de la app de Dify NUNCA va al navegador: todas las llamadas pasan por rutas del servidor de Next.js
  (`/api/...`) que reenvían a Dify. Variables de entorno en `.env.local` (y un `.env.example` sin secretos):
  `DIFY_API_URL` (ej. `http://localhost/v1` en el Nodo 10), `DIFY_APP_KEY`.
- Endpoints de Dify que se usan (app tipo Chatflow / advanced-chat):
  - `GET /parameters` → mensaje de bienvenida (`opening_statement`), preguntas sugeridas iniciales (`suggested_questions`),
    variables del formulario de inicio (`user_input_form`), si están activas las preguntas de seguimiento.
  - `POST /chat-messages` con `response_mode: "streaming"` (SSE), `inputs`, `query`, `conversation_id`, `user`.
  - `GET /messages/{message_id}/suggested?user=...` → preguntas de seguimiento después de cada respuesta.
  - `GET /conversations`, `GET /messages`, `DELETE /conversations/{id}` para el historial.
  - `POST /chat-messages/{task_id}/stop` para detener una respuesta.
- Un identificador de usuario anónimo por navegador (uuid en localStorage, envuelto en try/catch).
- Dockerfile + `docker-compose.yml` para correrla en el Nodo 10 (Linux) en el puerto 3000, en la misma máquina que Dify.

## Qué debe tener la pantalla
1. **Identidad**: nombre "UNAL por la Paz — Asistente de investigación", subtítulo corto ("Consulta la producción académica
   de la Universidad Nacional sobre tierra, conflicto y construcción de paz"). Estilo sobrio e institucional (no copies
   logos oficiales; usa un color base verde oscuro o vinotinto, tipografía limpia, mucho aire). Modo claro; responsive (celular).
2. **Chat** con streaming palabra por palabra, render de Markdown (negritas, listas, links que abren en pestaña nueva),
   botón detener, botón copiar respuesta, indicador "Buscando en los documentos…" mientras llega el primer token.
3. **Fuentes**: la respuesta del Chatflow ya trae al final un bloque `---\n**Fuentes**` con las referencias numeradas y
   su link al repositorio. Detéctalo y muéstralo como tarjetas debajo de la respuesta (título, autor/año, botón
   "Ver en el repositorio"). Si la respuesta NO trae ese bloque, no muestres ninguna sección de fuentes.
   Los números [1], [2] dentro del texto deben verse como pequeñas etiquetas que al pasar el mouse muestran el título.
4. **Preguntas sugeridas**: al iniciar, las de `/parameters` como chips encima del campo de texto; después de cada
   respuesta, las de `/messages/{id}/suggested`, también como chips encima del campo de texto. Clic = se envía.
5. **Filtros** (panel lateral plegable o fila de controles arriba del chat): campos que vienen en `user_input_form`
   (por ahora: año desde, año hasta, tipo de documento). Se mandan en `inputs`. Si el usuario cambia un filtro,
   avisa que aplica desde la siguiente pregunta. Todos opcionales.
6. **Historial** de conversaciones en una barra lateral (nueva conversación, abrir, borrar).
7. **Aviso** discreto en el pie: "Prototipo en pruebas. Las respuestas se basan solo en documentos del repositorio de la
   UNAL (2011–2021) y pueden contener errores; verifica en las fuentes."
8. Manejo de errores amable (Dify caído, tiempo de espera largo: el modelo puede tardar 30–90 s en responder, no cortes
   la conexión antes de 180 s).
9. Deja preparado (oculto tras una constante) un selector de "modo" para el futuro: "Consultar documentos" /
   "Orientar un proyecto de paz".

## Entregables
- Código en esta carpeta, README corto con: cómo correr en local (`npm install`, `npm run dev`), cómo construir y correr
  con Docker en el Nodo 10, y qué variables configurar.
- Antes de terminar: corre `npm run build` sin errores y prueba contra la API real si `DIFY_API_URL` responde.
