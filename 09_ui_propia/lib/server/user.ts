import 'server-only'

/** Valida el identificador anónimo que manda el navegador. */
export function cleanUser(v: unknown): string | null {
  if (typeof v !== 'string') return null
  const s = v.trim()
  return /^[A-Za-z0-9_-]{6,80}$/.test(s) ? s : null
}

export const badUser = () => Response.json({ code: 'bad_user', message: 'Identificador de usuario inválido.' }, { status: 400 })
