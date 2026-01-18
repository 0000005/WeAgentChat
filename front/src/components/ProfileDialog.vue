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

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useMemoryStore } from '@/stores/memory'
import { Plus, Trash2, Edit2, Check, X, Loader2, Camera, Info } from 'lucide-vue-next'
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
const addingTopic = ref<string | null>(null) // Track which topic is being added to
const newEntryContent = ref('')
const editingId = ref<string | null>(null)
const editingContent = ref('')
const isAvatarUploaderOpen = ref(false)
const settingsStore = useSettingsStore()
const isAddingCategory = ref(false)
const newCategoryName = ref('')
const newCategoryDescription = ref('')

// Confirmation Dialog State
const confirmDialog = ref({
    open: false,
    title: '',
    message: '',
    onConfirm: () => { }
})

const showConfirmDialog = (title: string, message: string, onConfirm: () => void) => {
    confirmDialog.value = {
        open: true,
        title,
        message,
        onConfirm
    }
}

const handleConfirm = () => {
    confirmDialog.value.onConfirm()
    confirmDialog.value.open = false
}

const handleCancel = () => {
    confirmDialog.value.open = false
}

const userAvatar = computed({
    get: () => settingsStore.userAvatar,
    set: (val) => settingsStore.saveUserSettings(val)
})

const userAvatarDisplayUrl = computed(() =>
    getStaticUrl(settingsStore.userAvatar) || '/default_avatar.svg'
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
}

const handleAddToTopic = async (topic: string) => {
    if (!newEntryContent.value.trim()) return
    try {
        await memoryStore.upsertProfile(null, newEntryContent.value, { topic })
        newEntryContent.value = ''
        addingTopic.value = null
    } catch (error) {
        console.error('Failed to add profile:', error)
    }
}

const startAddingToTopic = (topic: string) => {
    addingTopic.value = topic
    newEntryContent.value = ''
}

const cancelAddingToTopic = () => {
    addingTopic.value = null
    newEntryContent.value = ''
}

const handleAddCategory = async () => {
    if (!newCategoryName.value.trim() || !newCategoryDescription.value.trim()) return
    memoryStore.profileConfig.topics.push({
        topic: newCategoryName.value.trim(),
        description: newCategoryDescription.value.trim()
    })
    await memoryStore.saveConfig()
    newCategoryName.value = ''
    newCategoryDescription.value = ''
    isAddingCategory.value = false
}

const handleRemoveCategory = async (index: number) => {
    const topic = memoryStore.profileConfig.topics[index]
    // Find all profiles under this topic
    const profilesInTopic = memoryStore.profiles.filter(
        p => p.attributes.topic === topic.topic
    )
    const profileCount = profilesInTopic.length

    const message = profileCount > 0
        ? `确定要删除分类「${topic.topic}」吗？\n\n该分类下有 ${profileCount} 条资料记录将被一并删除，此操作不可撤销。`
        : `确定要删除分类「${topic.topic}」吗？`

    showConfirmDialog(
        '删除分类',
        message,
        async () => {
            // 1. Delete all profiles under this topic first
            if (profileCount > 0) {
                const profileIds = profilesInTopic.map(p => p.id)
                await memoryStore.removeProfiles(profileIds)
            }
            // 2. Remove the topic from config
            memoryStore.profileConfig.topics.splice(index, 1)
            await memoryStore.saveConfig()
            // 3. Refresh profiles list
            await memoryStore.fetchProfiles()
        }
    )
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
    showConfirmDialog(
        '删除资料',
        '确定要删除这条资料记录吗？',
        async () => {
            try {
                await memoryStore.removeProfile(id)
            } catch (error) {
                console.error('Failed to delete profile:', error)
            }
        }
    )
}

// Custom directive for auto-focus on input
const vFocus = {
    mounted: (el: HTMLElement) => el.focus()
}
</script>

