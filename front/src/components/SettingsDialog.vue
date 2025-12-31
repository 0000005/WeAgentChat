<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Eye, EyeOff, Loader2 } from 'lucide-vue-next'
import { useLlmStore } from '@/stores/llm'
import { storeToRefs } from 'pinia'

defineProps<{
  open: boolean
}>()

const emit = defineEmits(['update:open'])

const llmStore = useLlmStore()
const { apiBaseUrl, apiKey, modelName, isLoading } = storeToRefs(llmStore)

const activeTab = ref('llm')
const showApiKey = ref(false)

const toggleApiKeyVisibility = () => {
  showApiKey.value = !showApiKey.value
}

onMounted(() => {
    llmStore.fetchConfig()
})

const handleSave = async () => {
    try {
        await llmStore.saveConfig()
        emit('update:open', false)
    } catch (error) {
        // Error handling could be improved with a toast notification
        console.error('Failed to save settings', error)
    }
}
</script>

<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[700px] p-0 overflow-hidden flex h-[500px] gap-0">
      <DialogTitle class="sr-only">设置</DialogTitle>
      <DialogDescription class="sr-only">应用配置界面</DialogDescription>
        
      <!-- Sidebar -->
      <div class="w-[200px] bg-gray-50 border-r border-gray-200 p-4 flex flex-col gap-1">
        <h3 class="font-semibold mb-4 px-2 text-lg">设置</h3>
        <button 
            class="w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-colors"
            :class="activeTab === 'llm' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'"
            @click="activeTab = 'llm'"
        >
            LLM 设置
        </button>
      </div>

      <!-- Right Side Container -->
      <div class="flex-1 flex flex-col h-full overflow-hidden">
          <!-- Content -->
          <div class="flex-1 p-6 overflow-y-auto">
            <template v-if="activeTab === 'llm'">
                <div class="space-y-6">
                    <div>
                        <h3 class="text-lg font-medium">LLM 配置</h3>
                        <p class="text-sm text-gray-500">配置连接到大语言模型 API 的参数。</p>
                    </div>

                    <div class="space-y-4">
                        <div class="grid gap-2">
                            <label class="text-sm font-medium leading-none">
                                API Base URL
                            </label>
                            <Input v-model="apiBaseUrl" placeholder="例如: https://api.openai.com/v1" />
                            <p class="text-xs text-gray-500">
                                OpenAI 兼容接口的地址。为空则默认使用官方地址。
                            </p>
                        </div>

                        <div class="grid gap-2">
                            <label class="text-sm font-medium leading-none">
                                API Key
                            </label>
                            <div class="relative">
                                <Input 
                                    v-model="apiKey" 
                                    :type="showApiKey ? 'text' : 'password'" 
                                    placeholder="sk-..." 
                                    class="pr-10"
                                />
                                <button 
                                    type="button"
                                    @click="toggleApiKeyVisibility"
                                    class="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-gray-500 hover:text-gray-900 flex items-center justify-center"
                                >
                                    <Eye v-if="!showApiKey" :size="16" />
                                    <EyeOff v-else :size="16" />
                                </button>
                            </div>
                        </div>

                        <div class="grid gap-2">
                            <label class="text-sm font-medium leading-none">
                                Model Name
                            </label>
                            <Input v-model="modelName" placeholder="例如: gpt-3.5-turbo" />
                        </div>
                    </div>
                </div>
            </template>
          </div>

          <!-- Footer -->
          <div class="p-4 border-t border-gray-100 flex justify-end gap-2 bg-white">
              <Button variant="outline" @click="$emit('update:open', false)">取消</Button>
              <Button @click="handleSave" :disabled="isLoading">
                  <Loader2 v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                  保存
              </Button>
          </div>
      </div>

    </DialogContent>
  </Dialog>
</template>