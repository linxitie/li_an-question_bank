<template>
  <div class="student-papers">
    <div class="top-nav">
      <span class="nav-logo" @click="$router.push('/')">砺安题库</span>
      <div class="nav-links">
        <span class="nav-tab" @click="$router.push('/')">题库</span>
        <span class="nav-tab active">历年试卷</span>
        <span class="nav-tab" @click="$router.push('/home')">首页</span>
      </div>
      <span class="nav-user">{{ username }}</span>
    </div>

    <div class="page-content">
      <div class="page-header">
        <h2>📋 历年试卷</h2>
        <p class="subtitle">浏览教师发布的历年真题和模拟试卷，选择试卷开始答题</p>
      </div>

      <!-- 筛选工具栏 -->
      <div class="toolbar">
        <select class="filter-select" v-model="filterSubject" @change="loadPapers">
          <option value="">全部科目</option>
          <option value="1">行测</option>
          <option value="2">申论</option>
          <option value="3">公专</option>
        </select>
        <select class="filter-select" v-model="filterExamType" @change="loadPapers">
          <option value="">全部类型</option>
          <option value="SIMULATION">模拟考试</option>
          <option value="PRACTICE">练习</option>
          <option value="FORMAL">正式考试</option>
        </select>
        <select class="filter-select" v-model="filterYear" @change="loadPapers">
          <option value="">全部年份</option>
          <option value="2026">2026</option>
          <option value="2025">2025</option>
          <option value="2024">2024</option>
          <option value="2023">2023</option>
          <option value="2022">2022</option>
          <option value="2021">2021</option>
          <option value="2020">2020</option>
        </select>
        <select class="filter-select" v-model="filterStatus" @change="loadPapers">
          <option value="">全部状态</option>
          <option value="completed">已完成</option>
          <option value="in_progress">进行中</option>
          <option value="not_started">未开始</option>
        </select>
        <input class="search-input" v-model="searchKeyword" placeholder="搜索试卷名称..." @keyup.enter="loadPapers" />
        <button class="btn-search" @click="loadPapers">🔍 搜索</button>
        <div class="toolbar-spacer"></div>
        <button class="btn-back" @click="$router.push('/')">← 返回题库</button>
      </div>

      <!-- 试卷卡片网格 -->
      <div class="papers-grid" v-if="papers.length > 0">
        <div class="paper-card" v-for="p in papers" :key="p.paper_id">
          <div class="card-header">
            <span :class="['type-tag', examTypeClass(p.exam_type)]">{{ examTypeLabel(p.exam_type) }}</span>
            <span class="card-subject">{{ p.subject_name || subjectName(p.subject_id) }}</span>
            <span :class="['status-tag', getPaperStatus(p).cls]">{{ getPaperStatus(p).label }}</span>
          </div>
          <h3 class="card-title">{{ p.paper_name }}</h3>
          <div class="card-stats">
            <span>📝 {{ p.question_count || '?' }} 题</span>
            <span>⏱️ {{ p.duration || '?' }} 分钟</span>
            <span>📊 {{ p.total_score || '?' }} 分</span>
          </div>
          <div v-if="userProgress[p.paper_id] && userProgress[p.paper_id].completed" class="card-score">
            🏆 得分: {{ userProgress[p.paper_id].score }} / {{ userProgress[p.paper_id].maxScore || p.total_score || 100 }}
          </div>
          <div class="card-footer">
            <span class="card-difficulty">{{ '★'.repeat(p.difficulty || 1) }}</span>
            <div class="card-actions">
              <button class="btn-preview" @click.stop="previewPaper(p)">预览</button>
              <button class="btn-start" @click.stop="startExam(p)">开始考试 →</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="empty-state" v-else-if="loaded">
        <p>📭 暂无已发布的试卷</p>
        <p class="empty-hint">教师发布试卷后将在此显示</p>
      </div>

      <!-- 加载状态 -->
      <div class="empty-state" v-else>
        <p>⏳ 正在加载试卷...</p>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <div class="modal-overlay" v-if="showPreviewModal" @click.self="closePreview">
      <div class="modal-content preview-modal">
        <div class="modal-header">
          <h3>{{ currentPreviewPaper.paper_name || '试卷预览' }}</h3>
          <button class="modal-close" @click="closePreview">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="previewLoading" class="preview-loading">⏳ 正在加载预览...</div>
          <div v-else-if="previewQuestions.length === 0" class="preview-empty">暂无题目</div>
          <div v-else class="preview-questions">
            <div v-for="(q, idx) in previewQuestions" :key="q.question_id" class="preview-question">
              <div class="q-header">
                <span class="q-num">{{ idx + 1 }}.</span>
                <span class="q-type">{{ q.question_type || '未知题型' }}</span>
                <span class="q-score">{{ q.score }}分</span>
              </div>
              <div class="q-content" v-html="renderQuestionContent(q.question_content || q.clean_content, { stripInlineOption: true })"></div>
              <div v-if="q.options && q.options.length" class="q-options">
                <div v-for="opt in q.options" :key="opt.key || opt" class="q-option">
                  <span class="opt-key">{{ opt.key || opt }}.</span>
                  <span class="opt-value">{{ opt.value || opt }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useProvider } from '@vtj/renderer';
