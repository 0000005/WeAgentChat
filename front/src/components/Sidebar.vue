<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import { storeToRefs } from 'pinia'
import {
  Search,
  Pin,
  MoreVertical,
  Trash2,
  UserPlus,
  Pencil,
  LayoutGrid,
  Sparkles,
} from 'lucide-vue-next'
// FriendComposeDialog is now managed globally in App.vue


import { getStaticUrl } from '@/api/base'
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
import AssistantWizard from './AssistantWizard.vue'

const emit = defineEmits<{
  (e: 'open-gallery'): void
  (e: 'add-friend'): void
  (e: 'edit-friend', id: number): void
}>()


const sessionStore = useSessionStore()
const friendStore = useFriendStore()
const { currentFriendId, unreadCounts } = storeToRefs(sessionStore)
const { friends, isLoading: friendsLoading } = storeToRefs(friendStore)

const searchQuery = ref('')

// Get friend's last message preview
const getLastMessagePreview = (friend: any): string => {
  if (friend.last_message) {
    const prefix = friend.last_message_role === 'user' ? '[我]' : ''
    // Limit length to 30 characters
    const content = friend.last_message.length > 30
      ? friend.last_message.substring(0, 30) + '...'
      : friend.last_message
    return `${prefix}${content}`
  }
  return friend.description || '点击开始聊天...'
}

