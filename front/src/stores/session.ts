import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as ChatAPI from '@/api/chat'
import { useFriendStore } from './friend'

export interface ToolCall {
    name: string
    args: any
    result?: any
    status: 'calling' | 'completed' | 'error'
}

export interface Message {
    id: number
    role: 'user' | 'assistant' | 'system'
    content: string
    thinkingContent?: string
    toolCalls?: ToolCall[]
    createdAt: number
    sessionId?: number
}

/**
 * Parse message content into segments based on <message> tags.
 * If no tags are found, returns original content as a single segment.
 * 
 * Edge cases handled:
 * 1. No tags at all → return original content as single segment
 * 2. Multiple complete <message>...</message> tags → return all segments
 * 3. Trailing unclosed <message>... → include as last segment (for SSE streaming)
 * 4. Empty <message></message> → filter out
 * 5. Malformed/nested tags → extract outermost complete blocks
 */
export function parseMessageSegments(content: string): string[] {
    if (!content) return []

    // Quick path: no tags at all
    if (!content.includes('<message>')) {
        return [content.trim()]
    }

    const regex = /<message>([\s\S]*?)<\/message>/g
    const segments: string[] = []
    let lastIndex = 0
    let match

    while ((match = regex.exec(content)) !== null) {
        const segment = match[1].trim()
        if (segment) {
            segments.push(segment)
        }
        lastIndex = regex.lastIndex
    }

    // Handle trailing unclosed <message> tag (SSE streaming case)
    const remainingContent = content.slice(lastIndex)
    if (remainingContent.includes('<message>')) {
        const openTagIndex = remainingContent.indexOf('<message>')
        const trailingContent = remainingContent.slice(openTagIndex + '<message>'.length).trim()
        if (trailingContent) {
            segments.push(trailingContent)
        }
    }

    // Fallback: if we found <message> tags but extracted nothing, show raw content
    if (segments.length === 0) {
        return [content.trim()]
    }

    return segments
}

