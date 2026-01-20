<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getStaticUrl } from '@/api/base'
import { Search, LayoutGrid, ChevronDown, UserPlus, Sparkles, Plus } from 'lucide-vue-next'
import { MessageResponse } from '@/components/ai-elements/message'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { getFriendTemplates, getFriendTemplateTags, type FriendTemplate } from '@/api/friend-template'
import { useFriendStore } from '@/stores/friend'
import { useSessionStore } from '@/stores/session'
import { useToast } from '@/composables/useToast'
import { Loader2 } from 'lucide-vue-next'

import AssistantWizard from './AssistantWizard.vue'
import FriendComposeDialog from './FriendComposeDialog.vue'

const emit = defineEmits<{
  (e: 'back-chat'): void
}>()

const isElectron = Boolean(window.WeAgentChat?.windowControls)

const handleToggleMaximize = () => {
  if (!isElectron) return
  window.WeAgentChat?.windowControls?.toggleMaximize()
}

const handleHeaderContextMenu = (event: MouseEvent) => {
  if (!isElectron) return
  event.preventDefault()
  window.WeAgentChat?.windowControls?.showSystemMenu({
    x: event.screenX,
    y: event.screenY,
  })
}

const templates = ref<FriendTemplate[]>([])
const isLoading = ref(false)
const selectedTag = ref('全部')
const searchQuery = ref('')
const isDetailOpen = ref(false)
const activeTemplate = ref<FriendTemplate | null>(null)
const tagOptions = ref<string[]>([])
const tagsSeeded = ref(false)
const isWizardOpen = ref(false)
const isComposeOpen = ref(false)
const isCloning = ref(false)

const friendStore = useFriendStore()
const sessionStore = useSessionStore()
const toast = useToast()

let searchTimer: ReturnType<typeof setTimeout> | null = null

const fetchTemplates = async () => {
  isLoading.value = true
  const queryTag = selectedTag.value === '全部' ? undefined : selectedTag.value
  const queryText = searchQuery.value.trim()

  try {
    const data = await getFriendTemplates({
      page: 1,
      size: 60,
      tag: queryTag || undefined,
      q: queryText || undefined,
    })
    templates.value = data

    if (!tagsSeeded.value) {
      try {
        const allTags = await getFriendTemplateTags()
        tagOptions.value = allTags
        tagsSeeded.value = true
      } catch (err) {
        console.error('Failed to load tags', err)
        // Fallback to local extraction if endpoint fails
        const tagSet = new Set<string>()
        data.forEach((item) => {
          item.tags?.forEach((tag) => tagSet.add(tag))
        })
        tagOptions.value = Array.from(tagSet).sort((a, b) => a.localeCompare(b, 'zh-CN'))
        tagsSeeded.value = true
      }
    }
  } catch (error) {
    console.error('Failed to load friend templates', error)
  } finally {
    isLoading.value = false
  }
}

const openDetail = (template: FriendTemplate) => {
  activeTemplate.value = template
  isDetailOpen.value = true
}

const handleAddFriend = async () => {
  if (!activeTemplate.value || isCloning.value) return

  // 检查是否已添加过同名好友（防止重复添加同一模板）
  const existingFriend = friendStore.friends.find(
    f => f.name === activeTemplate.value!.name
  )
  if (existingFriend) {
    toast.info(`好友「${existingFriend.name}」已存在，已为你跳转`)
    isDetailOpen.value = false
    await sessionStore.selectFriend(existingFriend.id)
    emit('back-chat')
    return
  }

  isCloning.value = true
  try {
    const newFriend = await friendStore.cloneFromTemplate(activeTemplate.value.id)
    isDetailOpen.value = false
    toast.success(`好友「${newFriend.name}」添加成功`)
    // 选中新好友并跳转
    await sessionStore.selectFriend(newFriend.id)
    emit('back-chat')
  } catch (error) {
    console.error('Failed to add friend:', error)
    toast.error('添加好友失败，请稍后重试')
  } finally {
    isCloning.value = false
  }
}

const getAvatar = (template: FriendTemplate) => {
  if (template.avatar) {
    return getStaticUrl(template.avatar) || ''
  }
  return `https://api.dicebear.com/7.x/bottts/svg?seed=friend-${template.id}`
}

const displayTags = computed(() => ['全部', ...tagOptions.value])
const showAllTags = ref(false)
const tagPreviewCount = computed(() => (selectedTag.value === '全部' ? 18 : 17))
const visibleTags = computed(() => {
  if (showAllTags.value) return displayTags.value
  return displayTags.value.slice(0, tagPreviewCount.value)
})
const hasMoreTags = computed(() => displayTags.value.length > tagPreviewCount.value)

