import { ref, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { Message } from '@/types/chat'
import { useThinkingModeStore } from '@/stores/thinkingMode'

export { type Message }

export function useChat() {
    const store = useSessionStore()
    const thinkingModeStore = useThinkingModeStore()
    const input = ref('')

    // messages is computed from store
    const messages = computed(() => store.currentMessages)

    // Status: 'ready' | 'streaming'
    // Now directly based on per-friend streaming state from store
    const status = computed(() => {
        if (store.isStreaming) return 'streaming'
        return 'ready'
    })

    // Thinking mode state
    const isThinkingMode = computed(() => thinkingModeStore.isEnabled)
    const toggleThinkingMode = () => thinkingModeStore.toggle()

    const handleSubmit = (e?: Event | any) => {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault()
        }
        if (!input.value.trim()) return

        const content = input.value
        input.value = ''

        // Fire and forget - streaming state is managed per-friend in store
        store.sendMessage(content, thinkingModeStore.isEnabled).catch(error => {
            console.error('Failed to send message:', error)
        })
    }

    return {
        messages,
        input,
        status,
        isThinkingMode,
        toggleThinkingMode,
        handleSubmit
    }
}
