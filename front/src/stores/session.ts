import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as ChatAPI from '@/api/chat'

export interface Message {
    id: number
    role: 'user' | 'assistant' | 'system'
    content: string
    thinkingContent?: string
    createdAt: number
    sessionId?: number
}

export const useSessionStore = defineStore('session', () => {
    // Current selected friend ID (WeChat-style: contact list)
    const currentFriendId = ref<number | null>(null)

    // Messages map: friendId -> Message[]
    const messagesMap = ref<Record<number, Message[]>>({})

    const isLoading = ref(false)
    const isStreaming = ref(false)

    // Current specific session ID (if not null, show only this session's messages)
    const currentSessionId = ref<number | null>(null)
    const currentSessions = ref<ChatAPI.ChatSession[]>([])
    const fetchError = ref<string | null>(null)

    // Get messages for current friend
    const currentMessages = computed(() => {
        if (!currentFriendId.value) return []
        return messagesMap.value[currentFriendId.value] || []
    })

    // Fetch messages for a specific friend (merged from all sessions)
    const fetchFriendMessages = async (friendId: number) => {
        try {
            const apiMessages = await ChatAPI.getFriendMessages(friendId)
            const mappedMessages = apiMessages.map(m => ({
                id: m.id,
                role: m.role as 'user' | 'assistant' | 'system',
                content: m.content,
                createdAt: new Date(m.create_time).getTime(),
                sessionId: m.session_id
            }))
            messagesMap.value[friendId] = mappedMessages
        } catch (error) {
            console.error(`Failed to fetch messages for friend ${friendId}:`, error)
        }
    }

    // Fetch all sessions for a specific friend
    const fetchFriendSessions = async (friendId: number) => {
        fetchError.value = null
        try {
            const sessions = await ChatAPI.getFriendSessions(friendId)
            currentSessions.value = sessions
        } catch (error) {
            console.error(`Failed to fetch sessions for friend ${friendId}:`, error)
            fetchError.value = '无法加载会话列表，请检查网络连接。'
        }
    }

    // Reset to merged view (all messages for the friend)
    const resetToMergedView = async () => {
        if (!currentFriendId.value) return
        currentSessionId.value = null
        isLoading.value = true
        try {
            await fetchFriendMessages(currentFriendId.value)
        } finally {
            isLoading.value = false
        }
    }

    // Load messages for a SPECIFIC session
    const loadSpecificSession = async (sessionId: number) => {
        currentSessionId.value = sessionId
        isLoading.value = true
        try {
            const apiMessages = await ChatAPI.getMessages(sessionId)
            const mappedMessages = apiMessages.map(m => ({
                id: m.id,
                role: m.role as 'user' | 'assistant' | 'system',
                content: m.content,
                createdAt: new Date(m.create_time).getTime(),
                sessionId: m.session_id
            }))

            // For now, we reuse the same list but clear it if we are switching to a specific session
            // In a more persistent setup, we might want a separate map for sessions
            if (currentFriendId.value) {
                messagesMap.value[currentFriendId.value] = mappedMessages
            }
        } catch (error) {
            console.error(`Failed to load session ${sessionId}:`, error)
        } finally {
            isLoading.value = false
        }
    }

    // Select a friend and load their chat history
    const selectFriend = async (friendId: number) => {
        currentFriendId.value = friendId
        currentSessionId.value = null // Reset to default merged/latest view
        isLoading.value = true
        try {
            await Promise.all([
                fetchFriendMessages(friendId),
                fetchFriendSessions(friendId)
            ])
        } finally {
            isLoading.value = false
        }
    }

    // Send message to current friend
    const sendMessage = async (content: string, enableThinking: boolean = false) => {
        if (!currentFriendId.value) return

        const friendId = currentFriendId.value

        // 1. Add user message locally
        const userMsg: Message = {
            id: Date.now(),
            role: 'user',
            content: content,
            createdAt: Date.now()
        }

        if (!messagesMap.value[friendId]) {
            messagesMap.value[friendId] = []
        }
        messagesMap.value[friendId].push(userMsg)

        // 2. Add placeholder assistant message
        const assistantMsgId = Date.now() + 1
        const assistantMsg = ref<Message>({
            id: assistantMsgId,
            role: 'assistant',
            content: '',
            thinkingContent: '',
            createdAt: Date.now()
        })
        messagesMap.value[friendId].push(assistantMsg.value)

        try {
            // 如果当前正在查看特定会话，则按会话 ID 发送消息；否则按好友 ID 发送（由后端自动寻址）
            const stream = currentSessionId.value
                ? ChatAPI.sendMessageStream(currentSessionId.value, { content, enable_thinking: enableThinking })
                : ChatAPI.sendMessageToFriendStream(friendId, { content, enable_thinking: enableThinking })

            for await (const { event, data } of stream) {
                const msgIndex = messagesMap.value[friendId].findIndex(m => m.id === assistantMsgId)
                if (msgIndex === -1) continue

                if (event === 'start') {
                    // Stream started - update metadata if needed
                    // data: { session_id, message_id, user_message_id, ... }
                } else if (event === 'thinking') {
                    isStreaming.value = true
                    const delta = data.delta || ''
                    messagesMap.value[friendId][msgIndex].thinkingContent += delta
                } else if (event === 'message') {
                    isStreaming.value = true
                    const delta = data.delta || ''
                    messagesMap.value[friendId][msgIndex].content += delta
                } else if (event === 'error') {
                    messagesMap.value[friendId][msgIndex].content += `\n[Error: ${data.detail}]`
                } else if (event === 'done') {
                    // Finalize, update real ID if provided
                    if (data.message_id) {
                        messagesMap.value[friendId][msgIndex].id = data.message_id
                    }
                    isStreaming.value = false
                    // 异步刷新会话列表统计
                    fetchFriendSessions(friendId)
                }
            }

        } catch (error) {
            console.error('Failed to send message:', error)
            // Show error in the assistant message
            const msgIndex = messagesMap.value[friendId].findIndex(m => m.id === assistantMsgId)
            if (msgIndex !== -1) {
                messagesMap.value[friendId][msgIndex].content = 'Error: Failed to get response from AI.'
            }
        } finally {
            isStreaming.value = false
        }
    }

    // Clear messages for a friend (for testing or reset)
    const clearFriendMessages = (friendId: number) => {
        delete messagesMap.value[friendId]
    }

    return {
        currentFriendId,
        messagesMap,
        currentMessages,
        currentSessions,
        currentSessionId,
        fetchError,
        isLoading,
        isStreaming,
        selectFriend,
        sendMessage,
        fetchFriendMessages,
        fetchFriendSessions,
        loadSpecificSession,
        resetToMergedView,
        clearFriendMessages,
        startNewSession: async () => {
            if (!currentFriendId.value) return

            currentSessionId.value = null // 重置为活跃视图

            // Prevent multiple consecutive new sessions
            const messages = messagesMap.value[currentFriendId.value]
            if (messages && messages.length > 0) {
                const lastMsg = messages[messages.length - 1]
                if (lastMsg.role === 'system' && lastMsg.content === '新会话') {
                    return
                }
            }

            try {
                await ChatAPI.createSession({ friend_id: currentFriendId.value })
                await fetchFriendSessions(currentFriendId.value) // 刷新会话列表
                // Add system message manually to the local list
                if (!messagesMap.value[currentFriendId.value]) {
                    messagesMap.value[currentFriendId.value] = []
                }
                messagesMap.value[currentFriendId.value].push({
                    id: Date.now(),
                    role: 'system',
                    content: '新会话',
                    createdAt: Date.now()
                })
            } catch (error) {
                console.error('Failed to start new session:', error)
            }
        }
    }
})
