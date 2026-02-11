import { computed } from 'vue'
import type { Ref } from 'vue'
import type { GroupTypingUser, Message, VoicePayload } from '@/types/chat'
import { parseMessageSegments } from '@/utils/chat'

type GroupStoreLike = {
    updateLastMessage: (groupId: number, content: string, senderName: string) => void
    getGroup: (id: number) => {
        members?: { member_id: string; name?: string }[]
        last_message?: string | null
        last_message_sender_name?: string | null
        last_message_time?: string | null
    } | undefined
}

export type GroupStreamDeps = {
    currentGroupId: Ref<number | null>
    chatType: Ref<'friend' | 'group'>
    forceNewNextGroupMessageMap: Ref<Record<string, boolean>>
    messagesMap: Ref<Record<string, Message[]>>
    streamingMap: Ref<Record<string, boolean>>
    unreadCounts: Ref<Record<string, number>>
    groupTypingUsersMap: Ref<Record<string, GroupTypingUser[]>>
    groupStore: GroupStoreLike
}

const normalizeVoicePayload = (raw: any): VoicePayload | undefined => {
    if (!raw || typeof raw !== 'object') return undefined
    const segments = Array.isArray(raw.segments)
        ? raw.segments
            .filter((s: any) => s && typeof s.audio_url === 'string')
            .map((s: any) => ({
                segment_index: Number.isFinite(Number(s.segment_index)) ? Number(s.segment_index) : 0,
                text: typeof s.text === 'string' ? s.text : '',
                audio_url: s.audio_url,
                duration_sec: Number.isFinite(Number(s.duration_sec)) ? Number(s.duration_sec) : 1,
            }))
            .sort((a: { segment_index: number }, b: { segment_index: number }) => a.segment_index - b.segment_index)
        : []
    if (!segments.length) return undefined
    return {
        voice_id: String(raw.voice_id || ''),
        segments,
        generated_at: typeof raw.generated_at === 'string' ? raw.generated_at : undefined,
    }
}

const mergeVoiceSegment = (msg: Message, segment: any) => {
    if (!segment || typeof segment.audio_url !== 'string') return
    const normalized = {
        segment_index: Number.isFinite(Number(segment.segment_index)) ? Number(segment.segment_index) : 0,
        text: typeof segment.text === 'string' ? segment.text : '',
        audio_url: segment.audio_url,
        duration_sec: Number.isFinite(Number(segment.duration_sec)) ? Number(segment.duration_sec) : 1,
    }

    if (!msg.voicePayload) {
        msg.voicePayload = { voice_id: '', segments: [normalized] }
    } else if (!msg.voicePayload.segments.some(s => s.segment_index === normalized.segment_index)) {
        msg.voicePayload.segments.push(normalized)
        msg.voicePayload.segments.sort((a: { segment_index: number }, b: { segment_index: number }) => a.segment_index - b.segment_index)
    }

    if (!msg.voiceUnreadSegmentIndexes) {
        msg.voiceUnreadSegmentIndexes = []
    }
    if (!msg.voiceUnreadSegmentIndexes.includes(normalized.segment_index)) {
        msg.voiceUnreadSegmentIndexes.push(normalized.segment_index)
        msg.voiceUnreadSegmentIndexes.sort((a: number, b: number) => a - b)
    }
}

const applyVoicePayload = (msg: Message, payload: VoicePayload) => {
    msg.voicePayload = payload
    msg.voiceUnreadSegmentIndexes = payload.segments.map((s: { segment_index: number }) => s.segment_index).sort((a: number, b: number) => a - b)
}

