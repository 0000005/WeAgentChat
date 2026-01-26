<script setup lang="ts">
import { ref, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useGroupStore } from '@/stores/group'
import { useSettingsStore } from '@/stores/settings'
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
} from '@/components/ui/sheet'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import {
    Plus,
    Minus,
    Camera,
    Check,
    X,
    ChevronRight,
    Loader2
} from 'lucide-vue-next'
import { getStaticUrl } from '@/api/base'
import GroupMemberSelector from '@/components/common/GroupMemberSelector.vue'
import AvatarUploader from '@/components/common/AvatarUploader.vue'
import GroupAvatar from '@/components/common/GroupAvatar.vue'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
    open: boolean
}>()

const emit = defineEmits<{
    (e: 'update:open', value: boolean): void
}>()

const sessionStore = useSessionStore()
const groupStore = useGroupStore()
const settingsStore = useSettingsStore()
const toast = useToast()

const groupInfo = ref<any>(null)

const getMemberAvatarUrl = (member: any) => {
    // 如果是当前用户，优先使用 settingsStore 中的头像
    if (member.member_type === 'user') {
        return getStaticUrl(settingsStore.userAvatar) || 'default_avatar.svg'
    }
    // 其他成员（AI）
    return member.avatar ? getStaticUrl(member.avatar) : ''
}

// 群组管理状态
const showMemberSelector = ref(false)
const memberSelectorMode = ref<'invite' | 'remove'>('invite')
const showAvatarUploader = ref(false)
const isEditingGroupName = ref(false)
const editingGroupName = ref('')
const isUpdatingGroup = ref(false)
const showExitConfirm = ref(false)
const isExiting = ref(false)
const showClearConfirm = ref(false)
const isClearing = ref(false)

watch([() => props.open, () => sessionStore.currentGroupId], async ([open, groupId]) => {
    if (open && groupId) {
        try {
            groupInfo.value = await groupStore.fetchGroupDetails(groupId)
        } catch (e) {
            console.error('Failed to fetch group info:', e)
        }
    }
    // 重置编辑状态
    if (!open) {
        isEditingGroupName.value = false
        showMemberSelector.value = false
        showAvatarUploader.value = false
        showExitConfirm.value = false
        showClearConfirm.value = false
    }
})

// 打开成员选择器
const openMemberSelector = (mode: 'invite' | 'remove') => {
    memberSelectorMode.value = mode
    showMemberSelector.value = true
}

// 处理成员选择确认
const handleMemberConfirm = async (memberIds: string[]) => {
    if (!groupInfo.value) return

    try {
        if (memberSelectorMode.value === 'invite') {
            await groupStore.inviteMembers(groupInfo.value.id, memberIds)
            toast.success(`成功邀请 ${memberIds.length} 位成员`)
        } else {
            // 逐个移除成员
            for (const memberId of memberIds) {
                await groupStore.removeMember(groupInfo.value.id, memberId)
            }
            toast.success(`成功移除 ${memberIds.length} 位成员`)
        }
        // 刷新群组信息
        groupInfo.value = await groupStore.fetchGroupDetails(groupInfo.value.id)
    } catch (e: any) {
        toast.error(e.message || '操作失败')
    } finally {
        showMemberSelector.value = false
    }
}

// 开始编辑群名称
const startEditGroupName = () => {
    if (groupInfo.value) {
        editingGroupName.value = groupInfo.value.name
        isEditingGroupName.value = true
    }
}

// 保存群名称
const saveGroupName = async () => {
    if (!groupInfo.value || !editingGroupName.value.trim()) return

    isUpdatingGroup.value = true
    try {
        await groupStore.updateGroupSettings(groupInfo.value.id, { name: editingGroupName.value.trim() })
        groupInfo.value.name = editingGroupName.value.trim()
        isEditingGroupName.value = false
        toast.success('群名称已更新')
    } catch (e: any) {
        toast.error(e.message || '更新失败')
    } finally {
        isUpdatingGroup.value = false
    }
}

// 取消编辑群名称
const cancelEditGroupName = () => {
    isEditingGroupName.value = false
    editingGroupName.value = ''
}

// 处理群头像更新
const handleGroupAvatarUpdate = async (url: string) => {
    if (!groupInfo.value) return

    try {
        await groupStore.updateGroupSettings(groupInfo.value.id, { avatar: url })
        groupInfo.value.avatar = url
        showAvatarUploader.value = false
        toast.success('群头像已更新')
    } catch (e: any) {
        toast.error(e.message || '更新失败')
    }
}

