<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessionStore } from '@/stores/session'
import { usePersonaStore } from '@/stores/persona'
import { storeToRefs } from 'pinia'
import { 
  SquarePen, 
  MessageSquare, 
  Settings, 
  PanelLeft,
  MoreVertical,
  Trash2,
  UserPlus,
  Bot,
  Edit
} from 'lucide-vue-next'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import PersonaEditorDialog from '@/components/PersonaEditorDialog.vue'
import SettingsDialog from '@/components/SettingsDialog.vue'

const emit = defineEmits(['toggle-sidebar'])

const sessionStore = useSessionStore()
const personaStore = usePersonaStore()
const { sessions, currentSessionId } = storeToRefs(sessionStore)
const { personas } = storeToRefs(personaStore)

const activeTab = ref<'sessions' | 'personas'>('sessions')

// Settings Logic
const isSettingsOpen = ref(false)

// Session Grouping Logic
const groupedSessions = computed(() => {
    const today = new Date().setHours(0, 0, 0, 0)
    const groups = {
        '今天': [] as typeof sessions.value,
        '更早': [] as typeof sessions.value
    }
    
    sessions.value.forEach(session => {
        if (session.createdAt >= today) {
            groups['今天'].push(session)
        } else {
            groups['更早'].push(session)
        }
    })
    
    return groups
})

const onSelectSession = (id: number) => {
    sessionStore.selectSession(id)
}

const onNewChat = () => {
    sessionStore.createSession()
}

// Delete Session Dialog Logic
const isDeleteSessionOpen = ref(false)
const sessionToDelete = ref<number | null>(null)

const openDeleteSessionDialog = (id: number) => {
    sessionToDelete.value = id
    isDeleteSessionOpen.value = true
}

const confirmDeleteSession = () => {
    if (sessionToDelete.value) {
        sessionStore.deleteSession(sessionToDelete.value)
    }
    isDeleteSessionOpen.value = false
    sessionToDelete.value = null
}

// Persona Logic
const isPersonaDialogOpen = ref(false)
const editingPersonaId = ref<number | null>(null)

// Delete Persona Dialog Logic
const isDeletePersonaOpen = ref(false)
const personaToDelete = ref<number | null>(null)

const onNewPersona = () => {
    editingPersonaId.value = null
    isPersonaDialogOpen.value = true
}

const onEditPersona = (id: number) => {
    editingPersonaId.value = id
    isPersonaDialogOpen.value = true
}

const onDeletePersona = (id: number) => {
    personaToDelete.value = id
    isDeletePersonaOpen.value = true
}

const confirmDeletePersona = async () => {
    if (personaToDelete.value !== null) {
        await personaStore.deletePersona(personaToDelete.value)
    }
    isDeletePersonaOpen.value = false
    personaToDelete.value = null
}

const onStartChatFromPersona = () => {
    // This event comes from the dialog "Start Chat" button
    // Switch to sessions tab
    activeTab.value = 'sessions'
}

const onStartChatDirectly = (personaId: number) => {
    sessionStore.createSession(personaId)
    activeTab.value = 'sessions'
}
</script>

