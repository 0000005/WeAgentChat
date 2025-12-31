export interface ChatSession {
  id: number
  title: string | null
  persona_id: number
  create_time: string
  update_time: string
  deleted: boolean
}

export interface ChatSessionCreate {
  title?: string | null
  persona_id: number
}

export interface ChatSessionUpdate {
  title?: string | null
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  session_id: number
  persona_id?: number | null
  create_time: string
  update_time: string
  deleted: boolean
}

export interface MessageCreate {
  content: string
}

export async function getSessions(skip: number = 0, limit: number = 100): Promise<ChatSession[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(`/api/chat/sessions?${params}`)
  if (!response.ok) {
    throw new Error('Failed to fetch sessions')
  }
  return response.json()
}

export async function createSession(session: ChatSessionCreate): Promise<ChatSession> {
  const response = await fetch('/api/chat/sessions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(session),
  })
  if (!response.ok) {
    throw new Error('Failed to create session')
  }
  return response.json()
}

export async function updateSession(id: number, session: ChatSessionUpdate): Promise<ChatSession> {
  const response = await fetch(`/api/chat/sessions/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(session),
  })
  if (!response.ok) {
    throw new Error('Failed to update session')
  }
  return response.json()
}

export async function deleteSession(id: number): Promise<void> {
  const response = await fetch(`/api/chat/sessions/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete session')
  }
}

export async function getMessages(sessionId: number, skip: number = 0, limit: number = 100): Promise<Message[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(`/api/chat/sessions/${sessionId}/messages?${params}`)
  if (!response.ok) {
    throw new Error('Failed to fetch messages')
  }
  return response.json()
}

export async function* sendMessageStream(sessionId: number, message: MessageCreate): AsyncGenerator<string> {
  const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message),
  })

  if (!response.ok) {
    throw new Error('Failed to send message')
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventData = ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          eventData += (eventData ? '\n' : '') + data
        }
      }
      if (eventData) {
        yield eventData
      }
    }
  }
}

export async function sendMessage(sessionId: number, message: MessageCreate): Promise<Message> {
  const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message),
  })
  if (!response.ok) {
    throw new Error('Failed to send message')
  }
  return response.json()
}
