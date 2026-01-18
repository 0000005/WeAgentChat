<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { ref, computed } from 'vue'
import { cn } from '@/lib/utils'
import { reactiveOmit } from '@vueuse/core'
import { StickToBottom } from 'vue-stick-to-bottom'

interface Props {
  ariaLabel?: string
  class?: HTMLAttributes['class']
  initial?: boolean | 'instant' | { damping?: number, stiffness?: number, mass?: number }
  resize?: 'instant' | { damping?: number, stiffness?: number, mass?: number }
  damping?: number
  stiffness?: number
  mass?: number
  anchor?: 'auto' | 'none'
}

const props = withDefaults(defineProps<Props>(), {
  ariaLabel: 'Conversation',
  initial: 'instant', // Instant scroll like WeChat, no animation
  resize: 'instant',  // Also instant when content resizes
  damping: 0.7,
  stiffness: 0.05,
  mass: 1.25,
  anchor: 'none',
})
const delegatedProps = reactiveOmit(props, 'class')

// Ref to the StickToBottom component to access its exposed properties
const stickToBottomRef = ref<InstanceType<typeof StickToBottom> | null>(null)

// Expose scrollRef for parent components to attach scroll listeners
const scrollRef = computed(() => stickToBottomRef.value?.scrollRef)

defineExpose({
  scrollRef
})
</script>

<template>
  <StickToBottom
    ref="stickToBottomRef"
    v-bind="delegatedProps"
    :class="cn('relative flex-1 overflow-y-hidden', props.class)"
    role="log"
  >
    <slot />
  </StickToBottom>
</template>
