import { difyFetch, isConfigured, isDemo, networkError, translateDifyError } from '@/lib/server/dify'
import { demoParameters } from '@/lib/server/demo'

export const dynamic = 'force-dynamic'

type RawField = Record<string, { label?: string; variable: string; required?: boolean; options?: string[]; max_length?: number; default?: string }>

function normalize(raw: { opening_statement?: string; suggested_questions?: string[]; user_input_form?: RawField[] }, demo: boolean) {
  const form = (raw.user_input_form || [])
    .map((item) => {
      const type = Object.keys(item)[0]
      const f = item[type]
      if (!f || !f.variable) return null
      return {
        type,
        variable: f.variable,
        label: f.label || f.variable,
        required: !!f.required,
        options: f.options,
        max_length: f.max_length,
        default: f.default,
      }
    })
    .filter(Boolean)
  return {
    opening_statement: raw.opening_statement || '',
    suggested_questions: (raw.suggested_questions || []).filter(Boolean),
    user_input_form: form,
    demo,
    configured: demo || isConfigured(),
  }
}

export async function GET() {
  if (isDemo()) return Response.json(normalize(demoParameters as never, true))
  if (!isConfigured()) {
    return Response.json({ ...normalize({}, false), configured: false })
  }
  try {
    const res = await difyFetch('/parameters')
    if (!res.ok) return translateDifyError(res)
    return Response.json(normalize(await res.json(), false))
  } catch (e) {
    return networkError(e)
  }
}
