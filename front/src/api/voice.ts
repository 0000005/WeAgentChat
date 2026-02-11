import { withApiBase } from './base'

export interface VoiceTimbre {
    id: number
    voice_id: string
    name: string
    description?: string | null
    gender?: string | null
    preview_url?: string | null
    supported_models?: string[]
    category?: string | null
    create_time?: string
}

export interface VoiceTestPayload {
    api_key: string
    model: string
    voice_id: string
    text?: string
    base_url?: string
}

export interface VoiceTestResult {
    success: boolean
    message: string
    model: string
    voice_id: string
    audio_url: string
}

export async function getVoiceTimbres(): Promise<VoiceTimbre[]> {
    const response = await fetch(withApiBase('/api/voice/timbres'))
    if (!response.ok) {
        throw new Error('获取音色列表失败')
    }
    return response.json()
}

export async function testVoiceConfig(payload: VoiceTestPayload): Promise<VoiceTestResult> {
    const response = await fetch(withApiBase('/api/voice/test'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '语音测试失败' }))
        throw new Error(error.detail || '语音测试失败')
    }
    return response.json()
}
