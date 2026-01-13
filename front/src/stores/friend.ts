import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
    type Friend,
    type FriendCreate,
    type FriendUpdate,
    getFriends as apiGetFriends,
    createFriend as apiCreateFriend,
    updateFriend as apiUpdateFriend,
    deleteFriend as apiDeleteFriend
} from '@/api/friend'
import { cloneFriendTemplate as apiCloneFriendTemplate } from '@/api/friend-template'

export const useFriendStore = defineStore('friend', () => {
    const friends = ref<Friend[]>([])
    const isLoading = ref(false)
    const error = ref<string | null>(null)

    const fetchFriends = async () => {
        isLoading.value = true
        error.value = null
        try {
            friends.value = await apiGetFriends()
        } catch (e) {
            console.error('Failed to fetch friends', e)
            error.value = 'Failed to fetch friends'
        } finally {
            isLoading.value = false
        }
    }

    const addFriend = async (friend: FriendCreate) => {
        isLoading.value = true
        try {
            const newFriend = await apiCreateFriend(friend)
            friends.value.push(newFriend)
            return newFriend
        } catch (e) {
            console.error('Failed to create friend', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const updateFriend = async (id: number, updates: FriendUpdate) => {
        isLoading.value = true
        try {
            const updated = await apiUpdateFriend(id, updates)
            const index = friends.value.findIndex(p => p.id === id)
            if (index !== -1) {
                friends.value[index] = updated
            }
            return updated
        } catch (e) {
            console.error('Failed to update friend', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const deleteFriend = async (id: number) => {
        isLoading.value = true
        try {
            await apiDeleteFriend(id)
            const index = friends.value.findIndex(p => p.id === id)
            if (index !== -1) {
                friends.value.splice(index, 1)
            }
        } catch (e) {
            console.error('Failed to delete friend', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const cloneFromTemplate = async (templateId: number) => {
        isLoading.value = true
        try {
            const newFriend = await apiCloneFriendTemplate(templateId)
            friends.value.push(newFriend)
            return newFriend
        } catch (e) {
            console.error('Failed to clone friend from template', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const updateLastMessage = (friendId: number, content: string, role: string, time?: string) => {
        const index = friends.value.findIndex(f => f.id === friendId)
        if (index !== -1) {
            const friend = friends.value[index]
            friend.last_message = content
            friend.last_message_role = role
            friend.last_message_time = time || new Date().toISOString()

            // Re-sort based on pinned status and last message time
            friends.value.sort((a, b) => {
                // Pins first
                if (a.pinned_at && !b.pinned_at) return -1
                if (!a.pinned_at && b.pinned_at) return 1
                if (a.pinned_at && b.pinned_at) {
                    // Both pinned, sort by pinned_at time if available, otherwise by update_time
                    const timeA = new Date(a.pinned_at || a.update_time).getTime()
                    const timeB = new Date(b.pinned_at || b.update_time).getTime()
                    if (timeB !== timeA) return timeB - timeA
                }

                // Then last message time
                const timeA = new Date(a.last_message_time || a.update_time).getTime()
                const timeB = new Date(b.last_message_time || b.update_time).getTime()
                return timeB - timeA
            })
        }
    }

    const getFriend = (id: number) => {
        return friends.value.find(p => p.id === id)
    }

    // Initial fetch
    fetchFriends()

    return {
        friends,
        isLoading,
        error,
        fetchFriends,
        addFriend,
        updateFriend,
        deleteFriend,
        getFriend,
        cloneFromTemplate,
        updateLastMessage
    }
})
