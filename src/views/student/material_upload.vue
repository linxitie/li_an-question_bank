<template>
  <div class="mc-page">
    <header class="mc-head">
      <h1>创建卡片</h1>
      <p class="mc-sub">
        学生端两种建卡方式并存：<b>逐张创建</b>（人工填写，保存即公开展示，免审批）与
        <b>Excel 批量导入</b>（表格一次多行，提交后进待审队列，管理员上架后公开）。
      </p>
    </header>

    <nav class="mc-tabs" role="tablist">
      <button
        v-for="t in TABS"
        :key="t.value"
        class="mc-tab"
        :class="{ 'is-on': tab === t.value }"
        role="tab"
        :aria-selected="tab === t.value"
        @click="setTab(t.value)"
      >{{ t.label }}</button>
    </nav>

    <!-- ① 逐张创建：与手机端同一个表单组件（inline 形态） -->
    <section v-show="tab === 'manual'">
      <CardCreateForm inline :open="true" :subject="subject" @saved="onManualSaved" />
      <p class="mc-foot">
        字段说明：正面 ≤120 字；背面 ≤600 字（背面为空时必须配图）；分类留空由系统按文本自动判定；
        配图支持 png / jpg / webp，单张 ≤5MB，最多 2 张。
      </p>
    </section>

    <!-- ② Excel 批量导入：还原原有能力，走真实接口 /api/materials/my/upload -->
    <section v-show="tab === 'excel'" class="mc-excel">
      <div class="mc-quota">
        <div class="mc-quota-item">
          <span class="mc-quota-num">≤200</span>
          <span class="mc-quota-lab">单表最多行数</span>
        </div>
        <div class="mc-quota-item">
          <span class="mc-quota-num">5MB</span>
          <span class="mc-quota-lab">单文件上限</span>
        </div>
        <div class="mc-quota-item">
          <span class="mc-quota-num">50 张/天</span>
          <span class="mc-quota-lab">每人每日上限（含逐张创建）</span>
        </div>
        <p class="mc-quota-tip">
          表头需含「正面」「背面」；可选「分类」「考点」「难度」「封面」。分类留空会自动判定。
        </p>
      </div>

      <div class="mc-form">
        <div class="mc-row">
          <span class="mc-lab">科目</span>
          <div class="mc-seg">
            <button
              v-for="s in SUBJECTS"
              :key="s.value"
              class="mc-seg-btn"
              :class="{ 'is-on': excelSubject === s.value }"
              @click="excelSubject = s.value"
            >{{ s.label }}</button>
          </div>
        </div>

        <div class="mc-row">
          <span class="mc-lab">表格</span>
          <label
            class="mc-drop"
            :class="{ 'is-over': dragging, 'has-file': !!file }"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onDrop"
          >
            <input ref="fileInput" type="file" accept=".xlsx,.csv" hidden @change="onPick" />
            <template v-if="!file">
              <span class="mc-drop-main">点击选择，或把表格拖到这里</span>
              <span class="mc-drop-sub">.xlsx / .csv，≤5MB、≤200 行</span>
            </template>
            <template v-else>
              <span class="mc-drop-main">{{ file.name }}</span>
              <span class="mc-drop-sub">{{ (file.size / 1024).toFixed(0) }} KB · 点击可更换</span>
            </template>
          </label>
        </div>

        <div class="mc-actions">
          <button class="mc-btn" :disabled="!file || uploading" @click="submitExcel">
            {{ uploading ? '上传中…' : '提交导入' }}
          </button>
          <span class="mc-note">提交后进入待审队列，管理员审核通过才会公开展示</span>
        </div>
        <p v-if="error" class="mc-err">{{ error }}</p>
      </div>

      <div v-if="result" class="mc-result">
        <div class="mc-result-head">
          <b>已提交 {{ result.created }} 张</b>
          <span class="mc-pending">待审核</span>
          <span class="mc-result-note">{{ result.note }}</span>
        </div>

        <div v-if="(result.skipped || []).length" class="mc-block">
          <p class="mc-block-title">跳过 {{ result.skipped.length }} 行</p>
          <ul class="mc-list">
            <li v-for="(s, i) in result.skipped" :key="i">
              第 {{ s.row }} 行：{{ reasonText(s.reason) }}
            </li>
          </ul>
        </div>

        <div v-if="(result.warnings || []).length" class="mc-block mc-block-warn">
          <p class="mc-block-title">提醒 {{ result.warnings.length }} 条</p>
          <ul class="mc-list">
            <li v-for="(wm, i) in result.warnings" :key="i">
              第 {{ wm.row }} 行 {{ wm.column }}：{{ wm.message }}
            </li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import CardCreateForm from '@/components/materials/CardCreateForm.vue';

type Tab = 'manual' | 'excel';

const TABS: { value: Tab; label: string }[] = [
  { value: 'manual', label: '逐张创建' },
  { value: 'excel', label: 'Excel 批量导入' }
];

const SUBJECTS = [
  { value: 'xingce', label: '行测' },
  { value: 'shenlun', label: '申论' },
  { value: 'gongzhuan', label: '公专' }
];

const route = useRoute();
const router = useRouter();

const tab = ref<Tab>(route.query.tab === 'excel' ? 'excel' : 'manual');
const subject = ref('xingce');

// Excel 面板
const excelSubject = ref('xingce');
const file = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const dragging = ref(false);
const uploading = ref(false);
const error = ref('');
const result = ref<any>(null);

const apiFetch = (url: string, init?: RequestInit) => {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
};

const setTab = (next: Tab) => {
  tab.value = next;
  const query = next === 'excel' ? { tab: 'excel' } : {};
  router.replace({ path: route.path, query }).catch(() => {});
};

