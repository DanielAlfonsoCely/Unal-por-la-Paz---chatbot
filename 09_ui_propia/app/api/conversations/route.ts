import { NextRequest } from 'next/server'
import { difyFetch, isConfigured, isDemo, networkError, translateDifyError } from '@/lib/server/dify'
import { demoConversations } from '@/lib/server/demo'
import { badUser, cleanUser } from '@/lib/server/user'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const user = cleanUser(req.nextUrl.searchParams.get('user'))
  if (!user) return badUser()
  if (isDemo()) return Response.json(demoConversations(user))
  if (!isConfigured()) return Response.json({ data: [], has_more: false })
  try {
    const res = await difyFetch(`/conversations?user=${encodeURIComponent(user)}&limit=50&sort_by=-updated_at`)
    if (!res.ok) return translateDifyError(res)
    const json = await res.json()
    const data = (json.data || []).map((c: { id: string; name?: string; created_at: number }) => ({
      id: c.id,
      name: c.name || 'Conversación',
      created_at: c.created_at,
    }))
    return Response.json({ data, has_more: !!json.has_more })
  } catch (e) {
    return networkError(e)
  }
}