import { renderQuestionContent } from '@/utils/questionRender';
import { usePapersStore } from '@/modules/papers/store';

export default defineComponent({
  name: 'StudentPapers',
  setup() {
    const provider = useProvider({ id: 'student_papers', version: '1785407000000' });
    const router = useRouter();
    const papersStore = usePapersStore();
    let unbindRefresh: (() => void) | null = null;
    const username = ref('');
    const papers: any = ref([]);
    const filterSubject = ref('');
    const filterExamType = ref('');
    const filterYear = ref('');
    const filterStatus = ref('');
    const searchKeyword = ref('');
    const loaded = ref(false);
    const userProgress: any = ref({});  // {paper_id: {status, score}}

    // 预览弹窗状态
    const showPreviewModal = ref(false);
    const previewLoading = ref(false);
    const currentPreviewPaper: any = ref({});
    const previewQuestions: any = ref([]);

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '';
      await loadPapers();
      unbindRefresh = papersStore.bindRefresh();
      await loadUserProgress();
    });

    onUnmounted(() => {
      if (unbindRefresh) unbindRefresh();
    });

    async function loadPapers() {
      loaded.value = false;
      await papersStore.load({
        pageSize: 50,
        subjectId: filterSubject.value ? Number(filterSubject.value) : undefined,
        examType: filterExamType.value || undefined,
        keyword: searchKeyword.value.trim() || undefined,
      });
      papers.value = papersStore.items;
      loaded.value = true;
    }

    async function loadUserProgress() {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/exams/records?page_size=100');
        const data = await res.json();
        const records = data.data || data || [];
        const progress: any = {};
        records.forEach((r: any) => {
          const pid = r.paper_id;
          if (!progress[pid] || r.is_completed) {
            progress[pid] = {
              completed: !!r.is_completed,
              score: r.total_score,
              maxScore: data.max_score || 100,
            };
          }
        });
        userProgress.value = progress;
      } catch (e) {
        console.error('加载进度失败:', e);
      }
    }

    function subjectName(id: number) {
      const map: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
      return map[id] || '-';
    }

    function examTypeLabel(t: string) {
      const map: Record<string, string> = { SIMULATION: '模拟', PRACTICE: '练习', FORMAL: '正式' };
      return map[t] || t || '模拟';
    }

    function examTypeClass(t: string) {
      const map: Record<string, string> = { SIMULATION: 'tag-sim', PRACTICE: 'tag-practice', FORMAL: 'tag-formal' };
      return map[t] || 'tag-sim';
    }

    function getPaperStatus(p: any) {
      const pId = p.paper_id;
      const prog = userProgress.value[pId];
      if (!prog) return { label: '未开始', cls: 'status-new' };
      if (prog.completed) return { label: '已完成 ✓', cls: 'status-done' };
      return { label: '进行中', cls: 'status-progress' };
    }

    async function startExam(p: any) {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) {
        ElMessage.warning('请先登录后再参加考试');
        router.push('/login');
        return;
      }
      try {
        // 使用统一的新接口 /api/exams/start，paper_id 作为查询参数
        const res = await auth.apiFetch('/api/exams/start?paper_id=' + p.paper_id + '&exam_type=SELF_TEST', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();
        if (data.exam_id) {
          ElMessage.success('考试开始！');
          router.push('/paper-answer?record_id=' + data.exam_id + '&paper_id=' + p.paper_id);
        } else {
          ElMessage.error(data.detail || data.message || '开始考试失败');
        }
      } catch (e: any) {
        ElMessage.error('开始考试失败：' + (e.message || '未知错误'));
      }
    }

    async function previewPaper(p: any) {
      const auth = (window as any).__VTJ_AUTH__;
      showPreviewModal.value = true;
      previewLoading.value = true;
      currentPreviewPaper.value = p;
      previewQuestions.value = [];
      try {
        // 调用预览接口（不含答案）
        const res = await auth.apiFetch('/api/exams/preview/' + p.paper_id);
        const data = await res.json();
        // 后端直接返回数据对象（不含 success 包装），或返回带 success 的包装
        if (data.questions || data.success) {
          currentPreviewPaper.value = data;
          previewQuestions.value = data.questions || [];
        } else {
          ElMessage.error(data.message || data.detail || '预览失败');
        }
      } catch (e: any) {
        ElMessage.error('预览失败：' + (e.message || '未知错误'));
      } finally {
        previewLoading.value = false;
      }
    }

    function closePreview() {
      showPreviewModal.value = false;
      currentPreviewPaper.value = {};
      previewQuestions.value = [];
    }

    return {
      provider, username, papers,
      filterSubject, filterExamType, filterYear, filterStatus, searchKeyword,
      loaded, userProgress,
      loadPapers, loadUserProgress, subjectName, examTypeLabel, examTypeClass,
      getPaperStatus, startExam, previewPaper,
      showPreviewModal, previewLoading, currentPreviewPaper, previewQuestions, closePreview,
      renderQuestionContent,
    };
  }
});

