<!-- 笔记聚合页 -->
<template>
  <div class="notes-page">
    <NavBar></NavBar>
    <main class="notes-main">
      <div class="notes-header">
        <h2>
          <XIcon :icon="Edit" :size="24" color="#c41e3a"></XIcon>
          <span> 我的笔记</span>
        </h2>
        <div class="notes-stats">
          <span class="stat-item">新闻笔记: {{ state.stats.news_notes }}</span>
          <span class="stat-item">典题笔记: {{ state.stats.question_notes }}</span>
          <span class="stat-item total">总计: {{ state.stats.total }}</span>
        </div>
      </div>

      <div class="tab-bar">
        <div class="tab-item" :class="{ active: state.activeTab === 'news' }" @click="switchTab('news')">
          📰 新闻笔记
        </div>
        <div class="tab-item" :class="{ active: state.activeTab === 'question' }" @click="switchTab('question')">
          📝 典题笔记
        </div>
      </div>

      <div class="notes-content">
        <!-- 新闻笔记列表 -->
        <div v-if="state.activeTab === 'news'" class="note-list">
          <div v-if="state.newsNotes.length === 0" class="empty-state">
            <span class="empty-icon">📝</span>
            <p>暂无新闻笔记，去新闻页面划线记录想法吧！</p>
          </div>
          <div v-for="note in state.newsNotes" :key="note.note_id" class="note-card news-note">
            <div class="note-source">
              <span class="source-icon">📰</span>
              <span class="source-title">{{ note.news_title }}</span>
              <span class="source-from">{{ note.news_source }}</span>
            </div>
            <div v-if="note.quote_text" class="quote-section">
              <div class="quote-label">划线原文:</div>
              <div class="quote-text" :style="{ textDecorationColor: note.color, textDecorationStyle: note.line_style === 'wavy' ? 'wavy' : (note.line_style === 'straight' ? 'solid' : 'none'), background: note.line_style === 'marker' ? note.color : 'transparent' }">
                "{{ note.quote_text }}"
              </div>
            </div>
            <div class="thought-section">
              <div class="thought-label">💬 我的想法:</div>
              <div class="thought-text">{{ note.note_text }}</div>
            </div>
            <div class="note-actions">
              <button class="action-btn edit-btn" @click="startEdit(note, 'news')">编辑</button>
              <button class="action-btn delete-btn" @click="deleteNote(note, 'news')">删除</button>
              <span class="note-time">{{ formatTime(note.update_time) }}</span>
            </div>
          </div>
        </div>

        <!-- 典题笔记列表 -->
        <div v-if="state.activeTab === 'question'" class="note-list">
          <div v-if="state.questionNotes.length === 0" class="empty-state">
            <span class="empty-icon">📝</span>
            <p>暂无典题笔记，在做题时点击"笔记"按钮记录知识点吧！</p>
          </div>
          <div v-for="note in state.questionNotes" :key="note.note_id" class="note-card question-note">
            <div class="note-source">
              <span class="source-icon">📝</span>
              <span class="source-title" v-if="note.knowledge_path">{{ note.knowledge_path }}</span>
              <span class="source-title" v-else>{{ note.subject_name }} > {{ note.subcategory || '通用' }}</span>
              <span class="type-badge" :class="getTypeClass(note.question_type)">{{ note.question_type || '选择题' }}</span>
            </div>
            <div class="question-content-preview">
              <div class="preview-label">来源题目:
                <span class="view-detail-link" @click="showQuestionDetail(note.question_id)">点击查看完整题目 ›</span>
              </div>
              <div class="preview-text" v-html="renderQuestionContent(note.question_content)"></div>
            </div>
            <div class="thought-section">
              <div class="thought-label">📖 笔记内容:</div>
              <div class="thought-text">{{ note.note_text }}</div>
            </div>
            <div class="note-meta-info">
              <span class="meta-item">正确率: {{ note.correct_rate || 0 }}%</span>
              <span class="meta-item">难度: {{ '★'.repeat(note.difficulty || 3) }}</span>
            </div>
            <div class="note-actions">
              <button class="action-btn edit-btn" @click="startEdit(note, 'question')">编辑</button>
              <button class="action-btn delete-btn" @click="deleteNote(note, 'question')">删除</button>
              <span class="note-time">{{ formatTime(note.update_time) }}</span>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="state.total > state.pageSize" class="pagination">
          <button class="page-btn" :disabled="state.page <= 1" @click="prevPage">上一页</button>
          <span class="page-info">{{ state.page }} / {{ totalPages }}</span>
          <button class="page-btn" :disabled="state.page >= totalPages" @click="nextPage">下一页</button>
        </div>
      </div>
    </main>

    <!-- 编辑笔记弹窗 -->
    <div v-if="state.editDialogVisible" class="dialog-overlay" @click.self="closeEditDialog">
      <div class="dialog-box edit-dialog">
        <div class="dialog-header">
          <h3>编辑笔记</h3>
          <button class="dialog-close" @click="closeEditDialog">✕</button>
        </div>
        <div class="dialog-body">
          <textarea
            v-model="state.editNoteText"
            class="edit-textarea"
            placeholder="请输入笔记内容..."
            rows="8"
          ></textarea>
        </div>
        <div class="dialog-footer">
          <button class="dialog-btn cancel-btn" @click="closeEditDialog">取消</button>
          <button class="dialog-btn confirm-btn" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>

    <!-- 题目详情弹窗 -->
    <div v-if="state.detailDialogVisible" class="dialog-overlay" @click.self="closeDetailDialog">
      <div class="dialog-box detail-dialog">
        <div class="dialog-header">
          <h3>题目详情</h3>
          <button class="dialog-close" @click="closeDetailDialog">✕</button>
        </div>
        <div class="dialog-body" v-if="state.questionDetail">
          <!-- 知识点面包屑 -->
          <div class="detail-breadcrumb" v-if="state.questionDetail.knowledge_path">
            <span class="breadcrumb-label">知识点:</span>
            <span class="breadcrumb-path">{{ state.questionDetail.knowledge_path }}</span>
          </div>

          <!-- 题型标签 -->
          <div class="detail-type-row">
            <span class="type-badge" :class="getTypeClass(state.questionDetail.question_type)">
              {{ state.questionDetail.question_type || '选择题' }}
            </span>
            <span class="detail-subject">{{ state.questionDetail.subject_name }}</span>
            <span class="detail-correct-rate">正确率: {{ state.questionDetail.correct_rate || 0 }}%</span>
          </div>

          <!-- 题干 -->
          <div class="detail-section">
            <div class="detail-section-label">题干:</div>
            <div class="detail-content" v-html="renderQuestionContent(state.questionDetail.question_content)"></div>
          </div>

          <!-- 选项 -->
          <div class="detail-section" v-if="state.questionDetail.options && state.questionDetail.options.length">
            <div class="detail-section-label">选项:</div>
            <div class="detail-options">
              <div
                v-for="opt in state.questionDetail.options"
                :key="opt.letter"
                class="detail-option"
                :class="{ 'correct-answer': opt.is_correct }"
              >
                <span class="opt-letter">{{ opt.letter }}</span>
                <span class="opt-text" v-html="renderQuestionContent(opt.text)"></span>
                <span class="correct-mark" v-if="opt.is_correct">✓ 正确答案</span>
              </div>
            </div>
          </div>

          <!-- 答案 -->
          <div class="detail-section">
            <div class="detail-section-label">正确答案:</div>
            <div class="detail-answer">{{ state.questionDetail.answer || '暂无' }}</div>
          </div>

          <!-- 解析 -->
          <div class="detail-section">
            <div class="detail-section-label">答案解析:</div>
            <div class="detail-content" v-html="renderQuestionContent(state.questionDetail.answer_analysis)"></div>
          </div>
        </div>
        <div class="dialog-body" v-else>
          <div class="loading-state">加载中...</div>
        </div>
        <div class="dialog-footer">
          <button class="dialog-btn confirm-btn" @click="closeDetailDialog">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
  import { defineComponent, reactive, computed } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Edit } from '@vtj/icons';
  import { ElMessage, ElMessageBox } from 'element-plus';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { renderQuestionContent } from '@/utils/questionRender';
  import { useNotesStore } from '@/modules/notes/store';
  export default defineComponent({
    name: 'Notes',
    components: { NavBar, XIcon },
    setup(props) {
      const notesStore = useNotesStore();
      const provider = useProvider({ id: 'notes', version: '1785754700000' });
      const state = reactive({
        activeTab: 'news',
        newsNotes: [],
        questionNotes: [],
        stats: { news_notes: 0, question_notes: 0, total: 0 },
        page: 1,
        pageSize: 20,
        total: 0,
        loading: false,
        editDialogVisible: false,
        editNoteText: '',
        editingNote: null,
        editingType: '',
        detailDialogVisible: false,
        questionDetail: null
      });
      return { state, props, provider, notesStore, Edit, renderQuestionContent };
    },
    computed: {
      totalPages() {
        return Math.max(1, Math.ceil(this.state.total / this.state.pageSize));
      }
    },
    mounted() {
      this.loadStats();
      this.loadNotes();
    },
    methods: {
      getJsonHeaders() {
        return window.__VTJ_AUTH__.getJsonHeaders();
      },
      formatTime(iso) {
        if (!iso) return '';
        var d = new Date(iso);
        var pad = function(n) { return String(n).padStart(2, '0'); };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
      },
      getTypeClass(type) {
        if (!type) return 'type-single';
        if (type.indexOf('多选') >= 0) return 'type-multi';
        if (type.indexOf('论述') >= 0) return 'type-discuss';
        if (type.indexOf('写作') >= 0) return 'type-writing';
        if (type.indexOf('案例') >= 0) return 'type-case';
        return 'type-single';
      },
      switchTab(tab) {
        this.state.activeTab = tab;
        this.state.page = 1;
        this.loadNotes();
      },
      async loadStats() {
        try {
          await this.notesStore.loadStats();
          if (this.notesStore.stats) this.state.stats = this.notesStore.stats;
        } catch(e) { console.warn('加载统计失败:', e); }
      },
      async loadNotes() {
        this.state.loading = true;
        try {
          await this.notesStore.load({
            noteType: this.state.activeTab,
            page: this.state.page,
            pageSize: this.state.pageSize
          });
          this.state.total = this.notesStore.notesTotal;
          if (this.state.activeTab === 'news') {
            this.state.newsNotes = this.notesStore.notes;
          } else {
            this.state.questionNotes = this.notesStore.notes;
          }
        } catch(e) { console.warn('加载笔记失败:', e); }
        finally { this.state.loading = false; }
      },
      prevPage() {
        if (this.state.page > 1) { this.state.page--; this.loadNotes(); }
      },
      nextPage() {
        if (this.state.page < this.totalPages) { this.state.page++; this.loadNotes(); }
      },

      // ========== 编辑笔记 ==========
      startEdit(note, type) {
        this.state.editingNote = note;
        this.state.editingType = type;
        this.state.editNoteText = note.note_text || '';
        this.state.editDialogVisible = true;
      },
      closeEditDialog() {
        this.state.editDialogVisible = false;
        this.state.editingNote = null;
        this.state.editNoteText = '';
      },
      async saveEdit() {
        if (!this.state.editNoteText.trim()) {
          ElMessage.warning('笔记内容不能为空');
          return;
        }
        if (!this.state.editingNote) return;

        var noteId = this.state.editingNote.note_id;
        // 典题笔记的 note_id 是纯数字，新闻笔记是 n_xxx 格式
        // 后端 PUT /api/notes/{note_id} 期望 q_xxx 或 n_xxx 格式
        var fullNoteId = this.state.editingType === 'question'
          ? 'q_' + noteId
          : 'n_' + noteId;

        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/notes/' + fullNoteId, {
            method: 'PUT',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({ note_text: this.state.editNoteText.trim() })
          });
          if (res.ok) {
            ElMessage.success('笔记已更新');
            this.closeEditDialog();
            this.loadNotes();
            this.loadStats();
          } else {
            const errData = await res.json().catch(() => ({}));
            ElMessage.error('更新失败: ' + (errData.detail || '服务器错误'));
          }
        } catch(e) {
          console.warn('更新笔记失败:', e);
          ElMessage.error('更新失败: ' + (e.message || '网络错误'));
        }
      },

      // ========== 删除笔记 ==========
      async deleteNote(note, type) {
        try {
          await ElMessageBox.confirm('确定要删除这条笔记吗？删除后不可恢复。', '删除确认', {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning'
          });
        } catch(e) {
          return; // 用户取消
        }

        var noteId = note.note_id;
        var fullNoteId = type === 'question'
          ? 'q_' + noteId
          : 'n_' + noteId;

        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/notes/' + fullNoteId, {
            method: 'DELETE',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            ElMessage.success('笔记已删除');
            this.loadNotes();
            this.loadStats();
          } else {
            const errData = await res.json().catch(() => ({}));
            ElMessage.error('删除失败: ' + (errData.detail || '服务器错误'));
          }
        } catch(e) {
          console.warn('删除笔记失败:', e);
          ElMessage.error('删除失败: ' + (e.message || '网络错误'));
        }
      },

      // ========== 题目详情弹窗 ==========
      async showQuestionDetail(questionId) {
        if (!questionId) return;
        this.state.detailDialogVisible = true;
        this.state.questionDetail = null;

        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/notes/question/' + questionId, {
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            const text = await res.text();
            try {
              this.state.questionDetail = JSON.parse(text);
            } catch(parseErr) {
              // 响应非 JSON：不发起二次请求（原实现会回退到硬编码
              // http://localhost:8000，该地址在生产环境不存在，必然失败）
              console.warn('[notes] 题目详情响应不是合法 JSON:', parseErr);
            }
          } else {
            ElMessage.error('加载题目详情失败');
          }
        } catch(e) {
          console.warn('加载题目详情失败:', e);
          ElMessage.error('加载题目详情失败: ' + (e.message || '网络错误'));
        }
      },
      closeDetailDialog() {
        this.state.detailDialogVisible = false;
        this.state.questionDetail = null;
      }
    }
  });
