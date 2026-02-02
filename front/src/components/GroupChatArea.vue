<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount, onMounted, reactive } from 'vue'
import { useSessionStore } from '@/stores/session'
import { parseMessageSegments } from '@/utils/chat'
import { useFriendStore } from '@/stores/friend'
import { useGroupStore } from '@/stores/group'
import { useSettingsStore } from '@/stores/settings'
import type { AutoDriveEndAction, AutoDriveMode, DebateSide, Message } from '@/types/chat'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Menu, MoreHorizontal, Brain, MessageSquarePlus, Sparkles, Pause, Play, Square, RefreshCw } from 'lucide-vue-next'
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

import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit
} from '@/components/ai-elements/prompt-input'

import GroupAvatar from './common/GroupAvatar.vue'
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

const autoDriveState = computed(() => sessionStore.currentAutoDriveState)
const autoDriveConnectionStatus = computed(() => sessionStore.autoDriveConnectionStatus)
const isAutoDriveActive = computed(() => {
  return !!autoDriveState.value && ['running', 'paused', 'pausing'].includes(autoDriveState.value.status)
})
const isAutoDriveDisconnected = computed(() => autoDriveConnectionStatus.value === 'disconnected')
const showSummarySelector = computed(() => ['summary', 'both'].includes(autoDriveEndAction.value))
const showJudgeSelector = computed(() => autoDriveMode.value === 'debate' && ['judge', 'both'].includes(autoDriveEndAction.value))
const availableEndActions = computed(() => {
  if (autoDriveMode.value === 'debate') {
    return [
      { value: 'summary', label: '总结' },
      { value: 'judge', label: '胜负判定' },
      { value: 'both', label: '两者' }
    ]
  }
  return [{ value: 'summary', label: '总结' }]
})

const groupMembers = computed(() => currentGroup.value?.members || [])
const groupFriendMembers = computed(() => groupMembers.value.filter(m => m.member_type === 'friend'))

const autoDriveConfigOpen = ref(false)
const autoDriveMode = ref<AutoDriveMode>('brainstorm')
const autoDriveTurnLimit = ref(6)
const autoDriveEndAction = ref<AutoDriveEndAction>('summary')
const autoDriveJudgeId = ref('user')
const autoDriveSummaryBy = ref('user')

const brainstormTopic = reactive({
  theme: '',
  goal: '',
  constraints: ''
})

const decisionTopic = reactive({
  question: '',
  options: '',
  criteria: ''
})

const debateTopic = reactive({
  motion: '',
  affirmative: '',
  negative: ''
})

const brainstormParticipants = ref<string[]>([])
const decisionParticipants = ref<string[]>([])
const debateAffirmative = ref<string[]>([])
const debateNegative = ref<string[]>([])

