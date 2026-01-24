<script setup lang="ts">
import { computed } from 'vue'
import { getStaticUrl } from '@/api/base'
import { Users } from 'lucide-vue-next'

const props = defineProps<{
  members?: { avatar?: string; name?: string; member_type?: string }[]
  size?: number | string
  avatar?: string
}>()

const avatars = computed(() => {
  if (props.avatar) return [getStaticUrl(props.avatar)]
  if (!props.members || props.members.length === 0) return []
  
  // Take up to 9 members
  // Backend already populates avatar for both friends and user
  return props.members.slice(0, 9).map(m => {
    if (m.avatar) return getStaticUrl(m.avatar)
    return null // Will show placeholder or initials
  })
})

const itemClass = computed(() => {
  const count = avatars.value.length
  if (count <= 1) return 'w-full h-full'
  if (count <= 4) return 'w-[48%] h-[48%]'
  return 'w-[31%] h-[31%]'
})

const containerStyle = computed(() => {
  const size = typeof props.size === 'number' ? `${props.size}px` : props.size || '40px'
  return {
    width: size,
    height: size
  }
})
</script>

<template>
  <div 
    class="group-avatar-container bg-[#ddd] flex flex-wrap items-center justify-center p-[2px] gap-[2px] rounded overflow-hidden"
    :style="containerStyle"
  >
    <img v-if="props.avatar" :src="getStaticUrl(props.avatar)" class="w-full h-full object-cover" />
    
    <template v-else-if="avatars.length > 0">
      <div 
        v-for="(src, index) in avatars" 
        :key="index"
        :class="['bg-white flex-shrink-0 flex items-center justify-center overflow-hidden', itemClass]"
      >
        <img v-if="src" :src="src" class="w-full h-full object-cover" />
        <div v-else class="text-[8px] scale-75 text-gray-400">
           <Users v-if="props.members?.[index]?.member_type === 'user'" :size="8" />
           <span v-else>{{ props.members?.[index]?.name?.[0] || '?' }}</span>
        </div>
      </div>
    </template>

    <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
      <Users :size="24" />
    </div>
  </div>
</template>

<style scoped>
.group-avatar-container {
  aspect-ratio: 1/1;
  line-height: 0;
}
</style>
