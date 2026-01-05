<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from '@/components/ui/sheet'
import {
    MessageSquare,
    Brain,
    Search,
    Pin,
    Trash2,
    ChevronLeft,
    CheckCircle2
} from 'lucide-vue-next'

interface MenuItem {
    id: string
    label: string
    icon: any
    danger?: boolean
    action?: () => void
}

const props = defineProps<{
    open: boolean
}>()

const emit = defineEmits<{
    (e: 'update:open', value: boolean): void
}>()

const sessionStore = useSessionStore()
const friendStore = useFriendStore()

// 视图状态控制
const viewState = ref<'menu' | 'sessions'>('menu')

// 获取当前好友信息
const currentFriend = computed(() => {
    if (!sessionStore.currentFriendId) return null
    return friendStore.getFriend(sessionStore.currentFriendId)
})

const currentFriendAvatar = computed(() => {
    if (!currentFriend.value) return ''
    return `https://api.dicebear.com/7.x/bottts/svg?seed=${currentFriend.value.id}`
})

const currentFriendName = computed(() => {
    return currentFriend.value?.name || '好友'
})

// 菜单项列表
const menuItems = computed<MenuItem[]>(() => [
    {
        id: 'sessions',
        label: '会话列表',
        icon: MessageSquare,
        action: () => handleMenuClick('sessions')
    },
    {
        id: 'memories',
        label: '记忆列表',
        icon: Brain,
        action: () => handleMenuClick('memories')
    },
    {
        id: 'search',
        label: '查找聊天记录',
        icon: Search,
        action: () => handleMenuClick('search')
    },
    {
        id: 'pin',
        label: '顶置聊天',
        icon: Pin,
        action: () => handleMenuClick('pin')
    },
    {
        id: 'clear',
        label: '清空聊天记录',
        icon: Trash2,
        danger: true,
        action: () => handleMenuClick('clear')
    }
])

const handleMenuClick = (menuId: string) => {
    if (menuId === 'sessions') {
        viewState.value = 'sessions'
    } else {
        console.log(`Menu clicked: ${menuId}`)
    }
}

const handleBack = () => {
    viewState.value = 'menu'
}

const handleClose = () => {
    viewState.value = 'menu' // 重置视图
    emit('update:open', false)
}

const handleSelectSession = async (sessionId: number) => {
    await sessionStore.loadSpecificSession(sessionId)
    handleClose() // 选择会话后关闭抽屉
}

const handleSelectAllMessages = async () => {
    await sessionStore.resetToMergedView()
    handleClose()
}

const formatTime = (dateStr?: string) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 86400000 && now.getDate() === date.getDate()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}
</script>

<template>
    <Sheet :open="open" @update:open="handleClose">
        <SheetContent side="right" class="w-[360px] sm:w-[360px] p-0 flex flex-col">
            <!-- Header: 动态切换 -->
            <SheetHeader class="drawer-header" :class="{ 'header-white': viewState === 'sessions' }">
                <template v-if="viewState === 'menu'">
                    <div class="friend-info">
                        <div class="friend-avatar">
                            <img v-if="currentFriendAvatar" :src="currentFriendAvatar" :alt="currentFriendName" />
                        </div>
                        <SheetTitle class="friend-name">{{ currentFriendName }}</SheetTitle>
                    </div>
                </template>
                <template v-else>
                    <div class="header-back">
                        <button class="back-btn" @click="handleBack">
                            <ChevronLeft :size="20" />
                            <span>返回</span>
                        </button>
                        <SheetTitle class="header-title">会话列表</SheetTitle>
                    </div>
                </template>
            </SheetHeader>

            <!-- Main Menu View -->
            <div v-if="viewState === 'menu'" class="menu-list">
                <button v-for="item in menuItems" :key="item.id" class="menu-item"
                    :class="{ 'menu-item-danger': item.danger }" @click="item.action">
                    <component :is="item.icon" :size="20" class="menu-icon" />
                    <span class="menu-label">{{ item.label }}</span>
                </button>
            </div>

            <!-- Sessions List View -->
            <div v-else-if="viewState === 'sessions'" class="session-history-list">
                <div v-if="sessionStore.isLoading" class="list-loading">
                    <span>加载中...</span>
                </div>
                <div v-else-if="sessionStore.fetchError" class="list-error">
                    <p>{{ sessionStore.fetchError }}</p>
                    <button class="retry-btn"
                        @click="sessionStore.fetchFriendSessions(sessionStore.currentFriendId!)">重试</button>
                </div>
                <div v-else-if="sessionStore.currentSessions.length === 0" class="list-empty">
                    <MessageSquare :size="48" class="empty-icon" />
                    <p>暂无历史会话</p>
                </div>
                <template v-else>
                    <!-- 合并视图入口 -->
                    <button class="session-item merged-view-item" :class="{ 'active': !sessionStore.currentSessionId }"
                        @click="handleSelectAllMessages">
                        <div class="session-item-header">
                            <span class="session-title font-bold text-emerald-600">全部聊天记录</span>
                        </div>
                        <div class="session-item-content">
                            <p class="session-preview text-xs">显示与该好友的所有历史对话消息</p>
                        </div>
                    </button>

                    <button v-for="session in sessionStore.currentSessions" :key="session.id" class="session-item"
                        :class="{ 'active': session.id === sessionStore.currentSessionId }"
                        @click="handleSelectSession(session.id)">
                        <div class="session-item-header">
                            <span class="session-title">{{ session.title || '历史对话' }}</span>
                            <span class="session-time">{{ formatTime(session.create_time) }}</span>
                        </div>
                        <div class="session-item-content">
                            <p class="session-preview text-ellipsis overflow-hidden whitespace-nowrap">{{
                                session.last_message_preview || '无预览内容' }}</p>
                            <div class="session-meta mt-1 flex items-center gap-2">
                                <span class="msg-count text-xs text-gray-500">{{ session.message_count }} 条消息</span>
                                <span v-if="session.memory_generated"
                                    class="status-tag archived flex items-center gap-1 text-[10px] bg-gray-100 text-gray-500 px-1 rounded">
                                    <CheckCircle2 :size="10" /> 已归档
                                </span>
                                <span v-else-if="session.is_active"
                                    class="status-tag active text-[10px] bg-emerald-50 text-emerald-600 px-1 rounded">
                                    当前活跃
                                </span>
                            </div>
                        </div>
                    </button>
                </template>
            </div>
        </SheetContent>
    </Sheet>
