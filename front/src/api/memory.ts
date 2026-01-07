import { withApiBase } from './base'

export interface ProfileAttributes {
    topic: string
    [key: string]: any
}

export interface Profile {
    id: string
    content: string
    attributes: ProfileAttributes
    created_at?: string
    updated_at?: string
}

export interface ProfileConfig {
    profile_config: string // YAML string
}

export interface BatchDeleteRequest {
    profile_ids: string[]
}

export interface EventGistData {
    content: string
}

export interface UserEventGist {
    id: string
    gist_data: EventGistData
    created_at: string
    updated_at: string
}

export interface UserEventGistsData {
    gists: UserEventGist[]
    events: any[]
}

// --- API Functions ---

export async function getMemoryConfig(): Promise<ProfileConfig> {
    const response = await fetch(withApiBase('/api/memory/config'))
    if (!response.ok) {
        throw new Error('Failed to fetch memory config')
    }
    return response.json()
}

export async function updateMemoryConfig(config: string): Promise<any> {
    const response = await fetch(withApiBase('/api/memory/config'), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ profile_config: config }),
    })
    if (!response.ok) {
        throw new Error('Failed to update memory config')
    }
    return response.json()
}

export async function getProfiles(): Promise<{ profiles: Profile[] }> {
    const response = await fetch(withApiBase('/api/memory/profiles'))
    if (!response.ok) {
        throw new Error('Failed to fetch profiles')
    }
    return response.json()
}

export async function addProfile(content: string, attributes: ProfileAttributes): Promise<{ ids: string[] }> {
    const response = await fetch(withApiBase('/api/memory/profiles'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, attributes }),
    })
    if (!response.ok) {
        throw new Error('Failed to add profile')
    }
    return response.json()
}

export async function updateProfile(id: string, content: string, attributes?: ProfileAttributes): Promise<any> {
    const response = await fetch(withApiBase(`/api/memory/profiles/${id}`), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, attributes }),
    })
    if (!response.ok) {
        throw new Error('Failed to update profile')
    }
    return response.json()
}

export async function deleteProfile(id: string): Promise<any> {
    const response = await fetch(withApiBase(`/api/memory/profiles/${id}`), {
        method: 'DELETE',
    })
    if (!response.ok) {
        throw new Error('Failed to delete profile')
    }
    return response.json()
}

export async function deleteProfiles(ids: string[]): Promise<any> {
    const response = await fetch(withApiBase('/api/memory/profiles'), {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ profile_ids: ids }),
    })
    if (!response.ok) {
        throw new Error('Failed to delete profiles')
    }
    return response.json()
}

export async function getFriendEventGists(friendId: number, limit: number = 50): Promise<UserEventGistsData> {
    const response = await fetch(withApiBase(`/api/memory/events_gists?friend_id=${friendId}&limit=${limit}`))
    if (!response.ok) {
        throw new Error('Failed to fetch friend event gists')
    }
    return response.json()
}
