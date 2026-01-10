<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useMemoryStore } from '@/stores/memory'
import { Plus, Trash2, Edit2, Check, X, Loader2, Camera } from 'lucide-vue-next'
import AvatarUploader from '@/components/common/AvatarUploader.vue'
import { useSettingsStore } from '@/stores/settings'
import { getStaticUrl } from '@/api/base'

const props = defineProps<{
    open: boolean
}>()

const emit = defineEmits<{
    (e: 'update:open', value: boolean): void
}>()

const memoryStore = useMemoryStore()
const isAdding = ref(false)
const newEntry = ref({ content: '', topic: '' })
const editingId = ref<string | null>(null)
const editingContent = ref('')
const isAvatarUploaderOpen = ref(false)
const settingsStore = useSettingsStore()

const userAvatar = computed({
    get: () => settingsStore.userAvatar,
    set: (val) => settingsStore.saveUserSettings(val)
}) 

const userAvatarDisplayUrl = computed(() => 
    getStaticUrl(settingsStore.userAvatar) || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'
)

onMounted(async () => {
    if (props.open) {
        await initialize()
    }
})

watch(() => props.open, async (val) => {
    if (val) {
        await initialize()
    }
})

const initialize = async () => {
    await memoryStore.fetchConfig()
    await memoryStore.fetchProfiles()
    await settingsStore.fetchUserSettings()
    if (memoryStore.profileConfig.topics.length > 0) {
        newEntry.value.topic = memoryStore.profileConfig.topics[0].topic
    }
}

const handleAdd = async () => {
    if (!newEntry.value.content.trim()) return
    try {
        await memoryStore.upsertProfile(null, newEntry.value.content, { topic: newEntry.value.topic })
        newEntry.value.content = ''
        isAdding.value = false
    } catch (error) {
        console.error('Failed to add profile:', error)
    }
}

const startEdit = (id: string, content: string) => {
    editingId.value = id
    editingContent.value = content
}

const cancelEdit = () => {
    editingId.value = null
    editingContent.value = ''
}

const saveEdit = async (id: string, topic: string) => {
    if (!editingContent.value.trim()) return
    try {
        await memoryStore.upsertProfile(id, editingContent.value, { topic })
        editingId.value = null
    } catch (error) {
        console.error('Failed to update profile:', error)
    }
}

const handleDelete = async (id: string) => {
    try {
        await memoryStore.removeProfile(id)
    } catch (error) {
        console.error('Failed to delete profile:', error)
    }
}

// Custom directive for auto-focus on input
const vFocus = {
    mounted: (el: HTMLElement) => el.focus()
}
</script>

