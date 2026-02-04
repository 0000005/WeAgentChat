import type { Ref } from 'vue'
import * as ChatAPI from '@/api/chat'
import type { Message } from '@/types/chat'
import { INITIAL_MESSAGE_LIMIT } from '@/utils/chat'

export type SessionFetchDeps = {
    messagesMap: Ref<Record<string, Message[]>>
    isLoading: Ref<boolean>
    isLoadingMore: Ref<boolean>
    currentFriendId: Ref<number | null>
    currentSessions: Ref<ChatAPI.ChatSession[]>
    currentSessionId: Ref<number | null>
}

export const createSessionFetch = (deps: SessionFetchDeps) => {
    const {
        messagesMap,
        isLoading,
        isLoadingMore,
        currentFriendId,
        currentSessions,
        currentSessionId
    } = deps

    const fetchFriendMessages = async (friendId: number, skip: number = 0, limit: number = INITIAL_MESSAGE_LIMIT) => {
        try {
            const apiMessages = await ChatAPI.getFriendMessages(friendId, skip, limit)
            const mappedMessages = apiMessages.map(m => ({
                id: m.id,
                role: m.role as 'user' | 'assistant' | 'system',
                content: m.content,
                createdAt: new Date(m.create_time).getTime(),
                sessionId: m.session_id
            }))

            if (skip === 0) {
                messagesMap.value['f' + friendId] = mappedMessages
            } else {
                // If skipping, it's pagination - prepend messages
                const currentMsgs = messagesMap.value['f' + friendId] || []
                // Ensure no duplicates
                const existingIds = new Set(currentMsgs.map(m => m.id))
                const newMsgs = mappedMessages.filter(m => !existingIds.has(m.id))
                messagesMap.value['f' + friendId] = [...newMsgs, ...currentMsgs]
            }
            return apiMessages.length
        } catch (error) {
            console.error(`Failed to fetch messages for friend ${friendId}:`, error)
            return 0
        }
    }

    const fetchGroupMessages = async (groupId: number, skip: number = 0, limit: number = INITIAL_MESSAGE_LIMIT) => {
        const { groupApi } = await import('@/api/group')
        try {
            const apiMessages = await groupApi.getGroupMessages(groupId, skip, limit)
            const mappedMessages: Message[] = apiMessages.map(m => ({
                id: m.id,
                role: (m.sender_type === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
                content: m.content,
                createdAt: new Date(m.create_time).getTime(),
                sessionId: m.session_id,
                senderId: m.sender_id,
                senderType: m.sender_type,
                sessionType: m.session_type,
                debateSide: m.debate_side
            }))

            if (skip === 0) {
                messagesMap.value['g' + groupId] = mappedMessages
            } else {
                const currentMsgs = messagesMap.value['g' + groupId] || []
                const existingIds = new Set(currentMsgs.map(m => m.id))
                const newMsgs = mappedMessages.filter(m => !existingIds.has(m.id))
                messagesMap.value['g' + groupId] = [...newMsgs, ...currentMsgs]
            }
            return apiMessages.length
        } catch (error) {
            console.error(`Failed to fetch messages for group ${groupId}:`, error)
            return 0
        }
    }

    const loadMoreMessages = async (friendId: number): Promise<boolean> => {
        if (isLoadingMore.value) return false // Return false when already loading, don't assume there's more

        const currentMsgs = messagesMap.value['f' + friendId] || []
        const skip = currentMsgs.length

        isLoadingMore.value = true
        try {
            const count = await fetchFriendMessages(friendId, skip, INITIAL_MESSAGE_LIMIT)
            return count >= INITIAL_MESSAGE_LIMIT // If we got full page, there might be more
        } finally {
            isLoadingMore.value = false
        }
    }

    const loadMoreGroupMessages = async (groupId: number): Promise<boolean> => {
        if (isLoadingMore.value) return false // Return false when already loading, don't assume there's more

        const currentMsgs = messagesMap.value['g' + groupId] || []
        const skip = currentMsgs.length

        isLoadingMore.value = true
        try {
            const count = await fetchGroupMessages(groupId, skip, INITIAL_MESSAGE_LIMIT)
            return count >= INITIAL_MESSAGE_LIMIT // If we got full page, there might be more
        } finally {
            isLoadingMore.value = false
        }
    }

    const syncLatestMessages = async (friendId: number) => {
        try {
            // Get latest 10 messages to check for updates
            const apiMessages = await ChatAPI.getFriendMessages(friendId, 0, 10)
            const mappedMessages = apiMessages.map(m => ({
                id: m.id,
                role: m.role as 'user' | 'assistant' | 'system',
                content: m.content,
                createdAt: new Date(m.create_time).getTime(),
                sessionId: m.session_id
            }))

            const currentMsgs = messagesMap.value['f' + friendId] || []
            const existingIds = new Set(currentMsgs.map(m => m.id))

            // Helper to check if a message already exists (by ID or by content+timestamp)
            const isDuplicate = (serverMsg: typeof mappedMessages[0]): boolean => {
                // First check by ID
                if (existingIds.has(serverMsg.id)) return true

                // Then check by content + approximate timestamp (within 30 seconds)
                // This handles local messages with temp IDs (Date.now()) vs server IDs
                const TIME_TOLERANCE = 30000 // 30 seconds
                return currentMsgs.some(localMsg =>
                    localMsg.role === serverMsg.role &&
                    localMsg.content === serverMsg.content &&
                    Math.abs(localMsg.createdAt - serverMsg.createdAt) < TIME_TOLERANCE
                )
            }

            // Find messages that are NOT in current list
            const newMsgs = mappedMessages.filter(m => !isDuplicate(m))

            if (newMsgs.length > 0) {
                // Sort new messages by createdAt to ensure correct order
                newMsgs.sort((a, b) => a.createdAt - b.createdAt)
                // Append new messages to the end
                messagesMap.value['f' + friendId] = [...currentMsgs, ...newMsgs]
            }
        } catch (error) {
            console.warn(`Silent sync failed for friend ${friendId}:`, error)
        }
    }

    const clearFriendHistory = async (friendId: number) => {
        isLoading.value = true
        try {
            await ChatAPI.clearFriendMessages(friendId)
            // Clear local state
            messagesMap.value['f' + friendId] = []
            if (currentFriendId.value === friendId) {
                currentSessions.value = []
                currentSessionId.value = null
            }
        } catch (error) {
            console.error(`Failed to clear history for friend ${friendId}:`, error)
            throw error
        } finally {
            isLoading.value = false
        }
    }

    const clearGroupHistory = async (groupId: number) => {
        const { groupApi } = await import('@/api/group')
        isLoading.value = true
        try {
            await groupApi.clearMessages(groupId)
            // 清空本地状态
            messagesMap.value['g' + groupId] = []
        } catch (error) {
            console.error(`Failed to clear history for group ${groupId}:`, error)
            throw error
        } finally {
            isLoading.value = false
        }
    }

    return {
        fetchFriendMessages,
        fetchGroupMessages,
        loadMoreMessages,
        loadMoreGroupMessages,
        syncLatestMessages,
        clearFriendHistory,
        clearGroupHistory
    }
}
