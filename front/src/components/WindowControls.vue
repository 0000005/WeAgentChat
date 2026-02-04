<script setup lang="ts">
/**
 * ============================================================
 * WindowControls.vue - 全局窗口控制组件
 * ============================================================
 * 
 * 此组件仅在 Electron 桌面模式下渲染，提供:
 * - 最小化、最大化/还原、关闭按钮
 * - 可选的"更多"菜单按钮 (通过 showMore prop 控制)
 * 
 * 【重要设计说明】
 * showMore prop 的作用:
 * - 当 showMore=true 时，在窗口控制按钮左侧显示"更多"按钮 (...)
 * - 这使得"更多"按钮与窗口控制按钮在同一行，保持完美对齐
 * - 仅在聊天页面 (activeTab === 'chat') 时显示，好友库等页面不显示
 * 
 * 【与 ChatArea.vue 的关系】
 * - Electron 模式: "更多"按钮在这里渲染
 * - Web 浏览器模式: 此组件不渲染，"更多"按钮回退到 ChatArea 的 Header 中
 * - 这不是重复代码，而是针对不同运行环境的适配
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MoreHorizontal, Share2 } from 'lucide-vue-next'

// Props: showMore 控制是否显示"更多"按钮 (仅在聊天页面为 true)
const props = defineProps<{
  showMore?: boolean
  showExport?: boolean
}>()

const emit = defineEmits<{
  (e: 'more-click'): void
  (e: 'export-click'): void
}>()

const isElectron = Boolean(window.WeAgentChat?.windowControls)
const isMaximized = ref(false)
let unsubscribeWindowState: (() => void) | null = null

const updateWindowState = (state: { isMaximized: boolean }) => {
  isMaximized.value = state.isMaximized
}

const handleMinimize = () => {
  if (!isElectron) return
  window.WeAgentChat?.windowControls?.minimize()
}

const handleToggleMaximize = () => {
  if (!isElectron) return
  window.WeAgentChat?.windowControls?.toggleMaximize()
}

const handleCloseWindow = () => {
  if (!isElectron) return
  window.WeAgentChat?.windowControls?.close()
}

onMounted(async () => {
  if (!isElectron) return
  const controls = window.WeAgentChat?.windowControls
  if (!controls) return
  try {
    const state = await controls.getState()
    updateWindowState(state)
  } catch {
    // ignore state sync errors
  }
  unsubscribeWindowState = controls.onState(updateWindowState)
})

onBeforeUnmount(() => {
  if (unsubscribeWindowState) unsubscribeWindowState()
})

// Expose openSystemMenu for parent components that want to bind it to contextmenu
const showSystemMenu = (e: MouseEvent) => {
  if (!isElectron) return
  const target = e.target as HTMLElement | null
  // Prevent showing if clicking on a button inside the controls
  if (target?.closest('button')) return
  
  e.preventDefault()
  window.WeAgentChat?.windowControls?.showSystemMenu({
    x: e.screenX,
    y: e.screenY,
  })
}

defineExpose({
  showSystemMenu,
  handleToggleMaximize
})
</script>

<template>
  <div v-if="isElectron" class="window-controls">
    <!-- Export / More Actions (only in specific contexts like chat) -->
    <button v-if="showExport" class="window-btn export-action-btn" title="分享/导出"
      @click="emit('export-click')" @mousedown.stop>
      <Share2 :size="16" />
    </button>
    <button v-if="showMore" class="window-btn more-action-btn" title="更多" @click="emit('more-click')">
      <MoreHorizontal :size="18" />
    </button>

    <div class="controls-divider" v-if="showMore || showExport"></div>

    <button class="window-btn" title="最小化" @click="handleMinimize">
      <svg class="window-icon" viewBox="0 0 10 10" aria-hidden="true">
        <rect x="1" y="5" width="8" height="1.2" />
      </svg>
    </button>
    <button class="window-btn" title="最大化/还原" @click="handleToggleMaximize">
      <svg v-if="!isMaximized" class="window-icon" viewBox="0 0 10 10" aria-hidden="true">
        <rect x="1.5" y="1.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1" />
      </svg>
      <svg v-else class="window-icon" viewBox="0 0 10 10" aria-hidden="true">
        <rect x="2" y="3" width="6" height="6" fill="none" stroke="currentColor" stroke-width="1" />
        <rect x="1" y="1" width="6" height="6" fill="none" stroke="currentColor" stroke-width="1" />
      </svg>
    </button>
    <button class="window-btn close" title="关闭" @click="handleCloseWindow">
      <svg class="window-icon" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M2 2 L8 8 M8 2 L2 8" stroke="currentColor" stroke-width="1.2" fill="none" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.window-controls {
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
  pointer-events: auto;
}

.window-btn {
  width: 38px;
  height: 28px;
  border: none;
  background: transparent;
  color: #555;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  -webkit-app-region: no-drag;
  pointer-events: auto;
}

.window-btn:hover {
  background: #e5e5e5;
}

.window-btn svg,
.window-btn path,
.window-btn rect {
  -webkit-app-region: no-drag;
  pointer-events: none;
}

.window-btn.close:hover {
  background: #e81123;
  color: #fff;
}

.more-action-btn {
  margin-right: 2px;
  color: #666;
}

.export-action-btn {
  margin-right: 2px;
  color: #666;
  position: relative;
}

.export-action-btn::before {
  content: '';
  position: absolute;
  inset: -6px -4px;
}

.controls-divider {
  width: 1px;
  height: 14px;
  background-color: #e0e0e0;
  margin: 0 4px;
}

.window-icon {
  width: 12px;
  height: 12px;
  fill: currentColor;
}

/* Ensure SVG paths inherit color */
.window-icon rect, .window-icon path {
  fill: currentColor;
  stroke: currentColor;
}

/* Specific fix for the minimize rect which might need fill */
.window-icon rect[fill="none"] {
  fill: none;
}
</style>
