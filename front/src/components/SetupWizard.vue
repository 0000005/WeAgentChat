<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader } from '@/components/ai-elements/loader'
import {
  Rocket,
  Settings2,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  ShieldCheck,
  Zap,
  AlertCircle
} from 'lucide-vue-next'
import { useLlmStore } from '@/stores/llm'
import { useEmbeddingStore } from '@/stores/embedding'
import { useSettingsStore } from '@/stores/settings'
import { useMemoryStore } from '@/stores/memory'
import { useFriendStore } from '@/stores/friend'
import { getFriendTemplates } from '@/api/friend-template'
import { useToast } from '@/composables/useToast'

interface Props {
  open: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['update:open', 'complete'])

const toast = useToast()
const llmStore = useLlmStore()
const embeddingStore = useEmbeddingStore()
const settingsStore = useSettingsStore()
const memoryStore = useMemoryStore()
const friendStore = useFriendStore()

const step = ref(1)
const isTesting = ref(false)
const isSaving = ref(false)
const gender = ref<'男' | '女' | ''>('')
const isGenderInitialized = ref(false)
const llmConfigId = ref<number | null>(null)
const embeddingConfigId = ref<number | null>(null)

const llmDraft = ref({
  provider: 'openai',
  config_name: 'OpenAI',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  model_name: 'gpt-4o-mini'
})

const embeddingDraft = ref({
  config_name: 'OpenAI',
  embedding_provider: 'openai',
  embedding_api_key: '',
  embedding_base_url: '',
  embedding_dim: 1536,
  embedding_model: 'text-embedding-3-small'
})

// Step transitions logic
const nextStep = async () => {
  if (step.value === 1 && !isGenderInitialized.value) {
    try {
      isSaving.value = true
      await ensureGenderProfile()
      await ensureDefaultFriend()
      isGenderInitialized.value = true
    } catch (error: any) {
      toast.error(error.message || '性别保存失败')
      return
    } finally {
      isSaving.value = false
    }
  }
  if (step.value < 4) step.value++
}

const prevStep = () => {
  if (step.value > 1) step.value--
}

// LLM Test & Save
const testLlm = async () => {
  isTesting.value = true
  try {
    const res = await llmStore.testConfig({
      base_url: llmDraft.value.base_url || null,
      api_key: llmDraft.value.api_key || null,
      model_name: llmDraft.value.model_name || 'gpt-3.5-turbo'
    })
    if (res.success) {
      toast.success('LLM 连接测试成功！')
    } else {
      toast.error('LLM 连接测试失败')
    }
  } catch (error: any) {
    toast.error(error.message || '测试失败')
  } finally {
    isTesting.value = false
  }
}

// Embedding Test & Save
const testEmbedding = async () => {
  isTesting.value = true
  try {
    const res = await embeddingStore.testConfig({
      embedding_provider: embeddingDraft.value.embedding_provider,
      embedding_api_key: embeddingDraft.value.embedding_api_key || null,
      embedding_base_url: embeddingDraft.value.embedding_base_url || null,
      embedding_dim: embeddingDraft.value.embedding_dim,
      embedding_model: embeddingDraft.value.embedding_model,
      embedding_max_token_size: 8000
    })
    if (res.success) {
      toast.success('Embedding 连接测试成功！')
    } else {
      toast.error('Embedding 连接测试失败')
    }
  } catch (error: any) {
    toast.error(error.message || '测试失败')
  } finally {
    isTesting.value = false
  }
}

const ensureGenderProfile = async () => {
  if (!gender.value) return
  await memoryStore.fetchProfiles()
  const topic = '基本信息'
  const content = `性别：${gender.value}`
  const existing = memoryStore.profiles.find(
    p => p.attributes.topic === topic && p.content.startsWith('性别：')
  )
  await memoryStore.upsertProfile(existing?.id ?? null, content, { topic })
}

