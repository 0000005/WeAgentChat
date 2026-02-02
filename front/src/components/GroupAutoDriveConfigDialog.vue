<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { GroupMember } from '@/api/group'
import type { AutoDriveConfig, AutoDriveEndAction, AutoDriveMode } from '@/types/chat'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const props = withDefaults(defineProps<{ groupFriendMembers: GroupMember[] }>(), {
  groupFriendMembers: () => []
})

const emit = defineEmits<{
  (e: 'submit'): void
  (e: 'toast', message: string): void
}>()

const open = defineModel<boolean>('open', { default: false })

const autoDriveMode = ref<AutoDriveMode>('brainstorm')
const autoDriveTurnLimit = ref(6)
const autoDriveEndAction = ref<AutoDriveEndAction>('summary')
const autoDriveJudgeId = ref('user')
const autoDriveSummaryBy = ref('user')

const brainstormTopic = reactive({
  theme: '',
  goal: '',
  constraints: ''
})

const decisionTopic = reactive({
  question: '',
  options: '',
  criteria: ''
})

const debateTopic = reactive({
  motion: '',
  affirmative: '',
  negative: ''
})

const brainstormParticipants = ref<string[]>([])
const decisionParticipants = ref<string[]>([])
const debateAffirmative = ref<string[]>([])
const debateNegative = ref<string[]>([])

const showSummarySelector = computed(() => ['summary', 'both'].includes(autoDriveEndAction.value))
const showJudgeSelector = computed(() => autoDriveMode.value === 'debate' && ['judge', 'both'].includes(autoDriveEndAction.value))
const availableEndActions = computed(() => {
  if (autoDriveMode.value === 'debate') {
    return [
      { value: 'summary', label: '总结' },
      { value: 'judge', label: '胜负判定' },
      { value: 'both', label: '两者' }
    ]
  }
  return [{ value: 'summary', label: '总结' }]
})

const isEndActionJudge = computed(() => ['judge', 'both'].includes(autoDriveEndAction.value))

const resetAutoDriveConfig = () => {
  autoDriveMode.value = 'brainstorm'
  autoDriveTurnLimit.value = 6
  autoDriveEndAction.value = 'summary'
  autoDriveJudgeId.value = 'user'
  autoDriveSummaryBy.value = 'user'

  brainstormTopic.theme = ''
  brainstormTopic.goal = ''
  brainstormTopic.constraints = ''

  decisionTopic.question = ''
  decisionTopic.options = ''
  decisionTopic.criteria = ''

  debateTopic.motion = ''
  debateTopic.affirmative = ''
  debateTopic.negative = ''

  brainstormParticipants.value = []
  decisionParticipants.value = []
  debateAffirmative.value = []
  debateNegative.value = []
}

const isDebateSideDisabled = (side: 'affirmative' | 'negative', memberId: string) => {
  const affirmativeSet = new Set(debateAffirmative.value)
  const negativeSet = new Set(debateNegative.value)
  if (side === 'affirmative') {
    if (negativeSet.has(memberId)) return true
    if (!affirmativeSet.has(memberId) && debateAffirmative.value.length >= 2) return true
  } else {
    if (affirmativeSet.has(memberId)) return true
    if (!negativeSet.has(memberId) && debateNegative.value.length >= 2) return true
  }
  return false
}

