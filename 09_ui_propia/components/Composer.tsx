'use client'

import { useEffect, useRef } from 'react'
import { IconSend, IconStop } from './icons'

type Props = {
  value: string
  onChange: (v: string) => void
  onSend: (text: string) => void
  onStop: () => void
  streaming: boolean
  disabled: boolean
  chips: string[]
  chipsLabel: string
}

export default function Composer({ value, onChange, onSend, onStop, streaming, disabled, chips, chipsLabel }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const ta = ref.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px'
  }, [value])

  const submit = () => {
    const t = value.trim()
    if (!t || streaming || disabled) return
    onSend(t)
  }

  return (
    <div className="composer">
      {chips.length > 0 && !streaming && (
        <div className="chips" aria-label={chipsLabel}>
          <span className="chips-label">{chipsLabel}</span>
          <div className="chips-list">
            {chips.map((c) => (
              <button key={c} className="chip" onClick={() => onSend(c)} disabled={disabled}>
                {c}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="input-box">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          placeholder="Escribe tu pregunta…"
          aria-label="Escribe tu pregunta"
          maxLength={4000}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            }
          }}
        />
        {streaming ? (
          <button className="btn-round btn-stop" onClick={onStop} aria-label="Detener respuesta" title="Detener">
            <IconStop width={16} height={16} />
          </button>
        ) : (
          <button className="btn-round btn-send" onClick={submit} disabled={!value.trim() || disabled} aria-label="Enviar pregunta" title="Enviar">
            <IconSend width={18} height={18} />
          </button>
        )}
      </div>
    </div>
  )
}
