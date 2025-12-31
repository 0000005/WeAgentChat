<script setup lang="ts">
import { CommandItem } from '@/components/ui/command'
</script>

<template>
  <CommandItem v-bind="$attrs">
    <slot />
  </CommandItem>
</template>