</script>

<style scoped>
.student-papers { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.top-nav { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; cursor: pointer; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.nav-user { font-size: 14px; }
.page-content { max-width: 1100px; margin: 0 auto; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h2 { color: #1A3C6D; margin: 0 0 6px; font-size: 24px; }
.subtitle { color: #909399; margin: 0; font-size: 14px; }

/* 筛选工具栏 */
.toolbar { display: flex; gap: 10px; margin-bottom: 24px; align-items: center; flex-wrap: wrap; }
.toolbar-spacer { flex: 1; }
.filter-select { padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; background: #fff; cursor: pointer; outline: none; }
.filter-select:focus { border-color: #409EFF; }
.search-input { padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; background: #fff; outline: none; min-width: 180px; }
.search-input:focus { border-color: #409EFF; }
.btn-search { padding: 8px 16px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-search:hover { background: #2a4f80; }
.btn-back { padding: 8px 18px; background: #f0f0f0; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }

/* 试卷卡片 */
.papers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }
.paper-card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: transform 0.15s, box-shadow 0.15s; display: flex; flex-direction: column; }
.paper-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.type-tag { padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 500; color: #fff; }
.tag-sim { background: #409EFF; }
.tag-practice { background: #67C23A; }
.tag-formal { background: #E6A23C; }
.card-subject { font-size: 13px; color: #909399; }

/* 状态标签 */
.status-tag { padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 500; margin-left: auto; }
.status-new { background: #f0f2f5; color: #909399; }
.status-progress { background: #fff7e6; color: #e6a23c; }
.status-done { background: #f0f9eb; color: #67c23a; }

.card-title { color: #1A3C6D; margin: 0 0 12px; font-size: 17px; line-height: 1.4; }
.card-stats { display: flex; gap: 16px; margin-bottom: 8px; font-size: 14px; color: #606266; }
.card-score { font-size: 13px; color: #67c23a; font-weight: 600; margin-bottom: 12px; padding: 6px 10px; background: #f0f9eb; border-radius: 6px; }
.card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: auto; }
.card-difficulty { color: #E6A23C; letter-spacing: 2px; }
.card-actions { display: flex; gap: 8px; }
.btn-preview { padding: 8px 16px; background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-preview:hover { background: #f0f4ff; }
.btn-start { padding: 8px 20px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }
.btn-start:hover { background: #2a4f80; }

.empty-state { text-align: center; padding: 80px 0; color: #909399; font-size: 16px; }
.empty-hint { font-size: 14px; color: #c0c4cc; margin-top: 8px; }

/* 预览弹窗 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.preview-modal { background: #fff; border-radius: 12px; width: 90%; max-width: 800px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid #e8e8e8; }
.modal-header h3 { margin: 0; color: #1A3C6D; font-size: 18px; }
.modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #909399; padding: 0 8px; }
.modal-close:hover { color: #333; }
.modal-body { padding: 24px; overflow-y: auto; flex: 1; }
.preview-loading, .preview-empty { text-align: center; padding: 40px; color: #909399; }
.preview-questions { display: flex; flex-direction: column; gap: 20px; }
.preview-question { border: 1px solid #e8e8e8; border-radius: 8px; padding: 16px; }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.q-num { font-weight: 700; color: #1A3C6D; }
.q-type { font-size: 12px; padding: 2px 8px; background: #e8f0fe; color: #1A3C6D; border-radius: 4px; }
.q-score { font-size: 12px; color: #909399; margin-left: auto; }
.q-content { font-size: 15px; line-height: 1.6; color: #333; margin-bottom: 8px; }
.q-options { display: flex; flex-direction: column; gap: 4px; }
.q-option { padding: 6px 10px; background: #f8f9fa; border-radius: 4px; font-size: 14px; }
.opt-key { font-weight: 600; color: #1A3C6D; margin-right: 8px; }
.opt-value { color: #606266; }
</style>
