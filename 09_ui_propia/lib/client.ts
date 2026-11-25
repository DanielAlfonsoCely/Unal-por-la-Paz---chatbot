import { INACTIVIDAD_MAX_MS } from './config'
import type { AppParams, Conversation } from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, status = 0, code = 'error') {
    super(message)
    this.status = status
    this.code = code
  }
}

const MSG_RED =
  'No pudimos conectar con el servidor de la interfaz. Revisa tu conexión a internet e intenta de nuevo.'

async function asJson<T>(res: Response): Promise<T> {
  if (res.ok) return res.status === 204 ? (undefined as T) : res.json()
  let msg = 'Ocurrió un error inesperado. Intenta de nuevo.'
  let code = 'error'
  try {
    const j = await res.json()
    msg = j.message || msg
    code = j.code || code
  } catch {}
  throw new ApiError(msg, res.status, code)
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, { cache: 'no-store', ...init })
  } catch {
    throw new ApiError(MSG_RED)
  }
  return asJson<T>(res)
}

export const api = {
  parameters: () => call<AppParams>('/api/parameters'),
  conversations: (user: string) =>
    call<{ data: Conversation[] }>(`/api/conversations?user=${encodeURIComponent(user)}`).then((r) => r.data),
  messages: (user: string, conversationId: string) =>
    call<{ data: { id: string; query: string; answer: string; created_at: number }[] }>(
      `/api/messages?user=${encodeURIComponent(user)}&conversation_id=${encodeURIComponent(conversationId)}`,
    ).then((r) => r.data),
  deleteConversation: (user: string, id: string) =>
    call<void>(`/api/conversations/${encodeURIComponent(id)}?user=${encodeURIComponent(user)}`, { method: 'DELETE' }),
  stop: (user: string, taskId: string) =>
    fetch(`/api/chat/${encodeURIComponent(taskId)}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user }),
    }).catch(() => undefined),
}

export type StreamHandlers = {
  onIds?: (ids: { conversation_id?: string; message_id?: string; task_id?: string }) => void
  onPhase?: (phase: 'buscando' | 'redactando') => void
  onChunk: (text: string) => void
  onReplace?: (text: string) => void
}

/**
 * Envía una pregunta y consume el stream SSE (formato Dify).
 * Resuelve cuando termina; lanza ApiError si hay un error.
 */
export async function streamChat(
  payload: { query: string; conversation_id?: string; inputs: Record<string, unknown>; user: string },
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  // Corte por inactividad (Dify manda "ping" cada ~10 s, así que 200 s sin datos = conexión muerta).
  const watchdog = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  const kick = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => watchdog.abort(), INACTIVIDAD_MAX_MS)
  }
  const onAbort = () => watchdog.abort()
  signal.addEventListener('abort', onAbort)
  kick()

  try {
    let res: Response
    try {
      res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: watchdog.signal,
      })
    } catch (e) {
      if (signal.aborted) return
      if (watchdog.signal.aborted) throw new ApiError('El asistente tardó demasiado en responder. Intenta de nuevo.', 504, 'timeout')
      throw new ApiError(MSG_RED)
    }
    if (!res.ok || !res.body) await asJson(res)

    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let ids = false

    const handle = (raw: string) => {
      const data = raw
        .split('\n')
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).replace(/^ /, ''))
        .join('\n')
      if (!data) return
      let ev: Record<string, any>
      try {
        ev = JSON.parse(data)
      } catch {
        return
      }
      if (!ids && (ev.conversation_id || ev.task_id)) {
        ids = true
        handlers.onIds?.({ conversation_id: ev.conversation_id, message_id: ev.message_id, task_id: ev.task_id })
      }
      switch (ev.event) {
        case 'message':
        case 'agent_message':
          if (typeof ev.answer === 'string' && ev.answer) handlers.onChunk(ev.answer)
          break
        case 'message_replace':
          if (typeof ev.answer === 'string') handlers.onReplace?.(ev.answer)
          break
        case 'node_started': {
          const t = ev.data?.node_type
          if (t === 'llm') handlers.onPhase?.('redactando')
          else if (t === 'knowledge-retrieval') handlers.onPhase?.('buscando')
          break
        }
        case 'error':
          throw new ApiError(
            'El asistente encontró un problema al generar la respuesta. Intenta de nuevo o reformula la pregunta.',
            ev.status || 500,
            ev.code || 'stream_error',
          )
        case 'workflow_finished':
          if (ev.data?.status === 'failed')
            throw new ApiError('El asistente no pudo completar la respuesta. Intenta de nuevo en un momento.', 500, 'workflow_failed')
          break
      }
    }

    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>
      try {
        chunk = await reader.read()
      } catch {
        if (signal.aborted) return
        if (watchdog.signal.aborted) throw new ApiError('El asistente dejó de responder. Intenta de nuevo.', 504, 'timeout')
        throw new ApiError('Se perdió la conexión con el asistente mientras respondía. Intenta de nuevo.')
      }
      if (chunk.done) break
      kick()
      buffer += decoder.decode(chunk.value, { stream: true }).replace(/\r\n/g, '\n')
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const evento = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        handle(evento)
      }
    }
    if (buffer.trim()) handle(buffer)
  } finally {
    if (timer) clearTimeout(timer)
    signal.removeEventListener('abort', onAbort)
  }
}
