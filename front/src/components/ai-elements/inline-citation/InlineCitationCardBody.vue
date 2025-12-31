<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { HoverCardContent } from '@/components/ui/hover-card'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <HoverCardContent :class="cn('relative w-80 p-0', props.class)">
    <slot />
  </HoverCardContent>
</template>
