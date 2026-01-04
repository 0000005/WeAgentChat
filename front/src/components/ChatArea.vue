<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useFriendStore } from '@/stores/friend'
import { Menu, Plus, Mic, Smile, MoreHorizontal, Brain, MessageSquarePlus } from 'lucide-vue-next'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '@/components/ai-elements/conversation'
import { Message, MessageContent, MessageResponse } from '@/components/ai-elements/message'
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit
} from '@/components/ai-elements/prompt-input'
import { Loader } from '@/components/ai-elements/loader'
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger
} from '@/components/ai-elements/reasoning'
import { useChat } from '@/composables/useChat'

const props = defineProps({
  isSidebarCollapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-sidebar'])

const { messages, input, status, isThinkingMode, toggleThinkingMode, handleSubmit } = useChat()

const sessionStore = useSessionStore()
const friendStore = useFriendStore()

// Get current friend's name for header
const currentFriendName = computed(() => {
  if (!sessionStore.currentFriendId) return '选择好友'
  const friend = friendStore.getFriend(sessionStore.currentFriendId)
  return friend ? friend.name : '好友'
})

// Check if a specific message is in loading state (assistant message with no content yet)
const isMessageLoading = (msg: any, index: number) => {
  if (msg.role !== 'assistant') return false
  if (status.value !== 'submitted' && status.value !== 'streaming') return false
  // Only the last message can be loading
  if (index !== messages.value.length - 1) return false
  // Loading if no content (showing loader even if thinking, to keep avatar company)
  return !msg.content
}

const hasMessages = computed(() => messages.value.length > 0)

// Get avatar for user/assistant
const getUserAvatar = () => 'https://api.dicebear.com/7.x/avataaars/svg?seed=user123'
const getAssistantAvatar = () => {
  // Use friend's avatar if available
  if (sessionStore.currentFriendId) {
    return `https://api.dicebear.com/7.x/bottts/svg?seed=${sessionStore.currentFriendId}`
  }
  return 'https://api.dicebear.com/7.x/bottts/svg?seed=doudou'
}

// Toast Feedback Logic
const showToast = ref(false)
const toastMessage = ref('')
let toastTimeout: ReturnType<typeof setTimeout> | null = null

const handleToggleThinking = () => {
  toggleThinkingMode()
  // Toast text based on new state
  toastMessage.value = isThinkingMode.value ? '已开启思考模式' : '思考模式已关闭'
  showToast.value = true

  if (toastTimeout) clearTimeout(toastTimeout)
  toastTimeout = setTimeout(() => {
    showToast.value = false
  }, 2000)
}

const handleNewChat = async () => {
  await sessionStore.startNewSession()
  // Scroll to bottom handles automatically by ConversationScrollButton or watch logic if exists,
  // but usually new messages trigger scroll.
}
</script>

<template>
  <div class="wechat-chat-area">
    <!-- Header -->
    <header class="chat-header">
      <button v-if="isSidebarCollapsed" @click="emit('toggle-sidebar')" class="mobile-menu-btn">
        <Menu :size="20" />
      </button>
      <h2 class="chat-title">{{ currentFriendName }}</h2>
      <button class="more-btn">
        <MoreHorizontal :size="20" />
      </button>
    </header>

    <!-- Messages Area -->
    <div class="chat-messages-container">
      <!-- Empty State with WeChat Logo -->
      <div v-if="!hasMessages" class="empty-state">
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
      <Conversation v-else class="h-full w-full">
        <ConversationContent class="messages-content">
          <template v-for="(msg, index) in messages" :key="msg.id">
            <div v-if="msg.role === 'system'" class="message-system">
              <span>{{ msg.content }}</span>
            </div>
            <div v-else class="message-group" :class="msg.role === 'user' ? 'group-user' : 'group-assistant'">
              <!-- Thinking Block (Assistant Only) - Placed above the message row -->
              <div v-if="msg.role === 'assistant' && msg.thinkingContent" class="reasoning-external-container">
                <Reasoning :is-streaming="status === 'submitted' && index === messages.length - 1"
                  class="reasoning-block">
                  <ReasoningTrigger />
                  <ReasoningContent :content="msg.thinkingContent" />
                </Reasoning>
              </div>

              <div class="message-wrapper" :class="msg.role === 'user' ? 'message-user' : 'message-assistant'">
                <!-- Avatar -->
                <div class="message-avatar">
                  <img :src="msg.role === 'user' ? getUserAvatar() : getAssistantAvatar()" alt="Avatar" />
                </div>

                <!-- Message Bubble -->
                <div class="message-bubble-container">
                  <!-- Loading state for assistant message -->
                  <div v-if="isMessageLoading(msg, index)" class="message-bubble loading-bubble">
                    <Loader class="h-5 w-5 text-gray-400" />
                  </div>

                  <!-- Normal message content -->
                  <div v-else-if="msg.content" class="message-bubble">
                    <MessageContent>
                      <MessageResponse :content="msg.content" />
                    </MessageContent>
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
    <div class="chat-input-area">
      <div class="input-toolbar">
        <button class="toolbar-btn" title="表情">
          <Smile :size="22" />
        </button>
        <button class="toolbar-btn" title="文件">
          <Plus :size="22" />
        </button>
        <button class="toolbar-btn" title="新会话" @click="handleNewChat">
          <MessageSquarePlus :size="22" />
        </button>
      </div>

      <PromptInput class="input-box" @submit="handleSubmit">
        <PromptInputTextarea v-model="input" placeholder="输入消息..." class="input-textarea" />
        <div class="input-footer">
          <div class="footer-left">
            <button class="voice-btn" title="语音">
              <Mic :size="18" />
            </button>

            <!-- Thinking Mode Toggle -->
            <button type="button" class="thinking-btn" :class="{ 'active': isThinkingMode }"
              @click="handleToggleThinking" title="深度思考">
              <Brain :size="18" />
            </button>
          </div>

          <PromptInputSubmit :status="status" :loading="status === 'submitted'" class="send-btn" />
        </div>
      </PromptInput>
    </div>

    <!-- Toast Feedback -->
    <Transition name="fade">
      <div v-if="showToast" class="toast-feedback">
        {{ toastMessage }}
      </div>
    </Transition>
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
}

.mobile-menu-btn {
  padding: 8px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
}

.mobile-menu-btn:hover {
  background: #e5e5e5;
}

.chat-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  flex: 1;
  text-align: center;
}

.more-btn {
  padding: 8px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-radius: 4px;
}

.more-btn:hover {
  background: #e5e5e5;
}

/* Empty State */
.chat-messages-container {
  flex: 1;
  overflow: hidden;
  position: relative;
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
}

.message-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
  ring: none !important;
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
</style>
