<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  AlertTriangle,
  BookOpenText,
  Brain,
  ChevronLeft,
  LoaderCircle,
  Play,
  Pause,
  RefreshCw,
  Wrench,
} from 'lucide-vue-next'

import { getStaticUrl } from '@/api/base'
import {
  getBookReadingMessages,
  sendBookReadingMessageStream,
  type BookReadingMessageCreate,
  type Message as ApiMessage,
  type PageContextPayload,
  type SelectedQuotePayload,
} from '@/api/chat'
import type { Book } from '@/api/book'
import ToolCallsDetail from '@/components/common/ToolCallsDetail.vue'
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { MessageContent, MessageResponse } from '@/components/ai-elements/message'
import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
} from '@/components/ai-elements/prompt-input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { parseMessageSegments } from '@/utils/chat'
import type { Message as ChatMessage, ToolCall, VoicePayload } from '@/types/chat'
import { useThinkingModeStore } from '@/stores/thinkingMode'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  book: Book
  collapsed: boolean
  pageContext: PageContextPayload | null
  selectedQuote: SelectedQuotePayload | null
}>()

const emit = defineEmits<{
  (e: 'toggle-collapse'): void
  (e: 'clear-selected-quote'): void
}>()

const thinkingModeStore = useThinkingModeStore()
const settingsStore = useSettingsStore()

const getUserAvatar = () => {
  return getStaticUrl(settingsStore.userAvatar) || 'default_avatar.svg'
}

const messages = ref<ChatMessage[]>([])
const input = ref('')
const isLoadingHistory = ref(false)
const historyError = ref<string | null>(null)
const status = ref<'ready' | 'streaming'>('ready')
const sessionId = ref<number | null>(null)
const conversationRef = ref<InstanceType<typeof Conversation> | null>(null)
const currentScrollEl = ref<HTMLElement | null>(null)
const lastSentPageContextSignature = ref<string | null>(null)
const lastSentSelectedQuoteSignature = ref<string | null>(null)
const pendingSelectedQuoteClearSync = ref(false)

const thinkingDialogOpen = ref(false)
const toolCallsDialogOpen = ref(false)
const activeModelThinkingContent = ref('')
const activeRecallThinkingContent = ref('')
const activeToolCalls = ref<ToolCall[]>([])

const activeVoiceKey = ref<string | null>(null)
const activeVoiceState = ref<'playing' | 'paused' | null>(null)
let activeVoiceAudio: HTMLAudioElement | null = null

const friendId = computed(() => props.book.ai_friend_id ?? null)
const isBoundAuthorReady = computed(() => props.book.author_binding_status === 'valid' && !!friendId.value)
const boundAuthorName = computed(() => props.book.bound_friend_name || props.book.author || '未绑定作者')
const boundAuthorAvatar = computed(() => {
  const avatar = getStaticUrl(props.book.bound_friend_avatar) || props.book.bound_friend_avatar
  return avatar || `https://api.dicebear.com/7.x/shapes/svg?seed=book-reader-${props.book.id}`
})

const effectivePageContext = computed<PageContextPayload>(() => (
  props.pageContext ?? {
    supported: false,
    reason: '阅读器尚未定位到当前页',
    text: '',
    excerpt: '',
    locator: '定位中',
    tocPath: [],
    truncated: false,
    sourceType: props.book.format_type || 'unknown',
  }
))


const hasSelectedQuote = computed(() => Boolean(props.selectedQuote?.text?.trim()))

const selectedQuoteTitle = computed(() => {
  if (!hasSelectedQuote.value) {
    return ''
  }
  return props.selectedQuote?.truncated ? '已附加引用内容（已截断）' : '已附加引用内容'
})

const selectedQuoteDetail = computed(() => {
  if (!hasSelectedQuote.value) {
    return ''
  }
  const tocText = props.selectedQuote?.tocPath?.length
    ? props.selectedQuote.tocPath.join(' / ')
    : '未定位到目录'
  return `${props.selectedQuote?.locator || '当前位置'} · ${tocText}`
})

const selectedQuoteText = computed(() => {
  if (!hasSelectedQuote.value) {
    return ''
  }
  return props.selectedQuote?.excerpt?.trim() || props.selectedQuote?.text?.trim() || ''
})

