<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import { storeToRefs } from 'pinia'
import { 
  Search, 
  Plus,
  MoreVertical,
  Trash2,
  UserPlus,
  Pencil,
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
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

const sessionStore = useSessionStore()
const friendStore = useFriendStore()
const { currentFriendId } = storeToRefs(sessionStore)
const { friends, isLoading: friendsLoading } = storeToRefs(friendStore)

const searchQuery = ref('')

// Get friend's last message preview (placeholder for now)
const getLastMessagePreview = (friend: any): string => {
  // In real implementation, this could be cached or fetched
  return '点击开始聊天...'
}

// Get friend's last active time (placeholder for now)
const getLastActiveTime = (friend: any): string => {
  const date = new Date(friend.update_time)
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
  // Generate a unique avatar based on friend id
  return `https://api.dicebear.com/7.x/shapes/svg?seed=${friend.id}`
}

const filteredFriends = computed(() => {
  if (!searchQuery.value) return friends.value
  const query = searchQuery.value.toLowerCase()
  return friends.value.filter(f => f.name.toLowerCase().includes(query))
})

const onSelectFriend = (friendId: number) => {
  sessionStore.selectFriend(friendId)
}

// Add Friend Dialog Logic
const isAddFriendOpen = ref(false)
const isSubmitting = ref(false)
const newFriendForm = ref({
  name: '',
  description: '',
  system_prompt: '',
})

const resetAddFriendForm = () => {
  newFriendForm.value = {
    name: '',
    description: '',
    system_prompt: '',
  }
}

const onAddFriend = () => {
  resetAddFriendForm()
  isAddFriendOpen.value = true
}

const confirmAddFriend = async () => {
  if (!newFriendForm.value.name.trim()) {
    return
  }
  isSubmitting.value = true
  try {
    const createdFriend = await friendStore.addFriend({
      name: newFriendForm.value.name.trim(),
      description: newFriendForm.value.description.trim() || undefined,
      system_prompt: newFriendForm.value.system_prompt.trim() || undefined,
      is_preset: false,
    })
    isAddFriendOpen.value = false
    // Select the newly created friend
    sessionStore.selectFriend(createdFriend.id)
  } catch (e) {
    console.error('Failed to add friend:', e)
  } finally {
    isSubmitting.value = false
  }
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

// Edit Friend Dialog Logic
const isEditFriendOpen = ref(false)
const friendToEdit = ref<number | null>(null)
const editFriendForm = ref({
  name: '',
  description: '',
  system_prompt: '',
})

const openEditFriendDialog = (id: number) => {
  const friend = friendStore.getFriend(id)
  if (friend) {
    friendToEdit.value = id
    editFriendForm.value = {
      name: friend.name,
      description: friend.description || '',
      system_prompt: friend.system_prompt || '',
    }
    isEditFriendOpen.value = true
  }
}

const confirmEditFriend = async () => {
  if (!friendToEdit.value || !editFriendForm.value.name.trim()) {
    return
  }
  isSubmitting.value = true
  try {
    await friendStore.updateFriend(friendToEdit.value, {
      name: editFriendForm.value.name.trim(),
      description: editFriendForm.value.description.trim() || null,
      system_prompt: editFriendForm.value.system_prompt.trim() || null,
    })
    isEditFriendOpen.value = false
    friendToEdit.value = null
  } catch (e) {
    console.error('Failed to update friend:', e)
  } finally {
    isSubmitting.value = false
  }
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
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="搜索" 
          class="search-input"
        />
      </div>
      <button class="add-btn" @click="onAddFriend" title="新增好友">
        <UserPlus :size="18" />
      </button>
    </div>

    <!-- Friend List -->
    <div class="friend-list">
      <!-- Loading State -->
      <div v-if="friendsLoading" class="loading-state">
        <p>加载中...</p>
      </div>

      <!-- Friend Items -->
      <div
        v-else
        v-for="friend in filteredFriends"
        :key="friend.id"
        class="friend-item"
        :class="{ active: friend.id === currentFriendId }"
        @click="onSelectFriend(friend.id)"
      >
        <!-- Avatar -->
        <div class="friend-avatar">
          <img :src="getFriendAvatar(friend)" :alt="friend.name" />
        </div>

        <!-- Content -->
        <div class="friend-content">
          <div class="friend-header">
            <span class="friend-name">{{ friend.name }}</span>
            <span class="friend-time">{{ getLastActiveTime(friend) }}</span>
          </div>
          <div class="friend-preview">
            {{ friend.description || getLastMessagePreview(friend) }}
          </div>
        </div>

        <!-- Actions (shown on hover) -->
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <button 
              class="friend-actions" 
              @click.stop
            >
              <MoreVertical :size="14" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem 
              @click.stop="openEditFriendDialog(friend.id)" 
              class="cursor-pointer"
            >
              <Pencil class="mr-2 h-4 w-4" />
              编辑好友
            </DropdownMenuItem>
            <DropdownMenuItem 
              @click.stop="openDeleteFriendDialog(friend.id)" 
              class="text-red-600 focus:text-red-600 cursor-pointer"
            >
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

    <!-- Add Friend Dialog -->
    <Dialog v-model:open="isAddFriendOpen">
      <DialogContent class="sm:max-w-[500px] add-friend-dialog">
        <DialogHeader>
          <DialogTitle>新增好友</DialogTitle>
          <DialogDescription>
            创建一个新的 AI 好友，设置其名称和人格特征。
          </DialogDescription>
        </DialogHeader>
        
        <div class="dialog-form">
          <div class="form-group">
            <label for="friend-name" class="form-label">好友名称 <span class="required">*</span></label>
            <Input 
              id="friend-name"
              v-model="newFriendForm.name"
              placeholder="请输入好友名称，如：小助手、知心姐姐"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label for="friend-description" class="form-label">好友描述</label>
            <Input 
              id="friend-description"
              v-model="newFriendForm.description"
              placeholder="简短描述这个好友的特点"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label for="friend-system-prompt" class="form-label">系统提示词</label>
            <Textarea 
              id="friend-system-prompt"
              v-model="newFriendForm.system_prompt"
              placeholder="设置这个好友的人格特征和行为准则，例如：你是一个温暖友善的朋友，喜欢倾听和给出建设性意见..."
              class="form-textarea"
              :rows="5"
            />
            <p class="form-hint">系统提示词决定了 AI 好友的人格和回复风格</p>
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" @click="isAddFriendOpen = false" :disabled="isSubmitting">取消</Button>
          <Button 
            @click="confirmAddFriend" 
            :disabled="!newFriendForm.name.trim() || isSubmitting"
            class="add-confirm-btn"
          >
            {{ isSubmitting ? '创建中...' : '创建好友' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Edit Friend Dialog -->
    <Dialog v-model:open="isEditFriendOpen">
      <DialogContent class="sm:max-w-[500px] add-friend-dialog">
        <DialogHeader>
          <DialogTitle>编辑好友</DialogTitle>
          <DialogDescription>
            修改 AI 好友的名称和人格特征。
          </DialogDescription>
        </DialogHeader>
        
        <div class="dialog-form">
          <div class="form-group">
            <label for="edit-friend-name" class="form-label">好友名称 <span class="required">*</span></label>
            <Input 
              id="edit-friend-name"
              v-model="editFriendForm.name"
              placeholder="请输入好友名称"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label for="edit-friend-description" class="form-label">好友描述</label>
            <Input 
              id="edit-friend-description"
              v-model="editFriendForm.description"
              placeholder="简短描述这个好友的特点"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label for="edit-friend-system-prompt" class="form-label">系统提示词</label>
            <Textarea 
              id="edit-friend-system-prompt"
              v-model="editFriendForm.system_prompt"
              placeholder="设置这个好友的人格特征和行为准则..."
              class="form-textarea"
              :rows="5"
            />
            <p class="form-hint">系统提示词决定了 AI 好友的人格和回复风格</p>
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" @click="isEditFriendOpen = false" :disabled="isSubmitting">取消</Button>
          <Button 
            @click="confirmEditFriend" 
            :disabled="!editFriendForm.name.trim() || isSubmitting"
            class="add-confirm-btn"
          >
            {{ isSubmitting ? '保存中...' : '保存修改' }}
          </Button>
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

.friend-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
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

/* Add Friend Dialog Styles */
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-label .required {
  color: #dc2626;
}

.form-input {
  font-size: 14px;
}

.form-textarea {
  font-size: 14px;
  resize: none;
  min-height: 100px;
}

.form-hint {
  font-size: 12px;
  color: #888;
  margin: 0;
}

.add-confirm-btn {
  background: #07c160;
}

.add-confirm-btn:hover:not(:disabled) {
  background: #06ad56;
}

.add-confirm-btn:disabled {
  background: #a0a0a0;
  cursor: not-allowed;
}
</style>