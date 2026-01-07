import { withApiBase } from './base'

export interface ChatSession {
  id: number
  title: string | null
  friend_id: number
  create_time: string
  update_time: string
  deleted: boolean
  // 以下是统计字段，仅在获取列表时提供
  message_count?: number
  last_message_preview?: string
  is_active?: boolean
  memory_generated?: boolean
}

export interface ChatSessionCreate {
  title?: string | null
  friend_id: number
}

export interface ChatSessionUpdate {
  title?: string | null
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  session_id: number
  friend_id?: number | null
  create_time: string
  update_time: string
  deleted: boolean
}

export interface MessageCreate {
  content: string
  enable_thinking?: boolean
}

export async function getSessions(skip: number = 0, limit: number = 100): Promise<ChatSession[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(withApiBase(`/api/chat/sessions?${params}`))
  if (!response.ok) {
    throw new Error('Failed to fetch sessions')
  }
  return response.json()
}

export async function createSession(session: ChatSessionCreate): Promise<ChatSession> {
  const response = await fetch(withApiBase('/api/chat/sessions'), {
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
  const response = await fetch(withApiBase(`/api/chat/sessions/${id}`), {
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
  const response = await fetch(withApiBase(`/api/chat/sessions/${id}`), {
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
  const response = await fetch(withApiBase(`/api/chat/sessions/${sessionId}/messages?${params}`))
  if (!response.ok) {
    throw new Error('Failed to fetch messages')
  }
  return response.json()
}

export async function* sendMessageStream(sessionId: number, message: MessageCreate): AsyncGenerator<{ event: string, data: any }> {
  // SSE Debug timing
  const sseStartTime = performance.now()
  let sseFrameCount = 0
  const formatTime = (t: number) => ((t - sseStartTime) / 1000).toFixed(3)

  console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Starting fetch for session ${sessionId}`)

  const response = await fetch(withApiBase(`/api/chat/sessions/${sessionId}/messages`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message),
  })

  console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Response received at ${formatTime(performance.now())}s, status: ${response.status}`)

  if (!response.ok) {
    throw new Error('Failed to send message')
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''
  let firstChunkLogged = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Stream ended at ${formatTime(performance.now())}s, total frames: ${sseFrameCount}`)
      break
    }

    if (!firstChunkLogged && value) {
      console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] FIRST CHUNK at ${formatTime(performance.now())}s, bytes: ${value.length}`)
      firstChunkLogged = true
    }

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventType = 'message'
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
          sseFrameCount++

          // Log first few frames and every 50th frame
          if (sseFrameCount <= 5 || sseFrameCount % 50 === 0) {
            const preview = data.delta ? data.delta.substring(0, 20) : JSON.stringify(data).substring(0, 50)
            console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Frame #${sseFrameCount} at ${formatTime(performance.now())}s: event=${eventType}, data=${preview}...`)
          }

          yield { event: eventType, data }
        } catch (e) {
          console.error('Failed to parse SSE data JSON:', e)
          // Fallback for non-JSON data if any (though backend sends JSON)
          yield { event: eventType, data: dataString }
        }
      }
    }
  }
}

export async function sendMessage(sessionId: number, message: MessageCreate): Promise<Message> {
  const response = await fetch(withApiBase(`/api/chat/sessions/${sessionId}/messages`), {
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

// --- Friend-centric APIs (WeChat-style) ---

export async function getFriendMessages(friendId: number, skip: number = 0, limit: number = 200): Promise<Message[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(withApiBase(`/api/chat/friends/${friendId}/messages?${params}`))
  if (!response.ok) {
    throw new Error('Failed to fetch friend messages')
  }
  return response.json()
}

export async function getFriendSessions(friendId: number): Promise<ChatSession[]> {
  const response = await fetch(withApiBase(`/api/chat/friends/${friendId}/sessions`))
  if (!response.ok) {
    throw new Error('Failed to fetch friend sessions')
  }
  return response.json()
}

export async function* sendMessageToFriendStream(friendId: number, message: MessageCreate): AsyncGenerator<{ event: string, data: any }> {
  // SSE Debug timing
  const sseStartTime = performance.now()
  let sseFrameCount = 0
  const formatTime = (t: number) => ((t - sseStartTime) / 1000).toFixed(3)

  console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Starting fetch for friend ${friendId}`)

  const response = await fetch(withApiBase(`/api/chat/friends/${friendId}/messages`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message),
  })

  console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Response received at ${formatTime(performance.now())}s, status: ${response.status}`)

  if (!response.ok) {
    throw new Error('Failed to send message to friend')
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''
  let firstChunkLogged = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Stream ended at ${formatTime(performance.now())}s, total frames: ${sseFrameCount}`)
      break
    }

    if (!firstChunkLogged && value) {
      console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] FIRST CHUNK at ${formatTime(performance.now())}s, bytes: ${value.length}`)
      firstChunkLogged = true
    }

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventType = 'message'
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
          sseFrameCount++

          if (sseFrameCount <= 5 || sseFrameCount % 50 === 0) {
            const preview = data.delta ? data.delta.substring(0, 20) : JSON.stringify(data).substring(0, 50)
            console.log(`[SSE-FE ${new Date().toLocaleTimeString()}] Frame #${sseFrameCount} at ${formatTime(performance.now())}s: event=${eventType}, data=${preview}...`)
          }

          yield { event: eventType, data }
        } catch (e) {
          console.error('Failed to parse SSE data JSON:', e)
          yield { event: eventType, data: dataString }
        }
      }
    }
  }
}
export async function clearFriendMessages(friendId: number): Promise<void> {
  const response = await fetch(withApiBase(`/api/chat/friends/${friendId}/messages`), {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to clear friend messages')
  }
}
