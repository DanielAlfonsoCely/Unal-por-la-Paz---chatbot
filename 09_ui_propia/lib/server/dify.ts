import 'server-only'

// Solo se usa en rutas del servidor: la API key nunca llega al navegador.

export function isDemo(): boolean {
  return (process.env.DEMO_MODE || '').trim().toLowerCase() === 'true'
}

export function difyBase(): string {
  return (process.env.DIFY_API_URL || 'http://localhost/v1').trim().replace(/\/+$/, '')
}

export function difyKey(): string {
  return (process.env.DIFY_APP_KEY || '').trim()
}

export function isConfigured(): boolean {
  return difyKey().length > 0
}

/** Respuesta JSON de error con mensaje amable en español. */
export function errorJson(status: number, message: string, code = 'error') {
  return Response.json({ code, message }, { status })
}

export function noKeyError() {
  return errorJson(
    503,
    'El asistente todavía no está conectado a Dify (falta DIFY_APP_KEY en .env.local). Activa DEMO_MODE=true para probar la interfaz.',
    'not_configured',
  )
}

/** Traduce un error de Dify (o de red) a un mensaje para la persona usuaria. */
export async function translateDifyError(res: Response): Promise<Response> {
  let body: { code?: string; message?: string } = {}
  try {
    body = await res.json()
  } catch {}
  const code = body.code || `http_${res.status}`
  let message = 'El asistente tuvo un problema al procesar la solicitud. Intenta de nuevo en un momento.'
  if (res.status === 401) message = 'La clave de acceso a Dify no es válida. Revisa DIFY_APP_KEY.'
  else if (code === 'app_unavailable') message = 'La aplicación de Dify no está disponible (¿el Chatflow está publicado?).'
  else if (res.status === 404 && /conversation/i.test(body.message || ''))
    message = 'Esa conversación ya no existe. Empieza una nueva.'
  else if (res.status === 429) message = 'Hay demasiadas consultas en este momento. Espera unos segundos e intenta de nuevo.'
  else if (code === 'provider_not_initialize' || code === 'provider_quota_exceeded' || code === 'model_currently_not_support')
    message = 'El modelo de lenguaje no está disponible en este momento. Intenta de nuevo más tarde.'
  else if (res.status >= 500) message = 'El servidor del asistente no responde correctamente. Intenta de nuevo en un momento.'
  console.error('[dify]', res.status, code, body.message)
  return errorJson(res.status >= 400 && res.status < 600 ? res.status : 502, message, code)
}

export function networkError(e: unknown): Response {
  const name = (e as Error)?.name
  console.error('[dify] error de red:', e)
  if (name === 'TimeoutError' || name === 'AbortError')
    return errorJson(504, 'El asistente tardó demasiado en responder. Intenta de nuevo.', 'timeout')
  return errorJson(
    502,
    'No pudimos comunicarnos con el servidor del asistente. Puede estar apagado o sin conexión; intenta de nuevo en unos minutos.',
    'unreachable',
  )
}

/** fetch hacia Dify con la key y un tiempo máximo. */
export async function difyFetch(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<Response> {
  const { timeoutMs = 20_000, signal, headers, ...rest } = init
  const signals: AbortSignal[] = [AbortSignal.timeout(timeoutMs)]
  if (signal) signals.push(signal)
  return fetch(`${difyBase()}${path}`, {
    ...rest,
    cache: 'no-store',
    signal: AbortSignal.any(signals),
    headers: {
      Authorization: `Bearer ${difyKey()}`,
      'Content-Type': 'application/json',
      ...(headers || {}),
    },
  })
}