const normalizeSnapshotText = (value?: string | null) => (typeof value === 'string' ? value.trim() : '')

const buildPageContextSignature = (context: PageContextPayload) => JSON.stringify({
  supported: Boolean(context.supported),
  reason: normalizeSnapshotText(context.reason),
  text: normalizeSnapshotText(context.text),
  excerpt: normalizeSnapshotText(context.excerpt),
  locator: normalizeSnapshotText(context.locator),
  tocPath: Array.isArray(context.tocPath) ? context.tocPath.map(item => item.trim()).filter(Boolean) : [],
  truncated: Boolean(context.truncated),
  sourceType: normalizeSnapshotText(context.sourceType),
})

const buildSelectedQuoteSignature = (quote?: SelectedQuotePayload | null) => {
  const text = normalizeSnapshotText(quote?.text)
  if (!text) {
    return ''
  }

  return JSON.stringify({
    text,
    excerpt: normalizeSnapshotText(quote?.excerpt),
    locator: normalizeSnapshotText(quote?.locator),
    tocPath: Array.isArray(quote?.tocPath) ? quote.tocPath.map(item => item.trim()).filter(Boolean) : [],
    truncated: Boolean(quote?.truncated),
    sourceType: normalizeSnapshotText(quote?.sourceType),
  })
}

const inputPlaceholder = computed(() => {
  if (!isBoundAuthorReady.value) {
    return '请先绑定作者后再开启伴读'
  }
  if (hasSelectedQuote.value && effectivePageContext.value.supported) {
    return '输入问题，默认会附加引用内容与当前页正文'
  }
  if (hasSelectedQuote.value) {
    return '输入问题，默认会附加你选中的引用内容'
  }
  if (effectivePageContext.value.supported) {
    return '输入问题，默认会附加当前页正文片段'
  }
  return '输入问题，当前将以无正文上下文模式发送'
})

const stopVoicePlayback = () => {
  if (activeVoiceAudio) {
    activeVoiceAudio.pause()
    activeVoiceAudio.onended = null
    activeVoiceAudio.onerror = null
    activeVoiceAudio = null
  }
  activeVoiceKey.value = null
  activeVoiceState.value = null
}

const normalizeVoicePayload = (raw: any): VoicePayload | undefined => {
  if (!raw || typeof raw !== 'object') return undefined
  const segments = Array.isArray(raw.segments)
    ? raw.segments
      .filter((segment: any) => segment && typeof segment.audio_url === 'string')
      .map((segment: any) => ({
        segment_index: Number.isFinite(Number(segment.segment_index)) ? Number(segment.segment_index) : 0,
        text: typeof segment.text === 'string' ? segment.text : '',
        audio_url: segment.audio_url,
        duration_sec: Number.isFinite(Number(segment.duration_sec)) ? Number(segment.duration_sec) : 1,
      }))
      .sort((left: { segment_index: number }, right: { segment_index: number }) => left.segment_index - right.segment_index)
    : []

  if (!segments.length) return undefined
  return {
    voice_id: String(raw.voice_id || ''),
    segments,
    generated_at: typeof raw.generated_at === 'string' ? raw.generated_at : undefined,
  }
}

const applyVoicePayload = (message: ChatMessage, payload: VoicePayload) => {
  message.voicePayload = payload
  message.voiceUnreadSegmentIndexes = payload.segments
    .map(segment => segment.segment_index)
    .sort((left, right) => left - right)
}

const mergeVoiceSegment = (message: ChatMessage, segment: any) => {
  if (!segment || typeof segment.audio_url !== 'string') return
  const normalizedSegment = {
    segment_index: Number.isFinite(Number(segment.segment_index)) ? Number(segment.segment_index) : 0,
    text: typeof segment.text === 'string' ? segment.text : '',
    audio_url: segment.audio_url,
    duration_sec: Number.isFinite(Number(segment.duration_sec)) ? Number(segment.duration_sec) : 1,
  }

  if (!message.voicePayload) {
    message.voicePayload = {
      voice_id: '',
      segments: [normalizedSegment],
    }
  } else if (!message.voicePayload.segments.some(item => item.segment_index === normalizedSegment.segment_index)) {
    message.voicePayload.segments.push(normalizedSegment)
    message.voicePayload.segments.sort((left, right) => left.segment_index - right.segment_index)
  }
}

