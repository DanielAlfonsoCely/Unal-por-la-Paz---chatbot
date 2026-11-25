'use client'

import { useState } from 'react'
import { LOGO_SRC, SUBTITULO, TITULO } from '@/lib/config'
import { IconMenu } from './icons'

export default function Header({ onMenu, demo }: { onMenu: () => void; demo: boolean }) {
  const [logoOk, setLogoOk] = useState(true)
  return (
    <header className="hdr">
      <div className="hdr-top">
        <button className="hdr-menu" onClick={onMenu} aria-label="Abrir historial de conversaciones">
          <IconMenu width={18} height={18} />
          <span>Historial</span>
        </button>
        {demo && <span className="demo-badge" title="DEMO_MODE=true: las respuestas son simuladas y no se consulta Dify">Modo demostración</span>}
      </div>
      <div className="hdr-band">
        <div className="hdr-title">
          <h1>{TITULO}</h1>
          <p>{SUBTITULO}</p>
        </div>
      </div>
      <div className="hdr-badge" aria-hidden={!logoOk}>
        {logoOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={LOGO_SRC} alt="Universidad Nacional de Colombia" onError={() => setLogoOk(false)} />
        ) : (
          <span className="hdr-badge-fallback">UNAL</span>
        )}
      </div>
    </header>
  )
}
