export interface Friend {
  id: number
  name: string
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean
  create_time: string
  update_time: string
  deleted: boolean
}

export interface FriendCreate {
  name: string
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean
}

export interface FriendUpdate {
  name?: string | null
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean | null
}

export async function getFriends(skip: number = 0, limit: number = 100): Promise<Friend[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(`/api/friends/?${params}`)
  if (!response.ok) {
    throw new Error('Failed to fetch friends')
  }
  return response.json()
}

export async function createFriend(friend: FriendCreate): Promise<Friend> {
  const response = await fetch('/api/friends/', {
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
  const response = await fetch(`/api/friends/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch friend')
  }
  return response.json()
}

export async function updateFriend(id: number, friend: FriendUpdate): Promise<Friend> {
  const response = await fetch(`/api/friends/${id}`, {
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
  const response = await fetch(`/api/friends/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete friend')
  }
  return response.json()
}
