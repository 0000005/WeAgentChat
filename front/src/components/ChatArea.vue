<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { parseMessageSegments } from '@/utils/chat'
import type { Message as ChatMessage, ToolCall } from '@/types/chat'
import { useFriendStore } from '@/stores/friend'
import { Menu, MoreHorizontal, Brain, MessageSquarePlus, AlertTriangle, Share2, Play, Pause } from 'lucide-vue-next'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '@/components/ai-elements/conversation'
import { MessageContent, MessageResponse } from '@/components/ai-elements/message'
import { StreamMarkdown } from 'streamdown-vue'
import { useSettingsStore } from '@/stores/settings'
import { getStaticUrl } from '@/api/base'
import { useEmbeddingStore } from '@/stores/embedding'
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit
} from '@/components/ai-elements/prompt-input'
import { useChat } from '@/composables/useChat'
import EmojiPicker from '@/components/EmojiPicker.vue'
import ChatDrawerMenu from '@/components/ChatDrawerMenu.vue'
import ToolCallsDetail from '@/components/common/ToolCallsDetail.vue'
import ChatImageExportDialog from '@/components/common/ChatImageExportDialog.vue'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { useLlmStore } from '@/stores/llm'
import type { ExportMessage } from '@/types/export'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { onMounted, onBeforeUnmount, nextTick, watch } from 'vue'


const props = defineProps({
  isSidebarCollapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-sidebar', 'open-drawer', 'edit-friend', 'open-settings'])

const { messages, input, status, isThinkingMode, toggleThinkingMode, handleSubmit } = useChat()

const sessionStore = useSessionStore()
const friendStore = useFriendStore()
const settingsStore = useSettingsStore()
const llmStore = useLlmStore()
const embeddingStore = useEmbeddingStore()

onMounted(async () => {
  await Promise.all([
    llmStore.fetchConfigs(),
    embeddingStore.fetchConfigs(),
    settingsStore.fetchChatSettings(),
    settingsStore.fetchMemorySettings()
  ])
})

const showNoLlmDialog = ref(false)

const activeLlmConfig = computed(() => llmStore.getConfigById(settingsStore.activeLlmConfigId))
const isLlmConfigured = computed(() => {
  if (!activeLlmConfig.value) return false
  return !!activeLlmConfig.value.api_key
})

const checkLlmConfigAndSubmit = (e?: any) => {
  if (!isLlmConfigured.value) {
    showNoLlmDialog.value = true
    return
  }
  handleSubmit(e)
}

const handleGoToSettings = () => {
  showNoLlmDialog.value = false
  emit('open-settings')
}

const handleOpenEmbeddingSettings = () => {
  emit('open-settings', 'embedding')
}

const activeEmbeddingConfig = computed(() => embeddingStore.getConfigById(settingsStore.activeEmbeddingConfigId))
const isEmbeddingConfigured = computed(() => !!activeEmbeddingConfig.value)

// Get current friend metadata
const currentFriend = computed(() => {
  if (!sessionStore.currentFriendId) return null
  return friendStore.getFriend(sessionStore.currentFriendId)
})

const currentFriendName = computed(() => {
  return currentFriend.value ? currentFriend.value.name : '选择好友'
})

const currentFriendDescription = computed(() => {
  return currentFriend.value?.description || ''
})


const hasMessages = computed(() => messages.value.length > 0)

// 检测是否需要显示会话分隔线（session_id 变化时）
const shouldShowSessionDivider = (index: number): boolean => {
  if (index === 0) return false // 第一条消息不显示分隔线
  const currentMsg = messages.value[index]
  const prevMsg = messages.value[index - 1]

  // 跳过 system 消息的检测（system 消息本身就是分隔线）
  if (currentMsg.role === 'system') return false

  // 如果 sessionId 存在且不同，显示分隔线
  if (currentMsg.sessionId && prevMsg.sessionId && currentMsg.sessionId !== prevMsg.sessionId) {
    return true
  }
  return false
}

// 格式化会话时间戳（类似微信聊天记录中的时间显示）
const formatSessionTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  if (diffDays === 0) {
    // 今天：显示时间
    return timeStr
  } else if (diffDays === 1) {
    // 昨天
    return `昨天 ${timeStr}`
  } else if (diffDays < 7) {
    // 一周内：显示星期几
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    return `${weekdays[date.getDay()]} ${timeStr}`
  } else {
    // 超过一周：显示完整日期
    return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) + ' ' + timeStr
  }
}

// Fallback avatars
const DEFAULT_USER_AVATAR = 'default_avatar.svg'
const DEFAULT_ASSISTANT_AVATAR = 'https://api.dicebear.com/7.x/bottts/svg?seed=doudou'

// Get avatar for user/assistant
const getUserAvatar = () => {
  return getStaticUrl(settingsStore.userAvatar) || DEFAULT_USER_AVATAR
}

const getAssistantAvatar = () => {
  // Use friend's avatar if available
  if (sessionStore.currentFriendId) {
    const friend = friendStore.getFriend(sessionStore.currentFriendId)
    if (friend?.avatar) {
      return getStaticUrl(friend.avatar) || DEFAULT_ASSISTANT_AVATAR
    }
    // Fallback to a seeded avatar for this specific friend
    return `https://api.dicebear.com/7.x/shapes/svg?seed=${sessionStore.currentFriendId}`
  }
  return DEFAULT_ASSISTANT_AVATAR
}

const voicePlaybackKey = ref<string | null>(null)
const voiceAutoPlayEnabled = ref(false)
let activeVoiceAudio: HTMLAudioElement | null = null

const getVoiceSegmentForRender = (msg: ChatMessage, segmentIndex: number) => {
  const segments = msg.voicePayload?.segments
  if (!Array.isArray(segments) || !segments.length) return null
  return segments.find(s => s.segment_index === segmentIndex) || null
}

