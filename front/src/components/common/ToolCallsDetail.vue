<script setup lang="ts">
import type { ToolCall } from '@/types/chat'
import { computed } from 'vue'

interface Props {
  toolCalls: ToolCall[]
}

const props = defineProps<Props>()

const toolCalls = computed(() => props.toolCalls || [])

const statusLabel = (status: ToolCall['status']) => {
  if (status === 'calling') return '调用中'
  if (status === 'completed') return '已完成'
  return '失败'
}

const escapeHtml = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')

const formatValue = (value: unknown): string => {
  if (value === undefined) return ''
  if (value === null) return 'null'
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return ''
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2)
    } catch {
      return trimmed
    }
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const highlightJson = (value: unknown): string => {
  const formatted = formatValue(value)
  if (!formatted) return ''
  const escaped = escapeHtml(formatted)
  return escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let className = 'json-number'
      if (match.startsWith('"')) {
        className = match.endsWith(':') ? 'json-key' : 'json-string'
      } else if (match === 'true' || match === 'false') {
        className = 'json-boolean'
      } else if (match === 'null') {
        className = 'json-null'
      }
      return `<span class="${className}">${match}</span>`
    }
  )
}

const hasFormattedValue = (value: unknown) => Boolean(formatValue(value))
</script>

<template>
  <div class="tool-calls-detail">
    <div v-if="toolCalls.length === 0" class="tool-calls-empty">
      暂无工具调用
    </div>
    <div v-else class="tool-calls-list">
      <div v-for="(call, index) in toolCalls" :key="index" class="tool-call-card">
        <div class="tool-call-header">
          <div class="tool-call-title">
            <span class="tool-call-index">#{{ index + 1 }}</span>
            <span class="tool-call-name">{{ call.name || '未命名工具' }}</span>
          </div>
          <span class="tool-call-status" :class="`status-${call.status}`">
            {{ statusLabel(call.status) }}
          </span>
        </div>
        <div class="tool-call-body">
          <div class="tool-call-section">
            <div class="tool-call-label">输入参数</div>
            <pre v-if="hasFormattedValue(call.args)" class="tool-call-code"><code v-html="highlightJson(call.args)"></code></pre>
            <div v-else class="tool-call-empty">无参数</div>
          </div>
          <div class="tool-call-section">
            <div class="tool-call-label">返回结果</div>
            <pre v-if="hasFormattedValue(call.result)" class="tool-call-code"><code v-html="highlightJson(call.result)"></code></pre>
            <div v-else class="tool-call-empty">
              {{ call.status === 'error' ? '调用失败' : call.status === 'calling' ? '等待结果...' : '暂无结果' }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-calls-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-calls-empty {
  color: #999;
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}

.tool-calls-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-call-card {
  background: #fff;
  border: 1px solid #e9e9e9;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.tool-call-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.tool-call-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #333;
}

.tool-call-index {
  font-size: 12px;
  color: #999;
}

.tool-call-name {
  font-weight: 500;
}

.tool-call-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4b5563;
}

.tool-call-status.status-calling {
  background: #fff7ed;
  color: #b45309;
}

.tool-call-status.status-completed {
  background: #ecfdf3;
  color: #16a34a;
}

.tool-call-status.status-error {
  background: #fef2f2;
  color: #dc2626;
}

.tool-call-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 14px 14px;
}

.tool-call-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-call-label {
  font-size: 12px;
  color: #888;
  letter-spacing: 0.4px;
}

.tool-call-code {
  background: #f7f7f7;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  overflow-x: auto;
  white-space: pre;
  color: #1f2937;
}

.tool-call-empty {
  font-size: 12px;
  color: #999;
  padding: 8px 10px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px dashed #eee;
}

:deep(.json-key) {
  color: #2563eb;
}

:deep(.json-string) {
  color: #16a34a;
}

:deep(.json-number) {
  color: #b45309;
}

:deep(.json-boolean) {
  color: #0284c7;
}

:deep(.json-null) {
  color: #6b7280;
}
</style>
