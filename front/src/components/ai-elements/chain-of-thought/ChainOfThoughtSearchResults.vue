<script setup lang="ts">
import type { HtmlHTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HtmlHTMLAttributes['class']
}>()
</script>

<template>
  <div
    :class="cn('flex items-center gap-2', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
