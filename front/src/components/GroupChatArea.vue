<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { parseMessageSegments } from '@/utils/chat'
import { useFriendStore } from '@/stores/friend'
import { useGroupStore } from '@/stores/group'
import { useSettingsStore } from '@/stores/settings'
import type { AutoDriveMode, DebateSide, Message } from '@/types/chat'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Menu, MoreHorizontal, Brain, MessageSquarePlus, Sparkles, Pause, Play, Square, RefreshCw, Share2 } from 'lucide-vue-next'
import { useThinkingModeStore } from '@/stores/thinkingMode'
import { useLlmStore } from '@/stores/llm'
import { useEmbeddingStore } from '@/stores/embedding'

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '@/components/ai-elements/conversation'
import { MessageContent, MessageResponse } from '@/components/ai-elements/message'
import { StreamMarkdown } from 'streamdown-vue'
import ToolCallsDetail from '@/components/common/ToolCallsDetail.vue'
import EmojiPicker from '@/components/EmojiPicker.vue'
import { getStaticUrl } from '@/api/base'
import ChatImageExportDialog from '@/components/common/ChatImageExportDialog.vue'
import type { ExportMessage } from '@/types/export'

import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit
} from '@/components/ai-elements/prompt-input'

import GroupAvatar from './common/GroupAvatar.vue'
import GroupAutoDriveConfigDialog from './GroupAutoDriveConfigDialog.vue'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import {
  PromptInputCommand,
  PromptInputCommandEmpty,
  PromptInputCommandGroup,
  PromptInputCommandItem,
  PromptInputCommandList,
} from '@/components/ai-elements/prompt-input'


const props = defineProps({
  isSidebarCollapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-sidebar', 'open-drawer', 'open-settings'])

const sessionStore = useSessionStore()
const friendStore = useFriendStore()
const groupStore = useGroupStore()
const settingsStore = useSettingsStore()
const thinkingModeStore = useThinkingModeStore()
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

const input = ref('')

const status = ref<'ready' | 'streaming'>('ready')

const isThinkingMode = computed(() => thinkingModeStore.isEnabled)

// Get current group metadata
const currentGroup = computed(() => {
  if (!sessionStore.currentGroupId) return null
  return groupStore.getGroup(sessionStore.currentGroupId)
})

const currentGroupName = computed(() => {
  return currentGroup.value ? currentGroup.value.name : '未命名群聊'
})

const messages = computed(() => sessionStore.currentMessages)

// Pagination state
const hasMoreMessages = ref(true)
const conversationRef = ref<InstanceType<typeof Conversation> | null>(null)

// Reset hasMore when group changes
watch(() => sessionStore.currentGroupId, () => {
  hasMoreMessages.value = true
})

// Pagination using IntersectionObserver - triggers when top sentinel becomes visible
const loadMoreTriggerRef = ref<HTMLElement | null>(null)
let intersectionObserver: IntersectionObserver | null = null

const loadMore = async () => {
  if (!hasMoreMessages.value || sessionStore.isLoadingMore || !sessionStore.currentGroupId) return

  const scrollEl = currentScrollEl
  const prevHeight = scrollEl?.scrollHeight || 0
  const prevScrollTop = scrollEl?.scrollTop || 0

  const more = await sessionStore.loadMoreGroupMessages(sessionStore.currentGroupId)
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
  if (intersectionObserver) {
    intersectionObserver.disconnect()
    intersectionObserver = null
  }

  if (el) {
    intersectionObserver = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry && entry.isIntersecting) {
          console.log('[Pagination] Group load more triggered by IntersectionObserver')
          loadMore()
        }
      },
      { threshold: 0.1 }
    )
    intersectionObserver.observe(el)
  }
}, { immediate: true })