watch(selectedTag, () => {
  fetchTemplates()
})

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    fetchTemplates()
  }, 300)
})

onMounted(() => {
  fetchTemplates()
})
</script>

<template>
  <div class="friend-gallery">
    <header class="gallery-header" @dblclick="handleToggleMaximize" @contextmenu="handleHeaderContextMenu">
      <div class="gallery-header-inner">
        <div class="gallery-title">
          <button class="back-btn" @click="emit('back-chat')">返回</button>
          <LayoutGrid :size="18" />
          <span>好友库</span>
        </div>
        <div class="gallery-subtitle">探索更多 AI 角色，找到最合适的伙伴</div>
      </div>
    </header>

    <section class="gallery-toolbar">
      <div class="gallery-tabs">
        <div class="gallery-tabs-list" :class="{ expanded: showAllTags }">
          <button v-for="tag in visibleTags" :key="tag" class="tab-btn" :class="{ active: selectedTag === tag }"
            @click="selectedTag = tag">
            {{ tag }}
          </button>
        </div>
        <button v-if="hasMoreTags" class="tab-toggle" @click="showAllTags = !showAllTags">
          {{ showAllTags ? '收起' : '展开全部' }}
        </button>
      </div>

      <div class="toolbar-right">
        <div class="search-box">
          <Search :size="16" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索关键词或角色" class="search-input" />
        </div>

        <div class="gallery-actions">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button class="action-btn create-btn">
                <Plus :size="16" class="mr-2" />
                创建好友
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent class="create-menu" align="end">
              <DropdownMenuItem class="create-item" @click="isWizardOpen = true">
                <Sparkles :size="16" class="mr-2" />
                自动创建
              </DropdownMenuItem>
              <DropdownMenuItem class="create-item" @click="isComposeOpen = true">
                <UserPlus :size="16" class="mr-2" />
                手动创建
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </section>

    <section class="gallery-content">
      <div v-if="isLoading" class="gallery-grid">
        <div v-for="item in 8" :key="item" class="gallery-card skeleton">
          <div class="skeleton-avatar"></div>
          <div class="skeleton-line wide"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-tags">
            <span class="skeleton-pill"></span>
            <span class="skeleton-pill"></span>
          </div>
        </div>
      </div>

      <div v-else-if="templates.length === 0" class="empty-state">
        <div class="empty-illustration">
          <div class="bubble big"></div>
          <div class="bubble mid"></div>
          <div class="bubble small"></div>
          <div class="spark"></div>
        </div>
        <h3>暂无匹配的好友</h3>
        <p>可以尝试调整关键词，或创建你的专属 AI 伙伴。</p>
        <div class="empty-actions">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button class="empty-action create-btn">
                <Plus :size="16" class="mr-2" />
                创建好友
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent class="create-menu" align="center">
              <DropdownMenuItem class="create-item" @click="isWizardOpen = true">
                <Sparkles :size="16" class="mr-2" />
                自动创建
              </DropdownMenuItem>
              <DropdownMenuItem class="create-item" @click="isComposeOpen = true">
                <UserPlus :size="16" class="mr-2" />
                手动创建
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div v-else class="gallery-grid">
        <article v-for="template in templates" :key="template.id" class="gallery-card" @click="openDetail(template)">
          <div class="card-avatar">
            <img :src="getAvatar(template)" :alt="template.name" />
          </div>
          <div class="card-body">
            <div class="card-title">{{ template.name }}</div>
            <div class="card-description">{{ template.description }}</div>
            <div class="card-tags">
              <span v-for="tag in template.tags || []" :key="tag" class="tag-pill">
                {{ tag }}
              </span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <Dialog v-model:open="isDetailOpen">
      <DialogContent class="gallery-dialog">
        <DialogHeader>
          <DialogTitle>好友详情</DialogTitle>
        </DialogHeader>
        <div v-if="activeTemplate" class="sheet-body">
          <div class="sheet-content-scroll">
            <div class="sheet-hero">
              <div class="hero-avatar">
                <img :src="getAvatar(activeTemplate)" :alt="activeTemplate.name" />
              </div>
              <div class="hero-info">
                <h2>{{ activeTemplate.name }}</h2>
                <div class="hero-tags">
                  <span v-for="tag in activeTemplate.tags || []" :key="tag" class="tag-pill">
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>

            <div class="sheet-section">
              <div class="section-title">简介</div>
              <MessageResponse :content="activeTemplate.description" class="sheet-markdown" />
            </div>

            <div class="sheet-section">
              <Collapsible>
                <CollapsibleTrigger class="prompt-trigger">
                  <span>人格设定</span>
                  <ChevronDown :size="16" />
                </CollapsibleTrigger>
                <CollapsibleContent class="prompt-content">
                  <MessageResponse :content="activeTemplate.system_prompt" class="sheet-markdown" />
                </CollapsibleContent>
              </Collapsible>
            </div>
          </div>

          <div class="sheet-footer">
            <Button class="add-friend-btn" :disabled="isCloning" @click="handleAddFriend">
              <Loader2 v-if="isCloning" class="mr-2 h-4 w-4 animate-spin" />
              {{ isCloning ? '正在添加...' : '添加好友' }}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <AssistantWizard v-model:open="isWizardOpen" @success="emit('back-chat')" />
    <FriendComposeDialog v-model:open="isComposeOpen" mode="add" @success="emit('back-chat')" />
  </div>
