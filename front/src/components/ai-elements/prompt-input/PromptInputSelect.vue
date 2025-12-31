<script setup lang="ts">
import { Select } from '@/components/ui/select'

type PromptInputSelectProps = InstanceType<typeof Select>['$props']

interface Props extends /* @vue-ignore */ PromptInputSelectProps {}

const props = defineProps<Props>()
</script>

<template>
  <Select v-bind="props">
    <slot />
  </Select>
</template>
