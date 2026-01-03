<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import { Menu, Plus, Mic, Smile, MoreHorizontal } from 'lucide-vue-next'
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

const store = useSessionStore()

const currentSessionTitle = computed(() => {
  const session = store.sessions.find(s => s.id === store.currentSessionId)
  return session ? session.title : '豆豆'
})

const shouldShowLoader = computed(() => {
  if (status.value !== 'submitted') return false
  if (messages.value.length === 0) return true
  const lastMsg = messages.value[messages.value.length - 1]
  return lastMsg.role !== 'assistant' || (!lastMsg.content && !lastMsg.thinkingContent)
})

const hasMessages = computed(() => messages.value.length > 0)

// Get avatar for user/assistant
const getUserAvatar = () => 'https://api.dicebear.com/7.x/avataaars/svg?seed=user123'
const getAssistantAvatar = () => 'https://api.dicebear.com/7.x/bottts/svg?seed=doudou'
</script>

<template>
  <div class="wechat-chat-area">
    <!-- Header -->
    <header class="chat-header">
      <button 
        v-if="isSidebarCollapsed"
        @click="emit('toggle-sidebar')"
        class="mobile-menu-btn"
      >
        <Menu :size="20" />
      </button>
      <h2 class="chat-title">{{ currentSessionTitle }}</h2>
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
              <ellipse cx="38" cy="45" rx="28" ry="24"/>
              <ellipse cx="62" cy="55" rx="28" ry="24"/>
              <circle cx="30" cy="42" r="4" fill="#f5f5f5"/>
              <circle cx="46" cy="42" r="4" fill="#f5f5f5"/>
              <circle cx="54" cy="58" r="3" fill="#e9e9e9"/>
              <circle cx="70" cy="58" r="3" fill="#e9e9e9"/>
            </g>
          </svg>
        </div>
      </div>

      <!-- Conversation with Messages -->
      <Conversation v-else class="h-full w-full">
        <ConversationContent class="messages-content">
          <template v-for="(msg, index) in messages" :key="msg.id">
            <div 
              class="message-wrapper"
              :class="msg.role === 'user' ? 'message-user' : 'message-assistant'"
            >
              <!-- Avatar -->
              <div class="message-avatar">
                <img 
                  :src="msg.role === 'user' ? getUserAvatar() : getAssistantAvatar()" 
                  alt="Avatar"
                />
              </div>

              <!-- Message Bubble -->
              <div class="message-bubble-container">
                <Reasoning 
                  v-if="msg.role === 'assistant' && msg.thinkingContent"
                  :is-streaming="status === 'submitted' && index === messages.length - 1"
                  class="reasoning-block"
                >
                  <ReasoningTrigger />
                  <ReasoningContent :content="msg.thinkingContent" />
                </Reasoning>

                <div v-if="msg.content" class="message-bubble">
                  <MessageContent>
                    <MessageResponse :content="msg.content" />
                  </MessageContent>
                </div>
              </div>
            </div>
          </template>

          <!-- Loading State -->
          <div v-if="shouldShowLoader" class="message-wrapper message-assistant">
            <div class="message-avatar">
              <img :src="getAssistantAvatar()" alt="Avatar" />
            </div>
            <div class="message-bubble loading-bubble">
              <Loader class="h-5 w-5 text-gray-400" />
            </div>
          </div>
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
      </div>
      
      <PromptInput class="input-box" @submit="handleSubmit">
        <PromptInputTextarea 
          v-model="input" 
          placeholder="输入消息..."
          class="input-textarea"
        />
        <div class="input-footer">
          <button class="voice-btn" title="语音">
            <Mic :size="18" />
          </button>
          <PromptInputSubmit 
            :status="status" 
            :loading="status === 'submitted'"
            class="send-btn"
          />
        </div>
      </PromptInput>
    </div>
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
</style>
