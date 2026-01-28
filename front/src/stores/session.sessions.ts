import type { Ref } from 'vue'
import * as ChatAPI from '@/api/chat'
import type { Message } from '@/types/chat'
import { INITIAL_MESSAGE_LIMIT } from '@/utils/chat'

export type SessionActionsDeps = {
    currentFriendId: Ref<number | null>
    currentGroupId: Ref<number | null>
    chatType: Ref<'friend' | 'group'>
    unreadCounts: Ref<Record<string, number>>
    messagesMap: Ref<Record<string, Message[]>>
    currentSessions: Ref<ChatAPI.ChatSession[]>
    currentSessionId: Ref<number | null>
    fetchError: Ref<string | null>
    isLoading: Ref<boolean>
    fetchFriendMessages: (friendId: number, skip?: number, limit?: number) => Promise<number>
    fetchGroupMessages: (groupId: number, skip?: number, limit?: number) => Promise<number>
    syncLatestMessages: (friendId: number) => Promise<void>
}

export const createSessionActions = (deps: SessionActionsDeps) => {
    const {
        currentFriendId,
        currentGroupId,
        chatType,
        unreadCounts,
        messagesMap,
        currentSessions,
        currentSessionId,
        fetchError,
        isLoading,
        fetchFriendMessages,
        fetchGroupMessages,
        syncLatestMessages
    } = deps

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

    const resetToMergedView = async () => {
        if (!currentFriendId.value) return
        currentSessionId.value = null
        isLoading.value = true
        try {
            await fetchFriendMessages(currentFriendId.value, 0, INITIAL_MESSAGE_LIMIT)
        } finally {
            isLoading.value = false
        }
    }

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
                messagesMap.value['f' + currentFriendId.value] = mappedMessages
            }
        } catch (error) {
            console.error(`Failed to load session ${sessionId}:`, error)
        } finally {
            isLoading.value = false
        }
    }

    const selectFriend = async (friendId: number) => {
        currentFriendId.value = friendId
        currentGroupId.value = null
        chatType.value = 'friend'

        // Clear unread count when entering chat
        if (unreadCounts.value['f' + friendId]) {
            unreadCounts.value['f' + friendId] = 0
        }
        currentSessionId.value = null // Reset to default merged/latest view

        // Cache hit: render immediately, sync in background
        if (messagesMap.value['f' + friendId]?.length > 0) {
            // Background silent sync (don't await)
            syncLatestMessages(friendId).catch(e => console.warn('Silent sync failed:', e))
            fetchFriendSessions(friendId) // Also refresh sessions silently
            return
        }

        // Cache miss: show loading
        isLoading.value = true
        try {
            await Promise.all([
                fetchFriendMessages(friendId, 0, INITIAL_MESSAGE_LIMIT),
                fetchFriendSessions(friendId)
            ])
        } finally {
            isLoading.value = false
        }
    }

    const selectGroup = async (groupId: number) => {
        currentGroupId.value = groupId
        currentFriendId.value = null
        chatType.value = 'group'
        currentSessionId.value = null

        // Clear unread count when entering group chat
        if (unreadCounts.value['g' + groupId]) {
            unreadCounts.value['g' + groupId] = 0
        }

        // Fetch group messages
        isLoading.value = true
        try {
            await fetchGroupMessages(groupId)
        } finally {
            isLoading.value = false
        }
    }

    const deleteSession = async (sessionId: number) => {
        try {
            await ChatAPI.deleteSession(sessionId)
            // Remove from local list
            currentSessions.value = currentSessions.value.filter(s => s.id !== sessionId)
            // If deleting current session, reset
            if (currentSessionId.value === sessionId) {
                currentSessionId.value = null
                // If we were viewing this session, maybe we should go back to merged view or just empty
                // Resetting to merged view seems safer if user is in that mode
                if (currentFriendId.value) {
                    // Optionally fetch messages again or just init
                }
            }
        } catch (error) {
            console.error(`Failed to delete session ${sessionId}:`, error)
            throw error
        }
    }

    const startNewSession = async () => {
        if (!currentFriendId.value) return

        currentSessionId.value = null // 重置为活跃视图

        // Prevent multiple consecutive new sessions
        const messages = messagesMap.value['f' + currentFriendId.value]
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
            if (!messagesMap.value['f' + currentFriendId.value]) {
                messagesMap.value['f' + currentFriendId.value] = []
            }
            messagesMap.value['f' + currentFriendId.value].push({
                id: Date.now(),
                role: 'system',
                content: '新会话',
                createdAt: Date.now()
            })
        } catch (error) {
            console.error('Failed to start new session:', error)
        }
    }

    const startNewGroupSession = async () => {
        if (!currentGroupId.value) return

        const groupId = currentGroupId.value
        const { groupApi } = await import('@/api/group')

        // Prevent multiple consecutive new sessions
        const messages = messagesMap.value['g' + groupId]
        if (messages && messages.length > 0) {
            const lastMsg = messages[messages.length - 1]
            if (lastMsg.role === 'system' && lastMsg.content === '新会话') {
                return
            }
        }

        try {
            await groupApi.createGroupSession(groupId)
            if (!messagesMap.value['g' + groupId]) {
                messagesMap.value['g' + groupId] = []
            }
            messagesMap.value['g' + groupId].push({
                id: Date.now(),
                role: 'system',
                content: '新会话',
                createdAt: Date.now()
            })
        } catch (error) {
            console.error('Failed to start new group session:', error)
        }
    }

    return {
        fetchFriendSessions,
        loadSpecificSession,
        resetToMergedView,
        deleteSession,
        startNewSession,
        startNewGroupSession,
        selectFriend,
        selectGroup
    }
}
