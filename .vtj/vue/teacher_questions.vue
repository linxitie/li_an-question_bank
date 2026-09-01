<template>
  <div class="teacher-questions">
    <TeacherNavHeader activeNav="questions" @logout="handleLogout" />

    <div class="page-content">
      <!-- 操作栏 -->
      <div class="toolbar">
        <input class="search-input" v-model="keyword" placeholder="搜索题干关键词..." @keyup.enter="doSearch" />
        <select class="filter-select" v-model="filterSubject" @change="doSearch">
          <option value="">全部科目</option>
          <option :value="1">行测</option>
          <option :value="2">申论</option>
          <option :value="3">公专</option>
        </select>
        <select class="filter-select" v-model="filterType" @change="doSearch">
          <option value="">全部题型</option>
          <option value="单选题">单选题</option>
          <option value="多选题">多选题</option>
          <option value="论述题">论述题</option>
          <option value="写作题">写作题</option>
        </select>
        <select class="filter-select" v-model="filterDifficulty" @change="doSearch">
          <option value="">全部难度</option>
          <option :value="1">★</option>
          <option :value="2">★★</option>
          <option :value="3">★★★</option>
          <option :value="4">★★★★</option>
          <option :value="5">★★★★★</option>
        </select>
        <button class="btn-search" @click="doSearch">搜索</button>
        <div class="toolbar-spacer"></div>
        <button class="btn-import" @click="goImport">📤 题目导入</button>
      </div>

      <!-- 题目表格 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:60px">序号</th>
              <th>题干摘要</th>
              <th style="width:70px">科目</th>
              <th style="width:90px">题型</th>
              <th style="width:80px">难度</th>
              <th style="width:90px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(q, index) in questions" :key="q.question_id" :class="{ 'has-image': hasImage(q.question_content) }">
              <td class="td-seq">{{ (page - 1) * pageSize + index + 1 }}</td>
              <td class="td-content" @click="showDetail(q)" v-html="renderSummary(q)"></td>
              <td>{{ subjectName(q.subject_id) }}</td>
              <td>
                <span :class="['type-badge', typeBadgeClass(q.type_name)]">
                  {{ typeDisplayName(q.type_name) }}
                </span>
                <span v-if="q.group_id" class="group-badge" title="复合题小题（点击详情查看题组材料）">📑</span>
              </td>
              <td class="td-stars">{{ renderStars(q.difficulty) }}</td>
              <td class="td-actions">
                <button class="btn-action" @click="openEdit(q)" title="编辑">✏️</button>
                <button class="btn-action btn-danger" @click="deleteQuestion(q.question_id)" title="删除">🗑️</button>
                <span v-if="!q.answer_analysis" class="missing-analysis-badge" title="缺少答案解析">📝</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <button :disabled="page <= 1" @click="changePage(page - 1)">◀</button>
        <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button :disabled="page >= totalPages" @click="changePage(page + 1)">▶</button>
      </div>
    </div>

    <!-- 题目详情弹窗 -->
    <div class="modal-overlay" v-if="showDetailModal" @click.self="showDetailModal = false">
      <div class="modal-content detail-modal">
        <div class="modal-header">
          <h3>题目详情</h3>
          <span :class="['type-badge', 'type-badge-lg', typeBadgeClass(currentQuestion.type_name)]">
            {{ typeDisplayName(currentQuestion.type_name) }}
          </span>
        </div>

        <div class="detail-field">
          <strong>科目：</strong>
          <span>{{ subjectName(currentQuestion.subject_id) }}</span>
          <strong style="margin-left:16px">难度：</strong>
          <span>{{ renderStars(currentQuestion.difficulty) }}</span>
          <strong style="margin-left:16px">正确率：</strong>
          <span :class="{ 'high-rate': (currentQuestion.accuracy_rate || 0) >= 70, 'low-rate': (currentQuestion.accuracy_rate || 0) < 40 }">
            {{ currentQuestion.accuracy_rate ? currentQuestion.accuracy_rate + '%' : '暂无数据' }}
          </span>
        </div>

        <div class="detail-field" v-if="groupInfo && groupInfo.shared_content">
          <strong>📑 题组材料：</strong>
          <div class="detail-content group-material" v-html="cleanHtmlContent(groupInfo.shared_content)"></div>
        </div>

        <div class="detail-field">
          <strong>题干：</strong>
          <div class="detail-content" v-html="processImagePaths(cleanHtmlContent(currentQuestion.full_content || currentQuestion.question_content))"></div>
        </div>

        <div class="detail-field" v-if="extractImages(currentQuestion.full_content || currentQuestion.question_content).length > 0">
          <strong>图片：</strong>
          <div class="detail-images">
            <img v-for="(img, idx) in extractImages(currentQuestion.full_content || currentQuestion.question_content)" 
                 :key="idx" 
                 :src="normalizeImagePath(img)" 
                 @error="handleImageError"
                 class="detail-image" />
          </div>
        </div>

        <div class="detail-field" v-if="hasOptions(currentQuestion.options)">
          <strong>选项：</strong>
          <div class="options-list">
            <div v-for="(opt, key) in parsedOptions(currentQuestion.options)" :key="key"
                 :class="['option-item', { 'correct-option': isCorrectOption(key, currentQuestion.answer) }]">
              <span class="option-key">{{ key }}.</span>
              <span class="option-value" v-html="opt"></span>
              <span v-if="isCorrectOption(key, currentQuestion.answer)" class="correct-mark">✅ 正确答案</span>
            </div>
          </div>
        </div>

        <div class="detail-field" v-if="currentQuestion.answer && !hasOptions(currentQuestion.options)">
          <strong>答案：</strong>
          <span class="answer-highlight">{{ currentQuestion.answer }}</span>
        </div>

        <div class="detail-field">
          <strong>答案解析：</strong>
          <div class="analysis-box" v-if="currentQuestion.answer_analysis" v-html="currentQuestion.answer_analysis"></div>
          <span v-else class="no-data">暂无解析</span>
        </div>

        <div class="detail-meta" v-if="currentQuestion.source || currentQuestion.year">
          <span v-if="currentQuestion.year">📅 {{ currentQuestion.year }}年</span>
          <span v-if="currentQuestion.source" style="margin-left:12px">📄 来源：{{ currentQuestion.source }}</span>
        </div>

        <div class="modal-footer">
          <button class="btn-edit-inline" @click="showDetailModal = false; openEdit(currentQuestion)">✏️ 编辑此题</button>
          <button class="btn-feedback" @click="showDetailModal = false; openFeedback(currentQuestion)">🚩 反馈问题</button>
          <button class="btn-close" @click="showDetailModal = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 反馈弹窗 -->
    <div class="modal-overlay" v-if="showFeedbackModal" @click.self="showFeedbackModal = false">
      <div class="modal-content feedback-modal">
        <h3>🚩 提交识别反馈</h3>
        <p class="feedback-desc">题目 #{{ feedbackForm.question_id }} — 感谢您的反馈，帮助我们改进识别准确率。</p>

        <div class="form-group">
          <label>反馈类型 <span class="required">*</span></label>
          <div class="feedback-type-list">
            <label v-for="(label, key) in feedbackTypes" :key="key" class="feedback-type-item"
                   :class="{ active: feedbackForm.feedback_type === key }">
              <input type="radio" :value="key" v-model="feedbackForm.feedback_type" style="display:none" />
              {{ label }}
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>问题描述</label>
          <textarea class="form-input form-textarea" v-model="feedbackForm.description" rows="3"
                    placeholder="请描述具体问题（可选）"></textarea>
        </div>

        <div class="modal-footer">
          <button class="btn-save" @click="submitFeedback" :disabled="feedbackSaving || !feedbackForm.feedback_type">
            {{ feedbackSaving ? '提交中...' : '提交反馈' }}
          </button>
          <button class="btn-close" @click="showFeedbackModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 编辑题目弹窗 -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div class="modal-content edit-modal">
        <h3>{{ editForm.question_id ? '编辑题目 #' + editForm.question_id : '编辑题目' }}</h3>

        <div class="form-group">
          <label>科目</label>
          <select class="form-input" v-model="editForm.subject_id">
            <option :value="1">行测</option>
            <option :value="2">申论</option>
            <option :value="3">公专</option>
          </select>
        </div>

        <div class="form-group">
          <label>题目类型</label>
          <span :class="['type-badge', 'type-badge-lg', typeBadgeClass(currentQuestionTypeName)]">
            {{ currentQuestionTypeName }}
          </span>
          <span class="field-hint">题型在导入时确定，不可修改</span>
        </div>

        <div class="form-group">
          <label>题干内容</label>
          <textarea class="form-input form-textarea" v-model="editForm.question_content" rows="4" placeholder="请输入题干内容（支持HTML）"></textarea>
        </div>

        <div class="form-group" v-if="showOptionFields">
          <label>选项</label>
          <div class="option-edit-list">
            <div v-for="(opt, key, idx) in editForm.optionsParsed" :key="key" class="option-edit-item">
              <span class="option-edit-key">{{ key }}.</span>
              <input class="form-input option-edit-input" v-model="editForm.optionsParsed[key]" :placeholder="'选项 ' + key" />
            </div>
          </div>
          <div class="option-actions">
            <button class="btn-sm" @click="addOption">+ 添加选项</button>
            <button class="btn-sm btn-danger" @click="removeOption" :disabled="optionCount <= 2">- 删除选项</button>
          </div>
        </div>

        <div class="form-group">
          <label>正确答案</label>
          <input class="form-input" v-model="editForm.answer" :placeholder="showOptionFields ? '如: A 或 AB（多选用大写字母连写）' : '请输入正确答案'" />
        </div>

        <div class="form-group">
          <label>答案解析</label>
          <textarea class="form-input form-textarea" v-model="editForm.answer_analysis" rows="3" placeholder="请输入答案解析（支持HTML）"></textarea>
        </div>

        <div class="form-group">
          <label>图片上传</label>
          <div class="image-upload-area">
            <div class="uploaded-images" v-if="editForm.images && editForm.images.length > 0">
              <div v-for="(img, idx) in editForm.images" :key="idx" class="uploaded-image-item">
                <img :src="img.url" :alt="img.name" class="uploaded-image-preview" />
                <div class="uploaded-image-info">
                  <span class="uploaded-image-name">{{ img.name }}</span>
                  <button class="btn-remove-image" @click="removeImage(idx)" title="删除图片">×</button>
                </div>
              </div>
            </div>
            <div class="upload-button-area">
              <input type="file" ref="fileInput" @change="handleImageUpload" accept="image/*" multiple style="display: none;" />
              <button class="btn-upload" @click="$refs.fileInput.click()" type="button">
                📷 上传图片
              </button>
              <span class="upload-hint">支持 JPG、PNG、GIF 格式，单张不超过 5MB</span>
            </div>
          </div>
        </div>

        <div class="form-group">
          <label>难度</label>
          <div class="star-picker">
            <span v-for="s in 5" :key="s" :class="['star-item', { active: s <= editForm.difficulty }]" @click="editForm.difficulty = s">{{ s <= editForm.difficulty ? '★' : '☆' }}</span>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-save" @click="saveEdit" :disabled="saving">{{ saving ? '保存中...' : '保存修改' }}</button>
          <button class="btn-close" @click="showEditModal = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useProvider } from '@vtj/renderer';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherQuestions',
  components: { TeacherNavHeader },
  setup() {
    const provider = useProvider({ id: 'teacher_questions', version: '2' });
    const router = useRouter();

    const keyword = ref('');
    const filterSubject = ref('');
    const filterType = ref('');
    const filterDifficulty = ref('');
    const questions: any = ref([]);
    const page = ref(1);
    const pageSize = 20;
    const total = ref(0);
    const totalPages = ref(0);

    // 详情弹窗
const showDetailModal = ref(false);
const currentQuestion: any = ref({});
const groupInfo: any = ref(null);  // B4: 题组聚合信息（共享材料）

    // 编辑弹窗
    const showEditModal = ref(false);
    const saving = ref(false);
    const currentQuestionTypeName = ref('');
    const editForm: any = ref({
      question_id: null, subject_id: 1, type_id: 1,
      question_content: '', answer: '', answer_analysis: '',
      difficulty: 3, optionsParsed: { A: '', B: '', C: '', D: '' },
      images: []  // 图片列表
    });
    const fileInput = ref(null);

    // 反馈弹窗
    const showFeedbackModal = ref(false);
    const feedbackSaving = ref(false);
    const feedbackForm: any = ref({
      question_id: null,
      feedback_type: '',
      description: ''
    });
    const feedbackTypes: Record<string, string> = {
      'recognition_error': '识别错误',
      'wrong_answer': '答案错误',
      'missing_content': '内容缺失',
      'format_error': '格式错误',
      'duplicate': '重复题目',
      'other': '其他问题'
    };

    // 题型选项（需后台查询映射，这里用静态映射）
    const showOptionFields = computed(() => {
      const name = currentQuestionTypeName.value;
      return name === '单选题' || name === '多选题';
    });

    const optionCount = computed(() => {
      return Object.keys(editForm.value.optionsParsed || {}).length;
    });

    onMounted(async () => {
      await loadQuestions();
    });

    async function loadQuestions() {
      const auth = (window as any).__VTJ_AUTH__;
      const params = new URLSearchParams();
      if (keyword.value) params.append('keyword', keyword.value);
      if (filterSubject.value) params.append('subject_id', filterSubject.value);
      if (filterType.value) params.append('type_name', filterType.value);
      if (filterDifficulty.value) params.append('difficulty', filterDifficulty.value);
      params.append('page', String(page.value));
      params.append('page_size', String(pageSize));

      try {
        const res = await auth.apiFetch(`/api/teacher/questions?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
          questions.value = data.items || [];
          total.value = data.total;
          totalPages.value = Math.max(1, Math.ceil(data.total / pageSize));
        }
      } catch (e) { console.error('加载题目失败:', e); }
    }

    // ========== 工具函数 ==========

    function doSearch() { page.value = 1; loadQuestions(); }
    function changePage(p: number) { page.value = p; loadQuestions(); }

    function subjectName(id: number) {
      const map: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
      return map[id] || '-';
    }

    function typeDisplayName(typeInfo: any) {
      if (!typeInfo) return '-';
      const s = String(typeInfo);
      // 题型显示以 type_name 为单一事实来源（后端 teacher.py 始终返回）。
      // 数字 type_id 映射已删除：历史硬编码 {'1':单选,'2':多选,'3':论述,'4':写作}
      // 与真实库 type_id 分配错位（2=论述/3=单选/4=多选），是题型误显示根源之一。
      const nameMap: Record<string, string> = {
        '单选题': '单选题', '多选题': '多选题', '论述题': '论述题', '写作题': '写作题',
      };
      return nameMap[s] || s;
    }

    function typeBadgeClass(typeInfo: any) {
      const name = typeDisplayName(typeInfo);
      const map: Record<string, string> = {
        '单选题': 'badge-single', '多选题': 'badge-multi',
        '论述题': 'badge-essay', '写作题': 'badge-writing',
      };
      return map[name] || 'badge-single';
    }

    function renderStars(d: number) { return d ? '★'.repeat(Math.min(d, 5)) : '★'; }

    function stripPromoText(text: string) {
      if (!text) return '';
      let cleaned = text;
      cleaned = cleaned.replace(/来源\s*[：:：]\s*\S+/g, '');
      cleaned = cleaned.replace(/整理\s*[：:：]\s*\S+/g, '');
      cleaned = cleaned.replace(/(?:微信|QQ)\s*[：:：]\s*\S+/g, '');
      cleaned = cleaned.replace(/关注\s*(?:公众号|微信|微博)\s*\S*/g, '');
      cleaned = cleaned.replace(/gwy\d+|gwyeasy/g, '');
      cleaned = cleaned.replace(/\[IMAGE:[^\]]+\]/g, '[📷图片]');
      cleaned = cleaned.replace(/<img[^>]*\/>/g, '[📷图片]');
      return cleaned.trim();
    }

    // 新增：过滤题目内容（移除 UTB ID 等系统噪音）
    function cleanQuestionContent(text: string) {
      if (!text) return '';
      let cleaned = text;
      // 移除 UTB 系统 ID (UTB + 8位以上十六进制)
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}/gi, '');
      // 移除题号前缀 (如 "第5题：" "第1题：")
      cleaned = cleaned.replace(/^第\s*\d+\s*题[：:]\s*/, '');
      // 移除选项前缀的 UTB ID (如 "UTB7df857a7-选项A-5")
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}[-－]\s*选项[A-D]\s*[\d\-]*/gi, '');
      // 合并多余空白字符
      cleaned = cleaned.replace(/\s+/g, ' ');
      // 去除首尾空格
      cleaned = cleaned.trim();
      return cleaned;
    }

    // 新增：清洗HTML内容中的UTB ID（用于详情弹窗v-html显示）
    function cleanHtmlContent(text: string) {
      if (!text) return '';
      let cleaned = text;
      // 移除UTB ID（含选项后缀）
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*/gi, '');
      // 移除题号前缀
      cleaned = cleaned.replace(/第\s*\d+\s*题[：:]\s*/g, '');
      // 合并多余空白
      cleaned = cleaned.replace(/\s+/g, ' ');
      return cleaned.trim();
    }

    function truncate(text: string, len: number) {
      if (!text) return '';
      const cleaned = stripPromoText(text);
      if (cleaned.length > len) return cleaned.substring(0, len) + '...';
      return cleaned;
    }

    function hasImage(text: string) {
      if (!text) return false;
      return /\[IMAGE:|<img/.test(text);
    }

    function renderSummary(q: any) {
      const text = q.question_content || '';
      const cleaned = stripPromoText(text);
      const cleanText = cleanQuestionContent(cleaned); // 过滤 UTB ID
      // 处理图片路径
      const processedContent = processImagePaths(cleanText);
      // 替换img标签为[图片]占位符，避免显示无关图片
      const withPlaceholders = processedContent.replace(/<img[^>]*\/?>/g, '[📷图片]');
      const truncated = withPlaceholders.length > 80 ? withPlaceholders.substring(0, 80) + '...' : withPlaceholders;
      return truncated;
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
          const key = String.fromCharCode(65 + i);
          if (typeof o === 'object') result[key] = o.value || o.text || '';
          else result[key] = String(o);
        });
        return result;
      }
      if (typeof opts === 'object') return opts;
      if (typeof opts === 'string') {
        try { return parsedOptions(JSON.parse(opts)); } catch(e) { return {}; }
      }
      return {};
    }

    function isCorrectOption(key: string, answer: string) {
      if (!answer) return false;
      const normAnswer = String(answer).trim().toUpperCase().replace(/[^A-D]/g, '');
      return normAnswer.includes(key.toUpperCase());
    }

    // ========== 图片路径处理 ==========

    // 图片路径标准化函数
    function normalizeImagePath(path: string): string {
      if (!path) return '';
      
      // 如果是完整URL，直接返回
      if (path.startsWith('http://') || path.startsWith('https://')) {
        return path;
      }
      
      // 如果是data URL，直接返回
      if (path.startsWith('data:')) {
        return path;
      }
      
      // 移除开头的./或../
      let normalized = path.replace(/^\.\//, '').replace(/^\.\.\//, '');
      
      // 如果路径以/开头，直接使用
      if (normalized.startsWith('/')) {
        return normalized;
      }
      
      // 如果路径不以/开头，添加前缀
      if (!normalized.startsWith('static/') && !normalized.startsWith('uploads/')) {
        normalized = 'static/questions/' + normalized;
      }
      
      return '/' + normalized;
    }

    // 图片加载错误处理
    function handleImageError(event: Event) {
      const img = event.target as HTMLImageElement;
      if (img) {
        // 设置占位符图片
        img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJDNi40NzcgMiAyIDYuNDc3IDIgMTJzNC40NzcgMTAgMTAgMTAgMTAtNC40NzcgMTAtMTBTMTcuNTIzIDIgMTJ6bTAgNGEzIDMgMCAxMTAgNiAzIDMgMCAwMTAtNnoiIGZpbGw9IiM5OTkiLz4KPC9zdmc+';
        img.alt = '图片加载失败';
      }
    }

    // 处理题目内容中的图片路径
    function processImagePaths(content: string): string {
      if (!content) return '';
      
      // 处理<img>标签中的src属性
      return content.replace(/<img[^>]*src=["']([^"']*)["'][^>]*\/?>/gi, (match, src) => {
        const normalizedSrc = normalizeImagePath(src);
        return match.replace(src, normalizedSrc);
      });
    }

    // 检查图片是否存在（异步）
    async function checkImageExists(url: string): Promise<boolean> {
      try {
        const response = await fetch(url, { method: 'HEAD' });
        return response.ok;
      } catch {
        return false;
      }
    }

    // 从内容中提取图片URL
    function extractImages(content: string): string[] {
      if (!content) return [];
      const images: string[] = [];
      
      // 提取<img>标签中的src
      const imgRegex = /<img[^>]*src=["']([^"']*)["'][^>]*\/?>/gi;
      let match;
      while ((match = imgRegex.exec(content)) !== null) {
        if (match[1]) {
          images.push(match[1]);
        }
      }
      
      // 提取[IMAGE:xxx]格式的图片
      const imageTagRegex = /\[IMAGE:([^\]]+)\]/gi;
      while ((match = imageTagRegex.exec(content)) !== null) {
        if (match[1]) {
          images.push(match[1]);
        }
      }
      
      return images;
    }

    // ========== 详情弹窗 ==========

    function showDetail(q: any) {
      currentQuestion.value = q;
      showDetailModal.value = true;
      // B4: 复合题小题 → 拉取题组聚合（共享材料+同组成员）
      groupInfo.value = null;
      if (q.group_id) {
        const auth = (window as any).__VTJ_AUTH__;
        auth.apiFetch(`/api/questions/group/${q.group_id}`)
          .then((res: any) => res.json())
          .then((data: any) => {
            if (data && data.group) {
              groupInfo.value = data.group;
              currentQuestion.value = { ...q, group_members: data.members || [] };
            }
          })
          .catch((e: any) => console.error('题组详情加载失败:', e));
      }
    }

    // ========== 编辑弹窗 ==========

    function openEdit(q: any) {
      const opts = parsedOptions(q.options);
      currentQuestionTypeName.value = typeDisplayName(q.type_name);
      // 提取题目中的图片
      const existingImages = extractImages(q.full_content || q.question_content || '').map((url: string, idx: number) => ({
        url: url,
        name: `图片 ${idx + 1}`,
        isExisting: true
      }));
      editForm.value = {
        question_id: q.question_id,
        subject_id: q.subject_id || 1,
        question_content: q.full_content || q.question_content || '',
        answer: q.answer || '',
        answer_analysis: q.answer_analysis || '',
        difficulty: q.difficulty || 3,
        optionsParsed: Object.keys(opts).length > 0 ? { ...opts } : { A: '', B: '', C: '', D: '' },
        images: existingImages
      };
      showEditModal.value = true;
    }

    // ========== 图片上传功能 ==========

    function handleImageUpload(event: Event) {
      const input = event.target as HTMLInputElement;
      if (!input.files || input.files.length === 0) return;
      
      const files = Array.from(input.files);
      const maxSize = 5 * 1024 * 1024; // 5MB
      const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
      
      for (const file of files) {
        // 验证文件类型
        if (!allowedTypes.includes(file.type)) {
          ElMessage.error(`文件 ${file.name} 不是支持的图片格式`);
          continue;
        }
        
        // 验证文件大小
        if (file.size > maxSize) {
          ElMessage.error(`文件 ${file.name} 超过 5MB 限制`);
          continue;
        }
        
        // 读取文件并添加到图片列表
        const reader = new FileReader();
        reader.onload = (e) => {
          const url = e.target?.result as string;
          editForm.value.images.push({
            url: url,
            name: file.name,
            isExisting: false,
            file: file
          });
        };
        reader.readAsDataURL(file);
      }
      
      // 清空input
      input.value = '';
    }

    function removeImage(index: number) {
      editForm.value.images.splice(index, 1);
    }

    async function uploadImages(): Promise<string[]> {
      const auth = (window as any).__VTJ_AUTH__;
      const uploadedUrls: string[] = [];
      
      for (const img of editForm.value.images) {
        if (img.isExisting) {
          // 已存在的图片，直接使用URL
          uploadedUrls.push(img.url);
        } else if (img.file) {
          // 新上传的图片，需要上传到服务器
          try {
            const formData = new FormData();
            formData.append('file', img.file);
            const res = await auth.apiFetch('/api/upload/image', {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            if (data.success && data.url) {
              uploadedUrls.push(data.url);
            }
          } catch (e) {
            console.error('图片上传失败:', e);
            ElMessage.error(`图片 ${img.name} 上传失败`);
          }
        }
      }
      
      return uploadedUrls;
    }

    function addOption() {
      const opts = editForm.value.optionsParsed || {};
      const keys = Object.keys(opts);
      if (keys.length >= 8) return;
      const nextKey = String.fromCharCode(65 + keys.length);
      opts[nextKey] = '';
      editForm.value.optionsParsed = { ...opts };
    }

    function removeOption() {
      const opts = editForm.value.optionsParsed || {};
      const keys = Object.keys(opts);
      if (keys.length <= 2) return;
      delete opts[keys[keys.length - 1]];
      editForm.value.optionsParsed = { ...opts };
    }

    async function saveEdit() {
      saving.value = true;
      try {
        const auth = (window as any).__VTJ_AUTH__;
        
        // 上传图片并获取URL
        const imageUrls = await uploadImages();
        
        const payload: any = {
          subject_id: editForm.value.subject_id,
          question_content: editForm.value.question_content,
          answer: editForm.value.answer,
          answer_analysis: editForm.value.answer_analysis,
          difficulty: editForm.value.difficulty,
          images: imageUrls  // 添加图片URL列表
        };
        // 如果有选项数据，打包为数组格式
        if (showOptionFields.value) {
          const opts = editForm.value.optionsParsed || {};
          const optKeys = Object.keys(opts).filter(k => opts[k].trim());
          if (optKeys.length > 0) {
            payload.options = optKeys.map(k => ({ key: k, value: opts[k] }));
          }
        }
        const res = await auth.apiFetch(`/api/teacher/questions/${editForm.value.question_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('题目已更新');
          showEditModal.value = false;
          await loadQuestions();
        } else if (data.detail) {
          ElMessage.error('保存失败: ' + data.detail);
        } else {
          ElMessage.error('保存失败: ' + (data.message || '未知错误'));
        }
      } catch (e: any) {
        ElMessage.error('网络错误，请检查连接后重试');
      } finally {
        saving.value = false;
      }
    }

    // ========== 删除 ==========

    async function deleteQuestion(id: number) {
      if (confirm('确定要删除这道题目吗？此操作不可恢复。')) {
        const auth = (window as any).__VTJ_AUTH__;
        try {
          await auth.apiFetch(`/api/teacher/questions/${id}`, { method: 'DELETE' });
          ElMessage.success('题目已删除');
          await loadQuestions();
        } catch (e) {
          ElMessage.error('删除失败');
        }
      }
    }

    // ========== 导航 ==========

    function goImport() { router.push('/question-import'); }
    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    // ========== 反馈功能 ==========

    function openFeedback(q: any) {
      feedbackForm.value = {
        question_id: q.question_id,
        feedback_type: '',
        description: ''
      };
      showFeedbackModal.value = true;
    }

    async function submitFeedback() {
      if (!feedbackForm.value.feedback_type) {
        ElMessage.warning('请选择反馈类型');
        return;
      }
      feedbackSaving.value = true;
      try {
        const auth = (window as any).__VTJ_AUTH__;
        const res = await auth.apiFetch('/api/teacher/questions/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(feedbackForm.value),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('反馈已提交，感谢您的帮助！');
          showFeedbackModal.value = false;
        } else {
          ElMessage.error('提交失败: ' + (data.detail || data.message || '未知错误'));
        }
      } catch (e: any) {
        ElMessage.error('网络错误，请检查连接后重试');
      } finally {
        feedbackSaving.value = false;
      }
    }

    return {
      provider,
      keyword, filterSubject, filterType, filterDifficulty,
      questions, page, pageSize, total, totalPages,
      showDetailModal, currentQuestion,
      showEditModal, saving, currentQuestionTypeName, editForm, showOptionFields, optionCount,
      showFeedbackModal, feedbackSaving, feedbackForm, feedbackTypes,
      doSearch, changePage, subjectName, typeDisplayName, typeBadgeClass,
      renderStars, truncate, stripPromoText, hasImage, renderSummary,
      hasOptions, parsedOptions, isCorrectOption,
      showDetail, openEdit, addOption, removeOption, saveEdit,
      deleteQuestion, goImport, handleLogout, cleanHtmlContent,
      normalizeImagePath, handleImageError, processImagePaths, checkImageExists, extractImages,
      openFeedback, submitFeedback, fileInput, handleImageUpload, removeImage,
    };
  }
});

