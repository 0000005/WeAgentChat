import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as ChatAPI from '@/api/chat'
import { useFriendStore } from './friend'

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

    // Select a friend and load their chat history
    const selectFriend = async (friendId: number) => {
        currentFriendId.value = friendId
        isLoading.value = true
        try {
            await fetchFriendMessages(friendId)
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
            const stream = ChatAPI.sendMessageToFriendStream(friendId, { content, enable_thinking: enableThinking })

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
        isLoading,
        isStreaming,
        selectFriend,
        sendMessage,
        fetchFriendMessages,
        clearFriendMessages
    }
})
