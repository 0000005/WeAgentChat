<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import { Menu, Bot } from 'lucide-vue-next'
import { 
  Conversation, 
  ConversationContent, 
  ConversationScrollButton 
} from '@/components/ai-elements/conversation'
import { Message, MessageContent } from '@/components/ai-elements/message'
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

const { messages, input, status, handleSubmit } = useChat()

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
    <header class="h-16 flex items-center px-4 md:px-8 border-b border-gray-100 bg-white/80 backdrop-blur-md sticky top-0 z-10">
      <button 
        @click="emit('toggle-sidebar')"
        class="mr-3 p-2 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors"
        :class="props.isSidebarCollapsed ? 'flex' : 'hidden md:hidden md:hover:flex'"
      >
        <Menu :size="20" :class="!props.isSidebarCollapsed ? 'md:hidden' : ''" />
      </button>
      <h2 class="font-semibold text-lg">{{ currentSessionTitle }}</h2>
    </header>

    <!-- Conversation Area -->
    <div class="flex-1 overflow-hidden relative"> <!-- Added overflow-hidden to contain the scrollable Conversation -->
      <Conversation class="h-full w-full">
        <ConversationContent class="p-4 md:p-8 space-y-6">
          <template v-for="(msg, index) in messages" :key="msg.id">
            <Message :from="msg.role">
              
              <Reasoning 
                v-if="msg.role === 'assistant' && msg.thinkingContent"
                :is-streaming="status === 'submitted' && index === messages.length - 1"
              >
                <ReasoningTrigger />
                <ReasoningContent :content="msg.thinkingContent" />
              </Reasoning>

              <MessageContent class="leading-relaxed" v-if="msg.content">
                {{ msg.content }}
              </MessageContent>
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
        class="w-full max-w-4xl mx-auto shadow-sm border border-gray-200 rounded-3xl overflow-hidden focus-within:border-gray-300 focus-within:shadow-md transition-all duration-300 bg-gray-50/50"
        @submit="handleSubmit"
      >
        <PromptInputTextarea 
          v-model="input"
          placeholder="Send a message to DouDou..." 
          class="min-h-[60px] max-h-[200px] text-[15px] px-4 py-3 bg-transparent border-none focus:ring-0 resize-none" 
        />
        
        <div class="px-3 pb-3 pt-0 flex justify-between items-center bg-transparent">
             <!-- Left side actions (optional) -->
             <div class="flex gap-2 items-center">
                <span class="text-xs text-gray-400 font-medium flex items-center gap-1 select-none">
                  <Bot :size="14" />
                  {{ llmStore.modelName }}
                </span>
             </div>

             <PromptInputSubmit 
               :disabled="status !== 'idle' && status !== 'streaming'" 
               :loading="status === 'submitted'"
               class="ml-auto" 
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
</style>