// Get friend's last active time
const getLastActiveTime = (friend: any): string => {
  const timeStr = friend.last_message_time || friend.update_time
  const date = new Date(timeStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000
  const timestamp = date.getTime()

  if (timestamp >= today) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (timestamp >= yesterday) {
    return '昨天'
  } else {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  }
}

// Get friend's avatar
const getFriendAvatar = (friend: any): string => {
  if (friend.avatar) {
    return getStaticUrl(friend.avatar) || ''
  }
  // Generate a unique avatar based on friend id if no custom avatar
  return `https://api.dicebear.com/7.x/shapes/svg?seed=${friend.id}`
}

const filteredFriends = computed(() => {
  if (!searchQuery.value) return friends.value
  const query = searchQuery.value.toLowerCase()
  return friends.value.filter((f: any) => f.name.toLowerCase().includes(query))
})

const onSelectFriend = (friendId: number) => {
  sessionStore.selectFriend(friendId)
}

const isWizardOpen = ref(false)

const onAddFriend = () => {
  emit('add-friend')
}


// Delete Friend Dialog Logic
const isDeleteFriendOpen = ref(false)
const friendToDelete = ref<number | null>(null)

const openDeleteFriendDialog = (id: number) => {
  friendToDelete.value = id
  isDeleteFriendOpen.value = true
}

const confirmDeleteFriend = async () => {
  if (friendToDelete.value) {
    try {
      await friendStore.deleteFriend(friendToDelete.value)
      // If we deleted the current friend, clear selection
      if (currentFriendId.value === friendToDelete.value) {
        sessionStore.selectFriend(friends.value[0]?.id || 0)
      }
    } catch (e) {
      console.error('Failed to delete friend:', e)
    }
  }
  isDeleteFriendOpen.value = false
  friendToDelete.value = null
}

const openEditFriendDialog = (id: number) => {
  emit('edit-friend', id)
}


// Initialize: select first friend if none selected
onMounted(async () => {
  // Wait for friends to load if not already
  if (friends.value.length === 0) {
    await friendStore.fetchFriends()
  }
  // Select first friend if no friend is selected
  if (currentFriendId.value === null && friends.value.length > 0) {
    sessionStore.selectFriend(friends.value[0].id)
  }
})
</script>

<template>
  <aside class="wechat-sidebar">
    <!-- Search Header -->
    <div class="search-header">
      <div class="search-box">
        <Search :size="14" class="search-icon" />
        <input v-model="searchQuery" type="text" placeholder="搜索" class="search-input" />
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <button class="add-btn" title="新增">
            <UserPlus :size="18" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem @click="onAddFriend" class="cursor-pointer">
            <Pencil class="mr-2 h-4 w-4" />
            手动创建
          </DropdownMenuItem>
          <DropdownMenuItem @click="isWizardOpen = true" class="cursor-pointer">
            <Sparkles class="mr-2 h-4 w-4 text-green-600" />
            自动创建
          </DropdownMenuItem>
          <DropdownMenuItem @click="emit('open-gallery')" class="cursor-pointer">
            <LayoutGrid class="mr-2 h-4 w-4" />
            好友库
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>

    <!-- Friend List -->
    <div class="friend-list">
      <!-- Loading State -->
      <div v-if="friendsLoading" class="loading-state">
        <p>加载中...</p>
      </div>

      <!-- Friend Items -->
      <div v-else v-for="friend in filteredFriends" :key="friend.id" class="friend-item"
        :class="{ active: friend.id === currentFriendId, pinned: !!friend.pinned_at }"
        @click="onSelectFriend(friend.id)">
        <div class="avatar-wrapper relative">
          <div class="friend-avatar">
            <img :src="getFriendAvatar(friend)" :alt="friend.name" />
          </div>
          <div v-if="unreadCounts[friend.id] > 0" class="unread-badge">
            {{ unreadCounts[friend.id] }}
          </div>
        </div>

        <!-- Content -->
        <div class="friend-content">
          <div class="friend-header">
            <div class="friend-name-wrapper">
              <Pin v-if="friend.pinned_at" :size="12" class="pin-icon" />
              <span class="friend-name">{{ friend.name }}</span>
            </div>
            <span class="friend-time">{{ getLastActiveTime(friend) }}</span>
          </div>
          <div class="friend-preview">
            <template v-if="sessionStore.streamingMap[friend.id]">
              <span class="text-emerald-600 font-medium">对方正在输入...</span>
            </template>
            <template v-else>
              {{ getLastMessagePreview(friend) }}
            </template>
          </div>
        </div>

        <!-- Actions (shown on hover) -->
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <button class="friend-actions" @click.stop>
              <MoreVertical :size="14" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem @click.stop="openEditFriendDialog(friend.id)" class="cursor-pointer">
              <Pencil class="mr-2 h-4 w-4" />
              编辑好友
            </DropdownMenuItem>
            <DropdownMenuItem v-if="!friend.is_preset" @click.stop="openDeleteFriendDialog(friend.id)"
              class="text-red-600 focus:text-red-600 cursor-pointer">
              <Trash2 class="mr-2 h-4 w-4" />
              删除好友
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <!-- Empty State -->
      <div v-if="!friendsLoading && filteredFriends.length === 0" class="empty-state">
        <p>暂无好友</p>
        <button class="add-friend-btn" @click="onAddFriend">添加好友</button>
      </div>
    </div>

    <!-- Delete Friend Dialog -->
    <Dialog v-model:open="isDeleteFriendOpen">
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>确认删除</DialogTitle>
          <DialogDescription>
            您确定要删除此好友吗？相关的聊天记录也会被删除。此操作无法撤销。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteFriendOpen = false">取消</Button>
          <Button variant="destructive" @click="confirmDeleteFriend">删除</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>



    <!-- Assistant Wizard -->
    <AssistantWizard v-model:open="isWizardOpen" />
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

.friend-list {
  flex: 1;
  overflow-y: auto;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #888;
  font-size: 13px;
}

.friend-item {
  display: flex;
  align-items: center;
  padding: 12px;
  gap: 10px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.friend-item:hover {
  background: #d9d9d9;
}

.friend-item.pinned {
  background: #f1f1f1;
}

.friend-item.active {
  background: #c9c9c9;
}

.friend-avatar {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: #fff;
}

.friend-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.friend-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.friend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.friend-name-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.pin-icon {
  color: #07c160;
  flex-shrink: 0;
}

.friend-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.friend-time {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
  margin-left: 8px;
}

.friend-preview {
  font-size: 12px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.friend-actions {
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

.friend-item:hover .friend-actions,
.friend-actions[data-state="open"] {
  opacity: 1;
}

.friend-actions:hover {
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

.add-friend-btn {
  padding: 8px 16px;
  background: #07c160;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.add-friend-btn:hover {
  background: #06ad56;
}

.avatar-wrapper {
  position: relative;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.unread-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  background-color: #fa5151;
  color: white;
  font-size: 10px;
  font-weight: bold;
  height: 16px;
  min-width: 16px;
  padding: 0 4px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 1px #fff;
  z-index: 10;
}
</style>