const hasVoiceSegment = (msg: ChatMessage, segmentIndex: number) => {
  return !!getVoiceSegmentForRender(msg, segmentIndex)
}

const isVoiceSegmentUnread = (msg: ChatMessage, segmentIndex: number) => {
  return !!msg.voiceUnreadSegmentIndexes?.includes(segmentIndex)
}

const markVoiceSegmentAsRead = (msg: ChatMessage, segmentIndex: number) => {
  if (!msg.voiceUnreadSegmentIndexes?.length) return
  msg.voiceUnreadSegmentIndexes = msg.voiceUnreadSegmentIndexes.filter(index => index !== segmentIndex)
}

const formatVoiceDuration = (msg: ChatMessage, segmentIndex: number) => {
  const segment = getVoiceSegmentForRender(msg, segmentIndex)
  const duration = segment?.duration_sec ?? 1
  const safeSeconds = Math.max(1, Math.round(duration))
  return `${safeSeconds}″`
}

const isVoiceSegmentPlaying = (msg: ChatMessage, segmentIndex: number) => {
  return (
    voicePlaybackKey.value === `${msg.id}:${segmentIndex}` &&
    !!activeVoiceAudio &&
    !activeVoiceAudio.paused
  )
}

const stopVoicePlayback = (resetAutoPlay: boolean = true) => {
  if (activeVoiceAudio) {
    activeVoiceAudio.pause()
    activeVoiceAudio.onended = null
    activeVoiceAudio.onerror = null
    activeVoiceAudio = null
  }
  voicePlaybackKey.value = null
  if (resetAutoPlay) {
    voiceAutoPlayEnabled.value = false
  }
}

const resolveNextVoiceTarget = (currentMessageId: number, currentSegmentIndex: number) => {
  const list = messages.value
  const currentMessageIndex = list.findIndex(m => m.id === currentMessageId)
  if (currentMessageIndex === -1) return null

  const currentMessage = list[currentMessageIndex]
  const sameMessageUnread = [...(currentMessage.voiceUnreadSegmentIndexes || [])]
    .filter(index => index > currentSegmentIndex)
    .sort((a, b) => a - b)

  if (sameMessageUnread.length) {
    const candidateIndex = sameMessageUnread[0]
    if (hasVoiceSegment(currentMessage, candidateIndex)) {
      return { message: currentMessage, segmentIndex: candidateIndex }
    }
  }

  const nextMessage = list[currentMessageIndex + 1]
  if (!nextMessage || nextMessage.role !== 'assistant') return null
  const unreadIndexes = [...(nextMessage.voiceUnreadSegmentIndexes || [])].sort((a, b) => a - b)
  if (!unreadIndexes.length) return null
  const nextIndex = unreadIndexes[0]
  if (!hasVoiceSegment(nextMessage, nextIndex)) return null

  return { message: nextMessage, segmentIndex: nextIndex }
}

const playVoiceSegment = async (msg: ChatMessage, segmentIndex: number, autoTriggered: boolean = false) => {
  const segment = getVoiceSegmentForRender(msg, segmentIndex)
  if (!segment) return

  const segmentKey = `${msg.id}:${segmentIndex}`
  if (voicePlaybackKey.value === segmentKey && activeVoiceAudio) {
    if (activeVoiceAudio.paused) {
      try {
        await activeVoiceAudio.play()
      } catch (e) {
        console.error('Voice resume failed:', e)
      }
    }
    return
  }

  stopVoicePlayback(false)
  markVoiceSegmentAsRead(msg, segmentIndex)

  const sourceUrl = getStaticUrl(segment.audio_url) || segment.audio_url
  const audio = new Audio(sourceUrl)
  activeVoiceAudio = audio
  voicePlaybackKey.value = segmentKey

  audio.onended = () => {
    voicePlaybackKey.value = null
    activeVoiceAudio = null
    if (!voiceAutoPlayEnabled.value) return
    const next = resolveNextVoiceTarget(msg.id, segmentIndex)
    if (!next) {
      voiceAutoPlayEnabled.value = false
      return
    }
    void playVoiceSegment(next.message, next.segmentIndex, true)
  }

  audio.onerror = () => {
    console.warn('Voice playback failed:', sourceUrl)
    stopVoicePlayback()
  }

  try {
    await audio.play()
  } catch (e) {
    console.error('Voice play failed:', e)
    stopVoicePlayback()
    if (!autoTriggered) {
      triggerToast('语音播放失败')
    }
  }
}

const handleVoiceBubbleClick = (msg: ChatMessage, segmentIndex: number) => {
  const segmentKey = `${msg.id}:${segmentIndex}`
  if (voicePlaybackKey.value === segmentKey && activeVoiceAudio) {
    if (activeVoiceAudio.paused) {
      voiceAutoPlayEnabled.value = true
      void activeVoiceAudio.play().catch(err => {
        console.error('Voice resume failed:', err)
      })
    } else {
      activeVoiceAudio.pause()
      voiceAutoPlayEnabled.value = false
    }
    return
  }

  voiceAutoPlayEnabled.value = true
  void playVoiceSegment(msg, segmentIndex)
}

// Toast Feedback Logic
const showToast = ref(false)
const toastMessage = ref('')
let toastTimeout: ReturnType<typeof setTimeout> | null = null

const triggerToast = (message: string) => {
  toastMessage.value = message
  showToast.value = true

  if (toastTimeout) clearTimeout(toastTimeout)
  toastTimeout = setTimeout(() => {
    showToast.value = false
  }, 2000)
}

// Chat export selection state
const isSelectMode = ref(false)
const selectedMessageIds = ref<number[]>([])
const exportDialogOpen = ref(false)

