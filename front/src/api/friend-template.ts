import { Friend } from './friend'
import { withApiBase } from './base'

export interface FriendTemplate {
  id: number
  name: string
  avatar?: string | null
  description: string
  system_prompt: string
  initial_message?: string | null
  tags?: string[] | null
  created_at: string
  updated_at: string
}

export interface FriendTemplateQuery {
  page?: number
  size?: number
  tag?: string
  q?: string
}

export async function getFriendTemplates(query: FriendTemplateQuery = {}): Promise<FriendTemplate[]> {
  const params = new URLSearchParams()
  if (query.page) params.set('page', query.page.toString())
  if (query.size) params.set('size', query.size.toString())
  if (query.tag) params.set('tag', query.tag)
  if (query.q) params.set('q', query.q)

  const url = withApiBase(`/api/friend-templates/${params.toString() ? `?${params}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Failed to fetch friend templates')
  }
  return response.json()
}

export async function cloneFriendTemplate(id: number): Promise<Friend> {
  const url = withApiBase(`/api/friend-templates/${id}/clone`)
  const response = await fetch(url, {
    method: 'POST',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to clone friend' }))
    throw new Error(error.detail || 'Failed to clone friend')
  }
  return response.json()
}

export interface PersonaGenerateRequest {
  description: string
  name?: string
}

export interface PersonaGenerateResponse {
  name: string
  description: string
  system_prompt: string
  initial_message: string
}

export interface FriendTemplateCreateFriend {
  name: string
  avatar?: string | null
  description: string
  system_prompt: string
  initial_message?: string | null
}

/**
 * 根据描述自动生成 Persona 设定
 */
export async function getFriendTemplateTags(): Promise<string[]> {
  const url = withApiBase('/api/friend-templates/tags')
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Failed to fetch friend template tags')
  }
  return response.json()
}


export async function* generatePersonaStream(
  payload: PersonaGenerateRequest,
  options: { signal?: AbortSignal } = {}
): AsyncGenerator<{ event: string, data: any }> {
  const response = await fetch(withApiBase('/api/friend-templates/generate/stream'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error('Failed to generate persona stream')
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventType = 'delta'
      let dataString = ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          dataString += (dataString ? '\n' : '') + line.slice(6)
        }
      }

      if (dataString) {
        try {
          const data = JSON.parse(dataString)
          yield { event: eventType, data }
        } catch (e) {
          console.error('Failed to parse SSE data JSON:', e)
          yield { event: eventType, data: dataString }
        }
      }
    }
  }
}

/**
 * 根据生成的设定直接创建好友
 */
export async function createFriendFromPayload(payload: FriendTemplateCreateFriend): Promise<Friend> {
  const url = withApiBase('/api/friend-templates/create-friend')
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create friend' }))
    throw new Error(error.detail || 'Failed to create friend')
  }
  return response.json()
}