</template>

<style scoped>
.friend-gallery {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(180deg, #f6f7f6 0%, #eef2ef 55%, #f1f1f1 100%);
  overflow: hidden;
}

.friend-gallery::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 8%, rgba(7, 193, 96, 0.08), transparent 38%),
    radial-gradient(circle at 88% 18%, rgba(0, 0, 0, 0.04), transparent 42%),
    radial-gradient(circle at 30% 90%, rgba(7, 193, 96, 0.06), transparent 45%);
  pointer-events: none;
  z-index: 0;
}

.friend-gallery>* {
  position: relative;
  z-index: 1;
}

.gallery-header {
  padding: 20px 130px 12px 24px;
  /* Right padding for global window controls */
  border-bottom: 1px solid #e5e8e5;
  background: linear-gradient(180deg, #ffffff 0%, #f7f9f7 100%);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.04);
}

.gallery-header-inner {
  -webkit-app-region: drag;
  display: flex;
  flex-direction: column;
}

.gallery-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #222;
}

.back-btn {
  -webkit-app-region: no-drag;
  display: none;
  background: transparent;
  border: none;
  font-size: 12px;
  color: #07c160;
  padding: 4px 6px;
  border-radius: 6px;
  cursor: pointer;
}

.back-btn:hover {
  background: rgba(7, 193, 96, 0.1);
}

.gallery-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: #777;
}

.gallery-toolbar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 24px;
  background: rgba(247, 248, 247, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(6px);
}

.gallery-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  width: 100%;
  align-items: flex-start;
}

.gallery-tabs-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  max-height: 34px;
  /* Increase slightly to prevent cut-off */
  overflow: hidden;
  flex: 1;
}

.gallery-tabs-list.expanded {
  flex-wrap: wrap;
  max-height: none;
  overflow: visible;
}

.tab-btn {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 14px;
  background: #f0f2f0;
  border: none;
  border-radius: 999px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.tab-btn.active,
.tab-btn:hover {
  background: #07c160;
  color: #fff;
}

.tab-toggle {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 14px;
  background: #fff;
  border: 1px dashed rgba(7, 193, 96, 0.4);
  border-radius: 999px;
  font-size: 13px;
  color: #049b4f;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.tab-toggle:hover {
  background: rgba(7, 193, 96, 0.08);
  border-color: rgba(7, 193, 96, 0.7);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  justify-content: flex-start;
}

.gallery-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  height: 32px;
  border-radius: 999px;
  font-size: 13px;
  padding: 0 16px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
}

