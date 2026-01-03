<script setup>
import { ref, onMounted } from 'vue'
import IconSidebar from './components/IconSidebar.vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'
import SettingsDialog from './components/SettingsDialog.vue'

const isSidebarOpen = ref(true)
const activeTab = ref('chat')
const isSettingsOpen = ref(false)

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

onMounted(() => {
  // If screen width is less than 768px (md breakpoint), start with sidebar closed
  if (window.innerWidth < 768) {
    isSidebarOpen.value = false
  }
})
</script>

<template>
  <div class="wechat-app">
    <!-- Icon Sidebar (always visible on desktop) -->
    <div class="icon-sidebar-container">
      <IconSidebar 
        :active-tab="activeTab" 
        @update:activeTab="activeTab = $event"
        @open-settings="isSettingsOpen = true"
      />
    </div>

    <!-- Conversation List Sidebar -->
    <div 
      class="sidebar-container"
      :class="{ collapsed: !isSidebarOpen }"
    >
      <Sidebar />
    </div>

    <!-- Mobile Sidebar Overlay (Only on small screens) -->
    <div 
      v-if="isSidebarOpen"
      class="mobile-overlay md:hidden"
      @click="isSidebarOpen = false"
    >
      <div 
        class="mobile-sidebar"
        @click.stop
      >
        <IconSidebar 
          :active-tab="activeTab" 
          @update:activeTab="activeTab = $event"
          @open-settings="isSettingsOpen = true"
        />
        <Sidebar />
      </div>
    </div>

    <!-- Main Chat Area -->
    <main class="chat-container">
      <ChatArea 
        :is-sidebar-collapsed="!isSidebarOpen" 
        @toggle-sidebar="toggleSidebar" 
      />
    </main>

    <!-- Settings Dialog -->
    <SettingsDialog v-model:open="isSettingsOpen" />
  </div>
</template>

<style>
/* Reset and base styles */
.wechat-app {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
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