const autoDriveState = computed(() => sessionStore.currentAutoDriveState)
const autoDriveConnectionStatus = computed(() => sessionStore.autoDriveConnectionStatus)
const isAutoDriveActive = computed(() => {
  return !!autoDriveState.value && ['running', 'paused', 'pausing'].includes(autoDriveState.value.status)
})
const isAutoDriveDisconnected = computed(() => autoDriveConnectionStatus.value === 'disconnected')

const groupMembers = computed(() => currentGroup.value?.members || [])
const groupFriendMembers = computed(() => groupMembers.value.filter(m => m.member_type === 'friend'))

const autoDriveConfigOpen = ref(false)
const autoDriveConfigRef = ref<InstanceType<typeof GroupAutoDriveConfigDialog> | null>(null)

// 检测是否需要显示会话分隔线（session_id 变化时）
const shouldShowSessionDivider = (index: number): boolean => {
  if (index === 0) return false
  const currentMsg = messages.value[index]
  const prevMsg = messages.value[index - 1]

  if (currentMsg.role === 'system') return false

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
    return timeStr
  } else if (diffDays === 1) {
    return `昨天 ${timeStr}`
  } else if (diffDays < 7) {
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    return `${weekdays[date.getDay()]} ${timeStr}`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) + ' ' + timeStr
  }
}

// Toast Feedback Logic (Copied from ChatArea.vue)
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
  selectedMessages.value.map(msg => {
    const isUser = msg.role === 'user'
    const senderId = msg.senderId || (isUser ? 'user' : 'assistant')
    const senderType = msg.senderType || (isUser ? 'user' : 'assistant')
    return {
      id: msg.id,
      content: msg.content,
      isUser,
      avatar: getMemberAvatar(senderId, senderType),
      name: isUser ? '我' : getMemberName(senderId, senderType),
      showName: !isUser,
    }
  })
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

// Electron 模式检测
const isElectron = Boolean((window as any).WeAgentChat?.windowControls)

const handleHeaderContextMenu = (event: MouseEvent) => {
  if (!isElectron) return
  event.preventDefault()
    ; (window as any).WeAgentChat?.windowControls?.showSystemMenu({
      x: event.screenX,
      y: event.screenY,
    })
}

const handleToggleThinking = () => {
  const wasEnabled = isThinkingMode.value
  thinkingModeStore.toggle()
  const message = wasEnabled ? '思考模式已关闭' : '已开启思考模式'
  triggerToast(message)
}

const handleToggleMaximize = () => {
  if (!isElectron) return
    ; (window as any).WeAgentChat?.windowControls?.toggleMaximize()
}

const handleOpenDrawer = () => {
  emit('open-drawer')
}

const handleNewChat = async () => {
  await sessionStore.startNewGroupSession()
}

const handleOpenAutoDrive = () => {
  if (!sessionStore.currentGroupId) return
  if (isAutoDriveActive.value) {
    triggerToast('接力讨论状态已在上方状态栏展示')
  } else {
    autoDriveConfigOpen.value = true
  }
}

const handleStartAutoDrive = async () => {
  if (!sessionStore.currentGroupId) return
  if (!isLlmConfigured.value) {
    showNoLlmDialog.value = true
    return
  }
  const config = autoDriveConfigRef.value?.getConfig()
  if (!config) return
  try {
    await sessionStore.startAutoDrive(sessionStore.currentGroupId, config, isThinkingMode.value)
    autoDriveConfigOpen.value = false
  } catch (error) {
    console.error('Failed to start auto-drive:', error)
    triggerToast('接力讨论启动失败')
  }
}

const handlePauseAutoDrive = async () => {
  if (!sessionStore.currentGroupId) return
  try {
    await sessionStore.pauseAutoDrive(sessionStore.currentGroupId)
  } catch (error) {
    console.error('Failed to pause auto-drive:', error)
    triggerToast('暂停失败')
  }
}

const handleResumeAutoDrive = async () => {
  if (!sessionStore.currentGroupId) return
  try {
    await sessionStore.resumeAutoDrive(sessionStore.currentGroupId)
  } catch (error) {
    console.error('Failed to resume auto-drive:', error)
    triggerToast('继续失败')
  }
}

