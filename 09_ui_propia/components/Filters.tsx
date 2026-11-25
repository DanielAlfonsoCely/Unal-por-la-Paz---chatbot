'use client'

import { useState } from 'react'
import type { InputField } from '@/lib/types'
import { IconFilter } from './icons'

type Props = {
  fields: InputField[]
  values: Record<string, string>
  onChange: (variable: string, value: string) => void
  showNotice: boolean
}

export default function Filters({ fields, values, onChange, showNotice }: Props) {
  const [open, setOpen] = useState(false)
  if (!fields.length) return null
  const activos = fields.filter((f) => (values[f.variable] || '').trim() !== '').length
  return (
    <div className="filters">
      <button className="filters-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <IconFilter width={15} height={15} />
        Filtros{activos ? ` (${activos})` : ''}
        <span className={`chev${open ? ' chev-up' : ''}`} aria-hidden>▾</span>
      </button>
      {open && (
        <div className="filters-row">
          {fields.map((f) => (
            <label key={f.variable} className="filter">
              <span>{f.label}</span>
              {f.type === 'select' ? (
                <select value={values[f.variable] || ''} onChange={(e) => onChange(f.variable, e.target.value)}>
                  <option value="">Todos</option>
                  {(f.options || []).map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type === 'number' ? 'number' : 'text'}
                  inputMode={f.type === 'number' ? 'numeric' : undefined}
                  value={values[f.variable] || ''}
                  maxLength={f.max_length || undefined}
                  placeholder="Opcional"
                  onChange={(e) => onChange(f.variable, e.target.value)}
                />
              )}
            </label>
          ))}
          {activos > 0 && (
            <button className="link-muted" onClick={() => fields.forEach((f) => onChange(f.variable, ''))}>
              Limpiar filtros
            </button>
          )}
        </div>
      )}
      {showNotice && <p className="filters-note" role="status">Los cambios en los filtros aplican desde la siguiente pregunta.</p>}
    </div>
  )
}
