<script setup lang="ts">
/**
 * GroupMemberSelector - 群成员选择/移除组件
 * 支持邀请新成员(mode='invite') 和 剔除成员(mode='remove') 两种模式
 */
import { ref, computed, watch } from 'vue'
import { useFriendStore } from '@/stores/friend'
import { Search, User, Check } from 'lucide-vue-next'
import { getStaticUrl } from '@/api/base'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'

interface MemberItem {
  member_id: string
  member_type: 'user' | 'friend'
  name?: string
  avatar?: string
}

const props = defineProps<{
  open: boolean
  mode: 'invite' | 'remove'
  existingMembers: MemberItem[] // 现有群成员列表
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'confirm', memberIds: string[]): void
}>()

const friendStore = useFriendStore()

const isOpen = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const searchQuery = ref('')
const selectedIds = ref<string[]>([])
const isSubmitting = ref(false)

// 获取已存在成员的ID集合
const existingMemberIds = computed(() => 
  new Set(props.existingMembers.map(m => m.member_id))
)

// 邀请模式: 显示不在群里的好友
// 移除模式: 显示群里的成员 (不包括用户自己)
const availableItems = computed(() => {
  if (props.mode === 'invite') {
    // 过滤掉已在群里的好友
    return friendStore.friends
      .filter(f => !existingMemberIds.value.has(String(f.id)))
      .map(f => ({
        id: String(f.id),
        name: f.name,
        avatar: f.avatar
      }))
  } else {
    // 移除模式：显示群成员 (排除 user 类型)
    return props.existingMembers
      .filter(m => m.member_type === 'friend')
      .map(m => {
        // 尝试从 friendStore 获取更多信息
        const friend = friendStore.friends.find(f => String(f.id) === m.member_id)
        return {
          id: m.member_id,
          name: friend?.name || m.name || '未知成员',
          avatar: friend?.avatar || m.avatar
        }
      })
  }
})

const filteredItems = computed(() => {
  if (!searchQuery.value) return availableItems.value
  const query = searchQuery.value.toLowerCase()
  return availableItems.value.filter(item => 
    item.name?.toLowerCase().includes(query)
  )
})

const toggleSelection = (id: string) => {
  const index = selectedIds.value.indexOf(id)
  if (index === -1) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value.splice(index, 1)
  }
}

const getAvatarUrl = (avatar?: string) => {
  if (avatar) return getStaticUrl(avatar)
  return ''
}

const handleConfirm = () => {
  if (selectedIds.value.length === 0) return
  isSubmitting.value = true
  emit('confirm', [...selectedIds.value])
  // 关闭由父组件控制
}

watch(() => props.open, (val) => {
  if (val) {
    searchQuery.value = ''
    selectedIds.value = []
    isSubmitting.value = false
    if (friendStore.friends.length === 0) {
      friendStore.fetchFriends()
    }
  }
})

const dialogTitle = computed(() => 
  props.mode === 'invite' ? '邀请新成员' : '移除群成员'
)

const confirmText = computed(() => 
  props.mode === 'invite' ? '邀请' : '移除'
)
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[420px] p-0 overflow-hidden">
      <DialogHeader class="p-4 border-b">
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
      </DialogHeader>

      <div class="flex flex-col h-[400px]">
        <!-- Search -->
        <div class="p-3 border-b">
          <div class="relative">
            <Search class="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
            <Input
              v-model="searchQuery"
              placeholder="搜索"
              class="pl-9 h-9 bg-gray-50 border-gray-200"
            />
          </div>
        </div>

        <!-- List -->
        <ScrollArea class="flex-1">
          <div v-if="filteredItems.length === 0" class="flex flex-col items-center justify-center h-32 text-gray-400">
            <p class="text-sm">{{ mode === 'invite' ? '没有可邀请的好友' : '没有可移除的成员' }}</p>
          </div>
          <div v-else class="px-2 py-2">
            <div
              v-for="item in filteredItems"
              :key="item.id"
              class="flex items-center gap-3 p-2.5 rounded-md hover:bg-gray-50 cursor-pointer transition-colors"
              @click="toggleSelection(item.id)"
            >
              <!-- Checkbox -->
              <div class="relative flex items-center justify-center w-5 h-5">
                <div 
                  class="w-4 h-4 border rounded-sm flex items-center justify-center transition-colors"
                  :class="selectedIds.includes(item.id) 
                    ? (mode === 'remove' ? 'bg-red-500 border-red-500' : 'bg-[#07c160] border-[#07c160]') 
                    : 'border-gray-300'"
                >
                  <Check v-if="selectedIds.includes(item.id)" :size="12" class="text-white" />
                </div>
              </div>
              
              <!-- Avatar -->
              <div class="w-9 h-9 rounded bg-gray-200 overflow-hidden flex-shrink-0">
                <img v-if="item.avatar" :src="getAvatarUrl(item.avatar)" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
                  <User :size="20" />
                </div>
              </div>
              
              <!-- Name -->
              <span class="text-sm font-medium text-gray-700 flex-1 truncate">{{ item.name }}</span>
            </div>
          </div>
        </ScrollArea>

        <!-- Selected Count -->
        <div v-if="selectedIds.length > 0" class="px-4 py-2 border-t bg-gray-50 text-xs text-gray-500">
          已选择 {{ selectedIds.length }} 人
        </div>
      </div>

      <DialogFooter class="p-4 border-t bg-gray-50">
        <Button variant="outline" @click="isOpen = false">取消</Button>
        <Button 
          @click="handleConfirm" 
          :disabled="selectedIds.length === 0 || isSubmitting"
          :class="mode === 'remove' ? 'bg-red-500 hover:bg-red-600' : 'bg-[#07c160] hover:bg-[#06ad56]'"
          class="text-white px-6"
        >
          {{ isSubmitting ? '处理中...' : `${confirmText} (${selectedIds.length})` }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
