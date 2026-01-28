import { defineStore } from 'pinia';
import { ref } from 'vue';
import { groupApi, type GroupRead, type GroupCreate, type GroupUpdate } from '@/api/group';

export const useGroupStore = defineStore('group', () => {
    const groups = ref<GroupRead[]>([]);
    const isLoading = ref(false);
    const error = ref<string | null>(null);

    const fetchGroups = async () => {
        isLoading.value = true;
        error.value = null;
        try {
            groups.value = await groupApi.getGroups();
        } catch (e) {
            console.error('Failed to fetch groups', e);
            error.value = 'Failed to fetch groups';
        } finally {
            isLoading.value = false;
        }
    };

    const createGroup = async (group: GroupCreate) => {
        isLoading.value = true;
        try {
            const newGroup = await groupApi.createGroup(group);
            groups.value.push(newGroup);
            return newGroup;
        } catch (e) {
            console.error('Failed to create group', e);
            throw e;
        } finally {
            isLoading.value = false;
        }
    };

    const updateGroupSettings = async (groupId: number, updates: GroupUpdate) => {
        isLoading.value = true;
        try {
            const updated = await groupApi.updateSettings(groupId, updates);
            const index = groups.value.findIndex((g) => g.id === groupId);
            if (index !== -1) {
                groups.value[index] = updated;
            }
            return updated;
        } catch (e) {
            console.error('Failed to update group settings', e);
            throw e;
        } finally {
            isLoading.value = false;
        }
    };

    const exitGroup = async (groupId: number) => {
        isLoading.value = true;
        try {
            await groupApi.exitGroup(groupId);
            const index = groups.value.findIndex((g) => g.id === groupId);
            if (index !== -1) {
                groups.value.splice(index, 1);
            }
        } catch (e) {
            console.error('Failed to exit group', e);
            throw e;
        } finally {
            isLoading.value = false;
        }
    };

    const getGroup = (id: number) => {
        return groups.value.find((g) => g.id === id);
    };

    const fetchGroupDetails = async (id: number) => {
        try {
            const data = await groupApi.getGroup(id);
            // Update local state
            const index = groups.value.findIndex((g) => g.id === id);
            if (index !== -1) {
                groups.value[index] = { ...groups.value[index], ...data };
            }
            return data;
        } catch (e) {
            console.error(`Failed to fetch group details for ${id}`, e);
            throw e;
        }
    };

    const inviteMembers = async (groupId: number, memberIds: string[]) => {
        try {
            await groupApi.inviteMembers(groupId, memberIds);
            await fetchGroupDetails(groupId);
        } catch (e) {
            console.error('Failed to invite members', e);
            throw e;
        }
    };

    const removeMember = async (groupId: number, memberId: string) => {
        try {
            await groupApi.removeMember(groupId, memberId);
            await fetchGroupDetails(groupId);
        } catch (e) {
            console.error('Failed to remove member', e);
            throw e;
        }
    };

    const updateLastMessage = (groupId: number, content: string, senderName: string) => {
        const group = groups.value.find((g) => g.id === groupId);
        if (group) {
            group.last_message = content;
            group.last_message_sender_name = senderName;
            group.last_message_time = new Date().toISOString();
        }
    };

    return {
        groups,
        isLoading,
        error,
        fetchGroups,
        createGroup,
        updateGroupSettings,
        exitGroup,
        getGroup,
        fetchGroupDetails,
        inviteMembers,
        removeMember,
        updateLastMessage,
    };
});
