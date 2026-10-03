<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">我的笔记</h1>
      <span class="spacer"></span>
    </header>

    <div class="tabs">
      <div :class="['tab', { active: noteType === 'all' }]" @click="switchType('all')">全部</div>
      <div :class="['tab', { active: noteType === 'question' }]" @click="switchType('question')">题目笔记</div>
      <div :class="['tab', { active: noteType === 'news' }]" @click="switchType('news')">新闻笔记</div>
    </div>

    <main class="list">
      <div v-for="n in notes" :key="n.note_id" class="card" @click="openNote(n)">
        <div class="note-title">{{ n.title || '（无标题）' }}</div>
        <blockquote v-if="n.quote_text" class="note-quote">{{ n.quote_text }}</blockquote>
        <div class="note-text">{{ n.note_text }}</div>
        <div class="note-meta">
          <span class="tag">{{ n.type === 'question' ? '题目' : '新闻' }}</span>
          <span v-if="n.subject" class="tag">{{ n.subject }}</span>
          <span class="time">{{ formatTime(n.update_time) }}</span>
        </div>
      </div>
      <div v-if="!notes.length && !loading" class="empty">暂无笔记</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 题目笔记详情弹层（页内展示，不再跳转不存在的路由导致 404） -->
    <div v-if="detailVisible" class="modal-mask" @click="closeDetail">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <span class="modal-title">
            {{ detailData ? (detailData.subject_name || '题目') : '' }}
            <template v-if="detailData && detailData.question_type">· {{ detailData.question_type }}</template>
          </span>
          <button class="modal-close" @click="closeDetail" aria-label="关闭">✕</button>
        </div>

        <div class="modal-body">
          <div v-if="detailLoading" class="empty">加载中...</div>
          <div v-else-if="detailError" class="empty">{{ detailError }}</div>
          <template v-else-if="detailData">
            <div class="q-content" v-html="renderQuestionContent(detailData.question_content, { stripInlineOption: true })"></div>
            <div
              v-for="opt in detailData.options"
              :key="opt.letter"
              class="opt-row"
              :class="{ correct: opt.is_correct }"
            >
              <span class="opt-letter">{{ opt.letter }}</span>
              <span class="opt-text" v-html="renderQuestionContent(opt.text)"></span>
              <span v-if="opt.is_correct" class="opt-flag">正确答案</span>
            </div>
            <div v-if="detailData.answer" class="q-answer">参考答案：{{ detailData.answer }}</div>
            <div class="q-analysis" v-html="renderQuestionContent(detailData.answer_analysis)"></div>
            <div class="q-meta">
              <span v-if="detailData.knowledge_path" class="tag">知识点：{{ detailData.knowledge_path }}</span>
              <span v-if="detailData.correct_rate" class="tag">正确率：{{ detailData.correct_rate }}%</span>
              <span v-if="detailData.year" class="tag">{{ detailData.year }}年</span>
            </div>
          </template>
        </div>

        <!-- 笔记编辑区：后端 PUT /api/notes/{note_id} 已存在，此前仅缺前端入口 -->
        <div class="edit-box">
          <div class="edit-label">我的笔记</div>
          <textarea
            v-if="isEditing"
            v-model="editText"
            class="edit-textarea"
            rows="5"
            placeholder="记录你的思路、错因或记忆点……"
          ></textarea>
          <div v-else class="edit-preview">{{ currentNote ? currentNote.note_text : '' }}</div>
        </div>

        <div class="modal-actions">
          <template v-if="isEditing">
            <button class="action-btn primary" :disabled="savingNote" @click="saveCurrentNote">
              {{ savingNote ? '保存中…' : '保存' }}
            </button>
            <button class="action-btn" :disabled="savingNote" @click="cancelEdit">取消</button>
          </template>
          <template v-else>
            <button class="action-btn primary" @click="startEdit">编辑</button>
            <button class="action-btn danger" @click="deleteCurrentNote">删除笔记</button>
            <button class="action-btn" @click="closeDetail">关闭</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';

const router = useRouter();
const noteType = ref('all');
const notes = ref<any[]>([]);
const loading = ref(false);

// ===== 题目笔记详情弹层 =====
// 原实现跳转到 /mobile/notes-question/{id}，该路由从未注册，必然 404。
// 现改为调用已存在的 GET /api/notes/question/{question_id} 在页内弹层展示。
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref('');
const detailData = ref<any>(null);
const currentNote = ref<any>(null);

const closeDetail = () => {
  detailVisible.value = false;
  detailData.value = null;
  detailError.value = '';
  currentNote.value = null;
  isEditing.value = false;
  editText.value = '';
  savingNote.value = false;
};

// ===== 笔记编辑 =====
const isEditing = ref(false);
const editText = ref('');
const savingNote = ref(false);

const startEdit = () => {
  if (!currentNote.value) return;
  editText.value = currentNote.value.note_text || '';
  detailError.value = '';
  isEditing.value = true;
};

const cancelEdit = () => {
  isEditing.value = false;
  editText.value = '';
  detailError.value = '';
};

