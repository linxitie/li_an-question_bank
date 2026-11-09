<template>
  <Teleport to="body">
    <div v-if="open" class="egd-root" role="dialog" aria-modal="true" aria-label="设置考试时间">
      <div class="egd-mask" @click="close" />
      <section class="egd-panel">
        <header class="egd-head">
          <div>
            <h2 class="egd-title">设置考试时间<span v-if="paperCode" class="egd-code">（{{ paperCode }}）</span></h2>
            <p class="egd-desc">
              只在下面的时间窗内允许学生进入；<b>留空 = 不限</b>。到点自动生效，不靠后台任务。
              关闭/过期都<b>不影响历史成绩</b>。
            </p>
          </div>
          <button class="egd-x" type="button" :disabled="saving" @click="close">×</button>
        </header>

        <div class="egd-body">
          <div class="egd-grid">
            <label class="egd-field">
              <span>开始时间</span>
              <div class="egd-inputrow">
                <input
                  v-model="form.openAt"
                  class="adm-input egd-input"
                  type="datetime-local"
                  :disabled="saving"
                />
                <button class="adm-btn adm-btn--line adm-btn--sm" type="button"
                        :disabled="saving" @click="fillTonight('open')">快速填：今晚</button>
              </div>
            </label>
            <label class="egd-field">
              <span>结束时间</span>
              <div class="egd-inputrow">
                <input
                  v-model="form.closeAt"
                  class="adm-input egd-input"
                  type="datetime-local"
                  :disabled="saving"
                />
                <button class="adm-btn adm-btn--line adm-btn--sm" type="button"
                        :disabled="saving" @click="fillTonight('close')">快速填：今晚</button>
              </div>
            </label>
          </div>

          <p class="egd-now" :class="{ 'is-off': !currentReady }">{{ nowLine }}</p>
          <p v-if="windowPreview" class="egd-preview">{{ windowPreview }}</p>
          <p v-if="error" class="egd-error">{{ error }}</p>
        </div>

        <footer class="egd-foot">
          <span class="egd-foot__hint">{{ footHint }}</span>
          <button class="adm-btn adm-btn--line" type="button" :disabled="saving" @click="clearAll">清空</button>
          <button class="adm-btn adm-btn--line" type="button" :disabled="saving" @click="close">取消</button>
          <button class="adm-btn adm-btn--primary" type="button" :disabled="!canSave" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 「设置考试时间」弹层（P2，2026-11-09）。
 *
 * 为什么单独一个组件：管理端列表（`views/admin/materials.vue`）与以后的预览抽屉都要用，
 * 而本仓库 **Element Plus 是按需引入**（`el-dialog` 全局不存在，实测渲染成未知元素），
 * 所以沿用 `MaterialMetaDialog` 的 Teleport + mask 手写弹层。
 *
 * 口径（用户决策 S1）：时间一律按**服务器本地时间**解释。弹层里的「当前」用后端回传的
 * `server_now` 显示，不拿浏览器时间算 —— 学生机与服务器时区可能不同，
 * 前端自己算会出现"管理端说在窗口内、学生却进不去"。
 *
 * 保存走 `PUT /admin/{id}/exam-window`：两端都空 = 取消定时（等价「不限时」）。
 */
import { computed, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  setMaterialExamWindow,
  type LibraryExamState
} from '@/modules/library/api';
import {
  examNowLine,
  examStatusLabel,
  fromDatetimeLocal,
  toDatetimeLocal,
  tonightWindow
} from '@/utils/examGate';
import { errorMessage } from '@/utils/apiError';

const props = withDefaults(
  defineProps<{
    open: boolean;
    materialId: number | null;
    paperCode?: string | null;
    paperName?: string | null;
    exam?: LibraryExamState | null;
  }>(),
  { paperCode: '', paperName: '', exam: null }
);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', state: LibraryExamState): void;
}>();

const saving = ref(false);
const error = ref('');
const form = reactive({ openAt: '', closeAt: '' });

/** 打开时用当前值回填（同一弹层复用，切换行必须重置，否则会带着上一行的值保存） */
watch(
  () => [props.open, props.materialId],
  () => {
    if (!props.open) return;
    form.openAt = toDatetimeLocal(props.exam?.open_at);
    form.closeAt = toDatetimeLocal(props.exam?.close_at);
    error.value = '';
  },
  { immediate: true }
);

const currentReady = computed(() => Boolean(props.exam?.ready));
const nowLine = computed(() => examNowLine(props.exam));