const selectableMessages = computed(() => messages.value.filter(msg => msg.role !== 'system' && msg.content))
const selectedMessages = computed(() =>
  selectableMessages.value.filter(msg => selectedMessageIds.value.includes(msg.id))
)

const exportMessages = computed<ExportMessage[]>(() =>
  selectedMessages.value.map(msg => ({
    id: msg.id,
    content: msg.content,
    isUser: msg.role === 'user',
    avatar: msg.role === 'user' ? getUserAvatar() : getAssistantAvatar(),
    name: msg.role === 'assistant' ? currentFriendName.value : '我',
    showName: msg.role === 'assistant',
  }))
)

const enterSelectMode = () => {
  if (!selectableMessages.value.length) {
    triggerToast('暂无可导出的消息')
    return
  }
  isSelectMode.value = true
  selectedMessageIds.value = []
}

const exitSelectMode = () => {
  isSelectMode.value = false
  selectedMessageIds.value = []
}

const isMessageSelected = (id: number) => selectedMessageIds.value.includes(id)

const toggleMessageSelection = (id: number) => {
  const index = selectedMessageIds.value.indexOf(id)
  if (index === -1) {
    selectedMessageIds.value.push(id)
  } else {
    selectedMessageIds.value.splice(index, 1)
  }
}

const handleGenerateExport = () => {
  if (!selectedMessageIds.value.length) {
    triggerToast('请先选择消息')
    return
  }
  exportDialogOpen.value = true
}

defineExpose({
  enterSelectMode,
})

const handleToggleThinking = () => {
  toggleThinkingMode()
  // Toast text based on new state
  const message = isThinkingMode.value ? '已开启思考模式' : '思考模式已关闭'
  triggerToast(message)
}

const handleCopyContent = async (content: string) => {
  if (!content) return
  try {
    await navigator.clipboard.writeText(content)
    triggerToast('复制成功')
  } catch (err) {
    console.error('Copy failed:', err)
    triggerToast('复制失败')
  }
}

const handleNewChat = async () => {
  await sessionStore.startNewSession()
  // Scroll to bottom handles automatically by ConversationScrollButton or watch logic if exists,
  // but usually new messages trigger scroll.
}


// Recall Logic
const recallDialogOpen = ref(false)
const messageToRecall = ref<number | null>(null)
const messageToRecallContent = ref<string | null>(null)

const canRecall = (msg: any) => {
  // Only user messages
  if (msg.role !== 'user') return false

  // For messages with sessionId, check if session is archived
  // memory_generated == 0 means active
  if (msg.sessionId) {
    const session = sessionStore.currentSessions.find(s => s.id === msg.sessionId)
    if (session && session.memory_generated !== 0) {
      return false // Session is archived
    }
  }
  // For messages without sessionId (locally sent, not yet synced) or unknown sessions, allow recall attempt
  // Backend will do final validation
  return true
}

const handleRecallClick = (msg: any) => {
  if (!canRecall(msg)) {
    // Actually we shouldn't even show the button if !canRecall, but double check
    triggerToast('当前会话已归档，无法撤回消息')
    return
  }
  messageToRecall.value = msg.id
  messageToRecallContent.value = msg.content // Store original content
  recallDialogOpen.value = true
}

const confirmRecall = async () => {
  if (!messageToRecall.value) return
  const originalContent = messageToRecallContent.value
  try {
    await sessionStore.recallMessage(messageToRecall.value)
    triggerToast('消息已撤回')
    // Restore content to input box for re-editing
    if (originalContent) {
      input.value = originalContent
    }
  } catch (e: any) {
    console.error(e)
    // Show specific error message if available
    const errorMsg = e?.message?.includes('archived') || e?.message?.includes('归档')
      ? '会话已归档，无法撤回'
      : '撤回失败'
    triggerToast(errorMsg)
  } finally {
    recallDialogOpen.value = false
    messageToRecall.value = null
    messageToRecallContent.value = null
  }
}

const canRegenerate = (msg: any, index: number) => {
  if (msg.role !== 'assistant') return false
  if (sessionStore.isStreaming) return false // Disable while streaming to avoid conflicts

  // Check if session is archived
  if (msg.sessionId) {
    const session = sessionStore.currentSessions.find(s => s.id === msg.sessionId)
    if (session && session.memory_generated !== 0) {
      return false
    }
  }

  // Allow regeneration only for the last message
  return index === messages.value.length - 1
}

const handleRegenerate = async (msg: any) => {
  try {
    await sessionStore.regenerateMessage(msg)
  } catch (e: any) {
    console.error(e)
    const errorMsg = e?.message?.includes('archived') || e?.message?.includes('归档')
      ? '会话已归档，无法重新生成'
      : '重新生成失败'
    triggerToast(errorMsg)
  }
}

const thinkingDialogOpen = ref(false)
const toolCallsDialogOpen = ref(false)
const activeModelThinkingContent = ref('')
const activeRecallThinkingContent = ref('')
const activeToolCalls = ref<ToolCall[]>([])

const getModelThinkingContent = (msg: any): string => {
  const content = msg?.thinkingContent ?? msg?.reasoning ?? msg?.thinking
  if (typeof content !== 'string') return ''
  return content.trim()
}

const getRecallThinkingContent = (msg: any): string => {
  const content = msg?.recallThinkingContent ?? msg?.recall_thinking
  if (typeof content !== 'string') return ''
  return content.trim()
}

const getToolCalls = (msg: any): ToolCall[] => {
  const toolCalls = msg?.toolCalls ?? msg?.tool_calls
  return Array.isArray(toolCalls) ? toolCalls : []
}

const hasThinking = (msg: any) => {
  return getModelThinkingContent(msg).length > 0 || getRecallThinkingContent(msg).length > 0
}
const hasToolCalls = (msg: any) => getToolCalls(msg).length > 0

