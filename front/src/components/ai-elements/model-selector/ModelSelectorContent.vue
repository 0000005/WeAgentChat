<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { Command } from '@/components/ui/command'
import { DialogContent, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

interface Props {
  title?: string
  class?: HTMLAttributes['class']
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Model Selector',
})
</script>

<template>
  <DialogContent
    :class="cn('p-0', props.class)"
    v-bind="$attrs"
  >
    <DialogTitle class="sr-only">
      {{ props.title }}
    </DialogTitle>
    <Command class="**:data-[slot=command-input-wrapper]:h-auto">
      <slot />
    </Command>
  </DialogContent>
</template>
