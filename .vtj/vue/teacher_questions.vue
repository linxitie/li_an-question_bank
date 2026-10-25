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
          <option value="判断题">判断题</option>
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
        <!-- P3b：待复核筛选（导入时题型判定置信度不足的题） -->
        <select class="filter-select review-select" v-model="filterReview" @change="doSearch">
          <option value="">全部状态</option>
          <option value="1">⚠ 待复核</option>
          <option value="0">已确认</option>
        </select>
        <button class="btn-search" @click="doSearch">搜索</button>
        <div class="toolbar-spacer"></div>
        <button class="btn-batch" :class="{ 'btn-batch-active': batchMode }" @click="toggleBatchMode">🗂 批量处理</button>
        <button class="btn-import" @click="goImport">📤 题目导入</button>
      </div>

      <!-- 批量操作条（批量模式显示） -->
      <div class="batch-toolbar" v-if="batchMode">
        <label class="batch-checkall"><input type="checkbox" :checked="allChecked" @change="toggleAll" /> 全选本页</label>
        <span class="batch-count">已选 {{ selectedIds.length }} 题</span>
        <select class="filter-select" v-model="batchSubjectId" style="width:120px;">
          <option :value="0">改科目：</option>
          <option :value="1">行测</option>
          <option :value="2">申论</option>
          <option :value="3">公专</option>
        </select>
        <button class="btn-mini-reclassify" :disabled="!selectedIds.length || !batchSubjectId" @click="batchReclassify">应用改分类</button>
        <button class="btn-mini-danger" :disabled="!selectedIds.length" @click="batchDelete">删除选中</button>
        <button class="btn-mini-cancel" @click="toggleBatchMode">取消</button>
      </div>

      <!-- 题目表格 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:60px">序号</th>
              <th>题干摘要</th>
              <th style="width:70px">科目</th>
              <th style="width:110px">题型</th>
              <th style="width:80px">难度</th>
              <th style="width:90px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(q, index) in questions" :key="q.question_id" :class="{ 'has-image': hasImage(q.question_content) }">
              <td class="td-seq"><input v-if="batchMode" type="checkbox" class="td-check" :value="q.question_id" v-model="selectedIds" />{{ (page - 1) * pageSize + index + 1 }}</td>
              <td class="td-content" @click="showDetail(q)">{{ renderSummary(q) }}</td>
              <td>{{ subjectName(q.subject_id) }}</td>
              <td>
                <!-- P3b：待复核徽标。题型判定置信度不足的题在此显式提示，
                     避免教师以错误题型把它编入试卷。 -->
                <span v-if="q.need_review" class="review-flag" title="导入时题型判定置信度不足，请人工确认">⚠ 待复核</span>
                <span :class="['type-badge', typeBadgeClass(q.type_name)]">
                  {{ typeDisplayName(q.type_name) }}
                </span>
                <span v-if="q.group_id" class="group-badge" title="复合题小题（点击详情查看题组材料）">📑</span>
              </td>
              <td class="td-stars">{{ renderStars(q.difficulty) }}</td>
              <td class="td-actions">
                <button class="btn-action" @click="openEdit(q)" title="编辑">✏️</button>
                <button class="btn-action btn-danger" @click="deleteQuestion(q.question_id)" title="删除">🗑️</button>
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

        <div class="detail-field" v-if="currentQuestion.group_members && currentQuestion.group_members.length">
          <strong>📝 题组小题：</strong>
          <div v-for="(m, mi) in currentQuestion.group_members" :key="mi"
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

        <div class="detail-field">
          <strong>题干：</strong>
          <div class="detail-content" v-html="cleanHtmlContent(currentQuestion.full_content || currentQuestion.question_content)"></div>
        </div>

        <div class="detail-field" v-if="hasOptions(currentQuestion.options)">
          <strong>选项：</strong>
          <div class="options-list">
            <div v-for="(opt, key) in parsedOptions(currentQuestion.options)" :key="key"
                 :class="['option-item', { 'correct-option': isCorrectOption(key, currentQuestion.answer) }]">
              <span class="option-key">{{ key }}.</span>
              <span class="option-value" v-html="renderQuestionContent(opt)"></span>
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
          <div class="analysis-box" v-if="currentQuestion.answer_analysis" v-html="renderQuestionContent(currentQuestion.answer_analysis)"></div>
          <span v-else class="no-data">暂无解析</span>
        </div>

        <div class="detail-meta" v-if="currentQuestion.source || currentQuestion.year">
          <span v-if="currentQuestion.year">📅 {{ currentQuestion.year }}年</span>
          <span v-if="currentQuestion.source" style="margin-left:12px">📄 来源：{{ currentQuestion.source }}</span>
        </div>

        <div class="modal-footer">
          <button class="btn-edit-inline" @click="showDetailModal = false; openEdit(currentQuestion)">✏️ 编辑此题</button>
          <button class="btn-close" @click="showDetailModal = false">关闭</button>
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

        <!-- P2-5：题组共享材料编辑 -->
        <div class="form-group material-section">
          <label>
            题组材料
            <span class="material-group-hint" v-if="editForm.group_id > 0">（当前题组 #{{ editForm.group_id }}）</span>
          </label>
          <RichTextEditor v-model="editForm.shared_content" :group-id="editForm.group_id" placeholder="题组材料：支持加粗/链接/图片/表格" />
          <div class="material-preview" v-if="editForm.shared_content">{{ editForm.shared_content }}</div>
          <div class="material-actions">
            <button type="button" class="btn-sm" @click="clearMaterial">清除材料</button>
            <span class="field-hint">清空材料并解除题组关联，保存后生效</span>
          </div>
        </div>

        <div class="form-group">
          <label>题干内容</label>
          <textarea class="form-input form-textarea" v-model="editForm.question_content" rows="4" placeholder="请输入题干内容（支持HTML，可Ctrl+V粘贴图片）"
                    @paste="handleEditPaste('question_content', $event)"></textarea>
          <!-- P0-2 修复：编辑含图片题目时，textarea 里只能看到 <img src="/static/..."> 原文。
               在输入框下方加实时渲染预览，教师可直接确认图片是否正确挂到该题。 -->
          <div class="edit-preview-block" v-if="editForm.question_content">
            <div class="edit-preview-head">
              <span>实时预览</span>
              <label class="edit-preview-toggle">
                <input type="checkbox" v-model="editPreviewOpen" />
                <span>{{ editPreviewOpen ? '收起' : '展开' }}</span>
              </label>
            </div>
            <div class="edit-preview-body" v-if="editPreviewOpen" v-html="renderQuestionContent(editForm.question_content)"></div>
          </div>
          <div class="field-hint" v-if="!editHasImage(editForm.question_content)">
            提示：题干若含图片，请确认下方预览能正常显示；若显示为红色占位图说明图片文件缺失。
          </div>
          <!-- 图片上传：教师可直接为题目补图，无需手写 <img> 原文 -->
          <div class="img-upload-row">
            <label class="img-upload-label">题目图片</label>
            <input type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/bmp" class="form-input img-upload-input" @change="onPickImage" />
            <button class="btn-sm" @click="doUploadImage" :disabled="uploadingImg || !pickedImage">
              {{ uploadingImg ? '上传中...' : '上传图片' }}
            </button>
          </div>
          <div class="field-hint" v-if="imgUploadMsg">{{ imgUploadMsg }}</div>
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
          <input class="form-input" v-model="editForm.answer" :placeholder="showOptionFields ? '如: A 或 AB（多选用大写字母连写）' : '请输入正确答案'"
                 @paste="handleEditPaste('answer', $event)" />
        </div>

        <div class="form-group">
          <label>答案解析</label>
          <textarea class="form-input form-textarea" v-model="editForm.answer_analysis" rows="3" placeholder="请输入答案解析（支持HTML，可Ctrl+V粘贴图片）"
                    @paste="handleEditPaste('answer_analysis', $event)"></textarea>
          <div class="edit-preview-body" v-if="editPreviewOpen && editForm.answer_analysis" v-html="renderQuestionContent(editForm.answer_analysis)"></div>
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
import RichTextEditor from '@/components/rich-text/RichTextEditor.vue';
import { renderQuestionContent } from '@/utils/questionRender';

