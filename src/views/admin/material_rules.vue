<template>
  <div class="rules-page">
    <header class="rp-head">
      <div class="rp-title-wrap">
        <h1 class="rp-title">分类规则</h1>
        <p class="rp-sub">决定「资料卡片」在建卡/导入时自动归到哪个知识子类。仅管理员可见。</p>
      </div>
      <button class="rp-add" @click="openCreate">＋ 新增规则</button>
    </header>

    <section class="rp-toolbar">
      <input
        v-model="keyword"
        class="rp-search"
        type="text"
        placeholder="搜索规则名称（如：判断推理）"
        @input="onSearchInput"
      />
      <select v-model.number="enabled" class="rp-select" @change="reload">
        <option :value="-1">全部状态</option>
        <option :value="1">仅启用</option>
        <option :value="0">仅停用</option>
      </select>
      <span class="rp-count">共 {{ total }} 条</span>
    </section>

    <div v-if="error" class="rp-error">{{ error }}</div>

    <section class="rp-list" :class="{ 'is-loading': loading }">
      <div v-if="loading" class="rp-empty">加载中…</div>
      <div v-else-if="!items.length" class="rp-empty">暂无规则</div>
      <article v-for="r in items" :key="r.id" class="rp-row">
        <div class="rp-row-main">
          <div class="rp-row-title">
            <span class="rp-name">{{ r.name }}</span>
            <span class="rp-badge" :class="r.enabled ? 'on' : 'off'">
              {{ r.enabled ? '启用' : '停用' }}
            </span>
          </div>
          <div class="rp-meta">
            <span class="rp-tag">{{ subjectName(r.subject) }}</span>
            <span class="rp-tag rp-tag-cat">→ {{ r.category || '未设置' }}</span>
            <span class="rp-prio">优先级 {{ r.priority }}</span>
          </div>
          <div class="rp-kws">
            <span v-for="k in r.keywords" :key="k" class="rp-kw">{{ k }}</span>
          </div>
        </div>
        <div class="rp-row-actions">
          <button class="rp-btn" @click="openEdit(r)">编辑</button>
          <button class="rp-btn" :class="r.enabled ? 'danger' : 'ok'" @click="toggle(r)">
            {{ r.enabled ? '停用' : '启用' }}
          </button>
        </div>
      </article>
    </section>

    <footer class="rp-pager">
      <button class="rp-btn" :disabled="page <= 1 || loading" @click="goto(page - 1)">上一页</button>
      <span class="rp-pageinfo">第 {{ page }} / {{ maxPage }} 页</span>
      <button class="rp-btn" :disabled="page >= maxPage || loading" @click="goto(page + 1)">下一页</button>
    </footer>

    <!-- 新增 / 编辑 -->
    <div v-if="dialogVisible" class="rp-mask" @click.self="closeDialog">
      <div class="rp-dialog">
        <h2 class="rp-dialog-title">{{ form.id ? '编辑规则' : '新增规则' }}</h2>

        <label class="rp-field">
          <span>规则名称 *</span>
          <input v-model.trim="form.name" type="text" maxlength="100" placeholder="如：行测·判断推理" />
        </label>

        <div class="rp-field-row">
          <label class="rp-field">
            <span>科目</span>
            <select v-model="form.subject">
              <option value="">（不限）</option>
              <option value="xingce">行测</option>
              <option value="shenlun">申论</option>
              <option value="gongzhuan">公专</option>
            </select>
          </label>
          <label class="rp-field">
            <span>优先级（0–100）</span>
            <input v-model.number="form.priority" type="number" min="0" max="100" />
          </label>
        </div>

        <label class="rp-field">
          <span>目标分类 *</span>
          <input v-model.trim="form.category" type="text" placeholder="如：判断推理" />
        </label>

        <label class="rp-field">
          <span>关键词 *（逗号或换行分隔）</span>
          <textarea v-model="form.keywordsText" rows="4" placeholder="图形推理, 类比推理, 加强, 削弱"></textarea>
        </label>

        <label class="rp-check">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用（停用后不再参与自动分类）</span>
        </label>

        <div v-if="formError" class="rp-error">{{ formError }}</div>

        <div class="rp-dialog-actions">
          <button class="rp-btn" @click="closeDialog">取消</button>
          <button class="rp-btn primary" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="rp-toast">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

