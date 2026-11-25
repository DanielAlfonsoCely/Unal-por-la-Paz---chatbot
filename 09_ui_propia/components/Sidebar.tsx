'use client'

import type { Conversation } from '@/lib/types'
import { IconChat, IconClose, IconPlus, IconTrash } from './icons'

type Props = {
  open: boolean
  onClose: () => void
  conversations: Conversation[]
  currentId?: string
  loading: boolean
  error?: string
  busy: boolean
  onNew: () => void
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  confirmId?: string
  setConfirmId: (id?: string) => void
}

function fecha(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

export default function Sidebar(p: Props) {
  return (
    <>
      <div className={`scrim${p.open ? ' scrim-on' : ''}`} onClick={p.onClose} aria-hidden />
      <aside className={`side${p.open ? ' side-open' : ''}`} aria-label="Historial de conversaciones">
        <div className="side-head">
          <button className="btn btn-primary side-new" onClick={p.onNew} disabled={p.busy}>
            <IconPlus width={17} height={17} /> Nueva conversación
          </button>
          <button className="side-close" onClick={p.onClose} aria-label="Cerrar historial">
            <IconClose />
          </button>
        </div>
        <p className="side-label">Conversaciones</p>
        <nav className="side-list">
          {p.loading && p.conversations.length === 0 && <p className="side-empty">Cargando…</p>}
          {!p.loading && p.error && <p className="side-empty">{p.error}</p>}
          {!p.loading && !p.error && p.conversations.length === 0 && (
            <p className="side-empty">Aún no hay conversaciones. Tus preguntas aparecerán aquí.</p>
          )}
          <ul>
            {p.conversations.map((c) => (
              <li key={c.id} className={`side-item${c.id === p.currentId ? ' side-item-on' : ''}`}>
                {p.confirmId === c.id ? (
                  <div className="side-confirm">
                    <span>¿Borrar esta conversación?</span>
                    <div>
                      <button className="link-danger" onClick={() => p.onDelete(c.id)}>Borrar</button>
                      <button className="link-muted" onClick={() => p.setConfirmId(undefined)}>Cancelar</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button className="side-open-btn" onClick={() => p.onOpen(c.id)} disabled={p.busy} title={c.name}>
                      <IconChat width={15} height={15} />
                      <span className="side-name">{c.name}</span>
                      <span className="side-date">{fecha(c.created_at)}</span>
                    </button>
                    <button className="side-del" onClick={() => p.setConfirmId(c.id)} aria-label={`Borrar conversación: ${c.name}`} disabled={p.busy}>
                      <IconTrash width={15} height={15} />
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </>
  )
}
