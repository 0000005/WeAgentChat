import { withApiBase } from './base'

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
  const response = await fetch(withApiBase('/api/llm/config'))
  if (!response.ok) {
    throw new Error('Failed to fetch LLM config')
  }
  return response.json()
}

export async function updateLlmConfig(config: LLMConfigUpdate): Promise<LLMConfig> {
  const response = await fetch(withApiBase('/api/llm/config'), {
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
