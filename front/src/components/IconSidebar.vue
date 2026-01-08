<script setup lang="ts">
import { ref } from 'vue'
import packageJson from '../../package.json'
import {
  MessageCircle,
  LayoutGrid,
  Settings,
  Menu,
  User,
  Info
} from 'lucide-vue-next'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

defineProps<{
  activeTab: 'chat' | 'gallery'
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', value: string): void
  (e: 'open-settings'): void
  (e: 'open-profile'): void
}>()

const isPopoverOpen = ref(false)
const isAboutOpen = ref(false)
const appVersion = packageJson.version
const githubUrl = 'https://github.com/0000005/WeChatAgent'
const releaseUrl = `${githubUrl}/releases`
const authorName = 'JerryYin'

const handleOpenProfile = () => {
  isPopoverOpen.value = false
  emit('open-profile')
}

const handleOpenSettings = () => {
  isPopoverOpen.value = false
  emit('open-settings')
}

const handleOpenAbout = () => {
  isPopoverOpen.value = false
  isAboutOpen.value = true
}

const navItems = [
  { id: 'chat', icon: MessageCircle, label: '聊天' },
  { id: 'gallery', icon: LayoutGrid, label: '好友库' },
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
            <button
              class="flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-[#4a4a4a] rounded-md transition-colors"
              @click="handleOpenAbout">
              <Info :size="16" />
              <span>关于</span>
            </button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  </aside>

  <Dialog v-model:open="isAboutOpen">
    <DialogContent class="sm:max-w-[420px] p-0 overflow-hidden bg-[#f7f7f7] border-none shadow-2xl">
      <DialogHeader class="px-5 py-4 bg-white border-b">
        <DialogTitle class="text-base font-medium text-center">关于 WeAgentChat</DialogTitle>
        <DialogDescription class="sr-only">版本信息与项目地址</DialogDescription>
      </DialogHeader>
      <div class="px-5 py-4 space-y-3 text-sm text-gray-700">
        <div class="flex items-center justify-between">
          <span class="text-gray-500">软件版本</span>
          <span class="font-medium text-gray-900">v{{ appVersion }}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">版本更新</span>
          <a
            class="text-[#07c160] hover:underline"
            :href="releaseUrl"
            target="_blank"
            rel="noreferrer">
            查看更新
          </a>
        </div>
        <div class="space-y-1">
          <div class="text-gray-500">GitHub 地址（求 Star）</div>
          <a
            class="text-[#07c160] break-all hover:underline"
            :href="githubUrl"
            target="_blank"
            rel="noreferrer">
            {{ githubUrl }}
          </a>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">作者</span>
          <span class="text-gray-900">{{ authorName }}</span>
        </div>
      </div>
    </DialogContent>
  </Dialog>
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