const validateAutoDriveConfig = () => {
  const mode = autoDriveMode.value
  const limit = Number(autoDriveTurnLimit.value)
  if (!Number.isFinite(limit) || limit < 1) {
    emit('toast', '发言上限至少为 1')
    return false
  }
  if (mode === 'brainstorm') {
    if (!brainstormTopic.theme.trim() || !brainstormTopic.goal.trim() || !brainstormTopic.constraints.trim()) {
      emit('toast', '请填写头脑风暴的主题、目标与约束')
      return false
    }
    if (brainstormParticipants.value.length === 0) {
      emit('toast', '请至少选择 1 位参与成员')
      return false
    }
  }
  if (mode === 'decision') {
    if (!decisionTopic.question.trim() || !decisionTopic.options.trim() || !decisionTopic.criteria.trim()) {
      emit('toast', '请填写决策问题、候选方案与评估标准')
      return false
    }
    if (decisionParticipants.value.length === 0) {
      emit('toast', '请至少选择 1 位参与成员')
      return false
    }
  }
  if (mode === 'debate') {
    if (!debateTopic.motion.trim() || !debateTopic.affirmative.trim() || !debateTopic.negative.trim()) {
      emit('toast', '请填写辩题、正方立场与反方立场')
      return false
    }
    if (debateAffirmative.value.length === 0 || debateNegative.value.length === 0) {
      emit('toast', '请为正方与反方各选择 1-2 位成员')
      return false
    }
    if (debateAffirmative.value.length > 2 || debateNegative.value.length > 2) {
      emit('toast', '正反方最多各 2 人')
      return false
    }
    if (debateAffirmative.value.length !== debateNegative.value.length) {
      emit('toast', '正反人数必须相等')
      return false
    }
    if (isEndActionJudge.value && autoDriveJudgeId.value === 'user') {
      emit('toast', '胜负判定需要指定评委成员')
      return false
    }
  }
  return true
}

const buildAutoDriveConfig = (): AutoDriveConfig => {
  const mode = autoDriveMode.value
  if (mode === 'brainstorm') {
    return {
      mode,
      topic: {
        theme: brainstormTopic.theme.trim(),
        goal: brainstormTopic.goal.trim(),
        constraints: brainstormTopic.constraints.trim()
      },
      roles: {
        participants: brainstormParticipants.value
      },
      turnLimit: Number(autoDriveTurnLimit.value) || 1,
      endAction: autoDriveEndAction.value,
      judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
      summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
    }
  }
  if (mode === 'decision') {
    return {
      mode,
      topic: {
        question: decisionTopic.question.trim(),
        options: decisionTopic.options.trim(),
        criteria: decisionTopic.criteria.trim()
      },
      roles: {
        participants: decisionParticipants.value
      },
      turnLimit: Number(autoDriveTurnLimit.value) || 1,
      endAction: autoDriveEndAction.value,
      judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
      summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
    }
  }
  return {
    mode,
    topic: {
      motion: debateTopic.motion.trim(),
      affirmative: debateTopic.affirmative.trim(),
      negative: debateTopic.negative.trim()
    },
    roles: {
      affirmative: debateAffirmative.value,
      negative: debateNegative.value
    },
    turnLimit: Number(autoDriveTurnLimit.value) || 1,
    endAction: autoDriveEndAction.value,
    judgeId: autoDriveJudgeId.value === 'user' ? null : autoDriveJudgeId.value,
    summaryBy: autoDriveSummaryBy.value === 'user' ? null : autoDriveSummaryBy.value
  }
}

const getConfig = () => {
  if (!validateAutoDriveConfig()) return null
  return buildAutoDriveConfig()
}

const handleSubmit = () => {
  emit('submit')
}

watch(open, (val) => {
  if (val) resetAutoDriveConfig()
})

watch(autoDriveMode, (mode) => {
  if (mode !== 'debate' && autoDriveEndAction.value !== 'summary') {
    autoDriveEndAction.value = 'summary'
  }
})