const handleOpenThinking = (msg: any) => {
  const modelContent = getModelThinkingContent(msg)
  const recallContent = getRecallThinkingContent(msg)
  if (!modelContent && !recallContent) return
  activeModelThinkingContent.value = modelContent
  activeRecallThinkingContent.value = recallContent
  thinkingDialogOpen.value = true
}

const handleOpenToolCalls = (msg: any) => {
  const toolCalls = getToolCalls(msg)
  if (!toolCalls.length) return
  activeToolCalls.value = toolCalls
  toolCallsDialogOpen.value = true
}


/**
 * ============================================================
 * Electron 模式检测与 Web 模式回退逻辑
 * ============================================================
 * 
 * isElectron: 检测当前是否运行在 Electron 桌面环境中
 * 
 * 【"更多"按钮的双模式设计】
 * - Electron 模式 (isElectron = true):
 *   "更多"按钮在 App.vue 的 WindowControls 组件中渲染，
 *   与窗口控制按钮(最小化/最大化/关闭)在同一行，保持完美对齐。
 *   此处不渲染 "更多" 按钮，避免重复。
 * 
 * - Web 浏览器模式 (isElectron = false):
 *   WindowControls 组件不渲染，"更多"按钮回退到此处的 Header 中显示，
 *   确保开发者在 `npm run dev` 时仍能访问菜单功能。
 * 
 * 这不是重复代码，而是针对不同运行环境的适配逻辑。
 */
const isElectron = Boolean(window.WeAgentChat?.windowControls)

const handleToggleMaximize = () => {
  if (!isElectron) return
  window.WeAgentChat?.windowControls?.toggleMaximize()
}

const handleHeaderContextMenu = (event: MouseEvent) => {
  if (!isElectron) return
  event.preventDefault()
  window.WeAgentChat?.windowControls?.showSystemMenu({
    x: event.screenX,
    y: event.screenY,
  })
}

// Drawer 菜单状态 (仅 Web 模式使用，Electron 模式由 App.vue 管理)
const drawerOpen = ref(false)

const handleTitleClick = () => {
  if (sessionStore.currentFriendId) {
    emit('edit-friend', sessionStore.currentFriendId)
  }
}

const handleOpenDrawer = () => {
  if (isElectron) {
    emit('open-drawer')
  } else {
    drawerOpen.value = true
  }
}

// Pagination state
const hasMoreMessages = ref(true)
const conversationRef = ref<InstanceType<typeof Conversation> | null>(null)

// Reset hasMore when friend changes
watch(() => sessionStore.currentFriendId, () => {
  hasMoreMessages.value = true
  stopVoicePlayback()
})

watch(() => sessionStore.currentSessionId, () => {
  stopVoicePlayback()
})

onBeforeUnmount(() => {
  stopVoicePlayback()
})

// Pagination using IntersectionObserver - triggers when top sentinel becomes visible
const loadMoreTriggerRef = ref<HTMLElement | null>(null)
let intersectionObserver: IntersectionObserver | null = null

const loadMore = async () => {
  if (!hasMoreMessages.value || sessionStore.isLoadingMore || !sessionStore.currentFriendId) return

  const scrollEl = currentScrollEl
  const prevHeight = scrollEl?.scrollHeight || 0
  const prevScrollTop = scrollEl?.scrollTop || 0

  const more = await sessionStore.loadMoreMessages(sessionStore.currentFriendId)
  hasMoreMessages.value = more

  // Maintain scroll position after DOM updates
  if (scrollEl) {
    nextTick(() => {
      const newHeight = scrollEl.scrollHeight
      const heightDiff = newHeight - prevHeight
      scrollEl.scrollTop = prevScrollTop + heightDiff
    })
  }
}

// Track scroll element to maintain position
let currentScrollEl: HTMLElement | null = null

watch(
  // Watch the scrollRef - it resolves directly to HTMLElement
  () => {
    const conv = conversationRef.value as any
    if (!conv) return undefined
    const scrollRefComputed = conv.scrollRef
    const element = scrollRefComputed?.value ?? scrollRefComputed
    return element as HTMLElement | undefined
  },
  (scrollEl) => {
    currentScrollEl = scrollEl || null
  },
  { immediate: true, flush: 'post' }
)

// Setup IntersectionObserver for load-more trigger
watch(loadMoreTriggerRef, (el) => {
  // Cleanup old observer
  if (intersectionObserver) {
    intersectionObserver.disconnect()
    intersectionObserver = null
  }

  if (el) {
    intersectionObserver = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry && entry.isIntersecting) {
          console.log('[Pagination] Load more triggered by IntersectionObserver')
          loadMore()
        }
      },
      { threshold: 0.1 }
    )
    intersectionObserver.observe(el)
  }
}, { immediate: true })

// Avatar Preview Logic
const showAvatarPreview = ref(false)
const previewAvatarUrl = ref('')

const handleAvatarClick = (url: string) => {
  previewAvatarUrl.value = url
  showAvatarPreview.value = true
}
</script>