export default defineComponent({
  name: 'TeacherQuestions',
  components: { TeacherNavHeader, RichTextEditor },
  setup() {
    const provider = useProvider({ id: 'teacher_questions', version: '2' });
    const router = useRouter();

    const keyword = ref('');
    const filterSubject = ref('');
    const filterType = ref('');
    // P3b：待复核筛选。'' = 不限，'1' = 仅看待复核，'0' = 仅看已确认
    const filterReview = ref('');
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
    // P0-2：编辑弹窗内的实时渲染预览开关（默认展开，含图题目直接可见）
    const editPreviewOpen = ref(true);
    const editForm: any = ref({
      question_id: null, subject_id: 1, type_id: 1,
      question_content: '', answer: '', answer_analysis: '',
      difficulty: 3, optionsParsed: { A: '', B: '', C: '', D: '' },
      // P2-5：题组共享材料（保存时随 PUT 一起提交，后端事务化 upsert question_groups）
      group_id: 0, shared_content: '', shared_content_images: ''
    });

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
      // P3b：待复核筛选（need_review=1）。导入时题型判定置信度不足的题会被标记，
      // 由教师在这里集中确认，避免它们以错误题型长期混在题库里。
      if (filterReview.value !== '') params.append('need_review', filterReview.value);
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

    // 新增：清洗HTML内容中的UTB ID，并修复图片路径（用于详情弹窗v-html显示）
    // 题目正文渲染统一收敛到 src/utils/questionRender.js 这一单一真源。
    // 修复点：此前本函数只做 UTB/题号/图片占位符处理，**完全没有白名单清洗**，
    // 其输出被直接 v-html 渲染，题干中的 <script>/onerror 等可执行，形成 XSS 缺口。
    // 现在保留教师侧特有的导入残留清理与图片路径纠正，
    // 清洗、标记转换、onerror 兜底一律交给公共渲染器，避免两套实现再次分叉。
    function cleanHtmlContent(text: string) {
      if (!text) return '';
      let cleaned = text;
      // 移除UTB ID（含选项后缀）
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*/gi, '');
      // 移除题号前缀
      cleaned = cleaned.replace(/第\s*\d+\s*题[：:]\s*/g, '');
      // 修复相对路径的既有 img 标签：确保 /static/questions/ 前缀
      cleaned = cleaned.replace(/(<img\b[^>]*?\bsrc=")(?!\/static\/|https?:\/\/)([^"]+)"/gi, '$1/static/questions/$2"');
      // 合并多余空白
      cleaned = cleaned.replace(/\s+/g, ' ');
      // 统一交给公共渲染器：白名单清洗 + [IMAGE:hash_idx] → <img> + onerror 兜底
      return renderQuestionContent(cleaned.trim());
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

    // P0-2：判断编辑框内容是否含图，用于给出"图片是否正常"的操作提示。
    // 同时识别 [IMAGE:xxx] 占位符与 <img> 标签两种形态（导入管线两种都可能残留）。
    function editHasImage(text: string) {
      if (!text) return false;
      return /\[IMAGE:[^\]]+\]|<img[\s>]/i.test(String(text));
    }

    // 图片加载失败处理 - 多级重试机制
    function handleImageError(event: Event, questionId?: number) {
      const img = event.target as HTMLImageElement;
      const originalSrc = img.src;
      
      // 防止无限循环
      if (img.dataset.retrying === 'true') {
        img.src = '/static/images/placeholder.png';
        return;
      }
      
      img.dataset.retrying = 'true';
      
      // 尝试1: 去除查询参数
      const cleanSrc = originalSrc.split('?')[0];
      if (cleanSrc !== originalSrc) {
        setTimeout(() => {
          img.src = cleanSrc;
          img.dataset.retrying = 'false';
        }, 100);
        return;
      }
      
      // 尝试2: 从相对路径转为绝对路径
      if (!cleanSrc.startsWith('http') && !cleanSrc.startsWith('/static/')) {
        setTimeout(() => {
          img.src = window.location.origin + cleanSrc;
          img.dataset.retrying = 'false';
        }, 100);
        return;
      }
      
      // 尝试3: 如果有questionId，从后端重新获取图片路径
      if (questionId) {
        const auth = (window as any).__VTJ_AUTH__;
        if (auth) {
          auth.apiFetch(`/api/teacher/questions/${questionId}/images`)
            .then((res: any) => res.json())
            .then((data: any) => {
              if (data.images && data.images.length > 0) {
                img.src = data.images[0].path;
              } else {
                img.src = '/static/images/placeholder.png';
              }
              img.dataset.retrying = 'false';
            })
            .catch(() => {
              img.src = '/static/images/placeholder.png';
              img.dataset.retrying = 'false';
            });
          return;
        }
      }
      
      // 所有尝试失败，显示占位图
      setTimeout(() => {
        img.src = '/static/images/placeholder.png';
        img.dataset.retrying = 'false';
      }, 100);
    }

    function renderSummary(q: any) {
      const text = q.question_content || '';
      const cleaned = stripPromoText(text);
      const cleanText = cleanQuestionContent(cleaned); // 过滤 UTB ID
      // 将 [IMAGE:xxx] 占位符转为文字提示，避免显示损坏图片
      const withPlaceholders = cleanText.replace(/\[IMAGE:(\d+)[_-](\d+)\]/g, '[📷图片]');
      // 也处理 <img> 标签
      const noImages = withPlaceholders.replace(/<img[^>]*\/?>/g, '[📷图片]');
      const truncated = noImages.length > 80 ? noImages.substring(0, 80) + '...' : noImages;
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

    // ========== 复合题「题目要求」注入（script-only） ==========
    // 缺口：/api/questions/group/{id} 的 members[] 已带 requirements，
    // 但题组小题的渲染位只有 v-html="renderQuestionContent(m.question_content)"
    // 一处，requirements 此前完全没有出口 —— 教师端看不到申论「作答要求/采分点依据」。
    // <template> 属设计器领地（raw:true 红线）不能改结构，故在脚本内把
    // requirements 归一（string / array 两形态）后前置拼进 question_content。
    // 材料（题组共享块）渲染在小题列表之上，故最终呈现顺序即
    // 「材料 → 题目要求 → 题干 → 选项」，与三端约定一致。
    // 安全性：requirements 原文直接拼接，整串最终仍由模板的 renderQuestionContent
    // 走白名单清洗（见 src/utils/questionRender.js），与既有渲染链路同一道闸。
    const REQUIREMENT_LABEL = '题目要求：';

    function normalizeRequirements(req: any) {
      if (!req) return '';
      const list = Array.isArray(req) ? req : [req];
      return list
        .map((r: any) => String(r == null ? '' : r).trim())
        .filter((s: string) => !!s)
        .join('\n');
    }

    function requirementBlock(text: string) {
      return '<div style="margin:0 0 8px;padding:6px 10px;background:#f7f8fa;'
        + 'border-radius:6px;border-left:3px solid #409eff;color:#555;'
        + 'font-size:13px;line-height:1.7;">'
        + '<strong style="color:#1A3C6D;">' + REQUIREMENT_LABEL + '</strong> '
        + text.replace(/\r?\n/g, '<br>')
        + '</div>';
    }

    // 幂等：题干已含「题目要求：」时原样返回，重复打开详情不会叠加注入。
    function withRequirements(member: any) {
      const m = member || {};
      const text = normalizeRequirements(m.requirements);
      const content = String(m.question_content || '');
      if (!text || !content || content.indexOf(REQUIREMENT_LABEL) >= 0) return m;
      return { ...m, question_content: requirementBlock(text) + content };
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
              // members 的 requirements 前置拼进 question_content（见 withRequirements）
              currentQuestion.value = { ...q, group_members: (data.members || []).map(withRequirements) };
            }
          })
          .catch((e: any) => console.error('题组详情加载失败:', e));
      }
    }

    // ========== 编辑弹窗 ==========

    function openEdit(q: any) {
      const opts = parsedOptions(q.options);
      currentQuestionTypeName.value = typeDisplayName(q.type_name);
      editForm.value = {
        question_id: q.question_id,
        subject_id: q.subject_id || 1,
        question_content: q.full_content || q.question_content || '',
        answer: q.answer || '',
        answer_analysis: q.answer_analysis || '',
        difficulty: q.difficulty || 3,
        optionsParsed: Object.keys(opts).length > 0 ? { ...opts } : { A: '', B: '', C: '', D: '' },
        group_id: q.group_id || 0,
        shared_content: q.shared_content || '',
        shared_content_images: q.shared_content_images || '',
      };
      showEditModal.value = true;
      hydrateMaterialFromDetail(q.question_id);
    }

    // P2-5：列表接口不保证返回题组材料，编辑时按题目详情补齐；
    // 切换题目后旧请求返回时用 question_id 守卫，避免污染当前表单。
    function hydrateMaterialFromDetail(qid: any) {
      if (!qid) return;
      const auth = (window as any).__VTJ_AUTH__;
      auth.apiFetch(`/api/questions/${qid}`)
        .then((res: any) => res.json())
        .then((data: any) => {
          if (!data || editForm.value.question_id !== qid) return;
          editForm.value.group_id = data.group_id || 0;
          editForm.value.shared_content = data.shared_content || '';
          editForm.value.shared_content_images = data.shared_content_images || '';
        })
        .catch((e: any) => console.error('题组材料详情加载失败:', e));
    }

    function clearMaterial() {
      editForm.value.shared_content = '';
      editForm.value.shared_content_images = '';
      editForm.value.group_id = 0;
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

    const pickedImage = ref<File | null>(null);
const uploadingImg = ref(false);
const imgUploadMsg = ref('');

function onPickImage(e: any) {
  pickedImage.value = (e.target && e.target.files && e.target.files[0]) || null;
  imgUploadMsg.value = '';
}

async function doUploadImage() {
  const f = pickedImage.value;
  if (!f) {
    ElMessage.warning('请先选择图片文件');
    return;
  }
  uploadingImg.value = true;
  imgUploadMsg.value = '';
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const fd = new FormData();
    fd.append('file', f);
    // FormData 不能设 Content-Type，交给浏览器自动带 boundary
    const res = await auth.apiFetch(
      `/api/questions/${editForm.value.question_id}/images`,
      { method: 'POST', body: fd }
    );
    const data = await res.json();
    if (data.success && data.data && data.data.url) {
      const url = data.data.url;
      // 后端已把 <img> 追加进 question_content，但随后 saveEdit 的 PUT 会以
      // editForm.question_content 整体覆盖 —— 必须同步进本地表单，标签才不被抹掉。
      if ((editForm.value.question_content || '').indexOf(url) < 0) {
        const tag = `<img src="${url}" class="q-img" loading="lazy" />`;
        const base = editForm.value.question_content || '';
        editForm.value.question_content = base ? base + '\n' + tag : tag;
      }
      imgUploadMsg.value = '上传成功，图片已插入题干末尾；记得点「保存修改」持久化。';
      pickedImage.value = null;
      ElMessage.success('图片上传成功');
    } else {
      imgUploadMsg.value = data.detail || data.message || '上传失败';
      ElMessage.error(imgUploadMsg.value);
    }
  } catch (e: any) {
    imgUploadMsg.value = '上传异常：' + ((e && e.message) || e);
    ElMessage.error(imgUploadMsg.value);
  } finally {
    uploadingImg.value = false;
  }
}

