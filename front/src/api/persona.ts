export interface Persona {
  id: number
  name: string
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean
  create_time: string
  update_time: string
  deleted: boolean
}

export interface PersonaCreate {
  name: string
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean
}

export interface PersonaUpdate {
  name?: string | null
  description?: string | null
  system_prompt?: string | null
  is_preset?: boolean | null
}

export async function getPersonas(skip: number = 0, limit: number = 100): Promise<Persona[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  const response = await fetch(`/api/personas/?${params}`)
  if (!response.ok) {
    throw new Error('Failed to fetch personas')
  }
  return response.json()
}

export async function createPersona(persona: PersonaCreate): Promise<Persona> {
  const response = await fetch('/api/personas/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(persona),
  })
  if (!response.ok) {
    throw new Error('Failed to create persona')
  }
  return response.json()
}

export async function getPersona(id: number): Promise<Persona> {
  const response = await fetch(`/api/personas/${id}`)
  if (!response.ok) {
    throw new Error('Failed to fetch persona')
  }
  return response.json()
}

export async function updatePersona(id: number, persona: PersonaUpdate): Promise<Persona> {
  const response = await fetch(`/api/personas/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(persona),
  })
  if (!response.ok) {
    throw new Error('Failed to update persona')
  }
  return response.json()
}

export async function deletePersona(id: number): Promise<Persona> {
  const response = await fetch(`/api/personas/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete persona')
  }
  return response.json()
}
