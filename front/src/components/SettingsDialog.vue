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
import { Eye, EyeOff, Loader2, CheckCircle2, XCircle } from 'lucide-vue-next'
import { useLlmStore } from '@/stores/llm'
import { useEmbeddingStore } from '@/stores/embedding'
import { useSettingsStore } from '@/stores/settings'
import { storeToRefs } from 'pinia'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'

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
const { passiveTimeout, isLoading: isSettingsLoading, isSaving: isSettingsSaving } = storeToRefs(settingsStore)

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
})

const handleSave = async () => {
    try {
        await Promise.all([
            llmStore.saveConfig(),
            embeddingStore.saveConfig(),
            settingsStore.saveSessionSettings()
        ])
        emit('update:open', false)
    } catch (error) {
        // Error handling could be improved with a toast notification
        console.error('Failed to save settings', error)
    }
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
        <DialogContent class="sm:max-w-[700px] p-0 overflow-hidden flex h-[500px] gap-0">
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
                                <p class="text-sm text-gray-500">配置 Embedding 模型 API 的参数。</p>
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
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">记忆设置</h3>
                                <p class="text-sm text-gray-500">配置会话管理和记忆系统相关参数。</p>
                            </div>

                            <div class="space-y-4">
                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        会话过期时间（分钟）
                                    </label>
                                    <Input v-model.number="passiveTimeoutMinutes" type="number" min="1" max="1440" placeholder="30" />
                                    <p class="text-xs text-gray-500">
                                        当与好友的最后一次聊天超过此时间后，系统会自动归档会话并生成记忆摘要。下次聊天将开启新会话。
                                    </p>
                                </div>


                            </div>
                        </div>
                    </template>
                </div>

                <!-- Footer -->
                <div class="p-4 border-t border-gray-100 bg-white">
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
                        <Button v-if="activeTab !== 'memory'" variant="outline" @click="handleTest" :disabled="isLlmTesting || isEmbedTesting">
                            <Loader2 v-if="isLlmTesting || isEmbedTesting" class="w-4 h-4 mr-2 animate-spin" />
                            测试
                        </Button>
                        <Button @click="handleSave" :disabled="isLlmLoading || isEmbedLoading || isSettingsSaving">
                            <Loader2 v-if="isLlmLoading || isEmbedLoading || isSettingsSaving" class="w-4 h-4 mr-2 animate-spin" />
                            保存
                        </Button>
                    </div>
                </div>
            </div>

        </DialogContent>
    </Dialog>
</template>