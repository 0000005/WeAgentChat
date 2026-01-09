import { ref } from 'vue'

export interface ToastMessage {
    id: number
    message: string
    type: 'success' | 'error' | 'info'
    duration: number
}

const toasts = ref<ToastMessage[]>([])
let toastId = 0

export function useToast() {
    const showToast = (message: string, type: ToastMessage['type'] = 'info', duration = 2500) => {
        const id = ++toastId
        toasts.value.push({ id, message, type, duration })

        setTimeout(() => {
            removeToast(id)
        }, duration)

        return id
    }

    const removeToast = (id: number) => {
        const index = toasts.value.findIndex(t => t.id === id)
        if (index !== -1) {
            toasts.value.splice(index, 1)
        }
    }

    const success = (message: string, duration?: number) => showToast(message, 'success', duration)
    const error = (message: string, duration?: number) => showToast(message, 'error', duration)
    const info = (message: string, duration?: number) => showToast(message, 'info', duration)

    return {
        toasts,
        showToast,
        removeToast,
        success,
        error,
        info
    }
}
