// Identificador anónimo por navegador (uuid en localStorage).
const KEY = 'unal-paz-user-id'
let memoria: string | null = null

function nuevoId(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  } catch {}
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function getUserId(): string {
  if (memoria) return memoria
  let id: string | null = null
  try {
    id = window.localStorage.getItem(KEY)
  } catch {}
  if (!id) {
    id = nuevoId()
    try {
      window.localStorage.setItem(KEY, id)
    } catch {}
  }
  memoria = `web-${id.replace(/^web-/, '')}`
  return memoria
}
