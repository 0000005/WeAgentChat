import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
    getEmbeddingSettings,
    createEmbeddingSetting,
    updateEmbeddingSetting,
    type EmbeddingSettingCreate,
    type EmbeddingSettingUpdate
} from '@/api/embedding'

export const useEmbeddingStore = defineStore('embedding', () => {
    const id = ref<number | null>(null)
    const provider = ref<string>('openai')
    const apiKey = ref<string>('')
    const baseUrl = ref<string>('')
    const dim = ref<number>(1024)
    const model = ref<string>('BAAI/bge-m3')
    const maxTokenSize = ref<number>(8000)

    const isLoading = ref(false)
    const error = ref<string | null>(null)

    async function fetchConfig() {
        isLoading.value = true
        error.value = null
        try {
            const settings = await getEmbeddingSettings(0, 1)
            if (settings && settings.length > 0) {
                const config = settings[0]
                id.value = config.id
                provider.value = config.embedding_provider || 'openai'
                apiKey.value = config.embedding_api_key || ''
                baseUrl.value = config.embedding_base_url || ''
                dim.value = config.embedding_dim || 1024
                model.value = config.embedding_model || 'BAAI/bge-m3'
                maxTokenSize.value = config.embedding_max_token_size || 8000
            } else {
                // Reset to defaults if no config exists
                id.value = null
                provider.value = 'openai'
                apiKey.value = ''
                baseUrl.value = ''
                dim.value = 1024
                model.value = 'BAAI/bge-m3'
                maxTokenSize.value = 8000
            }
        } catch (e: any) {
            console.error('Failed to fetch embedding config:', e)
            error.value = e.message || 'Failed to fetch configuration'
        } finally {
            isLoading.value = false
        }
    }

    async function saveConfig() {
        isLoading.value = true
        error.value = null
        try {
            if (id.value) {
                const updateData: EmbeddingSettingUpdate = {
                    embedding_provider: provider.value,
                    embedding_api_key: apiKey.value || null,
                    embedding_base_url: baseUrl.value || null,
                    embedding_dim: dim.value,
                    embedding_model: model.value,
                    embedding_max_token_size: maxTokenSize.value
                }
                const config = await updateEmbeddingSetting(id.value, updateData)
                id.value = config.id
            } else {
                const createData: EmbeddingSettingCreate = {
                    embedding_provider: provider.value,
                    embedding_api_key: apiKey.value || null,
                    embedding_base_url: baseUrl.value || null,
                    embedding_dim: dim.value,
                    embedding_model: model.value,
                    embedding_max_token_size: maxTokenSize.value
                }
                const config = await createEmbeddingSetting(createData)
                id.value = config.id
            }
        } catch (e: any) {
            console.error('Failed to save embedding config:', e)
            error.value = e.message || 'Failed to save configuration'
            throw e
        } finally {
            isLoading.value = false
        }
    }

    return {
        id,
        provider,
        apiKey,
        baseUrl,
        dim,
        model,
        maxTokenSize,
        isLoading,
        error,
        fetchConfig,
        saveConfig
    }
})