<template>
  <div class="wechat-chat-area" :class="{ 'select-mode': isSelectMode }">
    <!-- Header -->
    <header class="chat-header" :class="{ 'electron-mode': isElectron }" @contextmenu="handleHeaderContextMenu">
      <button v-if="isSidebarCollapsed" @click="emit('toggle-sidebar')" class="mobile-menu-btn">
        <Menu :size="20" />
      </button>
      <div class="header-drag-area" @dblclick="handleToggleMaximize">
        <div v-if="sessionStore.currentFriendId" id="chat-title-area" class="chat-title-container"
          @click="handleTitleClick">
          <div class="title-text-group">
            <h2 class="chat-title">{{ currentFriendName }}</h2>
            <span v-if="sessionStore.isStreaming" class="typing-indicator">对方正在输入...</span>
          </div>

          <template v-if="currentFriendDescription && !sessionStore.isStreaming">
            <span class="title-separator">|</span>

            <TooltipProvider>
              <Tooltip :delay-duration="300">
                <TooltipTrigger as-child>
                  <span class="chat-description">{{ currentFriendDescription }}</span>
                </TooltipTrigger>
                <TooltipContent v-if="currentFriendDescription.length > 20" side="bottom" class="max-w-xs">
                  <p class="text-xs">{{ currentFriendDescription }}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </template>
        </div>
        <h2 v-else class="chat-title">{{ currentFriendName }}</h2>
      </div>

      <div class="header-actions">
        <!-- 
          "更多"按钮 - Web 模式回退
          仅在 Web 浏览器模式下显示 (v-if="!isElectron")
          Electron 模式下此按钮在 App.vue 的 WindowControls 中渲染
          详见上方 script 中的注释说明
        -->
        <button v-if="!isElectron" class="more-btn" @click="handleOpenDrawer">
          <MoreHorizontal :size="20" />
        </button>
      </div>
    </header>

    <!-- Messages Area -->
    <div class="chat-messages-container flex-col">
      <!-- Vectorization Warning Banner -->
      <div v-if="!isEmbeddingConfigured" class="vector-warning-banner" @click="handleOpenEmbeddingSettings">
        <div class="banner-content">
          <AlertTriangle :size="16" class="warning-icon" />
          <span>向量化模型未配置，记忆系统将无法工作。</span>
          <span class="action-link">去配置 &gt;</span>
        </div>
      </div>

      <!-- Session Navigation Banner (Back to Merged View) -->
      <div v-if="sessionStore.currentSessionId" class="session-nav-banner">
        <div class="banner-content">
          <Sparkles :size="14" class="nav-icon" />
          <span class="nav-text">当前正在查看历史对话</span>
          <button class="nav-action-btn" @click="sessionStore.resetToMergedView">
            返回全部消息
          </button>
        </div>
      </div>

      <!-- Empty State with WeChat Logo -->
      <div v-if="!hasMessages" class="empty-state flex-1">
        <div class="wechat-logo">
          <svg viewBox="0 0 100 100" class="logo-svg">
            <g fill="#c8c8c8">
              <ellipse cx="38" cy="45" rx="28" ry="24" />
              <ellipse cx="62" cy="55" rx="28" ry="24" />
              <circle cx="30" cy="42" r="4" fill="#f5f5f5" />
              <circle cx="46" cy="42" r="4" fill="#f5f5f5" />
              <circle cx="54" cy="58" r="3" fill="#e9e9e9" />
              <circle cx="70" cy="58" r="3" fill="#e9e9e9" />
            </g>
          </svg>
        </div>
      </div>

      <!-- Conversation with Messages -->
      <Conversation ref="conversationRef" v-else class="flex-1 w-full overflow-hidden">
        <ConversationContent class="messages-content">
          <!-- Load More Trigger (observed by IntersectionObserver) -->
          <div ref="loadMoreTriggerRef" class="load-more-trigger">
            <div v-if="sessionStore.isLoadingMore" class="loading-more-container">
              <div class="loading-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
            <div v-else-if="!hasMoreMessages && messages.length >= sessionStore.INITIAL_MESSAGE_LIMIT"
              class="no-more-messages">
              已经到头了
            </div>
          </div>
          <template v-for="(msg, index) in messages" :key="msg.id">
            <!-- 会话分隔线（session_id 变化时显示） -->
            <div v-if="shouldShowSessionDivider(index)" class="session-divider">
              <span class="divider-time">{{ formatSessionTime(msg.createdAt) }}</span>
            </div>

            <div v-if="msg.role === 'system'" class="message-system">
              <span>{{ msg.content }}</span>
            </div>

            <template v-else-if="msg.role === 'assistant'">
              <div class="message-row" :class="{ 'is-selected': isMessageSelected(msg.id) }">
                <button v-if="isSelectMode" class="select-checkbox" :class="{ selected: isMessageSelected(msg.id) }"
                  @click.stop="toggleMessageSelection(msg.id)" aria-label="选择消息"></button>
                <div class="message-stack">
                  <!-- AI 回复：动态拆分渲染 -->
                  <div v-for="(segment, sIndex) in parseMessageSegments(msg.content)" :key="msg.id + '-' + sIndex"
                    class="message-group group-assistant">
                    <div class="message-wrapper message-assistant group relative">
                      <!-- Avatar -->
                      <div class="message-avatar" @click="handleAvatarClick(getAssistantAvatar())">
                        <img :src="getAssistantAvatar()" alt="Avatar" />
                      </div>

                      <!-- Message Bubble -->
                      <div class="message-bubble-container" :class="{ 'message-pop-in': segment }">
                        <template v-if="hasVoiceSegment(msg, sIndex)">
                          <button class="voice-bubble" type="button" @click="handleVoiceBubbleClick(msg, sIndex)">
                            <span class="voice-icon">
                              <Pause v-if="isVoiceSegmentPlaying(msg, sIndex)" :size="14" />
                              <Play v-else :size="14" />
                            </span>
                            <span class="voice-wave"></span>
                            <span class="voice-duration">{{ formatVoiceDuration(msg, sIndex) }}</span>
                            <span v-if="isVoiceSegmentUnread(msg, sIndex)" class="voice-unread-dot"></span>
                          </button>
                          <div class="voice-text">
                            <MessageContent>
                              <MessageResponse :content="segment" />
                            </MessageContent>
                          </div>
                        </template>
                        <div v-else class="message-bubble">
                          <MessageContent>
                            <MessageResponse :content="segment" />
                          </MessageContent>
                        </div>
                      </div>

                      <!-- Message Action Menu -->
                      <div class="message-actions">
                        <DropdownMenu>
                          <DropdownMenuTrigger as-child>
                            <button
                              class="message-action-btn opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100 transition-opacity">
                              <MoreHorizontal :size="16" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start">
                            <DropdownMenuItem @click="handleCopyContent(segment)">
                              <span>复制</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem v-if="hasThinking(msg)" @click="handleOpenThinking(msg)">
                              <span>查看思考过程</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem v-if="hasToolCalls(msg)" @click="handleOpenToolCalls(msg)">
                              <span>查看工具调用</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem v-if="canRegenerate(msg, index)" @click="handleRegenerate(msg)">
                              <span>重新回答</span>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <div v-else class="message-row" :class="{ 'is-selected': isMessageSelected(msg.id) }">
              <button v-if="isSelectMode" class="select-checkbox" :class="{ selected: isMessageSelected(msg.id) }"
                @click.stop="toggleMessageSelection(msg.id)" aria-label="选择消息"></button>
              <div class="message-stack">
                <div class="message-group group-user">
                  <div class="message-wrapper message-user group relative">
                    <!-- Avatar -->
                    <div class="message-avatar" @click="handleAvatarClick(getUserAvatar())">
                      <img :src="getUserAvatar()" alt="Avatar" />
                    </div>

                    <!-- Message Bubble -->
                    <div class="message-bubble-container" :class="{ 'message-pop-in': msg.content }">
                      <!-- Normal message content -->
                      <div v-if="msg.content" class="message-bubble">
                        <MessageContent>
                          <MessageResponse :content="msg.content" />
                        </MessageContent>
                      </div>
                    </div>

                    <!-- Message Action Menu -->
                    <div class="message-actions">
                      <DropdownMenu>
                        <DropdownMenuTrigger as-child>
                          <button
                            class="message-action-btn opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100 transition-opacity">
                            <MoreHorizontal :size="16" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem @click="handleCopyContent(msg.content)">
                            <span>复制</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem v-if="canRecall(msg)" @click="handleRecallClick(msg)">
                            <span class="text-red-500">撤回</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- Note: Loading state is now handled within the message loop above -->
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>
    </div>


    <!-- Input Area -->
    <div v-if="!isSelectMode" class="chat-input-area">
      <div class="input-toolbar">
        <EmojiPicker @select="input += $event" />
        <button class="toolbar-btn" title="新会话" @click="handleNewChat">
          <MessageSquarePlus :size="22" />
        </button>
        <button class="toolbar-btn" title="分享/导出" @click="enterSelectMode">
          <Share2 :size="18" />
        </button>
      </div>

      <PromptInput class="input-box" @submit="checkLlmConfigAndSubmit">
        <PromptInputTextarea v-model="input" placeholder="输入消息..." class="input-textarea" />
        <div class="input-footer">
          <div class="footer-left">
            <!-- Thinking Mode Toggle -->
            <button type="button" class="thinking-btn" :class="{ 'active': isThinkingMode }"
              @click="handleToggleThinking" title="深度思考">
              <Brain :size="18" />
            </button>
          </div>

          <PromptInputSubmit :status="status" :loading="status === 'streaming'" class="send-btn" />
        </div>
      </PromptInput>
    </div>
    <div v-else class="export-selection-bar">
      <button class="selection-btn cancel" @click="exitSelectMode">取消</button>
      <span class="selection-count">已选 {{ selectedMessageIds.length }} 条</span>
      <button class="selection-btn primary" :disabled="selectedMessageIds.length === 0"
        @click="handleGenerateExport">生成图片</button>
    </div>

    <!-- Toast Feedback -->
    <Transition name="fade">
      <div v-if="showToast" class="toast-feedback">
        {{ toastMessage }}
      </div>
    </Transition>

    <!-- 
      Drawer 菜单组件 - Web 模式回退
      仅在 Web 浏览器模式下渲染 (v-if="!isElectron")
      Electron 模式下由 App.vue 中的 ChatDrawerMenu 处理
    -->
    <ChatDrawerMenu v-if="!isElectron" v-model:open="drawerOpen" />

    <Dialog v-model:open="thinkingDialogOpen">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>思考过程</DialogTitle>
        </DialogHeader>
        <div class="thinking-dialog-body">
          <div v-if="activeRecallThinkingContent" class="thinking-section">
            <div class="thinking-section-title">回忆思维链</div>
            <StreamMarkdown :content="activeRecallThinkingContent"
              :shiki-theme="{ light: 'github-light', dark: 'github-dark' }" class="thinking-markdown" />
          </div>
          <div v-if="activeModelThinkingContent" class="thinking-section">
            <div class="thinking-section-title">模型思维链</div>
            <StreamMarkdown :content="activeModelThinkingContent"
              :shiki-theme="{ light: 'github-light', dark: 'github-dark' }" class="thinking-markdown" />
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="toolCallsDialogOpen">
      <DialogContent class="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>工具调用</DialogTitle>
        </DialogHeader>
        <div class="tool-calls-dialog-body">
          <ToolCallsDetail :tool-calls="activeToolCalls" />
        </div>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="showAvatarPreview">
      <DialogContent
        class="p-0 bg-transparent border-none shadow-none max-w-3xl w-auto flex justify-center items-center">
        <img :src="previewAvatarUrl" class="max-w-full max-h-[80vh] object-contain rounded-md" alt="Avatar Preview" />
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="showNoLlmDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <div class="flex items-center gap-3 mb-2">
            <div class="p-2 bg-amber-100 rounded-full">
              <AlertTriangle class="h-6 w-6 text-amber-600" />
            </div>
            <DialogTitle>未配置 AI 模型</DialogTitle>
          </div>
          <DialogDescription class="text-base">
            发送消息需要先配置大语言模型（LLM）。目前检测到您尚未设置 API Key 或接口地址。
          </DialogDescription>
        </DialogHeader>
        <div class="py-4 text-sm text-gray-500 bg-gray-50 p-4 rounded-md border border-gray-100">
          请前往“设置 -> LLM 设置”中完成配置，配置完成后即可开始对话。
        </div>
        <DialogFooter class="sm:justify-end gap-2">
          <Button variant="ghost" @click="showNoLlmDialog = false">
            稍后再说
          </Button>
          <Button type="button" variant="default" @click="handleGoToSettings"
            class="bg-emerald-600 hover:bg-emerald-700">
            去配置
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <ChatImageExportDialog v-model:open="exportDialogOpen" :messages="exportMessages" title="聊天记录图片预览" />

    <!-- Recall Confirmation Dialog -->
    <Dialog v-model:open="recallDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>确认撤回消息？</DialogTitle>
          <DialogDescription>
            撤回后消息将无法恢复，且后端会自动重置对话上下文。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter class="sm:justify-end gap-2">
          <Button variant="ghost" @click="recallDialogOpen = false">
            取消
          </Button>
          <Button type="button" variant="destructive" @click="confirmRecall">
            确认撤回
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.wechat-chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f5f5;
}