const handleStopAutoDrive = async () => {
  if (!sessionStore.currentGroupId) return
  try {
    await sessionStore.stopAutoDrive(sessionStore.currentGroupId)
  } catch (error) {
    console.error('Failed to stop auto-drive:', error)
    triggerToast('终止失败')
  }
}

const handleReconnectAutoDrive = async () => {
  if (!sessionStore.currentGroupId) return
  await sessionStore.fetchAutoDriveState(sessionStore.currentGroupId)
  sessionStore.ensureAutoDriveStream(sessionStore.currentGroupId)
}

const getMemberAvatar = (senderId: string, senderType: string) => {
  if (senderId === 'user') {
    return getStaticUrl(settingsStore.userAvatar) || 'default_avatar.svg'
  }
  if (senderType === 'assistant' || senderType === 'friend') {
    const member = currentGroup.value?.members?.find(m => m.member_id === senderId)
    if (member?.avatar) return getStaticUrl(member.avatar) || 'default_avatar.svg'

    const friend = friendStore.friends.find(f => String(f.id) === senderId)
    if (friend?.avatar) return getStaticUrl(friend.avatar) || 'default_avatar.svg'
    return `https://api.dicebear.com/7.x/shapes/svg?seed=${senderId}`
  }
  return 'default_avatar.svg'
}

const getMemberName = (senderId: string, _senderType: string) => {
  if (senderId === 'user') return '我'
  const member = currentGroup.value?.members?.find(m => m.member_id === senderId)
  if (member?.member_type === 'user') return '我'
  if (member?.name) return member.name

  const friend = friendStore.friends.find(f => String(f.id) === senderId)
  return friend?.name || 'AI'
}

const autoDriveModeLabels: Record<AutoDriveMode, string> = {
  brainstorm: '头脑风暴',
  decision: '决策',
  debate: '辩论'
}

const autoDrivePhaseLabels: Record<AutoDriveMode, Record<string, string>> = {
  brainstorm: {
    opening: '开场设定',
    rounds: '轮次推进',
    summary: '收敛整理'
  },
  decision: {
    opening: '开场设定',
    rounds: '方案分析',
    summary: '推荐与落地'
  },
  debate: {
    opening: '立论陈述',
    free: '自由交锋',
    summary: '总结陈词',
    judge: '评委宣判'
  }
}

const autoDriveModeLabel = computed(() => {
  if (!autoDriveState.value) return ''
  return autoDriveModeLabels[autoDriveState.value.mode] || autoDriveState.value.mode
})

const autoDrivePhaseLabel = computed(() => {
  const state = autoDriveState.value
  if (!state || !state.phase) return ''
  return autoDrivePhaseLabels[state.mode]?.[state.phase] || state.phase
})

const autoDriveStatusLabel = computed(() => {
  const state = autoDriveState.value
  if (!state) return ''
  if (state.status === 'pausing') return '等待收尾'
  if (state.status === 'paused') return '暂停中'
  if (state.status === 'running') return '运行中'
  if (state.status === 'ended') return '已结束'
  return state.status
})

const autoDriveTopicSummary = computed(() => {
  const state = autoDriveState.value
  if (!state) return ''
  const topic = state.topic || {}
  if (state.mode === 'brainstorm') return topic.theme || topic.topic || ''
  if (state.mode === 'decision') return topic.question || ''
  if (state.mode === 'debate') return topic.motion || ''
  return ''
})

