<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useFriendStore } from '@/stores/friend'
import { useGroupStore } from '@/stores/group'
import { Search, X, User } from 'lucide-vue-next'
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

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'success', group: any): void
}>()

const friendStore = useFriendStore()
const groupStore = useGroupStore()

const isOpen = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const searchQuery = ref('')
const groupName = ref('')
const selectedFriendIds = ref<number[]>([])
const isSubmitting = ref(false)

const filteredFriends = computed(() => {
  const allFriends = friendStore.friends
  if (!searchQuery.value) return allFriends
  const query = searchQuery.value.toLowerCase()
  return allFriends.filter(f => f.name.toLowerCase().includes(query))
})

const selectedFriends = computed(() => {
  return friendStore.friends.filter(f => selectedFriendIds.value.includes(f.id))
})

const toggleFriendSelection = (id: number) => {
  const index = selectedFriendIds.value.indexOf(id)
  if (index === -1) {
    selectedFriendIds.value.push(id)
  } else {
    selectedFriendIds.value.splice(index, 1)
  }
}

const removeSelectedFriend = (id: number) => {
  const index = selectedFriendIds.value.indexOf(id)
  if (index !== -1) {
    selectedFriendIds.value.splice(index, 1)
  }
}

const getAvatarUrl = (avatar?: string) => {
  if (avatar) return getStaticUrl(avatar)
  return ''
}

const handleConfirm = async () => {
  if (selectedFriendIds.value.length < 2) return

  isSubmitting.value = true
  try {
    // 转换为 string id
    const memberIds = selectedFriends.value.map(f => String(f.id))
    
    // 如果没有输入群名，自动生成一个
    const finalGroupName = groupName.value.trim() || 
      selectedFriends.value.slice(0, 3).map(f => f.name).join('、') + (selectedFriends.value.length > 3 ? '...' : '') + '的群聊'

    const group = await groupStore.createGroup({
      name: finalGroupName,
      member_ids: memberIds,
    })

    emit('success', group)
    isOpen.value = false
    
    // TODO: 选择该群组并进入聊天
    // sessionStore.selectGroup(group.id)
  } catch (e) {
    console.error('Failed to create group:', e)
  } finally {
    isSubmitting.value = false
  }
}

watch(() => props.open, (val) => {
  if (val) {
    searchQuery.value = ''
    groupName.value = ''
    selectedFriendIds.value = []
    if (friendStore.friends.length === 0) {
      friendStore.fetchFriends()
    }
  }
})
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[700px] p-0 overflow-hidden group-selector-dialog">
      <DialogHeader class="p-4 border-b">
        <DialogTitle>发起群聊</DialogTitle>
      </DialogHeader>

      <div class="flex h-[450px]">
        <!-- Left: Search & Select List -->
        <div class="flex-1 flex flex-col border-r bg-white">
          <div class="p-3">
            <div class="relative">
              <Search class="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
              <Input
                v-model="searchQuery"
                placeholder="搜索好友"
                class="pl-9 h-9 bg-gray-100 border-none focus-visible:ring-1 focus-visible:ring-gray-200"
              />
            </div>
          </div>
          
          <ScrollArea class="flex-1">
            <div class="px-2 pb-2">
              <div
                v-for="friend in filteredFriends"
                :key="friend.id"
                class="flex items-center gap-3 p-2 rounded-md hover:bg-gray-100 cursor-pointer transition-colors"
                @click="toggleFriendSelection(friend.id)"
              >
                <div class="relative flex items-center justify-center w-5 h-5">
                  <div 
                    class="w-4 h-4 border rounded-sm flex items-center justify-center transition-colors"
                    :class="selectedFriendIds.includes(friend.id) ? 'bg-[#07c160] border-[#07c160]' : 'border-gray-300'"
                  >
                    <div v-if="selectedFriendIds.includes(friend.id)" class="w-2 h-1 border-l-2 border-b-2 border-white -rotate-45 mb-0.5"></div>
                  </div>
                </div>
                <div class="w-9 h-9 rounded bg-gray-200 overflow-hidden">
                  <img v-if="friend.avatar" :src="getAvatarUrl(friend.avatar)" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
                    <User :size="20" />
                  </div>
                </div>
                <span class="text-sm font-medium text-gray-700">{{ friend.name }}</span>
              </div>
            </div>
          </ScrollArea>
        </div>

        <!-- Right: Selected List -->
        <div class="w-[240px] flex flex-col bg-[#f5f5f5]">
          <div class="p-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
            已选择成员 ({{ selectedFriendIds.length }})
          </div>
          
          <ScrollArea class="flex-1">
            <div class="px-3 pb-3 space-y-2">
              <div
                v-for="friend in selectedFriends"
                :key="friend.id"
                class="flex items-center justify-between group bg-white p-2 rounded border border-gray-100 shadow-sm"
              >
                <div class="flex items-center gap-2 overflow-hidden">
                  <div class="w-7 h-7 rounded bg-gray-200 overflow-hidden shrink-0">
                    <img v-if="friend.avatar" :src="getAvatarUrl(friend.avatar)" class="w-full h-full object-cover" />
                    <User v-else :size="14" class="m-1.5 text-gray-400" />
                  </div>
                  <span class="text-sm truncate text-gray-700">{{ friend.name }}</span>
                </div>
                <button 
                  @click="removeSelectedFriend(friend.id)"
                  class="text-gray-400 hover:text-red-500 transition-colors"
                >
                  <X :size="14" />
                </button>
              </div>
            </div>
          </ScrollArea>

          <!-- Group Name Input Area -->
          <div class="p-4 border-t bg-white">
             <label class="text-xs text-gray-500 mb-1 block">群聊名称 (可选)</label>
             <Input v-model="groupName" placeholder="默认使用成员名称" class="h-8 text-sm" />
          </div>
        </div>
      </div>

      <DialogFooter class="p-4 border-t bg-gray-50">
        <Button variant="outline" @click="isOpen = false">取消</Button>
        <Button 
          @click="handleConfirm" 
          :disabled="selectedFriendIds.length < 2 || isSubmitting"
          class="bg-[#07c160] hover:bg-[#06ad56] text-white px-8"
        >
          {{ isSubmitting ? '创建中...' : '确定' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.group-selector-dialog :deep(.sm\:max-w-\[700px\]) {
  max-height: 90vh;
}
</style>
