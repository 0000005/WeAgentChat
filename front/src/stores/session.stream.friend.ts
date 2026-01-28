import type { Ref } from 'vue'
import * as ChatAPI from '@/api/chat'
import type { Message, ToolCall } from '@/types/chat'
import { parseMessageSegments } from '@/utils/chat'

type FriendStoreLike = {
    updateLastMessage: (friendId: number, content: string, role: string, time?: string) => void
}

export type FriendStreamDeps = {
    currentFriendId: Ref<number | null>
    currentSessionId: Ref<number | null>
    messagesMap: Ref<Record<string, Message[]>>
    streamingMap: Ref<Record<string, boolean>>
    unreadCounts: Ref<Record<string, number>>
    friendStore: FriendStoreLike
    fetchFriendSessions: (friendId: number) => Promise<void>
}

export const createFriendStreamActions = (deps: FriendStreamDeps) => {
    const {
        currentFriendId,
        currentSessionId,
        messagesMap,
        streamingMap,
        unreadCounts,
        friendStore,
        fetchFriendSessions
    } = deps

    // Send message to current friend
    const sendMessage = async (content: string, enableThinking: boolean = false) => {
        if (!currentFriendId.value) return

        const friendId = currentFriendId.value

        // 1. Add user message locally
        const userMsg: Message = {
            id: -(Date.now() + Math.random()),
            role: 'user',
            content: content,
            createdAt: Date.now()
        }

        if (!messagesMap.value['f' + friendId]) {
            messagesMap.value['f' + friendId] = []
        }
        messagesMap.value['f' + friendId].push(userMsg)

        // Update friend list preview immediately for user message
        friendStore.updateLastMessage(friendId, content, 'user')

        // Buffers for storing incoming data before they are "shown" in UI
        let contentBuffer = ''
        let modelThinkingBuffer = ''
        let recallThinkingBuffer = ''
        let toolCallsBuffer: ToolCall[] = []
        const assistantMsgId = Date.now() + 1
        let capturedSessionId: number | undefined = undefined // Capture session_id from start event
        let capturedAssistantMsgId: number | undefined = undefined // Capture assistant msg id from start event

        try {
            // 如果当前正在查看特定会话，则按会话 ID 发送消息；否则按好友 ID 发送（由后端自动寻址）
            const stream = currentSessionId.value
                ? ChatAPI.sendMessageStream(currentSessionId.value, { content, enable_thinking: enableThinking })
                : ChatAPI.sendMessageToFriendStream(friendId, { content, enable_thinking: enableThinking })

            for await (const { event, data } of stream) {
                if (event === 'start') {
                    // Stream started - mark as streaming immediately
                    streamingMap.value['f' + friendId] = true
                    friendStore.updateLastMessage(friendId, '对方正在输入...', 'assistant')

                    // Capture session_id for later use
                    capturedSessionId = data.session_id
                    capturedAssistantMsgId = data.message_id

                    // Update local user message with real database ID
                    if (data.user_message_id && messagesMap.value['f' + friendId]) {
                        const localUserMsg = messagesMap.value['f' + friendId].find(m => m.id === userMsg.id)
                        if (localUserMsg) {
                            localUserMsg.id = data.user_message_id
                            localUserMsg.sessionId = data.session_id
                        }
                    }
                } else if (event === 'model_thinking' || event === 'thinking') {
                    streamingMap.value['f' + friendId] = true
                    const delta = data.delta || ''
                    modelThinkingBuffer += delta
                } else if (event === 'recall_thinking') {
                    streamingMap.value['f' + friendId] = true
                    const delta = data.delta || ''
                    recallThinkingBuffer += delta
                } else if (event === 'message') {
                    streamingMap.value['f' + friendId] = true
                    const delta = data.delta || ''
                    contentBuffer += delta
                } else if (event === 'tool_call') {
                    streamingMap.value['f' + friendId] = true
                    toolCallsBuffer.push({
                        name: data.tool_name,
                        args: data.arguments,
                        callId: data.call_id,
                        status: 'calling'
                    })
                } else if (event === 'tool_result') {
                    streamingMap.value['f' + friendId] = true
                    const tc = data.call_id
                        ? [...toolCallsBuffer].reverse().find(t => t.callId === data.call_id && t.status === 'calling')
                        : [...toolCallsBuffer].reverse().find(t => t.name === data.tool_name && t.status === 'calling')
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
                        id: capturedAssistantMsgId ?? Date.now() + 2,
                        role: 'assistant',
                        content: errorContent,
                        thinkingContent: modelThinkingBuffer || undefined,
                        recallThinkingContent: recallThinkingBuffer || undefined,
                        toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                        createdAt: Date.now(),
                        sessionId: capturedSessionId
                    }
                    messagesMap.value['f' + friendId].push(errorMsg)

                    streamingMap.value['f' + friendId] = false
                    friendStore.updateLastMessage(friendId, contentBuffer || '[消息发送失败]', 'assistant')

                    // Return early - no need to continue processing
                    return
                } else if (event === 'done') {
                    // Finalize: Push the complete message to the list all at once
                    const assistantMsg: Message = {
                        id: data.message_id || assistantMsgId,
                        role: 'assistant',
                        content: contentBuffer,
                        thinkingContent: modelThinkingBuffer || undefined,
                        recallThinkingContent: recallThinkingBuffer || undefined,
                        toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                        createdAt: Date.now(),
                        sessionId: capturedSessionId // Use captured session_id
                    }
                    messagesMap.value['f' + friendId].push(assistantMsg)

                    streamingMap.value['f' + friendId] = false
                    // Check if user has switched away during streaming - mark as unread
                    // Count segments to match visual perception (3 bubbles = 3 unread)
                    if (currentFriendId.value !== friendId) {
                        const segmentCount = parseMessageSegments(contentBuffer).length || 1
                        unreadCounts.value['f' + friendId] = (unreadCounts.value['f' + friendId] || 0) + segmentCount
                    }

                    // Trigger tray/taskbar flash if window doesn't have focus (Electron only)
                    if (typeof document !== 'undefined' && !document.hasFocus()) {
                        window.WeAgentChat?.notification?.flash()
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
                thinkingContent: modelThinkingBuffer || undefined,
                recallThinkingContent: recallThinkingBuffer || undefined,
                toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                createdAt: Date.now()
            }
            messagesMap.value['f' + friendId].push(errorMsg)
            // Update sidebar preview with partial content or error indicator
            friendStore.updateLastMessage(friendId, contentBuffer || '[消息发送失败]', 'assistant')
        } finally {
            streamingMap.value['f' + friendId] = false
        }
    }

    // Recall a message
    const recallMessage = async (messageId: number) => {
        try {
            await ChatAPI.recallMessage(messageId)

            // Find message locally in current friend's list
            // Note: messagesMap stores all messages for a friend
            if (!currentFriendId.value) return
            const messages = messagesMap.value['f' + currentFriendId.value]
            if (!messages) return

            const index = messages.findIndex(m => m.id === messageId)
            if (index !== -1) {
                // Update the recalled message
                messages[index].content = '你撤回了一条消息'
                messages[index].role = 'system'
                // Clear any other properties if needed

                // If this was the last message, update the sidebar preview
                if (index === messages.length - 1) {
                    friendStore.updateLastMessage(currentFriendId.value, '你撤回了一条消息', 'system')
                }

                // Check if next message is assistant and remove it (cascade delete)
                if (index + 1 < messages.length) {
                    const nextMsg = messages[index + 1]
                    if (nextMsg.role === 'assistant') {
                        // Backend service deletes the FIRST assistant message after the recalled user message
                        // So we remove it here too
                        messages.splice(index + 1, 1)
                        // If we just removed the last message, update preview again
                        if (index === messages.length - 1) {
                            friendStore.updateLastMessage(currentFriendId.value, '你撤回了一条消息', 'system')
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Failed to recall message:', error)
            throw error
        }
    }

    // Regenerate an AI message
    const regenerateMessage = async (message: Message) => {
        if (!currentFriendId.value) return
        if (message.role !== 'assistant') return

        const friendId = currentFriendId.value
        const messages = messagesMap.value['f' + friendId] || []
        const msgIndex = messages.findIndex(m => m.id === message.id)

        // 1. Save backup of old message for recovery on failure
        const oldMessageBackup = msgIndex !== -1 ? { ...messages[msgIndex] } : null

        // 2. Remove the old message locally (optimistic update)
        if (msgIndex !== -1) {
            messages.splice(msgIndex, 1)
        } else {
            console.warn("Could not find message to regenerate in local store")
        }

        // 3. Prepare for streaming
        streamingMap.value['f' + friendId] = true
        friendStore.updateLastMessage(friendId, '对方正在输入...', 'assistant')

        let contentBuffer = ''
        let modelThinkingBuffer = ''
        let recallThinkingBuffer = ''
        let toolCallsBuffer: ToolCall[] = []
        const assistantMsgId = Date.now() + 1

        const sessionId = message.sessionId
        if (!sessionId) {
            console.error("Cannot regenerate message without session ID")
            // Restore old message
            if (oldMessageBackup) {
                messagesMap.value['f' + friendId].push(oldMessageBackup)
            }
            streamingMap.value['f' + friendId] = false
            return
        }

        try {
            const stream = ChatAPI.regenerateMessageStream(sessionId, message.id)

            for await (const { event, data } of stream) {
                if (event === 'start') {
                    streamingMap.value['f' + friendId] = true
                } else if (event === 'model_thinking' || event === 'thinking') {
                    streamingMap.value['f' + friendId] = true
                    modelThinkingBuffer += data.delta || ''
                } else if (event === 'recall_thinking') {
                    streamingMap.value['f' + friendId] = true
                    const delta = data.delta || ''
                    recallThinkingBuffer += delta
                } else if (event === 'message') {
                    streamingMap.value['f' + friendId] = true
                    contentBuffer += data.delta || ''
                } else if (event === 'tool_call') {
                    streamingMap.value['f' + friendId] = true
                    toolCallsBuffer.push({
                        name: data.tool_name,
                        args: data.arguments,
                        callId: data.call_id,
                        status: 'calling'
                    })
                } else if (event === 'tool_result') {
                    streamingMap.value['f' + friendId] = true
                    const tc = data.call_id
                        ? [...toolCallsBuffer].reverse().find(t => t.callId === data.call_id && t.status === 'calling')
                        : [...toolCallsBuffer].reverse().find(t => t.name === data.tool_name && t.status === 'calling')
                    if (tc) {
                        tc.result = data.result
                        tc.status = 'completed'
                    }
                } else if (event === 'error' || event === 'task_error') {
                    // AC-6: Restore old message on error
                    if (oldMessageBackup) {
                        messagesMap.value['f' + friendId].push(oldMessageBackup)
                        friendStore.updateLastMessage(friendId, oldMessageBackup.content, 'assistant')
                    }
                    streamingMap.value['f' + friendId] = false
                    const errorDetail = data.detail || data.message || JSON.stringify(data)
                    throw new Error(errorDetail)
                } else if (event === 'done') {
                    const assistantMsg: Message = {
                        id: data.message_id || assistantMsgId,
                        role: 'assistant',
                        content: contentBuffer,
                        thinkingContent: modelThinkingBuffer || undefined,
                        recallThinkingContent: recallThinkingBuffer || undefined,
                        toolCalls: toolCallsBuffer.length > 0 ? toolCallsBuffer : undefined,
                        createdAt: Date.now(),
                        sessionId: sessionId // Preserve sessionId for future operations
                    }
                    messagesMap.value['f' + friendId].push(assistantMsg)
                    streamingMap.value['f' + friendId] = false
                    if (currentFriendId.value !== friendId) {
                        const segmentCount = parseMessageSegments(contentBuffer).length || 1
                        unreadCounts.value['f' + friendId] = (unreadCounts.value['f' + friendId] || 0) + segmentCount
                    }
                    friendStore.updateLastMessage(friendId, contentBuffer, 'assistant')
                }
            }
        } catch (error) {
            console.error('Failed to regenerate message:', error)
            // AC-6: Restore old message on network/catch error
            if (oldMessageBackup && !messagesMap.value['f' + friendId].some(m => m.id === oldMessageBackup.id)) {
                messagesMap.value['f' + friendId].push(oldMessageBackup)
                friendStore.updateLastMessage(friendId, oldMessageBackup.content, 'assistant')
            }
            streamingMap.value['f' + friendId] = false
            throw error // Re-throw for ChatArea to show toast
        } finally {
            streamingMap.value['f' + friendId] = false
        }
    }

    return {
        sendMessage,
        regenerateMessage,
        recallMessage
    }
}