const autoDriveProgressLabel = computed(() => {
  const state = autoDriveState.value
  if (!state || !state.phase) return ''
  const phase = state.phase
  if (phase !== 'rounds' && phase !== 'free') return ''

  let total = state.turnLimit
  let current = state.currentRound ?? state.currentTurn ?? 0

  if (state.mode === 'debate' && phase === 'free') {
    const order = Array.isArray(state.roles?.order) ? state.roles.order : []
    const count = order.length || ((state.roles?.affirmative?.length || 0) + (state.roles?.negative?.length || 0))
    if (count > 0) total = state.turnLimit * count
    const openingCount = (state.roles?.affirmative?.length ? 1 : 0) + (state.roles?.negative?.length ? 1 : 0)
    current = Math.max((state.currentTurn ?? 0) - openingCount, 0)
  }

  const safeTotal = total || 0
  const safeCurrent = safeTotal ? Math.min(current, safeTotal) : current
  return safeTotal ? `${safeCurrent}/${safeTotal}` : ''
})

const autoDriveNextSpeakerName = computed(() => {
  const state = autoDriveState.value
  if (!state?.nextSpeakerId) return ''
  const member = groupMembers.value.find(m => m.member_id === state.nextSpeakerId)
  if (member?.member_type === 'user') return '我'
  return member?.name || 'AI'
})

const getMessageDebateSide = (msg: Message): DebateSide | undefined => {
  if (msg.debateSide) return msg.debateSide
  if (msg.sessionType !== 'debate') return undefined
  if (!autoDriveState.value || autoDriveState.value.sessionId !== msg.sessionId) return undefined
  const roles = autoDriveState.value.roles || {}
  if (Array.isArray(roles.affirmative) && roles.affirmative.includes(msg.senderId)) return 'affirmative'
  if (Array.isArray(roles.negative) && roles.negative.includes(msg.senderId)) return 'negative'
  return undefined
}

const getDebateSideLabel = (side?: DebateSide) => {
  if (side === 'affirmative') return '正方'
  if (side === 'negative') return '反方'
  return ''
}

const isAutoDriveMessage = (msg: Message) => {
  return !!msg.sessionType && msg.sessionType !== 'normal'
}

const getMessageSegments = (msg: Message) => {
  if (isAutoDriveMessage(msg)) {
    return msg.content ? [msg.content] : ['']
  }
  return parseMessageSegments(msg.content)
}

// Mention Logic
const showMentionMenu = ref(false)
const mentionSearch = ref('')
const mentionTriggerIndex = ref(-1)
const mentionedIds = ref<Set<string>>(new Set())
const selectedIndex = ref(0)
let mentionKeydownHandler: ((e: KeyboardEvent) => void) | null = null


watch(showMentionMenu, (val) => {
  if (!val) selectedIndex.value = 0
  if (val) {
    if (!mentionKeydownHandler) {
      mentionKeydownHandler = (e: KeyboardEvent) => {
        if (e.key !== 'Escape') return
        e.preventDefault()
        e.stopPropagation()
        showMentionMenu.value = false
        nextTick(() => {
          focusTextarea()
        })
      }
      window.addEventListener('keydown', mentionKeydownHandler)
    }
  } else if (mentionKeydownHandler) {
    window.removeEventListener('keydown', mentionKeydownHandler)
    mentionKeydownHandler = null
  }
})

const filteredMembers = computed(() => {
  if (!currentGroup.value?.members) return []
  const filtered = currentGroup.value.members.filter(m =>
    m.member_type === 'friend' &&
    (m.name?.toLowerCase().includes(mentionSearch.value.toLowerCase()) || !mentionSearch.value)
  )
  return filtered
})

watch(filteredMembers, () => {
  selectedIndex.value = 0
})

watch(
  () => {
    if (!sessionStore.currentGroupId) return null
    return sessionStore.autoDriveErrorMap['g' + sessionStore.currentGroupId] || null
  },
  (val) => {
    if (!val || !sessionStore.currentGroupId) return
    triggerToast(val)
    sessionStore.clearAutoDriveError(sessionStore.currentGroupId)
  }
)