// 退出群聊确认
const confirmExitGroup = async () => {
    if (!groupInfo.value) return

    isExiting.value = true
    try {
        await groupStore.exitGroup(groupInfo.value.id)
        toast.success('已退出群聊')
        showExitConfirm.value = false
        handleClose()
    } catch (e: any) {
        toast.error(e.message || '退出失败')
    } finally {
        isExiting.value = false
    }
}

// 清空聊天记录确认
const confirmClearHistory = async () => {
    if (!groupInfo.value) return

    isClearing.value = true
    try {
        await sessionStore.clearGroupHistory(groupInfo.value.id)
        toast.success('聊天记录已清空')
        showClearConfirm.value = false
    } catch (e: any) {
        toast.error(e.message || '清空失败')
    } finally {
        isClearing.value = false
    }
}

const handleClose = () => {
    emit('update:open', false)
}


</script>

<template>
    <Sheet :open="open" @update:open="handleClose">
        <SheetContent side="right" class="drawer-content w-[360px] sm:w-[360px] p-0 flex flex-col">
            <!-- Header -->
            <SheetHeader class="drawer-header header-white">
                <div class="friend-info">
                    <div class="friend-avatar cursor-pointer group relative" @click="showAvatarUploader = true">
                        <GroupAvatar :members="groupInfo?.members" :avatar="groupInfo?.avatar" size="40" />
                        <!-- Group Avatar Edit Overlay -->
                        <div
                            class="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded">
                            <Camera :size="20" class="text-white" />
                        </div>
                    </div>
                    <div class="flex flex-col">
                        <SheetTitle class="friend-name">{{ groupInfo?.name || '群聊' }}</SheetTitle>
                        <span v-if="groupInfo" class="text-xs text-gray-500">{{ groupInfo.members?.length || 0 }}
                            名成员</span>
                    </div>
                </div>
            </SheetHeader>

            <!-- Main Menu View -->
            <div class="menu-list overflow-y-auto flex-1">
                <!-- Group Member Grid -->
                <div v-if="groupInfo" class="group-members-section p-4 border-b bg-white">
                    <div class="members-grid grid grid-cols-4 gap-y-4">
                        <!-- Members -->
                        <div v-for="member in groupInfo.members" :key="member.member_id"
                            class="member-item flex flex-col items-center gap-1">
                            <div class="member-avatar w-12 h-12 rounded bg-gray-100 overflow-hidden">
                                <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)"
                                    class="w-full h-full object-cover" />
                                <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
                                    <span v-if="member.name">{{ member.name[0] }}</span>
                                </div>
                            </div>
                            <span class="text-[10px] text-gray-500 truncate w-full text-center">{{ member.name }}</span>
                        </div>
                        <!-- Add/Remove Buttons -->
                        <button class="member-item flex flex-col items-center gap-1"
                            @click="openMemberSelector('invite')">
                            <div
                                class="w-12 h-12 rounded border-2 border-dashed border-gray-200 flex items-center justify-center text-gray-300 hover:border-gray-400 hover:text-gray-400 transition-colors">
                                <Plus :size="24" />
                            </div>
                            <span class="text-[10px] text-gray-400">添加</span>
                        </button>
                        <button class="member-item flex flex-col items-center gap-1"
                            @click="openMemberSelector('remove')">
                            <div
                                class="w-12 h-12 rounded border-2 border-dashed border-gray-200 flex items-center justify-center text-gray-300 hover:border-gray-400 hover:text-gray-400 transition-colors">
                                <Minus :size="24" />
                            </div>
                            <span class="text-[10px] text-gray-400">移除</span>
                        </button>
                    </div>
                </div>

                <!-- Group Specific Settings -->
                <div v-if="groupInfo" class="group-settings mt-2">
                    <div class="menu-item flex justify-between items-center group/edit"
                        @click="!isEditingGroupName && startEditGroupName()">
                        <span class="menu-label">群聊名称</span>
                        <div class="flex-1 flex justify-end items-center gap-2 overflow-hidden">
                            <template v-if="!isEditingGroupName">
                                <span class="text-sm text-gray-400 truncate max-w-[180px]">{{ groupInfo.name }}</span>
                                <ChevronRight :size="16" class="text-gray-300" />
                            </template>
                            <template v-else>
                                <Input v-model="editingGroupName"
                                    class="h-8 py-0 px-2 text-sm focus-visible:ring-emerald-500" @click.stop
                                    @keyup.enter="saveGroupName" autofocus />
                                <div class="flex gap-1 shrink-0">
                                    <button @click.stop="saveGroupName"
                                        class="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                                        :disabled="isUpdatingGroup">
                                        <Loader2 v-if="isUpdatingGroup" :size="14" class="animate-spin" />
                                        <Check v-else :size="14" />
                                    </button>
                                    <button @click.stop="cancelEditGroupName"
                                        class="p-1 text-gray-400 hover:bg-gray-100 rounded">
                                        <X :size="14" />
                                    </button>
                                </div>
                            </template>
                        </div>
                    </div>
                    <div class="menu-item flex justify-between items-center">
                        <span class="menu-label">自动回复</span>
                        <Switch :model-value="groupInfo.auto_reply"
                            @update:model-value="(val) => groupStore.updateGroupSettings(groupInfo.id, { auto_reply: val }).then(updated => groupInfo = { ...groupInfo, auto_reply: updated.auto_reply })" />
                    </div>
                    <div class="mt-8 px-4 pb-2">
                        <Button variant="outline" class="w-full text-gray-600 border-gray-200 hover:bg-gray-50"
                            @click="showClearConfirm = true">清空聊天记录</Button>
                    </div>
                    <div class="px-4 pb-8">
                        <Button variant="destructive" class="w-full bg-[#fa5151] hover:bg-[#d93a3a]"
                            @click="showExitConfirm = true">退出群聊</Button>
                    </div>
                </div>
            </div>
        </SheetContent>
    </Sheet>

    <!-- Group Management Dialogs -->
    <GroupMemberSelector v-if="groupInfo" v-model:open="showMemberSelector" :mode="memberSelectorMode"
        :existing-members="groupInfo.members" @confirm="handleMemberConfirm" />

    <AvatarUploader v-if="showAvatarUploader && groupInfo"
        :initial-image="groupInfo.avatar ? getStaticUrl(groupInfo.avatar) : ''" title="上传群头像"
        @close="showAvatarUploader = false" @update:image="handleGroupAvatarUpdate" />

    <!-- Clear History Confirmation -->
    <Dialog v-model:open="showClearConfirm">
        <DialogContent class="sm:max-w-[400px]">
            <DialogHeader>
                <DialogTitle>清空聊天记录</DialogTitle>
                <DialogDescription class="mt-2 text-red-500 font-medium">
                    确定要清空该群聊的所有聊天记录吗？此操作不可撤销。
                </DialogDescription>
            </DialogHeader>
            <DialogFooter class="gap-2 sm:gap-0 mt-4">
                <Button variant="outline" @click="showClearConfirm = false" :disabled="isClearing">取消</Button>
                <Button variant="destructive" @click="confirmClearHistory" :disabled="isClearing"
                    class="bg-[#fa5151] hover:bg-[#d93a3a]">
                    <Loader2 v-if="isClearing" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isClearing ? '清空中...' : '确认清空' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>

    <!-- Exit Group Confirmation -->
    <Dialog v-model:open="showExitConfirm">
        <DialogContent class="sm:max-w-[400px]">
            <DialogHeader>
                <DialogTitle>退出群聊</DialogTitle>
                <DialogDescription class="mt-2">
                    退出后，你将不在该群聊中，且无法看到该群聊的历史记录。
                </DialogDescription>
            </DialogHeader>
            <DialogFooter class="gap-2 sm:gap-0 mt-4">
                <Button variant="outline" @click="showExitConfirm = false" :disabled="isExiting">取消</Button>
                <Button variant="destructive" @click="confirmExitGroup" :disabled="isExiting"
                    class="bg-[#fa5151] hover:bg-[#d93a3a]">
                    <Loader2 v-if="isExiting" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isExiting ? '退出中...' : '确认退出' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

<style scoped>
/* 引入共享样式 */
@import '@/styles/drawer-common.css';

/* 抽屉内容容器 - scoped 样式覆盖 */
:deep([data-radix-vue-dialog-content]) {
    max-width: 360px !important;
    -webkit-app-region: no-drag;
}

/* Header 样式 */
.drawer-content {
    -webkit-app-region: no-drag;
}

/* Override default sheet styles */
:deep(.sheet-content) {
    padding: 0 !important;
}

/* 移动端适配 */
@media (max-width: 640px) {
    :deep([data-radix-vue-dialog-content]) {
        max-width: 100% !important;
        width: 100% !important;
    }
}
</style>
