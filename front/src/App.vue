<script setup>
import { ref, onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatArea from './components/ChatArea.vue'

const isSidebarOpen = ref(true)

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
  <div class="flex h-screen bg-[#f9fafb] overflow-hidden text-gray-900 font-['Inter'] relative">
    <!-- Desktop Sidebar -->
    <div 
      class="hidden md:block overflow-hidden transition-all duration-300 ease-in-out border-r border-gray-200"
      :class="isSidebarOpen ? 'w-[260px]' : 'w-0'"
    >
      <Sidebar @toggle-sidebar="toggleSidebar" />
    </div>

    <!-- Mobile Sidebar Overlay (Only on small screens) -->
    <div 
      v-if="isSidebarOpen"
      class="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 md:hidden"
      @click="isSidebarOpen = false"
    >
      <div 
        class="w-[280px] h-full bg-white shadow-2xl transition-transform duration-300 transform"
        :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full'"
        @click.stop
      >
        <Sidebar @toggle-sidebar="toggleSidebar" />
      </div>
    </div>

    <!-- Main Chat Area -->
    <main class="flex-1 flex flex-col min-w-0 bg-white shadow-sm ring-1 ring-gray-200">
      <ChatArea 
        :is-sidebar-collapsed="!isSidebarOpen" 
        @toggle-sidebar="toggleSidebar" 
      />
    </main>
  </div>
</template>

<style>
/* Any global App styles if needed */
</style>
