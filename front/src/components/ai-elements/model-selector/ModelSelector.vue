<script setup lang="ts">
import { Dialog } from '@/components/ui/dialog'
</script>

<template>
  <Dialog v-bind="$attrs">
    <slot />
  </Dialog>
</template>
