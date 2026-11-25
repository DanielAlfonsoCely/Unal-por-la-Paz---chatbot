import 'server-only'

// ─────────────────────────────────────────────────────────────
// MODO DEMO (DEMO_MODE=true): simula la API de Dify sin llamarla.
// Respuestas de ejemplo; el historial vive en memoria del servidor
// (se pierde al reiniciar). Los eventos SSE tienen el mismo formato
// que Dify, así que el navegador usa exactamente el mismo código.
// ─────────────────────────────────────────────────────────────

type DemoMsg = { id: string; conversation_id: string; query: string; answer: string; created_at: number }
type DemoConv = { id: string; name: string; created_at: number; user: string; messages: DemoMsg[] }

const g = globalThis as unknown as { __demoStore?: Map<string, DemoConv> }
const store: Map<string, DemoConv> = g.__demoStore ?? (g.__demoStore = new Map())

const now = () => Math.floor(Date.now() / 1000)
const uid = () => crypto.randomUUID()

export const demoParameters = {
  opening_statement:
    'Hola. Soy el asistente de investigación de la Universidad Nacional. Respondo con base en tesis, artículos y libros del repositorio institucional y cito mis fuentes. (Modo demostración: las respuestas son simuladas.)',
  suggested_questions: [
    '¿Qué es la Reforma Rural Integral y qué dicen las investigaciones sobre su implementación?',
    '¿Cómo se relaciona la concentración de la tierra con el conflicto armado en Colombia?',
    '¿Qué son las Zonas de Reserva Campesina?',
    '¿Qué dificultades ha tenido la restitución de tierras?',
  ],
  suggested_questions_after_answer: { enabled: false },
  user_input_form: [] as unknown[],
}

function demoAnswer(query: string): string {
  const tema = query.replace(/[¿?]/g, '').trim()
  return [
    `*Respuesta de demostración (no proviene de Dify).* Sobre **${tema.length > 90 ? tema.slice(0, 90) + '…' : tema}**, los documentos del repositorio permiten destacar varios puntos:`,
    '',
    '1. **Contexto.** Las investigaciones coinciden en que el acceso desigual a la tierra es un factor estructural del conflicto armado y de su persistencia en las regiones [1].',
    '2. **Hallazgos principales.** Los estudios de caso muestran que los avances dependen de la coordinación entre instituciones locales y nacionales, y de la participación de las comunidades campesinas [2].',
    '3. **Diferencias entre autores.** Mientras un enfoque enfatiza la formalización de la propiedad [1], otro prioriza el fortalecimiento de las organizaciones sociales en el territorio [2].',
    '',
    'En conjunto, los documentos sugieren que la implementación ha sido parcial y desigual entre regiones [1, 2]. Puedes ver más detalles en el [repositorio institucional](https://repositorio.unal.edu.co/).',
    '',
    '---',
    '**Fuentes**',
    '',
    '**[1]** Documento de ejemplo: tierra, conflicto y desarrollo rural en Colombia (Autor de ejemplo, 2018) — [Ver en el Repositorio UNAL](https://repositorio.unal.edu.co/)',
    '',
    '**[2]** Documento de ejemplo: organizaciones campesinas y construcción de paz territorial (Autora de ejemplo, 2020) — [Ver en el Repositorio UNAL](https://repositorio.unal.edu.co/)',
    '',
    '<!--sugerencias:["¿Qué diferencias hay entre los enfoques de formalización y de organización social?","Explícame el papel de las comunidades campesinas en la implementación","¿Por qué la implementación ha sido desigual entre regiones?"]-->',
  ].join('\n')
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function demoChatStream(opts: {
  query: string
  user: string
  conversation_id?: string
  signal: AbortSignal
}): Response {
  const { query, user, signal } = opts
  let conv = opts.conversation_id ? store.get(opts.conversation_id) : undefined
  if (opts.conversation_id && (!conv || conv.user !== user)) {
    return Response.json({ code: 'not_found', message: 'Esa conversación ya no existe. Empieza una nueva.' }, { status: 404 })
  }
  if (!conv) {
    conv = { id: uid(), name: query.slice(0, 60), created_at: now(), user, messages: [] }
    store.set(conv.id, conv)
  }
  const c = conv
  const message_id = uid()
  const task_id = uid()
  const answer = demoAnswer(query)
  const enc = new TextEncoder()

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (obj: Record<string, unknown>) =>
        controller.enqueue(enc.encode(`data: ${JSON.stringify({ conversation_id: c.id, message_id, task_id, created_at: now(), ...obj })}\n\n`))
      let sent = ''
      try {
        send({ event: 'workflow_started', workflow_run_id: uid(), data: {} })
        send({ event: 'node_started', data: { node_type: 'knowledge-retrieval', title: 'Recuperar' } })
        await sleep(1800)
        send({ event: 'node_started', data: { node_type: 'llm', title: 'Redactar respuesta' } })
        await sleep(700)
        // palabra por palabra
        const piezas = answer.match(/\S+\s*|\s+/g) || []
        for (const p of piezas) {
          if (signal.aborted) break
          sent += p
          send({ event: 'message', answer: p })
          await sleep(p.includes('\n') ? 40 : 22)
        }
        if (!signal.aborted) {
          send({ event: 'message_end', metadata: {} })
          send({ event: 'workflow_finished', data: { status: 'succeeded' } })
        }
      } catch {
        // cliente desconectado
      } finally {
        c.messages.push({ id: message_id, conversation_id: c.id, query, answer: sent, created_at: now() })
        try {
          controller.close()
        } catch {}
      }
    },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive' },
  })
}

export function demoConversations(user: string) {
  const data = [...store.values()]
    .filter((c) => c.user === user)
    .sort((a, b) => b.created_at - a.created_at)
    .map(({ id, name, created_at }) => ({ id, name, created_at }))
  return { data, has_more: false, limit: 100 }
}

export function demoMessages(user: string, conversation_id: string) {
  const c = store.get(conversation_id)
  if (!c || c.user !== user) return null
  return { data: c.messages, has_more: false, limit: 100 }
}

export function demoDelete(user: string, conversation_id: string): boolean {
  const c = store.get(conversation_id)
  if (!c || c.user !== user) return false
  store.delete(conversation_id)
  return true
}
