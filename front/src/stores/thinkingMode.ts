import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useLlmStore } from '@/stores/llm'

export const useThinkingModeStore = defineStore('thinkingMode', () => {
    const settingsStore = useSettingsStore()
    const llmStore = useLlmStore()

    const isEnabled = computed(() => settingsStore.enableThinking)
    const canEnable = computed(() => {
        const config = llmStore.getConfigById(settingsStore.activeLlmConfigId)
        return !!config?.capability_reasoning
    })

    const toggle = async () => {
        if (!canEnable.value) {
            settingsStore.enableThinking = false
            await settingsStore.saveChatSettings()
            return
        }
        settingsStore.enableThinking = !settingsStore.enableThinking
        await settingsStore.saveChatSettings()
    }

    const enable = async () => {
        if (!canEnable.value) {
            settingsStore.enableThinking = false
            await settingsStore.saveChatSettings()
            return
        }
        settingsStore.enableThinking = true
        await settingsStore.saveChatSettings()
    }

    const disable = async () => {
        settingsStore.enableThinking = false
        await settingsStore.saveChatSettings()
    }

    return {
        isEnabled,
        canEnable,
        toggle,
        enable,
        disable
    }
})
