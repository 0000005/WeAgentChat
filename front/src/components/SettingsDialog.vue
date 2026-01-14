<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
    Dialog,
    DialogContent,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Eye, EyeOff, Loader2, CheckCircle2, XCircle, Plus, Trash2 } from 'lucide-vue-next'
import { useLlmStore } from '@/stores/llm'
import { useEmbeddingStore } from '@/stores/embedding'
import { useSettingsStore } from '@/stores/settings'
import { useMemoryStore } from '@/stores/memory'
import { storeToRefs } from 'pinia'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from '@/components/ui/accordion'

defineProps<{
    open: boolean
}>()

const emit = defineEmits(['update:open'])

const llmStore = useLlmStore()
const { apiBaseUrl, apiKey, modelName, isLoading: isLlmLoading, isTesting: isLlmTesting } = storeToRefs(llmStore)

const embeddingStore = useEmbeddingStore()
const {
    provider: embedProvider,
    apiKey: embedApiKey,
    baseUrl: embedBaseUrl,
    dim: embedDim,
    model: embedModel,
    maxTokenSize: embedMaxToken,
    isLoading: isEmbedLoading,
    isTesting: isEmbedTesting,
} = storeToRefs(embeddingStore)

const settingsStore = useSettingsStore()
const {
    passiveTimeout,
    enableThinking,
    showThinking,
    showToolCalls,
    recallEnabled,
    searchRounds,
    eventTopk,
    similarityThreshold,
    isSaving: isSettingsSaving
} = storeToRefs(settingsStore)

const memoryStore = useMemoryStore()

// 会话超时时间（分钟），用于界面显示
const passiveTimeoutMinutes = computed({
    get: () => Math.round(passiveTimeout.value / 60),
    set: (val: number) => { passiveTimeout.value = val * 60 }
})

// Testing state
const testStatus = ref<'idle' | 'success' | 'error'>('idle')
const testMessage = ref('')

const activeTab = ref('llm')
const showApiKey = ref(false)

const toggleApiKeyVisibility = () => {
    showApiKey.value = !showApiKey.value
}

onMounted(() => {
    llmStore.fetchConfig()
    embeddingStore.fetchConfig()
    settingsStore.fetchSessionSettings()
    settingsStore.fetchChatSettings()
    settingsStore.fetchMemorySettings()
    memoryStore.fetchConfig()
})

const handleSave = async () => {
    console.log('[SettingsDialog] handleSave triggered')
    try {
        await Promise.all([
            llmStore.saveConfig(),
            embeddingStore.saveConfig(),
            settingsStore.saveSessionSettings(),
            settingsStore.saveChatSettings(),
            settingsStore.saveMemorySettings(),
            memoryStore.saveConfig()
        ])
        console.log('[SettingsDialog] All settings saved successfully')
        emit('update:open', false)
    } catch (error) {
        // Error handling could be improved with a toast notification
        console.error('[SettingsDialog] Failed to save settings', error)
    }
}

const handleAddTopic = () => {
    memoryStore.profileConfig.topics.push({
        topic: '新分类',
        description: '请输入分类描述'
    })
}

const handleRemoveTopic = (index: number) => {
    memoryStore.profileConfig.topics.splice(index, 1)
}

const handleTest = async () => {
    testStatus.value = 'idle'
    testMessage.value = ''

    try {
        if (activeTab.value === 'llm') {
            const result = await llmStore.testConfig()
            testStatus.value = 'success'
            testMessage.value = `${result.message} (Model: ${result.model})`
        } else if (activeTab.value === 'embedding') {
            const result = await embeddingStore.testConfig()
            testStatus.value = 'success'
            testMessage.value = `${result.message} (Dimension: ${result.dimension})`
        }
    } catch (e: any) {
        testStatus.value = 'error'
        testMessage.value = e.message || 'Test failed'
    }
}

// Reset test status when switching tabs
const originalSetTab = (tab: string) => {
    activeTab.value = tab
    testStatus.value = 'idle'
    testMessage.value = ''
}
</script>

