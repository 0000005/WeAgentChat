export interface ToolCall {
    name: string
    args: any
    result?: any
    status: 'calling' | 'completed' | 'error'
    callId?: string
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
}

export interface GroupTypingUser {
    id: number
    name: string
}
