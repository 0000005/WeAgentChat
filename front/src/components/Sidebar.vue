<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { storeToRefs } from 'pinia'
import { 
  Search, 
  Plus,
  MoreVertical,
  Trash2,
} from 'lucide-vue-next'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const sessionStore = useSessionStore()
const { sessions, currentSessionId } = storeToRefs(sessionStore)

const searchQuery = ref('')

// Session formatting helpers
const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000
  
  if (timestamp >= today) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (timestamp >= yesterday) {
    return '昨天'
  } else {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  }
}

const getSessionPreview = (session: any): string => {
  // For now, return a placeholder. In real app, this would be the last message.
  return session.lastMessage || '开始新对话...'
}

const getSessionAvatar = (session: any): string => {
  // Generate a unique avatar based on session id
  return `https://api.dicebear.com/7.x/shapes/svg?seed=${session.id}`
}

const filteredSessions = computed(() => {
  if (!searchQuery.value) return sessions.value
  const query = searchQuery.value.toLowerCase()
  return sessions.value.filter(s => s.title.toLowerCase().includes(query))
})

const onSelectSession = (id: number) => {
  sessionStore.selectSession(id)
}

const onNewChat = () => {
  sessionStore.createSession()
}

// Delete Session Dialog Logic
const isDeleteSessionOpen = ref(false)
const sessionToDelete = ref<number | null>(null)

const openDeleteSessionDialog = (id: number) => {
  sessionToDelete.value = id
  isDeleteSessionOpen.value = true
}

const confirmDeleteSession = () => {
  if (sessionToDelete.value) {
    sessionStore.deleteSession(sessionToDelete.value)
  }
  isDeleteSessionOpen.value = false
  sessionToDelete.value = null
}
</script>

<template>
  <aside class="wechat-sidebar">
    <!-- Search Header -->
    <div class="search-header">
      <div class="search-box">
        <Search :size="14" class="search-icon" />
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="搜索" 
          class="search-input"
        />
      </div>
      <button class="add-btn" @click="onNewChat" title="新建对话">
        <Plus :size="18" />
      </button>
    </div>

    <!-- Session List -->
    <div class="session-list">
      <div
        v-for="session in filteredSessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === currentSessionId }"
        @click="onSelectSession(session.id)"
      >
        <!-- Avatar -->
        <div class="session-avatar">
          <img :src="getSessionAvatar(session)" :alt="session.title" />
        </div>

        <!-- Content -->
        <div class="session-content">
          <div class="session-header">
            <span class="session-name">{{ session.title }}</span>
            <span class="session-time">{{ formatTime(session.createdAt) }}</span>
          </div>
          <div class="session-preview">
            {{ getSessionPreview(session) }}
          </div>
        </div>

        <!-- Actions (shown on hover) -->
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <button 
              class="session-actions" 
              @click.stop
            >
              <MoreVertical :size="14" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem 
              @click.stop="openDeleteSessionDialog(session.id)" 
              class="text-red-600 focus:text-red-600 cursor-pointer"
            >
              <Trash2 class="mr-2 h-4 w-4" />
              删除会话
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <!-- Empty State -->
      <div v-if="filteredSessions.length === 0" class="empty-state">
        <p>暂无会话</p>
        <button class="new-chat-btn" @click="onNewChat">开始新对话</button>
      </div>
    </div>

    <!-- Delete Session Dialog -->
    <Dialog v-model:open="isDeleteSessionOpen">
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>确认删除</DialogTitle>
          <DialogDescription>
            您确定要删除此会话吗？此操作无法撤销。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteSessionOpen = false">取消</Button>
          <Button variant="destructive" @click="confirmDeleteSession">删除</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </aside>
</template>

<style scoped>
.wechat-sidebar {
  width: 260px;
  min-width: 260px;
  height: 100%;
  background: #e9e9e9;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #d9d9d9;
}

.search-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #f7f7f7;
}

.search-box {
  flex: 1;
  display: flex;
  align-items: center;
  background: #e7e7e7;
  border-radius: 4px;
  padding: 6px 10px;
}

.search-icon {
  color: #999;
  margin-right: 6px;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #333;
  outline: none;
}

.search-input::placeholder {
  color: #999;
}

.add-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.add-btn:hover {
  background: #ddd;
  color: #333;
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 12px;
  gap: 10px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.session-item:hover {
  background: #d9d9d9;
}

.session-item.active {
  background: #c9c9c9;
}

.session-avatar {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: #fff;
}

.session-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.session-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.session-time {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
  margin-left: 8px;
}

.session-preview {
  font-size: 12px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-actions {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #666;
  transition: all 0.15s;
}

.session-item:hover .session-actions,
.session-actions[data-state="open"] {
  opacity: 1;
}

.session-actions:hover {
  background: #fff;
  color: #333;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #888;
}

.empty-state p {
  margin-bottom: 12px;
  font-size: 13px;
}

.new-chat-btn {
  padding: 8px 16px;
  background: #07c160;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.new-chat-btn:hover {
  background: #06ad56;
}
</style>