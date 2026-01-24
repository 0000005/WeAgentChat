<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore, parseMessageSegments } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import { useGroupStore } from '@/stores/group'
import { useSettingsStore } from '@/stores/settings'
import { Menu, MoreHorizontal, Brain, MessageSquarePlus } from 'lucide-vue-next'
import { useThinkingModeStore } from '@/stores/thinkingMode'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '@/components/ai-elements/conversation'
import { MessageContent, MessageResponse } from '@/components/ai-elements/message'
import EmojiPicker from '@/components/EmojiPicker.vue'
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit
} from '@/components/ai-elements/prompt-input'
import { getStaticUrl } from '@/api/base'
import GroupAvatar from './common/GroupAvatar.vue'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'

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
  ;(window as any).WeAgentChat?.windowControls?.showSystemMenu({
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
  ;(window as any).WeAgentChat?.windowControls?.toggleMaximize()
}

const handleOpenDrawer = () => {
  emit('open-drawer')
}

const handleNewChat = async () => {
  // TODO: Implement group session management when backend is ready
  // For now, just add a system message locally
  if (!sessionStore.currentGroupId) return
  const groupId = sessionStore.currentGroupId
  
  if (!sessionStore.messagesMap[groupId]) {
    sessionStore.messagesMap[groupId] = []
  }
  
  // Prevent multiple consecutive new sessions
  const messages = sessionStore.messagesMap[groupId]
  if (messages.length > 0) {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg.role === 'system' && lastMsg.content === '新会话') {
      return
    }
  }
  
  sessionStore.messagesMap[groupId].push({
    id: Date.now(),
    role: 'system',
    content: '新会话',
    createdAt: Date.now()
  })
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

const handleSubmit = (_e?: any) => {
  if (!input.value.trim()) return
  
  if (!sessionStore.currentGroupId) return
  const groupId = sessionStore.currentGroupId
  
  if (!sessionStore.messagesMap[groupId]) {
    sessionStore.messagesMap[groupId] = []
  }
  
  sessionStore.messagesMap[groupId].push({
    id: Date.now(),
    role: 'user',
    content: input.value,
    createdAt: Date.now()
  })
  
  const currentInput = input.value
  input.value = ''

  // Mock assistant response
  setTimeout(() => {
    if (sessionStore.currentGroupId === groupId) {
      sessionStore.messagesMap[groupId].push({
        id: Date.now() + 1,
        role: 'assistant',
        content: `你刚才说：“${currentInput}”。我是群聊 AI，目前群聊互动功能还在开发中。`,
        createdAt: Date.now()
      })
    }
  }, 1000)
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
    <!-- Header -->
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
              <span class="member-count text-gray-400 text-sm font-normal">({{ currentGroup?.member_count || 0 }})</span>
            </div>
            <span v-if="sessionStore.isStreaming" class="typing-indicator">对方正在输入...</span>
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
          <template v-for="msg in messages" :key="msg.id">
            <div v-if="msg.role === 'system'" class="message-system">
              <span>{{ msg.content }}</span>
            </div>

            <template v-else-if="msg.role === 'assistant'">
              <!-- AI 回复：动态拆分渲染 -->
              <div v-for="(segment, sIndex) in parseMessageSegments(msg.content)" :key="msg.id + '-' + sIndex"
                class="message-group group-assistant">
                <div class="message-wrapper message-assistant group relative">
                  <!-- Avatar -->
                  <div class="message-avatar" @click="handleAvatarClick(getMemberAvatar(msg.senderId || 'assistant', 'assistant'))">
                    <img :src="getMemberAvatar(msg.senderId || 'assistant', 'assistant')" alt="Avatar" />
                  </div>

                  <!-- Message Bubble -->
                  <div class="message-bubble-container" :class="{ 'message-pop-in': segment }">
                    <!-- Member Name for groups -->
                    <span v-if="sIndex === 0" class="member-name">{{ getMemberName(msg.senderId || 'assistant', 'assistant') }}</span>
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
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <div class="input-toolbar">
        <EmojiPicker @select="input += $event" />
        <button class="toolbar-btn" title="新会话" @click="handleNewChat">
          <MessageSquarePlus :size="22" />
        </button>
      </div>

      <PromptInput class="input-box" @submit="handleSubmit">
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

    <!-- Toast Feedback -->
    <Transition name="fade">
      <div v-if="showToast" class="toast-feedback">
        {{ toastMessage }}
      </div>
    </Transition>

    <!-- Avatar Preview Dialog -->
    <Dialog v-model:open="showAvatarPreview">
      <DialogContent class="p-0 bg-transparent border-none shadow-none max-w-3xl w-auto flex justify-center items-center">
        <img :src="previewAvatarUrl" class="max-w-full max-h-[80vh] object-contain rounded-md" alt="Avatar Preview" />
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

@keyframes typing-fade {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.message-pop-in {
  animation: message-pop-in 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
}

@keyframes message-pop-in {
  from { opacity: 0; transform: scale(0.96) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
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
  background: #f5f5f5;
  border-top: 1px solid #e5e5e5;
  padding: 8px 16px 16px;
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
