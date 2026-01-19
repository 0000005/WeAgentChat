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
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
    MessageSquare,
    Brain,
    Pin,
    Trash2,
    Pencil,
    ChevronLeft,
    CheckCircle2,
    RefreshCw,
    AlertTriangle,
    Loader2
} from 'lucide-vue-next'
import { getFriendEventGists, updateEventGist, deleteEventGist, type UserEventGist } from '@/api/memory'
import { getStaticUrl } from '@/api/base'

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
const viewState = ref<'menu' | 'sessions' | 'memories'>('menu')

// 记忆相关状态
const memories = ref<UserEventGist[]>([])
const isLoadingMemories = ref(false)
const fetchMemoriesError = ref<string | null>(null)
const memoryActionError = ref<string | null>(null)
const isUpdatingMemory = ref(false)
const isDeletingMemory = ref(false)
const editingMemory = ref<UserEventGist | null>(null)
const editContent = ref('')
const deletingMemory = ref<UserEventGist | null>(null)
const showDeleteConfirm = ref(false)

// 会话删除相关状态
const deletingSessionId = ref<number | null>(null)
const showSessionDeleteConfirm = ref(false)
const isDeletingSession = ref(false)
const sessionActionError = ref<string | null>(null)

// 清空确认状态
const showClearConfirm = ref(false)
const isClearing = ref(false)
const clearError = ref<string | null>(null)

const fetchMemories = async () => {
    if (!sessionStore.currentFriendId) return
    isLoadingMemories.value = true
    fetchMemoriesError.value = null
    memoryActionError.value = null
    try {
        const data = await getFriendEventGists(sessionStore.currentFriendId)
        memories.value = data.gists
    } catch (err: any) {
        fetchMemoriesError.value = err.message || '加载记忆失败'
    } finally {
        isLoadingMemories.value = false
    }
}

const cleanGistContent = (content: string) => {
    return content.trim().replace(/^- /, '')
}

const handleEditMemory = (memory: UserEventGist) => {
    memoryActionError.value = null
    editingMemory.value = memory
    editContent.value = cleanGistContent(memory.gist_data.content)
}

const handleUpdateMemory = async () => {
    if (!editingMemory.value) return
    const content = editContent.value.trim()
    if (!content) {
        memoryActionError.value = '记忆内容不能为空'
        return
    }
    isUpdatingMemory.value = true
    memoryActionError.value = null
    try {
        await updateEventGist(editingMemory.value.id, content)
        const target = memories.value.find(item => item.id === editingMemory.value?.id)
        if (target) {
            target.gist_data.content = content
            target.updated_at = new Date().toISOString()
        }
        editingMemory.value = null
        editContent.value = ''
    } catch (err: any) {
        memoryActionError.value = err.message || '更新失败'
    } finally {
        isUpdatingMemory.value = false
    }
}

const handleCancelEdit = () => {
    editingMemory.value = null
    editContent.value = ''
    memoryActionError.value = null
}

const handleConfirmDelete = (memory: UserEventGist) => {
    memoryActionError.value = null
    deletingMemory.value = memory
    showDeleteConfirm.value = true
}

const handleDeleteMemory = async () => {
    if (!deletingMemory.value) return
    isDeletingMemory.value = true
    memoryActionError.value = null
    try {
        await deleteEventGist(deletingMemory.value.id)
        memories.value = memories.value.filter(item => item.id !== deletingMemory.value?.id)
        showDeleteConfirm.value = false
        deletingMemory.value = null
    } catch (err: any) {
        memoryActionError.value = err.message || '删除失败'
    } finally {
        isDeletingMemory.value = false
    }
}

// 获取当前好友信息
const currentFriend = computed(() => {
    if (!sessionStore.currentFriendId) return null
    return friendStore.getFriend(sessionStore.currentFriendId)
})

const currentFriendAvatar = computed(() => {
    if (!currentFriend.value) return ''
    if (currentFriend.value.avatar) {
        return getStaticUrl(currentFriend.value.avatar) || ''
    }
    // Generate a unique avatar based on friend id if no custom avatar
    return `https://api.dicebear.com/7.x/shapes/svg?seed=${currentFriend.value.id}`
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
    /* {
        id: 'pin',
        label: '顶置聊天',
        icon: Pin,
        action: () => handleMenuClick('pin')
    }, */
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
        if (sessionStore.currentFriendId) {
            sessionStore.fetchFriendSessions(sessionStore.currentFriendId)
        }
    } else if (menuId === 'memories') {
        viewState.value = 'memories'
        fetchMemories()
    } else if (menuId === 'clear') {
        showClearConfirm.value = true
    } else {
        console.log(`Menu clicked: ${menuId}`)
    }
}

