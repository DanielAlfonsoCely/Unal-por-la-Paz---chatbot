'use client'

import { memo, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { answerToClipboard, linkCitations, parseAnswer } from '@/lib/parse'
import type { ChatMessage, Source } from '@/lib/types'
import { AVISO_DEMORA_MS } from '@/lib/config'
import { IconAlert, IconBook, IconCheck, IconCopy, IconExternal } from './icons'

/**
 * Revela el texto palabra por palabra aunque llegue en bloques grandes
 * (el Chatflow entrega la respuesta final desde un nodo de código, en un solo bloque).
 */
function useTypewriter(full: string, active: boolean): string {
  const [shown, setShown] = useState(active ? '' : full)
  const shownRef = useRef(shown)
  const fullRef = useRef(full)
  fullRef.current = full

  useEffect(() => {
    if (!active) {
      shownRef.current = full
      setShown(full)
      return
    }
    // Si el texto se reemplazó (message_replace), reiniciar.
    if (!full.startsWith(shownRef.current)) {
      shownRef.current = ''
      setShown('')
    }
  }, [full, active])

  useEffect(() => {
    if (!active) return
    let raf = 0
    let last = 0
    const tick = (t: number) => {
      const target = fullRef.current
      const cur = shownRef.current
      if (cur.length < target.length && t - last > 18) {
        last = t
        const backlog = target.length - cur.length
        const palabras = backlog > 1500 ? 8 : backlog > 600 ? 4 : backlog > 200 ? 2 : 1
        let i = cur.length
        for (let k = 0; k < palabras && i < target.length; k++) {
          const m = /\s*\S+/y
          m.lastIndex = i
          i = m.exec(target) ? m.lastIndex : target.length
        }
        shownRef.current = target.slice(0, i)
        setShown(shownRef.current)
      }
      if (shownRef.current.length < fullRef.current.length) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active, full])

  return active ? shown : full
}

function CopyButton({ text }: { text: string }) {
  const [ok, setOk] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      try {
        document.execCommand('copy')
      } catch {}
      document.body.removeChild(ta)
    }
    setOk(true)
    setTimeout(() => setOk(false), 1800)
  }
  return (
    <button className="msg-action" onClick={copy} aria-label="Copiar respuesta">
      {ok ? <IconCheck width={15} height={15} /> : <IconCopy width={15} height={15} />}
      <span>{ok ? 'Copiado' : 'Copiar'}</span>
    </button>
  )
}

function SourceCards({ sources }: { sources: Source[] }) {
  return (
    <section className="sources" aria-label="Fuentes">
      <h3 className="sources-title">
        <IconBook width={15} height={15} /> Fuentes
      </h3>
      <ol className="sources-grid">
        {sources.map((s) => (
          <li key={s.n} className="source-card">
            <span className="source-n">{s.n}</span>
            <div className="source-body">
              <p className="source-name">{s.title}</p>
              {s.meta && <p className="source-meta">{s.meta}</p>}
              {s.url && (
                <a className="source-link" href={s.url} target="_blank" rel="noopener noreferrer">
                  Ver en el repositorio <IconExternal width={13} height={13} />
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Waiting({ phase }: { phase?: 'buscando' | 'redactando' }) {
  const [largo, setLargo] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setLargo(true), AVISO_DEMORA_MS)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="waiting" role="status" aria-live="polite">
      <span className="dots" aria-hidden>
        <i />
        <i />
        <i />
      </span>
      <span>{phase === 'redactando' ? 'Redactando la respuesta…' : 'Buscando en los documentos…'}</span>
      {largo && <span className="waiting-note">Las respuestas pueden tardar hasta un minuto y medio. Gracias por esperar.</span>}
    </div>
  )
}

function AssistantMessage({ m, onSettled }: { m: ChatMessage; onSettled?: (id: string) => void }) {
  const typing = useTypewriter(m.content, !!m.animate)
  const writing = !!m.streaming || typing.length < m.content.length
  useEffect(() => {
    if (!writing) onSettled?.(m.id)
  }, [writing, m.id, onSettled])
  const full = useMemo(() => parseAnswer(m.content), [m.content])
  const shown = useMemo(() => (writing ? parseAnswer(typing, true) : full), [typing, full, writing])

  const byN = useMemo(() => new Map(full.sources.map((s) => [s.n, s])), [full.sources])

  const components: Components = useMemo(
    () => ({
      a: ({ href, children }) => {
        if (href?.startsWith('#cita-')) {
          const n = Number(href.slice(6))
          const s = byN.get(n)
          const label = s ? `${s.title}${s.meta ? ` (${s.meta})` : ''}` : `Fuente ${n}`
          return s?.url ? (
            <a className="cite" href={s.url} target="_blank" rel="noopener noreferrer" data-tip={label} aria-label={`Fuente ${n}: ${label}`}>
              {n}
            </a>
          ) : (
            <span className="cite" tabIndex={0} data-tip={label} aria-label={`Fuente ${n}: ${label}`}>
              {n}
            </span>
          )
        }
        return (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        )
      },
      table: ({ children }) => (
        <div className="table-wrap">
          <table>{children}</table>
        </div>
      ),
    }),
    [byN],
  )

  const md = useMemo(() => linkCitations(shown.body), [shown.body])
  const empty = !shown.body && m.streaming

  return (
    <div className="msg msg-bot">
      {empty ? (
        <Waiting phase={m.phase} />
      ) : (
        <>
          {shown.body && (
            <div className={`md${writing ? ' md-writing' : ''}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {md}
              </ReactMarkdown>
            </div>
          )}
          {m.stopped && <p className="msg-note">Respuesta detenida.</p>}
          {m.error && (
            <div className="msg-error" role="alert">
              <IconAlert width={17} height={17} />
              <span>{m.error}</span>
            </div>
          )}
          {!writing && full.sources.length > 0 && <SourceCards sources={full.sources} />}
          {!writing && full.body && (
            <div className="msg-actions">
              <CopyButton text={answerToClipboard(full)} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

function MessageView({ m, onSettled }: { m: ChatMessage; onSettled?: (id: string) => void }) {
  if (m.role === 'user') {
    return (
      <div className="msg msg-user">
        <p>{m.content}</p>
      </div>
    )
  }
  return <AssistantMessage m={m} onSettled={onSettled} />
}

export default memo(MessageView)
