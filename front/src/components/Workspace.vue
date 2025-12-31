<script setup>
import { 
  Plus, 
  RotateCcw, 
  Library,
  Upload,
  Files
} from 'lucide-vue-next'
</script>

<template>
  <aside class="w-[300px] flex flex-col bg-[#f9fafb] border-l border-gray-200 h-full">
    <!-- Header -->
    <div class="px-6 py-5 border-b border-gray-100">
      <h3 class="font-bold text-lg mb-4">工作空间</h3>
      <div class="flex items-center justify-between text-gray-500">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-gray-700">文件</span>
          <button class="p-1 hover:bg-gray-200 rounded transition-colors">
            <RotateCcw :size="16" />
          </button>
          <button class="p-1 hover:bg-gray-200 rounded transition-colors">
            <Library :size="16" />
          </button>
        </div>
        <div class="flex items-center gap-1">
          <button class="p-1 hover:bg-gray-200 rounded transition-colors">
            <Plus :size="20" />
          </button>
          <button class="p-1 hover:bg-gray-200 rounded transition-colors">
            <Files :size="20" />
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div class="flex-1 flex flex-col items-center justify-center p-8 text-center">
      <div class="w-16 h-16 mb-4 text-gray-300">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        </svg>
      </div>
      <p class="text-sm font-semibold text-gray-800 mb-1">工作空间为空</p>
      <p class="text-[13px] text-gray-500 max-w-[200px] leading-relaxed">
        上传文件或打开文件夹后，文件将显示在这里
      </p>
    </div>
  </aside>
</template>
