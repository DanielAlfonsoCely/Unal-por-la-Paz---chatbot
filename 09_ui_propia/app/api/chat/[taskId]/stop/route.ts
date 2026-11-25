import { NextRequest } from 'next/server'
import { difyFetch, isConfigured, isDemo } from '@/lib/server/dify'
import { badUser, cleanUser } from '@/lib/server/user'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest, { params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params
  const body = await req.json().catch(() => ({}))
  const user = cleanUser(body.user)
  if (!user) return badUser()
  // En demo basta con que el navegador corte la conexión.
  if (isDemo() || !isConfigured()) return Response.json({ result: 'success' })
  try {
    const res = await difyFetch(`/chat-messages/${encodeURIComponent(taskId)}/stop`, {
      method: 'POST',
      body: JSON.stringify({ user }),
    })
    return Response.json({ result: res.ok ? 'success' : 'error' }, { status: res.ok ? 200 : 502 })
  } catch {
    return Response.json({ result: 'error' }, { status: 502 })
  }
}
