import { withApiBase } from './base'

export interface LLMConfig {
  id?: number
  provider?: string | null
  config_name?: string | null
  base_url?: string | null
  api_key?: string | null
  model_name?: string | null
  is_active?: boolean | null
  is_verified?: boolean | null
  capability_vision?: boolean | null
  capability_search?: boolean | null
  capability_reasoning?: boolean | null
  capability_function_call?: boolean | null
  create_time?: string
  update_time?: string
  deleted?: boolean
}

export interface LLMConfigUpdate {
  provider?: string | null
  config_name?: string | null
  base_url?: string | null
  api_key?: string | null
  model_name?: string | null
  is_active?: boolean | null
  is_verified?: boolean | null
  capability_vision?: boolean | null
  capability_search?: boolean | null
  capability_reasoning?: boolean | null
  capability_function_call?: boolean | null
}

export interface LLMConfigCreate extends LLMConfigUpdate {}

export async function getLlmConfigs(skip: number = 0, limit: number = 100): Promise<LLMConfig[]> {
  const response = await fetch(withApiBase(`/api/llm/configs?skip=${skip}&limit=${limit}`))
  if (!response.ok) {
    throw new Error('Failed to fetch LLM configs')
  }
  return response.json()
}

export async function createLlmConfig(config: LLMConfigCreate): Promise<LLMConfig> {
  const response = await fetch(withApiBase('/api/llm/configs'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create LLM config' }))
    throw new Error(error.detail || 'Failed to create LLM config')
  }
  return response.json()
}

export async function updateLlmConfig(id: number, config: LLMConfigUpdate): Promise<LLMConfig> {
  const response = await fetch(withApiBase(`/api/llm/configs/${id}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update LLM config' }))
    throw new Error(error.detail || 'Failed to update LLM config')
  }
  return response.json()
}

export async function deleteLlmConfig(id: number): Promise<LLMConfig> {
  const response = await fetch(withApiBase(`/api/llm/configs/${id}`), {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete LLM config' }))
    throw new Error(error.detail || 'Failed to delete LLM config')
  }
  return response.json()
}

export interface LLMTestResult {
  success: boolean
  message: string
  model?: string
  response?: string
}

export async function testLlmConfig(config: LLMConfigUpdate): Promise<LLMTestResult> {
  const response = await fetch(withApiBase('/api/llm/config/test'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Test failed' }))
    throw new Error(error.detail || 'LLM test failed')
  }
  return response.json()
}

export async function testLlmConfigById(id: number): Promise<LLMTestResult> {
  const response = await fetch(withApiBase(`/api/llm/configs/${id}/test`), {
    method: 'POST',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'LLM test failed' }))
    throw new Error(error.detail || 'LLM test failed')
  }
  return response.json()
}
