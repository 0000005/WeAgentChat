<script setup lang="ts">
import { CommandList } from '@/components/ui/command'
</script>

<template>
  <CommandList v-bind="$attrs">
    <slot />
  </CommandList>
</template>