const mapApiMessage = (message: ApiMessage): ChatMessage => ({
  id: message.id,
  role: message.role as 'user' | 'assistant' | 'system',
  content: message.content,
  createdAt: new Date(message.create_time).getTime(),
  sessionId: message.session_id,
  voicePayload: normalizeVoicePayload((message as any).voice_payload),
})

const scrollToBottom = async () => {
  await nextTick()
  const element = currentScrollEl.value
  if (!element) return
  element.scrollTop = element.scrollHeight
}

const loadMessages = async () => {
  stopVoicePlayback()
  historyError.value = null
  sessionId.value = null
  lastSentPageContextSignature.value = null
  lastSentSelectedQuoteSignature.value = null
  pendingSelectedQuoteClearSync.value = false

  if (!isBoundAuthorReady.value || !friendId.value) {
    messages.value = []
    return
  }

  isLoadingHistory.value = true
  try {
    const response = await getBookReadingMessages(props.book.id, friendId.value)
    const mapped = response.map(mapApiMessage)
    messages.value = mapped
    sessionId.value = mapped.length ? (mapped[mapped.length - 1].sessionId ?? null) : null
    if (mapped.length > 0 && !hasSelectedQuote.value) {
      pendingSelectedQuoteClearSync.value = true
    }
    await scrollToBottom()
  } catch (error) {
    messages.value = []
    historyError.value = error instanceof Error ? error.message : '伴读消息加载失败'
  } finally {
    isLoadingHistory.value = false
  }
}

const getToolCalls = (message: ChatMessage): ToolCall[] => (
  Array.isArray(message.toolCalls) ? message.toolCalls : []
)

const hasThinking = (message: ChatMessage) => Boolean(
  message.thinkingContent?.trim() || message.recallThinkingContent?.trim(),
)

const openThinkingDialog = (message: ChatMessage) => {
  activeModelThinkingContent.value = message.thinkingContent?.trim() || ''
  activeRecallThinkingContent.value = message.recallThinkingContent?.trim() || ''
  thinkingDialogOpen.value = true
}

const openToolCallsDialog = (message: ChatMessage) => {
  activeToolCalls.value = getToolCalls(message)
  toolCallsDialogOpen.value = true
}

const getAssistantMessageSegments = (message: ChatMessage) => {
  const textSegments = parseMessageSegments(message.content)
  const voiceSegments = (message.voicePayload?.segments || [])
    .slice()
    .sort((left, right) => left.segment_index - right.segment_index)

  if (!voiceSegments.length || textSegments.length >= voiceSegments.length) {
    return textSegments
  }

  return voiceSegments.map((segment, index) => textSegments[index] || segment.text || `语音片段 ${segment.segment_index + 1}`)
}

const getVoiceSegmentForRender = (message: ChatMessage, segmentIndex: number) => {
  const segments = message.voicePayload?.segments || []
  return segments.find(segment => segment.segment_index === segmentIndex) || null
}

const formatVoiceDuration = (duration: number) => `${Math.max(1, Math.round(duration || 1))}″`

const playVoiceSegment = async (message: ChatMessage, segmentIndex: number) => {
  const segment = getVoiceSegmentForRender(message, segmentIndex)
  if (!segment) return

  const key = `${message.id}:${segmentIndex}`
  if (activeVoiceKey.value === key && activeVoiceAudio) {
    if (activeVoiceAudio.paused) {
      try {
        await activeVoiceAudio.play()
        activeVoiceState.value = 'playing'
      } catch (error) {
        console.error('voice resume failed', error)
      }
    } else {
      activeVoiceAudio.pause()
      activeVoiceState.value = 'paused'
    }
    return
  }

  stopVoicePlayback()

  const audio = new Audio(getStaticUrl(segment.audio_url) || segment.audio_url)
  activeVoiceAudio = audio
  activeVoiceKey.value = key
  activeVoiceState.value = 'paused'

  audio.onplay = () => {
    if (activeVoiceKey.value === key) {
      activeVoiceState.value = 'playing'
    }
  }
  audio.onpause = () => {
    if (activeVoiceKey.value === key && !audio.ended) {
      activeVoiceState.value = 'paused'
    }
  }
  audio.onended = () => {
    if (activeVoiceKey.value === key) {
      stopVoicePlayback()
    }
  }
  audio.onerror = () => {
    console.warn('voice playback failed', segment.audio_url)
    stopVoicePlayback()
  }

  try {
    await audio.play()
  } catch (error) {
    console.error('voice play failed', error)
    stopVoicePlayback()
  }
}

