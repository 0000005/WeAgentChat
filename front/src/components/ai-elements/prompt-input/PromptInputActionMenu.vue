<script setup lang="ts">
import { DropdownMenu } from '@/components/ui/dropdown-menu'

type DropdownMenuProps = InstanceType<typeof DropdownMenu>['$props']

interface Props extends /* @vue-ignore */ DropdownMenuProps {}

const props = defineProps<Props>()
</script>

<template>
  <DropdownMenu v-bind="props">
    <slot />
  </DropdownMenu>
</template>
