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
