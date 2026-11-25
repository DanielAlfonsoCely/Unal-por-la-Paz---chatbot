import { NextRequest } from 'next/server'
import { difyFetch, errorJson, isConfigured, isDemo, networkError, noKeyError, translateDifyError } from '@/lib/server/dify'
import { demoChatStream } from '@/lib/server/demo'
import { badUser, cleanUser } from '@/lib/server/user'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

// El modelo puede tardar 30–90 s; nunca cortamos antes de 180 s.
const UPSTREAM_TIMEOUT_MS = 240_000

export async function POST(req: NextRequest) {
  let body: { query?: unknown; conversation_id?: unknown; inputs?: unknown; user?: unknown }
  try {
    body = await req.json()
  } catch {
    return errorJson(400, 'Solicitud inválida.')
  }
  const user = cleanUser(body.user)
  if (!user) return badUser()
  const query = typeof body.query === 'string' ? body.query.trim() : ''
  if (!query) return errorJson(400, 'Escribe una pregunta.')
  if (query.length > 4000) return errorJson(400, 'La pregunta es demasiado larga (máximo 4000 caracteres).')
  const conversation_id = typeof body.conversation_id === 'string' && body.conversation_id ? body.conversation_id : undefined
  const inputs: Record<string, string | number> = {}
  if (body.inputs && typeof body.inputs === 'object') {
    for (const [k, v] of Object.entries(body.inputs as Record<string, unknown>)) {
      if (typeof v === 'string' && v.trim() !== '') inputs[k] = v.trim()
      else if (typeof v === 'number' && Number.isFinite(v)) inputs[k] = v
    }
  }

  if (isDemo()) return demoChatStream({ query, user, conversation_id, signal: req.signal })
  if (!isConfigured()) return noKeyError()

  let upstream: Response
  try {
    upstream = await difyFetch('/chat-messages', {
      method: 'POST',
      timeoutMs: UPSTREAM_TIMEOUT_MS,
      signal: req.signal,
      body: JSON.stringify({ query, inputs, conversation_id, user, response_mode: 'streaming', auto_generate_name: true }),
    })
  } catch (e) {
    return networkError(e)
  }
  if (!upstream.ok || !upstream.body) return translateDifyError(upstream)

  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}
