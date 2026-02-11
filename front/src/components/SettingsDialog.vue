<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import {
    Dialog,
    DialogContent,
    DialogTitle,
    DialogDescription,
    DialogHeader,
    DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Eye, EyeOff, Loader2, CheckCircle2, XCircle, X, Plus, Trash2, BrainCircuit, Search, Wrench } from 'lucide-vue-next'
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

type TestStatus = 'idle' | 'success' | 'error'

type LlmFormState = {
    id: number | null
    provider: string
    config_name: string
    base_url: string
    api_key: string
    model_name: string
    is_verified: boolean
    capability_vision: boolean
    capability_search: boolean
    capability_reasoning: boolean
    capability_function_call: boolean
}

type EmbeddingFormState = {
    id: number | null
    config_name: string
    embedding_provider: string
    embedding_api_key: string
    embedding_base_url: string
    embedding_dim: number
    embedding_model: string
    embedding_max_token_size: number
    is_verified: boolean
}

type LlmListItem = {
    id: number
    config_name?: string | null
    provider?: string | null
    is_verified?: boolean | null
    capability_vision?: boolean | null
    capability_search?: boolean | null
    capability_reasoning?: boolean | null
    capability_function_call?: boolean | null
    __draft?: boolean
}

type EmbeddingListItem = {
    id: number
    config_name?: string | null
    embedding_provider?: string | null
    is_verified?: boolean | null
    __draft?: boolean
}

