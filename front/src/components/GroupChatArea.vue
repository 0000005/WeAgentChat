<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { parseMessageSegments } from '@/utils/chat'
import { useFriendStore } from '@/stores/friend'
import { useGroupStore } from '@/stores/group'
import { useSettingsStore } from '@/stores/settings'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Menu, MoreHorizontal, Brain, MessageSquarePlus } from 'lucide-vue-next'
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
  if (member?.name) return member.name

  const friend = friendStore.friends.find(f => String(f.id) === senderId)
  return friend?.name || 'AI'
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

const handleSubmit = async (_e?: any) => {
  if (!input.value.trim()) return
  if (!sessionStore.currentGroupId) return

  const content = input.value
  const mentions = Array.from(mentionedIds.value).filter(id => content.includes(`@${getMemberName(id, 'friend')}`))

  input.value = ''
  mentionedIds.value.clear()
  status.value = 'streaming'

  try {
    await sessionStore.sendGroupMessage(content, mentions, isThinkingMode.value)
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
              <div v-for="(segment, sIndex) in parseMessageSegments(msg.content)" :key="msg.id + '-' + sIndex"
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
                      'assistant') }}</span>
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
      <div v-if="sessionStore.isStreaming && sessionStore.groupTypingUsers.length > 0" class="group-typing-area">
        <span class="typing-text">
          {{sessionStore.groupTypingUsers.map(u => u.name).join('、')}} 正在输入中...
        </span>
      </div>
      <div v-else-if="sessionStore.isStreaming" class="group-typing-area">
        <span class="typing-text">正在思考谁来回复...</span>
      </div>
    </div>


    <!-- Input Area -->
    <div class="chat-input-area">
      <div class="input-toolbar">
        <EmojiPicker @select="input += $event" />
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
