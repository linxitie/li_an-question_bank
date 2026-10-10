<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap">
      <div class="sk-bar"></div>
      <div class="sk-table"></div>
    </div>
    <div v-else>
      <div class="action-bar">
        <h2 class="page-title">📋 题库管理</h2>
        <div class="action-buttons">
          <button class="btn-refresh" @click="load">🔄 刷新</button>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-cards">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总题目数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.xingce }}</div>
          <div class="stat-label">行测</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.shenlun }}</div>
          <div class="stat-label">申论</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.gongzhuan }}</div>
          <div class="stat-label">公专</div>
        </div>
        <div class="stat-card stat-warning">
          <div class="stat-value">{{ stats.pending }}</div>
          <div class="stat-label">待审核</div>
        </div>
      </div>

      <!-- 筛选区 -->
      <div class="filter-bar">
        <select class="filter-select" v-model="filters.subject_id" @change="load">
          <option value="">全部科目</option>
          <option value="1">行测</option>
          <option value="2">申论</option>
          <option value="3">公专</option>
        </select>
        <select class="filter-select" v-model="filters.type_id" @change="load">
          <option value="">全部类型</option>
          <option v-for="t in typeOptions" :key="t.type_id" :value="t.type_id">{{ t.type_name }}</option>
        </select>
        <select class="filter-select" v-model="filters.audit_status" @change="load">
          <option value="">全部状态</option>
          <option value="0">待审核</option>
          <option value="1">已通过</option>
          <option value="2">已驳回</option>
        </select>
        <input class="filter-input" v-model="filters.keyword" placeholder="搜索题目内容" @keyup.enter="load"/>
        <button class="btn-search" @click="load">🔍 查询</button>
        <button class="btn-reset" @click="resetFilter">🔄 重置</button>
      </div>

      <!-- 题目列表 -->
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>科目</th>
              <th>题目内容</th>
              <th>题型</th>
              <th>难度</th>
              <th>来源</th>
              <th>审核状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="q in questionList" :key="q.question_id">
              <td>{{ q.question_id }}</td>
              <td>
                <span class="tag">{{ q.subject_name || subjectName(q.subject_id) }}</span>
              </td>
              <td class="content-cell">
                <span class="content-link" @click="previewQuestion(q)">
                  {{ renderSummary(q) }}
                </span>
              </td>
              <td>
                <span :class="['type-badge', typeBadgeClass(q.type_name)]">{{ typeDisplayName(q.type_name) }}</span>
              </td>
              <td>
                <span class="stars">{{ '★'.repeat(q.difficulty || 0) }}{{ '☆'.repeat(5 - (q.difficulty || 0)) }}</span>
              </td>
              <td>{{ q.source || '未标注' }}</td>
              <td>
                <span class="status-badge" :class="'audit-' + q.audit_status">
                  {{ {0:'待审核',1:'已通过',2:'已驳回'}[q.audit_status] || '未知' }}
                </span>
              </td>
              <td class="actions">
                <button class="btn-icon" @click="previewQuestion(q)" title="预览">👁️</button>
                <button class="btn-icon" @click="editQuestion(q)" title="编辑">✏️</button>
                <button v-if="q.audit_status === 0" class="btn-icon btn-success" @click="auditPass(q)" title="通过">✅</button>
                <button v-if="q.audit_status === 0" class="btn-icon btn-danger" @click="showRejectDialog(q)" title="驳回">❌</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!questionList.length" class="empty-state">
          <div class="empty-icon">📋</div>
          <div>暂无题目数据</div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="total > 0">
        <button class="btn-page" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button class="btn-page" :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <div class="modal-overlay" v-if="showPreviewModal" @click.self="showPreviewModal = false">
      <div class="modal-content modal-xlarge">
        <h3>题目预览</h3>
        <div class="preview-section">
          <div class="preview-tags">
            <span class="tag">ID: {{ previewData.question_id }}</span>
            <span class="tag tag-info">{{ previewData.subject_name || subjectName(previewData.subject_id) }}</span>
            <span :class="['type-badge', typeBadgeClass(previewData.type_name)]">{{ typeDisplayName(previewData.type_name) }}</span>
            <span class="status-badge" :class="'audit-' + previewData.audit_status">
              {{ {0:'待审核',1:'已通过',2:'已驳回'}[previewData.audit_status] }}
            </span>
          </div>
          <!-- P1-2: 复合题共享材料（预览复合题小题时展示） -->
          <div class="preview-block" v-if="groupInfo && groupInfo.shared_content">
            <h4>📖 题组材料</h4>
            <div class="preview-content group-material" v-html="renderQuestionContent(groupInfo.shared_content)"></div>
          </div>
          <div class="preview-block" v-if="previewData.group_members && previewData.group_members.length">
            <h4>📝 题组小题</h4>
            <div v-for="(m, mi) in previewData.group_members" :key="mi"
                 style="margin:8px 0;padding:10px;background:#f7f8fa;border-radius:6px;border:1px solid #eee;">
              <div style="font-weight:600;color:#333;margin-bottom:6px;">
                第 {{ m.question_number || (mi + 1) }} 题
                <span v-if="m.question_type_detail" style="font-weight:400;color:#999;font-size:13px;margin-left:8px;">{{ m.question_type_detail }}</span>
              </div>
              <div style="color:#444;line-height:1.7;" v-html="renderQuestionContent(m.question_content)"></div>
              <div v-if="m.options && m.options.length" style="color:#666;margin-top:4px;line-height:1.7;">
                <div v-for="o in m.options" :key="o.key" style="margin-left:8px;">
                  <span style="font-weight:600;">{{ o.key }}.</span> <span v-html="renderQuestionContent(o.value)"></span>
                </div>
              </div>
              <div v-if="m.answer" style="margin-top:6px;color:#16a34a;"><strong>答案：</strong>{{ m.answer }}</div>
              <div v-if="m.answer_analysis" style="margin-top:4px;color:#666;"><strong>解析：</strong><span v-html="renderQuestionContent(m.answer_analysis)"></span></div>
            </div>
          </div>
          <div class="preview-block">
            <h4>题目内容</h4>
            <div class="preview-content" v-html="cleanHtmlContent(previewData.full_content || previewData.question_content)"></div>
          </div>
          <div class="preview-block" v-if="hasOptions(previewData.options)">
            <h4>选项</h4>
            <div v-for="(opt, key) in parsedOptions(previewData.options)" :key="key" class="option-item">
              <span class="option-label">{{ key }}.</span>
              <span class="option-value" v-html="cleanHtmlContent(opt)"></span>
            </div>
          </div>
          <div class="preview-block">
            <h4>正确答案</h4>
            <div class="preview-answer">{{ previewData.answer }}</div>
          </div>
          <div class="preview-block" v-if="previewData.answer_analysis">
            <h4>答案解析</h4>
            <div class="preview-analysis" v-html="cleanHtmlContent(previewData.answer_analysis)"></div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showPreviewModal = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div class="modal-content modal-xlarge">
        <h3>编辑题目</h3>
        <div class="form-grid">
          <div class="fg">
            <label>科目</label>
            <select class="fi" v-model="editForm.subject_id">
              <option value="1">行测</option>
              <option value="2">申论</option>
              <option value="3">公专</option>
            </select>
          </div>
          <div class="fg">
            <label>题型</label>
            <select class="fi" v-model="editForm.type_id">
              <option value="1">单选题</option>
              <option value="3">多选题</option>
              <option value="5">判断题</option>
              <option value="2">论述题</option>
              <option value="4">写作题</option>
            </select>
          </div>
        </div>
        <div class="fg">
          <label>题目内容</label>
          <textarea class="fi textarea" v-model="editForm.question_content" rows="4"></textarea>
        </div>
        <div class="fg">
          <label>选项（JSON 格式，如 [{"key":"A","value":"选项内容"}]）</label>
          <textarea class="fi textarea" v-model="editForm.options_text" rows="4"></textarea>
        </div>
        <div class="fg">
          <label>正确答案</label>
          <input class="fi" v-model="editForm.answer"/>
        </div>
        <div class="fg">
          <label>答案解析</label>
          <textarea class="fi textarea" v-model="editForm.answer_analysis" rows="3"></textarea>
        </div>
        <div class="form-grid">
          <div class="fg">
            <label>难度 (1-5)</label>
            <input class="fi" v-model="editForm.difficulty" type="number" min="1" max="5"/>
          </div>
          <div class="fg">
            <label>来源</label>
            <input class="fi" v-model="editForm.source"/>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEditModal = false">取消</button>
          <button class="btn-primary" @click="submitEdit">保存修改</button>
        </div>
      </div>
    </div>

    <!-- 驳回弹窗 -->
    <div class="modal-overlay" v-if="showRejectModal" @click.self="showRejectModal = false">
      <div class="modal-content">
        <h3>驳回原因</h3>
        <div class="fg">
          <label>选择原因</label>
          <select class="fi" v-model="rejectForm.reason_type">
            <option value="">请选择</option>
            <option value="内容有误">题目内容有误</option>
            <option value="选项问题">选项不正确</option>
            <option value="解析问题">解析不准确</option>
            <option value="重复题目">重复题目</option>
            <option value="其他">其他原因</option>
          </select>
        </div>
        <div class="fg">
          <label>详细说明（可选）</label>
          <textarea class="fi textarea" v-model="rejectForm.comment" rows="3" placeholder="请输入详细说明"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showRejectModal = false">取消</button>
          <button class="btn-danger" @click="submitReject">确认驳回</button>
        </div>
      </div>
    </div>

    <div class="msg" v-if="msg">{{ msg }}</div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