onBeforeUnmount(() => {
  if (mentionKeydownHandler) {
    window.removeEventListener('keydown', mentionKeydownHandler)
    mentionKeydownHandler = null
  }
  if (intersectionObserver) {
    intersectionObserver.disconnect()
    intersectionObserver = null
  }
})

const lastCursorPosition = ref(0)

const focusTextarea = (cursor?: number) => {
  const textarea = document.querySelector('.input-textarea') as HTMLTextAreaElement | null
  if (!textarea) return
  textarea.focus()
  if (typeof cursor === 'number') {
    const safeCursor = Math.min(cursor, textarea.value.length)
    textarea.setSelectionRange(safeCursor, safeCursor)
  }
}

const handleInput = (e: any) => {
  const val = e?.target?.value ?? ''
  const cursor = e?.target?.selectionStart ?? 0
  lastCursorPosition.value = cursor
  const lastChar = val[cursor - 1]

  if (lastChar === '@') {
    showMentionMenu.value = true
    mentionTriggerIndex.value = cursor
    mentionSearch.value = ''
  } else if (showMentionMenu.value) {
    if (cursor < mentionTriggerIndex.value || (lastChar === ' ' && mentionTriggerIndex.value === cursor - 1)) {
      showMentionMenu.value = false
    } else {
      mentionSearch.value = val.substring(mentionTriggerIndex.value, cursor)
    }
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!showMentionMenu.value) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value + 1) % filteredMembers.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value - 1 + filteredMembers.value.length) % filteredMembers.value.length
  } else if (e.key === 'Enter') {
    if (filteredMembers.value[selectedIndex.value]) {
      e.preventDefault()
      selectMention(filteredMembers.value[selectedIndex.value])
    }
  } else if (e.key === 'Escape') {
    showMentionMenu.value = false
    nextTick(() => {
      const cursor = (e.target as HTMLTextAreaElement | null)?.selectionStart ?? lastCursorPosition.value
      focusTextarea(cursor)
    })
  }
}

const selectMention = (member: any) => {
  const before = input.value.substring(0, mentionTriggerIndex.value)
  const after = input.value.substring(lastCursorPosition.value)
  input.value = `${before}${member.name} ${after}`
  mentionedIds.value.add(member.member_id)
  showMentionMenu.value = false

  // Focus back to textarea
  setTimeout(() => {
    const textarea = document.querySelector('.input-textarea') as HTMLTextAreaElement
    if (textarea) {
      textarea.focus()
      const newCursor = mentionTriggerIndex.value + member.name.length + 1
      textarea.setSelectionRange(newCursor, newCursor)
    }
  }, 0)
}

const resolveMentionIdsFromText = (content: string) => {
  const members = groupFriendMembers.value
  const matchedIds = new Set<string>()

  members.forEach(member => {
    if (member.name && content.includes(`@${member.name}`)) {
      matchedIds.add(member.member_id)
    }
  })

  const rawMatches = [...content.matchAll(/@([^\s@]+)/g)].map(m => m[1])
  const unknownNames = rawMatches.filter(name => !members.some(m => m.name === name))

  return { ids: Array.from(matchedIds), unknownNames }
}

const buildAutoDriveMentions = (content: string) => {
  const mentionsFromMenu = Array.from(mentionedIds.value).filter(id => content.includes(`@${getMemberName(id, 'friend')}`))
  const { ids: mentionsFromText, unknownNames } = resolveMentionIdsFromText(content)
  if (unknownNames.length) {
    triggerToast(`未找到成员：${unknownNames.join('、')}`)
  }
  return Array.from(new Set([...mentionsFromMenu, ...mentionsFromText]))
}

