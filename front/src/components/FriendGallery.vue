<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Search, LayoutGrid, ChevronDown, Plus } from 'lucide-vue-next'
import { MessageResponse } from '@/components/ai-elements/message'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { getFriendTemplates, type FriendTemplate } from '@/api/friend-template'
import { useFriendStore } from '@/stores/friend'
import { useSessionStore } from '@/stores/session'
import { useToast } from '@/composables/useToast'
import { Loader2 } from 'lucide-vue-next'

const emit = defineEmits<{
  (e: 'back-chat'): void
}>()

const templates = ref<FriendTemplate[]>([])
const isLoading = ref(false)
const selectedTag = ref('全部')
const searchQuery = ref('')
const isDetailOpen = ref(false)
const activeTemplate = ref<FriendTemplate | null>(null)
const tagOptions = ref<string[]>([])
const tagsSeeded = ref(false)
const isNoticeOpen = ref(false)
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
      const tagSet = new Set<string>()
      data.forEach((item) => {
        item.tags?.forEach((tag) => tagSet.add(tag))
      })
      tagOptions.value = Array.from(tagSet).sort((a, b) => a.localeCompare(b, 'zh-CN'))
      tagsSeeded.value = true
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
  return template.avatar || `https://api.dicebear.com/7.x/bottts/svg?seed=friend-${template.id}`
}

const displayTags = computed(() => ['全部', ...tagOptions.value])

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
    <header class="gallery-header">
      <div class="gallery-title">
        <button class="back-btn" @click="emit('back-chat')">返回</button>
        <LayoutGrid :size="18" />
        <span>好友库</span>
      </div>
      <div class="gallery-subtitle">探索更多 AI 角色，找到最合适的伙伴</div>
    </header>

    <section class="gallery-toolbar">
      <div class="gallery-tabs">
        <button
          v-for="tag in displayTags"
          :key="tag"
          class="tab-btn"
          :class="{ active: selectedTag === tag }"
          @click="selectedTag = tag"
        >
          {{ tag }}
        </button>
      </div>

      <div class="search-box">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索关键词或角色"
          class="search-input"
        />
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
        <Button class="empty-action" @click="isNoticeOpen = true">
          <Plus :size="16" class="mr-2" />
          AI 创建
        </Button>
      </div>

      <div v-else class="gallery-grid">
        <article
          v-for="template in templates"
          :key="template.id"
          class="gallery-card"
          @click="openDetail(template)"
        >
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

          <div class="sheet-footer">
            <Button class="add-friend-btn" :disabled="isCloning" @click="handleAddFriend">
              <Loader2 v-if="isCloning" class="mr-2 h-4 w-4 animate-spin" />
              {{ isCloning ? '正在添加...' : '添加好友' }}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isNoticeOpen">
      <DialogContent class="sm:max-w-[360px]">
        <DialogHeader>
          <DialogTitle>功能开发中</DialogTitle>
        </DialogHeader>
        <div class="text-sm text-gray-600">
          添加好友与 AI 创建将在下一阶段开放。
        </div>
        <DialogFooter>
          <Button @click="isNoticeOpen = false">知道了</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.friend-gallery {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(180deg, #f7f7f7 0%, #efefef 100%);
  overflow: hidden;
}

.gallery-header {
  padding: 20px 24px 12px;
  border-bottom: 1px solid #e3e3e3;
  background: #fdfdfd;
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
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 20px 8px;
  background: #f5f5f5;
}

.gallery-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  flex: 1 1 320px;
}

.gallery-tabs::-webkit-scrollbar {
  height: 4px;
}

.gallery-tabs::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 999px;
}

.tab-btn {
  padding: 6px 14px;
  background: #e8e8e8;
  border: none;
  border-radius: 999px;
  font-size: 12px;
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

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #e6e6e6;
  border-radius: 8px;
  flex: 0 1 240px;
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
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
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
  background: #f4f4f4;
  flex-shrink: 0;
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

.empty-action {
  margin-top: 8px;
  background: #07c160;
}

.empty-action:hover {
  background: #06ad56;
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

.gallery-dialog {
  max-width: min(560px, 92vw);
  background: #f9f9f9;
  border-radius: 16px;
  padding: 20px;
}

.sheet-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 8px;
}

.sheet-hero {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.06);
}

.hero-avatar {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  overflow: hidden;
  background: #f0f0f0;
}

.hero-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-info h2 {
  font-size: 18px;
  font-weight: 600;
  color: #222;
  margin-bottom: 6px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sheet-section {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.05);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

.sheet-markdown {
  font-size: 13px;
  color: #444;
  line-height: 1.6;
}

.prompt-trigger {
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

.prompt-content {
  margin-top: 10px;
}

.sheet-footer {
  display: flex;
  justify-content: flex-end;
}

.add-friend-btn {
  background: #07c160;
}

.add-friend-btn:hover {
  background: #06ad56;
}

@media (max-width: 640px) {
  .back-btn {
    display: inline-flex;
  }

  .gallery-toolbar {
    padding: 12px 14px 8px;
  }

  .gallery-content {
    padding: 14px;
  }
}
</style>
