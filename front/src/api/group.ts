import { withApiBase } from './base';

export interface GroupMember {
    id: number;
    group_id: number;
    member_id: string;
    member_type: 'user' | 'friend';
    name?: string;
    avatar?: string;
    join_time: string;
}

export interface GroupRead {
    id: number;
    name: string;
    avatar?: string;
    description?: string;
    owner_id: string;
    auto_reply: boolean;
    member_count?: number;
    members?: GroupMember[];
    create_time: string;
    update_time: string;
}

export interface GroupReadWithMembers extends GroupRead {
    members: GroupMember[];
}

export interface GroupCreate {
    name: string;
    member_ids: string[]; // List of persona_ids
    description?: string;
    avatar?: string;
    auto_reply?: boolean;
}

export interface GroupUpdate {
    name?: string;
    description?: string;
    avatar?: string;
    auto_reply?: boolean;
}

export interface GroupMessageRead {
    id: number;
    group_id: number;
    sender_id: string;
    sender_type: 'user' | 'friend';
    content: string;
    message_type: 'text' | 'system' | '@';
    mentions?: string[];
    create_time: string;
}

async function request<T>(options: { url: string; method: string; data?: any; params?: any }): Promise<T> {
    const url = new URL(withApiBase(`/api${options.url}`));
    if (options.params) {
        Object.keys(options.params).forEach((key) => url.searchParams.append(key, options.params[key]));
    }

    const response = await fetch(url.toString(), {
        method: options.method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: options.data ? JSON.stringify(options.data) : undefined,
    });

    if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || `Request failed with status ${response.status}`);
    }

    return response.json();
}

export const groupApi = {
    /**
     * 获取用户加入的所有群组
     */
    getGroups: () => {
        return request<GroupRead[]>({
            url: '/groups',
            method: 'GET',
        });
    },

    /**
     * 创建群组
     */
    createGroup: (data: GroupCreate) => {
        return request<GroupRead>({
            url: '/group/create',
            method: 'POST',
            data,
        });
    },

    /**
     * 获取群详情及成员列表
     */
    getGroup: (id: number) => {
        return request<GroupReadWithMembers>({
            url: `/group/${id}`,
            method: 'GET',
        });
    },

    /**
     * 邀请新成员
     */
    inviteMembers: (groupId: number, memberIds: string[]) => {
        return request<boolean>({
            url: '/group/invite',
            method: 'POST',
            data: {
                group_id: groupId,
                member_ids: memberIds,
            },
        });
    },

    /**
     * 更新群设置
     */
    updateSettings: (groupId: number, settings: GroupUpdate) => {
        return request<GroupRead>({
            url: '/group/settings',
            method: 'PATCH',
            data: {
                group_id: groupId,
                group_in: settings,
            },
        });
    },

    /**
     * 退出群组
     */
    exitGroup: (groupId: number) => {
        return request<boolean>({
            url: '/group/exit',
            method: 'DELETE',
            params: { group_id: groupId },
        });
    },

    /**
     * 移除群成员
     */
    removeMember: (groupId: number, memberId: string) => {
        return request<boolean>({
            url: `/group/${groupId}/member/${memberId}`,
            method: 'DELETE',
        });
    },

    /**
     * 获取群组历史消息
     */
    getGroupMessages: (groupId: number, skip: number = 0, limit: number = 100) => {
        return request<GroupMessageRead[]>({
            url: `/group/${groupId}/messages`,
            method: 'GET',
            params: { skip, limit },
        });
    },

    /**
     * 清空群消息记录
     */
    clearMessages: (groupId: number) => {
        return request<{ message: string }>({
            url: `/chat/group/${groupId}/messages`,
            method: 'DELETE',
        });
    },
    /**
     * 发送群消息并流式获取响应
     */
    async *sendGroupMessageStream(groupId: number, data: { content: string, mentions?: string[], enable_thinking?: boolean }): AsyncGenerator<{ event: string, data: any }> {
        const url = withApiBase(`/api/chat/group/${groupId}/messages`);
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorBody = await response.json().catch(() => ({}));
            throw new Error(errorBody.detail || `Request failed with status ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop() || '';

                for (const part of parts) {
                    const lines = part.split('\n');
                    let eventType = 'message';
                    let dataString = '';

                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ')) {
                            dataString += (dataString ? '\n' : '') + line.slice(6);
                        }
                    }

                    if (dataString) {
                        try {
                            yield {
                                event: eventType,
                                data: JSON.parse(dataString),
                            };
                        } catch (e) {
                            console.error('Failed to parse SSE data', e);
                            yield { event: eventType, data: dataString };
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    },
};