const isVoiceSegmentPlaying = (message: ChatMessage, segmentIndex: number) => (
  activeVoiceKey.value === `${message.id}:${segmentIndex}` && activeVoiceState.value === 'playing'
)

const pushAssistantErrorMessage = (
  contentBuffer: string,
  modelThinkingBuffer: string,
  recallThinkingBuffer: string,
  toolCallsBuffer: ToolCall[],
  detail: string,
) => {
  messages.value.push({
    id: Date.now() + 2,
    role: 'assistant',
    content: contentBuffer ? `${contentBuffer}\n\n[错误: ${detail}]` : `[错误: ${detail}]`,
    thinkingContent: modelThinkingBuffer || undefined,
    recallThinkingContent: recallThinkingBuffer || undefined,
    toolCalls: toolCallsBuffer.length ? toolCallsBuffer : undefined,
    createdAt: Date.now(),
    sessionId: sessionId.value ?? undefined,
  })
}

const clearSelectedQuote = () => {
  emit('clear-selected-quote')
}

const handleSubmit = async (_payload?: unknown) => {
  const content = input.value.trim()
  if (!content || status.value === 'streaming' || !isBoundAuthorReady.value || !friendId.value) {
    return
  }

  const userMessage: ChatMessage = {
    id: -(Date.now() + Math.random()),
    role: 'user',
    content,
    createdAt: Date.now(),
    sessionId: sessionId.value ?? undefined,
  }

  messages.value.push(userMessage)
  input.value = ''
  await scrollToBottom()

  let contentBuffer = ''
  let modelThinkingBuffer = ''
  let recallThinkingBuffer = ''
  const toolCallsBuffer: ToolCall[] = []
  const pendingVoicePayloadMap = new Map<number, VoicePayload>()
  const pendingVoiceSegmentsMap = new Map<number, any[]>()
  let currentAssistantMessageId: number | null = null
  let didComplete = false
  let didApplySnapshotSignatures = false

  const currentSelectedQuote = props.selectedQuote
  const currentPageContextSignature = buildPageContextSignature(effectivePageContext.value)
  const currentSelectedQuoteSignature = buildSelectedQuoteSignature(currentSelectedQuote)
  const shouldSendPageContext = currentPageContextSignature !== lastSentPageContextSignature.value
  const shouldSyncClearedSelectedQuote =
    pendingSelectedQuoteClearSync.value &&
    currentSelectedQuoteSignature === ''
  const shouldSendSelectedQuote =
    shouldSyncClearedSelectedQuote ||
    (
      currentSelectedQuoteSignature !== (lastSentSelectedQuoteSignature.value ?? '') &&
      (currentSelectedQuoteSignature !== '' || lastSentSelectedQuoteSignature.value !== null)
    )

  const requestPayload: BookReadingMessageCreate = {
    user_message: content,
    book_id: props.book.id,
    friend_id: friendId.value,
    page_context: shouldSendPageContext ? effectivePageContext.value : undefined,
    selected_quote: shouldSendSelectedQuote
      ? (currentSelectedQuoteSignature
        ? {
            text: currentSelectedQuote!.text,
            excerpt: currentSelectedQuote!.excerpt,
            locator: currentSelectedQuote!.locator,
            tocPath: currentSelectedQuote!.tocPath,
            truncated: currentSelectedQuote!.truncated,
            sourceType: currentSelectedQuote!.sourceType,
          }
        : {
            text: '',
          })
      : undefined,
    enable_thinking: thinkingModeStore.isEnabled,
  }

  status.value = 'streaming'

  try {
    for await (const { event: eventName, data } of sendBookReadingMessageStream(requestPayload)) {
      if (eventName === 'start') {
        sessionId.value = Number(data.session_id) || sessionId.value
        currentAssistantMessageId = Number(data.message_id) || Date.now() + 1
        if (Number.isFinite(Number(data.user_message_id))) {
          userMessage.id = Number(data.user_message_id)
        }
        userMessage.sessionId = sessionId.value ?? undefined
        if (!didApplySnapshotSignatures) {
          if (shouldSendPageContext) {
            lastSentPageContextSignature.value = currentPageContextSignature
          }
          if (shouldSendSelectedQuote) {
            lastSentSelectedQuoteSignature.value = currentSelectedQuoteSignature
            pendingSelectedQuoteClearSync.value = false
          }
          didApplySnapshotSignatures = true
        }
      } else if (eventName === 'message') {
        contentBuffer += data.delta || ''
      } else if (eventName === 'model_thinking' || eventName === 'thinking') {
        modelThinkingBuffer += data.delta || ''
      } else if (eventName === 'recall_thinking') {
        recallThinkingBuffer += data.delta || ''
      } else if (eventName === 'tool_call') {
        toolCallsBuffer.push({
          name: data.tool_name,
          args: data.arguments,
          callId: data.call_id,
          status: 'calling',
        })
      } else if (eventName === 'tool_result') {
        const target = data.call_id
          ? [...toolCallsBuffer].reverse().find(item => item.callId === data.call_id && item.status === 'calling')
          : [...toolCallsBuffer].reverse().find(item => item.name === data.tool_name && item.status === 'calling')
        if (target) {
          target.result = data.result
          target.status = 'completed'
        }
      } else if (eventName === 'voice_segment') {
        const messageId = Number(data.message_id)
        if (!Number.isFinite(messageId)) continue
        const queued = pendingVoiceSegmentsMap.get(messageId) || []
        queued.push(data.segment)
        pendingVoiceSegmentsMap.set(messageId, queued)
      } else if (eventName === 'voice_payload') {
        const messageId = Number(data.message_id)
        const payload = normalizeVoicePayload(data.voice_payload)
        if (!Number.isFinite(messageId) || !payload) continue
        pendingVoicePayloadMap.set(messageId, payload)
      } else if (eventName === 'error' || eventName === 'task_error') {
        pushAssistantErrorMessage(
          contentBuffer,
          modelThinkingBuffer,
          recallThinkingBuffer,
          toolCallsBuffer,
          data.detail || data.message || '伴读回复失败',
        )
      } else if (eventName === 'done') {
        didComplete = true
        const finalMessageId = Number(data.message_id || currentAssistantMessageId || Date.now() + 1)
        const doneVoicePayload = normalizeVoicePayload(data.voice_payload) || pendingVoicePayloadMap.get(finalMessageId)
        const assistantMessage: ChatMessage = {
          id: finalMessageId,
          role: 'assistant',
          content: typeof data.content === 'string' ? data.content : contentBuffer,
          thinkingContent: modelThinkingBuffer || undefined,
          recallThinkingContent: recallThinkingBuffer || undefined,
          toolCalls: toolCallsBuffer.length ? toolCallsBuffer : undefined,
          createdAt: Date.now(),
          sessionId: sessionId.value ?? undefined,
          voicePayload: doneVoicePayload,
          voiceUnreadSegmentIndexes: doneVoicePayload
            ? doneVoicePayload.segments.map(segment => segment.segment_index).sort((left, right) => left - right)
            : undefined,
        }

        const queuedSegments = pendingVoiceSegmentsMap.get(finalMessageId) || []
        queuedSegments.forEach(segment => mergeVoiceSegment(assistantMessage, segment))

        if (doneVoicePayload) {
          applyVoicePayload(assistantMessage, doneVoicePayload)
        }

        messages.value.push(assistantMessage)
      }
    }
  } catch (error) {
    pushAssistantErrorMessage(
      contentBuffer,
      modelThinkingBuffer,
      recallThinkingBuffer,
      toolCallsBuffer,
      error instanceof Error ? error.message : '伴读回复失败',
    )
  } finally {
    status.value = 'ready'
    if (didComplete && hasSelectedQuote.value) {
      clearSelectedQuote()
    }
    await scrollToBottom()
  }
}

