<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { CommandInput } from '@/components/ui/command'
import { cn } from '@/lib/utils'

type PromptInputCommandInputProps = InstanceType<typeof CommandInput>['$props']

interface Props extends /* @vue-ignore */ PromptInputCommandInputProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<Props>()
</script>

<template>
  <CommandInput :class="cn(props.class)" v-bind="props" />
</template>