const LLM_PROVIDER_PRESETS: Record<string, { label: string; baseUrl: string }> = {
    openai: { label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
    zhipu: { label: '智谱 AI', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
    modelscope: { label: '魔搭社区', baseUrl: 'https://api-inference.modelscope.cn/v1' },
    minimax: { label: 'MiniMax', baseUrl: 'https://api.minimax.chat/v1' },
    gemini: { label: 'Google Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta' },
    openai_compatible: { label: 'OpenAI (兼容)', baseUrl: '' }
}

const EMBEDDING_PROVIDER_PRESETS: Record<string, { label: string; provider: string; baseUrl: string; model: string; dim: number }> = {
    openai: { label: 'OpenAI (官方)', provider: 'openai', baseUrl: 'https://api.openai.com/v1', model: 'text-embedding-3-small', dim: 1536 },
    siliconflow: { label: 'SiliconFlow', provider: 'openai', baseUrl: 'https://api.siliconflow.cn/v1', model: 'BAAI/bge-m3', dim: 1024 },
    zhipu: { label: '智谱 AI', provider: 'openai', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'embedding-3', dim: 2048 },
    jina: { label: 'Jina', provider: 'jina', baseUrl: 'https://api.jina.ai/v1', model: 'jina-embeddings-v2-base-en', dim: 768 },
    ollama: { label: 'Ollama', provider: 'ollama', baseUrl: 'http://127.0.0.1:11434', model: 'bge-m3', dim: 1024 }
}

const EMBEDDING_PROTOCOL_OPTIONS = [
    { value: 'openai', label: 'OpenAI 协议' },
    { value: 'jina', label: 'Jina 协议' },
    { value: 'ollama', label: 'Ollama 协议' }
]

const EMBEDDING_PROVIDER_LABELS: Record<string, string> = Object.fromEntries(
    EMBEDDING_PROTOCOL_OPTIONS.map(opt => [opt.value, opt.label])
)

const MAX_CONFIGS = 20
const DRAFT_LLM_ID = -1
const DRAFT_EMBEDDING_ID = -2

const props = defineProps<{
    open: boolean
    defaultTab?: string
}>()

const emit = defineEmits(['update:open'])

const llmStore = useLlmStore()
const { configs: llmConfigs, isLoading: isLlmLoading, isTesting: isLlmTesting } = storeToRefs(llmStore)

const embeddingStore = useEmbeddingStore()
const {
    configs: embeddingConfigs,
    isLoading: isEmbedLoading,
    isTesting: isEmbedTesting,
} = storeToRefs(embeddingStore)

const settingsStore = useSettingsStore()
const {
    passiveTimeout,
    smartContextEnabled,
    smartContextModel,
    enableThinking,
    recallEnabled,
    searchRounds,
    eventTopk,
    similarityThreshold,
    activeLlmConfigId,
    activeEmbeddingConfigId,
    activeMemoryLlmConfigId,
    autoLaunch,
    isSaving: isSettingsSaving
} = storeToRefs(settingsStore)

const memoryStore = useMemoryStore()

// 会话超时时间（分钟），用于界面显示
const passiveTimeoutMinutes = computed({
    get: () => Math.round(passiveTimeout.value / 60),
    set: (val: number) => { passiveTimeout.value = val * 60 }
})

const activeTab = ref(props.defaultTab || 'llm')
const showApiKey = ref(false)
const llmTestStatus = ref<TestStatus>('idle')
const llmTestMessage = ref('')
const embeddingTestStatus = ref<TestStatus>('idle')
const embeddingTestMessage = ref('')

const selectedLlmId = ref<number | null>(null)
const selectedEmbeddingId = ref<number | null>(null)
const draftLlmForm = ref<LlmFormState | null>(null)
const draftEmbeddingForm = ref<EmbeddingFormState | null>(null)

const isSettingLlmForm = ref(false)
const isSettingEmbeddingForm = ref(false)

const buildUniqueName = (base: string, names: string[]) => {
    if (!names.includes(base)) return base
    let index = 2
    while (names.includes(`${base} #${index}`)) {
        index += 1
    }
    return `${base} #${index}`
}

const buildDefaultLlmForm = (provider: string): LlmFormState => {
    const preset = LLM_PROVIDER_PRESETS[provider] || LLM_PROVIDER_PRESETS.openai
    const existingNames = llmConfigs.value.map(item => item.config_name).filter(Boolean) as string[]
    return {
        id: null,
        provider,
        config_name: buildUniqueName(preset.label, existingNames),
        base_url: preset.baseUrl,
        api_key: '',
        model_name: 'gpt-3.5-turbo',
        is_verified: false,
        capability_vision: false,
        capability_search: false,
        capability_reasoning: false,
        capability_function_call: true,
    }
}

const buildDefaultEmbeddingForm = (provider: string): EmbeddingFormState => {
    const preset = EMBEDDING_PROVIDER_PRESETS[provider] || EMBEDDING_PROVIDER_PRESETS.openai
    const existingNames = embeddingConfigs.value.map(item => item.config_name).filter(Boolean) as string[]
    return {
        id: null as any,
        config_name: buildUniqueName(preset.label, existingNames),
        embedding_provider: preset.provider,
        embedding_api_key: '',
        embedding_base_url: preset.baseUrl,
        embedding_dim: preset.dim || 1024,
        embedding_model: preset.model || 'BAAI/bge-m3',
        embedding_max_token_size: 8000,
        is_verified: false,
    }
}

const applyEmbeddingPreset = (presetKey: string) => {
    const preset = EMBEDDING_PROVIDER_PRESETS[presetKey]
    if (!preset) return
    embeddingForm.value.embedding_provider = preset.provider
    embeddingForm.value.embedding_base_url = preset.baseUrl
    embeddingForm.value.embedding_model = preset.model
    embeddingForm.value.embedding_dim = preset.dim
    const existingNames = embeddingConfigs.value.map(c => c.config_name).filter(Boolean) as string[]
    embeddingForm.value.config_name = buildUniqueName(preset.label, existingNames)
}

const llmForm = ref<LlmFormState>(buildDefaultLlmForm('openai'))
const embeddingForm = ref<EmbeddingFormState>(buildDefaultEmbeddingForm('openai'))

const llmAddDisabled = computed(() => llmConfigs.value.length + (draftLlmForm.value ? 1 : 0) >= MAX_CONFIGS)
const embeddingAddDisabled = computed(() => embeddingConfigs.value.length + (draftEmbeddingForm.value ? 1 : 0) >= MAX_CONFIGS)

const draftLlmItem = computed<LlmListItem | null>(() => {
    if (!draftLlmForm.value) return null
    return {
        id: DRAFT_LLM_ID,
        config_name: draftLlmForm.value.config_name || '新配置（未保存）',
        provider: draftLlmForm.value.provider,
        is_verified: false,
        capability_vision: draftLlmForm.value.capability_vision,
        capability_search: draftLlmForm.value.capability_search,
        capability_reasoning: draftLlmForm.value.capability_reasoning,
        capability_function_call: draftLlmForm.value.capability_function_call,
        __draft: true
    }
})

const draftEmbeddingItem = computed<EmbeddingListItem | null>(() => {
    if (!draftEmbeddingForm.value) return null
    return {
        id: DRAFT_EMBEDDING_ID,
        config_name: draftEmbeddingForm.value.config_name || '新配置（未保存）',
        embedding_provider: draftEmbeddingForm.value.embedding_provider,
        is_verified: false,
        __draft: true
    }
})

const llmListItems = computed<LlmListItem[]>(() => {
    const list = draftLlmItem.value ? [draftLlmItem.value, ...llmConfigs.value] : llmConfigs.value
    return list as LlmListItem[]
})

const embeddingListItems = computed<EmbeddingListItem[]>(() => {
    const list = draftEmbeddingItem.value ? [draftEmbeddingItem.value, ...embeddingConfigs.value] : embeddingConfigs.value
    return list as EmbeddingListItem[]
})

// Confirmation Dialog State
const confirmDialog = ref({
    open: false,
    title: '',
    message: '',
    confirmText: '确认删除',
    showCancel: true,
    onConfirm: () => { }
})

const showConfirmDialog = (
    title: string,
    message: string,
    onConfirm: () => void,
    options: { confirmText?: string; showCancel?: boolean } = {}
) => {
    confirmDialog.value = {
        open: true,
        title,
        message,
        confirmText: options.confirmText || '确认删除',
        showCancel: options.showCancel ?? true,
        onConfirm
    }
}

const handleConfirm = () => {
    confirmDialog.value.onConfirm()
    confirmDialog.value.open = false
}

const handleCancel = () => {
    confirmDialog.value.open = false
}

// Watch for changes in defaultTab when the dialog opens
watch(() => props.open, (newVal) => {
    if (newVal && props.defaultTab) {
        activeTab.value = props.defaultTab
    }
    if (!newVal) {
        draftLlmForm.value = null
        draftEmbeddingForm.value = null
        if (selectedLlmId.value === DRAFT_LLM_ID) {
            selectedLlmId.value = null
        }
        if (selectedEmbeddingId.value === DRAFT_EMBEDDING_ID) {
            selectedEmbeddingId.value = null
        }
    }
})

// Also watch defaultTab directly in case it changes while open
watch(() => props.defaultTab, (newVal) => {
    if (newVal) {
        activeTab.value = newVal
    }
})


const toggleApiKeyVisibility = () => {
    showApiKey.value = !showApiKey.value
}

onMounted(() => {
    llmStore.fetchConfigs()
    embeddingStore.fetchConfigs()
    settingsStore.fetchSessionSettings()
    settingsStore.fetchChatSettings()
    settingsStore.fetchMemorySettings()
    settingsStore.fetchSystemSettings()
    memoryStore.fetchConfig()
})

const handleSave = async () => {
    console.log('[SettingsDialog] handleSave triggered')
    try {
        if (activeTab.value === 'llm') {
            const payload = {
                provider: llmForm.value.provider,
                config_name: llmForm.value.config_name,
                base_url: llmForm.value.base_url || null,
                api_key: llmForm.value.api_key || null,
                model_name: llmForm.value.model_name || 'gpt-3.5-turbo',
                capability_vision: llmForm.value.capability_vision,
                capability_search: llmForm.value.capability_search,
                capability_reasoning: llmForm.value.capability_reasoning,
                capability_function_call: true,
                is_verified: llmTestStatus.value === 'success' ? true : llmTestStatus.value === 'error' ? false : llmForm.value.is_verified
            }

            if (llmForm.value.id) {
                const updated = await llmStore.updateConfig(llmForm.value.id, payload)
                setLlmFormFromConfig(updated)
            } else {
                const created = await llmStore.createConfig(payload)
                draftLlmForm.value = null
                setLlmFormFromConfig(created)
                if (!activeLlmConfigId.value) {
                    activeLlmConfigId.value = created.id ?? null
                    await settingsStore.saveChatSettings()
                }
            }
        }

        if (activeTab.value === 'embedding') {
            const payload = {
                config_name: embeddingForm.value.config_name,
                embedding_provider: embeddingForm.value.embedding_provider,
                embedding_api_key: embeddingForm.value.embedding_api_key || null,
                embedding_base_url: embeddingForm.value.embedding_base_url || null,
                embedding_dim: embeddingForm.value.embedding_dim,
                embedding_model: embeddingForm.value.embedding_model,
                embedding_max_token_size: embeddingForm.value.embedding_max_token_size,
                is_verified: embeddingTestStatus.value === 'success' ? true : embeddingTestStatus.value === 'error' ? false : embeddingForm.value.is_verified
            }

            if (embeddingForm.value.id) {
                const updated = await embeddingStore.updateConfig(embeddingForm.value.id, payload)
                setEmbeddingFormFromConfig(updated)
            } else {
                const created = await embeddingStore.createConfig(payload)
                draftEmbeddingForm.value = null
                setEmbeddingFormFromConfig(created)
                if (!activeEmbeddingConfigId.value) {
                    activeEmbeddingConfigId.value = created.id ?? null
                    await settingsStore.saveMemorySettings()
                }
            }
        }

        if (activeTab.value === 'memory') {
            if (!activeEmbeddingConfigId.value) {
                // Session settings (passive timeout / smart context) should still be persisted.
                await settingsStore.saveSessionSettings()
                showConfirmDialog('请先选择向量模型', '记忆系统必须绑定一个向量模型配置。请先在「向量化设置」中创建并选择配置。', () => { }, { confirmText: '知道了', showCancel: false })
                return
            }
            await Promise.all([
                settingsStore.saveSessionSettings(),
                settingsStore.saveMemorySettings(),
                memoryStore.saveConfig()
            ])
        }

        if (activeTab.value === 'chat') {
            if (!activeLlmConfigId.value) {
                showConfirmDialog('请先选择聊天模型', '聊天设置需要绑定一个 LLM 配置，请先在「LLM 设置」中创建并选择配置。', () => { }, { confirmText: '知道了', showCancel: false })
                return
            }
            await settingsStore.saveChatSettings()
        }

        if (activeTab.value === 'system') {
            await settingsStore.saveSystemSettings()
            if ((window as any).WeAgentChat?.system?.setAutoLaunch) {
                await (window as any).WeAgentChat.system.setAutoLaunch(autoLaunch.value)
            }
        }

        console.log('[SettingsDialog] Settings saved successfully')
    } catch (error) {
        console.error('[SettingsDialog] Failed to save settings', error)
    }
}

const handleAddTopic = () => {
    memoryStore.profileConfig.topics.push({
        topic: '新分类',
        description: '请输入分类描述',
        sub_topics: []
    })
}

const handleRemoveTopic = async (index: number) => {
    const topic = memoryStore.profileConfig.topics[index]
    if (!topic) return
    await memoryStore.fetchProfiles()
    const profilesInTopic = memoryStore.profiles.filter(
        p => p.attributes.topic === topic.topic
    )
    const profileCount = profilesInTopic.length
    const message = profileCount > 0
        ? `确定要删除分类「${topic.topic}」吗？\n\n该分类下有 ${profileCount} 条资料记录将被一并删除，此操作不可撤销。`
        : `确定要删除分类「${topic.topic}」吗？`

    showConfirmDialog(
        '删除分类',
        message,
        async () => {
            if (profileCount > 0) {
                const profileIds = profilesInTopic.map(p => p.id)
                await memoryStore.removeProfiles(profileIds)
            }
            memoryStore.profileConfig.topics.splice(index, 1)
            await memoryStore.saveConfig()
            await memoryStore.fetchProfiles()
        }
    )
}

const handleAddSubTopic = (topic: any) => {
    if (!topic.sub_topics) {
        topic.sub_topics = []
    }
    topic.sub_topics.push({ name: '新子主题', description: '' })
}

const handleRemoveSubTopic = (topic: any, index: number) => {
    if (!topic.sub_topics) return
    topic.sub_topics.splice(index, 1)
}

const setLlmFormFromConfig = (config: any | null) => {
    isSettingLlmForm.value = true
    if (!config) {
        llmForm.value = buildDefaultLlmForm('openai')
        selectedLlmId.value = null
    } else {
        llmForm.value = {
            id: config.id ?? null,
            provider: config.provider || 'openai',
            config_name: config.config_name || LLM_PROVIDER_PRESETS[config.provider || 'openai']?.label || 'OpenAI',
            base_url: config.base_url || '',
            api_key: config.api_key || '',
            model_name: config.model_name || 'gpt-3.5-turbo',
            is_verified: !!config.is_verified,
            capability_vision: !!config.capability_vision,
            capability_search: !!config.capability_search,
            capability_reasoning: !!config.capability_reasoning,
            capability_function_call: true,
        }
        selectedLlmId.value = config.id ?? null
    }
    llmTestStatus.value = 'idle'
    llmTestMessage.value = ''
    nextTick(() => {
        isSettingLlmForm.value = false
    })
}

const setEmbeddingFormFromConfig = (config: any | null) => {
    isSettingEmbeddingForm.value = true
    if (!config) {
        embeddingForm.value = buildDefaultEmbeddingForm('openai')
        selectedEmbeddingId.value = null
    } else {
        embeddingForm.value = {
            id: config.id ?? null,
            config_name: config.config_name || EMBEDDING_PROVIDER_LABELS[config.embedding_provider || 'openai'] || 'OpenAI',
            embedding_provider: config.embedding_provider || 'openai',
            embedding_api_key: config.embedding_api_key || '',
            embedding_base_url: config.embedding_base_url || '',
            embedding_dim: config.embedding_dim || 1024,
            embedding_model: config.embedding_model || 'BAAI/bge-m3',
            embedding_max_token_size: config.embedding_max_token_size || 8000,
            is_verified: !!config.is_verified,
        }
        selectedEmbeddingId.value = config.id ?? null
    }
    embeddingTestStatus.value = 'idle'
    embeddingTestMessage.value = ''
    nextTick(() => {
        isSettingEmbeddingForm.value = false
    })
}

const handleAddLlmConfig = () => {
    if (llmAddDisabled.value) return
    if (!draftLlmForm.value) {
        draftLlmForm.value = buildDefaultLlmForm('openai')
    }
    llmForm.value = draftLlmForm.value
    selectedLlmId.value = DRAFT_LLM_ID
    llmTestStatus.value = 'idle'
    llmTestMessage.value = ''
}

const handleAddEmbeddingConfig = () => {
    if (embeddingAddDisabled.value) return
    if (!draftEmbeddingForm.value) {
        draftEmbeddingForm.value = buildDefaultEmbeddingForm('openai')
    }
    embeddingForm.value = draftEmbeddingForm.value
    selectedEmbeddingId.value = DRAFT_EMBEDDING_ID
    embeddingTestStatus.value = 'idle'
    embeddingTestMessage.value = ''
}

const discardLlmDraft = () => {
    if (!draftLlmForm.value) return
    const wasSelected = selectedLlmId.value === DRAFT_LLM_ID
    draftLlmForm.value = null
    if (wasSelected) {
        selectedLlmId.value = null
        const fallback = llmStore.getConfigById(activeLlmConfigId.value) || llmConfigs.value[0] || null
        setLlmFormFromConfig(fallback)
    }
}

const discardEmbeddingDraft = () => {
    if (!draftEmbeddingForm.value) return
    const wasSelected = selectedEmbeddingId.value === DRAFT_EMBEDDING_ID
    draftEmbeddingForm.value = null
    if (wasSelected) {
        selectedEmbeddingId.value = null
        const fallback = embeddingStore.getConfigById(activeEmbeddingConfigId.value) || embeddingConfigs.value[0] || null
        setEmbeddingFormFromConfig(fallback)
    }
}

const selectLlmDraft = () => {
    if (!draftLlmForm.value) return
    isSettingLlmForm.value = true
    llmForm.value = draftLlmForm.value
    selectedLlmId.value = DRAFT_LLM_ID
    llmTestStatus.value = 'idle'
    llmTestMessage.value = ''
    nextTick(() => {
        isSettingLlmForm.value = false
    })
}

const selectEmbeddingDraft = () => {
    if (!draftEmbeddingForm.value) return
    isSettingEmbeddingForm.value = true
    embeddingForm.value = draftEmbeddingForm.value
    selectedEmbeddingId.value = DRAFT_EMBEDDING_ID
    embeddingTestStatus.value = 'idle'
    embeddingTestMessage.value = ''
    nextTick(() => {
        isSettingEmbeddingForm.value = false
    })
}

const handleDeleteLlmConfig = () => {
    if (selectedLlmId.value === DRAFT_LLM_ID) {
        discardLlmDraft()
        return
    }
    if (!llmForm.value.id) return
    if (activeLlmConfigId.value === llmForm.value.id) {
        showConfirmDialog(
            '无法删除',
            '该配置当前正在被聊天模块使用，请先切换到其他配置后再删除。',
            () => { },
            { confirmText: '知道了', showCancel: false }
        )
        return
    }
    if (activeMemoryLlmConfigId.value === llmForm.value.id) {
        showConfirmDialog(
            '无法删除',
            '该配置当前正在被记忆模块使用，请先切换到其他配置后再删除。',
            () => { },
            { confirmText: '知道了', showCancel: false }
        )
        return
    }
    showConfirmDialog(
        '删除配置',
        `确定要删除「${llmForm.value.config_name || '未命名配置'}」吗？`,
        async () => {
            await llmStore.removeConfig(llmForm.value.id as number)
            setLlmFormFromConfig(null)
        }
    )
}

const handleDeleteEmbeddingConfig = () => {
    if (selectedEmbeddingId.value === DRAFT_EMBEDDING_ID) {
        discardEmbeddingDraft()
        return
    }
    if (!embeddingForm.value.id) return
    if (activeEmbeddingConfigId.value === embeddingForm.value.id) {
        showConfirmDialog(
            '无法删除',
            '该配置当前正在被记忆模块使用，请先切换到其他配置后再删除。',
            () => { },
            { confirmText: '知道了', showCancel: false }
        )
        return
    }
    showConfirmDialog(
        '删除配置',
        `确定要删除「${embeddingForm.value.config_name || '未命名配置'}」吗？`,
        async () => {
            await embeddingStore.removeConfig(embeddingForm.value.id as number)
            setEmbeddingFormFromConfig(null)
        }
    )
}

const handleLlmTest = async () => {
    llmTestStatus.value = 'idle'
    llmTestMessage.value = ''
    try {
        const result = await llmStore.testConfig({
            base_url: llmForm.value.base_url || null,
            api_key: llmForm.value.api_key || null,
            model_name: llmForm.value.model_name || 'gpt-3.5-turbo'
        })
        llmTestStatus.value = 'success'
        llmTestMessage.value = `${result.message} (Model: ${result.model})`
    } catch (e: any) {
        llmTestStatus.value = 'error'
        llmTestMessage.value = e.message || 'Test failed'
    }
}

const handleEmbeddingTest = async () => {
    embeddingTestStatus.value = 'idle'
    embeddingTestMessage.value = ''
    try {
        const result = await embeddingStore.testConfig({
            embedding_provider: embeddingForm.value.embedding_provider,
            embedding_api_key: embeddingForm.value.embedding_api_key || null,
            embedding_base_url: embeddingForm.value.embedding_base_url || null,
            embedding_dim: embeddingForm.value.embedding_dim,
            embedding_model: embeddingForm.value.embedding_model,
            embedding_max_token_size: embeddingForm.value.embedding_max_token_size
        })
        embeddingTestStatus.value = 'success'
        embeddingTestMessage.value = `${result.message} (Dimension: ${result.dimension})`
    } catch (e: any) {
        embeddingTestStatus.value = 'error'
        embeddingTestMessage.value = e.message || 'Test failed'
    }
}

const handleTest = async () => {
    if (activeTab.value === 'llm') {
        await handleLlmTest()
    } else if (activeTab.value === 'embedding') {
        await handleEmbeddingTest()
    }
}

// Reset test status when switching tabs
const originalSetTab = (tab: string) => {
    activeTab.value = tab
}

watch(
    () => [llmConfigs.value, activeLlmConfigId.value],
    () => {
        if (draftLlmForm.value) return
        if (!llmConfigs.value.length) {
            setLlmFormFromConfig(null)
            return
        }
        const preferredId = selectedLlmId.value || activeLlmConfigId.value || llmConfigs.value[0]?.id || null
        const preferredConfig = llmStore.getConfigById(preferredId)
        if (preferredConfig) {
            setLlmFormFromConfig(preferredConfig)
        }
    },
    { immediate: true }
)

watch(
    () => [embeddingConfigs.value, activeEmbeddingConfigId.value],
    () => {
        if (draftEmbeddingForm.value) return
        if (!embeddingConfigs.value.length) {
            setEmbeddingFormFromConfig(null)
            return
        }
        const preferredId = selectedEmbeddingId.value || activeEmbeddingConfigId.value || embeddingConfigs.value[0]?.id || null
        const preferredConfig = embeddingStore.getConfigById(preferredId)
        if (preferredConfig) {
            setEmbeddingFormFromConfig(preferredConfig)
        }
    },
    { immediate: true }
)

watch(
    () => llmForm.value.provider,
    (newProvider, oldProvider) => {
        if (isSettingLlmForm.value) return
        const newPreset = LLM_PROVIDER_PRESETS[newProvider] || LLM_PROVIDER_PRESETS.openai
        const oldPreset = oldProvider ? LLM_PROVIDER_PRESETS[oldProvider] : null
        const isBaseUrlDefault = !llmForm.value.base_url || (oldPreset && llmForm.value.base_url === oldPreset.baseUrl)
        if (isBaseUrlDefault) {
            llmForm.value.base_url = newPreset.baseUrl
        }
        if (!llmForm.value.id) {
            const existingNames = llmConfigs.value.map(item => item.config_name).filter(Boolean) as string[]
            const shouldReplaceName = !llmForm.value.config_name || (oldPreset && llmForm.value.config_name === oldPreset.label)
            if (shouldReplaceName) {
                llmForm.value.config_name = buildUniqueName(newPreset.label, existingNames)
            }
        }
    }
)

watch(
    () => llmForm.value,
    () => {
        if (isSettingLlmForm.value) return
        llmTestStatus.value = 'idle'
        llmTestMessage.value = ''
        if (llmForm.value.is_verified) {
            llmForm.value.is_verified = false
        }
    },
    { deep: true }
)

watch(
    () => embeddingForm.value.embedding_provider,
    (newProvider) => {
        if (isSettingEmbeddingForm.value) return

        // Provide defaults for Jina/Ollama, but for OpenAI we don't overwrite if it already has values 
        // unless it's a completely new form without a Base URL.
        if (newProvider === 'jina') {
            const preset = EMBEDDING_PROVIDER_PRESETS.jina
            embeddingForm.value.embedding_base_url = preset.baseUrl
            embeddingForm.value.embedding_model = preset.model
            embeddingForm.value.embedding_dim = preset.dim
        } else if (newProvider === 'ollama') {
            const preset = EMBEDDING_PROVIDER_PRESETS.ollama
            embeddingForm.value.embedding_base_url = preset.baseUrl
            embeddingForm.value.embedding_model = preset.model
            embeddingForm.value.embedding_dim = preset.dim
        } else if (newProvider === 'openai' && !embeddingForm.value.embedding_base_url) {
            const preset = EMBEDDING_PROVIDER_PRESETS.openai
            embeddingForm.value.embedding_base_url = preset.baseUrl
            embeddingForm.value.embedding_model = preset.model
            embeddingForm.value.embedding_dim = preset.dim
        }

        if (!embeddingForm.value.id) {
            const label = EMBEDDING_PROVIDER_LABELS[newProvider] || 'Embedding'
            const existingNames = embeddingConfigs.value.map(item => item.config_name).filter(Boolean) as string[]
            embeddingForm.value.config_name = buildUniqueName(label, existingNames)
        }
    }
)

watch(
    () => embeddingForm.value,
    () => {
        if (isSettingEmbeddingForm.value) return
        embeddingTestStatus.value = 'idle'
        embeddingTestMessage.value = ''
        if (embeddingForm.value.is_verified) {
            embeddingForm.value.is_verified = false
        }
    },
    { deep: true }
)

const activeLlmConfig = computed(() => llmStore.getConfigById(activeLlmConfigId.value))
const activeEmbeddingConfig = computed(() => embeddingStore.getConfigById(activeEmbeddingConfigId.value))
const activeMemoryLlmConfig = computed(() => llmStore.getConfigById(activeMemoryLlmConfigId.value))
const activeSmartContextLlmConfig = computed(() =>
    smartContextModel.value ? llmStore.getConfigById(Number(smartContextModel.value)) : null
)
const canEnableThinking = computed(() => !!activeLlmConfig.value?.capability_reasoning)
const canDeleteLlm = computed(() => !!llmForm.value.id || selectedLlmId.value === DRAFT_LLM_ID)
const canDeleteEmbedding = computed(() => !!embeddingForm.value.id || selectedEmbeddingId.value === DRAFT_EMBEDDING_ID)
const activeLlmConfigIdProxy = computed({
    get: () => (activeLlmConfigId.value ? String(activeLlmConfigId.value) : ''),
    set: (val: string) => {
        activeLlmConfigId.value = val ? Number(val) : null
    }
})
const activeEmbeddingConfigIdProxy = computed({
    get: () => (activeEmbeddingConfigId.value ? String(activeEmbeddingConfigId.value) : ''),
    set: (val: string) => {
        activeEmbeddingConfigId.value = val ? Number(val) : null
    }
})
const activeMemoryLlmConfigIdProxy = computed({
    get: () => (activeMemoryLlmConfigId.value ? String(activeMemoryLlmConfigId.value) : ''),
    set: (val: string) => {
        activeMemoryLlmConfigId.value = val ? Number(val) : null
    }
})
const smartContextModelProxy = computed({
    get: () => (smartContextModel.value ? String(smartContextModel.value) : '__default__'),
    set: (val: string) => {
        smartContextModel.value = val === '__default__' ? '' : val
    }
})
const currentTestStatus = computed(() => {
    if (activeTab.value === 'embedding') return embeddingTestStatus.value
    return llmTestStatus.value
})
const currentTestMessage = computed(() => {
    if (activeTab.value === 'embedding') return embeddingTestMessage.value
    return llmTestMessage.value
})
const isElectron = computed(() => !!(window as any).WeAgentChat?.isElectron)

watch(activeLlmConfig, (config) => {
    if (config && !config.capability_reasoning && enableThinking.value) {
        enableThinking.value = false
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
    <Dialog :open="open" @update:open="$emit('update:open', $event)">
        <DialogContent class="sm:max-w-[800px] p-0 overflow-hidden flex h-[600px] gap-0">
            <DialogTitle class="sr-only">设置</DialogTitle>
            <DialogDescription class="sr-only">应用配置界面</DialogDescription>

            <div class="w-[140px] bg-gray-50 border-r border-gray-200 p-2 flex flex-col gap-1">
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
                <button class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    :class="activeTab === 'system' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
                    @click="originalSetTab('system')">
                    系统设置
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
                                <div class="flex items-center justify-between">
                                    <p class="text-sm text-gray-500">配置连接到大语言模型 API 的参数。</p>
                                    <button class="text-xs text-emerald-600 hover:underline" @click="openTutorial">
                                        查看配置教程
                                    </button>
                                </div>
                            </div>

                            <div class="grid gap-4 md:grid-cols-[220px,1fr]">
                                <div class="space-y-3">
                                    <div class="flex items-center justify-between">
                                        <h4 class="text-sm font-semibold text-gray-700">已保存配置</h4>
                                        <Button variant="ghost" size="sm"
                                            class="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                            :disabled="llmAddDisabled" @click="handleAddLlmConfig">
                                            <Plus class="w-4 h-4 mr-1" />
                                            新增
                                        </Button>
                                    </div>

                                    <div v-if="!llmListItems.length"
                                        class="rounded-md border border-dashed bg-gray-50/60 px-3 py-6 text-center text-xs text-gray-400">
                                        暂无配置，点击上方按钮新增
                                    </div>

                                    <div v-else class="space-y-2">
                                        <button v-for="config in llmListItems" :key="config.id"
                                            class="w-full rounded-md border px-3 py-2 text-left text-sm transition hover:border-emerald-300"
                                            :class="selectedLlmId === config.id ? 'border-emerald-400 bg-emerald-50/40' : 'border-gray-200 bg-white'"
                                            @click="config.__draft ? selectLlmDraft() : setLlmFormFromConfig(config)">
                                            <div class="flex items-center justify-between">
                                                <span class="font-medium text-gray-800">{{ config.config_name || '未命名配置'
                                                    }}</span>
                                                <div class="flex items-center gap-1">
                                                    <span v-if="config.__draft"
                                                        class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">未保存</span>
                                                    <button v-if="config.__draft" type="button"
                                                        class="rounded-full p-0.5 text-gray-400 hover:text-gray-600"
                                                        @click.stop="discardLlmDraft">
                                                        <X class="w-3.5 h-3.5" />
                                                    </button>
                                                    <span
                                                        v-else-if="config.id === activeLlmConfigId && config.id === activeMemoryLlmConfigId"
                                                        class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 whitespace-nowrap">聊天/记忆使用中</span>
                                                    <span v-else-if="config.id === activeLlmConfigId"
                                                        class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 whitespace-nowrap">聊天使用中</span>
                                                    <span v-else-if="config.id === activeMemoryLlmConfigId"
                                                        class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 whitespace-nowrap">记忆使用中</span>
                                                    <CheckCircle2 v-if="!config.__draft && config.is_verified"
                                                        class="w-3.5 h-3.5 text-emerald-500" />
                                                    <XCircle v-else-if="!config.__draft"
                                                        class="w-3.5 h-3.5 text-gray-300" />
                                                </div>
                                            </div>
                                            <div class="text-xs text-gray-500 mt-0.5">
                                                {{ LLM_PROVIDER_PRESETS[config.provider || 'openai']?.label ||
                                                    config.provider }}
                                            </div>
                                            <div class="mt-1 flex items-center gap-1 text-gray-400">
                                                <Eye v-if="config.capability_vision" class="w-3.5 h-3.5" />
                                                <Search v-if="config.capability_search" class="w-3.5 h-3.5" />
                                                <BrainCircuit v-if="config.capability_reasoning" class="w-3.5 h-3.5" />
                                                <Wrench v-if="config.capability_function_call" class="w-3.5 h-3.5" />
                                            </div>
                                        </button>
                                    </div>

                                    <p class="text-[10px] text-gray-400">最多可保存 20 条配置</p>
                                </div>

                                <div class="space-y-4">
                                    <div class="flex items-center justify-between">
                                        <h4 class="text-sm font-semibold text-gray-700">配置详情</h4>
                                        <Button variant="ghost" size="sm" class="text-red-600 hover:text-red-700"
                                            :disabled="!canDeleteLlm" @click="handleDeleteLlmConfig">
                                            <Trash2 class="w-4 h-4 mr-1" />
                                            删除
                                        </Button>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">供应商</label>
                                        <Select v-model="llmForm.provider">
                                            <SelectTrigger>
                                                <SelectValue placeholder="选择供应商" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem v-for="(preset, key) in LLM_PROVIDER_PRESETS" :key="key"
                                                    :value="key">
                                                    {{ preset.label }}
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">配置名称</label>
                                        <Input v-model="llmForm.config_name" placeholder="例如：我的智谱" />
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">API Base URL</label>
                                        <Input v-model="llmForm.base_url" placeholder="例如: https://api.openai.com/v1" />
                                        <p class="text-xs text-gray-500">为空则默认使用官方地址。</p>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">API Key</label>
                                        <div class="relative">
                                            <Input v-model="llmForm.api_key" :type="showApiKey ? 'text' : 'password'"
                                                placeholder="sk-..." class="pr-10" />
                                            <button type="button" @click="toggleApiKeyVisibility"
                                                class="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-gray-500 hover:text-gray-900 flex items-center justify-center">
                                                <Eye v-if="!showApiKey" :size="16" />
                                                <EyeOff v-else :size="16" />
                                            </button>
                                        </div>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">Model Name</label>
                                        <Input v-model="llmForm.model_name" placeholder="例如: gpt-3.5-turbo" />
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">模型能力</label>
                                        <div class="grid grid-cols-2 gap-3">
                                            <div
                                                class="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2">
                                                <span class="text-xs text-gray-600">视觉能力</span>
                                                <Switch v-model="llmForm.capability_vision" />
                                            </div>
                                            <div
                                                class="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2">
                                                <span class="text-xs text-gray-600">联网能力</span>
                                                <Switch v-model="llmForm.capability_search" />
                                            </div>
                                            <div
                                                class="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2">
                                                <span class="text-xs text-gray-600">推理能力</span>
                                                <Switch v-model="llmForm.capability_reasoning" />
                                            </div>
                                            <div
                                                class="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 bg-gray-50/50 opacity-70">
                                                <span class="text-xs text-gray-600">工具调用 (必选)</span>
                                                <div class="w-8 h-4 bg-green-500 rounded-full relative">
                                                    <div
                                                        class="absolute right-0.5 top-0.5 w-3 h-3 bg-white rounded-full">
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </template>

                    <template v-if="activeTab === 'embedding'">
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">向量化配置</h3>
                                <div class="flex items-center justify-between">
                                    <p class="text-sm text-gray-500 text-pretty">配置 Embedding 模型 API 的参数。</p>
                                    <button class="text-xs text-emerald-600 hover:underline" @click="openTutorial">
                                        查看配置教程
                                    </button>
                                </div>
                                <p class="text-xs text-amber-600 mt-1.5 font-medium flex items-center gap-1">
                                    <span class="inline-block w-1 h-1 rounded-full bg-amber-600"></span>
                                    如果未正确配置向量化模型，记忆系统将无法正常工作
                                </p>
                            </div>

                            <div class="grid gap-4 md:grid-cols-[220px,1fr]">
                                <div class="space-y-3">
                                    <div class="flex items-center justify-between">
                                        <h4 class="text-sm font-semibold text-gray-700">已保存配置</h4>
                                        <Button variant="ghost" size="sm"
                                            class="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                            :disabled="embeddingAddDisabled" @click="handleAddEmbeddingConfig">
                                            <Plus class="w-4 h-4 mr-1" />
                                            新增
                                        </Button>
                                    </div>

                                    <div v-if="!embeddingListItems.length"
                                        class="rounded-md border border-dashed bg-gray-50/60 px-3 py-6 text-center text-xs text-gray-400">
                                        暂无配置，点击上方按钮新增
                                    </div>

                                    <div v-else class="space-y-2">
                                        <button v-for="config in embeddingListItems" :key="config.id"
                                            class="w-full rounded-md border px-3 py-2 text-left text-sm transition hover:border-emerald-300"
                                            :class="selectedEmbeddingId === config.id ? 'border-emerald-400 bg-emerald-50/40' : 'border-gray-200 bg-white'"
                                            @click="config.__draft ? selectEmbeddingDraft() : setEmbeddingFormFromConfig(config)">
                                            <div class="flex items-center justify-between">
                                                <span class="font-medium text-gray-800">{{ config.config_name || '未命名配置'
                                                    }}</span>
                                                <div class="flex items-center gap-1">
                                                    <span v-if="config.__draft"
                                                        class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">未保存</span>
                                                    <button v-if="config.__draft" type="button"
                                                        class="rounded-full p-0.5 text-gray-400 hover:text-gray-600"
                                                        @click.stop="discardEmbeddingDraft">
                                                        <X class="w-3.5 h-3.5" />
                                                    </button>
                                                    <span v-else-if="config.id === activeEmbeddingConfigId"
                                                        class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 whitespace-nowrap">使用中</span>
                                                    <CheckCircle2 v-if="!config.__draft && config.is_verified"
                                                        class="w-3.5 h-3.5 text-emerald-500" />
                                                    <XCircle v-else-if="!config.__draft"
                                                        class="w-3.5 h-3.5 text-gray-300" />
                                                </div>
                                            </div>
                                            <div class="text-xs text-gray-500 mt-0.5">
                                                {{ EMBEDDING_PROVIDER_LABELS[config.embedding_provider || 'openai'] ||
                                                    config.embedding_provider }}
                                            </div>
                                        </button>
                                    </div>

                                    <p class="text-[10px] text-gray-400">最多可保存 20 条配置</p>
                                </div>

                                <div class="space-y-4">
                                    <div class="flex items-center justify-between">
                                        <h4 class="text-sm font-semibold text-gray-700">配置详情</h4>
                                        <Button variant="ghost" size="sm" class="text-red-600 hover:text-red-700"
                                            :disabled="!canDeleteEmbedding" @click="handleDeleteEmbeddingConfig">
                                            <Trash2 class="w-4 h-4 mr-1" />
                                            删除
                                        </Button>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">配置名称</label>
                                        <Input v-model="embeddingForm.config_name" placeholder="例如：本地 Ollama" />
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">Provider</label>
                                        <Select v-model="embeddingForm.embedding_provider">
                                            <SelectTrigger>
                                                <SelectValue placeholder="选择协议类型" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem v-for="opt in EMBEDDING_PROTOCOL_OPTIONS" :key="opt.value"
                                                    :value="opt.value">
                                                    {{ opt.label }}
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div v-if="embeddingForm.embedding_provider === 'openai'" class="grid gap-2">
                                        <label
                                            class="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">常用预设</label>
                                        <div class="flex flex-wrap gap-2">
                                            <button v-for="(preset, key) in EMBEDDING_PROVIDER_PRESETS" :key="key"
                                                v-show="preset.provider === 'openai'" @click="applyEmbeddingPreset(key)"
                                                class="px-2 py-0.5 text-[11px] rounded-full border border-gray-200 bg-white hover:border-emerald-500 hover:text-emerald-600 transition-colors">
                                                {{ preset.label }}
                                            </button>
                                        </div>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">API Base URL</label>
                                        <Input v-model="embeddingForm.embedding_base_url"
                                            placeholder="例如: https://api.openai.com/v1" />
                                        <p class="text-xs text-gray-500">Embedding API 接口地址。</p>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">API Key</label>
                                        <div class="relative">
                                            <Input v-model="embeddingForm.embedding_api_key"
                                                :type="showApiKey ? 'text' : 'password'" placeholder="sk-..."
                                                class="pr-10" />
                                            <button type="button" @click="toggleApiKeyVisibility"
                                                class="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-gray-500 hover:text-gray-900 flex items-center justify-center">
                                                <Eye v-if="!showApiKey" :size="16" />
                                                <EyeOff v-else :size="16" />
                                            </button>
                                        </div>
                                    </div>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">Model Name</label>
                                        <Input v-model="embeddingForm.embedding_model" placeholder="例如: BAAI/bge-m3" />
                                    </div>

                                    <div class="grid grid-cols-2 gap-4">
                                        <div class="grid gap-2">
                                            <label class="text-sm font-medium leading-none">Dimension</label>
                                            <Input v-model.number="embeddingForm.embedding_dim" type="number"
                                                placeholder="1024" />
                                        </div>
                                        <div class="grid gap-2">
                                            <label class="text-sm font-medium leading-none">Max Token Size</label>
                                            <Input v-model.number="embeddingForm.embedding_max_token_size" type="number"
                                                placeholder="8000" />
                                        </div>
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

                            <div class="space-y-3">
                                <label class="text-sm font-medium leading-none">选择记忆 LLM</label>
                                <Select v-model="activeMemoryLlmConfigIdProxy" :disabled="!llmConfigs.length">
                                    <SelectTrigger>
                                        <SelectValue placeholder="未选择（将沿用聊天模型）" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem v-for="config in llmConfigs" :key="config.id"
                                            :value="String(config.id)">
                                            {{ config.config_name || LLM_PROVIDER_PRESETS[config.provider ||
                                                'openai']?.label || config.provider }}
                                        </SelectItem>
                                    </SelectContent>
                                </Select>
                                <div v-if="!llmConfigs.length" class="text-xs text-gray-400">
                                    请先在「LLM 设置」中添加配置，
                                    <button class="text-emerald-600 hover:underline" @click="originalSetTab('llm')">
                                        立即前往
                                    </button>
                                </div>
                                <div v-else-if="activeMemoryLlmConfig"
                                    class="rounded-md border border-gray-200 bg-gray-50/60 px-3 py-2 text-xs text-gray-600">
                                    <div>模型：{{ activeMemoryLlmConfig.model_name || '未设置' }}</div>
                                    <div>供应商：{{ LLM_PROVIDER_PRESETS[activeMemoryLlmConfig.provider || 'openai']?.label
                                        ||
                                        activeMemoryLlmConfig.provider }}</div>
                                </div>
                                <p class="text-xs text-gray-500">未选择时将使用聊天模型配置。</p>
                            </div>

                            <div class="space-y-3">
                                <label class="text-sm font-medium leading-none">选择向量模型</label>
                                <Select v-model="activeEmbeddingConfigIdProxy" :disabled="!embeddingConfigs.length">
                                    <SelectTrigger>
                                        <SelectValue placeholder="请先添加配置..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem v-for="config in embeddingConfigs" :key="config.id"
                                            :value="String(config.id)">
                                            {{ config.config_name || EMBEDDING_PROVIDER_LABELS[config.embedding_provider
                                                || 'openai'] ||
                                                config.embedding_provider }}
                                        </SelectItem>
                                    </SelectContent>
                                </Select>
                                <div v-if="!embeddingConfigs.length" class="text-xs text-gray-400">
                                    请先在「向量化设置」中添加配置，
                                    <button class="text-emerald-600 hover:underline"
                                        @click="originalSetTab('embedding')">
                                        立即前往
                                    </button>
                                </div>
                                <div v-else-if="activeEmbeddingConfig"
                                    class="rounded-md border border-gray-200 bg-gray-50/60 px-3 py-2 text-xs text-gray-600">
                                    <div>模型：{{ activeEmbeddingConfig.embedding_model || '未设置' }}</div>
                                    <div>维度：{{ activeEmbeddingConfig.embedding_dim || '-' }}</div>
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

                            <div class="space-y-4 border-t pt-6">
                                <div class="flex items-center justify-between">
                                    <label class="text-sm font-medium">启用严格模式</label>
                                    <Switch v-model="memoryStore.profileConfig.strictMode" />
                                </div>
                                <p class="text-xs text-gray-500">
                                    严格模式下仅允许在已配置的主题/子主题内抽取，避免出现未定义分类。
                                </p>
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
                                            <div class="grid gap-2">
                                                <div class="flex items-center justify-between">
                                                    <label class="text-xs font-medium text-gray-500">子主题</label>
                                                    <Button variant="ghost" size="sm"
                                                        class="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                                        @click="handleAddSubTopic(topic)">
                                                        <Plus class="w-3 h-3 mr-1" />
                                                        添加子主题
                                                    </Button>
                                                </div>
                                                <div v-if="!topic.sub_topics?.length"
                                                    class="text-xs text-gray-400 bg-gray-50 rounded-md px-3 py-2 border border-dashed">
                                                    暂无子主题
                                                </div>
                                                <div v-else class="space-y-2">
                                                    <div v-for="(sub, subIndex) in topic.sub_topics" :key="subIndex"
                                                        class="flex items-center gap-2">
                                                        <Input v-model="sub.name" class="h-8 text-sm flex-1"
                                                            placeholder="子主题名称" />
                                                        <Input v-model="sub.description" class="h-8 text-sm flex-1"
                                                            placeholder="说明（可选）" />
                                                        <Button variant="ghost" size="icon"
                                                            class="h-8 w-8 text-gray-400 hover:text-red-500"
                                                            @click="handleRemoveSubTopic(topic, subIndex)">
                                                            <Trash2 :size="14" />
                                                        </Button>
                                                    </div>
                                                </div>
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
                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">选择聊天模型</label>
                                    <Select v-model="activeLlmConfigIdProxy" :disabled="!llmConfigs.length">
                                        <SelectTrigger>
                                            <SelectValue placeholder="请先添加配置..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem v-for="config in llmConfigs" :key="config.id"
                                                :value="String(config.id)">
                                                {{ config.config_name || LLM_PROVIDER_PRESETS[config.provider ||
                                                    'openai']?.label || config.provider }}
                                            </SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div v-if="!llmConfigs.length" class="text-xs text-gray-400">
                                        请先在「LLM 设置」中添加配置，
                                        <button class="text-emerald-600 hover:underline" @click="originalSetTab('llm')">
                                            立即前往
                                        </button>
                                    </div>
                                    <div v-else-if="activeLlmConfig"
                                        class="rounded-md border border-gray-200 bg-gray-50/60 px-3 py-2 text-xs text-gray-600">
                                        <div>模型：{{ activeLlmConfig.model_name || '未设置' }}</div>
                                        <div>供应商：{{ LLM_PROVIDER_PRESETS[activeLlmConfig.provider || 'openai']?.label ||
                                            activeLlmConfig.provider }}</div>
                                    </div>
                                </div>

                                <div class="grid gap-2">
                                    <label class="text-sm font-medium leading-none">
                                        会话过期时间（分钟）
                                    </label>
                                    <Input v-model.number="passiveTimeoutMinutes" type="number" min="1" max="1440"
                                        placeholder="30" />
                                    <p class="text-xs text-gray-500">
                                        这是会话超时检查点。超时后会根据“超时智能复活”设置决定是复活旧会话还是新建会话。
                                    </p>
                                </div>

                                <div class="space-y-3 rounded-md border border-gray-200 bg-gray-50/60 px-3 py-3">
                                    <div class="flex items-center justify-between">
                                        <label class="text-sm font-medium">超时智能复活</label>
                                        <Switch v-model="smartContextEnabled" />
                                    </div>
                                    <p class="text-xs text-gray-500">
                                        超时智能复活：当会话超时后，尝试智能判断是否为同一话题。若是则复活会话，不进行归档。
                                    </p>

                                    <div class="grid gap-2">
                                        <label class="text-sm font-medium leading-none">智能复活判断模型</label>
                                        <Select v-model="smartContextModelProxy" :disabled="!llmConfigs.length">
                                            <SelectTrigger>
                                                <SelectValue placeholder="未选择（将沿用聊天模型）" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="__default__">沿用聊天模型</SelectItem>
                                                <SelectItem v-for="config in llmConfigs" :key="config.id"
                                                    :value="String(config.id)">
                                                    {{ config.config_name || LLM_PROVIDER_PRESETS[config.provider ||
                                                        'openai']?.label || config.provider }}
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <div v-if="activeSmartContextLlmConfig"
                                            class="rounded-md border border-gray-200 bg-white/80 px-3 py-2 text-xs text-gray-600">
                                            <div>模型：{{ activeSmartContextLlmConfig.model_name || '未设置' }}</div>
                                            <div>供应商：{{ LLM_PROVIDER_PRESETS[activeSmartContextLlmConfig.provider ||
                                                'openai']?.label || activeSmartContextLlmConfig.provider }}</div>
                                        </div>
                                        <p class="text-xs text-gray-500">留空时将自动回退到当前聊天模型。</p>
                                    </div>
                                </div>

                                <div class="flex items-center justify-between">
                                    <div class="space-y-0.5">
                                        <label class="text-sm font-medium">启用深度思考模式 (推理)</label>
                                        <p class="text-xs text-gray-500">如果模型支持，开启后将强制模型进行链式思考后再回答。</p>
                                    </div>
                                    <Switch v-model="enableThinking" :disabled="!canEnableThinking" />
                                </div>
                                <p v-if="!canEnableThinking" class="text-xs text-gray-400">
                                    当前模型未标记推理能力，深度思考已禁用。
                                </p>
                            </div>
                        </div>
                    </template>

                    <template v-if="activeTab === 'system'">
                        <div class="space-y-6">
                            <div>
                                <h3 class="text-lg font-medium">系统设置</h3>
                                <p class="text-sm text-gray-500">管理应用的启动行为。</p>
                            </div>

                            <div class="flex items-center justify-between">
                                <div class="space-y-0.5">
                                    <label class="text-sm font-medium">开机自启并最小化</label>
                                    <p class="text-xs text-gray-500">
                                        开启后，系统启动时自动运行并最小化到托盘。
                                    </p>
                                </div>
                                <Switch v-model="autoLaunch" :disabled="!isElectron" />
                            </div>
                            <p v-if="!isElectron" class="text-xs text-gray-400">
                                当前为非桌面端环境，自启设置仅在桌面端生效。
                            </p>
                        </div>
                    </template>
                </div>

                <!-- Footer -->
                <div class="p-4 border-t border-gray-100 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                    <!-- Test result display -->
                    <div v-if="(activeTab === 'llm' || activeTab === 'embedding') && currentTestStatus !== 'idle'"
                        class="mb-3 flex items-center gap-2 text-sm">
                        <CheckCircle2 v-if="currentTestStatus === 'success'" class="w-4 h-4 text-green-500" />
                        <XCircle v-else class="w-4 h-4 text-red-500" />
                        <span :class="currentTestStatus === 'success' ? 'text-green-600' : 'text-red-600'">
                            {{ currentTestMessage }}
                        </span>
                    </div>

                    <div class="flex justify-end gap-2">
                        <Button variant="outline" @click="$emit('update:open', false)">取消</Button>
                        <Button v-if="activeTab === 'llm' || activeTab === 'embedding'" variant="outline"
                            @click="handleTest" :disabled="activeTab === 'llm' ? isLlmTesting : isEmbedTesting">
                            <Loader2 v-if="activeTab === 'llm' ? isLlmTesting : isEmbedTesting"
                                class="w-4 h-4 mr-2 animate-spin" />
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

    <!-- Confirmation Dialog -->
    <Dialog :open="confirmDialog.open" @update:open="(val) => confirmDialog.open = val">
        <DialogContent
            class="sm:max-w-md rounded-2xl border border-[#e6e6e6] shadow-[0_18px_50px_-20px_rgba(0,0,0,0.35)]">
            <DialogHeader class="pb-2">
                <DialogTitle class="text-base font-semibold text-[#111]">{{ confirmDialog.title }}</DialogTitle>
            </DialogHeader>
            <div class="py-4">
                <p class="text-sm text-gray-600 whitespace-pre-line">{{ confirmDialog.message }}</p>
            </div>
            <DialogFooter class="flex gap-2">
                <Button v-if="confirmDialog.showCancel" variant="outline" @click="handleCancel">取消</Button>
                <Button :class="confirmDialog.showCancel ? 'bg-red-600 hover:bg-red-700' : 'bg-gray-900 hover:bg-black'"
                    @click="handleConfirm">
                    {{ confirmDialog.confirmText }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>
