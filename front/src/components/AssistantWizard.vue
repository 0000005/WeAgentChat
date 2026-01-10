<script setup lang="ts">
import { ref, computed } from 'vue'
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
import { Loader } from '@/components/ai-elements/loader'
import { Sparkles, ArrowRight, UserPlus, RefreshCw } from 'lucide-vue-next'
import {
  generatePersona,
  createFriendFromPayload,
  type PersonaGenerateResponse,
} from '@/api/friend-template'
import { useToast } from '@/composables/useToast'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import AvatarUploader from '@/components/common/AvatarUploader.vue'
import { Camera } from 'lucide-vue-next'

defineProps<{
  open: boolean
}>()

const emit = defineEmits(['update:open', 'success'])

const toast = useToast()
const sessionStore = useSessionStore()
const friendStore = useFriendStore()

const step = ref(1) // 1: Input, 2: Preview
const name = ref('')
const description = ref('')
const isGenerating = ref(false)
const isSaving = ref(false)
const isEditingPrompt = ref(false)
const generatedPersona = ref<PersonaGenerateResponse | null>(null)
const avatarUrl = ref<string | null>(null)
const isAvatarUploaderOpen = ref(false)

const canGoToPreview = computed(() => description.value.trim().length > 5)

const handleGenerate = async () => {
  if (!canGoToPreview.value) return

  isGenerating.value = true
  try {
    const res = await generatePersona({
      name: name.value || undefined,
      description: description.value,
    })
    generatedPersona.value = res
    step.value = 2
  } catch (error: any) {
    toast.error(error.message || '生成 AI 设定失败')
  } finally {
    isGenerating.value = false
  }
}

const handleConfirm = async () => {
  if (!generatedPersona.value) return

  isSaving.value = true
  try {
    const friend = await createFriendFromPayload({
      name: generatedPersona.value.name,
      description: generatedPersona.value.description,
      system_prompt: generatedPersona.value.system_prompt,
      initial_message: generatedPersona.value.initial_message,
      avatar: avatarUrl.value
    })

    // 强制同步 Store
    await friendStore.fetchFriends()

    toast.success(`好友「${friend.name}」创建成功`)
    emit('update:open', false)
    emit('success', friend)

    // 重置状态，确保下次打开时从头开始
    resetAll()

    // 跳转到聊天
    await sessionStore.selectFriend(friend.id)
  } catch (error: any) {
    toast.error(error.message || '保存好友失败')
  } finally {
    isSaving.value = false
  }
}

const reset = () => {
  step.value = 1
  generatedPersona.value = null
  isEditingPrompt.value = false
}

const resetAll = () => {
  step.value = 1
  name.value = ''
  description.value = ''
  generatedPersona.value = null
  isEditingPrompt.value = false
}

const handleClose = () => {
  emit('update:open', false)
  // 延迟重置，避免关闭动画时看到内容闪烁
  setTimeout(resetAll, 200)
}
</script>

