<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import html2canvas from 'html2canvas'
import type { ExportMessage } from '@/types/export'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Download, Loader2 } from 'lucide-vue-next'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  open: boolean
  messages: ExportMessage[]
  title?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const EXPORT_PAGE_WIDTH = 1080
const EXPORT_PAGE_HEIGHT = 1440
const EXPORT_PADDING = 64
const EXPORT_FOOTER_HEIGHT = 64
const BASE_GAP = 20
const CAPTURE_SCALE = 2
const CONTENT_WIDTH = EXPORT_PAGE_WIDTH - EXPORT_PADDING * 2
const CONTENT_HEIGHT = EXPORT_PAGE_HEIGHT - EXPORT_PADDING * 2 - EXPORT_FOOTER_HEIGHT

const isGenerating = ref(false)
const pages = ref<ExportMessage[][]>([])
const previewImages = ref<string[]>([])
const activePage = ref(0)

const measureRef = ref<HTMLElement | null>(null)
const measureItemRef = ref<HTMLElement | null>(null)
const measurePayload = ref<ExportMessage | null>(null)
const pageRefs = ref<(HTMLElement | null)[]>([])

const scaleOptions = [
  { label: 'x1.0', value: '1.0' },
  { label: 'x1.5', value: '1.5' },
  { label: 'x2.0', value: '2.0' },
  { label: 'x3.0', value: '3.0' },
]
const scaleValue = ref('1.5')
const contentScale = computed(() => Number(scaleValue.value))
const contentGap = computed(() => Math.round(BASE_GAP * contentScale.value))
const scaled = (value: number) => Math.round(value * contentScale.value)
const scaleStyle = computed(() => ({
  '--export-avatar-size': `${scaled(60)}px`,
  '--export-avatar-radius': `${scaled(14)}px`,
  '--export-name-size': `${scaled(16)}px`,
  '--export-bubble-font-size': `${scaled(24)}px`,
  '--export-bubble-pad-v': `${scaled(18)}px`,
  '--export-bubble-pad-h': `${scaled(22)}px`,
  '--export-bubble-radius': `${scaled(14)}px`,
  '--export-footer-font-size': `${scaled(18)}px`,
}))

const sanitizeContent = (text: string) => text.replace(/<\/?message[^>]*>/gi, '').trim()

const extractMessageSegments = (text: string) => {
  const segments: string[] = []
  const pattern = /<message[^>]*>([\s\S]*?)<\/message>/gi
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    const content = sanitizeContent(match[1] || '')
    if (content) segments.push(content)
  }
  if (segments.length) return segments
  const fallback = sanitizeContent(text)
  return fallback ? [fallback] : []
}

const normalizedMessages = computed<ExportMessage[]>(() => {
  const output: ExportMessage[] = []
  props.messages.forEach((msg) => {
    const segments = extractMessageSegments(msg.content || '')
    if (!segments.length) return
    segments.forEach((segment, index) => {
      output.push({
        ...msg,
        id: `${msg.id}-${index}`,
        content: segment,
        showName: msg.showName && index === 0,
      })
    })
  })
  return output
})

const toChars = (text: string) => Array.from(text)
const fromChars = (chars: string[]) => chars.join('')

const measureMessageHeight = async (msg: ExportMessage) => {
  measurePayload.value = msg
  await nextTick()
  const el = measureItemRef.value
  if (!el) return 0
  return Math.ceil(el.getBoundingClientRect().height)
}

const splitMessageToFit = async (msg: ExportMessage, availableHeight: number) => {
  const chars = toChars(msg.content || '')
  if (!chars.length) {
    return { fit: null, rest: null, height: 0 }
  }

  let left = 1
  let right = chars.length
  let best = 0
  let bestHeight = 0

  while (left <= right) {
    const mid = Math.floor((left + right) / 2)
    const candidate: ExportMessage = {
      ...msg,
      content: fromChars(chars.slice(0, mid)),
    }
    const height = await measureMessageHeight(candidate)
    if (height <= availableHeight) {
      best = mid
      bestHeight = height
      left = mid + 1
    } else {
      right = mid - 1
    }
  }

  if (best === 0) {
    return { fit: null, rest: msg, height: 0 }
  }

  const fit: ExportMessage = {
    ...msg,
    content: fromChars(chars.slice(0, best)),
  }
  const restContent = fromChars(chars.slice(best))
  const rest = restContent
    ? {
        ...msg,
        content: restContent,
        showName: false,
      }
    : null

  return { fit, rest, height: bestHeight }
}

const currentImage = computed(() => previewImages.value[activePage.value] || '')
const hasMultiplePages = computed(() => previewImages.value.length > 1)
const canGoPrev = computed(() => activePage.value > 0)
const canGoNext = computed(() => activePage.value < previewImages.value.length - 1)

const setPageRef = (el: HTMLElement | null, index: number) => {
  pageRefs.value[index] = el
}

const resetState = () => {
  pages.value = []
  previewImages.value = []
  activePage.value = 0
  pageRefs.value = []
}

