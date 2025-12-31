<script setup lang="ts">
import { CommandDialog } from '@/components/ui/command'
</script>

<template>
  <CommandDialog v-bind="$attrs">
    <slot />
  </CommandDialog>
</template>
