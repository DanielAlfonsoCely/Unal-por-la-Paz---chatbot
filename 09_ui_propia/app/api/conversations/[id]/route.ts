import { NextRequest } from 'next/server'
import { difyFetch, errorJson, isConfigured, isDemo, networkError, noKeyError, translateDifyError } from '@/lib/server/dify'
import { demoDelete } from '@/lib/server/demo'
import { badUser, cleanUser } from '@/lib/server/user'

export const dynamic = 'force-dynamic'

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const user = cleanUser(req.nextUrl.searchParams.get('user'))
  if (!user) return badUser()
  if (isDemo()) return demoDelete(user, id) ? new Response(null, { status: 204 }) : errorJson(404, 'Conversación no encontrada.')
  if (!isConfigured()) return noKeyError()
  try {
    const res = await difyFetch(`/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      body: JSON.stringify({ user }),
    })
    if (!res.ok) return translateDifyError(res)
    return new Response(null, { status: 204 })
  } catch (e) {
    return networkError(e)
  }
}