/* Header */
.chat-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  /* Default padding for web mode */
  background: #f5f5f5;
  border-bottom: 1px solid #e5e5e5;
  user-select: none;
}

/* Extra padding for Electron mode to accommodate window controls */
.chat-header.electron-mode {
  padding: 0 170px 0 16px;
}

.mobile-menu-btn {
  padding: 8px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  -webkit-app-region: no-drag;
}

.mobile-menu-btn:hover {
  background: #e5e5e5;
}

.chat-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  text-align: center;
}

.header-drag-area {
  flex: 1;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  height: 100%;
  padding-left: 8px;
  -webkit-app-region: drag;
}

.chat-title-container {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
  -webkit-app-region: no-drag;
  max-width: 100%;
  overflow: hidden;
}

.chat-title-container:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.chat-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  flex-shrink: 0;
  text-align: left;
}

.title-separator {
  color: #ccc;
  font-size: 14px;
  margin-top: 1px;
}

.chat-description {
  font-size: 12px;
  color: #999;
  font-weight: normal;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.title-text-group {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
}

.typing-indicator {
  font-size: 11px;
  color: #888;
  margin-top: -2px;
  animation: typing-fade 1.5s infinite ease-in-out;
  text-align: left;
}

@keyframes typing-fade {
  0%,
  100% {
    opacity: 0.6;
  }

  50% {
    opacity: 1;
  }
}

.message-pop-in {
  animation: message-pop-in 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
}

@keyframes message-pop-in {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(10px);
  }

  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

/* 窄屏适配：隐藏描述 */
@media (max-width: 640px) {

  .chat-description,
  .title-separator {
    display: none;
  }
}

.header-actions {

  display: flex;
  align-items: center;
  gap: 4px;
  -webkit-app-region: no-drag;
}

.more-btn {
  padding: 8px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  -webkit-app-region: no-drag;
}

.more-btn:hover {
  background: #e5e5e5;
}

/* Empty State */
.chat-messages-container {
  flex: 1;
  overflow: hidden;
  position: relative;
  display: flex !important;
  flex-direction: column;
}

.vector-warning-banner {
  background-color: #fef0f0;
  color: #f56c6c;
  padding: 8px 16px;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-bottom: 1px solid #fde2e2;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.vector-warning-banner:hover {
  background-color: #fde2e2;
}

.session-nav-banner {
  background-color: #f1f7ff;
  color: #576b95;
  padding: 8px 16px;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #e1e7f0;
  transition: all 0.2s;
  flex-shrink: 0;
}

.session-nav-banner .nav-icon {
  color: #576b95;
}

.session-nav-banner .nav-text {
  color: #7d8b9e;
}

.nav-action-btn {
  font-weight: 500;
  color: #576b95;
  cursor: pointer;
  margin-left: 4px;
}

.nav-action-btn:hover {
  text-decoration: underline;
  opacity: 0.8;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-link {
  text-decoration: underline;
  margin-left: 4px;
}

.warning-icon {
  flex-shrink: 0;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wechat-logo {
  width: 180px;
  height: 180px;
  opacity: 0.5;
}

.logo-svg {
  width: 100%;
  height: 100%;
}

/* Messages */
.messages-content {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-row {
  display: flex;
  width: 100%;
  align-items: flex-start;
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.select-checkbox {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  border: 1.5px solid #c7c7c7;
  background: #fff;
  margin-top: 6px;
  flex-shrink: 0;
  position: relative;
  cursor: pointer;
  transition: all 0.15s ease;
}

.select-checkbox.selected {
  border-color: #07c160;
  background: #07c160;
}

.select-checkbox.selected::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  background: #fff;
  border-radius: 999px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.wechat-chat-area.select-mode .message-row {
  gap: 12px;
}

.wechat-chat-area.select-mode .message-row .message-wrapper {
  opacity: 0.75;
}

.wechat-chat-area.select-mode .message-row.is-selected .message-wrapper {
  opacity: 1;
}

.wechat-chat-area.select-mode .message-actions {
  display: none;
}

.message-wrapper {
  display: flex;
  gap: 10px;
  max-width: 85%;
}

.message-user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.message-assistant {
  flex-direction: row;
  align-self: flex-start;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;

}

.message-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s;
}

.message-avatar:hover img {
  transform: scale(1.05);
}


.message-bubble-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.message-user .message-bubble {
  background: #95ec69;
  color: #000;
}

.message-assistant .message-bubble {
  background: #fff;
  color: #333;
}

.voice-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 140px;
  border: 0;
  background: #fff;
  border-radius: 8px;
  padding: 9px 12px;
  cursor: pointer;
  color: #2f2f2f;
  box-shadow: inset 0 0 0 1px #ececec;
}

.voice-bubble:hover {
  background: #f8f8f8;
}

.voice-icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #07c160;
  flex-shrink: 0;
}

.voice-wave {
  flex: 1;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #07c160 0%, #61d596 100%);
  opacity: 0.75;
}

.voice-duration {
  font-size: 12px;
  color: #666;
  flex-shrink: 0;
}

.voice-unread-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #ff4d4f;
  flex-shrink: 0;
}

.voice-text {
  background: #fff;
  color: #333;
  border-radius: 4px;
  padding: 9px 12px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.loading-bubble {
  background: #fff;
  padding: 12px 16px;
}

.reasoning-block {
  max-width: 100%;
}

.message-system {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 16px 0;
  color: #999;
  font-size: 12px;
  width: 100%;
}

.message-system span {
  background: rgba(0, 0, 0, 0.05);
  padding: 4px 12px;
  border-radius: 12px;
}

/* Message Group Wrapper */
.message-group {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.group-user {
  align-items: flex-end;
}

.group-assistant {
  align-items: flex-start;
}

/* Pagination Indicators */
.loading-more-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 10px 0;
  width: 100%;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  background-color: #ccc;
  border-radius: 50%;
  animation: dots-wave 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes dots-wave {

  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1.0);
  }
}

.no-more-messages {
  text-align: center;
  color: #bbb;
  font-size: 12px;
  padding: 10px 0;
  width: 100%;
  user-select: none;
}

/* External Reasoning Container */
.reasoning-external-container {
  margin-left: 50px;
  /* Align with message text (40px avatar + 10px gap) */
  margin-bottom: 4px;
  max-width: calc(100% - 60px);
  /* Prevent overflow */
}

@media (min-width: 640px) {
  .reasoning-external-container {
    max-width: calc(85% - 50px);
  }
}

/* 会话分隔线 */
.session-divider {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 20px 0;
  width: 100%;
}

.divider-time {
  background: rgba(0, 0, 0, 0.06);
  color: #888;
  font-size: 11px;
  padding: 4px 14px;
  border-radius: 14px;
  letter-spacing: 0.5px;
}

/* Input Area */
.chat-input-area {
  background: #f5f5f5;
  border-top: 1px solid #e5e5e5;
  padding: 8px 16px 16px;
}

.export-selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #f5f5f5;
  border-top: 1px solid #e5e5e5;
  gap: 12px;
}