<template>
  <Dialog :open="open" @update:open="(val) => emit('update:open', val)">
    <DialogContent class="max-w-[460px] overflow-hidden p-0 gap-0">
      <DialogHeader class="p-6 pb-2">
        <DialogTitle class="flex items-center gap-2 text-xl">
          <Sparkles class="w-5 h-5 text-green-600" />
          {{ step === 1 ? 'AI 伙伴创建向导' : '人格设定预览' }}
        </DialogTitle>
        <DialogDescription>
          {{
            step === 1
              ? '描述你想见到的 AI 伙伴，让 AI 帮你完成复杂的设定。'
              : '这是为您生成的好友设定，你可以重新生成或点击确认添加。'
          }}
        </DialogDescription>
      </DialogHeader>

      <div class="p-6 pt-2">
        <!-- Step 1: Input -->
        <div v-if="step === 1 && !isGenerating" class="space-y-5 py-2">
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">她/他叫什么名字？（可选）</label>
            <Input v-model="name" placeholder="例如：苏格拉底、隔壁王阿姨..." class="h-10 border-gray-200 focus-visible:ring-green-500" />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">性格与背景描述</label>
            <Textarea
              v-model="description"
              placeholder="例如：一个学识渊博但幽默的哲学老师，喜欢用反讽的方式引导我思考。说话风格温文尔雅，经常引用古典著作。"
              class="min-h-[140px] resize-none border-gray-200 focus-visible:ring-green-500 leading-relaxed"
            />
            <div class="flex justify-between items-center">
              <p class="text-[11px] text-gray-400">描述得越详细，生成的性格越鲜明。</p>
              <p class="text-[11px]" :class="canGoToPreview ? 'text-green-600' : 'text-gray-300'">
                已输入 {{ description.length }} 字
              </p>
            </div>
          </div>
        </div>

        <!-- Generating State -->
        <div v-if="isGenerating" class="flex flex-col items-center justify-center py-16 gap-5">
          <div class="relative">
            <Loader class="scale-150" />
            <Sparkles class="absolute -top-4 -right-4 w-6 h-6 text-yellow-400 animate-bounce" />
          </div>
          <div class="text-center">
            <p class="text-base font-semibold text-green-700">正在构思人格魅力...</p>
            <p class="text-xs text-gray-400 mt-1">这可能需要几秒钟时间</p>
          </div>
        </div>

        <!-- Step 2: Result Preview -->
        <div
          v-if="step === 2 && !isGenerating && generatedPersona"
          class="space-y-4 max-h-[440px] overflow-y-auto pr-2 py-2"
        >
          <div class="border rounded-xl p-5 bg-gradient-to-br from-green-50/50 to-white space-y-5 border-green-100/50 shadow-sm">
            <div class="flex items-center gap-4">
              <div
                class="w-14 h-14 rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center text-white font-bold text-2xl shadow-md shadow-green-200 cursor-pointer relative group overflow-hidden"
                @click="isAvatarUploaderOpen = true"
              >
                <img v-if="avatarUrl" :src="avatarUrl" class="w-full h-full object-cover" />
                <span v-else>{{ generatedPersona.name.charAt(0) }}</span>
                
                <div class="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <Camera class="text-white w-5 h-5" />
                </div>
              </div>
              <div class="min-w-0">
                <h3 class="font-bold text-lg text-gray-900 truncate">{{ generatedPersona.name }}</h3>
                <p class="text-xs text-gray-500 mt-1 line-clamp-1">{{ generatedPersona.description }}</p>
              </div>
            </div>

            <div class="space-y-2">
              <h4 class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">完整简介</h4>
              <p class="text-sm text-gray-600 leading-relaxed">
                {{ generatedPersona.description }}
              </p>
            </div>

            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <h4 class="text-[10px] font-bold text-green-600 uppercase tracking-wider">人格设定 (System Prompt)</h4>
                <button
                  v-if="!isEditingPrompt"
                  @click="isEditingPrompt = true"
                  class="text-[10px] text-green-600 hover:text-green-700 hover:underline"
                >
                  点击编辑
                </button>
                <button
                  v-else
                  @click="isEditingPrompt = false"
                  class="text-[10px] text-gray-500 hover:text-gray-600 hover:underline"
                >
                  完成编辑
                </button>
              </div>
              <Textarea
                v-if="isEditingPrompt"
                v-model="generatedPersona.system_prompt"
                class="min-h-[160px] text-xs text-gray-600 leading-relaxed resize-none border-green-200 focus-visible:ring-green-500 bg-white"
              />
              <div
                v-else
                @click="isEditingPrompt = true"
                class="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap bg-white/60 p-3 rounded-lg border border-green-100/50 cursor-pointer hover:bg-green-50/50 transition-colors max-h-[160px] overflow-y-auto"
              >
                {{ generatedPersona.system_prompt }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="p-6 pt-0 flex gap-3 sm:justify-end">
        <template v-if="step === 1 && !isGenerating">
          <Button variant="ghost" @click="handleClose" class="text-gray-500 h-10 px-6">取消</Button>
          <Button
            :disabled="!canGoToPreview"
            @click="handleGenerate"
            class="bg-green-600 hover:bg-green-700 shadow-md shadow-green-100 h-10 px-8 transition-all hover:translate-x-1"
          >
            开始生成
            <ArrowRight class="ml-2 w-4 h-4" />
          </Button>
        </template>

        <template v-if="step === 2 && !isGenerating">
          <Button variant="outline" @click="reset" class="border-gray-200 text-gray-600 h-10 px-6 hover:bg-gray-50">
            <RefreshCw class="mr-2 w-4 h-4" />
            不满意，重写
          </Button>
          <Button
            :disabled="isSaving"
            @click="handleConfirm"
            class="bg-green-600 hover:bg-green-700 shadow-md shadow-green-100 h-10 px-8"
          >
            <UserPlus v-if="!isSaving" class="mr-2 w-4 h-4" />
            <Loader v-else class="mr-2 h-4 w-4" />
            确认添加好友
          </Button>
        </template>
      </DialogFooter>
    </DialogContent>
  </Dialog>
  
  <AvatarUploader
    v-if="isAvatarUploaderOpen"
    :title="`为 ${generatedPersona?.name || '伙伴'} 设置头像`"
    @update:image="(url) => avatarUrl = url"
    @close="isAvatarUploaderOpen = false"
  />
</template>

<style scoped>
/* 自定义滚动条 */
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 999px;
}
.overflow-y-auto:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
}
</style>
