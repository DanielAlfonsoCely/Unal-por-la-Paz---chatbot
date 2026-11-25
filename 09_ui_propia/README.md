# UI propia del chatbot (UNAL)

Interfaz web (Next.js) para el Chatflow de Dify. Dify sigue siendo el backend; esta app solo
habla con su API a través de rutas del servidor (`/api/...`), así que la API key nunca llega al navegador.

## Correr en local

```bash
cd 09_ui_propia
npm install
cp .env.example .env.local     # solo la primera vez; ya viene con DEMO_MODE=true
npm run dev                    # abre http://localhost:3000
```

Para probar la versión de producción: `npm run build && npm start`.

## Variables (`.env.local`)

| Variable | Qué es |
|---|---|
| `DIFY_API_URL` | URL de la API de Dify, termina en `/v1`. Laptop (Tailscale): `http://100.103.228.104/v1`. Nodo 10 sin Docker: `http://localhost/v1`. Dentro del contenedor la fija el compose: `http://host.docker.internal/v1`. |
| `DIFY_APP_KEY` | API key de la app (Dify → la app → *Acceso a la API* → *API Key*, empieza por `app-`). |
| `DEMO_MODE` | `true`: no llama a Dify y simula respuestas. `false`: usa la API real. |

Después de cambiar `.env.local`, reinicia `npm run dev` (o el contenedor).

## Modo demo

Con `DEMO_MODE=true` la interfaz completa funciona sin Dify: bienvenida y preguntas sugeridas,
una respuesta simulada en streaming con citas [1] [2], tarjetas de fuentes, preguntas de seguimiento,
botones detener y copiar, e historial (en memoria del servidor; se borra al reiniciar). En el encabezado
aparece la etiqueta "Modo demostración". Los textos de ejemplo están en `lib/server/demo.ts`.

## Conectar con Dify

1. Importar `07_prototipo_dify/chatflow_paz_v1.yml` en Dify y **publicarlo**.
2. Copiar la API key de la app y pegarla en `.env.local` → `DIFY_APP_KEY=app-...`
3. Poner `DEMO_MODE=false` y reiniciar.

Si algo falla, la UI muestra un mensaje amable (Dify caído, key inválida, Chatflow sin publicar, tiempo de espera).
No corta la conexión antes de 180 s, porque el modelo puede tardar 30–90 s.

## Docker en el Nodo 10

```bash
# copiar la carpeta 09_ui_propia al Nodo 10 (sin node_modules ni .next), luego allí:
cd 09_ui_propia
cp .env.example .env.local   # pegar DIFY_APP_KEY y poner DEMO_MODE=false
docker compose up -d --build
docker compose logs -f ui    # ver registros
```

Queda en `http://<ip-del-nodo-10>:3000`. El compose fija `DIFY_API_URL=http://host.docker.internal/v1`
(con `extra_hosts: host-gateway`), así que no hay que cambiarla en `.env.local`. Es un contenedor aparte:
no toca la carpeta ni los contenedores de Dify. La key no se copia dentro de la imagen; se lee de `.env.local` al arrancar.

Para actualizar después de un cambio: `docker compose up -d --build`. Para detener: `docker compose down`.

Si el contenedor no llega a Dify, revisa que el firewall del Nodo 10 deje pasar tráfico de la red de Docker
al puerto 80 del host. Puedes probarlo con `docker exec unal-paz-ui wget -qO- http://host.docker.internal/v1/parameters`
(una respuesta 401 significa que sí llega).

## Cambiar logo, título y frase

Todo está en **`lib/config.ts`**:

- `TITULO`: título central (ahora "Título por definir").
- `SUBTITULO`: frase debajo del título.
- `LOGO_SRC`: ruta del logo. Lo más fácil es reemplazar `public/logo-unal.png` por el oficial, con el mismo nombre.
  Si el archivo no carga, se muestra un círculo con el texto "UNAL".
- `AVISO`: texto del pie.
- `MOSTRAR_SELECTOR_MODO`: selector "Consultar documentos / Orientar un proyecto de paz" (oculto, `false`).
  Si lo activas, el valor se envía en `inputs.modo`, así que el Chatflow necesita esa variable en el nodo Inicio.

Colores: variables CSS al inicio de `app/globals.css`. Tipografía Ancízar: el mismo archivo explica dónde poner las fuentes.

## Estructura

- `app/api/*`: rutas del servidor que reenvían a Dify (`parameters`, `chat` en streaming, `chat/[taskId]/stop`,
  `conversations`, `messages`). En modo demo responden desde `lib/server/demo.ts`.
- `components/`: encabezado, historial, chat, filtros, campo de texto.
- `lib/parse.ts`: separa el texto, el bloque `---\n**Fuentes**` y el comentario `<!--sugerencias:[...]-->`.

Notas:
- Los filtros salen de `user_input_form` del Chatflow. La v1 no trae ninguno, así que el panel no se muestra.
- Dify fija los `inputs` de una conversación cuando esta empieza. Cuando existan filtros, comprueba si un cambio
  de filtro dentro de una conversación ya iniciada se aplica; si no se aplica, el cambio tendrá efecto en una conversación nueva.
- El Chatflow entrega la respuesta en un solo bloque (sale de un nodo de código), así que la UI la revela palabra por palabra.