type Rule = {
  id: number;
  name: string;
  type: string;
  subject: string | null;
  category: string | null;
  keywords: string[];
  priority: number;
  enabled: number;
};

const SUBJECTS: Record<string, string> = { xingce: '行测', shenlun: '申论', gongzhuan: '公专' };
const subjectName = (s: string | null) => (s ? SUBJECTS[s] || s : '不限科目');

/** 取数：优先用宿主注入的 __VTJ_AUTH__.apiFetch（自带 token），否则退回原生 fetch */
const apiFetch = (url: string, init?: RequestInit) => {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
};

const items = ref<Rule[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const keyword = ref('');
const enabled = ref(-1);
const loading = ref(false);
const error = ref('');
const toast = ref('');
const saving = ref(false);
const dialogVisible = ref(false);
const formError = ref('');

const form = reactive({
  id: 0,
  name: '',
  subject: '',
  category: '',
  keywordsText: '',
  priority: 50,
  enabled: true
});

const maxPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));

const flash = (msg: string) => {
  toast.value = msg;
  window.setTimeout(() => (toast.value = ''), 2200);
};

const parseError = async (resp: Response) => {
  let detail = `请求失败（${resp.status}）`;
  try {
    const j = await resp.json();
    if (j && j.detail) detail = String(j.detail);
  } catch {
    /* 忽略解析失败 */
  }
  return detail;
};

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    const qs = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
      enabled: String(enabled.value),
      keyword: keyword.value.trim()
    });
    const resp = await apiFetch(`/api/materials/admin/rules?${qs.toString()}`);
    if (!resp.ok) {
      error.value = await parseError(resp);
      items.value = [];
      total.value = 0;
      return;
    }
    const data = await resp.json();
    items.value = (data.items || []) as Rule[];
    total.value = data.total || 0;
    if (page.value > maxPage.value) page.value = maxPage.value;
  } catch (e) {
    error.value = `加载失败：${(e as Error)?.message || e}`;
  } finally {
    loading.value = false;
  }
};

let searchTimer: number | undefined;
const onSearchInput = () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    page.value = 1;
    load();
  }, 300);
};

const reload = () => {
  page.value = 1;
  load();
};
const goto = (p: number) => {
  page.value = Math.min(Math.max(1, p), maxPage.value);
  load();
};

const resetForm = () => {
  form.id = 0;
  form.name = '';
  form.subject = '';
  form.category = '';
  form.keywordsText = '';
  form.priority = 50;
  form.enabled = true;
  formError.value = '';
};

const openCreate = () => {
  resetForm();
  dialogVisible.value = true;
};
const openEdit = (r: Rule) => {
  form.id = r.id;
  form.name = r.name;
  form.subject = r.subject || '';
  form.category = r.category || '';
  form.keywordsText = (r.keywords || []).join(', ');
  form.priority = r.priority;
  form.enabled = !!r.enabled;
  formError.value = '';
  dialogVisible.value = true;
};
const closeDialog = () => {
  dialogVisible.value = false;
};

const collectKeywords = () =>
  form.keywordsText
    .split(/[,，\n\r]+/)
    .map((s) => s.trim())
    .filter(Boolean);

const save = async () => {
  formError.value = '';
  const keywords = collectKeywords();
  if (!form.name.trim()) {
    formError.value = '规则名称必填';
    return;
  }
  if (!form.category.trim()) {
    formError.value = '目标分类必填';
    return;
  }
  if (!keywords.length) {
    formError.value = '关键词至少 1 个';
    return;
  }
  if (form.priority < 0 || form.priority > 100) {
    formError.value = '优先级需在 0–100 之间';
    return;
  }
  const body = {
    name: form.name.trim(),
    type: 'keyword',
    subject: form.subject || '',
    category: form.category.trim(),
    keywords,
    priority: form.priority,
    enabled: form.enabled ? 1 : 0
  };
  saving.value = true;
  try {
    const isEdit = !!form.id;
    const resp = await apiFetch(
      isEdit ? `/api/materials/admin/rules/${form.id}` : '/api/materials/admin/rules',
      {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }
    );
    if (!resp.ok) {
      formError.value = await parseError(resp);
      return;
    }
    dialogVisible.value = false;
    flash(isEdit ? '已保存修改' : '已新增规则');
    await load();
  } catch (e) {
    formError.value = `保存失败：${(e as Error)?.message || e}`;
  } finally {
    saving.value = false;
  }
};

