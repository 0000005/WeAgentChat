<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { HoverCardContent } from '@/components/ui/hover-card'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <HoverCardContent
    :class="
      cn('min-w-60 divide-y overflow-hidden p-0', props.class)
    "
    v-bind="$attrs"
  >
    <slot />
  </HoverCardContent>
</template>
