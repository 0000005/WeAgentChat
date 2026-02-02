import { withApiBase } from './base'

export type AutoDriveMode = 'brainstorm' | 'decision' | 'debate'
export type AutoDriveEndAction = 'summary' | 'judge' | 'both'

export interface AutoDriveConfigPayload {
    mode: AutoDriveMode
    topic: Record<string, any>
    roles: Record<string, any>
    turn_limit: number
    end_action: AutoDriveEndAction
    judge_id?: string | null
    summary_by?: string | null
}

export interface AutoDriveStartRequest {
    group_id: number
    config: AutoDriveConfigPayload
    enable_thinking?: boolean
}

export interface AutoDriveActionRequest {
    group_id: number
}

export interface AutoDriveStateRead {
    run_id: number
    group_id: number
    session_id: number
    mode: AutoDriveMode
    status: string
    phase?: string | null
    current_round: number
    current_turn: number
    next_speaker_id?: string | null
    pause_reason?: string | null
    started_at: string
    ended_at?: string | null
    topic: Record<string, any>
    roles: Record<string, any>
    turn_limit: number
    end_action: AutoDriveEndAction
    judge_id?: string | null
    summary_by?: string | null
}

export interface AutoDriveInterjectRequest {
    group_id: number
    content: string
    mentions?: string[]
}

async function request<T>(options: { url: string; method: string; data?: any; params?: any }): Promise<T> {
    const url = new URL(withApiBase(`/api${options.url}`))
    if (options.params) {
        Object.keys(options.params).forEach((key) => url.searchParams.append(key, options.params[key]))
    }

    const response = await fetch(url.toString(), {
        method: options.method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: options.data ? JSON.stringify(options.data) : undefined,
    })

    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}))
        throw new Error(errorBody.detail || `Request failed with status ${response.status}`)
    }

    if (response.status === 204) {
        return null as T
    }
    return response.json()
}

export const groupAutoDriveApi = {
    start: (payload: AutoDriveStartRequest) => {
        return request<AutoDriveStateRead>({
            url: '/group/auto-drive/start',
            method: 'POST',
            data: payload,
        })
    },

    pause: (payload: AutoDriveActionRequest) => {
        return request<AutoDriveStateRead>({
            url: '/group/auto-drive/pause',
            method: 'POST',
            data: payload,
        })
    },

    resume: (payload: AutoDriveActionRequest) => {
        return request<AutoDriveStateRead>({
            url: '/group/auto-drive/resume',
            method: 'POST',
            data: payload,
        })
    },

    stop: (payload: AutoDriveActionRequest) => {
        return request<AutoDriveStateRead>({
            url: '/group/auto-drive/stop',
            method: 'POST',
            data: payload,
        })
    },

    getState: (groupId: number) => {
        return request<AutoDriveStateRead | null>({
            url: '/group/auto-drive/state',
            method: 'GET',
            params: { group_id: groupId },
        })
    },

    interject: (payload: AutoDriveInterjectRequest) => {
        return request<any>({
            url: '/group/auto-drive/interject',
            method: 'POST',
            data: payload,
        })
    },

    async *stream(groupId: number, signal?: AbortSignal): AsyncGenerator<{ event: string; data: any }> {
        const url = withApiBase(`/api/group/auto-drive/stream?group_id=${groupId}`)
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            signal,
        })

        if (!response.ok) {
            const errorBody = await response.json().catch(() => ({}))
            throw new Error(errorBody.detail || `Request failed with status ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) return

        const decoder = new TextDecoder()
        let buffer = ''

        try {
            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const parts = buffer.split('\n\n')
                buffer = parts.pop() || ''

                for (const part of parts) {
                    const lines = part.split('\n')
                    let eventType = 'message'
                    let dataString = ''

                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim()
                        } else if (line.startsWith('data: ')) {
                            dataString += (dataString ? '\n' : '') + line.slice(6)
                        }
                    }

                    if (dataString) {
                        try {
                            yield {
                                event: eventType,
                                data: JSON.parse(dataString),
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data', e)
                            yield { event: eventType, data: dataString }
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock()
        }
    },
}