.selection-count {
  font-size: 13px;
  color: #666;
}

.selection-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #e5e5e5;
  background: #fff;
  color: #333;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.selection-btn:hover {
  background: #f0f0f0;
}

.selection-btn.primary {
  background: #07c160;
  border-color: #07c160;
  color: #fff;
}

.selection-btn.primary:disabled {
  background: #a0d8b7;
  border-color: #a0d8b7;
  cursor: not-allowed;
}

.input-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.toolbar-btn {
  padding: 6px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.toolbar-btn:hover {
  background: #e5e5e5;
  color: #333;
}

.input-box {
  background: #fff;
  border-radius: 4px;
  border: none !important;
  box-shadow: none !important;
}

.input-textarea {
  min-height: 80px;
  max-height: 200px;
  padding: 10px 12px;
  font-size: 14px;
  border: none !important;
  background: transparent;
  resize: none;
  outline: none;
}

.input-textarea:focus {
  box-shadow: none !important;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.voice-btn {
  padding: 6px;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  border-radius: 4px;
}

.voice-btn:hover {
  color: #666;
}

.thinking-btn {
  padding: 6px;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.thinking-btn:hover {
  color: #666;
}

.thinking-btn.active {
  color: #07c160;
}

.thinking-label {
  display: none;
}

.send-btn {
  padding: 6px 16px;
  background: #07c160;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.send-btn:hover {
  background: #06ad56;
}

.send-btn:disabled {
  background: #a0d8b7;
  cursor: not-allowed;
}

/* Toast Feedback */
.toast-feedback {
  position: absolute;
  top: 40%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 1000;
  pointer-events: none;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -40%);
}

/* Override ai-elements styles */
:deep([data-slot="input-group"]) {
  flex-direction: column !important;
  align-items: stretch !important;
  height: auto !important;
  border: none !important;
  box-shadow: none !important;
}

:deep(.conversation) {
  height: 100%;
}

/* Message Group Wrapper */
.message-group {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.group-user {
  align-items: flex-end;
}

.group-assistant {
  align-items: flex-start;
}

/* External Reasoning Container */
.reasoning-external-container {
  margin-left: 50px;
  /* Align with message text (40px avatar + 10px gap) */
  margin-bottom: 4px;
  max-width: calc(100% - 60px);
  /* Prevent overflow */
}

@media (min-width: 640px) {
  .reasoning-external-container {
    max-width: calc(85% - 50px);
  }
}

.tool-calls-container {
  width: 100%;
  max-width: 100%;
}

:deep(.tool-calls-container .tool) {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.thinking-dialog-body,
.tool-calls-dialog-body {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

:deep(.thinking-markdown) {
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}

:deep(.thinking-markdown pre) {
  background: #f7f7f7;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 10px;
}

.thinking-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thinking-section+.thinking-section {
  margin-top: 16px;
}

.thinking-section-title {
  font-size: 12px;
  color: #888;
  letter-spacing: 0.4px;
}

/* Message Actions */
.message-actions {
  display: flex;
  align-items: center;
  padding: 0 4px;
  align-self: center;
  /* Center vertically relative to the bubble */
}

.message-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background-color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.05);
  color: #666;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.message-action-btn:hover {
  background-color: #fff;
  color: #333;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

</style>
