import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'

export const useLlmStore = defineStore('llm', () => {
  const apiBaseUrl = useLocalStorage('llm-api-base-url', '')
  const apiKey = useLocalStorage('llm-api-key', '')
  const modelName = useLocalStorage('llm-model-name', 'gpt-3.5-turbo')

  return {
    apiBaseUrl,
    apiKey,
    modelName
  }
})
