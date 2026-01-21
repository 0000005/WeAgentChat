import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
    getEmbeddingSettings,
    createEmbeddingSetting,
    updateEmbeddingSetting,
    deleteEmbeddingSetting,
    testEmbeddingConfig,
    type EmbeddingSetting,
    type EmbeddingSettingCreate,
    type EmbeddingSettingUpdate,
    type EmbeddingTestResult
} from '@/api/embedding'

export const useEmbeddingStore = defineStore('embedding', () => {
    const configs = ref<EmbeddingSetting[]>([])
    const isLoading = ref(false)
    const isTesting = ref(false)
    const error = ref<string | null>(null)
    const testResult = ref<EmbeddingTestResult | null>(null)

    const upsertConfig = (config: EmbeddingSetting) => {
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
            const list = await getEmbeddingSettings(0, 100)
            configs.value = list
        } catch (e: any) {
            console.error('Failed to fetch embedding configs:', e)
            error.value = e.message || 'Failed to fetch configuration'
        } finally {
            isLoading.value = false
        }
    }

    function getConfigById(id: number | null) {
        if (!id) return null
        return configs.value.find(item => item.id === id) || null
    }

    async function createConfig(data: EmbeddingSettingCreate) {
        isLoading.value = true
        error.value = null
        try {
            const config = await createEmbeddingSetting(data)
            upsertConfig(config)
            return config
        } catch (e: any) {
            console.error('Failed to create embedding config:', e)
            error.value = e.message || 'Failed to create configuration'
            throw e
        } finally {
            isLoading.value = false
        }
    }

    async function updateConfig(id: number, data: EmbeddingSettingUpdate) {
        isLoading.value = true
        error.value = null
        try {
            const config = await updateEmbeddingSetting(id, data)
            upsertConfig(config)
            return config
        } catch (e: any) {
            console.error('Failed to update embedding config:', e)
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
            const config = await deleteEmbeddingSetting(id)
            configs.value = configs.value.filter(item => item.id !== id)
            return config
        } catch (e: any) {
            console.error('Failed to delete embedding config:', e)
            error.value = e.message || 'Failed to delete configuration'
            throw e
        } finally {
            isLoading.value = false
        }
    }

    async function testConfig(payload: EmbeddingSettingCreate): Promise<EmbeddingTestResult> {
        isTesting.value = true
        testResult.value = null
        error.value = null
        try {
            const result = await testEmbeddingConfig(payload)
            testResult.value = result
            return result
        } catch (e: any) {
            console.error('Failed to test embedding config:', e)
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
