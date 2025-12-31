import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { nanoid } from 'nanoid'
import { usePersonaStore } from './persona'

export interface Session {
    id: string
    title: string
    createdAt: number
    personaId: number | null
    systemPrompt?: string
}

export interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    createdAt: number
}

const STORAGE_KEY = 'doudou_chat_storage'

export const useSessionStore = defineStore('session', () => {
    const sessions = ref<Session[]>([])
    const messagesMap = ref<Record<string, Message[]>>({})
    const currentSessionId = ref<string>('')

    // Load from local storage on init
    const init = () => {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
            try {
                const data = JSON.parse(stored)
                // Basic validation
                if (Array.isArray(data.sessions) && typeof data.messagesMap === 'object') {
                    sessions.value = data.sessions
                    messagesMap.value = data.messagesMap
                    currentSessionId.value = data.currentSessionId || ''
                }
            } catch (e) {
                console.error('Failed to parse local storage data', e)
                localStorage.removeItem(STORAGE_KEY)
            }
        }

        // If no sessions, create one
        if (sessions.value.length === 0) {
            // We can't create a session properly without personas loaded, 
            // but we can create a placeholder or wait.
            // For now, let's just allow creating one with null persona or wait for user action.
            // createSession() // Defer creation until needed or allow null
        } else if (!currentSessionId.value || !sessions.value.find(s => s.id === currentSessionId.value)) {
            // If currentSessionId is invalid or empty, select the first one
            currentSessionId.value = sessions.value[0].id
        }
    }

    const currentMessages = computed(() => {
        return messagesMap.value[currentSessionId.value] || []
    })

    // Persistence
    watch(
        [sessions, messagesMap, currentSessionId],
        () => {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify({
                    sessions: sessions.value,
                    messagesMap: messagesMap.value,
                    currentSessionId: currentSessionId.value
                }))
            } catch (e) {
                console.error('Failed to save to local storage', e)
            }
        },
        { deep: true }
    )

    const createSession = (personaId?: number) => {
        const personaStore = usePersonaStore()
        
        // Use provided personaId or default to the first available if possible
        // Note: personaStore.personas might be empty if not fetched yet.
        let targetPersona = personaId ? personaStore.getPersona(personaId) : null
        
        if (!targetPersona && personaStore.personas.length > 0) {
            targetPersona = personaStore.personas[0]
        }

        const id = nanoid()
        const newSession: Session = {
            id,
            title: targetPersona ? targetPersona.name : '新对话',
            createdAt: Date.now(),
            personaId: targetPersona ? targetPersona.id : null,
            systemPrompt: targetPersona?.system_prompt || ''
        }
        
        // Add to the beginning of the list
        sessions.value.unshift(newSession)
        messagesMap.value[id] = []
        currentSessionId.value = id
    }

    const selectSession = (id: string) => {
        if (sessions.value.find(s => s.id === id)) {
            currentSessionId.value = id
        }
    }

    const deleteSession = (id: string) => {
        const index = sessions.value.findIndex(s => s.id === id)
        if (index === -1) return

        // If deleting current session, switch to another one
        if (currentSessionId.value === id) {
            // Remove session first
            sessions.value.splice(index, 1)
            delete messagesMap.value[id]

            if (sessions.value.length === 0) {
                createSession()
            } else {
                // Select the one at the same index if possible (it's the next one in the shifted array)
                // or the previous one if we deleted the last one
                if (index < sessions.value.length) {
                    currentSessionId.value = sessions.value[index].id
                } else {
                    currentSessionId.value = sessions.value[sessions.value.length - 1].id
                }
            }
        } else {
            sessions.value.splice(index, 1)
            delete messagesMap.value[id]
        }
    }

    const addMessageToCurrent = (message: Message) => {
        if (!currentSessionId.value) return

        // Ensure mapping exists
        if (!messagesMap.value[currentSessionId.value]) {
            messagesMap.value[currentSessionId.value] = []
        }

        const msgs = messagesMap.value[currentSessionId.value]
        msgs.push(message)

        // Update title if needed
        const currentSession = sessions.value.find(s => s.id === currentSessionId.value)
        if (currentSession && currentSession.title === '新对话' && message.role === 'user') {
            currentSession.title = message.content.slice(0, 15)
        }
    }

    // Initialize immediately
    init()

    return {
        sessions,
        messagesMap,
        currentSessionId,
        currentMessages,
        createSession,
        selectSession,
        deleteSession,
        addMessageToCurrent
    }
})