const handleClose = () => {
  emit('update:open', false)
}

const waitForImages = async (root: HTMLElement) => {
  const images = Array.from(root.querySelectorAll('img'))
  if (!images.length) return
  await Promise.all(
    images.map((img) => {
      if (img.complete && img.naturalWidth > 0) return Promise.resolve()
      return new Promise<void>((resolve) => {
        const cleanup = () => {
          img.removeEventListener('load', cleanup)
          img.removeEventListener('error', cleanup)
          resolve()
        }
        img.addEventListener('load', cleanup, { once: true })
        img.addEventListener('error', cleanup, { once: true })
      })
    })
  )
}

const downloadImage = (dataUrl: string, index: number) => {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = `weagentchat_share_${index}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const generatePreview = async () => {
  if (isGenerating.value || !normalizedMessages.value.length) return
  isGenerating.value = true
  previewImages.value = []
  pages.value = []
  pageRefs.value = []

  await nextTick()
  await nextTick()

  const measureEl = measureRef.value
  if (!measureEl) {
    isGenerating.value = false
    return
  }
  if (document.fonts?.ready) {
    await document.fonts.ready
  }

  const nextPages: ExportMessage[][] = []
  let current: ExportMessage[] = []
  let currentHeight = 0

  for (const msg of normalizedMessages.value) {
    let remaining: ExportMessage | null = msg
    while (remaining) {
      const gap = current.length ? contentGap.value : 0
      const available = CONTENT_HEIGHT - currentHeight - gap

      const fullHeight = await measureMessageHeight(remaining)
      if (fullHeight <= available) {
        currentHeight += gap + fullHeight
        current.push(remaining)
        remaining = null
        continue
      }

      if (current.length && fullHeight <= CONTENT_HEIGHT) {
        nextPages.push(current)
        current = []
        currentHeight = 0
        continue
      }

      const { fit, rest, height } = await splitMessageToFit(remaining, available)
      if (!fit) {
        if (current.length) {
          nextPages.push(current)
          current = []
          currentHeight = 0
          continue
        }

        const chars = toChars(remaining.content || '')
        const forcedContent = fromChars(chars.slice(0, 1))
        const forced: ExportMessage = { ...remaining, content: forcedContent }
        const forcedHeight = await measureMessageHeight(forced)
        current.push(forced)
        currentHeight = forcedHeight

        const restContent = fromChars(chars.slice(1))
        remaining = restContent
          ? { ...remaining, content: restContent, showName: false }
          : null

        nextPages.push(current)
        current = []
        currentHeight = 0
        continue
      }

      currentHeight += gap + height
      current.push(fit)
      remaining = rest

      if (remaining) {
        nextPages.push(current)
        current = []
        currentHeight = 0
      }
    }
  }

  if (current.length) nextPages.push(current)

  pages.value = nextPages
  await nextTick()

  const images: string[] = []
  const refs = pageRefs.value.filter(Boolean) as HTMLElement[]

  for (const pageEl of refs) {
    await waitForImages(pageEl)
    if (document.fonts?.ready) {
      await document.fonts.ready
    }
    const canvas = await html2canvas(pageEl, {
      scale: CAPTURE_SCALE,
      backgroundColor: null,
      useCORS: true,
    })
    images.push(canvas.toDataURL('image/png'))
  }

  previewImages.value = images
  activePage.value = 0
  isGenerating.value = false
}

const handleSaveCurrent = () => {
  if (!currentImage.value) return
  downloadImage(currentImage.value, activePage.value + 1)
}

const handleSaveAll = () => {
  previewImages.value.forEach((img, index) => {
    downloadImage(img, index + 1)
  })
}

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      resetState()
      return
    }
    if (!normalizedMessages.value.length) {
      resetState()
      return
    }
    await generatePreview()
  }
)

watch(
  () => props.messages,
  async () => {
    if (!props.open) return
    await generatePreview()
  },
  { deep: true }
)

watch(scaleValue, async () => {
  if (!props.open) return
  await generatePreview()
})
</script>

<template>
  <Dialog :open="open" @update:open="handleClose">
    <DialogContent class="export-dialog">
      <DialogHeader>
        <DialogTitle>{{ title || '聊天记录图片预览' }}</DialogTitle>
        <DialogDescription>长按或右键图片可保存到本地</DialogDescription>
        <div class="export-scale-row">
          <span class="export-scale-label">缩放倍率</span>
          <Select v-model="scaleValue">
            <SelectTrigger class="export-scale-trigger">
              <SelectValue :placeholder="scaleOptions.find(opt => opt.value === scaleValue)?.label || 'x2.0'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="opt in scaleOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </DialogHeader>

      <div class="export-preview">
        <div class="preview-frame">
          <div v-if="isGenerating" class="preview-loading">
            <Loader2 class="h-5 w-5 animate-spin" />
            <span>正在生成图片...</span>
          </div>
          <img v-else-if="currentImage" :src="currentImage" alt="预览图" class="preview-image" />
          <div v-else class="preview-empty">暂无预览</div>
        </div>

        <div v-if="hasMultiplePages" class="preview-controls">
          <button class="preview-nav" :disabled="!canGoPrev" @click="activePage -= 1">
            <ChevronLeft :size="18" />
          </button>
          <span class="preview-index">{{ activePage + 1 }} / {{ previewImages.length }}</span>
          <button class="preview-nav" :disabled="!canGoNext" @click="activePage += 1">
            <ChevronRight :size="18" />
          </button>
        </div>
      </div>

      <DialogFooter class="export-footer">
        <Button variant="outline" @click="handleClose">关闭</Button>
        <Button variant="outline" :disabled="!currentImage" @click="handleSaveCurrent">
          <Download class="mr-2 h-4 w-4" />
          保存当前页
        </Button>
        <Button :disabled="!previewImages.length" @click="handleSaveAll" class="bg-emerald-600 hover:bg-emerald-700">
          <Download class="mr-2 h-4 w-4" />
          保存全部
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Hidden render root for measurement and capture -->
  <div v-if="open" class="export-render-root" :style="scaleStyle" aria-hidden="true">
    <div ref="measureRef" class="export-measure" :style="{ width: `${CONTENT_WIDTH}px` }">
      <div v-if="measurePayload" ref="measureItemRef" class="export-message"
        :class="{ user: measurePayload.isUser }">
        <div class="export-avatar">
          <img :src="measurePayload.avatar" crossorigin="anonymous" alt="avatar" />
        </div>
        <div class="export-body">
          <div v-if="measurePayload.showName" class="export-name">{{ measurePayload.name }}</div>
          <div class="export-bubble" :class="{ user: measurePayload.isUser }">{{ measurePayload.content }}</div>
        </div>
      </div>
    </div>

    <div class="export-pages">
      <div
        v-for="(page, index) in pages"
        :key="`page-${index}`"
        :ref="(el) => setPageRef(el as HTMLElement | null, index)"
        class="export-page"
        :style="{
          width: `${EXPORT_PAGE_WIDTH}px`,
          height: `${EXPORT_PAGE_HEIGHT}px`,
          padding: `${EXPORT_PADDING}px`,
        }"
      >
        <div class="export-content" :style="{ gap: `${contentGap}px` }">
          <div v-for="msg in page" :key="msg.id" class="export-message" :class="{ user: msg.isUser }">
            <div class="export-avatar">
              <img :src="msg.avatar" crossorigin="anonymous" alt="avatar" />
            </div>
            <div class="export-body">
              <div v-if="msg.showName" class="export-name">{{ msg.name }}</div>
              <div class="export-bubble" :class="{ user: msg.isUser }">{{ msg.content }}</div>
            </div>
          </div>
        </div>
        <div class="export-footer-mark">
          <span>对话由 WeAgentChat（唯信）生成</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.export-dialog {
  max-width: 960px;
  width: 100%;
}

.export-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 8px 0 4px;
}

.export-scale-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.export-scale-label {
  min-width: 56px;
}

.export-scale-trigger {
  height: 32px;
  min-width: 96px;
  background: #fff;
  border-color: #e5e7eb;
  font-size: 12px;
}

.preview-frame {
  width: min(360px, 80vw);
  aspect-ratio: 3 / 4;
  border-radius: 18px;
  background: #f2f3f5;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 13px;
}

.preview-empty {
  color: #9ca3af;
  font-size: 13px;
}

.preview-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 12px;
}

.preview-nav {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.preview-nav:hover:not(:disabled) {
  border-color: #cbd5f5;
  color: #1f2937;
}

.preview-nav:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.preview-index {
  min-width: 48px;
  text-align: center;
}

.export-footer {
  gap: 8px;
  justify-content: center;
}

.export-render-root {
  position: fixed;
  left: -100000px;
  top: 0;
  opacity: 0;
  pointer-events: none;
}

.export-measure {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.export-pages {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.export-page {
  position: relative;
  border-radius: 24px;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.12);
}

.export-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.export-message {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.export-message.user {
  flex-direction: row-reverse;
}

.export-avatar {
  width: var(--export-avatar-size);
  height: var(--export-avatar-size);
  border-radius: var(--export-avatar-radius);
  overflow: hidden;
  flex-shrink: 0;
  background: #e5e7eb;
}

.export-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.export-body {
  max-width: 78%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.export-name {
  font-size: var(--export-name-size);
  color: #94a3b8;
}

.export-bubble {
  padding: var(--export-bubble-pad-v) var(--export-bubble-pad-h);
  border-radius: var(--export-bubble-radius);
  font-size: var(--export-bubble-font-size);
  line-height: 1.75;
  color: #111827;
  background: #fff;
  border: 1px solid #eef2f7;
  word-break: break-word;
  white-space: pre-wrap;
}

.export-bubble.user {
  background: #95ec69;
  border-color: #88df5e;
}

.export-footer-mark {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--export-footer-font-size);
  color: #94a3b8;
  letter-spacing: 0.3px;
}
</style>
