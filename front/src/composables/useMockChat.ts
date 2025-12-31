import { ref, computed } from 'vue'
import { useSessionStore, type Message } from '@/stores/session'
import { nanoid } from 'nanoid'

export { type Message }

export function useMockChat() {
    const store = useSessionStore()
    const input = ref('')
    const status = ref<'idle' | 'streaming' | 'submitted'>('idle')

    // messages is computed from store
    const messages = computed(() => store.currentMessages)

    const append = async (messagePartial: Omit<Message, 'id' | 'createdAt'>) => {
        const newMessage: Message = {
            id: nanoid(),
            createdAt: Date.now(),
            ...messagePartial,
        }

        store.addMessageToCurrent(newMessage)

        if (newMessage.role === 'user') {
            await mockResponse()
        }
    }

    const mockResponse = async () => {
        status.value = 'submitted'

        // Simulate network delay (1-1.5s)
        const delay = 1000 + Math.random() * 500
        await new Promise((resolve) => setTimeout(resolve, delay))

        // Prepare response
        const responses = [
            "This is a simulated response from DouDou.",
            "I am thinking about your interesting question...",
            "Could you please elaborate on that?",
            "That is a great point! Here is what I think...",
            "Running deep analysis... (just kidding, I am a mock!)"
        ]
        const randomResponse = responses[Math.floor(Math.random() * responses.length)]

        // Create empty assistant message
        const assistantMsgId = nanoid()
        const assistantMessage: Message = {
            id: assistantMsgId,
            role: 'assistant',
            content: '',
            createdAt: Date.now(),
        }

        store.addMessageToCurrent(assistantMessage)

        status.value = 'streaming'

        // Simulate typewriter effect
        let currentIndex = 0
        const streamInterval = setInterval(() => {
            if (currentIndex < randomResponse.length) {
                // To update the message in the store, we can find it in the reactive array
                // Since store.currentMessages returns the reactive array from messagesMap
                const msgs = store.currentMessages
                // Ensure we find the message. It should be the last one, but let's be safe
                const msg = msgs.find(m => m.id === assistantMsgId)

                if (msg) {
                    msg.content += randomResponse[currentIndex]
                }
                currentIndex++
            } else {
                clearInterval(streamInterval)
                status.value = 'idle'
            }
        }, 30 + Math.random() * 20)
    }

    const handleSubmit = (e?: Event | any) => {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault()
        }
        if (!input.value.trim()) return

        const content = input.value
        input.value = ''
        append({ role: 'user', content })
    }

    return {
        messages,
        input,
        status,
        handleSubmit,
        append
    }
}
