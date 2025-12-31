<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { CarouselItem } from '@/components/ui/carousel'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <CarouselItem :class="cn('w-full space-y-2 p-4 pl-8', props.class)">
    <slot />
  </CarouselItem>
</template>
