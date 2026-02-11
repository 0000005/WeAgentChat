<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
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
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Sparkles, ArrowRight, UserPlus, RefreshCw } from 'lucide-vue-next'
import { generatePersonaStream, type PersonaGenerateResponse } from '@/api/friend-template'
import { useToast } from '@/composables/useToast'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import AvatarUploader from '@/components/common/AvatarUploader.vue'
import { Camera, Search, MessageCircleQuestion, Globe } from 'lucide-vue-next'
import { recommendFriendsStream, type FriendRecommendationItem } from '@/api/friend'

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
const scriptExpression = ref(false)
const streamingText = ref('')
const streamContent = ref('')
const streamTimer = ref<number | null>(null)
const streamController = ref<AbortController | null>(null)

// Topic Search State
const currentTab = ref<'manual' | 'topic'>('manual')
const topicInput = ref('')
const isRecommending = ref(false)
const recommendations = ref<FriendRecommendationItem[]>([])
const recommendError = ref<string | null>(null)
const recommendController = ref<AbortController | null>(null)


const fetchRecommendations = async (isRefresh: boolean) => {
  const topic = topicInput.value.trim()
  if (!topic) return
  
  // 输入验证
  if (topic.length < 2) {
    toast.error('话题至少需要2个字符')
    return
  }
  if (topic.length > 200) {
    toast.error('话题长度不能超过200字符')
    return
  }
  
  // 取消之前的流式请求（复用 stopStream）
  stopStream()
  
  // 获取当前已有人选（如果是"换一批"）
  const excludeNames = isRefresh ? recommendations.value.map(r => r.name) : []
  
  isRecommending.value = true
  if (!isRefresh) {
    recommendations.value = []
  }
  recommendError.value = null
  streamingText.value = ''
  streamContent.value = ''
  
  const controller = new AbortController()
  recommendController.value = controller
  // 同时更新 streamController 以便 stopStream 能正确清理
  streamController.value = controller
  
  try {
    // 启动定时器，每2秒更新一次显示文本（取最后40个字符）
    streamTimer.value = window.setInterval(() => {
      if (!streamContent.value) return
      streamingText.value = streamContent.value.slice(-40)
    }, 2000)
    
    // 使用流式 API
    for await (const { event, data } of recommendFriendsStream(topic, excludeNames, { signal: controller.signal })) {
      if (event === 'delta') {
        // 累积流式文本（最多保留400字符）
        streamContent.value += data.delta || ''
        if (streamContent.value.length > 400) {
          streamContent.value = streamContent.value.slice(-400)
        }
      } else if (event === 'result') {
        // 最终结果
        const items = data.recommendations || []
        if (items.length === 0) {
          if (isRefresh) {
            toast.info('没有更多推荐了')
          } else {
            recommendError.value = '未找到相关推荐，请尝试其他话题'
          }
        } else {
          recommendations.value = items
        }
        stopStream()
      } else if (event === 'error') {
        const errorMsg = data.detail || '获取推荐失败'
        if (isRefresh) {
          toast.error(errorMsg)
        } else {
          recommendError.value = errorMsg
        }
        stopStream()
        break
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') return
    const errorMsg = error.message || '获取推荐失败'
    if (isRefresh) {
      toast.error(errorMsg)
    } else {
      recommendError.value = errorMsg
    }
  } finally {
    if (recommendController.value === controller) {
      isRecommending.value = false
      recommendController.value = null
      streamController.value = null
      streamingText.value = ''
      streamContent.value = ''
      if (streamTimer.value !== null) {
        window.clearInterval(streamTimer.value)
        streamTimer.value = null
      }
    }
  }
}

const handleRecommend = () => fetchRecommendations(false)
const handleRefresh = () => fetchRecommendations(true)

const handleSearchPerson = (event: Event, name: string) => {
  event.stopPropagation() // 阻止点击卡片触发应用推荐
  const url = `https://www.baidu.com/s?wd=${encodeURIComponent(name)}`
  window.open(url, '_blank')
}

const applyRecommendation = (item: FriendRecommendationItem) => {
  name.value = item.name
  description.value = item.description_hint
  currentTab.value = 'manual'
  // 提示用户可以修改
  toast.success(`已为您填充「${item.name}」的信息，可按需修改后生成`)
}

const canGoToPreview = computed(() => description.value.trim().length > 5)

const stopStream = () => {
  if (streamController.value) {
    streamController.value.abort()
    streamController.value = null
  }
  if (streamTimer.value !== null) {
    window.clearInterval(streamTimer.value)
    streamTimer.value = null
  }
}

const handleGenerate = async () => {
  if (!canGoToPreview.value) return

  isGenerating.value = true
  streamingText.value = ''
  streamContent.value = ''
  stopStream()
  const controller = new AbortController()
  streamController.value = controller
  try {
    streamTimer.value = window.setInterval(() => {
      if (!streamContent.value) return
      streamingText.value = streamContent.value.slice(-40)
    }, 2000)

    for await (const { event, data } of generatePersonaStream({
      name: name.value || undefined,
      description: description.value,
    }, { signal: controller.signal })) {
      if (event === 'delta') {
        const delta = typeof data?.delta === 'string' ? data.delta : ''
        if (delta) {
          streamContent.value += delta
          if (streamContent.value.length > 400) {
            streamContent.value = streamContent.value.slice(-400)
          }
        }
      } else if (event === 'result') {
        generatedPersona.value = data
        step.value = 2
        stopStream()
      } else if (event === 'error') {
        throw new Error(data?.detail || '生成 AI 设定失败')
      }
    }
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      toast.error(error.message || '生成 AI 设定失败')
    }
  } finally {
    isGenerating.value = false
    if (streamController.value === controller) {
      streamController.value = null
    }
  }
}

const handleConfirm = async () => {
  if (!generatedPersona.value) return

  isSaving.value = true
  try {
    const friend = await friendStore.addFriend({
      name: generatedPersona.value.name,
      description: generatedPersona.value.description,
      system_prompt: generatedPersona.value.system_prompt,
      avatar: avatarUrl.value || undefined,
      script_expression: scriptExpression.value,
      is_preset: false
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
  scriptExpression.value = false
  streamingText.value = ''
  streamContent.value = ''
  stopStream()
  // 重置推荐状态
  currentTab.value = 'manual'
  topicInput.value = ''
  recommendations.value = []
  recommendError.value = null
  if (recommendController.value) {
    recommendController.value.abort()
    recommendController.value = null
  }
}

const handleClose = () => {
  emit('update:open', false)
  stopStream()
  // 延迟重置，避免关闭动画时看到内容闪烁
  setTimeout(resetAll, 200)
}

onBeforeUnmount(() => {
  stopStream()
})
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
        <!-- Step 1: Input (Manual & Topic Tabs) -->
        <div v-if="step === 1 && !isGenerating" class="py-2">
          
          <!-- Custom Tabs -->
          <div class="flex p-1 bg-gray-100/80 rounded-lg mb-5 mx-1">
            <button 
              @click="currentTab = 'manual'"
              class="flex-1 text-sm font-medium py-1.5 rounded-md transition-all duration-200"
              :class="currentTab === 'manual' ? 'bg-white text-green-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
            >
              自定义创建
            </button>
             <button 
              @click="currentTab = 'topic'"
              class="flex-1 text-sm font-medium py-1.5 rounded-md transition-all duration-200"
              :class="currentTab === 'topic' ? 'bg-white text-green-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
            >
              话题找人
            </button>
          </div>

          <!-- Manual Tab Content -->
          <div v-if="currentTab === 'manual'" class="space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div class="space-y-2">
              <label class="text-sm font-semibold text-gray-700">她/他叫什么名字？（可选）</label>
              <Input v-model="name" placeholder="例如：苏格拉底、隔壁王阿姨..."
                class="h-10 border-gray-200 focus-visible:ring-green-500" />
            </div>
            <div class="space-y-2">
              <label class="text-sm font-semibold text-gray-700">性格与背景描述</label>
              <Textarea v-model="description" placeholder="例如：一个学识渊博但幽默的哲学老师，喜欢用反讽的方式引导我思考。说话风格温文尔雅，经常引用古典著作。"
                class="min-h-[140px] resize-none border-gray-200 focus-visible:ring-green-500 leading-relaxed" />
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 mt-2">
                <div class="space-y-0.5">
                  <Label for="script-expression-wizard" class="text-sm font-medium">剧本式表达</Label>
                  <p class="text-[11px] text-gray-500">让 AI 的回复包含动作、神态等环境描写</p>
                </div>
                <Switch id="script-expression-wizard" v-model="scriptExpression" />
              </div>
              <div class="flex justify-between items-center">
                <p class="text-[11px] text-gray-400">描述得越详细，生成的性格越鲜明。</p>
                <p class="text-[11px]" :class="canGoToPreview ? 'text-green-600' : 'text-gray-300'">
                  已输入 {{ description.length }} 字
                </p>
              </div>
            </div>
          </div>

          <!-- Topic Tab Content -->
          <div v-else class="space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300 min-h-[300px]">
             <div class="space-y-2">
               <label class="text-sm font-semibold text-gray-700">你想聊什么话题？</label>
               <div class="flex gap-2">
                 <Input v-model="topicInput" @keyup.enter="handleRecommend" placeholder="例如：量子力学、如何失恋走出来、三体..." 
                   class="h-10 border-gray-200 focus-visible:ring-green-500" />
                 <Button @click="handleRecommend" :disabled="isRecommending || !topicInput.trim()"
                   class="bg-green-600 hover:bg-green-700 shadow-sm w-12 px-0 shrink-0">
                   <Loader v-if="isRecommending" class="w-4 h-4" />
                   <Search v-else class="w-4 h-4" />
                 </Button>
               </div>
             </div>

             <!-- Topic Suggestions / Empty State -->
             <div v-if="!recommendations.length && !isRecommending" class="flex flex-col items-center justify-center py-8 text-center text-gray-400 space-y-3">
                <div class="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
                   <MessageCircleQuestion class="w-6 h-6 text-gray-300" />
                </div>
                <div class="text-xs">
                  <p>输入你感兴趣的话题</p>
                  <p class="mt-1">AI 将为你推荐最适合讨论的伙伴</p>
                </div>
             </div>

             <!-- Loading State -->
             <div v-if="isRecommending" class="flex flex-col items-center justify-center py-12 space-y-4">
                <Loader class="scale-125 text-green-600" />
                <p class="text-xs text-gray-400">正在寻找合适的人选...</p>
                
                <!-- 跑马灯流式文本展示区域 -->
                <div class="w-full max-w-[320px] overflow-hidden rounded-lg border border-green-100 bg-green-50 px-3 py-2">
                  <div class="marquee-track text-sm text-green-700">
                    <span>{{ streamingText || '正在匹配最佳人选...' }}</span>
                    <span aria-hidden="true">{{ streamingText || '正在匹配最佳人选...' }}</span>
                  </div>
                </div>
             </div>

             <!-- Error State -->
             <div v-if="recommendError && !isRecommending" class="flex flex-col items-center justify-center py-8 text-center space-y-3">
                <div class="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
                   <MessageCircleQuestion class="w-6 h-6 text-red-400" />
                </div>
                <div class="text-xs">
                  <p class="text-red-600 font-medium">{{ recommendError }}</p>
                  <button @click="handleRecommend" class="mt-2 text-green-600 hover:underline text-[11px]">
                    点击重试
                  </button>
                </div>
             </div>

             <!-- Results List -->
             <div v-if="recommendations.length > 0 && !isRecommending && !recommendError" class="space-y-3">
                <div class="flex items-center justify-between px-1">
                   <span class="text-[10px] text-gray-400 font-medium uppercase tracking-wider">推荐人选</span>
                   <button 
                     @click="handleRefresh" 
                     :disabled="isRecommending"
                     class="text-[10px] text-green-600 hover:text-green-700 font-bold flex items-center gap-1 active:scale-95 transition-transform disabled:opacity-50"
                   >
                     <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': isRecommending }" />
                     换一批
                   </button>
                </div>
                
                <div class="max-h-[260px] overflow-y-auto pr-1 space-y-3">
                  <div v-for="(item, idx) in recommendations" :key="idx" 
                    @click="applyRecommendation(item)"
                    class="group p-3 rounded-lg border border-gray-100 hover:border-green-200 hover:bg-green-50/50 cursor-pointer transition-all duration-200 space-y-1 relative overflow-hidden"
                  >
                    <!-- Decorative gradient line -->
                    <div class="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-green-400 to-emerald-600 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    
                    <div class="flex justify-between items-start">
                      <div class="flex items-center gap-2">
                        <h4 class="font-bold text-gray-800 text-sm group-hover:text-green-800">{{ item.name }}</h4>
                        <button 
                          @click.stop="handleSearchPerson($event, item.name)"
                          class="p-1 rounded-full text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors tooltip-search"
                          title="在百度中搜索"
                        >
                          <Globe class="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <span class="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded group-hover:bg-white group-hover:text-green-600 transition-colors">推荐</span>
                    </div>
                    <p class="text-xs text-gray-500 leading-relaxed group-hover:text-gray-600">{{ item.reason }}</p>
                  </div>
                </div>
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
            <p class="text-xs text-gray-400 mt-1">这可能需要1分钟左右的时间</p>
          </div>
          <div class="w-full max-w-[320px] overflow-hidden rounded-lg border border-green-100 bg-green-50 px-3 py-2">
            <div class="marquee-track text-sm text-green-700">
              <span>{{ streamingText || '正在生成角色设定...' }}</span>
              <span aria-hidden="true">{{ streamingText || '正在生成角色设定...' }}</span>
            </div>
          </div>
        </div>

        <!-- Step 2: Result Preview -->
        <div v-if="step === 2 && !isGenerating && generatedPersona"
          class="space-y-4 max-h-[440px] overflow-y-auto pr-2 py-2">
          <div
            class="border rounded-xl p-5 bg-gradient-to-br from-green-50/50 to-white space-y-5 border-green-100/50 shadow-sm">
            <div class="flex items-center gap-4">
              <div
                class="w-14 h-14 rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center text-white font-bold text-2xl shadow-md shadow-green-200 cursor-pointer relative group overflow-hidden"
                @click="isAvatarUploaderOpen = true">
                <img v-if="avatarUrl" :src="avatarUrl" class="w-full h-full object-cover" />
                <span v-else>{{ generatedPersona.name.charAt(0) }}</span>

                <div
                  class="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
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
                <button v-if="!isEditingPrompt" @click="isEditingPrompt = true"
                  class="text-[10px] text-green-600 hover:text-green-700 hover:underline">
                  点击编辑
                </button>
                <button v-else @click="isEditingPrompt = false"
                  class="text-[10px] text-gray-500 hover:text-gray-600 hover:underline">
                  完成编辑
                </button>
              </div>
              <Textarea v-if="isEditingPrompt" v-model="generatedPersona.system_prompt"
                class="min-h-[160px] text-xs text-gray-600 leading-relaxed resize-none border-green-200 focus-visible:ring-green-500 bg-white" />
              <div v-else @click="isEditingPrompt = true"
                class="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap bg-white/60 p-3 rounded-lg border border-green-100/50 cursor-pointer hover:bg-green-50/50 transition-colors max-h-[160px] overflow-y-auto">
                {{ generatedPersona.system_prompt }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter class="p-6 pt-0 flex gap-3 sm:justify-end">
        <template v-if="step === 1 && !isGenerating">
          <Button variant="ghost" @click="handleClose" class="text-gray-500 h-10 px-6">取消</Button>
          <Button :disabled="!canGoToPreview" @click="handleGenerate"
            class="bg-green-600 hover:bg-green-700 shadow-md shadow-green-100 h-10 px-8 transition-all hover:translate-x-1">
            开始生成
            <ArrowRight class="ml-2 w-4 h-4" />
          </Button>
        </template>

        <template v-if="step === 2 && !isGenerating">
          <Button variant="outline" @click="reset" class="border-gray-200 text-gray-600 h-10 px-6 hover:bg-gray-50">
            <RefreshCw class="mr-2 w-4 h-4" />
            不满意，重写
          </Button>
          <Button :disabled="isSaving" @click="handleConfirm"
            class="bg-green-600 hover:bg-green-700 shadow-md shadow-green-100 h-10 px-8">
            <UserPlus v-if="!isSaving" class="mr-2 w-4 h-4" />
            <Loader v-else class="mr-2 h-4 w-4" />
            确认添加好友
          </Button>
        </template>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <AvatarUploader v-if="isAvatarUploaderOpen" :title="`为 ${generatedPersona?.name || '伙伴'} 设置头像`"
    @update:image="(url: string) => avatarUrl = url" @close="isAvatarUploaderOpen = false" />
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

.marquee-track {
  display: flex;
  gap: 2rem;
  width: max-content;
  white-space: nowrap;
  animation: marquee 8s linear infinite;
}

@keyframes marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}
</style>
