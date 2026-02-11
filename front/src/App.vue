<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import IconSidebar from './components/IconSidebar.vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'
import FriendGallery from './components/FriendGallery.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import ProfileDialog from './components/ProfileDialog.vue'
import SetupWizard from './components/SetupWizard.vue'
import ToastContainer from './components/ToastContainer.vue'
import WindowControls from './components/WindowControls.vue'
import ChatDrawerMenu from './components/ChatDrawerMenu.vue'
import GroupChatDrawer from './components/GroupChatDrawer.vue'
import FriendComposeDialog from './components/FriendComposeDialog.vue'
import GroupComposeDialog from './components/GroupComposeDialog.vue'
import GroupChatArea from './components/GroupChatArea.vue'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useUpdateCheck } from '@/composables/useUpdateCheck'
import UpdateNotifyDialog from './components/UpdateNotifyDialog.vue'

import { checkHealth } from '@/api/health'

const isSidebarOpen = ref(true)
const activeTab = ref<'chat' | 'gallery'>('chat')
const isSettingsOpen = ref(false)
const isProfileOpen = ref(false)
const isSetupWizardOpen = ref(false)
const isDrawerOpen = ref(false)
const isFriendComposeOpen = ref(false)
const isGroupComposeOpen = ref(false)
const friendComposeMode = ref<'add' | 'edit'>('add')
const friendComposeId = ref<number | null>(null)
const sessionStore = useSessionStore()
const settingsStore = useSettingsStore()
const settingsDefaultTab = ref('llm')

const {
  updateAvailable: isUpdateAvailable,
  latestVersion: latestAppVersion,
  currentVersion: currentAppVersion,
  checkUpdate,
  openReleases
} = useUpdateCheck()

const handleOpenSettings = (tab: string = 'llm') => {
  settingsDefaultTab.value = tab
  isSettingsOpen.value = true
}

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

const handleAddFriend = () => {
  friendComposeMode.value = 'add'
  friendComposeId.value = null
  isFriendComposeOpen.value = true
}

const handleEditFriend = (id: number) => {
  friendComposeMode.value = 'edit'
  friendComposeId.value = id
  isFriendComposeOpen.value = true
}

// Global focus handler to stop notification flashing
const handleWindowFocus = () => {
  window.WeAgentChat?.notification?.stopFlash()
}

onMounted(async () => {
  activeTab.value = 'chat'
  // If screen width is less than 768px (md breakpoint), start with sidebar closed
  if (window.innerWidth < 768) {
    isSidebarOpen.value = false
  }

  // Register global focus listener to stop tray flashing
  window.addEventListener('focus', handleWindowFocus)

  // Load chat and user settings from backend
  await Promise.all([
    settingsStore.fetchChatSettings(),
    settingsStore.fetchUserSettings()
  ])

  // Check if system is configured
  try {
    const health = await checkHealth()
    if (!health.llm_configured || !health.embedding_configured) {
      isSetupWizardOpen.value = true
    }
  } catch (error) {
    console.error('Failed to check health:', error)
  }

  // 异步检测更新 (Async update check)
  setTimeout(() => {
    checkUpdate()
  }, 2000)
})

onUnmounted(() => {
  window.removeEventListener('focus', handleWindowFocus)
})

const handleSetupComplete = () => {
  isSetupWizardOpen.value = false
  // Reload settings or friends if needed
}
</script>

