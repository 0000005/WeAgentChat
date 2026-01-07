/**
 * Settings API - 系统设置相关接口
 * 对应后端 /api/settings 路由
 */
import { withApiBase } from './base'

// 获取指定分组的所有设置
export async function getSettingsByGroup(groupName: string): Promise<Record<string, any>> {
    const response = await fetch(withApiBase(`/api/settings/${groupName}`))
    if (!response.ok) {
        throw new Error(`Failed to fetch settings for group: ${groupName}`)
    }
    return response.json()
}

// 批量更新指定分组的设置
export async function updateSettingsBulk(groupName: string, settings: Record<string, any>): Promise<void> {
    const response = await fetch(withApiBase(`/api/settings/${groupName}/bulk`), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ settings }),
    })
    if (!response.ok) {
        throw new Error(`Failed to update settings for group: ${groupName}`)
    }
}

// 获取单个设置值
export async function getSetting(groupName: string, key: string): Promise<any> {
    const response = await fetch(withApiBase(`/api/settings/${groupName}/${key}`))
    if (!response.ok) {
        if (response.status === 404) {
            return undefined
        }
        throw new Error(`Failed to fetch setting: ${groupName}.${key}`)
    }
    return response.json()
}

// 更新单个设置
export async function updateSetting(groupName: string, key: string, value: any): Promise<void> {
    const response = await fetch(withApiBase(`/api/settings/${groupName}/${key}`), {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ value }),
    })
    if (!response.ok) {
        throw new Error(`Failed to update setting: ${groupName}.${key}`)
    }
}
