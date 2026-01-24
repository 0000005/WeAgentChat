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
};
