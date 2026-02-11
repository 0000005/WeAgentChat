export interface ToolCall {
    name: string
    args: any
    result?: any
    status: 'calling' | 'completed' | 'error'
    callId?: string
}

export type SessionType = 'normal' | 'brainstorm' | 'decision' | 'debate'
export type DebateSide = 'affirmative' | 'negative'
export type AutoDriveMode = 'brainstorm' | 'decision' | 'debate'
export type AutoDriveEndAction = 'summary' | 'judge' | 'both'

export interface VoiceSegment {
    segment_index: number
    text: string
    audio_url: string
    duration_sec: number
}

export interface VoicePayload {
    voice_id: string
    segments: VoiceSegment[]
    generated_at?: string
}

export interface AutoDriveConfig {
    mode: AutoDriveMode
    topic: Record<string, any>
    roles: Record<string, any>
    turnLimit: number
    endAction: AutoDriveEndAction
    judgeId?: string | null
    summaryBy?: string | null
}

export interface AutoDriveState {
    runId: number
    groupId: number
    sessionId: number
    mode: AutoDriveMode
    status: string
    phase?: string | null
    currentRound: number
    currentTurn: number
    nextSpeakerId?: string | null
    pauseReason?: string | null
    startedAt: number
    endedAt?: number | null
    topic: Record<string, any>
    roles: Record<string, any>
    turnLimit: number
    endAction: AutoDriveEndAction
    judgeId?: string | null
    summaryBy?: string | null
}

export interface Message {
    id: number
    role: 'user' | 'assistant' | 'system'
    content: string
    thinkingContent?: string
    recallThinkingContent?: string
    toolCalls?: ToolCall[]
    createdAt: number
    sessionId?: number
    senderId?: string
    senderType?: string
    sessionType?: SessionType
    debateSide?: DebateSide
    voicePayload?: VoicePayload
    voiceUnreadSegmentIndexes?: number[]
}

export interface GroupTypingUser {
    id: number
    name: string
}
