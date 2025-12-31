export interface LLMConfig {
  id: number
  base_url: string | null
  api_key: string | null
  model_name: string | null
  create_time: string
  update_time: string
  deleted: boolean
}

export interface LLMConfigUpdate {
  base_url?: string | null
  api_key?: string | null
  model_name?: string | null
}

export async function getLlmConfig(): Promise<LLMConfig> {
  const response = await fetch('/api/llm/config')
  if (!response.ok) {
    throw new Error('Failed to fetch LLM config')
  }
  return response.json()
}

export async function updateLlmConfig(config: LLMConfigUpdate): Promise<LLMConfig> {
  const response = await fetch('/api/llm/config', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  if (!response.ok) {
    throw new Error('Failed to update LLM config')
  }
  return response.json()
}