const handleSubmit = async (_e?: any) => {
  if (!input.value.trim()) return
  if (!sessionStore.currentGroupId) return

  const content = input.value
  const mentions = isAutoDriveActive.value
    ? buildAutoDriveMentions(content)
    : Array.from(mentionedIds.value).filter(id => content.includes(`@${getMemberName(id, 'friend')}`))

  input.value = ''
  mentionedIds.value.clear()
  status.value = 'streaming'

  try {
    if (isAutoDriveActive.value) {
      await sessionStore.sendAutoDriveInterject(content, mentions)
    } else {
      await sessionStore.sendGroupMessage(content, mentions, isThinkingMode.value)
    }
  } catch (err) {
    console.error('Failed to send group message:', err)
    triggerToast('发送失败')
  } finally {
    status.value = 'ready'
  }
}

// Thinking & Tool Calls Dialogs
const thinkingDialogOpen = ref(false)
const toolCallsDialogOpen = ref(false)
const activeModelThinkingContent = ref('')
const activeRecallThinkingContent = ref('')
const activeToolCalls = ref<any[]>([])

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

const getToolCalls = (msg: any): any[] => {
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
  if (!toolCalls || !toolCalls.length) return
  activeToolCalls.value = toolCalls
  toolCallsDialogOpen.value = true
}


// Avatar Preview
const showAvatarPreview = ref(false)
const previewAvatarUrl = ref('')

const handleAvatarClick = (url: string) => {
  previewAvatarUrl.value = url
  showAvatarPreview.value = true
}

</script>

