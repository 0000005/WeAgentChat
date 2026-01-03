<script setup lang="ts">
import { computed } from 'vue'
import { 
  MessageCircle, 
  Users, 
  Star, 
  FolderOpen,
  Link2,
  Settings
} from 'lucide-vue-next'

const props = defineProps<{
  activeTab: 'chat' | 'contacts' | 'favorites' | 'files' | 'mini-programs'
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', value: string): void
  (e: 'open-settings'): void
}>()

const navItems = [
  { id: 'chat', icon: MessageCircle, label: '聊天' },
  { id: 'contacts', icon: Users, label: '联系人' },
  { id: 'favorites', icon: Star, label: '收藏' },
  { id: 'files', icon: FolderOpen, label: '文件' },
  { id: 'mini-programs', icon: Link2, label: '小程序' },
]
</script>

<template>
  <aside class="wechat-icon-sidebar">
    <!-- User Avatar -->
    <div class="avatar-section">
      <div class="avatar">
        <img 
          src="https://api.dicebear.com/7.x/avataaars/svg?seed=doudou" 
          alt="User Avatar"
          class="avatar-img"
        />
      </div>
    </div>

    <!-- Navigation Icons -->
    <nav class="nav-icons">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-btn"
        :class="{ active: activeTab === item.id }"
        :title="item.label"
        @click="emit('update:activeTab', item.id)"
      >
        <component :is="item.icon" :size="22" :stroke-width="1.5" />
        <span v-if="item.id === 'chat'" class="unread-dot"></span>
      </button>
    </nav>

    <!-- Bottom Actions -->
    <div class="bottom-actions">
      <button 
        class="nav-btn"
        title="设置"
        @click="emit('open-settings')"
      >
        <Settings :size="22" :stroke-width="1.5" />
      </button>
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
