export interface EmbeddingSetting {
    id: number
    embedding_provider: string | null
    embedding_api_key: string | null
    embedding_base_url: string | null
    embedding_dim: number | null
    embedding_model: string | null
    embedding_max_token_size: number | null
    create_time: string
    update_time: string
    deleted: boolean
}

export interface EmbeddingSettingCreate {
    embedding_provider?: string | null
    embedding_api_key?: string | null
    embedding_base_url?: string | null
    embedding_dim?: number | null
    embedding_model?: string | null
    embedding_max_token_size?: number | null
}

export interface EmbeddingSettingUpdate {
    embedding_provider?: string | null
    embedding_api_key?: string | null
    embedding_base_url?: string | null
    embedding_dim?: number | null
    embedding_model?: string | null
    embedding_max_token_size?: number | null
}

export async function getEmbeddingSettings(skip: number = 0, limit: number = 100): Promise<EmbeddingSetting[]> {
    const response = await fetch(`/api/embedding-settings/?skip=${skip}&limit=${limit}`)
    if (!response.ok) {
        throw new Error('Failed to fetch embedding settings')
    }
    return response.json()
}

export async function createEmbeddingSetting(data: EmbeddingSettingCreate): Promise<EmbeddingSetting> {
    const response = await fetch('/api/embedding-settings/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    if (!response.ok) {
        throw new Error('Failed to create embedding setting')
    }
    return response.json()
}

export async function updateEmbeddingSetting(id: number, data: EmbeddingSettingUpdate): Promise<EmbeddingSetting> {
    const response = await fetch(`/api/embedding-settings/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    if (!response.ok) {
        throw new Error('Failed to update embedding setting')
    }
    return response.json()
}