const ensureDefaultFriend = async () => {
  if (!gender.value) return
  const targetName = gender.value === '男' ? '灵儿' : '俊哥'
  await friendStore.fetchFriends()
  if (friendStore.friends.some(f => f.name === targetName)) return
  const templates = await getFriendTemplates({ q: targetName })
  const match = templates.find(t => t.name === targetName)
  if (!match) {
    throw new Error(`未找到默认好友模板：${targetName}`)
  }
  await friendStore.cloneFromTemplate(match.id)
}

const hydrateGenderFromProfile = async () => {
  await memoryStore.fetchProfiles()
  const existing = memoryStore.profiles.find(
    p => p.attributes.topic === '基本信息' && p.content.startsWith('性别：')
  )
  if (existing) {
    const value = existing.content.replace('性别：', '').trim() as '男' | '女'
    if (value === '男' || value === '女') {
      gender.value = value
      isGenderInitialized.value = true
    }
  }
}

const completeSetup = async () => {
  isSaving.value = true
  try {
    if (llmConfigId.value) {
      await llmStore.updateConfig(llmConfigId.value, {
        provider: llmDraft.value.provider,
        config_name: llmDraft.value.config_name,
        base_url: llmDraft.value.base_url || null,
        api_key: llmDraft.value.api_key || null,
        model_name: llmDraft.value.model_name || 'gpt-3.5-turbo'
      })
    } else {
      const created = await llmStore.createConfig({
        provider: llmDraft.value.provider,
        config_name: llmDraft.value.config_name,
        base_url: llmDraft.value.base_url || null,
        api_key: llmDraft.value.api_key || null,
        model_name: llmDraft.value.model_name || 'gpt-3.5-turbo'
      })
      llmConfigId.value = created.id ?? null
    }

    if (embeddingConfigId.value) {
      await embeddingStore.updateConfig(embeddingConfigId.value, {
        config_name: embeddingDraft.value.config_name,
        embedding_provider: embeddingDraft.value.embedding_provider,
        embedding_api_key: embeddingDraft.value.embedding_api_key || null,
        embedding_base_url: embeddingDraft.value.embedding_base_url || null,
        embedding_dim: embeddingDraft.value.embedding_dim,
        embedding_model: embeddingDraft.value.embedding_model,
        embedding_max_token_size: 8000
      })
    } else {
      const created = await embeddingStore.createConfig({
        config_name: embeddingDraft.value.config_name,
        embedding_provider: embeddingDraft.value.embedding_provider,
        embedding_api_key: embeddingDraft.value.embedding_api_key || null,
        embedding_base_url: embeddingDraft.value.embedding_base_url || null,
        embedding_dim: embeddingDraft.value.embedding_dim,
        embedding_model: embeddingDraft.value.embedding_model,
        embedding_max_token_size: 8000
      })
      embeddingConfigId.value = created.id ?? null
    }

    if (llmConfigId.value) {
      settingsStore.activeLlmConfigId = llmConfigId.value
      await settingsStore.saveChatSettings()
    }
    if (embeddingConfigId.value) {
      settingsStore.activeEmbeddingConfigId = embeddingConfigId.value
      await settingsStore.saveMemorySettings()
    }
    await ensureGenderProfile()
    await ensureDefaultFriend()

    toast.success('配置已保存，欢迎使用 WeAgentChat！')
    emit('complete')
    emit('update:open', false)
  } catch (error: any) {
    toast.error(error.message || '保存配置失败')
  } finally {
    isSaving.value = false
  }
}

const embeddingKeyRequired = computed(() => {
  return ['openai', 'jina'].includes(embeddingDraft.value.embedding_provider)
})

const canGoNext = computed(() => {
  if (step.value === 1) {
    return !!gender.value && !isSaving.value
  }
  if (step.value === 2) {
    return !!llmDraft.value.api_key && !!llmDraft.value.model_name
  }
  if (step.value === 3) {
    return !!embeddingDraft.value.embedding_model && (!embeddingKeyRequired.value || !!embeddingDraft.value.embedding_api_key)
  }
  return true
})

