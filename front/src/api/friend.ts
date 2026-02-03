import { withApiBase } from './base'

export interface Friend {
  id: number
  name: string
  description?: string | null
  system_prompt?: string | null
  avatar?: string | null
  is_preset?: boolean
  create_time: string
  update_time: string
  pinned_at?: string | null
  deleted: boolean
  script_expression: boolean
  temperature: number
  top_p: number
  last_message?: string | null
  last_message_role?: string | null
  last_message_time?: string | null
}

export interface FriendCreate {
  name: string
  description?: string | null
  system_prompt?: string | null
  avatar?: string | null
  is_preset?: boolean
  script_expression?: boolean
  temperature?: number
  top_p?: number
}

export interface FriendUpdate {
  name?: string | null
  description?: string | null
  system_prompt?: string | null
  avatar?: string | null
  is_preset?: boolean | null
  pinned_at?: string | null
  script_expression?: boolean | null
  temperature?: number | null
  top_p?: number | null
}

export interface FriendRecommendationItem {
  name: string
  reason: string
  description_hint: string
}

export interface FriendRecommendationResponse {
  recommendations: FriendRecommendationItem[]
}

export async function getFriends(skip: number = 0, limit: number = 100): Promise<Friend[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(withApiBase(`/api/friends/?${params}`))
  if (!response.ok) {
    throw new Error('Failed to fetch friends')
  }
  return response.json()
}

export async function createFriend(friend: FriendCreate): Promise<Friend> {
  const response = await fetch(withApiBase('/api/friends/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(friend),
  })
  if (!response.ok) {
    throw new Error('Failed to create friend')
  }
  return response.json()
}

export async function getFriend(id: number): Promise<Friend> {
  const response = await fetch(withApiBase(`/api/friends/${id}`))
  if (!response.ok) {
    throw new Error('Failed to fetch friend')
  }
  return response.json()
}

export async function updateFriend(id: number, friend: FriendUpdate): Promise<Friend> {
  const response = await fetch(withApiBase(`/api/friends/${id}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(friend),
  })
  if (!response.ok) {
    throw new Error('Failed to update friend')
  }
  return response.json()
}

export async function deleteFriend(id: number): Promise<Friend> {
  const response = await fetch(withApiBase(`/api/friends/${id}`), {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete friend')
  }
  return response.json()
}

export async function recommendFriends(topic: string, excludeNames: string[] = []): Promise<FriendRecommendationItem[]> {
  const response = await fetch(withApiBase('/api/friends/recommend'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic,
      exclude_names: excludeNames
    }),
  })
  if (!response.ok) {
    throw new Error('Failed to get friend recommendations')
  }
  const data: FriendRecommendationResponse = await response.json()
  return data.recommendations
}

export async function* recommendFriendsStream(
  topic: string,
  excludeNames: string[] = [],
  options: { signal?: AbortSignal } = {}
): AsyncGenerator<{ event: string, data: any }> {
  const response = await fetch(withApiBase('/api/friends/recommend/stream'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic,
      exclude_names: excludeNames
    }),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error('Failed to get friend recommendations stream')
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
          let data = JSON.parse(dataString)
          if (eventType === 'result' && Array.isArray(data)) {
            data = { recommendations: data }
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
