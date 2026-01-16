/**
 * Settings Store - 系统设置状态管理
 * 管理记忆设置（Memory Settings）相关配置
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as SettingsAPI from '@/api/settings'

export const useSettingsStore = defineStore('settings', () => {
    // ===== Session 配置 =====
    // 会话过期时间（秒），默认 1800（30分钟）
    const passiveTimeout = ref<number>(1800)

    // ===== Chat 配置 =====
    // 是否启用深度思考模式，默认 false
    const enableThinking = ref<boolean>(false)

    // ===== Memory 配置 =====
    const recallEnabled = ref<boolean>(true)
    const searchRounds = ref<number>(3)
    const eventTopk = ref<number>(5)
    const similarityThreshold = ref<number>(0.5)

    // ===== User 配置 =====
    const userAvatar = ref<string>('')

    // ===== Loading 状态 =====
    const isLoading = ref(false)
    const isSaving = ref(false)

    /**
     * 通用方法：从后端获取指定分组的配置
     */
    const fetchSettings = async (groupName: string, fieldMapping: Record<string, any>) => {
        isLoading.value = true
        try {
            const settings = await SettingsAPI.getSettingsByGroup(groupName)
            Object.entries(fieldMapping).forEach(([settingKey, ref]) => {
                if (settings[settingKey] !== undefined) {
                    ref.value = settings[settingKey]
                }
            })
        } catch (error) {
            console.error(`Failed to fetch ${groupName} settings:`, error)
        } finally {
            isLoading.value = false
        }
    }

    /**
     * 通用方法：保存指定分组的配置到后端
     */
    const saveSettings = async (groupName: string, fieldMapping: Record<string, any>) => {
        isSaving.value = true
        try {
            const payload = Object.fromEntries(
                Object.entries(fieldMapping).map(([key, ref]) => [key, ref.value])
            )
            console.log(`[SettingsStore] Saving ${groupName} settings payload:`, payload)
            const response = await SettingsAPI.updateSettingsBulk(groupName, payload)
            console.log(`[SettingsStore] Save ${groupName} response:`, response)
        } catch (error) {
            console.error(`[SettingsStore] Failed to save ${groupName} settings:`, error)
            throw error
        } finally {
            isSaving.value = false
        }
    }

    /**
     * 从后端获取 session 分组的配置
     */
    const fetchSessionSettings = () =>
        fetchSettings('session', { passive_timeout: passiveTimeout })

    /**
     * 保存 session 配置到后端
     */
    const saveSessionSettings = () =>
        saveSettings('session', { passive_timeout: passiveTimeout })

    /**
     * 从后端获取 chat 分组的配置
     */
    const fetchChatSettings = () =>
        fetchSettings('chat', {
            enable_thinking: enableThinking
        })

    /**
     * 保存 chat 配置到后端
     */
    const saveChatSettings = () =>
        saveSettings('chat', {
            enable_thinking: enableThinking
        })

    /**
     * 从后端获取 memory 分组的配置
     */
    const fetchMemorySettings = () =>
        fetchSettings('memory', {
            recall_enabled: recallEnabled,
            search_rounds: searchRounds,
            event_topk: eventTopk,
            similarity_threshold: similarityThreshold
        })

    const saveMemorySettings = () =>
        saveSettings('memory', {
            recall_enabled: recallEnabled,
            search_rounds: searchRounds,
            event_topk: eventTopk,
            similarity_threshold: similarityThreshold
        })

    /**
     * 从后端获取 user 分组的配置
     */
    const fetchUserSettings = () =>
        fetchSettings('user', { avatar: userAvatar })

    /**
     * 保存 user 配置到后端
     */
    const saveUserSettings = (avatar?: string) => {
        if (avatar !== undefined) userAvatar.value = avatar
        return saveSettings('user', { avatar: userAvatar })
    }

    /**
     * 将秒数转换为分钟显示
     */
    const getTimeoutInMinutes = (): number => {
        return Math.round(passiveTimeout.value / 60)
    }

    /**
     * 从分钟设置超时时间
     */
    const setTimeoutFromMinutes = (minutes: number) => {
        passiveTimeout.value = minutes * 60
    }

    return {
        // State
        passiveTimeout,
        enableThinking,
        recallEnabled,
        searchRounds,
        eventTopk,
        similarityThreshold,
        userAvatar,
        isLoading,
        isSaving,
        // Actions
        fetchSessionSettings,
        saveSessionSettings,
        getTimeoutInMinutes,
        setTimeoutFromMinutes,
        fetchChatSettings,
        saveChatSettings,
        fetchMemorySettings,
        saveMemorySettings,
        fetchUserSettings,
        saveUserSettings,
    }
})