// PC 资料页的「Excel 批量导入」按钮直接带 ?tab=excel 进来
watch(
  () => route.query.tab,
  (v) => {
    tab.value = v === 'excel' ? 'excel' : 'manual';
  }
);

const onManualSaved = (payload: Record<string, any>) => {
  if (payload?.subject) subject.value = String(payload.subject);
  ElMessage.success('卡片已创建并公开展示');
};

const reasonText = (r: string) => {
  const map: Record<string, string> = {
    empty: '正面或背面为空，已跳过',
    invalid: '格式不合规（超长/重复/含不允许的标签），已跳过',
    duplicate: '与已有资料内容重复，已跳过'
  };
  return map[r] || r;
};

const setFile = (f: File) => {
  error.value = '';
  result.value = null;
  if (!/\.(xlsx|csv)$/i.test(f.name)) {
    error.value = '只支持 .xlsx 或 .csv';
    return;
  }
  if (f.size > 5 * 1024 * 1024) {
    error.value = '文件超过 5MB';
    return;
  }
  file.value = f;
};

const onPick = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) setFile(f);
};

const onDrop = (e: DragEvent) => {
  dragging.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) setFile(f);
};

const submitExcel = async () => {
  if (!file.value || uploading.value) return;
  uploading.value = true;
  error.value = '';
  result.value = null;
  try {
    const fd = new FormData();
    fd.append('file', file.value, file.value.name);
    const resp = await apiFetch(
      `/api/materials/my/upload?subject=${encodeURIComponent(excelSubject.value)}`,
      { method: 'POST', body: fd }
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error((data as any)?.detail || `导入失败（${resp.status}）`);
    result.value = data;
    file.value = null;
    if (fileInput.value) fileInput.value.value = '';
    ElMessage.success(`已提交 ${data.created} 张，等待管理员审核`);
  } catch (e) {
    error.value = (e as Error)?.message || '导入失败，请稍后重试';
  } finally {
    uploading.value = false;
  }
};
</script>

<style scoped>
.mc-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 18px 56px;
}
.mc-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  color: #111827;
}
.mc-sub {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}
.mc-sub b {
  color: #b45309;
}
/* 两种建卡方式：分段式切换 */
.mc-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: #eef2f8;
}
.mc-tab {
  height: 34px;
  padding: 0 20px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: #5a6b85;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
}
.mc-tab.is-on {
  background: #fff;
  color: #1d4ed8;
  box-shadow: 0 2px 8px rgba(24, 44, 84, 0.12);
}

/* ===== Excel 面板 ===== */
.mc-quota {
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 12px 16px;
  margin-bottom: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  flex-wrap: wrap;
}
.mc-quota-item {
  display: flex;
  flex-direction: column;
}
.mc-quota-num {
  font-size: 18px;
  font-weight: 700;
  color: #2563eb;
}
.mc-quota-lab {
  font-size: 11.5px;
  color: #6b7280;
}
.mc-quota-tip {
  flex: 1 1 260px;
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}
.mc-form {
  padding: 16px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(23, 43, 77, 0.05);
}
.mc-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 0;
}
.mc-lab {
  width: 46px;
  flex: none;
  font-size: 13px;
  color: #374151;
}
.mc-seg {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.mc-seg-btn {
  padding: 6px 16px;
  border: 1px solid #d8dbe6;
  border-radius: 999px;
  background: #fff;
  color: #4b5563;
  font-size: 13px;
  cursor: pointer;
}
.mc-seg-btn.is-on {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.mc-drop {
  flex: 1;
  min-height: 92px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1.5px dashed #cbd5e1;
  border-radius: 12px;
  background: #fafbff;
  cursor: pointer;
}
.mc-drop.is-over {
  border-color: #2563eb;
  background: #eff6ff;
}
.mc-drop.has-file {
  border-style: solid;
  border-color: #bfd3f7;
  background: #f4f8ff;
}
.mc-drop-main {
  font-size: 14px;
  color: #111827;
  word-break: break-all;
  text-align: center;
  padding: 0 10px;
}
.mc-drop-sub {
  font-size: 12px;
  color: #9ca3af;
}
.mc-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 10px;
  flex-wrap: wrap;
}
.mc-btn {
  padding: 9px 22px;
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.mc-btn:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}
.mc-note {
  font-size: 12px;
  color: #b45309;
}
.mc-err {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: #dc2626;
}
.mc-result {
  margin-top: 14px;
  padding: 14px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
}
.mc-result-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  flex-wrap: wrap;
}
.mc-pending {
  padding: 1px 7px;
  border-radius: 6px;
  background: #fef3c7;
  color: #b45309;
  font-size: 11px;
}
.mc-result-note {
  font-size: 12px;
  color: #6b7280;
}
.mc-block {
  margin-top: 10px;
}
.mc-block-title {
  margin: 0 0 4px;
  font-size: 12.5px;
  color: #6b7280;
}
.mc-block-warn .mc-block-title {
  color: #b45309;
}
.mc-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.8;
  color: #374151;
}
.mc-foot {
  margin: 14px 0 0;
  font-size: 12px;
  line-height: 1.8;
  color: #9ca3af;
}

@media (max-width: 640px) {
  .mc-page {
    padding: 16px 12px 40px;
  }
  .mc-tabs {
    display: flex;
  }
  .mc-tab {
    flex: 1;
    padding: 0 10px;
    font-size: 12.5px;
  }
  .mc-row {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .mc-lab {
    width: auto;
  }
  .mc-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .mc-btn {
    width: 100%;
  }
}
/* 触屏（平板/手机）：交互元素补到 44px 最小可点区；PC 鼠标端不受影响 */
@media (pointer: coarse) {
  .mc-tab,
  .mc-btn,
  .mc-seg-btn,
  .mc-subj,
  button {
    min-height: 44px;
  }
}
</style>
