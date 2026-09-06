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
          <div class="detail-content" v-html="cleanHtmlContent(currentQuestion.full_content || currentQuestion.question_content)"></div>
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
      difficulty: 3, optionsParsed: { A: '', B: '', C: '', D: '' }
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

    // 新增：清洗HTML内容中的UTB ID，并修复图片路径（用于详情弹窗v-html显示）
    function cleanHtmlContent(text: string) {
      if (!text) return '';
      let cleaned = text;
      // 移除UTB ID（含选项后缀）
      cleaned = cleaned.replace(/UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*/gi, '');
      // 移除题号前缀
      cleaned = cleaned.replace(/第\s*\d+\s*题[：:]\s*/g, '');
      
      // 修复 [IMAGE:qid_idx] 占位符为真实img标签
      cleaned = cleaned.replace(/\[IMAGE:(\d+)[_-](\d+)\]/g, function(_match: string, qid: string, idx: string) {
        return '<img src="/static/questions/' + qid + '/' + qid + '_' + idx + '.png" ' +
          'class="question-img" loading="lazy" ' +
          'onerror="this.onerror=null;this.src=\'/static/images/placeholder.png\';this.alt=\'图片加载失败\'" />';
      });
      
      // 修复已有的img标签，添加onerror兜底
      cleaned = cleaned.replace(/<img\s+([^>]*?)(?:\s*\/?>|>)/g, function(match: string, attrs: string) {
        // 如果已经有onerror，不重复添加
        if (attrs.toLowerCase().includes('onerror')) return match;
        // 修复路径：确保 /static/questions/ 格式
        let fixedAttrs = attrs.replace(/src="(?!\/static\/|http)([^"]+)"/g, 'src="/static/questions/$1"');
        return '<img ' + fixedAttrs + ' onerror="this.onerror=null;this.src=\'/static/images/placeholder.png\';this.alt=\'图片加载失败\'" />';
      });
      
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
      editForm.value = {
        question_id: q.question_id,
        subject_id: q.subject_id || 1,
        question_content: q.full_content || q.question_content || '',
        answer: q.answer || '',
        answer_analysis: q.answer_analysis || '',
        difficulty: q.difficulty || 3,
        optionsParsed: Object.keys(opts).length > 0 ? { ...opts } : { A: '', B: '', C: '', D: '' },
      };
      showEditModal.value = true;
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
        const payload: any = {
          subject_id: editForm.value.subject_id,
          question_content: editForm.value.question_content,
          answer: editForm.value.answer,
          answer_analysis: editForm.value.answer_analysis,
          difficulty: editForm.value.difficulty,
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

    return {
      provider,
      keyword, filterSubject, filterType, filterDifficulty,
      questions, page, pageSize, total, totalPages,
      showDetailModal, currentQuestion, groupInfo,
      showEditModal, saving, currentQuestionTypeName, editForm, showOptionFields, optionCount,
      doSearch, changePage, subjectName, typeDisplayName, typeBadgeClass,
      renderStars, truncate, stripPromoText, hasImage, renderSummary,
      hasOptions, parsedOptions, isCorrectOption,
      showDetail, openEdit, addOption, removeOption, saveEdit,
      deleteQuestion, goImport, handleLogout, cleanHtmlContent,
      handleImageError,
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
</style>