export const createGroupStreamActions = (deps: GroupStreamDeps) => {
    const {
        currentGroupId,
        chatType,
        forceNewNextGroupMessageMap,
        messagesMap,
        streamingMap,
        unreadCounts,
        groupTypingUsersMap,
        groupStore
    } = deps

    const groupTypingUsers = computed(() => {
        if (chatType.value !== 'group' || !currentGroupId.value) return []
        return groupTypingUsersMap.value['g' + currentGroupId.value] || []
    })

    const setGroupTypingUsers = (groupId: number, users: GroupTypingUser[]) => {
        groupTypingUsersMap.value = {
            ...groupTypingUsersMap.value,
            ['g' + groupId]: users
        }
    }

    const removeGroupTypingUser = (groupId: number, senderId?: string | number) => {
        if (!senderId) return
        const key = 'g' + groupId
        const current = groupTypingUsersMap.value[key] || []
        const next = current.filter(u => String(u.id) !== String(senderId))
        groupTypingUsersMap.value = {
            ...groupTypingUsersMap.value,
            [key]: next
        }
    }

    const clearGroupTypingUsers = (groupId: number) => {
        setGroupTypingUsers(groupId, [])
    }

    // Send message to current group
    const sendGroupMessage = async (content: string, mentions: string[] = [], enableThinking: boolean = false) => {
        if (!currentGroupId.value) return

        const groupId = currentGroupId.value
        const groupKey = 'g' + groupId
        const existingMessages = messagesMap.value[groupKey] || []
        const lastMessage = existingMessages.length > 0 ? existingMessages[existingMessages.length - 1] : undefined
        const hasManualNewSessionMarker = !!(
            lastMessage &&
            lastMessage.role === 'system' &&
            lastMessage.content === '新会话'
        )
        const forceNewForNextMessage = (
            !!forceNewNextGroupMessageMap.value[groupKey] || hasManualNewSessionMarker
        )
        if (forceNewForNextMessage) {
            forceNewNextGroupMessageMap.value[groupKey] = false
        }
        console.log('[SessionStream] sendGroupMessage routing', {
            groupId,
            forceNewFlag: forceNewForNextMessage,
            marker: hasManualNewSessionMarker
        })

        const prevGroupSnapshot = (() => {
            const g = groupStore.getGroup(groupId)
            if (!g) return null
            return {
                last_message: g.last_message,
                last_message_sender_name: g.last_message_sender_name,
                last_message_time: g.last_message_time
            }
        })()
        const { groupApi } = await import('@/api/group')

        // 1. Add user message locally
        const userMsg: Message = {
            id: -(Date.now() + Math.random()),
            role: 'user',
            content: content,
            createdAt: Date.now(),
            senderId: 'user'
        }

        if (!messagesMap.value['g' + groupId]) {
            messagesMap.value['g' + groupId] = []
        }
        messagesMap.value['g' + groupId].push(userMsg)

        // Update group list preview immediately for user message
        groupStore.updateLastMessage(groupId, content, '我')

        // Map friend IDs to track streaming content for each friend
        const aiMessages: Record<string, Message> = {}
        const pendingVoicePayloadByMessageId = new Map<number, VoicePayload>()

        let capturedSessionId: number | undefined = undefined
        let hasServerAck = false

        try {
            const stream = groupApi.sendGroupMessageStream(
                groupId,
                { content, mentions, enable_thinking: enableThinking },
                { forceNewSession: forceNewForNextMessage }
            )
            streamingMap.value['g' + groupId] = true

            for await (const { event, data } of stream) {
                if (event === 'start') {
                    // Update user message ID
                    if (data.message_id) {
                        const localMsg = messagesMap.value['g' + groupId].find(m => m.id === userMsg.id)
                        if (localMsg) {
                            localMsg.id = data.message_id
                            localMsg.sessionId = data.session_id
                        }
                    }
                    if (data.session_id) {
                        capturedSessionId = data.session_id
                    }
                    hasServerAck = true
                } else if (event === 'meta_participants') {
                    // Story 09-10: Update typing users list (bind by group/session)
                    if (data.group_id && Number(data.group_id) !== groupId) {
                        continue
                    }
                    if (data.session_id) {
                        if (!capturedSessionId) {
                            capturedSessionId = data.session_id
                        } else if (capturedSessionId !== data.session_id) {
                            continue
                        }
                    }
                    if (data.participants && Array.isArray(data.participants)) {
                        setGroupTypingUsers(groupId, data.participants)
                    }
                } else if (event === 'voice_segment') {
                    const senderId = data.sender_id
                    const messageId = Number(data.message_id)
                    const segment = data.segment
                    if (!senderId || !Number.isFinite(messageId) || !segment) continue
                    const target = (messagesMap.value['g' + groupId] || []).find(m => m.id === messageId) || aiMessages[senderId]
                    if (target) {
                        mergeVoiceSegment(target, segment)
                    }
                } else if (event === 'voice_payload') {
                    const senderId = data.sender_id
                    const messageId = Number(data.message_id)
                    const payload = normalizeVoicePayload(data.voice_payload)
                    if (!senderId || !Number.isFinite(messageId) || !payload) continue
                    const target = (messagesMap.value['g' + groupId] || []).find(m => m.id === messageId) || aiMessages[senderId]
                    if (target) {
                        applyVoicePayload(target, payload)
                    } else {
                        pendingVoicePayloadByMessageId.set(messageId, payload)
                    }
                } else if (event === 'message' || event === 'model_thinking' || event === 'thinking' || event === 'recall_thinking' || event === 'tool_call' || event === 'tool_result') {
                    const senderId = data.sender_id
                    if (!senderId) continue

                    // If we haven't seen this AI friend yet in this interaction, create a placeholder
                    if (!aiMessages[senderId]) {
                        const newMsg: Message = {
                            id: -(Date.now() + Math.random()),
                            role: 'assistant',
                            content: '',
                            thinkingContent: '',
                            recallThinkingContent: '',
                            toolCalls: [],
                            createdAt: Date.now(),
                            senderId: senderId,
                            sessionId: capturedSessionId
                        }
                        messagesMap.value['g' + groupId].push(newMsg)
                        // Important: Get the reactive proxy from the messages list to ensure property updates are tracked
                        aiMessages[senderId] = messagesMap.value['g' + groupId][messagesMap.value['g' + groupId].length - 1]
                    }

                    if (event === 'message') {
                        aiMessages[senderId].content += data.delta || ''
                    } else if (event === 'model_thinking' || event === 'thinking') {
                        aiMessages[senderId].thinkingContent = (aiMessages[senderId].thinkingContent || '') + (data.delta || '')
                    } else if (event === 'recall_thinking') {
                        aiMessages[senderId].recallThinkingContent = (aiMessages[senderId].recallThinkingContent || '') + (data.delta || '')
                    } else if (event === 'tool_call') {
                        if (!aiMessages[senderId].toolCalls) aiMessages[senderId].toolCalls = []
                        aiMessages[senderId].toolCalls?.push({
                            name: data.tool_name,
                            args: data.arguments,
                            callId: data.call_id,
                            status: 'calling'
                        })
                    } else if (event === 'tool_result') {
                        const tc = data.call_id
                            ? [...(aiMessages[senderId].toolCalls || [])].reverse().find(t => t.callId === data.call_id && t.status === 'calling')
                            : [...(aiMessages[senderId].toolCalls || [])].reverse().find(t => t.name === data.tool_name && t.status === 'calling')
                        if (tc) {
                            tc.result = data.result
                            tc.status = 'completed'
                        }
                    }

                    // Update sidebar preview for streaming content
                    if (event === 'message') {
                        const senderName = groupStore.getGroup(groupId)?.members?.find(m => m.member_id === senderId)?.name || '...'
                        const currentContent = aiMessages[senderId]?.content || '...'
                        groupStore.updateLastMessage(groupId, currentContent, senderName)
                    }
                } else if (event === 'done') {
                    const senderId = data.sender_id
                    if (data.session_id && capturedSessionId && data.session_id !== capturedSessionId) {
                        continue
                    }
                    if (!capturedSessionId && data.session_id) {
                        capturedSessionId = data.session_id
                    }
                    if (senderId && aiMessages[senderId]) {
                        const finalMessageId = data.message_id
                        aiMessages[senderId].id = finalMessageId
                        if (capturedSessionId) {
                            aiMessages[senderId].sessionId = capturedSessionId
                        }
                        // Use finalized content if provided
                        if (data.content) {
                            aiMessages[senderId].content = data.content
                        }
                        const donePayload = normalizeVoicePayload(data.voice_payload) || pendingVoicePayloadByMessageId.get(finalMessageId)
                        if (donePayload) {
                            applyVoicePayload(aiMessages[senderId], donePayload)
                        }
                        pendingVoicePayloadByMessageId.delete(finalMessageId)
                    }

                    if (senderId) {
                        const finalContent = data.content || aiMessages[senderId]?.content || ''
                        if (finalContent) {
                            const senderName = senderId === 'user'
                                ? '我'
                                : (groupStore.getGroup(groupId)?.members?.find(m => m.member_id === senderId)?.name || '未知')
                            groupStore.updateLastMessage(groupId, finalContent, senderName)
                        }
                    }

                    // If user has switched away during streaming, mark as unread
                    if (currentGroupId.value !== groupId) {
                        const finalContent = data.content || (senderId ? aiMessages[senderId]?.content : '') || ''
                        const segmentCount = parseMessageSegments(finalContent).length || 1
                        unreadCounts.value['g' + groupId] = (unreadCounts.value['g' + groupId] || 0) + segmentCount
                    }

                    // Trigger tray/taskbar flash if window doesn't have focus (Electron only)
                    if (typeof document !== 'undefined' && !document.hasFocus()) {
                        window.WeAgentChat?.notification?.flash()
                    }
                    // Story 09-10: Remove from typing list on done
                    removeGroupTypingUser(groupId, senderId)
                }
                else if (event === 'error') {
                    console.error('Group stream error:', data)
                    // Story 09-10: Remove from typing list on error
                    removeGroupTypingUser(groupId, data.sender_id)
                }
            }
        } catch (error) {
            console.error('Failed to send group message:', error)
            if (!hasServerAck) {
                const group = groupStore.getGroup(groupId)
                if (group && prevGroupSnapshot) {
                    group.last_message = prevGroupSnapshot.last_message
                    group.last_message_sender_name = prevGroupSnapshot.last_message_sender_name
                    group.last_message_time = prevGroupSnapshot.last_message_time
                } else {
                    groupStore.updateLastMessage(groupId, '[消息发送失败]', '我')
                }
            }
        } finally {
            streamingMap.value['g' + groupId] = false
            clearGroupTypingUsers(groupId) // Ensure clean state
        }
    }

    return {
        sendGroupMessage,
        groupTypingUsers,
        groupTypingUsersMap,
        setGroupTypingUsers,
        removeGroupTypingUser,
        clearGroupTypingUsers
    }
}