/** 保存后的效果预告：让人在点保存前就知道"学生这一刻能不能进" */
const windowPreview = computed(() => {
  // 前置条件不满足时，定时设了也白设 —— 先说清楚，别让人以为保存完就能考
  if (!props.exam?.known) return '还没有可作答卷，定时不会生效。';
  if (!props.exam.question_count) return '这张卷还是 0 题：保存后学生仍然进不去，先导题。';
  if (!props.exam.published) return '资料还没上架（卷仍是草稿）：保存后学生仍然进不去。';
  const openAt = fromDatetimeLocal(form.openAt);
  const closeAt = fromDatetimeLocal(form.closeAt);
  if (!openAt && !closeAt) return '保存后：不限时间，开关打开即可进入。';
  const now = String(props.exam?.server_now || '').replace(' ', 'T').slice(0, 16);
  if (now && openAt && now < openAt.replace(' ', 'T')) {
    return `保存后：学生要等到 ${openAt.slice(5, 16)} 才能进入。`;
  }
  if (now && closeAt && now >= closeAt.replace(' ', 'T')) {
    return `保存后：窗口已过去（${closeAt.slice(5, 16)} 结束），学生现在进不去。`;
  }
  return '保存后：只要开关是打开的，学生现在就能进入。';
});

const canSave = computed(() => {
  if (saving.value || props.materialId == null) return false;
  const openAt = fromDatetimeLocal(form.openAt);
  const closeAt = fromDatetimeLocal(form.closeAt);
  if (openAt && closeAt && openAt >= closeAt) return false;   // 后端也会拦，前端先给出禁用态
  return true;
});

const footHint = computed(() => {
  const openAt = fromDatetimeLocal(form.openAt);
  const closeAt = fromDatetimeLocal(form.closeAt);
  if (openAt && closeAt && openAt >= closeAt) return '开始时间必须早于结束时间';
  if (!openAt && !closeAt) return '当前：不限时间';
  if (!props.exam?.known) return '还没有可作答卷，设定时也不会生效';
  return `当前状态：${examStatusLabel(props.exam)}`;
});

/** 「快速填：今晚」—— 以服务器日期为准的今天 20:00 / 22:00 */
function fillTonight(which: 'open' | 'close'): void {
  const w = tonightWindow(props.exam?.server_now);
  if (which === 'open') form.openAt = w.open;
  else form.closeAt = w.close;
}

async function save(): Promise<void> {
  if (!canSave.value || props.materialId == null) return;
  saving.value = true;
  error.value = '';
  try {
    const state = await setMaterialExamWindow(props.materialId, {
      open_at: fromDatetimeLocal(form.openAt),
      close_at: fromDatetimeLocal(form.closeAt)
    });
    ElMessage.success('已保存考试时间');
    emit('saved', state);
  } catch (e) {
    error.value = errorMessage(e, '保存失败');
  } finally {
    saving.value = false;
  }
}

/** 清空 = 取消定时（不保存，只清表单；点保存才落库，避免误操作直接改线上） */
function clearAll(): void {
  form.openAt = '';
  form.closeAt = '';
  error.value = '';
}

function close(): void {
  if (saving.value) return;
  emit('close');
}
</script>

<style scoped>
.egd-root {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.egd-mask {
  position: absolute;
  inset: 0;
  background: rgba(16, 24, 40, 0.42);
}
.egd-panel {
  position: relative;
  width: 520px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: var(--adm-r-card, 12px);
  box-shadow: 0 18px 48px rgba(16, 24, 40, 0.18);
  font-family: var(--adm-font);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 64px);
}
.egd-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--adm-s3, 12px);
  padding: 16px 18px 10px;
  border-bottom: 1px solid var(--adm-line, #eef1f6);
}
.egd-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--adm-text);
}
.egd-code {
  font-family: var(--adm-mono, monospace);
  font-size: 12px;
  color: var(--adm-text-sub);
  font-weight: 600;
}
.egd-desc {
  margin: 6px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--adm-text-sub);
}
.egd-x {
  border: none;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: var(--adm-text-weak, #93a0b5);
  cursor: pointer;
}
.egd-body {
  padding: 14px 18px 4px;
  overflow: auto;
}
.egd-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.egd-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11.5px;
  color: var(--adm-text-sub);
}
.egd-inputrow {
  display: flex;
  align-items: center;
  gap: 8px;
}
.egd-input {
  flex: 1;
  min-width: 0;
}
.egd-now {
  margin: 14px 0 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--adm-ok, #12a150);
}
.egd-now.is-off { color: var(--adm-danger, #d9463b); }
.egd-preview {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: var(--adm-text-sub);
}
.egd-error {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--adm-danger, #d9463b);
}
.egd-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--adm-line, #eef1f6);
}
.egd-foot__hint {
  flex: 1;
  font-size: 11px;
  color: var(--adm-text-weak, #93a0b5);
}
</style>
