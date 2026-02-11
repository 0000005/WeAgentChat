<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useFriendStore } from '@/stores/friend'
import { useSessionStore } from '@/stores/session'
import { UserPlus, Camera } from 'lucide-vue-next'
import { getStaticUrl } from '@/api/base'
import AvatarUploader from '@/components/common/AvatarUploader.vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const props = defineProps<{
  open: boolean
  mode: 'add' | 'edit'
  friendId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'success', friend: any): void
}>()

const friendStore = useFriendStore()
const sessionStore = useSessionStore()

const isSubmitting = ref(false)
const isAvatarUploaderOpen = ref(false)

const form = ref({
  name: '',
  description: '',
  system_prompt: '',
  avatar: '',
  script_expression: false,
  temperature: 1,
  top_p: 0.9,
})

const isOpen = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const resetForm = () => {
  form.value = {
    name: '',
    description: '',
    system_prompt: '',
    avatar: '',
    script_expression: false,
    temperature: 1,
    top_p: 0.9,
  }
}

const loadFriendData = () => {
  if (props.mode === 'edit' && props.friendId) {
    const friend = friendStore.getFriend(props.friendId)
    if (friend) {
      form.value = {
        name: friend.name,
        description: friend.description || '',
        system_prompt: friend.system_prompt || '',
        avatar: friend.avatar || '',
        script_expression: friend.script_expression ?? false,
        temperature: typeof friend.temperature === 'number' ? friend.temperature : 1,
        top_p: typeof friend.top_p === 'number' ? friend.top_p : 0.9,
      }
    }
  } else {
    resetForm()
  }
}

watch(() => props.open, (newVal) => {
  if (newVal) {
    loadFriendData()
  }
})

const handleAvatarUploaded = (url: string) => {
  form.value.avatar = url
}

const clampValue = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const getStepPrecision = (step: number) => {
  const stepText = step.toString()
  const dotIndex = stepText.indexOf('.')
  return dotIndex === -1 ? 0 : stepText.length - dotIndex - 1
}

const roundToStep = (value: number, step: number) => {
  const precision = getStepPrecision(step)
  const rounded = Math.round((value + Number.EPSILON) / step) * step
  return Number(rounded.toFixed(precision))
}

const normalizeTemperature = () => {
  if (!Number.isFinite(form.value.temperature)) {
    form.value.temperature = 1
    return
  }
  form.value.temperature = clampValue(roundToStep(form.value.temperature, 0.1), 0, 2)
}

const normalizeTopP = () => {
  if (!Number.isFinite(form.value.top_p)) {
    form.value.top_p = 0.9
    return
  }
  form.value.top_p = clampValue(roundToStep(form.value.top_p, 0.05), 0, 1)
}

const isFormValid = computed(() => {
  return form.value.name.trim() && 
         form.value.description.trim() && 
         form.value.system_prompt.trim()
})

