import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useFriendStore } from './friend'
import { useGroupStore } from './group'
import { createSessionFetch } from './session.fetch'
import { createSessionActions } from './session.sessions'
import { createFriendStreamActions } from './session.stream.friend'
import { createGroupStreamActions } from './session.stream.group'
import { createGroupAutoDriveStreamActions } from './session.stream.group.auto_drive'
import type { ChatSession } from '@/api/chat'
import type { Message, GroupTypingUser, AutoDriveState } from '@/types/chat'
import { INITIAL_MESSAGE_LIMIT } from '@/utils/chat'

export const useSessionStore = defineStore('session', () => {
    const friendStore = useFriendStore()
    const groupStore = useGroupStore()

    // Current selected friend ID (WeChat-style: contact list)
    const currentFriendId = ref<number | null>(null)
    const currentGroupId = ref<number | null>(null)
    const chatType = ref<'friend' | 'group'>('friend')

    // Unread counts map: 'f' + friendId or 'g' + groupId -> count
    const unreadCounts = ref<Record<string, number>>({})

    // Messages map: 'f' + friendId or 'g' + groupId -> Message[]
    const messagesMap = ref<Record<string, Message[]>>({})

    const isLoading = ref(false)
    // Streaming state per friend/group: 'f' + friendId or 'g' + groupId -> boolean
    const streamingMap = ref<Record<string, boolean>>({})

    // Current specific session ID (if not null, show only this session's messages)
    const currentSessionId = ref<number | null>(null)
    const currentSessions = ref<ChatSession[]>([])
    const fetchError = ref<string | null>(null)

    // Story 09-10: Group typing users list (per group)
    const groupTypingUsersMap = ref<Record<string, GroupTypingUser[]>>({})

    const autoDriveStateMap = ref<Record<string, AutoDriveState | null>>({})
    const autoDriveStreamingMap = ref<Record<string, boolean>>({})
    const autoDriveConnectionMap = ref<Record<string, 'connected' | 'disconnected'>>({})
    const autoDriveErrorMap = ref<Record<string, string | null>>({})
    // Get messages for current friend or group
    const currentMessages = computed(() => {
        if (chatType.value === 'group') {
            if (!currentGroupId.value) return []
            return messagesMap.value['g' + currentGroupId.value] || []
        }
        if (!currentFriendId.value) return []
        return messagesMap.value['f' + currentFriendId.value] || []
    })

    // Is current friend or group chat streaming?
    const isStreaming = computed(() => {
        if (chatType.value === 'group') {
            return !!currentGroupId.value && !!streamingMap.value['g' + currentGroupId.value]
        }
        if (!currentFriendId.value) return false
        return !!streamingMap.value['f' + currentFriendId.value]
    })

    const isLoadingMore = ref(false)

    const sessionFetch = createSessionFetch({
        messagesMap,
        isLoading,
        isLoadingMore,
        currentFriendId,
        currentSessions,
        currentSessionId
    })
    const {
        fetchFriendMessages,
        fetchGroupMessages,
        loadMoreMessages,
        syncLatestMessages,
        clearFriendHistory,
        clearGroupHistory
    } = sessionFetch

    const sessionActions = createSessionActions({
        currentFriendId,
        currentGroupId,
        chatType,
        unreadCounts,
        messagesMap,
        currentSessions,
        currentSessionId,
        fetchError,
        isLoading,
        fetchFriendMessages,
        fetchGroupMessages,
        syncLatestMessages
    })
    const {
        fetchFriendSessions,
        loadSpecificSession,
        resetToMergedView,
        deleteSession,
        startNewSession,
        startNewGroupSession,
        selectFriend,
        selectGroup
    } = sessionActions
    const friendStreamActions = createFriendStreamActions({
        currentFriendId,
        currentSessionId,
        messagesMap,
        streamingMap,
        unreadCounts,
        friendStore,
        fetchFriendSessions
    })
    const { sendMessage, regenerateMessage, recallMessage } = friendStreamActions

    const groupStreamActions = createGroupStreamActions({
        currentGroupId,
        chatType,
        messagesMap,
        streamingMap,
        unreadCounts,
        groupTypingUsersMap,
        groupStore
    })
    const {
        sendGroupMessage,
        groupTypingUsers,
        groupTypingUsersMap: groupTypingUsersMapRef,
        setGroupTypingUsers,
        removeGroupTypingUser,
        clearGroupTypingUsers
    } = groupStreamActions

    const autoDriveStreamActions = createGroupAutoDriveStreamActions({
        currentGroupId,
        messagesMap,
        unreadCounts,
        autoDriveStateMap,
        autoDriveStreamingMap,
        autoDriveConnectionMap,
        autoDriveErrorMap,
        groupStore
    })

    const {
        startAutoDrive,
        pauseAutoDrive,
        resumeAutoDrive,
        stopAutoDrive,
        fetchAutoDriveState,
        sendAutoDriveInterject,
        ensureAutoDriveStream,
        disconnectAutoDriveStream,
        clearAutoDriveError
    } = autoDriveStreamActions

    const currentAutoDriveState = computed(() => {
        if (!currentGroupId.value) return null
        return autoDriveStateMap.value['g' + currentGroupId.value] || null
    })

    const autoDriveConnectionStatus = computed(() => {
        if (!currentGroupId.value) return 'connected'
        return autoDriveConnectionMap.value['g' + currentGroupId.value] || 'connected'
    })

    const autoDriveStreaming = computed(() => {
        if (!currentGroupId.value) return false
        return !!autoDriveStreamingMap.value['g' + currentGroupId.value]
    })

    const selectGroupWithAutoDrive = async (groupId: number) => {
        await selectGroup(groupId)
        await fetchAutoDriveState(groupId)
    }

    return {
        currentFriendId,
        unreadCounts,
        messagesMap,
        streamingMap,
        groupTypingUsers,
        groupTypingUsersMap: groupTypingUsersMapRef,
        setGroupTypingUsers,
        removeGroupTypingUser,
        clearGroupTypingUsers,
        autoDriveStateMap,
        autoDriveStreamingMap,
        autoDriveConnectionMap,
        autoDriveErrorMap,
        currentAutoDriveState,
        autoDriveConnectionStatus,
        autoDriveStreaming,
        currentMessages,
        currentSessions,
        currentSessionId,
        fetchError,
        isLoading,
        isLoadingMore,
        INITIAL_MESSAGE_LIMIT,
        isStreaming,
        chatType,
        currentGroupId,
        selectFriend,
        selectGroup: selectGroupWithAutoDrive,
        sendMessage,
        sendGroupMessage,
        startAutoDrive,
        pauseAutoDrive,
        resumeAutoDrive,
        stopAutoDrive,
        fetchAutoDriveState,
        sendAutoDriveInterject,
        ensureAutoDriveStream,
        disconnectAutoDriveStream,
        clearAutoDriveError,
        fetchFriendMessages,
        fetchGroupMessages,
        loadMoreMessages,
        syncLatestMessages,
        fetchFriendSessions,
        loadSpecificSession,
        resetToMergedView,
        clearFriendHistory,
        recallMessage,
        regenerateMessage,
        deleteSession,
        startNewSession,
        startNewGroupSession,
        clearGroupHistory
    }
})
