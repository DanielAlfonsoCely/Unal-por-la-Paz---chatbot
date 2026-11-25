'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'
import Filters from './Filters'
import Composer from './Composer'
import MessageView from './Message'
import { IconAlert } from './icons'
import { api, ApiError, streamChat } from '@/lib/client'
import { getUserId } from '@/lib/user'
import { parseAnswer } from '@/lib/parse'
import { AVISO, BIENVENIDA_POR_DEFECTO, MODOS, MOSTRAR_SELECTOR_MODO, VARIABLE_MODO } from '@/lib/config'
import type { AppParams, ChatMessage, Conversation } from '@/lib/types'

const tmpId = () => `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

export default function ChatApp() {
  const [user, setUser] = useState('')
  const [params, setParams] = useState<AppParams | null>(null)
  const [paramsError, setParamsError] = useState('')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [convLoading, setConvLoading] = useState(true)
  const [convError, setConvError] = useState('')
  const [currentId, setCurrentId] = useState<string | undefined>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loadingConv, setLoadingConv] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [input, setInput] = useState('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [filtersNotice, setFiltersNotice] = useState(false)
  const [modo, setModo] = useState<string>(MODOS[0].valor)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [confirmId, setConfirmId] = useState<string | undefined>()
  const [settled, setSettled] = useState<Set<string>>(new Set())
  const [banner, setBanner] = useState('')

  const abortRef = useRef<AbortController | null>(null)
  const taskRef = useRef<string | undefined>(undefined)
  const convRef = useRef<string | undefined>(undefined)
  const scrollRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)

  convRef.current = currentId

  // ── carga inicial ──────────────────────────────────────────
  const loadParams = useCallback(async () => {
    setParamsError('')
    try {
      const p = await api.parameters()
      setParams(p)
      const init: Record<string, string> = {}
      p.user_input_form.forEach((f) => {
        if (f.default) init[f.variable] = String(f.default)
      })
      setFilters((prev) => ({ ...init, ...prev }))
    } catch (e) {
      setParamsError((e as Error).message)
    }
  }, [])

  const loadConversations = useCallback(async (u: string) => {
    try {
      const list = await api.conversations(u)
      setConversations(list)
      setConvError('')
    } catch {
      setConvError('No se pudo cargar el historial.')
    } finally {
      setConvLoading(false)
    }
  }, [])

  useEffect(() => {
    const u = getUserId()
    setUser(u)
    loadParams()
    loadConversations(u)
  }, [loadParams, loadConversations])

  // ── autoscroll ─────────────────────────────────────────────
  useEffect(() => {
    const el = scrollRef.current
    const inner = innerRef.current
    if (!el || !inner) return
    const onScroll = () => {
      stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    const ro = new ResizeObserver(() => {
      if (stickRef.current) el.scrollTop = el.scrollHeight
    })
    ro.observe(inner)
    return () => {
      el.removeEventListener('scroll', onScroll)
      ro.disconnect()
    }
  }, [])

  const onSettled = useCallback((id: string) => {
    setSettled((s) => (s.has(id) ? s : new Set(s).add(id)))
  }, [])

  const patchMsg = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)))

  // ── enviar ─────────────────────────────────────────────────
  const send = useCallback(
    async (text: string) => {
      const query = text.trim()
      if (!query || streaming || !user) return
      setBanner('')
      setInput('')
      setFiltersNotice(false)
      setSidebarOpen(false)
      stickRef.current = true

      const botId = tmpId()
      setMessages((ms) => [
        ...ms,
        { id: tmpId(), role: 'user', content: query },
        { id: botId, role: 'assistant', content: '', streaming: true, animate: true, phase: 'buscando' },
      ])
      setStreaming(true)
      const ac = new AbortController()
      abortRef.current = ac
      taskRef.current = undefined

      const inputs: Record<string, unknown> = { ...filters }
      if (MOSTRAR_SELECTOR_MODO) inputs[VARIABLE_MODO] = modo
      const wasNew = !convRef.current

      let error: string | undefined
      try {
        await streamChat(
          { query, conversation_id: convRef.current, inputs, user },
          {
            onIds: ({ conversation_id, task_id }) => {
              if (task_id) taskRef.current = task_id
              if (conversation_id && !convRef.current) {
                convRef.current = conversation_id
                setCurrentId(conversation_id)
              }
            },
            onPhase: (phase) => patchMsg(botId, (m) => ({ ...m, phase })),
            onChunk: (t) => patchMsg(botId, (m) => ({ ...m, content: m.content + t })),
            onReplace: (t) => patchMsg(botId, (m) => ({ ...m, content: t })),
          },
          ac.signal,
        )
      } catch (e) {
        const err = e as ApiError
        error = err.message || 'Ocurrió un error inesperado. Intenta de nuevo.'
        if (err.status === 404 && convRef.current) {
          convRef.current = undefined
          setCurrentId(undefined)
        }
      } finally {
        const stopped = ac.signal.aborted
        patchMsg(botId, (m) => ({ ...m, streaming: false, error, stopped: stopped && !error }))
        setStreaming(false)
        abortRef.current = null
        // Refresca el historial (Dify genera el nombre de la conversación unos segundos después).
        loadConversations(user)
        if (wasNew) setTimeout(() => loadConversations(user), 5000)
      }
    },
    [streaming, user, filters, modo, loadConversations],
  )

  const stop = useCallback(() => {
    if (taskRef.current && user) api.stop(user, taskRef.current)
    abortRef.current?.abort()
  }, [user])

  // ── historial ──────────────────────────────────────────────
  const newConversation = () => {
    if (streaming) return
    setCurrentId(undefined)
    setMessages([])
    setInput('')
    setFiltersNotice(false)
    setSidebarOpen(false)
    setBanner('')
  }

  const openConversation = async (id: string) => {
    if (streaming || id === currentId) {
      setSidebarOpen(false)
      return
    }
    setLoadingConv(true)
    setBanner('')
    setSidebarOpen(false)
    try {
      const data = await api.messages(user, id)
      const ms: ChatMessage[] = []
      data.forEach((d) => {
        ms.push({ id: `${d.id}-q`, role: 'user', content: d.query })
        ms.push({ id: d.id, role: 'assistant', content: d.answer || '' })
      })
      stickRef.current = true
      setCurrentId(id)
      setMessages(ms)
      setFiltersNotice(false)
    } catch (e) {
      setBanner((e as Error).message || 'No se pudo abrir la conversación.')
      if ((e as ApiError).status === 404) loadConversations(user)
    } finally {
      setLoadingConv(false)
    }
  }

  const deleteConversation = async (id: string) => {
    setConfirmId(undefined)
    const prev = conversations
    setConversations((cs) => cs.filter((c) => c.id !== id))
    if (id === currentId) newConversation()
    try {
      await api.deleteConversation(user, id)
    } catch (e) {
      setConversations(prev)
      setBanner((e as Error).message || 'No se pudo borrar la conversación.')
    }
  }

  // ── derivados ──────────────────────────────────────────────
  const fields = params?.user_input_form ?? []
  const notConfigured = params && !params.configured
  const last = messages[messages.length - 1]
  const followUps = useMemo(() => {
    if (!last || last.role !== 'assistant' || last.streaming || last.error || !settled.has(last.id)) return []
    return parseAnswer(last.content).suggestions
  }, [last, settled])
  const chips = messages.length === 0 ? params?.suggested_questions ?? [] : followUps
  const chipsLabel = messages.length === 0 ? 'Preguntas sugeridas' : 'Para seguir explorando'
  const welcome = params?.opening_statement || BIENVENIDA_POR_DEFECTO

  return (
    <div className="app">
      <Header onMenu={() => setSidebarOpen(true)} demo={!!params?.demo} />
      <div className="body">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          conversations={conversations}
          currentId={currentId}
          loading={convLoading}
          error={convError}
          busy={streaming}
          onNew={newConversation}
          onOpen={openConversation}
          onDelete={deleteConversation}
          confirmId={confirmId}
          setConfirmId={setConfirmId}
        />
        <main className="main">
          {(fields.length > 0 || MOSTRAR_SELECTOR_MODO) && (
            <div className="toolbar">
              {MOSTRAR_SELECTOR_MODO && (
                <div className="modes" role="radiogroup" aria-label="Modo">
                  {MODOS.map((m) => (
                    <button
                      key={m.valor}
                      role="radio"
                      aria-checked={modo === m.valor}
                      className={`mode${modo === m.valor ? ' mode-on' : ''}`}
                      onClick={() => setModo(m.valor)}
                      disabled={streaming}
                    >
                      {m.etiqueta}
                    </button>
                  ))}
                </div>
              )}
              <Filters
                fields={fields}
                values={filters}
                showNotice={filtersNotice}
                onChange={(k, v) => {
                  setFilters((f) => ({ ...f, [k]: v }))
                  if (messages.length > 0) setFiltersNotice(true)
                }}
              />
            </div>
          )}

          <div className="scroll" ref={scrollRef}>
            <div className="thread" ref={innerRef}>
              {notConfigured && (
                <div className="banner banner-warn" role="status">
                  <IconAlert width={18} height={18} />
                  <span>
                    El asistente todavía no está conectado a Dify. Falta configurar <code>DIFY_APP_KEY</code> en{' '}
                    <code>.env.local</code> (o activar <code>DEMO_MODE=true</code> para probar la interfaz).
                  </span>
                </div>
              )}
              {paramsError && (
                <div className="banner banner-error" role="alert">
                  <IconAlert width={18} height={18} />
                  <span>{paramsError}</span>
                  <button className="link-muted" onClick={loadParams}>Reintentar</button>
                </div>
              )}

              {messages.length === 0 && !loadingConv && (
                <div className="welcome">
                  <p className="welcome-kicker">Asistente de investigación</p>
                  <p className="welcome-text">{params ? welcome : ' '}</p>
                  <p className="welcome-hint">Escribe una pregunta o elige una de las sugeridas abajo.</p>
                </div>
              )}
              {loadingConv && <p className="loading-conv">Cargando conversación…</p>}

              {messages.map((m) => (
                <MessageView key={m.id} m={m} onSettled={onSettled} />
              ))}

              {banner && (
                <div className="banner banner-error" role="alert">
                  <IconAlert width={18} height={18} />
                  <span>{banner}</span>
                  <button className="link-muted" onClick={() => setBanner('')}>Cerrar</button>
                </div>
              )}
            </div>
          </div>

          <div className="bottom">
            <Composer
              value={input}
              onChange={setInput}
              onSend={send}
              onStop={stop}
              streaming={streaming}
              disabled={!user || !!notConfigured || loadingConv}
              chips={chips}
              chipsLabel={chipsLabel}
            />
            <p className="disclaimer">{AVISO}</p>
          </div>
        </main>
      </div>
    </div>
  )
}