</script>

<style scoped>
.teacher-questions { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 1300px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
.search-input { flex: 1; min-width: 180px; padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.btn-search { padding: 8px 20px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-import { padding: 8px 20px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.toolbar-spacer { flex: 1; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; white-space: nowrap; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.td-seq { text-align: center; color: #909399; font-weight: 500; }
.td-content { color: #1A3C6D; cursor: pointer; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-content:hover { text-decoration: underline; }
.has-image .td-content { white-space: normal; max-width: none; }
.has-image td { vertical-align: top; }
.td-stars { color: #E6A23C; letter-spacing: 2px; }
.td-actions { white-space: nowrap; }
.btn-action { padding: 4px 8px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 14px; }
.btn-action:hover { background: #f0f0f0; }
.btn-danger:hover { background: #C41E3A; color: #fff; border-color: #C41E3A; }
.btn-sm { padding: 4px 10px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; margin-right: 4px; }
.btn-sm:hover { background: #f0f0f0; }
.btn-sm.btn-danger { color: #C41E3A; border-color: #f5c6cb; }
.btn-sm.btn-danger:hover { background: #C41E3A; color: #fff; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }
.pagination button { padding: 8px 16px; border: 1px solid #d9d9d9; background: #fff; border-radius: 6px; cursor: pointer; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }

/* 题型徽章 */
.type-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 13px; font-weight: 500; color: #fff; }
.type-badge-lg { padding: 4px 14px; font-size: 15px; }
.badge-single { background: #409EFF; }
.badge-multi { background: #67C23A; }
.badge-essay { background: #E6A23C; }
.badge-writing { background: #F56C6C; }

/* 详情弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 1100px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.modal-header h3 { color: #1A3C6D; margin: 0; flex: 1; }
.detail-modal { max-width: 1100px; }
.detail-field { margin-bottom: 14px; line-height: 1.8; }
.detail-field strong { color: #1A3C6D; }
.detail-content { margin-top: 6px; padding: 10px 14px; background: #f9fafb; border-radius: 8px; line-height: 1.8; }
.detail-content img { max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }
  .options-list { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }
  .group-badge { margin-left: 6px; font-size: 12px; cursor: help; }
  .group-material { background: #f5f7fa; border-left: 3px solid #409eff; padding: 8px 10px; border-radius: 4px; }
.option-item { display: flex; align-items: flex-start; gap: 8px; padding: 8px 12px; border-radius: 6px; border: 1px solid #e8e8e8; background: #fafafa; }
.option-item.correct-option { background: #f0fdf4; border-color: #86efac; }
.option-key { font-weight: 700; color: #1A3C6D; min-width: 24px; }
.option-value { flex: 1; }
.correct-mark { color: #22c55e; font-weight: 700; font-size: 13px; }
.answer-highlight { color: #22c55e; font-weight: 700; font-size: 16px; background: #f0fdf4; padding: 4px 12px; border-radius: 4px; }
.analysis-box { margin-top: 6px; padding: 12px 14px; background: #fffbeb; border-radius: 8px; border-left: 3px solid #E6A23C; line-height: 1.8; }
.detail-meta { margin-top: 12px; color: #909399; font-size: 13px; }
.high-rate { color: #22c55e; font-weight: 600; }
.low-rate { color: #F56C6C; font-weight: 600; }

/* 编辑弹窗 */
.edit-modal { max-width: 1100px; }
.edit-modal h3 { color: #1A3C6D; margin: 0 0 20px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #1A3C6D; font-size: 14px; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
.form-textarea { resize: vertical; font-family: inherit; line-height: 1.6; }
.option-edit-list { display: flex; flex-direction: column; gap: 6px; }
.option-edit-item { display: flex; align-items: center; gap: 8px; }
.option-edit-key { font-weight: 700; color: #1A3C6D; min-width: 24px; }
.option-edit-input { flex: 1; }
.option-actions { margin-top: 8px; display: flex; gap: 8px; }
.star-picker { display: flex; gap: 4px; cursor: pointer; }
.star-item { font-size: 24px; color: #d9d9d9; user-select: none; }
.star-item.active { color: #E6A23C; }
.modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.btn-save { padding: 10px 28px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-save:hover { background: #2a4f80; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-edit-inline { padding: 10px 28px; background: #409EFF; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-close { padding: 10px 28px; background: #f0f0f0; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }

/* 图片样式 */
.detail-images {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}
.detail-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
  object-fit: contain;
}
.detail-image:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* 缺失解析标记 */
.missing-analysis-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: rgba(245, 158, 11, 0.15);
  border-radius: 4px;
  font-size: 14px;
  cursor: help;
  margin-left: 4px;
}
.missing-analysis-badge:hover {
  background: rgba(245, 158, 11, 0.3);
}

/* 图片上传样式 */
.image-upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}
.uploaded-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.uploaded-image-item {
  position: relative;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.uploaded-image-preview {
  width: 100%;
  height: 80px;
  object-fit: cover;
  display: block;
}
.uploaded-image-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  background: #f5f5f5;
}
.uploaded-image-name {
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 80px;
}
.btn-remove-image {
  width: 20px;
  height: 20px;
  border: none;
  background: #ff4d4f;
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-remove-image:hover {
  background: #ff7875;
}
.upload-button-area {
  display: flex;
  align-items: center;
  gap: 12px;
}
.btn-upload {
  padding: 8px 16px;
  background: #409EFF;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-upload:hover {
  background: #66b1ff;
}
.upload-hint {
  font-size: 12px;
  color: #909399;
}

/* 反馈弹窗 */
.feedback-modal { max-width: 520px; }
.feedback-modal h3 { color: #1A3C6D; margin: 0 0 8px; }
.feedback-desc { color: #909399; font-size: 13px; margin-bottom: 16px; }
.feedback-type-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.feedback-type-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  text-align: center;
  transition: all 0.2s;
  user-select: none;
}
.feedback-type-item:hover {
  border-color: #409EFF;
  color: #409EFF;
}
.feedback-type-item.active {
  border-color: #409EFF;
  background: #ecf5ff;
  color: #409EFF;
  font-weight: 600;
}
.required { color: #F56C6C; }
.btn-feedback {
  padding: 10px 28px;
  background: #E6A23C;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 15px;
}
.btn-feedback:hover { background: #ebb563; }
</style>