onMounted(async () => {
  // Try to load existing configs if any
  await Promise.all([
    llmStore.fetchConfigs(),
    embeddingStore.fetchConfigs(),
    settingsStore.fetchChatSettings(),
    settingsStore.fetchMemorySettings()
  ])

  const activeLlm = llmStore.getConfigById(settingsStore.activeLlmConfigId) || llmStore.configs[0] || null
  const activeEmbedding = embeddingStore.getConfigById(settingsStore.activeEmbeddingConfigId) || embeddingStore.configs[0] || null

  if (activeLlm) {
    llmConfigId.value = activeLlm.id ?? null
    llmDraft.value = {
      provider: activeLlm.provider || 'openai',
      config_name: activeLlm.config_name || 'OpenAI',
      base_url: activeLlm.base_url || 'https://api.openai.com/v1',
      api_key: activeLlm.api_key || '',
      model_name: activeLlm.model_name || 'gpt-3.5-turbo'
    }
  }

  if (activeEmbedding) {
    embeddingConfigId.value = activeEmbedding.id ?? null
    embeddingDraft.value = {
      config_name: activeEmbedding.config_name || 'OpenAI',
      embedding_provider: activeEmbedding.embedding_provider || 'openai',
      embedding_api_key: activeEmbedding.embedding_api_key || '',
      embedding_base_url: activeEmbedding.embedding_base_url || '',
      embedding_dim: activeEmbedding.embedding_dim || 1536,
      embedding_model: activeEmbedding.embedding_model || 'text-embedding-3-small'
    }
  }
  await hydrateGenderFromProfile()
  if (isGenderInitialized.value) {
    step.value = 2
  }
})

