import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getLlmConfigs,
  createLlmConfig,
  updateLlmConfig,
  deleteLlmConfig,
  testLlmConfig,
  type LLMConfig,
  type LLMConfigCreate,
  type LLMConfigUpdate,
  type LLMTestResult
} from '@/api/llm'

export const useLlmStore = defineStore('llm', () => {
  const configs = ref<LLMConfig[]>([])
  const isLoading = ref(false)
  const isTesting = ref(false)
  const error = ref<string | null>(null)
  const testResult = ref<LLMTestResult | null>(null)

  const upsertConfig = (config: LLMConfig) => {
    const index = configs.value.findIndex(item => item.id === config.id)
    if (index >= 0) {
      configs.value.splice(index, 1, config)
    } else {
      configs.value.unshift(config)
    }
  }

  async function fetchConfigs() {
    isLoading.value = true
    error.value = null
    try {
      const list = await getLlmConfigs(0, 100)
      configs.value = list
    } catch (e: any) {
      console.error('Failed to fetch LLM configs:', e)
      error.value = e.message || 'Failed to fetch configuration'
    } finally {
      isLoading.value = false
    }
  }

  function getConfigById(id: number | null) {
    if (!id) return null
    return configs.value.find(item => item.id === id) || null
  }

  async function createConfig(data: LLMConfigCreate) {
    isLoading.value = true
    error.value = null
    try {
      const config = await createLlmConfig(data)
      upsertConfig(config)
      return config
    } catch (e: any) {
      console.error('Failed to create LLM config:', e)
      error.value = e.message || 'Failed to create configuration'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function updateConfig(id: number, data: LLMConfigUpdate) {
    isLoading.value = true
    error.value = null
    try {
      const config = await updateLlmConfig(id, data)
      upsertConfig(config)
      return config
    } catch (e: any) {
      console.error('Failed to update LLM config:', e)
      error.value = e.message || 'Failed to update configuration'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function removeConfig(id: number) {
    isLoading.value = true
    error.value = null
    try {
      const config = await deleteLlmConfig(id)
      configs.value = configs.value.filter(item => item.id !== id)
      return config
    } catch (e: any) {
      console.error('Failed to delete LLM config:', e)
      error.value = e.message || 'Failed to delete configuration'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function testConfig(payload: LLMConfigUpdate): Promise<LLMTestResult> {
    isTesting.value = true
    testResult.value = null
    error.value = null
    try {
      const result = await testLlmConfig(payload)
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

  const hasConfigs = computed(() => configs.value.length > 0)

  return {
    configs,
    isLoading,
    isTesting,
    error,
    testResult,
    hasConfigs,
    fetchConfigs,
    getConfigById,
    createConfig,
    updateConfig,
    removeConfig,
    testConfig
  }
})
