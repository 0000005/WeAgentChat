import type { Ref } from 'vue'
import type { AutoDriveConfig, AutoDriveState, Message } from '@/types/chat'
import { groupAutoDriveApi, type AutoDriveConfigPayload, type AutoDriveStateRead } from '@/api/group-auto-drive'
import { groupApi } from '@/api/group'

const buildGroupKey = (groupId: number) => `g${groupId}`

type GroupStoreLike = {
    updateLastMessage: (groupId: number, content: string, senderName: string) => void
    getGroup: (id: number) => {
        members?: { member_id: string; name?: string; member_type?: 'user' | 'friend' }[]
    } | undefined
}

export type GroupAutoDriveStreamDeps = {
    currentGroupId: Ref<number | null>
    messagesMap: Ref<Record<string, Message[]>>
    unreadCounts: Ref<Record<string, number>>
    autoDriveStateMap: Ref<Record<string, AutoDriveState | null>>
    autoDriveStreamingMap: Ref<Record<string, boolean>>
    autoDriveConnectionMap: Ref<Record<string, 'connected' | 'disconnected'>>
    autoDriveErrorMap: Ref<Record<string, string | null>>
    groupStore: GroupStoreLike
}

const isActiveStatus = (status?: string | null) => status === 'running' || status === 'paused' || status === 'pausing'

const toAutoDriveState = (raw: AutoDriveStateRead): AutoDriveState => {
    return {
        runId: raw.run_id,
        groupId: raw.group_id,
        sessionId: raw.session_id,
        mode: raw.mode,
        status: raw.status,
        phase: raw.phase ?? null,
        currentRound: raw.current_round,
        currentTurn: raw.current_turn,
        nextSpeakerId: raw.next_speaker_id ?? null,
        pauseReason: raw.pause_reason ?? null,
        startedAt: new Date(raw.started_at).getTime(),
        endedAt: raw.ended_at ? new Date(raw.ended_at).getTime() : null,
        topic: raw.topic || {},
        roles: raw.roles || {},
        turnLimit: raw.turn_limit,
        endAction: raw.end_action,
        judgeId: raw.judge_id ?? null,
        summaryBy: raw.summary_by ?? null,
    }
}

