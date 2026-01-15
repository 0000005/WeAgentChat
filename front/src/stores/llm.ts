import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getLlmConfig, updateLlmConfig, testLlmConfig, type LLMConfigUpdate, type LLMTestResult } from '@/api/llm'

export const useLlmStore = defineStore('llm', () => {
  const apiBaseUrl = ref('')
  const apiKey = ref('')
  const modelName = ref('gpt-3.5-turbo')
  const isLoading = ref(false)
  const isTesting = ref(false)
  const error = ref<string | null>(null)
  const testResult = ref<LLMTestResult | null>(null)

  async function fetchConfig() {
    isLoading.value = true
    error.value = null
    try {
      const config = await getLlmConfig()
      apiBaseUrl.value = config.base_url || ''
      apiKey.value = config.api_key || ''
      modelName.value = config.model_name || 'gpt-3.5-turbo'
    } catch (e: any) {
      console.error('Failed to fetch LLM config:', e)
      error.value = e.message || 'Failed to fetch configuration'
    } finally {
      isLoading.value = false
    }
  }

  async function saveConfig() {
    isLoading.value = true
    error.value = null
    try {
      const updateData: LLMConfigUpdate = {
        base_url: apiBaseUrl.value || null, // Convert empty string to null if preferred, or keep as string
        api_key: apiKey.value || null,
        model_name: modelName.value || 'gpt-3.5-turbo'
      }
      const config = await updateLlmConfig(updateData)
      // Update state with returned config
      apiBaseUrl.value = config.base_url || ''
      apiKey.value = config.api_key || ''
      modelName.value = config.model_name || 'gpt-3.5-turbo'
    } catch (e: any) {
      console.error('Failed to save LLM config:', e)
      error.value = e.message || 'Failed to save configuration'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function testConfig(): Promise<LLMTestResult> {
    isTesting.value = true
    testResult.value = null
    error.value = null
    try {
      const result = await testLlmConfig({
        base_url: apiBaseUrl.value || null,
        api_key: apiKey.value || null,
        model_name: modelName.value || 'gpt-3.5-turbo'
      })
      testResult.value = result
      return result
    } catch (e: any) {
      console.error('Failed to test LLM config:', e)
      error.value = e.message || 'Test failed'
      throw e
    } finally {
      isTesting.value = false
    }
  }

  const isConfigured = computed(() => {
    return !!apiBaseUrl.value && apiBaseUrl.value.trim().length > 0
  })

  return {
    apiBaseUrl,
    apiKey,
    modelName,
    isLoading,
    isTesting,
    error,
    testResult,
    isConfigured,
    fetchConfig,
    saveConfig,
    testConfig
  }
})