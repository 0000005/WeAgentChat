import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import {
    getMemoryConfig,
    updateMemoryConfig,
    getProfiles,
    addProfile,
    updateProfile,
    deleteProfile,
    deleteProfiles,
    type Profile,
    type ProfileAttributes
} from '@/api/memory'
import yaml from 'js-yaml'

/**
 * Topic configuration for UI display.
 * Maps to Memobase UserProfileTopic structure.
 */
export interface TopicConfig {
    topic: string
    description?: string
    sub_topics?: Array<{ name: string; description?: string }>
}

/**
 * Memory config data structure.
 * Uses overwrite_user_profiles to match Memobase ProfileConfig format.
 */
export interface MemobaseProfileConfig {
    overwrite_user_profiles?: TopicConfig[]
    additional_user_profiles?: TopicConfig[]
    language?: 'en' | 'zh'
}

// Default topics that match Memobase's zh_user_profile_topics.py
const DEFAULT_TOPICS: TopicConfig[] = [
    { topic: '基本信息', description: '用户姓名、年龄、性别、国籍等基础信息', sub_topics: [] },
    { topic: '兴趣爱好', description: '书籍、电影、音乐、美食、运动等', sub_topics: [] },
    { topic: '生活方式', description: '饮食偏好、运动习惯、健康状况等', sub_topics: [] },
    { topic: '心理特征', description: '性格特点、价值观、信仰、目标等', sub_topics: [] },
]

export const useMemoryStore = defineStore('memory', () => {
    // Internal state: uses Memobase's expected format
    const _config = ref<MemobaseProfileConfig>({ overwrite_user_profiles: [] })
    const profiles = ref<Profile[]>([])
    const isLoading = ref(false)

    /**
     * Reactive accessor for topics - provides compatibility with UI components.
     * This is the array that UI components should use for v-model binding.
     */
    const profileConfig = reactive({
        get topics(): TopicConfig[] {
            return _config.value.overwrite_user_profiles || []
        },
        set topics(val: TopicConfig[]) {
            _config.value.overwrite_user_profiles = val
        }
    })

    const fetchConfig = async () => {
        try {
            const res = await getMemoryConfig()
            if (res.profile_config) {
                const parsed = yaml.load(res.profile_config) as MemobaseProfileConfig
                // Handle both old format (topics) and new format (overwrite_user_profiles)
                if (parsed.overwrite_user_profiles) {
                    _config.value = parsed
                } else if ((parsed as any).topics) {
                    // Migration from old format
                    _config.value = {
                        overwrite_user_profiles: (parsed as any).topics.map((t: TopicConfig) => ({
                            ...t,
                            sub_topics: t.sub_topics || []
                        }))
                    }
                } else {
                    _config.value = { overwrite_user_profiles: [...DEFAULT_TOPICS] }
                }
            } else {
                // Fallback to defaults if empty
                _config.value = { overwrite_user_profiles: [...DEFAULT_TOPICS] }
            }
        } catch (error) {
            console.error('Failed to fetch memory config:', error)
            // Fallback
            _config.value = { overwrite_user_profiles: [...DEFAULT_TOPICS] }
        }
    }

    const saveConfig = async () => {
        try {
            // Ensure all topics have sub_topics field
            const configToSave: MemobaseProfileConfig = {
                overwrite_user_profiles: (_config.value.overwrite_user_profiles || []).map(t => ({
                    topic: t.topic,
                    description: t.description,
                    sub_topics: t.sub_topics || []
                }))
            }
            const yamlStr = yaml.dump(configToSave)
            await updateMemoryConfig(yamlStr)
        } catch (error) {
            console.error('Failed to save memory config:', error)
            throw error
        }
    }

    const fetchProfiles = async () => {
        isLoading.value = true
        try {
            const res = await getProfiles()
            profiles.value = res.profiles
        } catch (error) {
            console.error('Failed to fetch profiles:', error)
        } finally {
            isLoading.value = false
        }
    }

    const upsertProfile = async (id: string | null, content: string, attributes: ProfileAttributes) => {
        try {
            if (id) {
                await updateProfile(id, content, attributes)
            } else {
                await addProfile(content, attributes)
            }
            await fetchProfiles()
        } catch (error) {
            console.error('Failed to upsert profile:', error)
            throw error
        }
    }

    const removeProfile = async (id: string) => {
        try {
            await deleteProfile(id)
            await fetchProfiles()
        } catch (error) {
            console.error('Failed to delete profile:', error)
            throw error
        }
    }

    const removeProfiles = async (ids: string[]) => {
        if (ids.length === 0) return
        try {
            await deleteProfiles(ids)
            // Do not refresh here, let the caller decide
        } catch (error) {
            console.error('Failed to delete profiles:', error)
            throw error
        }
    }

    const groupedProfiles = computed(() => {
        const groups: Record<string, Profile[]> = {}

        // Initialize groups with topics from config
        // Note: profileConfig is reactive, access .topics directly (not .value.topics)
        profileConfig.topics.forEach((t: TopicConfig) => {
            groups[t.topic] = []
        })

        // Add profiles to groups
        profiles.value.forEach(p => {
            const topic = p.attributes.topic || '其他'

            // Direct match: if the topic is already configured, add to it
            if (groups[topic] !== undefined) {
                groups[topic].push(p)
            } else {
                // Dynamic group: create a new group for topics not in config
                // This ensures we don't hide any profile data
                if (!groups[topic]) {
                    groups[topic] = []
                }
                groups[topic].push(p)
            }
        })

        return groups
    })

    return {
        profileConfig,
        profiles,
        isLoading,
        fetchConfig,
        saveConfig,
        fetchProfiles,
        upsertProfile,
        removeProfile,
        removeProfiles,
        groupedProfiles
    }
})