<template>
  <div class="wechat-chat-area group-chat" :class="{ 'select-mode': isSelectMode }">
    <header class="chat-header" :class="{ 'electron-mode': isElectron }" @contextmenu="handleHeaderContextMenu">
      <button v-if="isSidebarCollapsed" @click="emit('toggle-sidebar')" class="mobile-menu-btn">
        <Menu :size="20" />
      </button>
      <div class="header-drag-area" @dblclick="handleToggleMaximize">
        <div v-if="sessionStore.currentGroupId" class="chat-title-container" @click="handleOpenDrawer">
          <div class="title-text-group">
            <div class="flex items-center gap-2">
              <GroupAvatar :size="32" :members="currentGroup?.members" :avatar="currentGroup?.avatar" />
              <h2 class="chat-title">{{ currentGroupName }}</h2>
              <span class="member-count text-gray-400 text-sm font-normal">({{ currentGroup?.member_count || 0
              }})</span>
            </div>
          </div>
        </div>
        <h2 v-else class="chat-title">{{ currentGroupName }}</h2>
      </div>

      <div class="header-actions">
        <button class="more-btn export-btn" title="分享/导出" @click="enterSelectMode">
          <Share2 :size="18" />
        </button>
        <!-- "更多"按钮 - Web 模式回退 -->
        <button v-if="!isElectron" class="more-btn" @click="handleOpenDrawer">
          <MoreHorizontal :size="20" />
        </button>
      </div>
    </header>

    <!-- Messages Area -->
    <div class="chat-messages-container flex-col bg-[#f5f5f5]">
      <!-- Vectorization Warning Banner -->
      <div v-if="!isEmbeddingConfigured" class="vector-warning-banner" @click="handleOpenEmbeddingSettings">
        <div
          class="banner-content text-amber-600 bg-amber-50 px-4 py-2 border-b border-amber-100 flex items-center gap-2 text-sm cursor-pointer hover:bg-amber-100 transition-colors">
          <AlertTriangle :size="16" class="warning-icon" />
          <span>向量化模型未配置，记忆系统将无法工作。</span>
          <span class="action-link text-amber-700 font-medium ml-auto">去配置 &gt;</span>
        </div>
      </div>

      <div v-if="autoDriveState && autoDriveState.status !== 'ended'" class="auto-drive-banner">
        <div class="auto-drive-row">
          <div class="auto-drive-left">
            <span class="auto-drive-tag">{{ autoDriveModeLabel }}</span>
            <span class="auto-drive-topic" :title="autoDriveTopicSummary">{{ autoDriveTopicSummary || '未设置题目'
            }}</span>
          </div>
          <div class="auto-drive-center">
            <span class="auto-drive-phase">{{ autoDrivePhaseLabel || autoDriveStatusLabel }}</span>
            <span v-if="autoDriveProgressLabel" class="auto-drive-progress">{{ autoDriveProgressLabel }}</span>
          </div>
          <div class="auto-drive-right">
            <button v-if="isAutoDriveDisconnected" class="auto-drive-action" @click="handleReconnectAutoDrive">
              <RefreshCw :size="14" />
              重连
            </button>
            <template v-else>
              <button v-if="autoDriveState?.status === 'running'" class="auto-drive-action" @click="handlePauseAutoDrive">
                <Pause :size="14" />
                暂停
              </button>
              <button v-else-if="autoDriveState?.status === 'paused'" class="auto-drive-action"
                @click="handleResumeAutoDrive">
                <Play :size="14" />
                继续
              </button>
              <button v-else-if="autoDriveState?.status === 'pausing'" class="auto-drive-action disabled" disabled>
                等待收尾
              </button>
              <button class="auto-drive-action danger" @click="handleStopAutoDrive">
                <Square :size="14" />
                终止
              </button>
            </template>
          </div>
        </div>
        <div class="auto-drive-row secondary">
          <span v-if="isAutoDriveDisconnected" class="auto-drive-muted">已断开</span>
          <span v-else class="auto-drive-muted">下一位：{{ autoDriveNextSpeakerName || '...' }}</span>
        </div>
      </div>

      <!-- Empty State with WeChat Logo -->

      <div v-if="messages.length === 0" class="empty-state flex-1">
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
              已无更多消息
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
                  <div v-for="(segment, sIndex) in getMessageSegments(msg)" :key="msg.id + '-' + sIndex"
                    class="message-group group-assistant">
                    <div class="message-wrapper message-assistant group relative">
                      <!-- Avatar -->
                      <div class="message-avatar"
                        @click="handleAvatarClick(getMemberAvatar(msg.senderId || 'assistant', 'assistant'))">
                        <img :src="getMemberAvatar(msg.senderId || 'assistant', 'assistant')" alt="Avatar" />
                      </div>

                      <!-- Message Bubble -->
                      <div class="message-bubble-container" :class="{ 'message-pop-in': segment }">
                        <!-- Member Name for groups -->
                        <span v-if="sIndex === 0" class="member-name">{{ getMemberName(msg.senderId || 'assistant',
                          'assistant') }}
                          <span v-if="getMessageDebateSide(msg)" class="debate-name-tag"
                            :class="getMessageDebateSide(msg) === 'affirmative' ? 'affirmative' : 'negative'">
                            {{ getDebateSideLabel(getMessageDebateSide(msg)) }}
                          </span>
                        </span>
                        <div class="message-bubble">
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
                    <div class="message-avatar" @click="handleAvatarClick(getMemberAvatar('user', 'user'))">
                      <img :src="getMemberAvatar('user', 'user')" alt="Avatar" />
                    </div>

                    <!-- Message Bubble -->
                    <div class="message-bubble-container" :class="{ 'message-pop-in': msg.content }">
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
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <!-- Story 09-10: Group specific typing indicator -->
      <div v-if="!isAutoDriveActive && sessionStore.isStreaming && sessionStore.groupTypingUsers.length > 0"
        class="group-typing-area">
        <span class="typing-text">
          {{sessionStore.groupTypingUsers.map(u => u.name).join('、')}} 正在输入中...
        </span>
      </div>
      <div v-else-if="!isAutoDriveActive && sessionStore.isStreaming" class="group-typing-area">
        <span class="typing-text">正在思考谁来回复...</span>
      </div>
    </div>


    <!-- Input Area -->
    <div v-if="!isSelectMode" class="chat-input-area">
      <div class="input-toolbar">
        <EmojiPicker @select="input += $event" />
        <button class="toolbar-btn auto-drive-btn" title="接力讨论" @click="handleOpenAutoDrive">
          <Sparkles :size="18" />
        </button>
        <button class="toolbar-btn" title="新会话" @click="handleNewChat">
          <MessageSquarePlus :size="22" />
        </button>
      </div>

      <!-- Mention Menu (Absolute positioned relative to input-box) -->
      <div v-if="showMentionMenu" ref="mentionMenuRef" class="mention-menu-container">
        <PromptInputCommand class="mention-menu">
          <PromptInputCommandList>
            <PromptInputCommandGroup heading="选择提醒的人">
              <PromptInputCommandItem v-for="(member, index) in filteredMembers" :key="member.member_id"
                :value="member.name || member.member_id" @select="selectMention(member)" class="mention-item"
                :class="{ 'bg-accent text-accent-foreground': index === selectedIndex }">
                <img :src="getMemberAvatar(member.member_id, 'friend')" class="w-6 h-6 rounded mr-2" />
                <span>{{ member.name }}</span>
              </PromptInputCommandItem>
            </PromptInputCommandGroup>
            <PromptInputCommandEmpty v-if="filteredMembers.length === 0">未找到成员</PromptInputCommandEmpty>
          </PromptInputCommandList>
        </PromptInputCommand>
      </div>

      <PromptInput class="input-box" @submit="checkLlmConfigAndSubmit">

        <PromptInputTextarea v-model="input" placeholder="输入消息..." class="input-textarea" @input="handleInput"
          @keydown="handleKeyDown" @click="lastCursorPosition = $event.target.selectionStart" />
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

    <!-- Auto Drive Config Dialog -->
    <GroupAutoDriveConfigDialog ref="autoDriveConfigRef" v-model:open="autoDriveConfigOpen"
      :group-friend-members="groupFriendMembers" @submit="handleStartAutoDrive" @toast="triggerToast" />

    <ChatImageExportDialog v-model:open="exportDialogOpen" :messages="exportMessages" title="聊天记录图片预览" />

    <!-- Toast Feedback -->
    <Transition name="fade">
      <div v-if="showToast" class="toast-feedback">
        {{ toastMessage }}
      </div>
    </Transition>

    <!-- Avatar Preview Dialog -->
    <Dialog v-model:open="showAvatarPreview">
      <DialogContent
        class="p-0 bg-transparent border-none shadow-none max-w-3xl w-auto flex justify-center items-center">
        <img :src="previewAvatarUrl" class="max-w-full max-h-[80vh] object-contain rounded-md" alt="Avatar Preview" />
      </DialogContent>
    </Dialog>

    <!-- Thinking Dialog -->
    <Dialog v-model:open="thinkingDialogOpen">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>思考过程</DialogTitle>
        </DialogHeader>
        <div class="thinking-dialog-body max-h-[60vh] overflow-y-auto pr-2">
          <div v-if="activeRecallThinkingContent" class="thinking-section mb-6">
            <div
              class="thinking-section-title text-sm font-semibold text-gray-500 mb-2 border-l-4 border-amber-400 pl-2">
              回忆思维链</div>
            <StreamMarkdown :content="activeRecallThinkingContent"
              :shiki-theme="{ light: 'github-light', dark: 'github-dark' }"
              class="thinking-markdown text-sm text-gray-700 bg-gray-50 p-3 rounded" />
          </div>
          <div v-if="activeModelThinkingContent" class="thinking-section">
            <div
              class="thinking-section-title text-sm font-semibold text-gray-500 mb-2 border-l-4 border-emerald-400 pl-2">
              模型思维链</div>
            <StreamMarkdown :content="activeModelThinkingContent"
              :shiki-theme="{ light: 'github-light', dark: 'github-dark' }"
              class="thinking-markdown text-sm text-gray-700 bg-gray-50 p-3 rounded" />
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Tool Calls Dialog -->
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

    <!-- LLM Not Configured Dialog -->
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

  </div>
</template>


<style scoped src="./GroupChatArea.css">
</style>