const openTutorial = () => {
  // Robustly determine base URL ensuring file:// compatibility
  const baseUrl = window.location.href.split('#')[0].substring(0, window.location.href.split('#')[0].lastIndexOf('/') + 1)
  const url = `${baseUrl}configuration_doc.pdf`

  if ((window as any).WeAgentChat?.shell?.openExternal) {
    (window as any).WeAgentChat.shell.openExternal(url)
  } else {
    window.open(url, '_blank')
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(val) => (isSaving || !isGenderInitialized) ? null : emit('update:open', val)">
    <DialogContent class="max-w-[500px] p-0 gap-0 overflow-hidden border-none shadow-2xl">
      <!-- Gradient Header Area -->
      <div class="h-32 bg-gradient-to-br from-green-600 to-emerald-700 p-8 flex items-end relative overflow-hidden">
        <div class="absolute -top-10 -right-10 w-40 h-40 bg-white/10 rounded-full blur-3xl"></div>
        <div class="absolute top-4 right-4 text-white/20">
          <Zap v-if="step === 1" class="w-16 h-16" />
          <BrainCircuit v-if="step === 2" class="w-16 h-16" />
          <Settings2 v-if="step === 3" class="w-16 h-16" />
          <CheckCircle2 v-if="step === 4" class="w-16 h-16" />
        </div>
        <div class="z-10">
          <h2 class="text-2xl font-bold text-white leading-tight">
            {{ step === 1 ? '欢迎使用 WeAgentChat' :
              step === 2 ? '配置对话大模型 (LLM)' :
                step === 3 ? '配置向量模型 (Embedding)' :
                  '一切准备就绪' }}
          </h2>
          <p class="text-green-100 text-sm mt-1 opacity-90">
            {{ step === 1 ? '您的私人 AI 社交沙盒' :
              step === 2 ? '这是 AI 伙伴的大脑，用于日常对话' :
                step === 3 ? '这是 AI 伙伴的记忆系统，用于存取历史信息' :
                  '开启您的第一个 AI 社交实验' }}
          </p>
        </div>
      </div>

      <!-- Content Area -->
      <div class="p-8 min-h-[380px]">
        <!-- Step 1: Welcome -->
        <div v-if="step === 1" class="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div class="flex items-start gap-4 p-4 rounded-xl bg-green-50/50 border border-green-100">
            <div
              class="w-10 h-10 rounded-lg bg-green-500 flex items-center justify-center text-white shrink-0 shadow-sm">
              <ShieldCheck class="w-6 h-6" />
            </div>
            <div>
              <h4 class="font-bold text-gray-900">数据隐私安全</h4>
              <p class="text-sm text-gray-500 mt-0.5">WeAgentChat 是一个本地运行的应用。除了您配置的 API 调用外，您的聊天记录和数据永远留在本地。</p>
            </div>
          </div>
          <div class="flex items-start gap-4 p-4 rounded-xl bg-emerald-50/50 border border-emerald-100">
            <div
              class="w-10 h-10 rounded-lg bg-emerald-500 flex items-center justify-center text-white shrink-0 shadow-sm">
              <Sparkles class="w-6 h-6" />
            </div>
            <div>
              <h4 class="font-bold text-gray-900">双轨记忆系统</h4>
              <p class="text-sm text-gray-500 mt-0.5">AI 伙伴会记住您的习惯与点滴，模拟真实的社交反馈。这需要您配置一个向量模型来支持高效检索。</p>
            </div>
          </div>
          <div v-if="!isGenderInitialized" class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">
              性别 <span class="text-red-500">*</span>
            </label>
            <Select v-model="gender">
              <SelectTrigger class="border-gray-200">
                <SelectValue placeholder="请选择性别" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="男">男</SelectItem>
                <SelectItem value="女">女</SelectItem>
              </SelectContent>
            </Select>
            <p class="text-[10px] text-gray-400">用于初始化默认好友与个人档案</p>
          </div>
          <div v-else class="rounded-lg border border-green-100 bg-green-50/50 px-4 py-3 text-sm text-gray-600">
            已设置性别：<span class="font-semibold text-gray-800">{{ gender }}</span>
          </div>
          <p class="text-sm text-gray-400 text-center pt-4">为了开始体验，我们需要几分钟时间来配置您的 AI 后端服务。</p>
        </div>

        <!-- Step 2: LLM Config -->
        <div v-if="step === 2" class="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">API Key</label>
            <Input v-model="llmDraft.api_key" type="password" placeholder="sk-..."
              class="border-gray-200 focus:ring-green-500" />
            <p class="text-[10px] text-gray-400">目前仅支持 OpenAI 兼容接口</p>
          </div>
          <div class="flex justify-end">
            <button class="text-xs text-green-600 hover:underline flex items-center" @click="openTutorial">
              <span class="mr-1">👉</span> 不知道如何配置？查看教程
            </button>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">Base URL (可选)</label>
            <Input v-model="llmDraft.base_url" placeholder="https://api.openai.com/v1" class="border-gray-200" />
            <p class="text-[10px] text-gray-400">如果使用代理或国内厂商，请填入相应的接口地址</p>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">模型名称</label>
            <Input v-model="llmDraft.model_name" placeholder="gpt-4o-mini" class="border-gray-200" />
          </div>
          <div class="pt-2">
            <Button variant="outline" size="sm" @click="testLlm" :disabled="isTesting || !llmDraft.api_key"
              class="w-full text-xs h-9 border-dashed border-gray-300 hover:border-green-500 hover:text-green-600 transition-colors">
              <Loader v-if="isTesting" class="mr-2 h-3 w-3" />
              <Zap v-else class="mr-2 h-3 w-3" />
              {{ isTesting ? '正在测试连接...' : '测试连接' }}
            </Button>
          </div>
        </div>

        <!-- Step 3: Embedding Config -->
        <div v-if="step === 3" class="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
          <div class="flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-100 text-amber-800">
            <AlertCircle class="w-4 h-4 mt-0.5 shrink-0" />
            <p class="text-xs font-medium leading-normal">如果未正确配置向量化模型，记忆系统将无法正常工作。</p>
          </div>
          <div class="flex justify-end -mt-2">
            <button class="text-xs text-green-600 hover:underline flex items-center" @click="openTutorial">
              <span class="mr-1">👉</span> 查看配置教程
            </button>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">Provider 服务商</label>
            <Select v-model="embeddingDraft.embedding_provider">
              <SelectTrigger class="border-gray-200">
                <SelectValue placeholder="选择服务商" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="openai">OpenAI (兼容)</SelectItem>
                <SelectItem value="jina">Jina AI</SelectItem>
                <SelectItem value="ollama">Ollama (本地)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">API Key</label>
            <Input v-model="embeddingDraft.embedding_api_key" type="password" placeholder="sk-..."
              class="border-gray-200" />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-gray-700">Base URL (可选)</label>
            <Input v-model="embeddingDraft.embedding_base_url" placeholder="https://api.openai.com/v1"
              class="border-gray-200" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <label class="text-sm font-semibold text-gray-700">模型名称</label>
              <Input v-model="embeddingDraft.embedding_model" placeholder="text-embedding-3-small"
                class="border-gray-200" />
            </div>
            <div class="space-y-2">
              <label class="text-sm font-semibold text-gray-700">维度 (Dimensions)</label>
              <Input v-model.number="embeddingDraft.embedding_dim" placeholder="1536" type="number"
                class="border-gray-200" />
            </div>
          </div>
          <div class="pt-2">
            <Button variant="outline" size="sm" @click="testEmbedding"
              :disabled="isTesting || (embeddingKeyRequired && !embeddingDraft.embedding_api_key)"
              class="w-full text-xs h-9 border-dashed border-gray-300 hover:border-green-500 hover:text-green-600 transition-colors">
              <Loader v-if="isTesting" class="mr-2 h-3 w-3" />
              <Zap v-else class="mr-2 h-3 w-3" />
              {{ isTesting ? '正在测试连接...' : '测试连接' }}
            </Button>
          </div>
        </div>

        <!-- Step 4: Success -->
        <div v-if="step === 4"
          class="flex flex-col items-center justify-center space-y-6 pt-4 animate-in zoom-in-95 duration-500">
          <div class="w-24 h-24 rounded-full bg-green-100 flex items-center justify-center text-green-600 shadow-inner">
            <Rocket class="w-12 h-12" />
          </div>
          <div class="text-center space-y-2">
            <h3 class="text-xl font-bold text-gray-900">太棒了！配置完成</h3>
            <p class="text-sm text-gray-500 max-w-[320px] mx-auto">
              我们将根据您的配置初始化记忆中心和 AI 运行时环境。这可能需要一点点时间。
            </p>
          </div>
          <div class="w-full space-y-3">
            <div class="flex items-center justify-between text-xs text-gray-500 px-2">
              <span class="flex items-center">
                <CheckCircle2 class="w-3 h-3 text-green-500 mr-1" /> LLM 对话模型
              </span>
              <span class="font-mono">{{ llmDraft.model_name }}</span>
            </div>
            <div class="flex items-center justify-between text-xs text-gray-500 px-2">
              <span class="flex items-center">
                <CheckCircle2 class="w-3 h-3 text-green-500 mr-1" /> Embedding 记忆模型
              </span>
              <span class="font-mono">{{ embeddingDraft.embedding_model }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Buttons -->
      <DialogFooter
        class="p-6 pt-0 flex flex-row items-center justify-between gap-3 bg-gray-50/50 border-t border-gray-100">
        <div>
          <Button v-if="step > 1" variant="ghost" size="sm" @click="prevStep" class="text-gray-500"
            :disabled="isGenderInitialized && step === 2">
            <ChevronLeft class="mr-1 w-4 h-4" /> 上一步
          </Button>
        </div>
        <div class="space-x-2">
          <Button v-if="step < 4" :disabled="!canGoNext" @click="nextStep"
            class="bg-gray-900 hover:bg-black text-white px-6 h-10">
            下一步
            <ChevronRight class="ml-1 w-4 h-4" />
          </Button>
          <Button v-else :disabled="isSaving" @click="completeSetup"
            class="bg-green-600 hover:bg-green-700 text-white px-10 h-10 shadow-lg shadow-green-100 font-bold transition-all hover:scale-105 active:scale-95">
            <Loader v-if="isSaving" class="mr-2 h-4 w-4" />
            开启 AI 社交之旅
          </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
/* Any custom animations */
@keyframes slide-up {
  from {
    transform: translateY(10px);
    opacity: 0;
  }

  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