export const useSessionStore = defineStore('session', () => {
    const friendStore = useFriendStore()

    // Current selected friend ID (WeChat-style: contact list)
    const currentFriendId = ref<number | null>(null)

    // Unread counts map: friendId -> count
    const unreadCounts = ref<Record<number, number>>({})

    // Messages map: friendId -> Message[]
    const messagesMap = ref<Record<number, Message[]>>({})

    const isLoading = ref(false)
    // Streaming state per friend: friendId -> boolean
    const streamingMap = ref<Record<number, boolean>>({})

    // Current specific session ID (if not null, show only this session's messages)
    const currentSessionId = ref<number | null>(null)
    const currentSessions = ref<ChatAPI.ChatSession[]>([])
    const fetchError = ref<string | null>(null)

    // Get messages for current friend
    const currentMessages = computed(() => {
        if (!currentFriendId.value) return []
        return messagesMap.value[currentFriendId.value] || []
    })

    // Is current friend's chat streaming?
    const isStreaming = computed(() => {
        if (!currentFriendId.value) return false
        return !!streamingMap.value[currentFriendId.value]
    })

    const isLoadingMore = ref(false)
    const INITIAL_MESSAGE_LIMIT = 10 // TODO: Change back to 30 after testing

    // Fetch messages for a specific friend (merged from all sessions)
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
                messagesMap.value[friendId] = mappedMessages
            } else {
                // If skipping, it's pagination - prepend messages
                const currentMsgs = messagesMap.value[friendId] || []
                // Ensure no duplicates
                const existingIds = new Set(currentMsgs.map(m => m.id))
                const newMsgs = mappedMessages.filter(m => !existingIds.has(m.id))
                messagesMap.value[friendId] = [...newMsgs, ...currentMsgs]
            }
            return apiMessages.length
        } catch (error) {
            console.error(`Failed to fetch messages for friend ${friendId}:`, error)
            return 0
        }
    }

    // Load more (older) messages
    const loadMoreMessages = async (friendId: number): Promise<boolean> => {
        if (isLoadingMore.value) return false // Return false when already loading, don't assume there's more

        const currentMsgs = messagesMap.value[friendId] || []
        const skip = currentMsgs.length

        isLoadingMore.value = true
        try {
            const count = await fetchFriendMessages(friendId, skip, INITIAL_MESSAGE_LIMIT)
            return count >= INITIAL_MESSAGE_LIMIT // If we got full page, there might be more
        } finally {
            isLoadingMore.value = false
        }
    }

    // Silent sync latest messages
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

            const currentMsgs = messagesMap.value[friendId] || []
            const existingIds = new Set(currentMsgs.map(m => m.id))

            // Find messages that are NOT in current list
            const newMsgs = mappedMessages.filter(m => !existingIds.has(m.id))

            if (newMsgs.length > 0) {
                // Sort new messages by createdAt to ensure correct order
                newMsgs.sort((a, b) => a.createdAt - b.createdAt)
                // Append new messages to the end
                messagesMap.value[friendId] = [...currentMsgs, ...newMsgs]
            }
        } catch (error) {
            console.warn(`Silent sync failed for friend ${friendId}:`, error)
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

    const selectFriend = async (friendId: number) => {
        currentFriendId.value = friendId
        // Clear unread count when entering chat
        if (unreadCounts.value[friendId]) {
            unreadCounts.value[friendId] = 0
        }
        currentSessionId.value = null // Reset to default merged/latest view

        // Cache hit: render immediately, sync in background
        if (messagesMap.value[friendId]?.length > 0) {
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

        // Update friend list preview immediately for user message
        friendStore.updateLastMessage(friendId, content, 'user')

        // Buffers for storing incoming data before they are "shown" in UI
        let contentBuffer = ''
        let thinkingBuffer = ''
        let toolCallsBuffer: ToolCall[] = []
        const assistantMsgId = Date.now() + 1

        try {
            // 如果当前正在查看特定会话，则按会话 ID 发送消息；否则按好友 ID 发送（由后端自动寻址）
            const stream = currentSessionId.value
                ? ChatAPI.sendMessageStream(currentSessionId.value, { content, enable_thinking: enableThinking })
                : ChatAPI.sendMessageToFriendStream(friendId, { content, enable_thinking: enableThinking })

            for await (const { event, data } of stream) {
                if (event === 'start') {
                    // Stream started - mark as streaming immediately
                    streamingMap.value[friendId] = true
                    friendStore.updateLastMessage(friendId, '对方正在输入...', 'assistant')
                } else if (event === 'thinking') {
                    streamingMap.value[friendId] = true
                    const delta = data.delta || ''
                    thinkingBuffer += delta
                } else if (event === 'message') {
                    streamingMap.value[friendId] = true
                    const delta = data.delta || ''
                    contentBuffer += delta
                } else if (event === 'tool_call') {
                    streamingMap.value[friendId] = true
                    toolCallsBuffer.push({
                        name: data.tool_name,
                        args: data.arguments,
                        status: 'calling'
                    })
                } else if (event === 'tool_result') {
                    streamingMap.value[friendId] = true
                    // Find the last one with the same name that is still 'calling'
                    const tc = [...toolCallsBuffer].reverse().find(t => t.name === data.tool_name && t.status === 'calling')
                    if (tc) {
                        tc.result = data.result
                        tc.status = 'completed'
                    }
                } else if (event === 'error' || event === 'task_error') {
                    // Backend error - immediately show error and reset streaming state
                    const errorDetail = data.detail || data.message || JSON.stringify(data)
                    const errorContent = contentBuffer
                        ? `${contentBuffer}\n\n[错误: ${errorDetail}]`
                        : `[错误: ${errorDetail}]`

                    const errorMsg: Message = {
                        id: Date.now() + 2,
                        role: 'assistant',
                        content: errorContent,
                        thinkingContent: thinkingBuffer || undefined,
                        toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                        createdAt: Date.now()
                    }
                    messagesMap.value[friendId].push(errorMsg)

                    streamingMap.value[friendId] = false
                    friendStore.updateLastMessage(friendId, contentBuffer || '[消息发送失败]', 'assistant')

                    // Return early - no need to continue processing
                    return
                } else if (event === 'done') {
                    // Finalize: Push the complete message to the list all at once
                    const assistantMsg: Message = {
                        id: data.message_id || assistantMsgId,
                        role: 'assistant',
                        content: contentBuffer,
                        thinkingContent: thinkingBuffer,
                        toolCalls: toolCallsBuffer,
                        createdAt: Date.now()
                    }
                    messagesMap.value[friendId].push(assistantMsg)

                    streamingMap.value[friendId] = false

                    // Check if user has switched away during streaming - mark as unread
                    // Count segments to match visual perception (3 bubbles = 3 unread)
                    if (currentFriendId.value !== friendId) {
                        const segmentCount = parseMessageSegments(contentBuffer).length || 1
                        unreadCounts.value[friendId] = (unreadCounts.value[friendId] || 0) + segmentCount
                    }

                    // 异步刷新会话列表统计
                    fetchFriendSessions(friendId)
                    // Update friend list preview for assistant message with final content
                    friendStore.updateLastMessage(friendId, contentBuffer, 'assistant')
                }
            }

        } catch (error) {
            console.error('Failed to send message:', error)
            // If buffer has content, show it with a connection break marker
            // Otherwise show a generic error message
            const finalContent = contentBuffer
                ? `${contentBuffer}\n\n[连接中断]`
                : 'Error: Failed to get response from AI.'
            const errorMsg: Message = {
                id: Date.now() + 2,
                role: 'assistant',
                content: finalContent,
                thinkingContent: thinkingBuffer || undefined,
                toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                createdAt: Date.now()
            }
            messagesMap.value[friendId].push(errorMsg)
            // Update sidebar preview with partial content or error indicator
            friendStore.updateLastMessage(friendId, contentBuffer || '[消息发送失败]', 'assistant')
        } finally {
            streamingMap.value[friendId] = false
        }
    }

    // Clear all chat history for a friend via API
    const clearFriendHistory = async (friendId: number) => {
        isLoading.value = true
        try {
            await ChatAPI.clearFriendMessages(friendId)
            // Clear local state
            messagesMap.value[friendId] = []
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

    // Delete a specific session
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

    return {
        currentFriendId,
        unreadCounts,
        messagesMap,
        streamingMap,
        currentMessages,
        currentSessions,
        currentSessionId,
        fetchError,
        isLoading,
        isLoadingMore,
        INITIAL_MESSAGE_LIMIT,
        isStreaming,
        selectFriend,
        sendMessage,
        fetchFriendMessages,
        loadMoreMessages,
        syncLatestMessages,
        fetchFriendSessions,
        loadSpecificSession,
        resetToMergedView,
        clearFriendHistory,
        deleteSession,
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
