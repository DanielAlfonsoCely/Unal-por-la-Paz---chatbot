import type { Source } from './types'

// El Chatflow termina la respuesta así:
//   texto con citas [1] [2]...
//   \n\n---\n**Fuentes**\n\n**[1]** Título (Autor, 2018) — [Ver en el Repositorio UNAL](https://...)
//   \n\n<!--sugerencias:["...","...","..."]-->

const RE_SUGERENCIAS = /<!--\s*sugerencias\s*:\s*([\s\S]*?)-->/i
const RE_FUENTES = /(?:^|\n)[ \t]*-{3,}[ \t]*\n+[ \t]*\*\*\s*Fuentes\s*\*\*[ \t]*:?[ \t]*(?:\n|$)/i

export type ParsedAnswer = {
  body: string
  sources: Source[]
  suggestions: string[]
}

export function parseAnswer(raw: string, streaming = false): ParsedAnswer {
  let text = raw || ''
  // Quita razonamiento interno si algún modelo lo deja pasar.
  text = text.replace(/<think>[\s\S]*?<\/think>/g, '')

  // 1) Sugerencias (comentario HTML)
  let suggestions: string[] = []
  const ms = text.match(RE_SUGERENCIAS)
  if (ms) {
    try {
      const arr = JSON.parse(ms[1].trim())
      if (Array.isArray(arr)) suggestions = arr.map((x) => String(x).trim()).filter(Boolean).slice(0, 3)
    } catch {}
    text = text.slice(0, ms.index) + text.slice((ms.index ?? 0) + ms[0].length)
  }
  // Comentario a medio llegar (durante el streaming): no mostrarlo.
  const abierto = text.lastIndexOf('<!--')
  if (abierto !== -1 && text.indexOf('-->', abierto) === -1) text = text.slice(0, abierto)
  if (streaming) text = text.replace(/<!?-?-?$/, '')

  // 2) Bloque de fuentes
  let sources: Source[] = []
  const mf = RE_FUENTES.exec(text)
  if (mf) {
    const bloque = text.slice(mf.index + mf[0].length)
    text = text.slice(0, mf.index)
    sources = parseSources(bloque)
  } else if (streaming) {
    // Inicio parcial del bloque ("\n---", "\n---\n**Fue") mientras se escribe: ocultarlo.
    text = text.replace(/\n[ \t]*-{1,3}[ \t]*(\n+[ \t]*\*{0,2}[A-Za-zÁ-ú]*\**)?[ \t]*$/, '')
  }

  return { body: text.trim(), sources, suggestions }
}

function parseSources(bloque: string): Source[] {
  const out: Source[] = []
  const lineas = bloque
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean)

  for (const linea of lineas) {
    let l = linea.replace(/^[-*•]\s+/, '')
    // número: **[1]**, [1], 1.
    const mn = l.match(/^\*{0,2}\[(\d+)\]\*{0,2}\s*|^(\d+)[.)]\s+/)
    if (!mn) continue
    const n = Number(mn[1] ?? mn[2])
    l = l.slice(mn[0].length)

    // enlace al final: — [texto](url)  o una URL suelta
    let url = ''
    const ml = l.match(/\s*[—–-]?\s*\[[^\]]*\]\((https?:[^)\s]+)\)\s*$/)
    if (ml) {
      url = ml[1]
      l = l.slice(0, ml.index).trim()
    } else {
      const mu = l.match(/\s*[—–-]?\s*<?(https?:\/\/\S+?)>?\s*$/)
      if (mu) {
        url = mu[1]
        l = l.slice(0, mu.index).trim()
      }
    }

    // (Autor, Año) al final del título → último paréntesis balanceado
    let meta = ''
    if (l.endsWith(')')) {
      let depth = 0
      for (let i = l.length - 1; i >= 0; i--) {
        if (l[i] === ')') depth++
        else if (l[i] === '(') {
          depth--
          if (depth === 0) {
            meta = l.slice(i + 1, -1).trim()
            l = l.slice(0, i).trim()
            break
          }
        }
      }
    }
    const title = l.replace(/^\*+|\*+$/g, '').trim() || 'Documento sin título'
    out.push({ n, title, meta, url })
  }
  return out
}

/**
 * Convierte [1], [1, 2] o [1][2] en enlaces "#cita-n" que el render de Markdown
 * pinta como etiquetas con tooltip. No toca enlaces Markdown reales ([texto](url)).
 */
export function linkCitations(md: string): string {
  return md.replace(/\[(\d+(?:\s*[,;]\s*\d+)*)\](?!\()/g, (_m, grupo: string) =>
    grupo
      .split(/[,;]/)
      .map((x) => x.trim())
      .filter(Boolean)
      .map((k) => `[${k}](#cita-${k})`)
      .join(''),
  )
}

/** Texto plano para el botón "copiar". */
export function answerToClipboard(p: ParsedAnswer): string {
  let t = p.body
  if (p.sources.length) {
    t +=
      '\n\nFuentes:\n' +
      p.sources
        .map((s) => `[${s.n}] ${s.title}${s.meta ? ` (${s.meta})` : ''}${s.url ? ` — ${s.url}` : ''}`)
        .join('\n')
  }
  return t
}