<template>
  <aside class="w-[260px] flex flex-col bg-[#f9fafb] border-r border-gray-200 h-full relative">
    <!-- Header -->
    <div class="p-4 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-black rounded-lg flex items-center justify-center">
          <svg viewBox="0 0 24 24" class="w-5 h-5 text-white fill-current">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
          </svg>
        </div>
        <span class="font-bold text-xl tracking-tight">DouDou</span>
      </div>
      <button 
        @click="emit('toggle-sidebar')"
        class="text-gray-500 hover:bg-gray-200 p-1.5 rounded-md transition-colors"
      >
        <PanelLeft :size="18" />
      </button>
    </div>

    <!-- Tab Switcher -->
    <div class="px-4 pb-2">
        <div class="grid grid-cols-2 p-1 bg-gray-100 rounded-lg">
            <button 
                class="py-1.5 text-sm font-medium rounded-md transition-all"
                :class="activeTab === 'sessions' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'"
                @click="activeTab = 'sessions'"
            >
                会话
            </button>
            <button 
                class="py-1.5 text-sm font-medium rounded-md transition-all"
                :class="activeTab === 'personas' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'"
                @click="activeTab = 'personas'"
            >
                角色
            </button>
        </div>
    </div>

    <!-- SESSIONS VIEW -->
    <template v-if="activeTab === 'sessions'">
        <!-- New Chat Button -->
        <div class="px-4 mb-2">
            <button 
                @click="onNewChat"
                class="w-full flex items-center gap-3 px-3 py-2.5 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-all shadow-sm group"
            >
                <SquarePen :size="18" class="text-gray-500 group-hover:text-black" />
                <span class="text-sm font-medium">新对话</span>
            </button>
        </div>

        <!-- Session List -->
        <div class="flex-1 overflow-y-auto px-2 py-2 space-y-4">
            <template v-for="(list, group) in groupedSessions" :key="group">
                <div v-if="list.length > 0">
                    <div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {{ group }}
                    </div>
                    <div class="space-y-0.5">
                        <div 
                            v-for="session in list" 
                            :key="session.id"
                            class="group relative w-full flex items-center px-3 py-2 rounded-xl text-sm transition-colors cursor-pointer"
                            :class="session.id === currentSessionId ? 'bg-gray-200 text-black' : 'text-gray-600 hover:bg-gray-100'"
                            @click="onSelectSession(session.id)"
                        >
                            <MessageSquare :size="16" class="opacity-60 mr-3 shrink-0" />
                            <span class="truncate flex-1">{{ session.title }}</span>
                            
                            <!-- Dropdown Menu -->
                            <DropdownMenu>
                                <DropdownMenuTrigger as-child>
                                    <button 
                                        class="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-300 rounded ml-1 transition-opacity data-[state=open]:opacity-100" 
                                        @click.stop
                                    >
                                        <MoreVertical :size="14" />
                                    </button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                    <DropdownMenuItem @click.stop="openDeleteSessionDialog(session.id)" class="text-red-600 focus:text-red-600 cursor-pointer">
                                        <Trash2 class="mr-2 h-4 w-4" />
                                        删除会话
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </template>
        </div>
    </template>

    <!-- PERSONAS VIEW -->
    <template v-else>
        <!-- New Persona Button -->
        <div class="px-4 mb-2">
            <button 
                @click="onNewPersona"
                class="w-full flex items-center gap-3 px-3 py-2.5 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-all shadow-sm group"
            >
                <UserPlus :size="18" class="text-gray-500 group-hover:text-black" />
                <span class="text-sm font-medium">新建角色</span>
            </button>
        </div>

        <!-- Persona List -->
        <div class="flex-1 overflow-y-auto px-2 py-2">
            <div class="space-y-0.5">
                <div 
                    v-for="persona in personas" 
                    :key="persona.id"
                    class="group relative w-full flex items-center px-3 py-3 rounded-xl text-sm transition-colors cursor-pointer text-gray-600 hover:bg-gray-100"
                    @click="onStartChatDirectly(persona.id)"
                >
                    <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center mr-3 text-indigo-600 shrink-0">
                        <Bot :size="16" />
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-gray-900 truncate">{{ persona.name }}</div>
                        <div class="text-xs text-gray-500 truncate">{{ persona.description }}</div>
                    </div>
                    
                     <!-- Dropdown Menu -->
                    <DropdownMenu>
                        <DropdownMenuTrigger as-child>
                            <button 
                                class="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-300 rounded ml-1 transition-opacity data-[state=open]:opacity-100" 
                                @click.stop
                            >
                                <MoreVertical :size="14" />
                            </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem @click.stop="onEditPersona(persona.id)" class="cursor-pointer">
                                <Edit class="mr-2 h-4 w-4" />
                                编辑角色
                            </DropdownMenuItem>
                            <DropdownMenuSeparator v-if="!persona.is_preset" />
                            <DropdownMenuItem 
                                v-if="!persona.is_preset"
                                @click.stop="onDeletePersona(persona.id)" 
                                class="text-red-600 focus:text-red-600 cursor-pointer"
                            >
                                <Trash2 class="mr-2 h-4 w-4" />
                                删除角色
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
        </div>
    </template>

    <!-- Bottom Actions -->
    <div class="p-4 border-t border-gray-200">
      <button 
        @click="isSettingsOpen = true"
        class="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-600 hover:bg-gray-100 transition-colors"
      >
        <Settings :size="18" />
        <span>设置</span>
      </button>
    </div>
    
    <!-- Delete Session Dialog -->
    <Dialog v-model:open="isDeleteSessionOpen">
        <DialogContent class="sm:max-w-[425px]">
            <DialogHeader>
                <DialogTitle>确认删除</DialogTitle>
                <DialogDescription>
                    您确定要删除此会话吗？此操作无法撤销。
                </DialogDescription>
            </DialogHeader>
            <DialogFooter>
                <Button variant="outline" @click="isDeleteSessionOpen = false">取消</Button>
                <Button variant="destructive" @click="confirmDeleteSession">删除</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Delete Persona Dialog -->
    <Dialog v-model:open="isDeletePersonaOpen">
        <DialogContent class="sm:max-w-[425px]">
            <DialogHeader>
                <DialogTitle>确认删除角色</DialogTitle>
                <DialogDescription>
                    您确定要删除这个角色吗？此操作无法撤销。
                </DialogDescription>
            </DialogHeader>
            <DialogFooter>
                <Button variant="outline" @click="isDeletePersonaOpen = false">取消</Button>
                <Button variant="destructive" @click="confirmDeletePersona">删除</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Persona Editor Dialog -->
    <PersonaEditorDialog 
        v-model:open="isPersonaDialogOpen"
        :persona-id="editingPersonaId"
        @start-chat="onStartChatFromPersona"
    />

    <!-- Settings Dialog -->
    <SettingsDialog v-model:open="isSettingsOpen" />
  </aside>
</template>