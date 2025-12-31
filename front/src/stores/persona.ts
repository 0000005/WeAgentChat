import { defineStore } from 'pinia'
import { ref } from 'vue'
import { 
    type Persona, 
    type PersonaCreate, 
    type PersonaUpdate,
    getPersonas as apiGetPersonas,
    createPersona as apiCreatePersona,
    updatePersona as apiUpdatePersona,
    deletePersona as apiDeletePersona
} from '@/api/persona'

export const usePersonaStore = defineStore('persona', () => {
    const personas = ref<Persona[]>([])
    const isLoading = ref(false)
    const error = ref<string | null>(null)

    const fetchPersonas = async () => {
        isLoading.value = true
        error.value = null
        try {
            personas.value = await apiGetPersonas()
        } catch (e) {
            console.error('Failed to fetch personas', e)
            error.value = 'Failed to fetch personas'
        } finally {
            isLoading.value = false
        }
    }

    const addPersona = async (persona: PersonaCreate) => {
        isLoading.value = true
        try {
            const newPersona = await apiCreatePersona(persona)
            personas.value.push(newPersona)
            return newPersona
        } catch (e) {
            console.error('Failed to create persona', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const updatePersona = async (id: number, updates: PersonaUpdate) => {
        isLoading.value = true
        try {
            const updated = await apiUpdatePersona(id, updates)
            const index = personas.value.findIndex(p => p.id === id)
            if (index !== -1) {
                personas.value[index] = updated
            }
            return updated
        } catch (e) {
            console.error('Failed to update persona', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const deletePersona = async (id: number) => {
        isLoading.value = true
        try {
            await apiDeletePersona(id)
            const index = personas.value.findIndex(p => p.id === id)
            if (index !== -1) {
                personas.value.splice(index, 1)
            }
        } catch (e) {
            console.error('Failed to delete persona', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    const getPersona = (id: number) => {
        return personas.value.find(p => p.id === id)
    }

    // Initial fetch
    fetchPersonas()

    return {
        personas,
        isLoading,
        error,
        fetchPersonas,
        addPersona,
        updatePersona,
        deletePersona,
        getPersona
    }
})