<template>
    <Dialog :open="open" @update:open="emit('update:open', $event)">
        <DialogContent class="max-w-2xl h-[80vh] flex flex-col p-0 overflow-hidden bg-[#f3f3f3] border-none shadow-2xl">
            <DialogHeader class="p-4 bg-white border-b shrink-0">
                <DialogTitle class="text-lg font-medium text-center">个人资料</DialogTitle>
            </DialogHeader>
            
            <!-- Avatar Section -->
            <div class="flex flex-col items-center py-6 bg-white border-b shrink-0">
                <div class="relative group cursor-pointer" @click="isAvatarUploaderOpen = true">
                    <img :src="userAvatarDisplayUrl" 
                         class="w-24 h-24 rounded-lg object-cover border border-gray-200 shadow-sm bg-gray-50" />
                    <div class="absolute inset-0 bg-black/40 rounded-lg opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-[1px]">
                        <Camera class="text-white w-8 h-8" stroke-width="1.5" />
                    </div>
                </div>
                <div class="mt-3 text-xs text-gray-500">点击更换头像</div>
            </div>


            <ScrollArea class="flex-1 p-4">
                <div class="space-y-6">
                    <div v-if="memoryStore.isLoading && memoryStore.profiles.length === 0"
                        class="flex justify-center py-10">
                        <Loader2 class="w-8 h-8 animate-spin text-gray-400" />
                    </div>

                    <template v-else>
                        <Card v-for="topic in memoryStore.profileConfig.topics" :key="topic.topic"
                            class="border-none shadow-sm overflow-hidden mb-4">
                            <CardHeader class="bg-white py-2 px-4 border-b">
                                <CardTitle
                                    class="text-sm font-semibold text-gray-700 flex items-center justify-between">
                                    <span>{{ topic.topic }}</span>
                                    <span class="text-xs font-normal text-gray-400">{{ topic.description }}</span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent class="p-0 bg-white">
                                <div v-if="memoryStore.groupedProfiles[topic.topic]?.length === 0"
                                    class="p-6 text-center text-sm text-gray-400">
                                    暂无记录
                                </div>
                                <div v-else class="divide-y divide-gray-100">
                                    <div v-for="profile in memoryStore.groupedProfiles[topic.topic]" :key="profile.id"
                                        class="group flex items-start gap-3 p-3 hover:bg-gray-50 transition-colors">
                                        <div class="flex-1">
                                            <div v-if="editingId === profile.id" class="flex items-center gap-2">
                                                <Input v-model="editingContent"
                                                    class="h-8 text-sm focus-visible:ring-emerald-500"
                                                    @keyup.enter="saveEdit(profile.id, topic.topic)"
                                                    @keyup.esc="cancelEdit" v-focus />
                                                <Button size="icon" variant="ghost" class="h-8 w-8 text-emerald-600"
                                                    @click="saveEdit(profile.id, topic.topic)">
                                                    <Check class="h-4 w-4" />
                                                </Button>
                                                <Button size="icon" variant="ghost" class="h-8 w-8 text-gray-400"
                                                    @click="cancelEdit">
                                                    <X class="h-4 w-4" />
                                                </Button>
                                            </div>
                                            <div v-else
                                                class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                                                {{ profile.content }}
                                            </div>
                                        </div>

                                        <div v-if="editingId !== profile.id"
                                            class="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                                            <Button size="icon" variant="ghost"
                                                class="h-8 w-8 text-gray-400 hover:text-emerald-600"
                                                @click="startEdit(profile.id, profile.content)">
                                                <Edit2 class="h-4 w-4" />
                                            </Button>
                                            <Button size="icon" variant="ghost"
                                                class="h-8 w-8 text-gray-400 hover:text-red-600"
                                                @click="handleDelete(profile.id)">
                                                <Trash2 class="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </template>
                </div>
            </ScrollArea>

            <div class="p-4 bg-white border-t shrink-0">
                <div v-if="isAdding" class="flex flex-col gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-medium text-gray-500 w-12 text-right">分类:</span>
                        <Select v-model="newEntry.topic">
                            <SelectTrigger class="h-8 text-xs w-32">
                                <SelectValue placeholder="选择分类" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem v-for="t in memoryStore.profileConfig.topics" :key="t.topic"
                                    :value="t.topic">
                                    {{ t.topic }}
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-medium text-gray-500 w-12 text-right">内容:</span>
                        <Input v-model="newEntry.content" placeholder="输入资料内容..."
                            class="h-8 text-sm flex-1 focus-visible:ring-emerald-500" @keyup.enter="handleAdd" />
                    </div>
                    <div class="flex justify-end gap-2 mt-1">
                        <Button variant="outline" size="sm" class="h-8" @click="isAdding = false">取消</Button>
                        <Button size="sm" class="h-8 bg-emerald-600 hover:bg-emerald-700"
                            @click="handleAdd">确认添加</Button>
                    </div>
                </div>
                <Button v-else variant="outline"
                    class="w-full border-dashed border-gray-300 py-6 text-gray-500 hover:text-emerald-600 hover:border-emerald-600"
                    @click="isAdding = true">
                    <Plus class="w-4 h-4 mr-2" />
                    添加资料记录
                </Button>
            </div>

            <DialogFooter class="hidden">
                <!-- Prevent default footer -->
            </DialogFooter>
        </DialogContent>
    </Dialog>
    
    <AvatarUploader 
        v-if="isAvatarUploaderOpen"
        :initial-image="userAvatar || undefined"
        title="设置个人头像"
        @update:image="(url) => userAvatar = url"
        @close="isAvatarUploaderOpen = false"
    />
</template>

<style scoped>
:deep(.lucide) {
    stroke-width: 1.5;
}
</style>