watch(
  () => `${props.book.id}:${props.book.ai_friend_id}:${props.book.author_binding_status}`,
  () => {
    void loadMessages()
  },
  { immediate: true },
)

watch(
  () => messages.value.length,
  () => {
    void scrollToBottom()
  },
)

watch(
  () => {
    const conv = conversationRef.value as any
    if (!conv) return undefined
    const scrollRefComputed = conv.scrollRef
    const element = scrollRefComputed?.value ?? scrollRefComputed
    return element as HTMLElement | undefined
  },
  scrollEl => {
    currentScrollEl.value = scrollEl || null
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => {
  stopVoicePlayback()
})
</script>

<template>
  <aside class="reader-chat-panel" :class="{ collapsed }" data-reader-chat-panel>
    <button
      v-if="collapsed"
      type="button"
      class="collapsed-trigger"
      @click="emit('toggle-collapse')"
    >
      <img :src="boundAuthorAvatar" alt="" class="collapsed-avatar" />
      <span class="collapsed-label">伴读</span>
      <ChevronLeft :size="16" />
    </button>

    <template v-else>
      <header class="panel-header">
        <div class="panel-header-main">
          <img :src="boundAuthorAvatar" alt="" class="author-avatar" />
          <div class="author-meta">
            <p class="panel-eyebrow">作者伴读</p>
            <h2 class="author-name">{{ boundAuthorName }}</h2>
            <p class="author-subtitle">{{ book.title }}</p>
          </div>
        </div>

        <button type="button" class="panel-icon-btn" @click="emit('toggle-collapse')">
          <ChevronLeft :size="16" />
        </button>
      </header>

      <div v-if="!isBoundAuthorReady || isLoadingHistory || historyError || messages.length === 0" class="panel-empty-container">
        <ConversationEmptyState
          v-if="!isBoundAuthorReady"
          class="state-card"
          title="未绑定作者"
          :description="book.author_binding_message || '请先返回图书馆为这本书绑定作者，再开启伴读。'"
        >
          <template #icon>
            <AlertTriangle :size="18" />
          </template>
        </ConversationEmptyState>

        <ConversationEmptyState
          v-else-if="isLoadingHistory"
          class="state-card"
          title="正在加载伴读记录"
          description="稍等片刻，正在恢复这本书的专属伴读历史。"
        >
          <template #icon>
            <LoaderCircle :size="18" class="spinning text-green" />
          </template>
        </ConversationEmptyState>

        <ConversationEmptyState
          v-else-if="historyError"
          class="state-card"
          title="伴读记录加载失败"
          :description="historyError"
        >
          <template #icon>
            <AlertTriangle :size="18" />
          </template>
          <button type="button" class="retry-btn" @click="loadMessages">
            <RefreshCw :size="14" />
            <span>重试</span>
          </button>
        </ConversationEmptyState>

        <ConversationEmptyState
          v-else-if="messages.length === 0"
          class="state-card"
          title="开始和作者共读"
          :description="effectivePageContext.supported
            ? '现在可以直接提问，系统会默认附加当前页正文片段。'
            : '现在可以先聊天，但本次消息会以“未附加当前页正文”模式发送。'"
        >
          <template #icon>
            <BookOpenText :size="18" />
          </template>
        </ConversationEmptyState>
      </div>

      <Conversation v-else ref="conversationRef" class="panel-body">
        <ConversationContent class="message-list">
            <template
              v-for="message in messages"
              :key="message.id"
            >
              <!-- 系统消息 -->
              <div v-if="message.role === 'system'" class="msg-system">
                <span>{{ message.content }}</span>
              </div>

              <!-- 助手消息 -->
              <div v-else-if="message.role === 'assistant'" class="msg-row msg-assistant">
                <div class="msg-avatar">
                  <img :src="boundAuthorAvatar" alt="" />
                </div>
                <div class="msg-body">
                  <div v-if="hasThinking(message) || getToolCalls(message).length" class="assistant-meta-actions">
                    <button
                      v-if="hasThinking(message)"
                      type="button"
                      class="meta-chip"
                      @click="openThinkingDialog(message)"
                    >
                      <Brain :size="13" />
                      <span>思考</span>
                    </button>
                    <button
                      v-if="getToolCalls(message).length"
                      type="button"
                      class="meta-chip"
                      @click="openToolCallsDialog(message)"
                    >
                      <Wrench :size="13" />
                      <span>工具</span>
                    </button>
                  </div>
                  <template
                    v-for="(segment, segmentIndex) in getAssistantMessageSegments(message)"
                    :key="`${message.id}:${segmentIndex}`"
                  >
                    <div class="msg-bubble msg-bubble-assistant">
                      <MessageContent>
                        <MessageResponse :content="segment" />
                      </MessageContent>
                    </div>

                    <button
                      v-if="getVoiceSegmentForRender(message, segmentIndex)"
                      type="button"
                      class="voice-chip"
                      @click="playVoiceSegment(message, segmentIndex)"
                    >
                      <Play v-if="!isVoiceSegmentPlaying(message, segmentIndex)" :size="14" />
                      <Pause v-else :size="14" />
                      <span>
                        {{
                          getVoiceSegmentForRender(message, segmentIndex)?.text || `语音片段 ${segmentIndex + 1}`
                        }}
                      </span>
                      <span class="voice-duration">
                        {{
                          formatVoiceDuration(getVoiceSegmentForRender(message, segmentIndex)?.duration_sec || 1)
                        }}
                      </span>
                    </button>
                  </template>
                </div>
              </div>

              <!-- 用户消息 -->
              <div v-else class="msg-row msg-user">
                <div class="msg-body">
                  <div class="msg-bubble msg-bubble-user">
                    <p>{{ message.content }}</p>
                  </div>
                </div>
                <div class="msg-avatar">
                  <img :src="getUserAvatar()" alt="" />
                </div>
              </div>
            </template>
          </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div class="panel-input">
        <section v-if="hasSelectedQuote" class="quote-card">
          <div class="quote-card-header">
            <div>
              <p class="quote-card-title">{{ selectedQuoteTitle }}</p>
              <p class="quote-card-detail">{{ selectedQuoteDetail }}</p>
            </div>
            <button type="button" class="quote-clear-btn" @click="clearSelectedQuote">
              清除
            </button>
          </div>
          <blockquote class="quote-card-content">
            {{ selectedQuoteText }}
          </blockquote>
        </section>
        <PromptInput class="panel-input-form" @submit="handleSubmit">
          <PromptInputTextarea
            v-model="input"
            :disabled="status === 'streaming' || !isBoundAuthorReady"
            :placeholder="inputPlaceholder"
            class="panel-textarea"
          />
          <div class="panel-input-footer">
            <PromptInputSubmit :status="status" :loading="status === 'streaming'" class="send-btn" />
          </div>
        </PromptInput>
      </div>
    </template>
  </aside>

  <Dialog v-model:open="thinkingDialogOpen">
    <DialogContent class="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>模型思考</DialogTitle>
        <DialogDescription>这里展示当前伴读回复的内部推理与召回过程。</DialogDescription>
      </DialogHeader>
      <div class="dialog-scroll">
        <section v-if="activeModelThinkingContent" class="dialog-section">
          <h4>模型思考</h4>
          <pre>{{ activeModelThinkingContent }}</pre>
        </section>
        <section v-if="activeRecallThinkingContent" class="dialog-section">
          <h4>记忆召回</h4>
          <pre>{{ activeRecallThinkingContent }}</pre>
        </section>
      </div>
    </DialogContent>
  </Dialog>

  <Dialog v-model:open="toolCallsDialogOpen">
    <DialogContent class="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>工具调用</DialogTitle>
        <DialogDescription>这里展示这次伴读回复触发的工具调用详情。</DialogDescription>
      </DialogHeader>
      <ToolCallsDetail :tool-calls="activeToolCalls" />
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.reader-chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(244, 247, 244, 0.96) 100%);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.reader-chat-panel.collapsed {
  width: 68px;
  min-width: 68px;
}