<template>
  <div class="wechat-shell">
    <!-- 
      ============================================================
      全局窗口控制组件 (Global Window Controls)
      ============================================================
      此组件仅在 Electron 桌面模式下渲染 (由 WindowControls 内部判断 isElectron)。
      
      【关于 "更多" 按钮的显示逻辑】
      - Electron 模式: "更多"按钮集成在这里的 WindowControls 中，与最小化/最大化/关闭按钮同一行。
      - Web 浏览器模式: WindowControls 不渲染，"更多"按钮回退到 ChatArea.vue 的 Header 中显示。
      
      这样设计是为了:
      1. Electron 模式下保持标题栏按钮的完美对齐
      2. Web 开发模式下保留完整的菜单访问功能
      
      注意: 这不是重复代码，而是针对不同运行环境的适配逻辑。
    -->
    <WindowControls class="global-window-controls" :show-more="activeTab === 'chat'"
      @more-click="isDrawerOpen = true" />

    <div class="wechat-app">
      <!-- Icon Sidebar (always visible on desktop) -->
      <div class="icon-sidebar-container">
        <IconSidebar :active-tab="activeTab" @update:activeTab="updateActiveTab($event as 'chat' | 'gallery')"
          @open-settings="handleOpenSettings('llm')" @open-profile="isProfileOpen = true" />
      </div>

      <!-- Conversation List Sidebar -->
      <div v-if="activeTab !== 'gallery'" class="sidebar-container" :class="{ collapsed: !isSidebarOpen }">
        <Sidebar @open-gallery="handleOpenGallery" @add-friend="handleAddFriend" @edit-friend="handleEditFriend"
          @create-group="isGroupComposeOpen = true" />
      </div>

      <!-- Mobile Sidebar Overlay (Only on small screens) -->
      <div v-if="isSidebarOpen && activeTab !== 'gallery'" class="mobile-overlay md:hidden"
        @click="isSidebarOpen = false">
        <div class="mobile-sidebar" @click.stop>
          <IconSidebar :active-tab="activeTab" @update:activeTab="updateActiveTab($event as 'chat' | 'gallery')"
            @open-settings="handleOpenSettings('llm')" @open-profile="isProfileOpen = true" />
          <Sidebar @open-gallery="handleOpenGallery" @add-friend="handleAddFriend" @edit-friend="handleEditFriend"
            @create-group="isGroupComposeOpen = true" />
        </div>
      </div>


      <!-- Main Chat Area -->
      <main class="chat-container">
        <FriendGallery v-if="activeTab === 'gallery'" @back-chat="updateActiveTab('chat')"
          @open-settings="handleOpenSettings" />
        <template v-else>
          <GroupChatArea v-if="sessionStore.chatType === 'group'" :is-sidebar-collapsed="!isSidebarOpen"
            @toggle-sidebar="toggleSidebar" @open-drawer="isDrawerOpen = true" @open-settings="handleOpenSettings" />
          <ChatArea v-else :is-sidebar-collapsed="!isSidebarOpen" @toggle-sidebar="toggleSidebar"
            @open-drawer="isDrawerOpen = true" @edit-friend="handleEditFriend" @open-settings="handleOpenSettings" />
        </template>
      </main>


      <!-- Settings Dialog -->
      <SettingsDialog v-model:open="isSettingsOpen" :default-tab="settingsDefaultTab" />

      <!-- Profile Dialog -->
      <ProfileDialog v-model:open="isProfileOpen" />

      <!-- Setup Wizard Onboarding -->
      <SetupWizard v-model:open="isSetupWizardOpen" @complete="handleSetupComplete" />

      <!-- Global Chat Drawer -->
      <GroupChatDrawer v-if="sessionStore.chatType === 'group'" v-model:open="isDrawerOpen" />
      <ChatDrawerMenu v-else v-model:open="isDrawerOpen" />

      <!-- Global Friend Compose Dialog -->
      <FriendComposeDialog v-model:open="isFriendComposeOpen" :mode="friendComposeMode" :friend-id="friendComposeId"
        @open-settings="handleOpenSettings" />

      <!-- Global Group Compose Dialog -->
      <GroupComposeDialog v-model:open="isGroupComposeOpen" />


      <!-- Global Toast Container -->
      <ToastContainer />

      <!-- Update Notification Dialog -->
      <UpdateNotifyDialog v-model:open="isUpdateAvailable" :latest-version="latestAppVersion"
        :current-version="currentAppVersion" @download="openReleases" />
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
  position: relative;
}

/* Global Window Controls - Fixed Position */
.global-window-controls {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 9999;
  background: transparent;
  -webkit-app-region: no-drag;
  pointer-events: auto;
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
