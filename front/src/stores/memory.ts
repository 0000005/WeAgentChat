import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

export interface TopicConfig {
    topic: string
    description?: string
    [key: string]: any
}

export interface MemoryConfigData {
    topics: TopicConfig[]
}

export const useMemoryStore = defineStore('memory', () => {
    const profileConfig = ref<MemoryConfigData>({ topics: [] })
    const profiles = ref<Profile[]>([])
    const isLoading = ref(false)

    const fetchConfig = async () => {
        try {
            const res = await getMemoryConfig()
            if (res.profile_config) {
                profileConfig.value = yaml.load(res.profile_config) as MemoryConfigData
            } else {
                // Fallback to defaults if empty
                profileConfig.value = {
                    topics: [
                        { topic: '基本特征', description: '姓名、年龄、职业等基础信息' },
                        { topic: '性格习惯', description: '性格特点、日常习惯等' },
                        { topic: '兴趣爱好', description: '喜欢的事物、常去的地点等' }
                    ]
                }
            }
        } catch (error) {
            console.error('Failed to fetch memory config:', error)
            // Fallback
            profileConfig.value = {
                topics: [
                    { topic: '基本特征', description: '姓名、年龄、职业等基础信息' },
                    { topic: '性格习惯', description: '性格特点、日常习惯等' },
                    { topic: '兴趣爱好', description: '喜欢的事物、常去的地点等' }
                ]
            }
        }
    }

    const saveConfig = async () => {
        try {
            const yamlStr = yaml.dump(profileConfig.value)
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
        profileConfig.value.topics.forEach(t => {
            groups[t.topic] = []
        })

        // Standard mapping from Memobase keys to our default Chinese topics
        const topicMapping: Record<string, string> = {
            'basic_info': '基本特征',
            'contact_info': '基本特征',
            'education': '基本特征',
            'work': '基本特征',
            'demographics': '基本特征',

            'psychological': '性格习惯',
            'personality': '性格习惯',

            'interest': '兴趣爱好',
            'life_event': '兴趣爱好' // Or create a new category if needed
        }

        // Add profiles to groups
        profiles.value.forEach(p => {
            let topic = p.attributes.topic || '其他'

            // 1. Try direct match
            if (!groups[topic]) {
                // 2. Try mapping
                const mapped = topicMapping[topic]
                if (mapped && groups[mapped]) {
                    topic = mapped
                }
            }

            // 3. If still not found, check if we should add it to a fallback or just ignore
            // For now, if we match a group, push it.
            if (groups[topic]) {
                groups[topic].push(p)
            } else {
                // Determine if we should create a temporary group or put in "Others"
                // Ideally, we shouldn't hide data. 
                // However, the current UI iterates over `profileConfig.topics` exclusively.
                // So adding to `groups` with a new key won't help unless we update config or UI.
                // Let's try to put into the first available group if absolutely necessary, 
                // OR (better) just let them fall into "other" if "other" exists, 
                // but since "other" isn't in default config, they remain hidden.
                // LIMITATION: Profiles with topics not in config and not in mapping will be hidden.
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