.collapsed-trigger {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  height: 100%;
  border: none;
  background: transparent;
  color: #334155;
  cursor: pointer;
}

.collapsed-avatar,
.author-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  object-fit: cover;
  background: #e2e8f0;
}

.collapsed-label {
  writing-mode: vertical-rl;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #087443;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 18px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.panel-header-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.author-meta {
  min-width: 0;
}

.panel-eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #07c160;
}

.author-name {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.author-subtitle {
  margin: 3px 0 0;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.84);
  color: #475569;
  cursor: pointer;
}

.panel-body {
  flex: 1;
  min-height: 0;
  margin: 0 8px;
}

.panel-empty-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 16px;
  min-height: 0;
}

.state-card {
  width: 100%;
  height: max-content !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 140px;
  padding: 20px;
  text-align: center;
  border-radius: 22px;
  border: 1px dashed rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.72);
  color: #475569;
}

.state-card h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.state-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  color: #334155;
  cursor: pointer;
}

/* ===== 消息列表 ===== */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 0 16px;
}

/* 系统消息 */
.msg-system {
  text-align: center;
  padding: 0 12px;
}

.msg-system span {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.7);
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

/* 消息行 */
.msg-row {
  display: flex;
  gap: 10px;
  padding: 0 8px;
}

.msg-assistant {
  flex-direction: row;
  align-items: flex-start;
}

