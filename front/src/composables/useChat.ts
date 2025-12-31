import { ref, computed } from 'vue'
import { useSessionStore, type Message } from '@/stores/session'

export { type Message }

export function useChat() {
    const store = useSessionStore()
    const input = ref('')
    const status = ref<'idle' | 'streaming' | 'submitted'>('idle')

    // messages is computed from store
    const messages = computed(() => store.currentMessages)

    const handleSubmit = async (e?: Event | any) => {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault()
        }
        if (!input.value.trim()) return

        const content = input.value
        input.value = ''
        
        status.value = 'submitted'
        try {
            await store.sendMessage(content)
        } catch (error) {
            console.error(error)
        } finally {
            status.value = 'idle'
        }
    }

    return {
        messages,
        input,
        status,
        handleSubmit
    }
}
