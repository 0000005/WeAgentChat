<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <Badge
    :class="
      cn(
        'gap-1 px-2 py-0.5 font-normal text-xs',
        props.class,
      )
    "
    variant="secondary"
    v-bind="$attrs"
  >
    <slot />
  </Badge>
</template>