const saveCurrentNote = async () => {
  const n = currentNote.value;
  if (!n || n.note_id == null || savingNote.value) return;
  const text = (editText.value || '').trim();
  if (!text) {
    detailError.value = '笔记内容不能为空';
    return;
  }
  savingNote.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/notes/' + n.note_id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note_text: text })
    });
    if (res.ok) {
      // 就地更新：详情弹层与列表保持一致，无需整页刷新
      n.note_text = text;
      notes.value = notes.value.map((x) => (x.note_id === n.note_id ? { ...x, note_text: text } : x));
      isEditing.value = false;
      editText.value = '';
    } else {
      detailError.value = '保存失败（' + res.status + '）';
    }
  } catch (e) {
    detailError.value = '保存失败，请稍后重试';
  } finally {
    savingNote.value = false;
  }
};

const loadQuestionDetail = async (questionId: number) => {
  detailLoading.value = true;
  detailError.value = '';
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/notes/question/' + questionId);
    if (res.ok) {
      detailData.value = await res.json();
    } else {
      detailError.value = '题目加载失败（' + res.status + '）';
    }
  } catch (e) {
    detailError.value = '题目加载失败，请检查网络后重试';
  } finally {
    detailLoading.value = false;
  }
};

const deleteCurrentNote = async () => {
  const n = currentNote.value;
  if (!n || n.note_id == null) return;
  if (!window.confirm('确定删除这条笔记吗？')) return;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/notes/' + n.note_id, {
      method: 'DELETE'
    });
    if (res.ok) {
      closeDetail();
      notes.value = notes.value.filter((x) => x.note_id !== n.note_id);
    } else {
      detailError.value = '删除失败（' + res.status + '）';
    }
  } catch (e) {
    detailError.value = '删除失败，请稍后重试';
  }
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const formatTime = (iso: string) => {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString();
};

const switchType = (t: string) => {
  noteType.value = t;
  fetchNotes();
};

const openNote = async (n: any) => {
  // 新闻笔记跳新闻详情（该路由已注册）
  if (n.type === 'news' && n.news_id) {
    router.push('/mobile/news/' + n.news_id);
    return;
  }
  // 题目笔记：原实现跳 /mobile/notes-question/{id}，该路由从未注册，必然 404。
  // 改为调用已存在的 GET /api/notes/question/{question_id}，在页内弹层展示。
  if (n.type === 'question' && n.question_id) {
    currentNote.value = n;
    detailData.value = null;
    detailVisible.value = true;
    await loadQuestionDetail(n.question_id);
  }
};

const fetchNotes = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/notes?note_type=' + noteType.value);
    const data = await res.json();
    if (res.ok && data.items) notes.value = data.items;
  } catch (e) {
    console.error('获取笔记失败:', e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchNotes);
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 7px 0;
  border-radius: 8px;
  font-size: 13px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.tab.active {
  background: #1a2b5f;
  color: #fff;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.note-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.4;
  margin-bottom: 6px;
}
.note-quote {
  margin: 0 0 6px;
  padding: 4px 8px;
  font-size: 13px;
  color: #5a6488;
  background: #f8f9fc;
  border-radius: 4px;
}
.note-text {
  font-size: 14px;
  color: #1a2a3a;
  line-height: 1.6;
  margin-bottom: 8px;
}
.note-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}
.tag {
  font-size: 11px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 2px 8px;
  border-radius: 6px;
}
.time {
  font-size: 11px;
  color: #8899aa;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}

/* ===== 题目笔记详情弹层 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
}
.modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 560px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
}
.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
}
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  padding: 4px 8px;
  min-width: 44px;
  min-height: 44px;
}
.modal-body {
  padding: 16px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  flex: 1;
}
.q-content {
  font-size: 15px;
  line-height: 1.7;
  color: #1a2a3a;
  margin-bottom: 12px;
}
.opt-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 14px;
}
.opt-row.correct {
  border-color: #52c41a;
  background: #f6ffed;
}
.opt-letter {
  font-weight: 600;
  color: #1a2b5f;
  flex-shrink: 0;
}
.opt-text {
  flex: 1;
  line-height: 1.6;
}
.opt-flag {
  font-size: 11px;
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  padding: 1px 6px;
  flex-shrink: 0;
}
.q-answer {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 12px 0 8px;
}
.q-analysis {
  font-size: 13px;
  line-height: 1.7;
  color: #5a6488;
  margin-bottom: 12px;
}
.q-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.modal-actions {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
}
.action-btn {
  flex: 1;
  min-height: 44px;
  border: 1px solid #1a2b5f;
  background: #1a2b5f;
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.action-btn.danger {
  background: #fff;
  color: #c41e3a;
  border-color: #ffccc7;
}
.action-btn:active {
  opacity: 0.85;
}

/* ===== 笔记编辑 ===== */
.edit-box {
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
}
.edit-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.edit-textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 96px;
  padding: 10px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  background: #fff;
  resize: vertical;
  font-family: inherit;
}
.edit-textarea:focus {
  outline: none;
  border-color: #1a2b5f;
}
.edit-preview {
  padding: 10px 12px;
  background: #f5f7fa;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 40px;
}
/* 主按钮：仅强调“编辑/保存”，删除仍走 danger 白底红字，避免误触 */
.action-btn.primary {
  background: #1a2b5f;
  color: #fff;
}
.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