defineExpose({ getConfig })
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="auto-drive-dialog sm:max-w-3xl">
      <DialogHeader class="dialog-header">
        <div class="dialog-title-wrap">
          <DialogTitle>自驱模式配置</DialogTitle>
          <span class="dialog-tag">多轮自动对话</span>
        </div>
        <DialogDescription>AI 好友将自动接力回复，多轮互动更轻松。</DialogDescription>
      </DialogHeader>
      <div class="auto-drive-form">
        <section class="form-card">
          <div class="form-card-title">模式选择</div>
          <div class="mode-switch">
            <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'brainstorm' }"
              @click="autoDriveMode = 'brainstorm'">头脑风暴</button>
            <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'decision' }"
              @click="autoDriveMode = 'decision'">决策</button>
            <button type="button" class="mode-btn" :class="{ active: autoDriveMode === 'debate' }"
              @click="autoDriveMode = 'debate'">辩论</button>
          </div>
          <div class="mode-tip" v-if="autoDriveMode === 'brainstorm'">适合快速发散想法与行动方案。</div>
          <div class="mode-tip" v-else-if="autoDriveMode === 'decision'">适合权衡多方案并给出结论。</div>
          <div class="mode-tip" v-else>适合对立观点的结构化碰撞。</div>
        </section>

        <section class="form-card">
          <div class="form-card-title">话题设置</div>
          <div v-if="autoDriveMode === 'brainstorm'" class="form-section">
            <label class="form-label">主题</label>
            <textarea v-model="brainstormTopic.theme" class="form-textarea"
              placeholder="例如：提升我们产品在大学生群体中的活跃度"></textarea>
            <label class="form-label">目标</label>
            <textarea v-model="brainstormTopic.goal" class="form-textarea"
              placeholder="例如：产出 10 个可执行的增长方案"></textarea>
            <label class="form-label">约束</label>
            <textarea v-model="brainstormTopic.constraints" class="form-textarea"
              placeholder="例如：预算 5 万以内，2 周内落地"></textarea>
          </div>

          <div v-if="autoDriveMode === 'decision'" class="form-section">
            <label class="form-label">决策问题</label>
            <textarea v-model="decisionTopic.question" class="form-textarea"
              placeholder="例如：是否在本季度推出会员制"></textarea>
            <label class="form-label">候选方案</label>
            <textarea v-model="decisionTopic.options" class="form-textarea"
              placeholder="例如：A. 先小范围内测&#10;B. 直接全量上线&#10;C. 延后至下季度"></textarea>
            <label class="form-label">评估标准</label>
            <textarea v-model="decisionTopic.criteria" class="form-textarea"
              placeholder="例如：用户留存权重 40%，成本权重 30%，风险权重 30%"></textarea>
          </div>

          <div v-if="autoDriveMode === 'debate'" class="form-section">
            <label class="form-label">辩题</label>
            <textarea v-model="debateTopic.motion" class="form-textarea"
              placeholder="例如：工作压力大时应该主动辞职"></textarea>
            <label class="form-label">正方立场</label>
            <textarea v-model="debateTopic.affirmative" class="form-textarea"
              placeholder="例如：应该辞职，优先保护身心健康"></textarea>
            <label class="form-label">反方立场</label>
            <textarea v-model="debateTopic.negative" class="form-textarea"
              placeholder="例如：不应辞职，应先寻求调整与支持"></textarea>
          </div>
        </section>

        <section class="form-card">
          <div class="form-card-title">参与成员</div>
          <div v-if="autoDriveMode === 'brainstorm'" class="form-section">
            <div class="member-grid">
              <label v-for="member in props.groupFriendMembers" :key="member.member_id" class="member-chip">
                <input type="checkbox" :value="member.member_id" v-model="brainstormParticipants" />
                <span>{{ member.name }}</span>
              </label>
            </div>
          </div>

          <div v-else-if="autoDriveMode === 'decision'" class="form-section">
            <div class="member-grid">
              <label v-for="member in props.groupFriendMembers" :key="member.member_id + '-decision'" class="member-chip">
                <input type="checkbox" :value="member.member_id" v-model="decisionParticipants" />
                <span>{{ member.name }}</span>
              </label>
            </div>
          </div>

          <div v-if="autoDriveMode === 'debate'" class="form-section">
            <div class="debate-grid">
              <div class="debate-col">
                <label class="form-label">正方成员（1-2 人）</label>
                <div class="member-grid">
                  <label v-for="member in props.groupFriendMembers" :key="member.member_id + '-aff'" class="member-chip">
                    <input type="checkbox" :value="member.member_id" v-model="debateAffirmative"
                      :disabled="isDebateSideDisabled('affirmative', member.member_id)" />
                    <span>{{ member.name }}</span>
                  </label>
                </div>
              </div>
              <div class="debate-col">
                <label class="form-label">反方成员（1-2 人）</label>
                <div class="member-grid">
                  <label v-for="member in props.groupFriendMembers" :key="member.member_id + '-neg'" class="member-chip">
                    <input type="checkbox" :value="member.member_id" v-model="debateNegative"
                      :disabled="isDebateSideDisabled('negative', member.member_id)" />
                    <span>{{ member.name }}</span>
                  </label>
                </div>
              </div>
            </div>
            <div class="form-hint">正反人数必须相等且每方最多 2 人</div>
          </div>
        </section>

        <section class="form-card">
          <div class="form-card-title">流程设置</div>
          <div class="form-section form-inline">
            <div class="form-inline-item">
              <label class="form-label">发言上限</label>
              <input v-model="autoDriveTurnLimit" type="number" min="1" class="form-input" />
            </div>
            <div class="form-inline-item">
              <label class="form-label">结束动作</label>
              <select v-model="autoDriveEndAction" class="form-select" :disabled="availableEndActions.length === 1">
                <option v-for="action in availableEndActions" :key="action.value" :value="action.value">
                  {{ action.label }}
                </option>
              </select>
            </div>
          </div>
        </section>

        <section v-if="showSummarySelector" class="form-card">
          <div class="form-card-title">总结角色</div>
          <div class="form-section">
            <select v-model="autoDriveSummaryBy" class="form-select">
              <option value="user">我（默认）</option>
              <option v-for="member in props.groupFriendMembers" :key="member.member_id + '-summary'"
                :value="member.member_id">
                {{ member.name }}
              </option>
            </select>
          </div>
        </section>

        <section v-if="showJudgeSelector" class="form-card">
          <div class="form-card-title">评委角色</div>
          <div class="form-section">
            <select v-model="autoDriveJudgeId" class="form-select">
              <option value="user">我（默认）</option>
              <option v-for="member in props.groupFriendMembers" :key="member.member_id + '-judge'"
                :value="member.member_id">
                {{ member.name }}
              </option>
            </select>
            <div v-if="autoDriveJudgeId === 'user'" class="form-hint">
              选择“我”不会自动生成胜负判断，请改选评委成员
            </div>
          </div>
        </section>
      </div>
      <DialogFooter class="dialog-footer">
        <Button variant="ghost" @click="open = false">取消</Button>
        <Button type="button" variant="default" class="btn-primary" @click="handleSubmit">
          开始自驱
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.auto-drive-dialog {
  background: #f7f8fa;
  border: 1px solid #e6e8eb;
}