// B 修复：编辑弹窗粘贴剪贴板图片 → data URI 插入字段（入库/保存时由后端提取落盘）
function handleEditPaste(field: string, event: any) {
  const cd = event.clipboardData || (event.originalEvent && event.originalEvent.clipboardData);
  if (!cd || !cd.items) return;
  const ta = event.target;
  const selStart = (ta && typeof ta.selectionStart === 'number') ? ta.selectionStart : 0;
  for (let i = 0; i < cd.items.length; i++) {
    const item = cd.items[i];
    if (item.kind === 'file' && item.type.indexOf('image') === 0) {
      const file = item.getAsFile();
      if (!file) continue;
      const reader = new FileReader();
      reader.onload = function (ev: any) {
        const tag = '<img src="' + ev.target.result + '" class="q-img" loading="lazy" />';
        const cur = (editForm.value as any)[field] || '';
        (editForm.value as any)[field] = cur.slice(0, selStart) + tag + cur.slice(selStart);
        if (ta) {
          setTimeout(function () {
            ta.selectionStart = ta.selectionEnd = selStart + tag.length;
          }, 0);
        }
      };
      reader.readAsDataURL(file);
      event.preventDefault();
      return;
    }
  }
}

async function saveEdit() {
      saving.value = true;
      try {
        const auth = (window as any).__VTJ_AUTH__;
        const payload: any = {
          subject_id: editForm.value.subject_id,
          question_content: editForm.value.question_content,
          answer: editForm.value.answer,
          answer_analysis: editForm.value.answer_analysis,
          difficulty: editForm.value.difficulty,
          // P2-5：题组材料随保存一起提交；清空后传 0/'' 以便后端解除关联
          group_id: editForm.value.group_id || 0,
          shared_content: editForm.value.shared_content || '',
          shared_content_images: editForm.value.shared_content_images || '',
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
          // P2-5：保存后按详情回填材料，确保再次打开编辑时显示的是已持久化内容
          if (data.data && data.data.question_id) {
            hydrateMaterialFromDetail(data.data.question_id);
          } else {
            hydrateMaterialFromDetail(editForm.value.question_id);
          }
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

    // ========== 批量处理（真实功能：后端批量接口） ==========
    const batchMode = ref(false);
    const selectedIds: any = ref([]);
    const batchSubjectId = ref(0);
    const allChecked = computed(() => questions.value.length > 0
      && selectedIds.value.length >= questions.value.length);

    function toggleBatchMode() {
      batchMode.value = !batchMode.value;
      selectedIds.value = [];
      batchSubjectId.value = 0;
    }
    function toggleAll(e: any) {
      selectedIds.value = e.target.checked
        ? questions.value.map((q: any) => q.question_id) : [];
    }
    async function batchDelete() {
      if (!selectedIds.value.length) return;
      if (!confirm(`确定删除选中的 ${selectedIds.value.length} 道题目吗？此操作不可恢复。`)) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/questions/batch-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question_ids: selectedIds.value }),
        });
        const data = await res.json();
        ElMessage.success(data.message || `已删除 ${data.deleted_count || selectedIds.value.length} 道题目`);
        selectedIds.value = [];
        await loadQuestions();
      } catch (e) {
        ElMessage.error('批量删除失败');
      }
    }
    async function batchReclassify() {
      if (!selectedIds.value.length || !batchSubjectId.value) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/questions/batch-reclassify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question_ids: selectedIds.value,
            subject_id: batchSubjectId.value,
          }),
        });
        const data = await res.json();
        ElMessage.success(data.message || `已修改 ${data.updated_count} 道题目科目`);
        selectedIds.value = [];
        batchSubjectId.value = 0;
        await loadQuestions();
      } catch (e) {
        ElMessage.error('批量改分类失败');
      }
    }

    // ========== 导航 ==========

    function goImport() { router.push('/question-import'); }
    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return {
      provider,
      keyword, filterSubject, filterType, filterDifficulty, filterReview,
      questions, page, pageSize, total, totalPages,
      showDetailModal, currentQuestion, groupInfo,
      showEditModal, saving, currentQuestionTypeName, editForm, showOptionFields, optionCount,
      editPreviewOpen, editHasImage,
      doSearch, changePage, subjectName, typeDisplayName, typeBadgeClass,
      renderStars, truncate, stripPromoText, hasImage, renderSummary,
      hasOptions, parsedOptions, isCorrectOption,
      showDetail, openEdit, addOption, removeOption, saveEdit, clearMaterial,
      handleEditPaste, deleteQuestion, goImport, handleLogout,
      batchMode, selectedIds, batchSubjectId, allChecked,
      toggleBatchMode, toggleAll, batchDelete,       batchReclassify, cleanHtmlContent,
      handleImageError, renderQuestionContent,
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
/* 批量处理：复用 admin_materials.vue 批量条规格 + 本页按钮 token，
   此前 7 个类无任何 CSS 定义，导致浏览器默认样式破坏页面风格 */
.btn-batch { padding: 8px 20px; background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-batch:hover { background: #eef3f9; }
.btn-batch-active { background: #1A3C6D; color: #fff; }
.batch-toolbar { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.batch-checkall { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #5a6b85; cursor: pointer; }
.batch-count { font-size: 13px; color: #5a6b85; }
.btn-mini-reclassify, .btn-mini-cancel { padding: 4px 10px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; color: #606266; }
.btn-mini-reclassify:hover, .btn-mini-cancel:hover { background: #f0f0f0; }
.btn-mini-reclassify:disabled, .btn-mini-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-mini-danger { padding: 4px 10px; border: 1px solid #f5c6cb; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; color: #C41E3A; }
.btn-mini-danger:hover { background: #C41E3A; color: #fff; border-color: #C41E3A; }
.td-check { margin-right: 6px; vertical-align: middle; cursor: pointer; }
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
/* P3b：待复核徽标 */
.review-flag { display: inline-block; margin-right: 4px; padding: 2px 6px; border-radius: 4px; background: #FEF0F0; color: #F56C6C; border: 1px solid #FBC4C4; font-size: 12px; line-height: 1.4; white-space: nowrap; }
.review-select { border-color: #FBC4C4; }
.badge-single { background: #409EFF; }
.badge-multi { background: #67C23A; }
.badge-judge { background: #8B5CF6; }
.badge-essay { background: #E6A23C; }
.badge-writing { background: #F56C6C; }

/* 详情弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
/* P0-4：1100px → 1280px / 80vh → 85vh。
   含图表题的题干图片原始宽度常达 1000px+，1100px 容器内会被压到 900px 以下，
   表格/流程图类图片文字不可读。 */
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 1280px; width: 94vw; max-height: 85vh; overflow-y: auto; }
.modal-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.modal-header h3 { color: #1A3C6D; margin: 0; flex: 1; }
.detail-modal { max-width: 1280px; }
.detail-field { margin-bottom: 14px; line-height: 1.8; }
.detail-field strong { color: #1A3C6D; }
.detail-content { margin-top: 6px; padding: 10px 14px; background: #f9fafb; border-radius: 8px; line-height: 1.8; }
/* P0-2：编辑弹窗实时预览区 */
.edit-preview-block { margin-top: 10px; border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden; }
.edit-preview-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #f5f7fa; border-bottom: 1px solid #e8e8e8; font-size: 13px; color: #1A3C6D; font-weight: 600; }
.edit-preview-toggle { display: inline-flex; align-items: center; gap: 4px; font-weight: 400; color: #666; cursor: pointer; }
.edit-preview-body { padding: 12px 14px; background: #fff; line-height: 1.8; font-size: 14px; color: #333; max-height: 420px; overflow-y: auto; }
.edit-preview-body :deep(img), .edit-preview-body img { max-width: 100%; max-height: 400px; height: auto; object-fit: contain; display: block; margin: 10px 0; border-radius: 6px; border: 1px solid #f0f0f0; background: #fff; }
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
.edit-modal { max-width: 1280px; }
.edit-modal h3 { color: #1A3C6D; margin: 0 0 20px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #1A3C6D; font-size: 14px; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
.form-textarea { resize: vertical; font-family: inherit; line-height: 1.6; }
/* P2-5：题组共享材料编辑区 */
.material-section { padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
.material-section label { color: #1A3C6D; }
.material-group-hint { font-weight: 400; color: #909399; font-size: 13px; }
.material-textarea { min-height: 120px; }
.material-preview { margin-top: 8px; padding: 10px 12px; max-height: 220px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; background: #fff; border: 1px dashed #cbd5e1; border-radius: 6px; color: #475569; line-height: 1.7; font-size: 13px; }
.material-actions { margin-top: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.option-edit-list { display: flex; flex-direction: column; gap: 6px; }
.option-edit-item { display: flex; align-items: center; gap: 8px; }
.option-edit-key { font-weight: 700; color: #1A3C6D; min-width: 24px; }
.option-edit-input { flex: 1; }
.img-upload-row { margin-top: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.img-upload-label { font-size: 13px; color: #606266; white-space: nowrap; }
.img-upload-input { flex: 1; min-width: 180px; padding: 4px 6px; font-size: 13px; }
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
</style>
