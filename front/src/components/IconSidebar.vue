<script setup lang="ts">
import { ref } from 'vue'
import {
  MessageCircle,
  Users,
  Settings,
  Menu,
  User
} from 'lucide-vue-next'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

defineProps<{
  activeTab: 'chat' | 'contacts'
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', value: string): void
  (e: 'open-settings'): void
  (e: 'open-profile'): void
}>()

const isPopoverOpen = ref(false)

const handleOpenProfile = () => {
  isPopoverOpen.value = false
  emit('open-profile')
}

const handleOpenSettings = () => {
  isPopoverOpen.value = false
  emit('open-settings')
}

const navItems = [
  { id: 'chat', icon: MessageCircle, label: '聊天' },
  { id: 'contacts', icon: Users, label: '联系人' },
]
</script>

<template>
  <aside class="wechat-icon-sidebar">
    <!-- User Avatar -->
    <div class="avatar-section">
      <div class="avatar cursor-pointer" @click="emit('open-profile')">
        <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=doudou" alt="User Avatar" class="avatar-img" />
      </div>
    </div>

    <!-- Navigation Icons -->
    <nav class="nav-icons">
      <button v-for="item in navItems" :key="item.id" class="nav-btn" :class="{ active: activeTab === item.id }"
        :title="item.label" @click="emit('update:activeTab', item.id)">
        <component :is="item.icon" :size="22" :stroke-width="1.5" />
        <span v-if="item.id === 'chat'" class="unread-dot"></span>
      </button>
    </nav>

    <!-- Bottom Actions -->
    <div class="bottom-actions">
      <Popover v-model:open="isPopoverOpen">
        <PopoverTrigger as-child>
          <button class="nav-btn" title="更多">
            <Menu :size="22" :stroke-width="1.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent side="right" align="end" :side-offset="12" class="w-32 p-1 bg-[#3c3c3c] border-none shadow-xl">
          <div class="flex flex-col gap-1">
            <button
              class="flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-[#4a4a4a] rounded-md transition-colors"
              @click="handleOpenProfile">
              <User :size="16" />
              <span>个人资料</span>
            </button>
            <button
              class="flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-[#4a4a4a] rounded-md transition-colors"
              @click="handleOpenSettings">
              <Settings :size="16" />
              <span>设置</span>
            </button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  </aside>
</template>

<style scoped>
.wechat-icon-sidebar {
  width: 56px;
  min-width: 56px;
  height: 100%;
  background: #2e2e2e;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
}

.avatar-section {
  padding: 8px 0 16px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  overflow: hidden;
  background: #444;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.nav-icons {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-top: 8px;
}

.nav-btn {
  position: relative;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #8c8c8c;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.nav-btn:hover {
  color: #c0c0c0;
  background: rgba(255, 255, 255, 0.05);
}

.nav-btn.active {
  color: #07c160;
  background: rgba(7, 193, 96, 0.1);
}

.unread-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: #fa5151;
  border-radius: 50%;
}

.bottom-actions {
  padding: 16px 0 8px;
}
</style>
