<script setup lang="ts">
import { DialogTrigger } from '@/components/ui/dialog'
</script>

<template>
  <DialogTrigger v-bind="$attrs">
    <slot />
  </DialogTrigger>
</template>