const resetAutoDriveConfig = () => {
  autoDriveMode.value = 'brainstorm'
  autoDriveTurnLimit.value = 6
  autoDriveEndAction.value = 'summary'
  autoDriveJudgeId.value = 'user'
  autoDriveSummaryBy.value = 'user'

  brainstormTopic.theme = ''
  brainstormTopic.goal = ''
  brainstormTopic.constraints = ''

  decisionTopic.question = ''
  decisionTopic.options = ''
  decisionTopic.criteria = ''

  debateTopic.motion = ''
  debateTopic.affirmative = ''
  debateTopic.negative = ''

  brainstormParticipants.value = []
  decisionParticipants.value = []
  debateAffirmative.value = []
  debateNegative.value = []
}

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
    triggerToast('自驱状态已在上方状态栏展示')
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
  if (!validateAutoDriveConfig()) return
  try {
    await sessionStore.startAutoDrive(sessionStore.currentGroupId, buildAutoDriveConfig(), isThinkingMode.value)
    autoDriveConfigOpen.value = false
  } catch (error) {
    console.error('Failed to start auto-drive:', error)
    triggerToast('自驱启动失败')
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

const isDebateSideDisabled = (side: 'affirmative' | 'negative', memberId: string) => {
  const affirmativeSet = new Set(debateAffirmative.value)
  const negativeSet = new Set(debateNegative.value)
  if (side === 'affirmative') {
    if (negativeSet.has(memberId)) return true
    if (!affirmativeSet.has(memberId) && debateAffirmative.value.length >= 2) return true
  } else {
    if (affirmativeSet.has(memberId)) return true
    if (!negativeSet.has(memberId) && debateNegative.value.length >= 2) return true
  }
  return false
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

watch(autoDriveConfigOpen, (val) => {
  if (val) resetAutoDriveConfig()
})

watch(autoDriveMode, (mode) => {
  if (mode !== 'debate' && autoDriveEndAction.value !== 'summary') {
    autoDriveEndAction.value = 'summary'
  }
})

onBeforeUnmount(() => {
  if (mentionKeydownHandler) {
    window.removeEventListener('keydown', mentionKeydownHandler)
    mentionKeydownHandler = null
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

const validateAutoDriveConfig = () => {
  const mode = autoDriveMode.value
  const limit = Number(autoDriveTurnLimit.value)
  if (!Number.isFinite(limit) || limit < 1) {
    triggerToast('发言上限至少为 1')
    return false
  }
  if (mode === 'brainstorm') {
    if (!brainstormTopic.theme.trim() || !brainstormTopic.goal.trim() || !brainstormTopic.constraints.trim()) {
      triggerToast('请填写头脑风暴的主题、目标与约束')
      return false
    }
    if (brainstormParticipants.value.length === 0) {
      triggerToast('请至少选择 1 位参与成员')
      return false
    }
  }
  if (mode === 'decision') {
    if (!decisionTopic.question.trim() || !decisionTopic.options.trim() || !decisionTopic.criteria.trim()) {
      triggerToast('请填写决策问题、候选方案与评估标准')
      return false
    }
    if (decisionParticipants.value.length === 0) {
      triggerToast('请至少选择 1 位参与成员')
      return false
    }
  }
  if (mode === 'debate') {
    if (!debateTopic.motion.trim() || !debateTopic.affirmative.trim() || !debateTopic.negative.trim()) {
      triggerToast('请填写辩题、正方立场与反方立场')
      return false
    }
    if (debateAffirmative.value.length === 0 || debateNegative.value.length === 0) {
      triggerToast('请为正方与反方各选择 1-2 位成员')
      return false
    }
    if (debateAffirmative.value.length > 2 || debateNegative.value.length > 2) {
      triggerToast('正反方最多各 2 人')
      return false
    }
    if (debateAffirmative.value.length !== debateNegative.value.length) {
      triggerToast('正反人数必须相等')
      return false
    }
  }
  return true
}

const buildAutoDriveConfig = () => {
  const mode = autoDriveMode.value
  if (mode === 'brainstorm') {
    return {
      mode,
      topic: {
        theme: brainstormTopic.theme.trim(),
        goal: brainstormTopic.goal.trim(),
        constraints: brainstormTopic.constraints.trim()
      },
      roles: {
        participants: brainstormParticipants.value
      },
      turnLimit: Number(autoDriveTurnLimit.value) || 1,
      endAction: autoDriveEndAction.value,
      judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
      summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
    }
  }
  if (mode === 'decision') {
    return {
      mode,
      topic: {
        question: decisionTopic.question.trim(),
        options: decisionTopic.options.trim(),
        criteria: decisionTopic.criteria.trim()
      },
      roles: {
        participants: decisionParticipants.value
      },
      turnLimit: Number(autoDriveTurnLimit.value) || 1,
      endAction: autoDriveEndAction.value,
      judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
      summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
    }
  }
  return {
    mode,
    topic: {
      motion: debateTopic.motion.trim(),
      affirmative: debateTopic.affirmative.trim(),
      negative: debateTopic.negative.trim()
    },
    roles: {
      affirmative: debateAffirmative.value,
      negative: debateNegative.value
    },
    turnLimit: Number(autoDriveTurnLimit.value) || 1,
    endAction: autoDriveEndAction.value,
    judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
    summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
  }
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
  <div class="wechat-chat-area group-chat">
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

      <Conversation v-else class="flex-1 w-full overflow-hidden">
        <ConversationContent class="messages-content">
          <template v-for="(msg, index) in messages" :key="msg.id">
            <!-- 会话分隔线（session_id 变化时显示） -->
            <div v-if="shouldShowSessionDivider(index)" class="session-divider">
              <span class="divider-time">{{ formatSessionTime(msg.createdAt) }}</span>
            </div>
            <div v-if="msg.role === 'system'" class="message-system">
              <span>{{ msg.content }}</span>
            </div>

            <template v-else-if="msg.role === 'assistant'">
              <!-- AI 回复：动态拆分渲染 -->
              <div v-for="(segment, sIndex) in getMessageSegments(msg)" :key="msg.id + '-' + sIndex"
                class="message-group group-assistant">
                <div class="message-wrapper message-assistant group relative">
                  <!-- Avatar -->
                  <div class="message-avatar" :class="{ 'debate-avatar': getMessageDebateSide(msg) }"
                    @click="handleAvatarClick(getMemberAvatar(msg.senderId || 'assistant', 'assistant'))">
                    <img :src="getMemberAvatar(msg.senderId || 'assistant', 'assistant')" alt="Avatar" />
                    <span v-if="getMessageDebateSide(msg)" class="debate-badge"
                      :class="getMessageDebateSide(msg) === 'affirmative' ? 'affirmative' : 'negative'">
                      {{ getMessageDebateSide(msg) === 'affirmative' ? '正' : '反' }}
                    </span>
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
            </template>

            <div v-else class="message-group group-user">
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
    <div class="chat-input-area">
      <div class="input-toolbar">
        <EmojiPicker @select="input += $event" />
        <button class="toolbar-btn auto-drive-btn" title="自驱" @click="handleOpenAutoDrive">
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

    <!-- Auto Drive Config Dialog -->
    <Dialog v-model:open="autoDriveConfigOpen">
      <DialogContent class="auto-drive-dialog sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>自驱模式配置</DialogTitle>
          <DialogDescription>一次配置即可自动多轮对话。</DialogDescription>
        </DialogHeader>
        <div class="auto-drive-form">
          <div class="form-section">
            <label class="form-label">模式</label>
            <div class="mode-switch">
              <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'brainstorm' }"
                @click="autoDriveMode = 'brainstorm'">头脑风暴</button>
              <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'decision' }"
                @click="autoDriveMode = 'decision'">决策</button>
              <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'debate' }"
                @click="autoDriveMode = 'debate'">辩论</button>
            </div>
          </div>

          <div v-if="autoDriveMode === 'brainstorm'" class="form-section">
            <label class="form-label">主题</label>
            <textarea v-model="brainstormTopic.theme" class="form-textarea"
              placeholder="例如：提升我们产品在大学生群体中的活跃度"></textarea>
            <label class="form-label">目标</label>
            <textarea v-model="brainstormTopic.goal" class="form-textarea"
              placeholder="例如：产出 10 个可执行的增长方案"></textarea>
            <label class="form-label">约束</label>
            <textarea v-model="brainstormTopic.constraints" class="form-textarea"
              placeholder="例如：预算 5 万以内，2 周内落地"></textarea>
          </div>

          <div v-if="autoDriveMode === 'decision'" class="form-section">
            <label class="form-label">决策问题</label>
            <textarea v-model="decisionTopic.question" class="form-textarea"
              placeholder="例如：是否在本季度推出会员制"></textarea>
            <label class="form-label">候选方案</label>
            <textarea v-model="decisionTopic.options" class="form-textarea"
              placeholder="例如：A. 先小范围内测&#10;B. 直接全量上线&#10;C. 延后至下季度"></textarea>
            <label class="form-label">评估标准</label>
            <textarea v-model="decisionTopic.criteria" class="form-textarea"
              placeholder="例如：用户留存权重 40%，成本权重 30%，风险权重 30%"></textarea>
          </div>

          <div v-if="autoDriveMode === 'debate'" class="form-section">
            <label class="form-label">辩题</label>
            <textarea v-model="debateTopic.motion" class="form-textarea"
              placeholder="例如：工作压力大时应该主动辞职"></textarea>
            <label class="form-label">正方立场</label>
            <textarea v-model="debateTopic.affirmative" class="form-textarea"
              placeholder="例如：应该辞职，优先保护身心健康"></textarea>
            <label class="form-label">反方立场</label>
            <textarea v-model="debateTopic.negative" class="form-textarea"
              placeholder="例如：不应辞职，应先寻求调整与支持"></textarea>
          </div>

          <div v-if="autoDriveMode === 'brainstorm'" class="form-section">
            <label class="form-label">参与成员</label>
            <div class="member-grid">
              <label v-for="member in groupFriendMembers" :key="member.member_id" class="member-chip">
                <input type="checkbox" :value="member.member_id" v-model="brainstormParticipants" />
                <span>{{ member.name }}</span>
              </label>
            </div>
          </div>

          <div v-else-if="autoDriveMode === 'decision'" class="form-section">
            <label class="form-label">参与成员</label>
            <div class="member-grid">
              <label v-for="member in groupFriendMembers" :key="member.member_id + '-decision'" class="member-chip">
                <input type="checkbox" :value="member.member_id" v-model="decisionParticipants" />
                <span>{{ member.name }}</span>
              </label>
            </div>
          </div>

          <div v-if="autoDriveMode === 'debate'" class="form-section">
            <div class="debate-grid">
              <div class="debate-col">
                <label class="form-label">正方成员（1-2 人）</label>
                <div class="member-grid">
                  <label v-for="member in groupFriendMembers" :key="member.member_id + '-aff'" class="member-chip">
                    <input type="checkbox" :value="member.member_id" v-model="debateAffirmative"
                      :disabled="isDebateSideDisabled('affirmative', member.member_id)" />
                    <span>{{ member.name }}</span>
                  </label>
                </div>
              </div>
              <div class="debate-col">
                <label class="form-label">反方成员（1-2 人）</label>
                <div class="member-grid">
                  <label v-for="member in groupFriendMembers" :key="member.member_id + '-neg'" class="member-chip">
                    <input type="checkbox" :value="member.member_id" v-model="debateNegative"
                      :disabled="isDebateSideDisabled('negative', member.member_id)" />
                    <span>{{ member.name }}</span>
                  </label>
                </div>
              </div>
            </div>
            <div class="form-hint">正反人数必须相等且每方最多 2 人</div>
          </div>

          <div class="form-section form-inline">
            <div class="form-inline-item">
              <label class="form-label">发言上限</label>
              <input v-model="autoDriveTurnLimit" type="number" min="1" class="form-input" />
            </div>
            <div class="form-inline-item">
              <label class="form-label">结束动作</label>
              <select v-model="autoDriveEndAction" class="form-select"
                :disabled="availableEndActions.length === 1">
                <option v-for="action in availableEndActions" :key="action.value" :value="action.value">
                  {{ action.label }}
                </option>
              </select>
            </div>
          </div>

          <div v-if="showSummarySelector" class="form-section">
            <label class="form-label">总结角色</label>
            <select v-model="autoDriveSummaryBy" class="form-select">
              <option value="user">我（默认）</option>
              <option v-for="member in groupFriendMembers" :key="member.member_id + '-summary'"
                :value="member.member_id">
                {{ member.name }}
              </option>
            </select>
          </div>

          <div v-if="showJudgeSelector" class="form-section">
            <label class="form-label">评委角色</label>
            <select v-model="autoDriveJudgeId" class="form-select">
              <option value="user">我（默认）</option>
              <option v-for="member in groupFriendMembers" :key="member.member_id + '-judge'"
                :value="member.member_id">
                {{ member.name }}
              </option>
            </select>
          </div>
        </div>
        <DialogFooter class="sm:justify-end gap-2">
          <Button variant="ghost" @click="autoDriveConfigOpen = false">取消</Button>
          <Button type="button" variant="default" class="bg-emerald-600 hover:bg-emerald-700"
            @click="handleStartAutoDrive">
            开始自驱
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

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
  background: #f5f5f5;
  border-bottom: 1px solid #e5e5e5;
  user-select: none;
}

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

/* Story 09-10: Input area typing indicator */
.group-typing-area {
  padding: 4px 16px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  background: #f5f5f5;
  min-height: 24px;
}

.typing-text {
  font-size: 12px;
  color: #888;
  animation: typing-fade 1.5s infinite ease-in-out;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  gap: 4px;
}

.member-name {
  font-size: 11px;
  color: #888;
  margin-left: 2px;
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

.debate-avatar {
  position: relative;
}

.debate-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.debate-badge.affirmative {
  background: #22c55e;
}

.debate-badge.negative {
  background: #ef4444;
}

.debate-name-tag {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
}

.debate-name-tag.affirmative {
  background: #eafaf1;
  color: #16a34a;
}

.debate-name-tag.negative {
  background: #fee2e2;
  color: #dc2626;
}

.auto-drive-banner {
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.auto-drive-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.auto-drive-row.secondary {
  font-size: 12px;
  color: #888;
}

.auto-drive-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.auto-drive-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eafaf1;
  color: #0f9d58;
  flex-shrink: 0;
}

.auto-drive-topic {
  font-size: 12px;
  color: #555;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.auto-drive-center {
  font-size: 12px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.auto-drive-progress {
  color: #999;
}

.auto-drive-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.auto-drive-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid #e5e5e5;
  background: #fafafa;
  color: #333;
  cursor: pointer;
  transition: all 0.15s ease;
}

.auto-drive-action:hover {
  background: #f0f0f0;
}

.auto-drive-action.danger {
  background: #fff5f5;
  border-color: #f5c2c7;
  color: #c0392b;
}

.auto-drive-action.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.auto-drive-muted {
  font-size: 12px;
}

.auto-drive-dialog .auto-drive-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 12px;
  color: #666;
}

.form-textarea {
  min-height: 64px;
  padding: 8px 10px;
  font-size: 13px;
  border-radius: 4px;
  border: 1px solid #e5e5e5;
  background: #fff;
  resize: vertical;
}

.form-input,
.form-select {
  padding: 8px 10px;
  font-size: 13px;
  border-radius: 4px;
  border: 1px solid #e5e5e5;
  background: #fff;
}

.form-inline {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.form-inline-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 140px;
  flex: 1;
}

.mode-switch {
  display: flex;
  gap: 8px;
}

.mode-btn {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid #e5e5e5;
  background: #fff;
  cursor: pointer;
}

.mode-btn.active {
  background: #07c160;
  border-color: #07c160;
  color: #fff;
}

.member-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.member-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid #e5e5e5;
  background: #fafafa;
  font-size: 12px;
  cursor: pointer;
}

.member-chip input {
  margin: 0;
}

.member-chip input:checked + span {
  color: #07c160;
  font-weight: 600;
}

.debate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.form-hint {
  font-size: 12px;
  color: #999;
}

/* Input Area */
.chat-input-area {
  position: relative;
  /* 重要：为提及菜单提供定位基准 */
  background: #f5f5f5;
  border-top: 1px solid #e5e5e5;
  padding: 8px 16px 16px;
  overflow: visible !important;
  /* 确保菜单不会被切掉 */
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

.auto-drive-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px;
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

/* Mention Menu */
/* Mention Menu */
.mention-menu-container {
  position: absolute;
  bottom: 100%;
  left: 16px;
  width: 220px;
  margin-bottom: 8px;
  z-index: 1000;
  display: block;
}

.mention-menu {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.mention-item {
  display: flex !important;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.mention-item:hover {
  background: #f5f5f5;
}

@keyframes mention-pop {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

:deep(.mention-item[data-selected="true"]) {
  background: #f0f0f0 !important;
}

/* Message Actions */
.message-actions {
  display: flex;
  align-items: center;
  padding: 0 4px;
  align-self: center;
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
