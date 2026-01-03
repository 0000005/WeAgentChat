import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as ChatAPI from '@/api/chat'
import { useFriendStore } from './friend'

export interface Session {
    id: number
    title: string
    createdAt: number
    friendId: number
}

export interface Message {
    id: number
    role: 'user' | 'assistant' | 'system'
    content: string
    thinkingContent?: string
    createdAt: number
}

export const useSessionStore = defineStore('session', () => {
    const sessions = ref<Session[]>([])
    const messagesMap = ref<Record<number, Message[]>>({})
    const currentSessionId = ref<number | null>(null)
    const isLoading = ref(false)
    const isStreaming = ref(false)

    const currentMessages = computed(() => {
        if (!currentSessionId.value) return []
        return messagesMap.value[currentSessionId.value] || []
    })

    // Fetch all sessions
    const fetchSessions = async () => {
        isLoading.value = true
        try {
            const apiSessions = await ChatAPI.getSessions()
            sessions.value = apiSessions.map(s => ({
                id: s.id,
                title: s.title || '新对话',
                createdAt: new Date(s.create_time).getTime(),
                friendId: s.friend_id
            }))

            // If we have sessions but no current one, select the first
            if (sessions.value.length > 0 && currentSessionId.value === null) {
                selectSession(sessions.value[0].id)
            }
        } catch (error) {
            console.error('Failed to fetch sessions:', error)
        } finally {
            isLoading.value = false
        }
    }

    const fetchMessages = async (sessionId: number) => {
        try {
            const apiMessages = await ChatAPI.getMessages(sessionId)
            // Sort by creation time if needed, API usually returns sorted but let's ensure
            const mappedMessages = apiMessages.map(m => ({
                id: m.id,
                role: m.role,
                content: m.content,
                createdAt: new Date(m.create_time).getTime()
            }))
            messagesMap.value[sessionId] = mappedMessages
        } catch (error) {
            console.error(`Failed to fetch messages for session ${sessionId}:`, error)
        }
    }

    const createSession = async (friendId?: number) => {
        const friendStore = useFriendStore()

        // Ensure friends are loaded if needed
        if (friendStore.friends.length === 0) {
            try {
                await friendStore.fetchFriends()
            } catch (e) {
                console.error("Failed to load friends for creating session", e)
            }
        }

        let targetFriendId = friendId
        if (!targetFriendId) {
            if (friendStore.friends.length > 0) {
                targetFriendId = friendStore.friends[0].id
            } else {
                console.warn("No friends available to create session")
                return
            }
        }

        try {
            const newSessionApi = await ChatAPI.createSession({
                friend_id: targetFriendId!
            })

            const newSession: Session = {
                id: newSessionApi.id,
                title: newSessionApi.title || '新对话',
                createdAt: new Date(newSessionApi.create_time).getTime(),
                friendId: newSessionApi.friend_id
            }

            sessions.value.unshift(newSession)
            messagesMap.value[newSession.id] = []
            currentSessionId.value = newSession.id
        } catch (error) {
            console.error('Failed to create session:', error)
        }
    }

    const selectSession = async (id: number) => {
        if (sessions.value.find(s => s.id === id)) {
            currentSessionId.value = id
            // Fetch messages if not already loaded or force refresh?
            // For now, fetch if empty or always fetch to sync?
            // Let's always fetch to ensure we have latest history
            await fetchMessages(id)
        }
    }

    const deleteSession = async (id: number) => {
        try {
            await ChatAPI.deleteSession(id)

            const index = sessions.value.findIndex(s => s.id === id)
            if (index !== -1) {
                sessions.value.splice(index, 1)
                delete messagesMap.value[id]

                if (currentSessionId.value === id) {
                    currentSessionId.value = null
                    if (sessions.value.length > 0) {
                        // Select next available
                        selectSession(sessions.value[0].id)
                    } else {
                        // Create a new one? Or just leave empty
                        createSession()
                    }
                }
            }
        } catch (error) {
            console.error('Failed to delete session:', error)
        }
    }

    const sendMessage = async (content: string, enableThinking: boolean = false) => {
        if (!currentSessionId.value) return

        const sessionId = currentSessionId.value

        // 1. Add user message locally
        const userMsg: Message = {
            id: Date.now(),
            role: 'user',
            content: content,
            createdAt: Date.now()
        }

        if (!messagesMap.value[sessionId]) {
            messagesMap.value[sessionId] = []
        }
        messagesMap.value[sessionId].push(userMsg)

        // 2. Add placeholder assistant message
        const assistantMsgId = Date.now() + 1
        const assistantMsg = ref<Message>({
            id: assistantMsgId,
            role: 'assistant',
            content: '',
            thinkingContent: '',
            createdAt: Date.now()
        })
        messagesMap.value[sessionId].push(assistantMsg.value)

        try {
            const stream = ChatAPI.sendMessageStream(sessionId, { content, enable_thinking: enableThinking })

            for await (const { event, data } of stream) {
                const msgIndex = messagesMap.value[sessionId].findIndex(m => m.id === assistantMsgId)
                if (msgIndex === -1) continue

                if (event === 'start') {
                    // Stream started - update metadata if needed
                    // data: { session_id, message_id, user_message_id, ... }
                } else if (event === 'thinking') {
                    isStreaming.value = true
                    const delta = data.delta || ''
                    messagesMap.value[sessionId][msgIndex].thinkingContent += delta
                } else if (event === 'message') {
                    isStreaming.value = true
                    const delta = data.delta || ''
                    messagesMap.value[sessionId][msgIndex].content += delta
                } else if (event === 'error') {
                    messagesMap.value[sessionId][msgIndex].content += `\n[Error: ${data.detail}]`
                } else if (event === 'done') {
                    // Finalize, update real ID if provided
                    if (data.message_id) {
                        messagesMap.value[sessionId][msgIndex].id = data.message_id
                    }
                    isStreaming.value = false
                }
            }

            // Update session title if it's the first message
            const session = sessions.value.find(s => s.id === sessionId)
            if (session && (session.title === '新对话' || session.title === 'New Chat')) {
                const newTitle = content.slice(0, 15)
                session.title = newTitle
                ChatAPI.updateSession(sessionId, { title: newTitle }).catch(e => {
                    console.error("Failed to update session title", e)
                })
            }

        } catch (error) {
            console.error('Failed to send message:', error)
            // Show error in the assistant message
            const msgIndex = messagesMap.value[sessionId].findIndex(m => m.id === assistantMsgId)
            if (msgIndex !== -1) {
                messagesMap.value[sessionId][msgIndex].content = 'Error: Failed to get response from AI.'
            }
        } finally {
            isStreaming.value = false
        }
    }

    // Initialize
    fetchSessions()

    return {
        sessions,
        messagesMap,
        currentSessionId,
        currentMessages,
        isLoading,
        isStreaming,
        fetchSessions,
        createSession,
        selectSession,
        deleteSession,
        sendMessage
    }
})
