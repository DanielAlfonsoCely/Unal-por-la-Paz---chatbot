# Prompt para Claude Code — UI propia del chatbot de paz (UNAL)

Cómo usarlo: abre Claude Code dentro de `09_ui_propia/` (laptop o torre) y pídele que lea este archivo completo
y lo construya. Cuando funcione en local, se copia al Nodo 10 y se levanta con Docker.

Versión 2 (24-nov noche): identidad visual con los colores de la UNAL, logo en `assets/logo-unal.png`,
título "por definir", modo demo sin API key.

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
  `DIFY_API_URL`, `DIFY_APP_KEY`, `DEMO_MODE`.
- Conexión: Dify corre en el Nodo 10. Desde la laptop se llega por Tailscale: `DIFY_API_URL=http://100.103.228.104/v1`.
  Dentro del contenedor de la UI en el Nodo 10 se usa `http://host.docker.internal/v1`
  (con `extra_hosts: ["host.docker.internal:host-gateway"]` en el compose).
- La API key de la app todavía no existe (falta importar el Chatflow en Dify). Deja todo listo para que yo solo pegue la
  key en `.env.local` (`DIFY_APP_KEY`).
- **Modo demo**: con `DEMO_MODE=true` la UI no llama a Dify y simula una respuesta en streaming: texto con citas
  [1] [2], un bloque final `---\n**Fuentes**` con 2 fuentes de ejemplo y el comentario
  `<!--sugerencias:["...","...","..."]-->`. Con `DEMO_MODE=false` habla con la API real. Así se puede ver y probar toda
  la interfaz sin Dify.
- Endpoints de Dify que se usan (app tipo Chatflow / advanced-chat):
  - `GET /parameters` → mensaje de bienvenida (`opening_statement`), preguntas sugeridas iniciales (`suggested_questions`),
    variables del formulario de inicio (`user_input_form`), si están activas las preguntas de seguimiento.
  - `POST /chat-messages` con `response_mode: "streaming"` (SSE), `inputs`, `query`, `conversation_id`, `user`.
  - `GET /conversations`, `GET /messages`, `DELETE /conversations/{id}` para el historial.
  - `POST /chat-messages/{task_id}/stop` para detener una respuesta.
  - NO uses `/messages/{id}/suggested`: está apagado a propósito (esas preguntas no salen de los documentos).
- Un identificador de usuario anónimo por navegador (uuid en localStorage, envuelto en try/catch).
- Dockerfile + `docker-compose.yml` para correrla en el Nodo 10 (Linux) en el puerto 3000, en la misma máquina que Dify.
  Es un contenedor aparte: NO modifiques la carpeta ni los contenedores de Dify.

## Identidad visual (Universidad Nacional de Colombia)
Referencia: los sitios de la U (aluna.unal.edu.co y web.unal.edu.co). Imítalos en estructura y sobriedad, sin copiar
contenido ni usar otros logos.

- **Fondo base: blanco.** El resto de colores se usan solo para detalles (encabezado, botones, enlaces, chips, bordes).
- **Colores** (guía de identidad visual UNAL, paleta institucional; defínelos como variables CSS en un solo lugar):
  - Verde de la franja del encabezado: `#5F7E24` (tomado de los sitios de la U).
  - Verde oscuro institucional: `#466B3F` (botones, enlaces, texto destacado).
  - Verde claro institucional: `#94B43B` (acentos pequeños: chips, estado activo).
  - Gris oscuro `#565A5C` (texto secundario) y `#333333` (franja superior fina del encabezado).
  - Gris claro `#B1B2B0` (bordes y divisores).
  - Rojo `#A61C31` (oscuro `#76232F`) solo para detalles puntuales: botón detener y errores.
  - No uses el morado/azul de la página de la DNED. Verifica el contraste del texto sobre cada fondo.
- **Tipografía**: Ancízar (familia institucional, de uso libre para la comunidad universitaria) como primera opción, con
  fallback a una sans-serif limpia. Si no puedes descargarla, usa el fallback y deja un comentario en el CSS
  indicando dónde poner los archivos de fuente.