.msg-user {
  flex-direction: row;
  justify-content: flex-end;
  align-items: flex-start;
}

/* 头像 */
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
}

.msg-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 消息内容区 */
.msg-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  max-width: calc(100% - 52px);
}

/* 气泡 */
.msg-bubble {
  padding: 10px 14px;
  border-radius: 4px 18px 18px 18px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
}

.msg-bubble-assistant {
  background: #fff;
  color: #1f2937;
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.msg-bubble-user {
  border-radius: 18px 4px 18px 18px;
  background: #07c160;
  color: #fff;
}

.msg-bubble-user p {
  margin: 0;
}

/* meta 标签 */
.assistant-meta-actions {
  display: flex;
  gap: 6px;
}

.meta-chip,
.voice-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: #475569;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.meta-chip:hover,
.voice-chip:hover {
  background: rgba(241, 245, 249, 0.9);
}

.voice-chip {
  justify-content: space-between;
  max-width: 100%;
}

.voice-duration {
  color: #94a3b8;
}

.panel-input {
  border-top: 1px solid rgba(148, 163, 184, 0.14);
  padding: 14px 16px 16px;
  background: rgba(255, 255, 255, 0.84);
}

.panel-input-form {
  width: 100%;
}

.quote-card {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(7, 193, 96, 0.16);
  background: linear-gradient(180deg, rgba(237, 250, 241, 0.96) 0%, rgba(248, 252, 249, 0.94) 100%);
}

.quote-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.quote-card-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #166534;
}

.quote-card-detail {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.quote-clear-btn {
  flex-shrink: 0;
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: #475569;
  font-size: 12px;
  cursor: pointer;
}

.quote-card-content {
  margin: 10px 0 0;
  padding: 0 0 0 12px;
  border-left: 3px solid rgba(7, 193, 96, 0.26);
  font-size: 13px;
  line-height: 1.6;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-textarea {
  min-height: 92px;
}

.panel-input-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.send-btn {
  flex-shrink: 0;
}

.dialog-scroll {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.dialog-section + .dialog-section {
  margin-top: 16px;
}

.dialog-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.dialog-section pre {
  margin: 0;
  padding: 12px;
  border-radius: 14px;
  background: #f8fafc;
  white-space: pre-wrap;
  word-break: break-word;
  color: #334155;
}

.text-green {
  color: #07c160;
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .reader-chat-panel {
    min-height: 320px;
  }

  .reader-chat-panel.collapsed {
    width: 100%;
    min-width: 0;
    height: 72px;
  }

  .collapsed-trigger {
    flex-direction: row;
  }

  .collapsed-label {
    writing-mode: horizontal-tb;
    letter-spacing: 0.08em;
  }
}
</style>