</script>

<style scoped>
.notes-page {
  font-size: 15px;
  min-height: 100vh;
  background: #f5f7fa;
}
.notes-main {
  max-width: 1400px;
  min-height: 800px;
  margin: 0 auto;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.notes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 2px solid #c41e3a;
}
.notes-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 22px;
  color: #1a3a5c;
  margin: 0;
}
.notes-stats {
  display: flex;
  gap: 16px;
}
.stat-item {
  font-size: 14px;
  color: #666;
  padding: 4px 12px;
  background: #f0f4f8;
  border-radius: 6px;
}
.stat-item.total {
  color: #c41e3a;
  font-weight: 600;
  background: #fff0f0;
}
.tab-bar {
  display: flex;
  gap: 4px;
  margin: 20px 0;
  border-bottom: 1px solid #e8e8e8;
}
.tab-item {
  padding: 10px 24px;
  font-size: 15px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
}
.tab-item:hover { color: #c41e3a; }
.tab-item.active {
  color: #c41e3a;
  border-bottom-color: #c41e3a;
  font-weight: 600;
}
.notes-content { min-height: 500px; }
.note-list { display: flex; flex-direction: column; gap: 16px; }
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}
.empty-icon { font-size: 48px; display: block; margin-bottom: 12px; }
.note-card {
  background: #fafbfc;
  border: 1px solid #e8e8e8;
  border-left: 4px solid #1a3a5c;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;
}
.note-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.question-note { border-left-color: #c41e3a; }
.note-source {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  flex-wrap: wrap;
}
.source-icon { font-size: 18px; }
.source-title { font-weight: 600; color: #1a3a5c; }
.source-from { color: #999; margin-left: auto; }
.type-badge {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 4px;
  font-weight: 600;
  margin-left: 4px;
}
.type-single { background: #e3f2fd; color: #1565c0; }
.type-multi { background: #fff3e0; color: #e65100; }
.type-discuss { background: #f3e5f5; color: #7b1fa2; }
.type-writing { background: #e8f5e9; color: #2e7d32; }
.type-case { background: #fce4ec; color: #c62828; }
.quote-section, .question-content-preview {
  margin-bottom: 12px;
  padding: 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px dashed #e0e0e0;
}
.quote-label, .preview-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.view-detail-link {
  color: #c41e3a;
  cursor: pointer;
  font-size: 12px;
  text-decoration: none;
}
.view-detail-link:hover { text-decoration: underline; }
.quote-text {
  font-size: 14px;
  color: #333;
  font-style: italic;
  padding: 4px 8px;
  text-decoration: underline;
}
.preview-text {
  font-size: 14px;
  color: #555;
  line-height: 1.6;
}
.thought-section { margin-bottom: 8px; }
.thought-label {
  font-size: 13px;
  color: #c41e3a;
  margin-bottom: 4px;
  font-weight: 600;
}
.thought-text {
  font-size: 15px;
  color: #333;
  line-height: 1.7;
  padding: 8px 12px;
  background: #fff8f8;
  border-radius: 6px;
}
.note-meta-info {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #888;
}
.meta-item {
  padding: 2px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}
.note-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.action-btn {
  padding: 4px 12px;
  font-size: 13px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  background: #fff;
  transition: all 0.3s;
}
.edit-btn { color: #1a3a5c; border-color: #1a3a5c; }
.edit-btn:hover { background: #1a3a5c; color: #fff; }
.delete-btn { color: #c41e3a; border-color: #c41e3a; }
.delete-btn:hover { background: #c41e3a; color: #fff; }
.note-time {
  font-size: 12px;
  color: #aaa;
  margin-left: auto;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding: 16px 0;
}
.page-btn {
  padding: 6px 16px;
  font-size: 14px;
  color: #1a3a5c;
  background: #fff;
  border: 1px solid #1a3a5c;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}
.page-btn:hover:not(:disabled) {
  background: #1a3a5c;
  color: #fff;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 14px; color: #666; }

/* ========== 弹窗样式 ========== */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
.dialog-box {
  background: #fff;
  border-radius: 12px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.edit-dialog { width: 500px; }
.detail-dialog { width: 750px; max-width: 90vw; }
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
}
.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1a3a5c;
}
.dialog-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}
.dialog-close:hover { background: #f0f0f0; color: #c41e3a; }
.dialog-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}
.edit-textarea {
  width: 100%;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  font-family: inherit;
}
.edit-textarea:focus {
  outline: none;
  border-color: #c41e3a;
  box-shadow: 0 0 0 2px rgba(196, 30, 58, 0.1);
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid #e8e8e8;
}
.dialog-btn {
  padding: 8px 20px;
  font-size: 14px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #ddd;
  transition: all 0.3s;
}
.cancel-btn { background: #fff; color: #666; }
.cancel-btn:hover { background: #f5f5f5; }
.confirm-btn { background: #c41e3a; color: #fff; border-color: #c41e3a; }
.confirm-btn:hover { background: #a01729; }

/* ========== 题目详情弹窗 ========== */
.loading-state {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 15px;
}
.detail-breadcrumb {
  background: #f0f4f8;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
}
.breadcrumb-label { color: #999; margin-right: 6px; }
.breadcrumb-path { color: #1a3a5c; font-weight: 600; }
.detail-type-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.detail-subject { font-size: 14px; color: #666; }
.detail-correct-rate {
  margin-left: auto;
  font-size: 14px;
  color: #c41e3a;
  font-weight: 600;
}
.detail-section {
  margin-bottom: 20px;
}
.detail-section-label {
  font-size: 14px;
  font-weight: 600;
  color: #1a3a5c;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid #c41e3a;
}
.detail-content {
  font-size: 15px;
  color: #333;
  line-height: 1.8;
  padding: 12px;
  background: #fafbfc;
  border-radius: 6px;
}
.detail-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 8px 0;
}
.detail-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: #fafbfc;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  transition: all 0.3s;
}
.detail-option.correct-answer {
  background: #e8f5e9;
  border-color: #4caf50;
}
.opt-letter {
  font-weight: 700;
  color: #1a3a5c;
  min-width: 20px;
}
.correct-answer .opt-letter { color: #2e7d32; }
.opt-text {
  flex: 1;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
}
.opt-text :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}
.correct-mark {
  font-size: 12px;
  color: #2e7d32;
  font-weight: 600;
  white-space: nowrap;
}
.detail-answer {
  font-size: 18px;
  font-weight: 700;
  color: #c41e3a;
  padding: 8px 12px;
  background: #fff0f0;
  border-radius: 6px;
  display: inline-block;
}
</style>