const mapGroupMessageToMessage = (m: {
    id: number
    content: string
    sender_id: string
    sender_type: 'user' | 'friend'
    session_id: number
    create_time: string
    session_type?: 'normal' | 'brainstorm' | 'decision' | 'debate'
    debate_side?: 'affirmative' | 'negative'
}) => {
    return {
        id: m.id,
        role: (m.sender_type === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
        content: m.content,
        createdAt: new Date(m.create_time).getTime(),
        sessionId: m.session_id,
        senderId: m.sender_id,
        senderType: m.sender_type,
        sessionType: m.session_type,
        debateSide: m.debate_side,
    } as Message
}

const toPayloadConfig = (config: AutoDriveConfig): AutoDriveConfigPayload => {
    return {
        mode: config.mode,
        topic: config.topic,
        roles: config.roles,
        turn_limit: config.turnLimit,
        end_action: config.endAction,
        judge_id: config.judgeId ?? null,
        summary_by: config.summaryBy ?? null,
    }
}

export const createGroupAutoDriveStreamActions = (deps: GroupAutoDriveStreamDeps) => {
    const {
        currentGroupId,
        messagesMap,
        unreadCounts,
        autoDriveStateMap,
        autoDriveStreamingMap,
        autoDriveConnectionMap,
        autoDriveErrorMap,
        groupStore,
    } = deps

    const activeStreams = new Map<number, AbortController>()

    const setConnectionStatus = (groupId: number, status: 'connected' | 'disconnected') => {
        autoDriveConnectionMap.value = {
            ...autoDriveConnectionMap.value,
            [buildGroupKey(groupId)]: status,
        }
    }

    const setAutoDriveState = (groupId: number, state: AutoDriveState | null) => {
        autoDriveStateMap.value = {
            ...autoDriveStateMap.value,
            [buildGroupKey(groupId)]: state,
        }
    }

    const setAutoDriveError = (groupId: number, message: string | null) => {
        autoDriveErrorMap.value = {
            ...autoDriveErrorMap.value,
            [buildGroupKey(groupId)]: message,
        }
    }

    const clearAutoDriveError = (groupId: number) => {
        if (!autoDriveErrorMap.value[buildGroupKey(groupId)]) return
        autoDriveErrorMap.value = {
            ...autoDriveErrorMap.value,
            [buildGroupKey(groupId)]: null,
        }
    }

    const ensureMessagesList = (groupId: number) => {
        const key = buildGroupKey(groupId)
        if (!messagesMap.value[key]) {
            messagesMap.value[key] = []
        }
        return messagesMap.value[key]
    }

    const upsertMessage = (groupId: number, msg: Message) => {
        const messages = ensureMessagesList(groupId)
        const existing = messages.find(m => m.id === msg.id)
        if (existing) {
            Object.assign(existing, msg)
            return
        }
        const insertIndex = messages.findIndex(m => m.createdAt > msg.createdAt)
        if (insertIndex === -1) {
            messages.push(msg)
        } else {
            messages.splice(insertIndex, 0, msg)
        }
    }

    const resolveSenderName = (groupId: number, senderId: string) => {
        const group = groupStore.getGroup(groupId)
        const member = group?.members?.find(m => m.member_id === senderId)
        if (member?.member_type === 'user') return '我'
        return member?.name || 'AI'
    }

    const resolveDebateSide = (groupId: number, senderId: string) => {
        const state = autoDriveStateMap.value[buildGroupKey(groupId)]
        if (!state || state.mode !== 'debate') return undefined
        const roles = state.roles || {}
        if (Array.isArray(roles.affirmative) && roles.affirmative.includes(senderId)) return 'affirmative'
        if (Array.isArray(roles.negative) && roles.negative.includes(senderId)) return 'negative'
        return undefined
    }

    const startAutoDrive = async (groupId: number, config: AutoDriveConfig, enableThinking: boolean = false) => {
        const payload = toPayloadConfig(config)
        const state = await groupAutoDriveApi.start({
            group_id: groupId,
            config: payload,
            enable_thinking: enableThinking,
        })
        setAutoDriveState(groupId, toAutoDriveState(state))
        setConnectionStatus(groupId, 'connected')
        ensureAutoDriveStream(groupId)
        return state
    }

    const pauseAutoDrive = async (groupId: number) => {
        const state = await groupAutoDriveApi.pause({ group_id: groupId })
        setAutoDriveState(groupId, toAutoDriveState(state))
        return state
    }

    const resumeAutoDrive = async (groupId: number) => {
        const state = await groupAutoDriveApi.resume({ group_id: groupId })
        setAutoDriveState(groupId, toAutoDriveState(state))
        ensureAutoDriveStream(groupId)
        return state
    }

    const stopAutoDrive = async (groupId: number) => {
        const state = await groupAutoDriveApi.stop({ group_id: groupId })
        setAutoDriveState(groupId, toAutoDriveState(state))
        return state
    }

    const fetchAutoDriveState = async (groupId: number) => {
        try {
            const state = await groupAutoDriveApi.getState(groupId)
            if (!state) {
                setAutoDriveState(groupId, null)
                return null
            }
            const mapped = toAutoDriveState(state)
            setAutoDriveState(groupId, mapped)
            if (isActiveStatus(mapped.status)) {
                ensureAutoDriveStream(groupId)
            }
            return mapped
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            if (message.includes('No active auto-drive') || message.includes('404')) {
                setAutoDriveState(groupId, null)
                return null
            }
            setAutoDriveError(groupId, message)
            return null
        }
    }

    const sendAutoDriveInterject = async (groupId: number, content: string, mentions: string[] = []) => {
        const messages = ensureMessagesList(groupId)
        const state = autoDriveStateMap.value[buildGroupKey(groupId)]
        const userMsg: Message = {
            id: -(Date.now() + Math.random()),
            role: 'user',
            content,
            createdAt: Date.now(),
            senderId: 'user',
            sessionId: state?.sessionId,
            sessionType: state?.mode,
        }
        messages.push(userMsg)
        groupStore.updateLastMessage(groupId, content, '我')

        await groupAutoDriveApi.interject({
            group_id: groupId,
            content,
            mentions,
        })
    }

    const disconnectAutoDriveStream = (groupId: number) => {
        const controller = activeStreams.get(groupId)
        if (controller) {
            controller.abort()
            activeStreams.delete(groupId)
        }
        autoDriveStreamingMap.value = {
            ...autoDriveStreamingMap.value,
            [buildGroupKey(groupId)]: false,
        }
    }

    const ensureAutoDriveStream = (groupId: number) => {
        if (activeStreams.has(groupId)) return

        const controller = new AbortController()
        activeStreams.set(groupId, controller)
        autoDriveStreamingMap.value = {
            ...autoDriveStreamingMap.value,
            [buildGroupKey(groupId)]: true,
        }
        setConnectionStatus(groupId, 'connected')

        consumeAutoDriveStream(groupId, controller).catch((error) => {
            if (controller.signal.aborted) return
            const message = error instanceof Error ? error.message : String(error)
            console.error('Auto-drive stream error:', message)
            setAutoDriveError(groupId, message)
            setConnectionStatus(groupId, 'disconnected')
        })
    }

    const consumeAutoDriveStream = async (groupId: number, controller: AbortController) => {
        const aiMessages: Record<string, Message> = {}
        const hostFetchPending = new Set<number>()
        let currentSessionId: number | undefined
        let currentMode: AutoDriveState['mode'] | undefined

        const existingState = autoDriveStateMap.value[buildGroupKey(groupId)]
        if (existingState) {
            currentSessionId = existingState.sessionId
            currentMode = existingState.mode
        }

        const hydrateHostMessage = async (messageId: number) => {
            if (hostFetchPending.has(messageId)) return
            hostFetchPending.add(messageId)
            try {
                for (let attempt = 0; attempt < 3; attempt += 1) {
                    const recent = await groupApi.getGroupMessages(groupId, 0, 20)
                    const found = recent.find(item => item.id === messageId)
                    if (found) {
                        const mapped = mapGroupMessageToMessage(found)
                        upsertMessage(groupId, mapped)
                        if (mapped.content) {
                            groupStore.updateLastMessage(groupId, mapped.content, '我')
                        }
                        return
                    }
                    await new Promise(resolve => setTimeout(resolve, 200))
                }
            } catch (error) {
                console.warn('Failed to hydrate host message:', error)
            } finally {
                hostFetchPending.delete(messageId)
            }
        }

        try {
            for await (const { event, data } of groupAutoDriveApi.stream(groupId, controller.signal)) {
                if (event === 'auto_drive_state') {
                    const state = toAutoDriveState(data as AutoDriveStateRead)
                    currentSessionId = state.sessionId
                    currentMode = state.mode
                    setAutoDriveState(groupId, state)
                    setConnectionStatus(groupId, 'connected')
                    continue
                }

                if (event === 'auto_drive_error') {
                    const detail = (data && (data.detail || data.message)) || '自驱运行中断'
                    setAutoDriveError(groupId, String(detail))
                    continue
                }

                if (event === 'auto_drive_done') {
                    setAutoDriveState(groupId, null)
                    continue
                }

                if (event === 'start') {
                    if (data?.session_id) {
                        currentSessionId = data.session_id
                    }
                    const messageId = data?.message_id
                    if (messageId) {
                        const placeholder: Message = {
                            id: messageId,
                            role: 'user',
                            content: '',
                            createdAt: Date.now(),
                            senderId: 'user',
                            senderType: 'user',
                            sessionId: currentSessionId,
                            sessionType: currentMode,
                        }
                        upsertMessage(groupId, placeholder)
                        void hydrateHostMessage(messageId)
                    }
                    continue
                }

                if (
                    event === 'message' ||
                    event === 'model_thinking' ||
                    event === 'thinking' ||
                    event === 'recall_thinking' ||
                    event === 'tool_call' ||
                    event === 'tool_result'
                ) {
                    const senderId = data?.sender_id
                    const messageId = data?.message_id
                    if (!senderId || !messageId) continue

                    if (!aiMessages[messageId]) {
                        const messages = ensureMessagesList(groupId)
                        const newMsg: Message = {
                            id: messageId,
                            role: 'assistant',
                            content: '',
                            thinkingContent: '',
                            recallThinkingContent: '',
                            toolCalls: [],
                            createdAt: Date.now(),
                            senderId: senderId,
                            sessionId: currentSessionId,
                            sessionType: currentMode,
                            debateSide: resolveDebateSide(groupId, senderId),
                        }
                        messages.push(newMsg)
                        aiMessages[messageId] = messages[messages.length - 1]
                    }

                    if (event === 'message') {
                        aiMessages[messageId].content += data.delta || ''
                    } else if (event === 'model_thinking' || event === 'thinking') {
                        aiMessages[messageId].thinkingContent = (aiMessages[messageId].thinkingContent || '') + (data.delta || '')
                    } else if (event === 'recall_thinking') {
                        aiMessages[messageId].recallThinkingContent = (aiMessages[messageId].recallThinkingContent || '') + (data.delta || '')
                    } else if (event === 'tool_call') {
                        if (!aiMessages[messageId].toolCalls) aiMessages[messageId].toolCalls = []
                        aiMessages[messageId].toolCalls?.push({
                            name: data.tool_name,
                            args: data.arguments,
                            callId: data.call_id,
                            status: 'calling',
                        })
                    } else if (event === 'tool_result') {
                        const tc = data.call_id
                            ? [...(aiMessages[messageId].toolCalls || [])].reverse().find(t => t.callId === data.call_id && t.status === 'calling')
                            : [...(aiMessages[messageId].toolCalls || [])].reverse().find(t => t.name === data.tool_name && t.status === 'calling')
                        if (tc) {
                            tc.result = data.result
                            tc.status = 'completed'
                        }
                    }

                    if (event === 'message') {
                        const senderName = resolveSenderName(groupId, senderId)
                        const currentContent = aiMessages[messageId]?.content || '...'
                        groupStore.updateLastMessage(groupId, currentContent, senderName)
                    }

                    continue
                }

                if (event === 'done') {
                    const senderId = data?.sender_id
                    const messageId = data?.message_id
                    if (messageId && aiMessages[messageId]) {
                        if (currentSessionId) {
                            aiMessages[messageId].sessionId = currentSessionId
                        }
                        if (data?.content) {
                            aiMessages[messageId].content = data.content
                        }
                    }

                    if (senderId) {
                        const finalContent = data?.content || (messageId ? aiMessages[messageId]?.content : '') || ''
                        if (finalContent) {
                            const senderName = resolveSenderName(groupId, senderId)
                            groupStore.updateLastMessage(groupId, finalContent, senderName)
                        }
                    }

                    if (currentGroupId.value !== groupId) {
                        unreadCounts.value[buildGroupKey(groupId)] = (unreadCounts.value[buildGroupKey(groupId)] || 0) + 1
                    }

                    if (typeof document !== 'undefined' && !document.hasFocus()) {
                        window.WeAgentChat?.notification?.flash()
                    }
                }
            }
        } finally {
            autoDriveStreamingMap.value = {
                ...autoDriveStreamingMap.value,
                [buildGroupKey(groupId)]: false,
            }
            if (activeStreams.get(groupId) === controller) {
                activeStreams.delete(groupId)
            }
        }
    }

    return {
        startAutoDrive,
        pauseAutoDrive,
        resumeAutoDrive,
        stopAutoDrive,
        fetchAutoDriveState,
        sendAutoDriveInterject,
        ensureAutoDriveStream,
        disconnectAutoDriveStream,
        clearAutoDriveError,
    }
}
