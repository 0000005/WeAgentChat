<script setup lang="ts">
import { ref, onMounted } from 'vue'
import IconSidebar from './components/IconSidebar.vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'
import FriendGallery from './components/FriendGallery.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import ProfileDialog from './components/ProfileDialog.vue'
import { useSettingsStore } from '@/stores/settings'

const isSidebarOpen = ref(true)
const activeTab = ref<'chat' | 'gallery'>('chat')
const isSettingsOpen = ref(false)
const isProfileOpen = ref(false)
const settingsStore = useSettingsStore()

const updateActiveTab = (tab: 'chat' | 'gallery') => {
  const nextTab = tab === 'gallery' ? 'gallery' : 'chat'
  activeTab.value = nextTab
  if (nextTab === 'gallery') {
    isSidebarOpen.value = false
    return
  }
  if (window.innerWidth >= 768) {
    isSidebarOpen.value = true
  }
}

const handleOpenGallery = () => {
  updateActiveTab('gallery')
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

onMounted(async () => {
  activeTab.value = 'chat'
  // If screen width is less than 768px (md breakpoint), start with sidebar closed
  if (window.innerWidth < 768) {
    isSidebarOpen.value = false
  }

  // Load chat settings from backend (including enable_thinking)
  await settingsStore.fetchChatSettings()
})
</script>

<template>
  <div class="wechat-shell">
    <div class="wechat-app">
      <!-- Icon Sidebar (always visible on desktop) -->
      <div class="icon-sidebar-container">
        <IconSidebar :active-tab="activeTab" @update:activeTab="updateActiveTab($event)" @open-settings="isSettingsOpen = true"
          @open-profile="isProfileOpen = true" />
      </div>

      <!-- Conversation List Sidebar -->
      <div v-if="activeTab !== 'gallery'" class="sidebar-container" :class="{ collapsed: !isSidebarOpen }">
        <Sidebar @open-gallery="handleOpenGallery" />
      </div>

      <!-- Mobile Sidebar Overlay (Only on small screens) -->
      <div v-if="isSidebarOpen && activeTab !== 'gallery'" class="mobile-overlay md:hidden" @click="isSidebarOpen = false">
        <div class="mobile-sidebar" @click.stop>
          <IconSidebar :active-tab="activeTab" @update:activeTab="updateActiveTab($event)"
            @open-settings="isSettingsOpen = true" @open-profile="isProfileOpen = true" />
          <Sidebar @open-gallery="handleOpenGallery" />
        </div>
      </div>

      <!-- Main Chat Area -->
      <main class="chat-container">
        <FriendGallery v-if="activeTab === 'gallery'" @back-chat="updateActiveTab('chat')" />
        <ChatArea v-else :is-sidebar-collapsed="!isSidebarOpen" @toggle-sidebar="toggleSidebar" />
      </main>

      <!-- Settings Dialog -->
      <SettingsDialog v-model:open="isSettingsOpen" />

      <!-- Profile Dialog -->
      <ProfileDialog v-model:open="isProfileOpen" />
    </div>
  </div>
</template>

<style>
/* Reset and base styles */
.wechat-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
}

.wechat-app {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Icon Sidebar */
.icon-sidebar-container {
  display: none;
}

@media (min-width: 768px) {
  .icon-sidebar-container {
    display: block;
    flex-shrink: 0;
  }
}

/* Conversation Sidebar */
.sidebar-container {
  display: none;
  flex-shrink: 0;
  transition: width 0.3s ease;
}

@media (min-width: 768px) {
  .sidebar-container {
    display: block;
    width: 260px;
  }

  .sidebar-container.collapsed {
    width: 0;
    overflow: hidden;
  }
}

/* Chat Container */
.chat-container {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* Mobile Overlay */
.mobile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 50;
}

.mobile-sidebar {
  display: flex;
  height: 100%;
  background: #e9e9e9;
  width: 316px;
  max-width: 90vw;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

/* Hide on md and up */
@media (min-width: 768px) {
  .mobile-overlay {
    display: none !important;
  }
}
</style>

