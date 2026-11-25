export type InputField = {
  type: 'text-input' | 'paragraph' | 'select' | 'number' | string
  variable: string
  label: string
  required: boolean
  options?: string[]
  max_length?: number
  default?: string
}

export type AppParams = {
  opening_statement: string
  suggested_questions: string[]
  user_input_form: InputField[]
  demo: boolean
  configured: boolean
}

export type Conversation = { id: string; name: string; created_at: number }

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  animate?: boolean
  error?: string
  stopped?: boolean
  phase?: 'buscando' | 'redactando'
}

export type Source = { n: number; title: string; meta: string; url: string }