import { renderQuestionContent } from '@/utils/questionRender';

export default defineComponent({
  name: 'AdminQuestions',
  setup() {
    const provider = useProvider({ id: 'admin_questions', version: '1' });
    const loading = ref(true);
    const questionList = ref<any[]>([]);
    const total = ref(0);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const totalPages = ref(1);
    const msg = ref('');
    const showPreviewModal = ref(false);
    const showEditModal = ref(false);
    const showRejectModal = ref(false);

    const stats = ref({
      total: 0, xingce: 0, shenlun: 0, gongzhuan: 0, pending: 0
    });

    const filters = ref({
      subject_id: '',
      type_id: '',
      audit_status: '',
      keyword: ''
    });

    // 题型筛选项（按 type_name 去重；"单选题"历史错位为 type_id=1 和 3，筛选时后端会同时命中）
    const typeOptions = ref([
      { type_id: 1, type_name: '单选题' },
      { type_id: 4, type_name: '多选题' },
      { type_id: 5, type_name: '判断题' },
      { type_id: 2, type_name: '论述题' },
      { type_id: 6, type_name: '写作题' },
      { type_id: 7, type_name: '简述题' },
    ]);

    const previewData = ref<any>({});
    // P1-2: 题组聚合材料缓存（预览复合题小题时展示共享材料）
    const groupInfo = ref<any>(null);
    const editForm = ref({
      question_id: null,
      subject_id: '1',
      type_id: '',
      question_content: '',
      options_text: '',
      answer: '',
      answer_analysis: '',
      difficulty: 3,
      source: ''
    });
    const rejectForm = ref({
      question_id: null,
      reason_type: '',
      comment: ''
    });

    const auth = () => (window as any).__VTJ_AUTH__;

    // ========== 对标教师端的工具函数 ==========

    function subjectName(id: number) {
      const map: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
      return map[id] || '-';
    }

    function typeDisplayName(typeInfo: any) {
      if (!typeInfo) return '-';
      const s = String(typeInfo);
      const nameMap: Record<string, string> = {
        '单选题': '单选题', '多选题': '多选题', '判断题': '判断题', '论述题': '论述题', '写作题': '写作题',
      };
      return nameMap[s] || s;
    }

    function typeBadgeClass(typeInfo: any) {
      const name = typeDisplayName(typeInfo);
      const map: Record<string, string> = {
        '单选题': 'badge-single', '多选题': 'badge-multi',
        '判断题': 'badge-judge',
        '论述题': 'badge-essay', '写作题': 'badge-writing',
      };
      return map[name] || 'badge-single';
    }

    // 清洗 HTML：移除 UTB ID、题号前缀（域内预处理），
    // 最终清洗统一委托 src/utils/questionRender.js 的 renderQuestionContent（单一真源），
    // 与 teacher_questions.vue 的 cleanHtmlContent 保持同一范式，避免出现第二套清洗语义。
    function cleanHtmlContent(text: string) {
      if (!text) return '';
      let cleaned = text;
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*/gi, '');
      cleaned = cleaned.replace(/第\s*\d+\s*题[：:]\s*/g, '');
      // 统一走共享渲染：负责 [IMAGE:标记] 转 <img>、白名单过滤与图片加载失败兜底
      return renderQuestionContent(cleaned);
    }

    function renderSummary(q: any) {
      const text = q.question_content || '';
      // 图片占位符转文字，避免列表摘要显示长路径
      let cleaned = text.replace(/<img[^>]*\/?>/g, '[图片]');
      cleaned = cleaned.replace(/\[IMAGE:[^\]]+\]/g, '[图片]');
      return cleaned;
    }

    function hasOptions(opts: any) {
      if (!opts) return false;
      if (Array.isArray(opts) && opts.length > 0) return true;
      if (typeof opts === 'object' && Object.keys(opts).length > 0) return true;
      if (typeof opts === 'string') {
        try { const p = JSON.parse(opts); return Array.isArray(p) && p.length > 0; } catch(e) { return false; }
      }
      return false;
    }

    function parsedOptions(opts: any) {
      if (!opts) return {};
      if (Array.isArray(opts)) {
        const result: Record<string, string> = {};
        opts.forEach((o: any, i: number) => {
          const key = (o && o.key) || String.fromCharCode(65 + i);
          if (typeof o === 'object') result[key] = o.value || o.text || '';
          else result[key] = String(o);
        });
        return result;
      }
      if (typeof opts === 'object') {
        // 已是 {A: "...", B: "..."} 形式
        const result: Record<string, string> = {};
        Object.keys(opts).forEach(k => { result[k] = opts[k]; });
        return result;
      }
      if (typeof opts === 'string') {
        try { return parsedOptions(JSON.parse(opts)); } catch(e) { return {}; }
      }
      return {};
    }

    onMounted(() => {
      load();
      loadStats();
    });

    async function load() {
      loading.value = true;
      try {
        const params = new URLSearchParams({
          page: currentPage.value.toString(),
          page_size: pageSize.value.toString()
        });
        if (filters.value.subject_id) params.append('subject_id', filters.value.subject_id);
        if (filters.value.type_id !== '') params.append('type_id', filters.value.type_id);
        if (filters.value.audit_status !== '') params.append('audit_status', filters.value.audit_status);
        if (filters.value.keyword) params.append('keyword', filters.value.keyword);

        const r = await auth().apiFetch('/api/admin/questions?' + params.toString());
        const d = await r.json();
        if (d.success) {
          questionList.value = d.items || [];
          total.value = d.total || 0;
          totalPages.value = Math.ceil(total.value / pageSize.value);
        }
      } catch (e) {
        console.error('加载题目列表失败:', e);
      }
      loading.value = false;
    }

    async function loadStats() {
      try {
        const r = await auth().apiFetch('/api/admin/questions/stats');
        const d = await r.json();
        if (d.success) {
          stats.value = d;
        }
      } catch (e) {
        console.error('加载统计数据失败:', e);
      }
    }

    function resetFilter() {
      filters.value = { subject_id: '', type_id: '', audit_status: '', keyword: '' };
      currentPage.value = 1;
      load();
    }

    function changePage(page: number) {
      currentPage.value = page;
      load();
    }

    function previewQuestion(q: any) {
      previewData.value = { ...q };
      groupInfo.value = null;
      showPreviewModal.value = true;
      // P1-2: 复合题小题 → 拉取题组聚合（共享材料）
      if (q.group_id) {
        auth().apiFetch('/api/questions/group/' + q.group_id)
          .then(function(r) { return r.json(); })
          .then(function(d) {
            if (d && d.group) {
              groupInfo.value = d.group;
              previewData.value.group_members = d.members || [];
            }
          })
          .catch(function() { /* 静默：材料加载失败不影响预览 */ });
      }
    }

    function editQuestion(q: any) {
      editForm.value = {
        question_id: q.question_id,
        subject_id: String(q.subject_id),
        type_id: q.type_id,
        question_content: q.full_content || q.question_content,
        options_text: typeof q.options === 'string' ? q.options : JSON.stringify(q.options || []),
        answer: q.answer,
        answer_analysis: q.answer_analysis || '',
        difficulty: q.difficulty || 3,
        source: q.source || ''
      };
      showEditModal.value = true;
    }

    async function submitEdit() {
      try {
        // 解析选项 JSON，转换失败则不传 options
        let options = null;
        if (editForm.value.options_text && editForm.value.options_text.trim()) {
          try {
            options = JSON.parse(editForm.value.options_text);
          } catch (e) {
            msg.value = '❌ 选项 JSON 格式错误，请检查';
            setTimeout(() => msg.value = '', 3000);
            return;
          }
        }
        const data: any = {
          subject_id: parseInt(editForm.value.subject_id),
          type_id: editForm.value.type_id,
          question_content: editForm.value.question_content,
          answer: editForm.value.answer,
          answer_analysis: editForm.value.answer_analysis,
          difficulty: editForm.value.difficulty,
          source: editForm.value.source
        };
        if (options !== null) data.options = options;

        const r = await auth().apiFetch('/api/admin/questions/' + editForm.value.question_id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 题目已更新';
          showEditModal.value = false;
          load();
        } else {
          msg.value = '❌ ' + (d.message || '更新失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 更新失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function auditPass(q: any) {
      if (!confirm('确定通过题目 ' + q.question_id + ' 的审核吗？')) return;
      try {
        const r = await auth().apiFetch('/api/admin/questions/' + q.question_id + '/audit', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_status: 1, audit_comment: '审核通过' })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 审核通过';
          load();
          loadStats();
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 操作失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    function showRejectDialog(q: any) {
      rejectForm.value = { question_id: q.question_id, reason_type: '', comment: '' };
      showRejectModal.value = true;
    }

    async function submitReject() {
      if (!rejectForm.value.reason_type) {
        msg.value = '❌ 请选择驳回原因';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      try {
        const comment = rejectForm.value.reason_type + (rejectForm.value.comment ? '：' + rejectForm.value.comment : '');
        const r = await auth().apiFetch('/api/admin/questions/' + rejectForm.value.question_id + '/audit', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_status: 2, audit_comment: comment })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 已驳回';
          showRejectModal.value = false;
          load();
          loadStats();
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 操作失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    return {
      provider, loading, questionList, total, currentPage, totalPages,
      stats, filters, typeOptions, msg, showPreviewModal, showEditModal, showRejectModal,
      previewData, groupInfo, editForm, rejectForm,
      load, resetFilter, changePage, previewQuestion, editQuestion,
      submitEdit, auditPass, showRejectDialog, submitReject,
      subjectName, typeDisplayName, typeBadgeClass, cleanHtmlContent, renderSummary,
      hasOptions, parsedOptions, renderQuestionContent
    };
  }
});
</script>

<style scoped>
.admin-content { padding: 20px; }
.skeleton-wrap { display: flex; flex-direction: column; gap: 20px; }
.sk-bar, .sk-table {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: sk 1.5s infinite;
  border-radius: 10px;
}
.sk-bar { height: 60px; }
.sk-table { height: 400px; }
@keyframes sk { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.action-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; color: #1A3C6D; }
.action-buttons { display: flex; gap: 10px; }

.stats-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 20px; }
.stat-card {
  background: #fff; border-radius: 12px; padding: 16px; text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.stat-value { font-size: 28px; font-weight: bold; color: #1a2b5f; }
.stat-label { color: #909399; font-size: 14px; margin-top: 4px; }
.stat-warning .stat-value { color: #e6a23c; }

.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-input { flex: 1; min-width: 150px; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; }

.table-container { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 16px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.data-table tr:hover { background: #f5f7fa; }

.content-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.content-link { color: #1a2b5f; cursor: pointer; }
.content-link:hover { text-decoration: underline; }

.tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f0f9eb; color: #67C23A; }
.tag-info { background: #ecf5ff; color: #409eff; }

/* 题型彩色徽章（对标教师端） */
.type-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 13px; font-weight: 500; color: #fff; }
.badge-single { background: #409EFF; }
.badge-multi { background: #67C23A; }
.badge-judge { background: #8B5CF6; }
.badge-essay { background: #E6A23C; }
.badge-writing { background: #F56C6C; }

.stars { color: #f7ba2a; font-size: 12px; }

.status-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
.audit-0 { background: #fff7e6; color: #fa8c16; }
.audit-1 { background: #f6ffed; color: #52c41a; }
.audit-2 { background: #fff2f0; color: #ff4d4f; }

.actions { display: flex; gap: 4px; }
.btn-icon { width: 28px; height: 28px; border: none; background: transparent; cursor: pointer; border-radius: 4px; font-size: 14px; }
.btn-icon:hover { background: #f0f0f0; }
.btn-success:hover { background: #f6ffed; }
.btn-danger:hover { background: #fff2f0; }

.empty-state { text-align: center; padding: 60px 20px; color: #999; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }

.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; padding: 16px; }
.page-info { color: #666; font-size: 14px; }

.btn-primary { padding: 8px 16px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-secondary { padding: 8px 16px; background: #fff; color: #333; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-danger { padding: 8px 16px; background: #f56c6c; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-refresh { padding: 8px 16px; background: #fff; color: #666; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-search { padding: 8px 16px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-reset { padding: 8px 16px; background: #fff; color: #666; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-page { padding: 6px 12px; background: #fff; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; cursor: pointer; }
.btn-page:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 24px; min-width: 400px; max-width: 90vw; max-height: 80vh; overflow-y: auto; }
.modal-large { min-width: 600px; }
.modal-xlarge { min-width: 800px; }
.modal-content h3 { margin: 0 0 20px; color: #1A3C6D; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }

.preview-section { margin-bottom: 20px; }
.preview-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
.preview-block { margin-bottom: 16px; }
.preview-block h4 { margin-bottom: 8px; color: #303133; }
.preview-content, .preview-answer, .preview-analysis {
  padding: 12px; background: #f5f7fa; border-radius: 6px; line-height: 1.8;
}
.preview-content img, .preview-analysis img { max-width: 100%; height: auto; border-radius: 6px; display: block; margin: 8px 0; }
.option-item { display: flex; gap: 8px; padding: 8px; background: #fafafa; border-radius: 4px; margin-bottom: 4px; }
.option-label { font-weight: bold; color: #1a2b5f; }
.option-value img { max-width: 100%; height: auto; display: block; }

.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.fg { margin-bottom: 12px; }
.fg label { display: block; margin-bottom: 6px; font-weight: 500; color: #333; }
.fi { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.fi.textarea { min-height: 80px; resize: vertical; }

.msg { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 12px 24px; background: #f0f9eb; color: #67C23A; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 2000; }
</style>