<template>
    <Dialog :open="open" @update:open="$emit('update:open', $event)">
        <DialogContent class="sm:max-w-[750px] p-0 overflow-hidden flex h-[600px] gap-0">
            <DialogTitle class="sr-only">设置</DialogTitle>
            <DialogDescription class="sr-only">应用配置界面</DialogDescription>

            <div class="w-[200px] bg-gray-50 border-r border-gray-200 p-4 flex flex-col gap-1">
                <h3 class="font-semibold mb-4 px-2 text-lg">设置</h3>
                <button class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    :class="activeTab === 'llm' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
                    @click="originalSetTab('llm')">
                    LLM 设置
                </button>
                <button class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    :class="activeTab === 'embedding' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
                    @click="originalSetTab('embedding')">
                    向量化设置
                </button>
                <button class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    :class="activeTab === 'memory' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
                    @click="originalSetTab('memory')">
                    记忆设置
                </button>
                <button class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    :class="activeTab === 'chat' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
                    @click="originalSetTab('chat')">
                    聊天设置
                </button>
            </div>

            <!-- Right Side Container -->
            <div class="flex-1 flex flex-col h-full overflow-hidden">
                <!-- Content -->
                <div class="flex-1 p-6 overflow-y-auto">
                    <template v-if="activeTab === 'llm'">
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">LLM 配置</h3>
                                <p class="text-sm text-gray-500">配置连接到大语言模型 API 的参数。</p>
                            </div>

                            <div class="space-y-4">
                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        API Base URL
                                    </label>
                                    <Input v-model="apiBaseUrl" placeholder="例如: https://api.openai.com/v1" />
                                    <p class="text-xs text-gray-500">
                                        OpenAI 兼容接口的地址。为空则默认使用官方地址。
                                    </p>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        API Key
                                    </label>
                                    <div class="relative">
                                        <Input v-model="apiKey" :type="showApiKey ? 'text' : 'password'"
                                            placeholder="sk-..." class="pr-10" />
                                        <button type="button" @click="toggleApiKeyVisibility"
                                            class="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-gray-500 hover:text-gray-900 flex items-center justify-center">
                                            <Eye v-if="!showApiKey" :size="16" />
                                            <EyeOff v-else :size="16" />
                                        </button>
                                    </div>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        Model Name
                                    </label>
                                    <Input v-model="modelName" placeholder="例如: gpt-3.5-turbo" />
                                </div>
                            </div>
                        </div>
                    </template>

                    <template v-if="activeTab === 'embedding'">
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">向量化配置</h3>
                                <p class="text-sm text-gray-500 text-pretty">配置 Embedding 模型 API 的参数。</p>
                                <p class="text-xs text-amber-600 mt-1.5 font-medium flex items-center gap-1">
                                    <span class="inline-block w-1 h-1 rounded-full bg-amber-600"></span>
                                    如果未正确配置向量化模型，记忆系统将无法正常工作
                                </p>
                            </div>

                            <div class="space-y-4">
                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        API Base URL
                                    </label>
                                    <Input v-model="embedBaseUrl" placeholder="例如: https://api.openai.com/v1" />
                                    <p class="text-xs text-gray-500">
                                        Embedding API 接口地址。
                                    </p>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        Provider
                                    </label>
                                    <Select v-model="embedProvider">
                                        <SelectTrigger>
                                            <SelectValue placeholder="选择提供商" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="openai">OpenAI</SelectItem>
                                            <SelectItem value="jina">Jina</SelectItem>
                                            <SelectItem value="lmstudio">LMStudio</SelectItem>
                                            <SelectItem value="ollama">Ollama</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        API Key
                                    </label>
                                    <div class="relative">
                                        <Input v-model="embedApiKey" :type="showApiKey ? 'text' : 'password'"
                                            placeholder="sk-..." class="pr-10" />
                                        <button type="button" @click="toggleApiKeyVisibility"
                                            class="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-gray-500 hover:text-gray-900 flex items-center justify-center">
                                            <Eye v-if="!showApiKey" :size="16" />
                                            <EyeOff v-else :size="16" />
                                        </button>
                                    </div>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        Model Name
                                    </label>
                                    <Input v-model="embedModel" placeholder="例如: BAAI/bge-m3" />
                                </div>

                                <div class="grid grid-cols-2 gap-4">
                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">
                                            Dimension
                                        </label>
                                        <Input v-model.number="embedDim" type="number" placeholder="1024" />
                                    </div>
                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">
                                            Max Token Size
                                        </label>
                                        <Input v-model.number="embedMaxToken" type="number" placeholder="8000" />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </template>

                    <template v-if="activeTab === 'memory'">
                        <div class="space-y-8">
                            <div>
                                <h3 class="text-lg font-medium">记忆管理设置</h3>
                                <p class="text-sm text-gray-500">配置会话管理和记忆关注维度。</p>
                            </div>

                            <!-- Basic Configuration -->
                            <div class="space-y-4">
                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        会话过期时间（分钟）
                                    </label>
                                    <Input v-model.number="passiveTimeoutMinutes" type="number" min="1" max="1440"
                                        placeholder="30" />
                                    <p class="text-xs text-gray-500">
                                        当与好友的最后一次聊天超过此时间后，系统会自动归档会话并生成记忆摘要。
                                    </p>
                                </div>
                            </div>

                            <!-- Recall Settings -->
                            <div class="space-y-4 border-t pt-6">
                                <div class="flex items-center justify-between">
                                    <label class="text-sm font-medium">启用记忆召回</label>
                                    <Switch v-model="recallEnabled" />
                                </div>
                                <p class="text-xs text-gray-500">
                                    根据上下文语义自动召回相关的事件历史，增强对话的个性化体验。
                                </p>

                                <div v-if="recallEnabled" class="space-y-6 pt-2">
                                    <div class="grid gap-2">
                                        <div class="flex justify-between items-center">
                                            <label class="text-sm font-medium">相似度阈值 ({{ similarityThreshold }})</label>
                                        </div>
                                        <Slider :model-value="[similarityThreshold]"
                                            @update:model-value="(val: number[] | undefined) => { if (val) similarityThreshold = val[0] }"
                                            :max="1" :step="0.05" class="py-4" />
                                        <p class="text-xs text-gray-500">语义检索的最低匹配得分，值越高越精准但召回内容越少。</p>
                                    </div>

                                    <div class="grid grid-cols-2 gap-4">
                                        <div class="grid gap-2">
                                            <label class="text-sm font-medium">搜索轮数</label>
                                            <Input v-model.number="searchRounds" type="number" min="1" max="10" />
                                        </div>
                                    </div>

                                    <div class="grid grid-cols-2 gap-4">
                                        <div class="grid gap-2">
                                            <label class="text-sm font-medium">事件召回 TopK</label>
                                            <Input v-model.number="eventTopk" type="number" min="1" max="20" />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Schema Builder -->
                            <div class="space-y-4 border-t pt-6">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <h4 class="text-sm font-semibold">资料关注维度 (YAML Schema)</h4>
                                        <p class="text-xs text-gray-500">定义系统自动提取记忆时关注的分类和维度。</p>
                                    </div>
                                    <Button variant="ghost" size="sm"
                                        class="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                        @click="handleAddTopic">
                                        <Plus class="w-4 h-4 mr-1" />
                                        添加分类
                                    </Button>
                                </div>

                                <Accordion type="single" collapsible class="w-full">
                                    <AccordionItem v-for="(topic, index) in memoryStore.profileConfig.topics"
                                        :key="index" :value="`item-${index}`"
                                        class="border rounded-md px-3 mb-2 bg-white shadow-sm overflow-hidden">
                                        <div class="flex items-center justify-between py-1">
                                            <AccordionTrigger class="flex-1 hover:no-underline py-2">
                                                <span class="text-sm font-medium">{{ topic.topic }}</span>
                                            </AccordionTrigger>
                                            <button class="ml-2 p-1 text-gray-400 hover:text-red-500 transition-colors"
                                                @click.stop="handleRemoveTopic(index)">
                                                <Trash2 :size="14" />
                                            </button>
                                        </div>
                                        <AccordionContent class="pb-3 border-t pt-3 space-y-3">
                                            <div class="grid gap-1.5">
                                                <label class="text-xs font-medium text-gray-500">分类名称</label>
                                                <Input v-model="topic.topic" class="h-8 text-sm" />
                                            </div>
                                            <div class="grid gap-1.5">
                                                <label class="text-xs font-medium text-gray-500">提取引导说明</label>
                                                <Input v-model="topic.description" class="h-8 text-sm"
                                                    placeholder="描述此分类关注的信息点..." />
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>
                                </Accordion>

                                <div v-if="memoryStore.profileConfig.topics.length === 0"
                                    class="py-10 text-center border border-dashed rounded-md bg-gray-50/50">
                                    <p class="text-sm text-gray-400">暂无维度定义，请点击上方按钮添加。</p>
                                </div>
                            </div>
                        </div>
                    </template>

                    <template v-if="activeTab === 'chat'">
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">聊天展示设置</h3>
                                <p class="text-sm text-gray-500">配置聊天界面的展示细节。</p>
                            </div>

                            <div class="space-y-4">
                                <div class="flex items-center justify-between">
                                    <div class="space-y-0.5">
                                        <label class="text-sm font-medium">显示思维链</label>
                                        <p class="text-xs text-gray-500">在消息下方展示 AI 的推理思考过程。</p>
                                    </div>
                                    <Switch v-model="showThinking" />
                                </div>

                                <div class="flex items-center justify-between border-t pt-4">
                                    <div class="space-y-0.5">
                                        <label class="text-sm font-medium">显示工具调用</label>
                                        <p class="text-xs text-gray-500">在消息中展示 AI 调用外部工具的详细信息。</p>
                                    </div>
                                    <Switch v-model="showToolCalls" />
                                </div>

                                <div class="flex items-center justify-between border-t pt-4">
                                    <div class="space-y-0.5">
                                        <label class="text-sm font-medium">启用深度思考模式 (推理)</label>
                                        <p class="text-xs text-gray-500">如果模型支持，开启后将强制模型进行链式思考后再回答。</p>
                                    </div>
                                    <Switch v-model="enableThinking" />
                                </div>
                            </div>
                        </div>
                    </template>
                </div>

                <!-- Footer -->
                <div class="p-4 border-t border-gray-100 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                    <!-- Test result display -->
                    <div v-if="testStatus !== 'idle'" class="mb-3 flex items-center gap-2 text-sm">
                        <CheckCircle2 v-if="testStatus === 'success'" class="w-4 h-4 text-green-500" />
                        <XCircle v-else class="w-4 h-4 text-red-500" />
                        <span :class="testStatus === 'success' ? 'text-green-600' : 'text-red-600'">
                            {{ testMessage }}
                        </span>
                    </div>

                    <div class="flex justify-end gap-2">
                        <Button variant="outline" @click="$emit('update:open', false)">取消</Button>
                        <Button v-if="activeTab === 'llm' || activeTab === 'embedding'" variant="outline"
                            @click="handleTest" :disabled="isLlmTesting || isEmbedTesting">
                            <Loader2 v-if="isLlmTesting || isEmbedTesting" class="w-4 h-4 mr-2 animate-spin" />
                            测试
                        </Button>
                        <Button @click="handleSave" :disabled="isLlmLoading || isEmbedLoading || isSettingsSaving">
                            <Loader2 v-if="isLlmLoading || isEmbedLoading || isSettingsSaving"
                                class="w-4 h-4 mr-2 animate-spin" />
                            保存
                        </Button>
                    </div>
                </div>
            </div>

        </DialogContent>
    </Dialog>
</template>
