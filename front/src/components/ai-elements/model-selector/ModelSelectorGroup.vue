<script setup lang="ts">
import { CommandGroup } from '@/components/ui/command'
</script>

<template>
  <CommandGroup v-bind="$attrs">
    <slot />
  </CommandGroup>
</template>