</template>

<style scoped>
/* 抽屉内容容器 */
:deep([data-radix-vue-dialog-content]) {
    max-width: 360px !important;
}

/* Header 样式 */
.drawer-header {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 20px 16px;
    border-bottom: 1px solid #e5e5e5;
    background: #f5f5f5;
    transition: background 0.3s;
}

.header-white {
    background: #fff;
}

.friend-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
}

.header-back {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
}

.back-btn {
    display: flex;
    align-items: center;
    gap: 2px;
    color: #07c160;
    font-size: 15px;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    margin-right: 8px;
}

.header-title {
    font-size: 16px;
    font-weight: 600;
}

.friend-avatar {
    width: 48px;
    height: 48px;
    border-radius: 6px;
    overflow: hidden;
    background: #e5e5e5;
    flex-shrink: 0;
}

.friend-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.friend-name {
    font-size: 16px;
    font-weight: 500;
    color: #333;
    margin: 0;
}


/* Menu List */
.menu-list {
    flex: 1;
    background: #fff;
    padding: 8px 0;
    overflow-y: auto;
}

/* Session History List */
.session-history-list {
    flex: 1;
    background: #fff;
    overflow-y: auto;
    padding: 0;
}

.session-item {
    width: 100%;
    padding: 12px 16px;
    border: none;
    background: transparent;
    border-bottom: 1px solid #f0f0f0;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s;
}

.session-item:hover {
    background: #f9f9f9;
}

.session-item.active {
    background: #f2f2f2;
}

.session-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.session-title {
    font-size: 14px;
    font-weight: 500;
    color: #333;
}

.session-time {
    font-size: 12px;
    color: #b2b2b2;
}

.session-preview {
    font-size: 13px;
    color: #888;
    line-height: 1.4;
    margin: 0;
}

.list-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding-top: 100px;
    color: #ccc;
}

.empty-icon {
    margin-bottom: 16px;
    opacity: 0.5;
}

.list-loading {
    padding: 20px;
    text-align: center;
    color: #888;
    font-size: 14px;
}

.list-error {
    padding: 40px 20px;
    text-align: center;
}

.list-error p {
    color: #fa5151;
    font-size: 14px;
    margin-bottom: 12px;
}

.retry-btn {
    background: #07c160;
    color: #fff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
}

.retry-btn:hover {
    background: #06ad56;
}

.merged-view-item {
    background: #fbfbfb;
    border-bottom: 2px solid #f0f0f0;
}

.menu-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    border: none;
    background: transparent;
    color: #333;
    cursor: pointer;
    transition: background 0.15s;
    text-align: left;
}

.menu-item:hover {
    background: #f5f5f5;
}

.menu-item:active {
    background: #ececec;
}

.menu-icon {
    flex-shrink: 0;
    color: #666;
}

.menu-label {
    font-size: 15px;
    color: #333;
}

/* 危险操作样式 (清空聊天记录) */
.menu-item-danger .menu-label {
    color: #fa5151;
}

.menu-item-danger .menu-icon {
    color: #fa5151;
}

.menu-item-danger:hover {
    background: #fff5f5;
}

/* 移动端适配 */
@media (max-width: 640px) {
    :deep([data-radix-vue-dialog-content]) {
        max-width: 100% !important;
        width: 100% !important;
    }
}

/* Override default sheet styles */
:deep(.sheet-content) {
    padding: 0 !important;
}
</style>