.action-btn.create-btn {
  background: linear-gradient(135deg, #07c160 0%, #18d471 100%);
  color: #fff;
  border: none;
}

.action-btn.create-btn:hover {
  background: linear-gradient(135deg, #06ad56 0%, #13c566 100%);
}

.search-box {
  height: 32px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  background: #eef1ee;
  border-radius: 999px;
  /* Use rounded pill shape to match buttons if desired, but user likely wants consistent style. Let's stick to 8px or make it 999px for consistency */
  border-radius: 18px;
  /* Slightly rounder to match the "soft" feel */
  flex: 0 1 240px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.search-icon {
  color: #888;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #333;
  outline: none;
}

.gallery-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 24px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.gallery-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  gap: 12px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.gallery-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
}

.card-avatar {
  width: 54px;
  height: 54px;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #f2f4f2, #e6efe8);
  flex-shrink: 0;
  border: 1px solid rgba(7, 193, 96, 0.18);
}

.card-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #222;
}

.card-description {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-pill {
  padding: 2px 8px;
  background: rgba(7, 193, 96, 0.12);
  color: #07c160;
  border-radius: 999px;
  font-size: 11px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  padding: 60px 20px;
  color: #666;
}

.empty-illustration {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 12px;
}

.bubble {
  position: absolute;
  border-radius: 50%;
  background: rgba(7, 193, 96, 0.12);
}

.bubble.big {
  width: 90px;
  height: 90px;
  left: 10px;
  top: 10px;
}

.bubble.mid {
  width: 50px;
  height: 50px;
  right: 0;
  top: 20px;
}

.bubble.small {
  width: 30px;
  height: 30px;
  left: 0;
  bottom: 10px;
}

.spark {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #07c160;
  border-radius: 4px;
  right: 18px;
  bottom: 22px;
  transform: rotate(20deg);
}

.empty-actions {
  margin-top: 8px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

.empty-action {
  border-radius: 999px;
  height: 34px;
  font-size: 12px;
}

.empty-action.create-btn {
  background: linear-gradient(135deg, #07c160 0%, #18d471 100%);
  color: #fff;
}

.empty-action.create-btn:hover {
  background: linear-gradient(135deg, #06ad56 0%, #13c566 100%);
}

:global(.create-menu) {
  min-width: 160px;
  border-radius: 12px;
  padding: 6px;
}

:global(.create-item) {
  gap: 8px;
  border-radius: 8px;
}

:global(.create-item[data-highlighted]) {
  background: rgba(7, 193, 96, 0.12);
  color: #047a40;
}

.skeleton {
  cursor: default;
  box-shadow: none;
}

.skeleton-avatar {
  width: 54px;
  height: 54px;
  border-radius: 12px;
  background: #ececec;
}

.skeleton-line {
  height: 10px;
  background: #ededed;
  border-radius: 999px;
  margin-top: 8px;
  width: 70%;
}

.skeleton-line.wide {
  width: 90%;
}

.skeleton-tags {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.skeleton-pill {
  width: 40px;
  height: 12px;
  background: #e9e9e9;
  border-radius: 999px;
}

/* Dialog styles need :global() because DialogPortal renders outside this component */
:global(.gallery-dialog) {
  max-width: min(560px, 92vw) !important;
  max-height: 85vh !important;
  background: #f9f9f9 !important;
  border-radius: 16px !important;
  padding: 0 !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}

/* Fix DialogHeader positioning */
:global(.gallery-dialog > div:first-child) {
  padding: 20px 20px 10px;
  flex-shrink: 0;
}

:global(.gallery-dialog > div:first-child h2) {
  font-size: 18px;
  font-weight: 600;
  color: #222;
}

:global(.gallery-dialog .sheet-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

:global(.gallery-dialog .sheet-content-scroll) {
  flex: 1;
  overflow-y: auto;
  padding: 10px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
}

:global(.gallery-dialog .sheet-content-scroll::-webkit-scrollbar) {
  width: 6px;
}

:global(.gallery-dialog .sheet-content-scroll::-webkit-scrollbar-thumb) {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 999px;
}

:global(.gallery-dialog .sheet-hero) {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.06);
}

:global(.gallery-dialog .hero-avatar) {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  overflow: hidden;
  background: #f0f0f0;
}

:global(.gallery-dialog .hero-avatar img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

:global(.gallery-dialog .hero-info h2) {
  font-size: 18px;
  font-weight: 600;
  color: #222;
  margin-bottom: 6px;
}

:global(.gallery-dialog .hero-tags) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:global(.gallery-dialog .sheet-section) {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.05);
}

:global(.gallery-dialog .section-title) {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

:global(.gallery-dialog .sheet-markdown) {
  font-size: 13px;
  color: #444;
  line-height: 1.6;
}

:global(.gallery-dialog .prompt-trigger) {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f3f3f3;
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: #333;
  cursor: pointer;
}

:global(.gallery-dialog .prompt-content) {
  margin-top: 10px;
}

:global(.gallery-dialog .sheet-footer) {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #eee;
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}

:global(.gallery-dialog .add-friend-btn) {
  background: #07c160;
}

:global(.gallery-dialog .add-friend-btn:hover) {
  background: #06ad56;
}

@media (max-width: 640px) {
  .back-btn {
    display: inline-flex;
  }

  .toolbar-right {
    flex: 1 1 100%;
    justify-content: space-between;
  }

  .gallery-actions {
    width: 100%;
    justify-content: space-between;
  }

  .action-btn {
    flex: 1;
    justify-content: center;
  }

  .gallery-toolbar {
    padding: 12px 14px 8px;
  }

  .gallery-content {
    padding: 14px;
  }
}
</style>