const handleConfirm = async () => {
  if (!isFormValid.value) return

  normalizeTemperature()
  normalizeTopP()

  isSubmitting.value = true
  try {
    if (props.mode === 'add') {
      const createdFriend = await friendStore.addFriend({
        name: form.value.name.trim(),
        description: form.value.description.trim() || undefined,
        system_prompt: form.value.system_prompt.trim() || undefined,
        is_preset: false,
        avatar: form.value.avatar || undefined,
        script_expression: form.value.script_expression,
        temperature: form.value.temperature,
        top_p: form.value.top_p
      })
      emit('success', createdFriend)
      sessionStore.selectFriend(createdFriend.id)
    } else if (props.mode === 'edit' && props.friendId) {
      const updatedFriend = await friendStore.updateFriend(props.friendId, {
        name: form.value.name.trim(),
        description: form.value.description.trim() || null,
        system_prompt: form.value.system_prompt.trim() || null,
        avatar: form.value.avatar || null,
        script_expression: form.value.script_expression,
        temperature: form.value.temperature,
        top_p: form.value.top_p
      })
      emit('success', updatedFriend)
    }
    isOpen.value = false
  } catch (e) {
    console.error(`Failed to ${props.mode} friend:`, e)
  } finally {
    isSubmitting.value = false
  }
}
</script>
<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[500px] friend-compose-dialog">
      <DialogHeader>
        <DialogTitle>{{ mode === 'add' ? '新增好友' : '编辑好友' }}</DialogTitle>
        <DialogDescription>
          {{ mode === 'add' ? '创建一个新的 AI 好友，设置其名称和人格特征。' : '修改 AI 好友的名称和人格特征。' }}
        </DialogDescription>
      </DialogHeader>

      <Tabs default-value="basic" class="w-full">
        <TabsList class="grid grid-cols-2 w-full bg-gray-100 p-1 rounded-lg">
          <TabsTrigger value="basic"
            class="data-[state=active]:bg-white data-[state=active]:text-green-700 data-[state=active]:shadow-sm">
            基本资料
          </TabsTrigger>
          <TabsTrigger value="advanced"
            class="data-[state=active]:bg-white data-[state=active]:text-green-700 data-[state=active]:shadow-sm">
            模型设置
          </TabsTrigger>
        </TabsList>

        <TabsContent value="basic" class="pt-4">
          <!-- Avatar Upload Section -->
          <div class="flex flex-col items-center py-4 shrink-0">
            <div class="relative group cursor-pointer" @click="isAvatarUploaderOpen = true">
              <div
                class="w-20 h-20 rounded-lg border border-gray-200 shadow-sm bg-gray-50 flex items-center justify-center overflow-hidden">
                <img v-if="form.avatar" :src="getStaticUrl(form.avatar)" class="w-full h-full object-cover" />
                <UserPlus v-else class="text-gray-300 w-8 h-8" />
              </div>
              <div
                class="absolute inset-0 bg-black/40 rounded-lg opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-[1px]">
                <Camera class="text-white w-6 h-6" stroke-width="1.5" />
              </div>
            </div>
            <div class="mt-2 text-xs text-gray-500">{{ mode === 'add' ? '点击设置头像' : '点击更换头像' }}</div>
          </div>

          <div class="dialog-form">
            <div class="form-group">
              <label for="friend-name" class="form-label">好友名称 <span class="required">*</span></label>
              <Input id="friend-name" v-model="form.name" :placeholder="mode === 'add' ? '请输入好友名称，如：小助手、知心姐姐' : '请输入好友名称'"
                class="form-input" />
            </div>

            <div class="form-group">
              <label for="friend-description" class="form-label">好友描述 <span class="required">*</span></label>
              <Input id="friend-description" v-model="form.description" placeholder="简短描述这个好友的特点" class="form-input" />
            </div>

            <div class="form-group">
              <label for="friend-system-prompt" class="form-label">系统提示词 <span class="required">*</span></label>
              <Textarea id="friend-system-prompt" v-model="form.system_prompt"
                placeholder="设置这个好友的人格特征和行为准则，例如：你是一个温暖友善的朋友，喜欢倾听和给出建设性意见..." class="form-textarea" :rows="5" />
              <p class="form-hint">系统提示词决定了 AI 好友的人格和回复风格</p>
            </div>

            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 mt-2">
              <div class="space-y-0.5">
                <Label for="script-expression" class="text-sm font-medium">剧本式表达</Label>
                <p class="text-[11px] text-gray-500">让 AI 的回复包含动作、神态等环境描写</p>
              </div>
              <Switch id="script-expression" v-model="form.script_expression" />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="advanced" class="pt-4">
          <div class="space-y-4">
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-4 space-y-3">
              <div class="flex items-center justify-between">
                <div class="space-y-1">
                  <Label for="friend-temperature" class="text-sm font-medium">Temperature</Label>
                  <p class="text-[11px] text-gray-500">值越高回复更随机，值越低更稳定</p>
                </div>
                <Input id="friend-temperature" v-model.number="form.temperature" type="number" min="0" max="2" step="0.1"
                  class="w-24 h-8 text-xs text-right" @blur="normalizeTemperature" />
              </div>
              <div>
                <Slider :model-value="[form.temperature]" :min="0" :max="2" :step="0.1" class="py-3"
                  @update:model-value="(val) => { if (val) form.temperature = roundToStep(val[0], 0.1) }" />
                <div class="flex justify-between text-[11px] text-gray-400 mt-1">
                  <span>0.0</span>
                  <span>2.0</span>
                </div>
              </div>
            </div>

            <div class="rounded-lg border border-gray-100 bg-gray-50 p-4 space-y-3">
              <div class="flex items-center justify-between">
                <div class="space-y-1">
                  <Label for="friend-top-p" class="text-sm font-medium">Top-P</Label>
                  <p class="text-[11px] text-gray-500">控制采样范围，值越低越保守</p>
                </div>
                <Input id="friend-top-p" v-model.number="form.top_p" type="number" min="0" max="1" step="0.05"
                  class="w-24 h-8 text-xs text-right" @blur="normalizeTopP" />
              </div>
              <div>
                <Slider :model-value="[form.top_p]" :min="0" :max="1" :step="0.05" class="py-3"
                  @update:model-value="(val) => { if (val) form.top_p = roundToStep(val[0], 0.05) }" />
                <div class="flex justify-between text-[11px] text-gray-400 mt-1">
                  <span>0.0</span>
                  <span>1.0</span>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <DialogFooter>
        <Button variant="outline" @click="isOpen = false" :disabled="isSubmitting">取消</Button>
        <Button @click="handleConfirm" :disabled="!isFormValid || isSubmitting" class="confirm-btn">
          {{ isSubmitting ? (mode === 'add' ? '创建中...' : '保存中...') : (mode === 'add' ? '创建好友' : '保存修改') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Avatar Uploader -->
  <AvatarUploader v-if="isAvatarUploaderOpen" :title="mode === 'add' ? '设置好友头像' : '更换好友头像'"
    :initial-image="form.avatar ? getStaticUrl(form.avatar) : undefined" @update:image="handleAvatarUploaded"
    @close="isAvatarUploaderOpen = false" />
</template>

<style scoped>
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-label .required {
  color: #dc2626;
}

.form-input {
  font-size: 14px;
}

.form-textarea {
  font-size: 14px;
  resize: none;
  min-height: 100px;
}

.form-hint {
  font-size: 12px;
  color: #888;
  margin: 0;
}

.confirm-btn {
  background: #07c160;
}

.confirm-btn:hover:not(:disabled) {
  background: #06ad56;
}

.confirm-btn:disabled {
  background: #a0a0a0;
  cursor: not-allowed;
}
</style>
