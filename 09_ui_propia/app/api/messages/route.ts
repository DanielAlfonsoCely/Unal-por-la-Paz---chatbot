import { NextRequest } from 'next/server'
import { difyFetch, errorJson, isConfigured, isDemo, networkError, noKeyError, translateDifyError } from '@/lib/server/dify'
import { demoMessages } from '@/lib/server/demo'
import { badUser, cleanUser } from '@/lib/server/user'

export const dynamic = 'force-dynamic'

type Msg = { id: string; query: string; answer: string; created_at: number }

export async function GET(req: NextRequest) {
  const user = cleanUser(req.nextUrl.searchParams.get('user'))
  const conversation_id = req.nextUrl.searchParams.get('conversation_id') || ''
  if (!user) return badUser()
  if (!conversation_id) return errorJson(400, 'Falta la conversación.')
  if (isDemo()) {
    const r = demoMessages(user, conversation_id)
    return r ? Response.json(r) : errorJson(404, 'Esa conversación ya no existe.')
  }
  if (!isConfigured()) return noKeyError()
  try {
    const res = await difyFetch(
      `/messages?user=${encodeURIComponent(user)}&conversation_id=${encodeURIComponent(conversation_id)}&limit=100`,
    )
    if (!res.ok) return translateDifyError(res)
    const json = await res.json()
    const data = ((json.data || []) as Msg[])
      .map(({ id, query, answer, created_at }) => ({ id, query, answer, created_at }))
      .sort((a, b) => a.created_at - b.created_at)
    return Response.json({ data })
  } catch (e) {
    return networkError(e)
  }
}
