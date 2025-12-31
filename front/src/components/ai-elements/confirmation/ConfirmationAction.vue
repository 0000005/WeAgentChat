<script setup lang="ts">
import { Button } from '@/components/ui/button'
</script>

<template>
  <Button class="h-8 px-3 text-sm" type="button" v-bind="$attrs">
    <slot />
  </Button>
</template>
