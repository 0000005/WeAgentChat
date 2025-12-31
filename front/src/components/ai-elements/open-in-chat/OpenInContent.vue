<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { DropdownMenuContent } from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

interface Props {
  class?: HTMLAttributes['class']
}

defineOptions({
  inheritAttrs: false,
})

const props = defineProps<Props>()
</script>

<template>
  <DropdownMenuContent
    align="start"
    :class="cn('w-[240px]', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </DropdownMenuContent>
</template>