<template>
    <Dialog :open="open" @update:open="emit('update:open', $event)">
        <DialogContent
            class="max-w-2xl h-[80vh] flex flex-col p-0 overflow-hidden rounded-2xl border border-[#e6e6e6] bg-[linear-gradient(180deg,#f7f7f7_0%,#f0f1f3_100%)] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.35)]">
            <DialogHeader class="p-3 bg-white/90 backdrop-blur border-b border-[#ededed] shrink-0">
                <DialogTitle class="text-base font-semibold text-center text-[#111] tracking-wide">个人资料</DialogTitle>
            </DialogHeader>

            <!-- Avatar Section -->
            <div class="flex flex-col items-center py-4 bg-[linear-gradient(180deg,#ffffff_0%,#f7f7f7_100%)] border-b border-[#ededed] shrink-0">
                <div class="relative group cursor-pointer" @click="isAvatarUploaderOpen = true">
                    <img :src="userAvatarDisplayUrl"
                        class="w-24 h-24 rounded-xl object-cover border border-[#e5e7eb] shadow-[0_8px_20px_-12px_rgba(0,0,0,0.35)] bg-gray-50 ring-2 ring-[#07c160]/20" />
                    <div
                        class="absolute inset-0 bg-black/35 rounded-xl opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-[2px]">
                        <Camera class="text-white w-7 h-7" stroke-width="1.5" />
                    </div>
                </div>
                <div class="mt-2 text-xs text-gray-500">点击更换头像</div>
            </div>

            <!-- Tip Message -->
            <div class="px-6 py-2 shrink-0 bg-[#f8fff9] border-b border-[#e7f7ed]">
                <div class="flex items-center gap-2 text-[#07c160]/90">
                    <Info class="w-3.5 h-3.5" />
                    <p class="text-[11px] font-medium">
                        提示：个人资料由 AI 随聊天进程自动更新，无需手动维护。
                    </p>
                </div>
            </div>


            <ScrollArea class="flex-1 p-3">
                <div class="space-y-4">
                    <div v-if="memoryStore.isLoading && memoryStore.profiles.length === 0"
                        class="flex justify-center py-8">
                        <Loader2 class="w-8 h-8 animate-spin text-gray-400" />
                    </div>

                    <template v-else>
                        <Card v-for="(topic, index) in memoryStore.profileConfig.topics" :key="topic.topic"
                            class="border border-[#ebecef] bg-white shadow-[0_10px_24px_-16px_rgba(0,0,0,0.35)] overflow-hidden mb-3 rounded-xl">
                            <CardHeader class="bg-[#fafafa] py-2 px-3 border-b border-[#efefef]">
                                <CardTitle
                                    class="text-sm font-semibold text-[#2b2f33] flex items-center justify-between">
                                    <span>{{ topic.topic }}</span>
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs font-normal text-gray-400 mr-2">{{ topic.description
                                        }}</span>
                                        <Button size="icon" variant="ghost"
                                            class="h-7 w-7 text-[#07c160] hover:text-[#06ad55] hover:bg-[#e9f8ef]"
                                            @click="startAddingToTopic(topic.topic)">
                                            <Plus class="h-4 w-4" />
                                        </Button>
                                        <Button size="icon" variant="ghost"
                                            class="h-7 w-7 text-gray-400 hover:text-red-600 hover:bg-red-50"
                                            @click="handleRemoveCategory(index)">
                                            <Trash2 class="h-4 w-4" />
                                        </Button>
                                    </div>
                                </CardTitle>
                            </CardHeader>
                            <CardContent class="p-0 bg-white">
                                <!-- Add new entry form for this topic -->
                                <div v-if="addingTopic === topic.topic"
                                    class="p-2.5 border-b border-gray-100 bg-[#f6f7f8]">
                                    <div class="flex items-center gap-2">
                                        <Input v-model="newEntryContent" placeholder="输入资料内容..."
                                            class="h-8 text-sm flex-1 bg-white focus-visible:ring-[#07c160]"
                                            @keyup.enter="handleAddToTopic(topic.topic)"
                                            @keyup.esc="cancelAddingToTopic" v-focus />
                                        <Button size="icon" variant="ghost" class="h-8 w-8 text-[#07c160]"
                                            @click="handleAddToTopic(topic.topic)">
                                            <Check class="h-4 w-4" />
                                        </Button>
                                        <Button size="icon" variant="ghost" class="h-8 w-8 text-gray-400"
                                            @click="cancelAddingToTopic">
                                            <X class="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                                <div v-if="memoryStore.groupedProfiles[topic.topic]?.length === 0 && addingTopic !== topic.topic"
                                    class="p-4 text-center text-sm text-gray-400">
                                    暂无记录
                                </div>
                                <div v-else class="divide-y divide-gray-100">
                                    <div v-for="profile in memoryStore.groupedProfiles[topic.topic]" :key="profile.id"
                                        class="group flex items-start gap-3 p-2.5 hover:bg-[#f7f8f9] transition-colors">
                                        <div class="flex-1">
                                            <div v-if="editingId === profile.id" class="flex items-center gap-2">
                                                <Input v-model="editingContent"
                                                    class="h-8 text-sm bg-white focus-visible:ring-[#07c160]"
                                                    @keyup.enter="saveEdit(profile.id, topic.topic)"
                                                    @keyup.esc="cancelEdit" v-focus />
                                                <Button size="icon" variant="ghost" class="h-8 w-8 text-[#07c160]"
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
                                                class="h-8 w-8 text-gray-400 hover:text-[#07c160]"
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

            <div class="p-3 bg-white border-t border-[#ededed] shrink-0">
                <div v-if="isAddingCategory"
                    class="flex flex-col gap-2.5 p-3 bg-[#f7f8f9] rounded-xl border border-[#e6e8eb]">
                    <div class="grid gap-2">
                        <label class="text-xs font-medium text-gray-500">分类名称 *</label>
                        <Input v-model="newCategoryName" placeholder="例如：兴趣爱好"
                            class="h-8 text-sm bg-white focus-visible:ring-[#07c160]" />
                    </div>
                    <div class="grid gap-2">
                        <label class="text-xs font-medium text-gray-500">引导说明 *</label>
                        <Input v-model="newCategoryDescription" placeholder="例如：喜欢的事物、常去的地点等"
                            class="h-8 text-sm bg-white focus-visible:ring-[#07c160]" @keyup.enter="handleAddCategory" />
                    </div>
                    <div class="flex justify-end gap-2 mt-1">
                        <Button variant="outline" size="sm" class="h-8"
                            @click="isAddingCategory = false; newCategoryName = ''; newCategoryDescription = ''">取消</Button>
                        <Button size="sm" class="h-8 bg-[#07c160] hover:bg-[#06ad55]"
                            :disabled="!newCategoryName.trim() || !newCategoryDescription.trim()"
                            @click="handleAddCategory">确认</Button>
                    </div>
                </div>
                <Button v-else variant="outline"
                    class="w-full border-dashed border-gray-300 py-6 text-gray-500 hover:text-[#07c160] hover:border-[#07c160]"
                    @click="isAddingCategory = true">
                    <Plus class="w-4 h-4 mr-2" />
                    新增分类
                </Button>
            </div>

            <DialogFooter class="hidden">
                <!-- Prevent default footer -->
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Confirmation Dialog -->
    <Dialog :open="confirmDialog.open" @update:open="(val) => confirmDialog.open = val">
        <DialogContent class="sm:max-w-md rounded-2xl border border-[#e6e6e6] shadow-[0_18px_50px_-20px_rgba(0,0,0,0.35)]">
            <DialogHeader class="pb-2">
                <DialogTitle class="text-base font-semibold text-[#111]">{{ confirmDialog.title }}</DialogTitle>
            </DialogHeader>
            <div class="py-4">
                <p class="text-sm text-gray-600 whitespace-pre-line">{{ confirmDialog.message }}</p>
            </div>
            <DialogFooter class="flex gap-2">
                <Button variant="outline" @click="handleCancel">取消</Button>
                <Button class="bg-red-600 hover:bg-red-700" @click="handleConfirm">确认删除</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <AvatarUploader v-if="isAvatarUploaderOpen" :initial-image="userAvatar || undefined" title="设置个人头像"
        @update:image="(url) => userAvatar = url" @close="isAvatarUploaderOpen = false" />
</template>

<style scoped>
:deep(.lucide) {
    stroke-width: 1.5;
}
</style>