const toggle = async (r: Rule) => {
  try {
    const resp = await apiFetch(`/api/materials/admin/rules/${r.id}/toggle`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: r.enabled ? 0 : 1 })
    });
    if (!resp.ok) {
      error.value = await parseError(resp);
      return;
    }
    r.enabled = r.enabled ? 0 : 1;
    flash(r.enabled ? '已启用' : '已停用');
  } catch (e) {
    error.value = `操作失败：${(e as Error)?.message || e}`;
  }
};

onMounted(load);
</script>

<style scoped>
.rules-page {
  --brand: #3b82f6;
  --brand-soft: #eef4ff;
  padding: 20px 28px 40px;
  background: #f5f7fb;
  min-height: 100vh;
  color: #1a2a4a;
}
.rp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.rp-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}
.rp-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #66738a;
}
.rp-add {
  flex: 0 0 auto;
  height: 40px;
  padding: 0 18px;
  border: none;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.rp-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.rp-search {
  flex: 1;
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e9eef6;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
}
.rp-select {
  height: 40px;
  padding: 0 12px;
  border: 1px solid #e9eef6;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  color: #3d4d66;
}
.rp-count {
  font-size: 13px;
  color: #8091a8;
}
.rp-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rp-list.is-loading {
  opacity: 0.6;
}
.rp-row {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #e9eef6;
  border-radius: 14px;
}
.rp-row-main {
  min-width: 0;
  flex: 1;
}
.rp-row-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.rp-name {
  font-size: 15px;
  font-weight: 700;
}
.rp-badge {
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 10px;
}
.rp-badge.on {
  color: #0f9d58;
  background: #e9f7ef;
}
.rp-badge.off {
  color: #8a95a8;
  background: #f1f3f7;
}
.rp-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.rp-tag {
  font-size: 12px;
  color: var(--brand);
  background: var(--brand-soft);
  border-radius: 8px;
  padding: 3px 9px;
}
.rp-tag-cat {
  color: #7a5af8;
  background: #f1edff;
}
.rp-prio {
  font-size: 12px;
  color: #8091a8;
}
.rp-kws {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.rp-kw {
  font-size: 12px;
  color: #52627a;
  background: #f4f6fa;
  border-radius: 6px;
  padding: 2px 8px;
}
.rp-row-actions {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}
.rp-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid #e9eef6;
  border-radius: 9px;
  background: #fff;
  color: #52627a;
  font-size: 13px;
  cursor: pointer;
}
.rp-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.rp-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.rp-btn.primary {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
  font-weight: 600;
}
.rp-btn.ok {
  color: #0f9d58;
}
.rp-btn.danger {
  color: #d93b3b;
}
.rp-empty {
  padding: 48px 0;
  text-align: center;
  color: #8091a8;
  background: #fff;
  border: 1px dashed #e3e9f3;
  border-radius: 14px;
}
.rp-error {
  margin: 10px 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fdecec;
  color: #c22b2b;
  font-size: 13px;
}
.rp-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 18px;
}
.rp-pageinfo {
  font-size: 13px;
  color: #66738a;
}
.rp-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 25, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.rp-dialog {
  width: 520px;
  max-height: 88vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 16px;
  padding: 22px 24px;
  box-shadow: 0 24px 60px rgba(16, 25, 40, 0.22);
}
.rp-dialog-title {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 700;
}
.rp-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #52627a;
}
.rp-field input,
.rp-field select,
.rp-field textarea {
  border: 1px solid #e9eef6;
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 14px;
  color: #1a2a4a;
  font-family: inherit;
}
.rp-field-row {
  display: flex;
  gap: 14px;
}
.rp-field-row .rp-field {
  flex: 1;
}
.rp-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #52627a;
  margin-bottom: 10px;
}
.rp-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.rp-toast {
  position: fixed;
  left: 50%;
  bottom: 40px;
  transform: translateX(-50%);
  padding: 10px 20px;
  border-radius: 10px;
  background: rgba(22, 35, 59, 0.92);
  color: #fff;
  font-size: 13px;
  z-index: 2100;
}
</style>
