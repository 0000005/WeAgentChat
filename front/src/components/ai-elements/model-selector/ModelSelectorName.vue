<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

interface Props {
  class?: HTMLAttributes['class']
}

const props = defineProps<Props>()
</script>

<template>
  <span
    :class="cn('flex-1 truncate text-left', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </span>
</template>
