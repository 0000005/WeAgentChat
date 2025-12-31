import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { nanoid } from 'nanoid'

export interface Persona {
    id: string
    name: string
    description: string
    systemPrompt: string
    isPreset?: boolean
}

const STORAGE_KEY = 'doudou_chat_personas'

const DEFAULT_PERSONAS: Persona[] = [
    {
        id: 'assistant',
        name: '默认助手',
        description: '通用的 AI 助手，能帮你处理各种任务',
        systemPrompt: '你是一个乐于助人的 AI 助手。',
        isPreset: true
    },
    {
        id: 'coder',
        name: '代码专家',
        description: '精通各种编程语言，专注于代码编写和问题调试',
        systemPrompt: '你是一个资深的软件工程师，精通 TypeScript, Vue 3, Python 等技术栈。请提供高质量、遵循最佳实践的代码，并对代码进行简洁的解释。',
        isPreset: true
    },
    {
        id: 'writer',
        name: '创意写作',
        description: '擅长故事创作、文案润色和创意发散',
        systemPrompt: '你是一个创意丰富的作家。请用生动、优美的语言进行创作。',
        isPreset: true
    }
]

export const usePersonaStore = defineStore('persona', () => {
    const personas = ref<Persona[]>([])

    // Load from local storage
    const init = () => {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
            try {
                const data = JSON.parse(stored)
                if (Array.isArray(data)) {
                    personas.value = data
                }
            } catch (e) {
                console.error('Failed to parse personas from local storage', e)
            }
        }

        // Merge defaults if missing (ensure presets always exist)
        // Check if presets exist, if not, add them.
        // Actually, for simplicity, if it's the first run (empty list), we add defaults.
        // If list is not empty, we might want to ensure presets are there or update them?
        // Let's just ensure presets are present if they are missing by ID.
        DEFAULT_PERSONAS.forEach(defaultP => {
            const exists = personas.value.find(p => p.id === defaultP.id)
            if (!exists) {
                personas.value.push(defaultP)
            } else if (exists.isPreset) {
                 // Optionally update preset prompts if we change them in code?
                 // For now let's respect user's local storage unless we force update logic.
                 // But requirements say "System built-in roles... ID fixed". 
                 // Let's assume we don't overwrite user changes to presets if allowed, 
                 // BUT requirements say "Preset roles cannot be deleted". 
                 // It doesn't explicitly say "cannot be edited". 
                 // Usually presets are read-only or reset-able.
                 // Let's just keep existing logic: ensure they exist.
            }
        })
        
        // If really empty (e.g. storage cleared), ensure defaults are populated
        if (personas.value.length === 0) {
            personas.value = [...DEFAULT_PERSONAS]
        }
    }

    // Persist
    watch(personas, () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(personas.value))
        } catch (e) {
            console.error('Failed to save personas', e)
        }
    }, { deep: true })

    const addPersona = (persona: Omit<Persona, 'id' | 'isPreset'>) => {
        const newPersona: Persona = {
            ...persona,
            id: nanoid(),
            isPreset: false
        }
        personas.value.push(newPersona)
    }

    const updatePersona = (id: string, updates: Partial<Omit<Persona, 'id' | 'isPreset'>>) => {
        const index = personas.value.findIndex(p => p.id === id)
        if (index !== -1) {
            // Merge updates
            personas.value[index] = { ...personas.value[index], ...updates }
        }
    }

    const deletePersona = (id: string) => {
        const index = personas.value.findIndex(p => p.id === id)
        if (index !== -1) {
            if (personas.value[index].isPreset) {
                console.warn('Cannot delete preset persona')
                return
            }
            personas.value.splice(index, 1)
        }
    }

    const getPersona = (id: string) => {
        return personas.value.find(p => p.id === id)
    }

    // Init immediately
    init()

    return {
        personas,
        addPersona,
        updatePersona,
        deletePersona,
        getPersona
    }
})
