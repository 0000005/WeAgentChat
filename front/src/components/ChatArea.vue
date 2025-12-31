<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import { Menu, Bot, Brain, Plus, Mic, Globe } from 'lucide-vue-next'
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
import { useLlmStore } from '@/stores/llm'
const llmStore = useLlmStore()

const currentSessionTitle = computed(() => {
  const session = store.sessions.find(s => s.id === store.currentSessionId)
  return session ? session.title : 'DouDou'
})

const shouldShowLoader = computed(() => {
  if (status.value !== 'submitted') return false
  if (messages.value.length === 0) return true
  const lastMsg = messages.value[messages.value.length - 1]
  return lastMsg.role !== 'assistant' || (!lastMsg.content && !lastMsg.thinkingContent)
})
</script>

<template>
  <div class="flex flex-col h-full relative bg-white">
    <!-- Header -->
    <header
      class="h-16 flex items-center px-4 md:px-8 border-b border-gray-100 bg-white/80 backdrop-blur-md sticky top-0 z-10">
      <button @click="emit('toggle-sidebar')"
        class="mr-3 p-2 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors"
        :class="props.isSidebarCollapsed ? 'flex' : 'hidden md:hidden md:hover:flex'">
        <Menu :size="20" :class="!props.isSidebarCollapsed ? 'md:hidden' : ''" />
      </button>
      <h2 class="font-semibold text-lg flex-1">{{ currentSessionTitle }}</h2>

      <!-- Thinking Mode Toggle -->
      <button @click="toggleThinkingMode"
        class="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200" :class="isThinkingMode
          ? 'bg-purple-100 text-purple-700 hover:bg-purple-200'
          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'" :title="isThinkingMode ? '关闭思考模式' : '开启思考模式'">
        <Brain :size="16" />
        <span class="hidden sm:inline">{{ isThinkingMode ? '思考中' : '思考' }}</span>
      </button>
    </header>

    <!-- Conversation Area -->
    <div class="flex-1 overflow-hidden relative"> <!-- Added overflow-hidden to contain the scrollable Conversation -->
      <Conversation class="h-full w-full">
        <ConversationContent class="p-4 md:p-8 space-y-6">
          <template v-for="(msg, index) in messages" :key="msg.id">
            <Message :from="msg.role">
              <div class="flex flex-col gap-2 w-full">
                <Reasoning v-if="msg.role === 'assistant' && msg.thinkingContent"
                  :is-streaming="status === 'submitted' && index === messages.length - 1">
                  <ReasoningTrigger />
                  <ReasoningContent :content="msg.thinkingContent" />
                </Reasoning>

                <MessageContent class="leading-relaxed" v-if="msg.content">
                  <MessageResponse :content="msg.content" />
                </MessageContent>
              </div>
            </Message>
          </template>

          <!-- Loading State (AI Thinking) -->
          <div v-if="shouldShowLoader" class="flex justify-start">
            <div class="bg-muted/50 rounded-2xl px-4 py-3">
              <Loader class="h-5 w-5 text-muted-foreground" />
            </div>
          </div>
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>
    </div>

    <!-- Input Area -->
    <div class="px-4 md:px-24 pb-8 pt-4">
      <PromptInput
        class="w-full max-w-5xl mx-auto shadow-lg border border-gray-100/50 rounded-2xl bg-white"
        @submit="handleSubmit">
        <PromptInputTextarea v-model="input" placeholder="What would you like to know?"
          class="min-h-[100px] max-h-[300px] text-base px-5 py-5 bg-transparent border-none focus:ring-0 resize-none placeholder:text-gray-400 text-gray-800 w-full shadow-none focus-visible:ring-0" />

        <div class="px-4 pb-4 pt-2 flex justify-between items-center bg-transparent mt-auto">
          <!-- Left side actions -->
          <div class="flex gap-4 items-center">
            <div class="flex gap-1">
              <button type="button"
                class="text-gray-400 hover:text-gray-600 p-2 rounded-full hover:bg-gray-100 transition-all duration-200"
                title="Add Attachment"
              >
                <Plus :size="20" stroke-width="1.5" />
              </button>
              
              <button type="button"
                class="text-gray-400 hover:text-gray-600 p-2 rounded-full hover:bg-gray-100 transition-all duration-200"
                title="Voice Input"
              >
                <Mic :size="20" stroke-width="1.5" />
              </button>
            </div>

            <button type="button"
              class="flex items-center gap-2 text-gray-500 hover:text-gray-800 px-2 py-1.5 rounded-full hover:bg-gray-100 transition-all duration-200 group"
            >
              <Globe :size="18" stroke-width="1.5" class="group-hover:text-blue-500 transition-colors" />
              <span class="text-sm font-medium">Search</span>
            </button>

            <div class="flex items-center gap-2 text-gray-500 select-none px-2">
              <Bot :size="18" stroke-width="1.5" class="text-gray-400" />
              <span class="text-sm font-medium tracking-tight text-gray-600">{{ llmStore.modelName }}</span>
            </div>
          </div>

          <PromptInputSubmit :status="status" :loading="status === 'submitted'"
            class="ml-auto bg-gray-900 text-white hover:bg-black rounded-xl w-10 h-10 p-0 flex items-center justify-center transition-all duration-200 shadow-sm hover:shadow active:scale-95" 
          />
        </div>
      </PromptInput>

      <div class="text-center mt-2">
        <p class="text-xs text-gray-400">DouDou can make mistakes. Check important info.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Ensure the Conversation component takes full height of its container */
:deep(.conversation) {
  height: 100%;
}

/* Force the InputGroup to act as a column for this specific design */
:deep([data-slot="input-group"]) {
  flex-direction: column !important;
  align-items: stretch !important;
  height: auto !important;
  border: none !important; /* Remove inner border to use the outer one */
  box-shadow: none !important;
}
</style>
