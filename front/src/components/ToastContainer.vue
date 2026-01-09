<script setup lang="ts">
import { useToast } from '@/composables/useToast'
import { X } from 'lucide-vue-next'

const { toasts, removeToast } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="toast.type"
        >
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" @click="removeToast(toast.id)">
            <X :size="14" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(8px);
  pointer-events: auto;
  max-width: 360px;
}

.toast-item.success {
  background: rgba(7, 193, 96, 0.95);
  color: #fff;
}

.toast-item.error {
  background: rgba(220, 38, 38, 0.95);
  color: #fff;
}

.toast-item.info {
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
}

.toast-message {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: inherit;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.15s;
}

.toast-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Transition animations */
.toast-enter-active {
  transition: all 0.3s ease-out;
}

.toast-leave-active {
  transition: all 0.25s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>