.dialog-header {
  gap: 6px;
}

.dialog-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(7, 193, 96, 0.12);
  color: #0f5132;
}

.auto-drive-dialog .auto-drive-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 2px 2px 4px;
}

.form-card {
  background: #fff;
  border: 1px solid #e6e8eb;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.03);
}

.form-card-title {
  font-size: 12px;
  color: #3f4a5a;
  font-weight: 600;
  margin-bottom: 10px;
  letter-spacing: 0.2px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-label {
  font-size: 12px;
  color: #6b7280;
}

.form-textarea {
  min-height: 72px;
  padding: 10px 12px;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  resize: vertical;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-input,
.form-select {
  padding: 9px 12px;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-textarea:focus,
.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #07c160;
  box-shadow: 0 0 0 2px rgba(7, 193, 96, 0.15);
}

.form-inline {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.form-inline-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
  flex: 1;
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  background: #f0f2f5;
  padding: 6px;
  border-radius: 12px;
}

.mode-btn {
  padding: 7px 12px;
  font-size: 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: #3f4a5a;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  background: #ffffff;
  border-color: #e5e7eb;
}

.mode-btn.active {
  background: #07c160;
  border-color: #07c160;
  color: #fff;
  box-shadow: 0 6px 14px rgba(7, 193, 96, 0.2);
}

.mode-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.member-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.member-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e6e8eb;
  background: #f8f9fb;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.member-chip:hover {
  border-color: #cfd8e3;
  background: #ffffff;
}

.member-chip input {
  margin: 0;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid #cfd4dc;
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.member-chip input:checked {
  border-color: #07c160;
  background: #07c160;
}

.member-chip input:checked::after {
  content: '';
  width: 4px;
  height: 8px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.member-chip input:checked + span {
  color: #0f5132;
  font-weight: 600;
  background: rgba(7, 193, 96, 0.12);
  border-radius: 999px;
  padding: 2px 6px;
}

.debate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.debate-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-hint {
  font-size: 12px;
  color: #64748b;
  background: #f5f7fa;
  border-left: 3px solid #07c160;
  padding: 8px 10px;
  border-radius: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-primary {
  background: #07c160;
  color: #fff;
}

.btn-primary:hover {
  background: #06ad56;
}
</style>