- **Encabezado** (como en los sitios de la U):
  - Franja superior fina gris oscuro (`#333333`) y debajo una franja verde (`#5F7E24`).
  - **Logo arriba a la izquierda**: el escudo va dentro de una insignia circular blanca que cuelga del borde superior y
    se superpone a las franjas, igual que en aluna.unal.edu.co. Usa el archivo `assets/logo-unal.png` (313×313, escudo
    en verde claro sobre blanco; cópialo a `public/`). Es un archivo provisional que yo reemplazo por el oficial de
    Unimedios, así que cárgalo desde una sola ruta/constante. NO dibujes ni inventes un escudo; si el archivo no existe,
    muestra un círculo neutro con el texto "UNAL".
  - **Título al centro**: texto temporal **"Título por definir"** (una sola constante fácil de cambiar).
  - Debajo del título, una frase muy breve y general: "Consulta la producción académica de la Universidad Nacional."
    (otra constante editable).
- Estilo sobrio e institucional, mucho aire, esquinas suavemente redondeadas, modo claro, responsive (celular).

## Qué debe tener la pantalla
1. **Encabezado** como arriba.
2. **Chat** con streaming palabra por palabra, render de Markdown (negritas, listas, links que abren en pestaña nueva),
   botón detener, botón copiar respuesta, indicador "Buscando en los documentos…" mientras llega el primer token.
3. **Fuentes**: la respuesta del Chatflow ya trae al final un bloque `---\n**Fuentes**` con las referencias numeradas y
   su link al repositorio. Detéctalo y muéstralo como tarjetas debajo de la respuesta (título, autor/año, botón
   "Ver en el repositorio"). Si la respuesta NO trae ese bloque, no muestres ninguna sección de fuentes.
   Los números [1], [2] dentro del texto deben verse como pequeñas etiquetas que al pasar el mouse muestran el título.
4. **Preguntas sugeridas**: al iniciar, las de `/parameters` (`suggested_questions`) como chips encima del campo de
   texto. Después de cada respuesta, el Chatflow agrega al final un comentario HTML
   `<!--sugerencias:["pregunta 1","pregunta 2","pregunta 3"]-->` (JSON). Quítalo del texto mostrado y pinta esas
   preguntas como chips encima del campo de texto. Clic = se envía.
5. **Filtros** (panel lateral plegable o fila de controles arriba del chat): los campos que vengan en
   `user_input_form` (la versión 1 del Chatflow todavía no trae ninguno; luego vendrán año desde, año hasta y tipo de
   documento). Si no viene ninguno, no muestres el panel. Se mandan en `inputs`. Si el usuario cambia un filtro,
   avisa que aplica desde la siguiente pregunta. Todos opcionales.
6. **Historial** de conversaciones en una barra lateral (nueva conversación, abrir, borrar).
7. **Aviso** discreto en el pie: "Prototipo en pruebas. Las respuestas se basan solo en documentos del repositorio de la
   UNAL y pueden contener errores; verifica en las fuentes."
8. Manejo de errores amable (Dify caído, tiempo de espera largo: el modelo puede tardar 30–90 s en responder, no cortes
   la conexión antes de 180 s).
9. Deja preparado (oculto tras una constante) un selector de "modo" para el futuro: "Consultar documentos" /
   "Orientar un proyecto de paz".

## Reglas
- No toques ninguna carpeta fuera de `09_ui_propia/`. No hagas `git commit` ni `git push` (lo hago yo).

## Entregables
- Código en esta carpeta, README corto con: cómo correr en local (`npm install`, `npm run dev`), cómo usar el modo demo,
  cómo construir y correr con Docker en el Nodo 10, qué variables configurar y cómo cambiar el logo, el título y la frase.
- Antes de terminar: corre `npm run build` sin errores y prueba contra la API real si `DIFY_API_URL` responde.
- Al final dime exactamente qué comandos corro para verla en local y qué falta para conectarla a Dify.
