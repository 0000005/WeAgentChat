<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { usePersonaStore } from '@/stores/persona'
import { useSessionStore } from '@/stores/session'
import { MessageSquare, Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  personaId: number | null
}>()

const emit = defineEmits(['update:open', 'saved', 'start-chat'])

const personaStore = usePersonaStore()
const sessionStore = useSessionStore()

const isLoading = ref(false)
const formData = ref({
    name: '',
    description: '',
    system_prompt: ''
})

const isEdit = computed(() => props.personaId !== null)

watch(() => props.open, (newVal) => {
    if (newVal) {
        if (props.personaId !== null) {
            const p = personaStore.getPersona(props.personaId)
            if (p) {
                formData.value = {
                    name: p.name,
                    description: p.description || '',
                    system_prompt: p.system_prompt || ''
                }
            }
        } else {
            formData.value = {
                name: '',
                description: '',
                system_prompt: ''
            }
        }
    }
})

const onSave = async () => {
    if (!formData.value.name) return // Simple validation

    isLoading.value = true
    try {
        if (props.personaId !== null) {
            await personaStore.updatePersona(props.personaId, formData.value)
        } else {
            await personaStore.addPersona(formData.value)
        }
        emit('saved')
        emit('update:open', false)
    } catch (e) {
        console.error('Failed to save persona', e)
    } finally {
        isLoading.value = false
    }
}

const onStartChat = () => {
    if (props.personaId !== null) {
        sessionStore.createSession(props.personaId)
        emit('start-chat')
        emit('update:open', false)
    }
}
</script>

<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[500px]">
      <DialogHeader>
        <DialogTitle>{{ isEdit ? '编辑角色' : '新建角色' }}</DialogTitle>
      </DialogHeader>
      
      <div class="grid gap-4 py-4">
        <div class="grid gap-2">
          <label for="name" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
            名称
          </label>
          <Input id="name" v-model="formData.name" placeholder="例如：代码助手" />
        </div>
        
        <div class="grid gap-2">
          <label for="description" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
            描述
          </label>
          <Input id="description" v-model="formData.description" placeholder="简短描述该角色的功能..." />
        </div>
        
        <div class="grid gap-2">
          <label for="prompt" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
            系统提示词 (System Prompt)
          </label>
          <Textarea 
            id="prompt" 
            v-model="formData.system_prompt" 
            placeholder="你是一个..." 
            class="min-h-[150px]"
          />
        </div>
      </div>

      <DialogFooter class="flex justify-between sm:justify-between items-center">
        <!-- Left side actions (Start Chat) -->
        <div>
            <Button v-if="isEdit" type="button" variant="secondary" @click="onStartChat">
                <MessageSquare class="w-4 h-4 mr-2" />
                发起对话
            </Button>
        </div>

        <!-- Right side actions (Save/Cancel) -->
        <div class="flex gap-2">
            <Button type="button" variant="outline" @click="$emit('update:open', false)">
            取消
            </Button>
            <Button type="button" @click="onSave" :disabled="isLoading">
                <Loader2 v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                保存
            </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>