const isPinned = computed(() => !!currentFriend.value?.pinned_at)

const handleTogglePin = async (checked: boolean) => {
    if (!sessionStore.currentFriendId) return
    try {
        await friendStore.updateFriend(sessionStore.currentFriendId, {
            pinned_at: checked ? new Date().toISOString() : null
        })
        // Refresh list to show new order
        friendStore.fetchFriends()
    } catch (err: any) {
        console.error('Failed to toggle pin', err)
    }
}

const handleClearHistory = async () => {
    if (!sessionStore.currentFriendId) return

    isClearing.value = true
    clearError.value = null
    try {
        await sessionStore.clearFriendHistory(sessionStore.currentFriendId)
        showClearConfirm.value = false
        handleClose() // 清空后关闭
    } catch (err: any) {
        clearError.value = err.message || '清空失败'
    } finally {
        isClearing.value = false
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



const formatTime = (dateStr?: string) => {
    if (!dateStr) return ''
    // Fix: Backend might return naive UTC string (e.g. from memobase), treat as UTC
    // Only append Z if no timezone info is present (no Z and no offset)
    let dateString = dateStr
    if (!dateString.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(dateString)) {
        dateString += 'Z'
    }
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 86400000 && now.getDate() === date.getDate()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

const handleConfirmDeleteSession = (sessionId: number) => {
    sessionActionError.value = null
    deletingSessionId.value = sessionId
    showSessionDeleteConfirm.value = true
}

const handleExecuteDeleteSession = async () => {
    if (!deletingSessionId.value) return
    isDeletingSession.value = true
    sessionActionError.value = null
    try {
        await sessionStore.deleteSession(deletingSessionId.value)
        showSessionDeleteConfirm.value = false
        deletingSessionId.value = null
    } catch (err: any) {
        sessionActionError.value = err.message || '删除会话失败'
    } finally {
        isDeletingSession.value = false
    }
}
</script>

<template>
    <Sheet :open="open" @update:open="handleClose">
        <SheetContent side="right" class="drawer-content w-[360px] sm:w-[360px] p-0 flex flex-col">
            <!-- Header: 动态切换 -->
            <SheetHeader class="drawer-header" :class="{ 'header-white': viewState !== 'menu' }">
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
                        <SheetTitle class="header-title">
                            {{ viewState === 'sessions' ? '会话列表' : '记忆列表' }}
                        </SheetTitle>
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

                <!-- 置顶聊天开关 -->
                <div class="menu-item flex justify-between items-center">
                    <div class="flex items-center gap-4">
                        <Pin :size="20" class="menu-icon" />
                        <span class="menu-label">顶置聊天</span>
                    </div>
                    <Switch :model-value="isPinned" @update:model-value="handleTogglePin" />
                </div>
            </div>

            <!-- Sessions List View -->
            <div v-else-if="viewState === 'sessions'" class="session-history-list">
                <div v-if="sessionStore.isLoading" class="list-loading">
                    <RefreshCw class="animate-spin mr-2 h-4 w-4 inline" />
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


                    <button v-for="session in sessionStore.currentSessions" :key="session.id" class="session-item group"
                        :class="{ 'active': session.id === sessionStore.currentSessionId }"
                        @click="handleSelectSession(session.id)">
                        <div class="session-item-header justify-end">
                            <div class="flex items-center gap-2">
                                <span class="session-time">{{ formatTime(session.create_time) }}</span>
                                <div class="w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-gray-200 rounded-full"
                                    @click.stop="handleConfirmDeleteSession(session.id)" title="删除会话">
                                    <Trash2 :size="12" class="text-gray-500 hover:text-red-500" />
                                </div>
                            </div>
                        </div>
                        <div class="session-item-content">
                            <p class="session-preview text-ellipsis overflow-hidden whitespace-nowrap">{{
                                session.last_message_preview || '无预览内容' }}</p>
                            <div class="session-meta mt-1 flex items-center gap-2">
                                <span class="msg-count text-xs text-gray-500">{{ session.message_count }} 条消息</span>
                                <span v-if="session.memory_generated === 1"
                                    class="status-tag archived flex items-center gap-1 text-[10px] bg-gray-100 text-gray-500 px-1 rounded">
                                    <CheckCircle2 :size="10" /> 已归档
                                </span>
                                <span v-else-if="session.memory_generated === 2"
                                    class="status-tag error flex items-center gap-1 text-[10px] bg-red-50 text-red-500 px-1 rounded"
                                    :title="session.memory_error || '生成失败'">
                                    <AlertTriangle :size="10" /> 归档异常
                                </span>
                                <span v-else-if="session.memory_generated === 3"
                                    class="status-tag processing flex items-center gap-1 text-[10px] bg-blue-50 text-blue-500 px-1 rounded">
                                    <Loader2 :size="10" class="animate-spin" /> 生成中
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

            <!-- Memories List View -->
            <div v-else-if="viewState === 'memories'" class="memory-history-list">
                <div v-if="isLoadingMemories" class="list-loading">
                    <RefreshCw class="animate-spin mr-2 h-4 w-4 inline" />
                    <span>加载中...</span>
                </div>
                <div v-else-if="fetchMemoriesError" class="list-error">
                    <p>{{ fetchMemoriesError }}</p>
                    <button class="retry-btn" @click="fetchMemories">重试</button>
                </div>
                <div v-else-if="memories.length === 0" class="list-empty">
                    <Brain :size="48" class="empty-icon" />
                    <p>暂无相关记忆</p>
                    <span class="text-xs text-gray-400 mt-2">AI 会根据对话自动整理记忆</span>
                </div>
                <div v-else class="memory-items">
                    <div v-if="memoryActionError" class="list-error memory-action-error">
                        <p>{{ memoryActionError }}</p>
                    </div>
                    <div v-for="memory in memories" :key="memory.id" class="memory-card">
                        <div class="memory-content">
                            {{ cleanGistContent(memory.gist_data.content) }}
                        </div>
                        <div class="memory-footer">
                            <div class="memory-actions">
                                <button class="memory-action-btn" @click="handleEditMemory(memory)">
                                    <Pencil :size="14" />
                                </button>
                                <button class="memory-action-btn memory-action-danger"
                                    @click="handleConfirmDelete(memory)">
                                    <Trash2 :size="14" />
                                </button>
                            </div>
                            <span class="memory-time">{{ formatTime(memory.created_at) }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </SheetContent>
    </Sheet>

    <!-- Clear Confirmation Dialog -->
    <Dialog v-model:open="showClearConfirm">
        <DialogContent class="sm:max-w-[425px]">
            <DialogHeader>
                <div class="flex items-center gap-3 mb-2">
                    <div class="p-2 bg-red-100 rounded-full">
                        <AlertTriangle class="w-6 h-6 text-red-600" />
                    </div>
                    <DialogTitle>确认清空聊天记录？</DialogTitle>
                </div>
                <DialogDescription class="text-gray-600 space-y-2 py-2">
                    <p>这将执行以下操作：</p>
                    <ul class="list-disc list-inside text-sm pl-2">
                        <li>删除与 <b>{{ currentFriendName }}</b> 的所有历史聊天记录</li>
                        <li>自动将当前未归档的对话整理为记忆摘要</li>
                        <li><b>注意：</b>此操作不可撤销，但已生成的“记忆列表”将保留。</li>
                    </ul>
                </DialogDescription>
            </DialogHeader>
            <div v-if="clearError" class="py-2 text-sm text-red-500 font-medium">
                {{ clearError }}
            </div>
            <DialogFooter class="gap-2 sm:gap-0">
                <Button variant="outline" @click="showClearConfirm = false" :disabled="isClearing">取消</Button>
                <Button variant="destructive" @click="handleClearHistory" :disabled="isClearing">
                    <Loader2 v-if="isClearing" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isClearing ? '正在清空...' : '确认清空' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Edit Memory Dialog -->
    <Dialog :open="!!editingMemory" @update:open="handleCancelEdit">
        <DialogContent class="sm:max-w-[460px]">
            <DialogHeader>
                <DialogTitle>编辑记忆点</DialogTitle>
                <DialogDescription class="text-gray-600">
                    修改后会在后台异步重新向量化。
                </DialogDescription>
            </DialogHeader>
            <div class="py-2">
                <textarea v-model="editContent" class="memory-edit-textarea" rows="5" placeholder="请输入记忆内容"></textarea>
            </div>
            <div v-if="memoryActionError" class="text-sm text-red-500 font-medium">
                {{ memoryActionError }}
            </div>
            <DialogFooter class="gap-2 sm:gap-0">
                <Button variant="outline" @click="handleCancelEdit" :disabled="isUpdatingMemory">取消</Button>
                <Button @click="handleUpdateMemory" :disabled="isUpdatingMemory">
                    <Loader2 v-if="isUpdatingMemory" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isUpdatingMemory ? '保存中...' : '保存修改' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Delete Memory Dialog -->
    <Dialog v-model:open="showDeleteConfirm">
        <DialogContent class="sm:max-w-[425px]">
            <DialogHeader>
                <div class="flex items-center gap-3 mb-2">
                    <div class="p-2 bg-red-100 rounded-full">
                        <AlertTriangle class="w-6 h-6 text-red-600" />
                    </div>
                    <DialogTitle>确认删除记忆点？</DialogTitle>
                </div>
                <DialogDescription class="text-gray-600 space-y-2 py-2">
                    <p>删除后将无法恢复该记忆点。</p>
                </DialogDescription>
            </DialogHeader>
            <div v-if="memoryActionError" class="py-2 text-sm text-red-500 font-medium">
                {{ memoryActionError }}
            </div>
            <DialogFooter class="gap-2 sm:gap-0">
                <Button variant="outline" @click="showDeleteConfirm = false; memoryActionError = null"
                    :disabled="isDeletingMemory">取消</Button>
                <Button variant="destructive" @click="handleDeleteMemory" :disabled="isDeletingMemory">
                    <Loader2 v-if="isDeletingMemory" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isDeletingMemory ? '删除中...' : '确认删除' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Delete Session Dialog -->
    <Dialog v-model:open="showSessionDeleteConfirm">
        <DialogContent class="sm:max-w-[425px]">
            <DialogHeader>
                <div class="flex items-center gap-3 mb-2">
                    <div class="p-2 bg-red-100 rounded-full">
                        <AlertTriangle class="w-6 h-6 text-red-600" />
                    </div>
                    <DialogTitle>确认删除会话？</DialogTitle>
                </div>
                <DialogDescription class="text-gray-600 space-y-2 py-2">
                    <p>将删除该条会话记录。</p>
                    <p class="text-xs text-red-500">注意：该操作同时会删除由该会话生成的记忆（如有），且不可恢复。</p>
                </DialogDescription>
            </DialogHeader>
            <div v-if="sessionActionError" class="py-2 text-sm text-red-500 font-medium">
                {{ sessionActionError }}
            </div>
            <DialogFooter class="gap-2 sm:gap-0">
                <Button variant="outline" @click="showSessionDeleteConfirm = false; sessionActionError = null"
                    :disabled="isDeletingSession">取消</Button>
                <Button variant="destructive" @click="handleExecuteDeleteSession" :disabled="isDeletingSession">
                    <Loader2 v-if="isDeletingSession" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isDeletingSession ? '删除中...' : '确认删除' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

<style scoped>
/* 抽屉内容容器 */
:deep([data-radix-vue-dialog-content]) {
    max-width: 360px !important;
    -webkit-app-region: no-drag;
}

/* Header 样式 */
.drawer-content {
    -webkit-app-region: no-drag;
}

.drawer-header {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 20px 16px;
    border-bottom: 1px solid #e5e5e5;
    background: #f5f5f5;
    transition: background 0.3s;
    -webkit-app-region: no-drag;
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
    -webkit-app-region: no-drag;
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
    -webkit-app-region: no-drag;
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
    -webkit-app-region: no-drag;
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
    -webkit-app-region: no-drag;
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

/* Memory List View Styles */
.memory-history-list {
    flex: 1;
    background: #f8f9fa;
    overflow-y: auto;
    padding: 16px;
}

.memory-items {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.memory-card {
    background: #fff;
    border-radius: 8px;
    padding: 14px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    border: 1px solid #f0f0f0;
}

.memory-content {
    font-size: 14px;
    color: #333;
    line-height: 1.6;
    word-break: break-word;
}

.memory-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid #f9f9f9;
    align-items: center;
    gap: 8px;
}

.memory-time {
    font-size: 11px;
    color: #b2b2b2;
}

.memory-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-right: auto;
}

.memory-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 6px;
    border: none;
    background: #f3f4f6;
    color: #666;
    cursor: pointer;
    transition: background 0.15s;
}

.memory-action-btn:hover {
    background: #e9ecef;
}

.memory-action-danger {
    color: #fa5151;
}

.memory-action-error {
    padding: 10px 12px;
    border-radius: 8px;
    background: #fff2f2;
    text-align: left;
}

.memory-edit-textarea {
    width: 100%;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    line-height: 1.6;
    resize: vertical;
    outline: none;
}

.memory-edit-textarea:focus {
    border-color: #07c160;
    box-shadow: 0 0 0 2px rgba(7, 193, 96, 0.12);
}

.menu-item {
    width: 100%;
    -webkit-app-region: no-drag;
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
