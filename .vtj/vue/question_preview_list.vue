<template>
  <div class="docs-question-list">
    <!-- 顶部统计 + 全部导入按钮 -->
    <div class="docs-list-topbar">
      <div class="docs-list-stats">
        <span class="docs-stat-total">共 {{ questions.length }} 题</span>
        <span class="docs-stat-answered">
          已答 {{ questions.filter(function(q){return q.answer && q.answer !== '待补充'}).length }}
        </span>
        <span class="docs-stat-missing" v-if="questions.filter(function(q){return !q.answer || q.answer === '待补充'}).length">
          ⚠ 缺答案 {{ questions.filter(function(q){return !q.answer || q.answer === '待补充'}).length }} 题
        </span>
        <span class="docs-stat-missing" v-if="questions.filter(function(q){return !q.analysis}).length" style="color:#e6a23c;background:rgba(230,162,60,0.1);">
          💡 缺解析 {{ questions.filter(function(q){return !q.analysis}).length }} 题
        </span>
        <span class="docs-stat-imported">
          已导入 {{ questions.filter(function(q){return q._imported}).length }}
        </span>
        <span class="docs-stat-dup" v-if="questions.filter(function(q){return q._is_duplicate}).length" style="color:#f56c6c;margin-left:8px;">
          ⚠ 重复 {{ questions.filter(function(q){return q._is_duplicate}).length }}
        </span>
        <span class="docs-stat-confidence" v-if="questions.filter(function(q){return q.confidence !== undefined && q.confidence < 0.5}).length" style="color:#f56c6c;margin-left:8px;background:rgba(245,108,108,0.1);padding:2px 8px;border-radius:4px;">
          🔴 低置信度 {{ questions.filter(function(q){return q.confidence !== undefined && q.confidence < 0.5}).length }}
        </span>
      </div>
      <div class="docs-list-actions-top">
        <button class="btn-primary btn-top-import" @click="$emit('import-all')" :disabled="loading" :title="mode === 'combined' ? '导入所有有答案的题目' : '导入所有题目（含待补充答案）'">
          <span>全部入库</span>
          <span style="font-size:15px;opacity:0.8;">({{ questions.filter(function(q){return !q._imported}).length }} 题)</span>
        </button>
        <button class="btn-secondary btn-top-close" @click="$emit('close')">完成</button>
      </div>
    </div>
    <!-- F-9b：复合题组头内嵌到题目流——在组内首题上方渲染（材料与子题同框），
         不再集中堆在列表顶部；材料>800 字自动折叠 -->
    <template v-for="(q, idx) in questions" :key="idx">
    <div class="docs-q-group-head" v-if="groupHeadIndex(q.question_number) !== -1
         && groupHeads[groupHeadIndex(q.question_number)].visible"
         :style="{ marginTop: idx === 0 ? '0' : '18px' }">
      <div class="docs-q-group-title">
        <span class="docs-q-group-badge" v-if="groupHeads[groupHeadIndex(q.question_number)].question_count > 1">复合题组</span>
        <span class="docs-q-group-meta" v-if="groupHeads[groupHeadIndex(q.question_number)].question_count > 1">
          给定材料 {{ groupHeads[groupHeadIndex(q.question_number)].material_length }} 字 · 共 {{ groupHeads[groupHeadIndex(q.question_number)].question_count }} 道小题
        </span>
        <button class="btn-mini-toggle" @click="toggleGroup(groupHeadIndex(q.question_number))"
                v-if="groupHeads[groupHeadIndex(q.question_number)].material_length > 0">{{ expandedGroups[groupHeadIndex(q.question_number)] ? '收起材料' : '展开材料' }}</button>
      </div>
      <div class="docs-q-material" v-if="groupHeads[groupHeadIndex(q.question_number)].material_length > 0 && expandedGroups[groupHeadIndex(q.question_number)]">
        <div class="docs-q-material-titles" v-if="groupHeads[groupHeadIndex(q.question_number)].material_titles && groupHeads[groupHeadIndex(q.question_number)].material_titles.length">
          <span class="docs-q-mt" v-for="(t, ti) in groupHeads[groupHeadIndex(q.question_number)].material_titles" :key="ti">{{ t }}</span>
        </div>
        <div class="docs-q-material-text">{{ groupHeads[groupHeadIndex(q.question_number)].material_preview }}</div>
        <button class="btn-mini-expand" v-if="groupHeads[groupHeadIndex(q.question_number)].truncated" @click="toggleGroup(groupHeadIndex(q.question_number))">
          [展开全部 {{ groupHeads[groupHeadIndex(q.question_number)].material_length }} 字]
        </button>
      </div>
    </div>
    <div class="docs-q-section-head" v-if="showSectionHead(idx)" @click="toggleSection(q.xingce_subcategory)">
      <span class="docs-q-section-caret">{{ isSectionCollapsed(q.xingce_subcategory) ? '▸' : '▾' }}</span>
      <span class="docs-q-section-name">{{ q.xingce_subcategory || '未分区' }}</span>
      <span class="docs-q-section-count">{{ sectionCount(q.xingce_subcategory) }} 题</span>
    </div>
    <div class="docs-q-card" v-if="!isSectionCollapsed(q.xingce_subcategory)" :id="'qcard_' + idx" :class="{ 'docs-q-card-noans': !q.answer || q.answer === '待补充', 'docs-q-card-suspicious': q.suspicious, 'docs-q-card-grouped': qnumInMultiGroup(q.question_number) }">
      <div class="docs-q-header">
        <span class="docs-q-num">第 {{ idx + 1 }} 题</span>
        <span class="docs-q-type">{{ q.question_type_detail || '单选题' }}</span>
        <span class="docs-q-subject">{{ q.subject_category || '公专' }}</span>
        <span class="docs-q-dup-badge" v-if="q._is_duplicate" style="color:#f56c6c;font-size:15px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'该题目已存在（相似度 ' + Math.round((q._similarity || 0) * 100) + '%），将自动跳过导入'">⚠ 该题目已存在</span>
        <span class="docs-q-ans-badge" v-if="q.answer && q.answer !== '待补充'" style="color:#4ade80;font-size:15px;margin-right:8px;" title="已匹配答案">已匹配答案 ✓</span>
        <span class="docs-q-ans-badge docs-q-ans-badge-warn" v-else style="color:#f59e0b;font-size:15px;margin-right:8px;" title="缺少答案，请在下方手动录入">⚠ 缺答案</span>
        <span v-if="!q.analysis" class="docs-q-ans-badge" style="color:#e6a23c;font-size:15px;margin-right:8px;" title="缺少答案解析，请点击「+解析图」或「编辑」补充，避免误以为题目完整">⚠ 缺解析</span>
        <span class="docs-q-conf-badge" v-if="q.confidence !== undefined && q.confidence < 0.5" style="color:#f56c6c;font-size:13px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'匹配置信度仅 ' + Math.round((q.confidence||0)*100) + '%，建议人工核对'">🔴 低置信度({{ Math.round((q.confidence||0)*100) }}%)</span>
        <span class="docs-q-suspicious-badge" v-if="q.suspicious" :title="q.suspicious_reason || '块内混入了其他题号，可能吞并了相邻题目，建议核对或删除'">⚠ 疑似串题</span>
        <button class="btn-mini-reverify" @click="$emit('reverify', idx)" title="重新校验选项分割">重检</button>
        <button class="btn-mini-img" :disabled="attachingKey === (idx + ':content')"
                @click="pickImage(idx, 'content')" title="为该题题干添加图片">+题干图</button>
        <button class="btn-mini-edit" @click="openEditDialog(idx)" title="编辑题目">编辑</button>
        <button class="btn-mini-import" @click="$emit('import-one', idx)" :disabled="q._imported">
          {{ q._imported ? '已导入' : '导入此题' }}
        </button>
        <button class="btn-mini-delete" @click="$emit('delete-question', idx)" :disabled="q._imported"
                title="从本次导入中剔除该题（已入库的题请到「题目管理」删除）">删除</button>
      </div>
      <div class="docs-q-body">
        <div class="docs-q-content" v-html="renderQuestionContent(q.question_content)"></div>
         <div class="docs-q-kao-tags" v-if="q.kao_points_normalized && q.kao_points_normalized.length">
           <span class="docs-q-kao-label">考点：</span>
           <span class="docs-q-kao-tag" v-for="(k, ki) in q.kao_points_normalized" :key="'k' + ki">{{ k }}</span>
         </div>
        <div class="docs-q-requirements" v-if="q.requirements && q.requirements.length">
          <div class="docs-q-ans-label" style="margin-bottom:4px;">题目要求：</div>
          <div class="docs-q-req-text" style="white-space:pre-wrap;word-break:break-word;color:#b0b8c4;font-size:15px;line-height:1.7;"
               v-html="renderQuestionContent(Array.isArray(q.requirements) ? q.requirements.join('\n') : q.requirements)"></div>
        </div>
        <div class="docs-q-options" v-if="q.options && q.options.length">
          <span class="docs-q-opt" v-for="opt in q.options" :key="opt.key">
            <span class="docs-q-opt-text">{{ opt.key }}. <span class="docs-q-opt-val" v-html="renderQuestionContent(opt.value)"></span></span>
            <button class="btn-mini-img" :disabled="attachingKey === (idx + ':' + opt.key)"
                    @click="pickImage(idx, 'option', opt.key)"
                    :title="'为选项 ' + opt.key + ' 添加图片'">+图</button>
          </span>
        </div>
        <div class="docs-q-answer-row" :class="{ 'docs-q-answer-row-warn': !q.answer || q.answer === '待补充' }" @paste="handlePaste(idx, 'answer', null, $event)" tabindex="0" title="点击此处后可直接 Ctrl+V 粘贴图片到答案">
          <span class="docs-q-ans-label">题目答案：</span>
          <button class="btn-mini-img" :disabled="attachingKey === (idx + ':answer')"
                  @click="pickImage(idx, 'answer')" title="为该题答案添加图片">+答案图</button>
          <input v-if="isShortAnswer(q)" class="docs-q-ans-input" v-model="q.answer" :placeholder="isJudgeQuestion(q) ? '正确/错误' : 'A/B/C/D'" :maxlength="isJudgeQuestion(q) ? 8 : 4" />
          <div v-else class="docs-q-ans-text" style="flex:1;min-width:0;white-space:pre-wrap;word-break:break-word;color:#b0b8c4;font-size:15px;line-height:1.7;" v-html="renderQuestionContent(q.answer || '')"></div>
          <span class="docs-q-ans-hint" v-if="!q.answer || q.answer === '待补充'">（必填 — {{ isJudgeQuestion(q) ? '判断题请填写 正确 或 错误' : '请输入选项字母' }}）</span>
        </div>
        <div class="docs-q-analysis" @paste="handlePaste(idx, 'analysis', null, $event)" tabindex="0" title="点击此处后可直接 Ctrl+V 粘贴图片到解析">
          <div class="docs-q-ans-label" style="margin-bottom:4px;">题目解析：
            <button class="btn-mini-img" :disabled="attachingKey === (idx + ':analysis')"
                    @click="pickImage(idx, 'analysis')" title="为该题解析添加图片">+解析图</button>
          </div>
          <div v-if="q.analysis" class="docs-q-analysis-text" style="white-space:pre-wrap;word-break:break-word;line-height:1.7;" v-html="renderQuestionContent(q.analysis)"></div>
          <div v-else class="docs-q-analysis-text" style="white-space:pre-wrap;word-break:break-word;line-height:1.7;color:#e6a23c;font-style:italic;padding:6px 0;">⚠ 暂无答案解析，请补充（点击上方「+解析图」添加图片解析，或点「编辑」补文字解析）</div>
        </div>
      </div>
    </div>
    </template>
     <div class="form-actions" style="justify-content:center;margin-top:16px;flex-wrap:wrap;">
      <button class="btn-primary" @click="$emit('import-all')" :disabled="loading" style="min-width:200px;">
        {{ loading ? '导入中...' : '全部导入（' + questions.filter(function(q){return !q._imported && !q._is_duplicate}).length + ' 题）' }}
      </button>
      <button class="btn-secondary" @click="$emit('close')">完成</button>
    </div>

    <!-- 编辑对话框 -->
    <div class="edit-dialog-overlay" v-if="editDialogVisible" @click.self="closeEditDialog">
      <div class="edit-dialog">
        <div class="edit-dialog-header">
          <h3>编辑题目</h3>
          <button class="edit-dialog-close" @click="closeEditDialog">×</button>
        </div>
        <div class="edit-dialog-body">
          <div class="edit-field">
            <label>题干：</label>
            <textarea v-model="editForm.question_content" rows="4" placeholder="请输入题干内容（可 Ctrl+V 粘贴图片）"
                      @paste="handleEditPaste('question_content', $event)"></textarea>
          </div>
          <div class="edit-field">
            <label>题型：</label>
            <select v-model="editForm.question_type_detail">
              <option value="单选题">单选题</option>
              <option value="多选题">多选题</option>
              <option value="判断题">判断题</option>
              <option value="填空题">填空题</option>
              <option value="简答题">简答题</option>
            </select>
          </div>
          <div class="edit-field">
            <label>难度：</label>
            <select v-model="editForm.difficulty">
              <option value="简单">简单</option>
              <option value="中等">中等</option>
              <option value="困难">困难</option>
            </select>
          </div>
          <div class="edit-field">
            <label>选项：</label>
            <div class="edit-options-list">
              <div class="edit-option-item" v-for="(opt, optIdx) in editForm.options" :key="optIdx">
                <span class="edit-option-key">{{ opt.key }}.</span>
                <input v-model="opt.value" :placeholder="'选项' + opt.key" />
                <button class="edit-option-delete" @click="removeOption(optIdx)" v-if="editForm.options.length > 2">×</button>
              </div>
              <button class="edit-option-add" @click="addOption">+ 添加选项</button>
            </div>
          </div>
          <div class="edit-field" :class="{ 'field-missing': !editForm.answer || editForm.answer === '待补充' }">
            <label>答案：<span class="required">*</span></label>
            <input v-model="editForm.answer" placeholder="请输入答案（如：A、AB、ABCD）" />
            <span class="field-hint" v-if="!editForm.answer || editForm.answer === '待补充'">
              ⚠ 必填项
            </span>
          </div>
          <div class="edit-field" :class="{ 'field-warning': !editForm.analysis }">
            <label>答案解析：</label>
            <textarea v-model="editForm.analysis" rows="3" placeholder="请输入答案解析（可选，可 Ctrl+V 粘贴图片）"
                      @paste="handleEditPaste('analysis', $event)"></textarea>
            <span class="field-hint" v-if="!editForm.analysis">
              💡 建议补充解析，帮助学生理解
            </span>
          </div>
        </div>
        <div class="edit-dialog-footer">
          <button class="btn-secondary" @click="closeEditDialog">取消</button>
          <button class="btn-primary" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// @ts-nocheck
import { defineComponent, ref, reactive, computed, watch, onMounted, getCurrentInstance } from 'vue';
import { useProvider } from '@vtj/renderer';
import { renderQuestionContent } from '@/utils/questionRender';

export default defineComponent({
  name: 'QuestionPreviewList',
  props: {
    // ===== 数据入口 A（向后兼容）：导入预览的扁平题目列表 =====
    questions: { type: Array, default: function() { return []; } },
    // 复合题组：后端按「给定材料」聚合，与 questions 并存（向后兼容，旧调用方不传即退化为旧渲染）
    // 旧形态字段 material_length / material_titles / material_preview（即 material_text）保持不变
    groups: { type: Array, default: function() { return []; } },

    // ===== 数据入口 B（统一契约）：与 GET /api/questions/group/{id} 同构 =====
    // 三端（学生端 / 教师端 / 管理员端）共用本题组渲染组件时的唯一入口：
    //   group   : { id, title, shared_content, group_type, subject, source }
    //   members : [ { question_content, options, answer, answer_analysis,
    //                 requirements, question_type_detail, difficulty,
    //                 score, need_review, parent_id, ... } ]
    // 入口 A 与入口 B 在脚本内归一到同一套渲染数据，模板无需分叉。
    group: { type: Object, default: null },
    members: { type: Array, default: function() { return []; } },

    mode: { type: String, default: 'combined' },
    loading: { type: Boolean, default: false },

    // 学生端只读开关：隐藏全部编辑/导入控件，并封死所有写事件与写方法。
    // 教师端/管理员端与导入预览一律传 false（缺省即 false，行为与重构前一致）。
    readonly: { type: Boolean, default: false }
  },
    emits: ['import-one', 'import-all', 'reverify', 'close', 'edit-question', 'delete-question', 'attach-image'],
  setup(props, { emit }) {
    const provider = useProvider({ id: 'question_preview_list', version: '1785406000000' });
    
    // 编辑对话框状态
    const editDialogVisible = ref(false);
    const editIndex = ref(-1);
    const editForm = reactive({
      question_content: '',
      question_type_detail: '单选题',
      difficulty: '中等',
      options: [],
      answer: '',
      analysis: ''
    });

    // 打开编辑对话框（只读态直接拒绝：编辑弹窗由 editDialogVisible 控制，无需改模板即可隐藏）
    function openEditDialog(idx) {
      if (isReadonly.value) return;
      const q = props.questions[idx];
      editIndex.value = idx;
      editForm.question_content = q.question_content || '';
      editForm.question_type_detail = q.question_type_detail || '单选题';
      editForm.difficulty = q.difficulty || '中等';
      editForm.options = q.options ? JSON.parse(JSON.stringify(q.options)) : [
        { key: 'A', value: '' },
        { key: 'B', value: '' },
        { key: 'C', value: '' },
        { key: 'D', value: '' }
      ];
      editForm.answer = q.answer || '';
      editForm.analysis = q.analysis || '';
      editDialogVisible.value = true;
    }

    // 关闭编辑对话框
    function closeEditDialog() {
      editDialogVisible.value = false;
      editIndex.value = -1;
    }

    // 保存编辑
    // F-7：编辑弹层内粘贴剪贴板图片 → data URI 插入对应字段。
    // 入库时由后端 _extract_and_save_images 统一提取落盘（复用既有管线，不新增端点）。
    function handleEditPaste(field, event) {
      if (isReadonly.value) return;
      const cd = event.clipboardData || (event.originalEvent && event.originalEvent.clipboardData);
      if (!cd || !cd.items) return;
      // 提前捕获目标元素与光标位置（reader 回调是异步的，晚取会丢）
      const ta = event.target;
      const selStart = (ta && typeof ta.selectionStart === 'number') ? ta.selectionStart : 0;
      const selEnd = (ta && typeof ta.selectionEnd === 'number') ? ta.selectionEnd : selStart;
      for (let i = 0; i < cd.items.length; i++) {
        const item = cd.items[i];
        if (item.kind === 'file' && item.type.indexOf('image') === 0) {
          const file = item.getAsFile();
          if (!file) continue;
          const reader = new FileReader();
          reader.onload = function (ev) {
            const tag = '<img src="' + ev.target.result + '" class="q-img" loading="lazy" />';
            // B-修复：在光标（或选区）位置插入，不再追加到文本末端
            const cur = (editForm[field] || '');
            editForm[field] = cur.slice(0, selStart) + tag + cur.slice(selEnd);
            const newPos = selStart + tag.length;
            if (ta) {
              setTimeout(function () {
                ta.selectionStart = ta.selectionEnd = newPos;
                ta.focus();
              }, 0);
            }
          };
          reader.readAsDataURL(file);
          event.preventDefault();
          return;
        }
      }
    }

    function saveEdit() {
      if (isReadonly.value) return;
      // 必填字段验证
      if (!editForm.answer || editForm.answer === '待补充') {
        alert('请填写正确答案');
        return;
      }
      
      // 更新本地数据
      const q = props.questions[editIndex.value];
      q.question_content = editForm.question_content;
      q.question_type_detail = editForm.question_type_detail;
      q.difficulty = editForm.difficulty;
      q.options = JSON.parse(JSON.stringify(editForm.options));
      q.answer = editForm.answer;
      q.analysis = editForm.analysis;
      
      // 通知父组件
      emitWrite('edit-question', {
        index: editIndex.value,
        data: {
          question_content: editForm.question_content,
          question_type_detail: editForm.question_type_detail,
          difficulty: editForm.difficulty,
          options: editForm.options,
          answer: editForm.answer,
          analysis: editForm.analysis
        }
      });
      
      closeEditDialog();
    }

    // 添加选项
    function addOption() {
      const keys = editForm.options.map(function(o) { return o.key; });
      const nextKey = String.fromCharCode(Math.max.apply(null, keys.map(function(k) { return k.charCodeAt(0); })) + 1);
      editForm.options.push({ key: nextKey, value: '' });
    }

    // 删除选项
    function removeOption(idx) {
      if (editForm.options.length > 2) {
        editForm.options.splice(idx, 1);
      }
    }

    // 判断题答案填写「正确/错误」而非选项字母
    // 后端已把无选项判断题的答案从任意字母纠正为判定词（见 text_parser.judge_verdict_from_text），
    // 输入框的占位符与长度限制必须随之自适应，否则教师会照着「A/B/C/D」填出无效答案。
    function isJudgeQuestion(q) {
      if (!q) return false;
      if (q.question_type_detail === '判断题') return true;
      return !(q.options && q.options.length >= 2);
    }

    // ===== 申论长文本答案的展示分流（2026-10-01 新增）=====
    // 背景：原「答案」输入框是选择题专用的（maxlength=4、placeholder="A/B/C/D"），
    // 而申论答案是数百字的长文本（实测国考/安徽参考答案常达 500 字以上），
    // 用单行输入框会导致正确解析出的答案在录入环节被截断丢失。
    // 策略：只有「短答案题型」保留可编辑输入框；其余（申论等）改为多行只读展示区。
    // 纯文本的换行不在 renderQuestionContent 内转换（见 src/utils/questionRender.js
    // 第 124 行：纯文本直接原样返回），因此换行保留依赖 CSS white-space:pre-wrap。
    function isShortAnswer(q) {
      if (!q) return false;
      // 学生端只读：答案一律走多行只读展示区，绝不出现可编辑输入框
      if (isReadonly.value) return false;
      // 有选项的题（含判断/单选/多选）一律走短答案输入框
      if (q.options && q.options.length) return true;
      const t = String(q.question_type_detail || q.type_name || '');
      if (/单选|多选|判断/.test(t)) return true;
      // 无选项但答案形如 A/B/C/D 的，仍按短答案处理（兼容历史数据）
      const a = String(q.answer || '').trim();
      return a.length > 0 && a.length <= 8 && /^[A-Ha-h]([、,，\s]*[A-Ha-h])*$/.test(a);
    }

    // ===== 预览态为题目添加图片（2026-09-29 新增）=====
    // 上传态标记：`${idx}:${optionKey||'content'}`，用于禁用对应按钮防重复提交。
    // 真正的上传与状态回填由父组件（question_import.vue）完成 —— 它持有
    // import_id 与 questions 数据源，本组件只负责选文件与发出事件。
    const attachingKey = ref('');

    // ============================================================
    // 三端共用题组渲染（任务 23 / 模块 E-2）
    // ============================================================
    // 内部渲染顺序固定：材料（可折叠，默认展开）→ 题目要求 → 小题列表（每题带答案 + 解析）
    //   · 材料      —— 题组共享上下文，来自 groups[].material_text 或 group.shared_content
    //   · 题目要求  —— 小题的 requirements（string 与 array 两形态都支持）
    //   · 小题列表  —— 每题答案（answer）与解析（answer_analysis）
    // 两条数据入口归一后共用模板既有结构，不新增任何容器。
    const MATERIAL_FOLD_THRESHOLD = 800; // 超过 800 字时提供「摘要 + 展开」形态，避免上万字材料淹没首屏
    const MATERIAL_CLIP_LEN = 600;       // 折叠态先给一段摘要

    // 哪些组处于展开态（key 而非下标，避免组顺序变化时展开错位）
    // 规格要求材料「默认展开」：未显式折叠过的组一律视为展开。
    // 必须把默认值真实写进 ref —— 模板里 `expandedGroups[gidx] ? '收起材料' : '展开材料'`
    // 直接读原始 ref，靠读取时的兜底默认值会让按钮文案与实际显示状态自相矛盾。
    const expandedGroups = ref({});

    function isGroupExpanded(gidx) {
      return expandedGroups.value[String(gidx)] !== false;
    }

    function toggleGroup(gidx) {
      const key = String(gidx);
      const next = {};
      Object.keys(expandedGroups.value).forEach(function (k) {
        next[k] = expandedGroups.value[k];
      });
      next[key] = !isGroupExpanded(gidx);
      expandedGroups.value = next;
    }

    // ── 行测分区折叠 ──────────────────────────────────────
    // 行测单卷 5 个分区、130 题，一屏铺开难以逐题核对，故按分区折叠。
    // key 用分区名而非下标：题目顺序变化（含重导入）时展开态不会错位。
    const collapsedSections = ref({});

    // 无分区信息（如公专链路）一律不折叠，保持既有渲染完全不变
    function isSectionCollapsed(sec) {
      if (!sec) return false;
      return collapsedSections.value[sec] === true;
    }

    function toggleSection(sec) {
      if (!sec) return;
      const next = {};
      Object.keys(collapsedSections.value).forEach(function (k) {
        next[k] = collapsedSections.value[k];
      });
      next[sec] = !collapsedSections.value[sec];
      collapsedSections.value = next;
    }

    // 仅在该题所属分区与上一题不同处插入分区头；
    // 题目无 xingce_subcategory 时返回 false，故公专预览不会多出「未分区」头
    function showSectionHead(idx) {
      const list = props.questions || [];
      const cur = (list[idx] || {}).xingce_subcategory || '';
      if (!cur) return false;
      if (idx <= 0) return true;
      const prev = (list[idx - 1] || {}).xingce_subcategory || '';
      return cur !== prev;
    }

    function sectionCount(sec) {
      const list = props.questions || [];
      let n = 0;
      for (let i = 0; i < list.length; i++) {
        if (((list[i] || {}).xingce_subcategory || '') === (sec || '')) n++;
      }
      return n;
    }

    // ── 统一契约归一 ─────────────────────────────────────
    // 入口 B 的 members[] 字段名与导入预览的 questions[] 不同（answer_analysis vs analysis），
    // 这里只做「改名 + 缺省补齐」，绝不改写内容本身：
    // 图片 <img> 已由后端净化，仍交由 renderQuestionContent 做白名单清洗。
    const MATERIAL_TITLE_RE = /^[ \t\u3000]*(给定资料|资料|材料)[ \t\u3000]*[一二三四五六七八九十百\d]+[ \t\u3000]*[：:、.．]?[ \t\u3000]*(.*)$/gm;

    // 契约只给 shared_content 一整块，没有 material_titles；从正文行首还原小标题，
    // 让两个入口的材料呈现形态一致（旧入口的「给定资料1/2/3」小标签）。
    function extractMaterialTitles(text) {
      const out = [];
      const s = String(text || '');
      if (!s) return out;
      MATERIAL_TITLE_RE.lastIndex = 0;
      let m = MATERIAL_TITLE_RE.exec(s);
      while (m !== null) {
        const head = (m[1] + ' ' + (m[2] || '')).trim();
        if (head && out.indexOf(head) < 0) out.push(head);
        m = MATERIAL_TITLE_RE.exec(s);
      }
      return out;
    }

    // 兼容两种选项形态：{key,value} 对象（模板契约）或 "A. xxx" 裸字符串
    function normalizeOptions(options) {
      if (!Array.isArray(options)) return [];
      return options.map(function (o) {
        if (o && typeof o === 'object') return o;
        const s = String(o == null ? '' : o);
        const m = s.match(/^\s*([A-Ha-h])\s*[.、．)）:：]?\s*([\s\S]*)$/);
        return m ? { key: m[1].toUpperCase(), value: m[2] } : { key: '', value: s };
      });
    }

    // 统一契约 members[] → 组件内部题目形态（与入口 A 的 questions[] 同构）
    function normalizeMember(src, idx, groupCtx) {
      const m = src || {};
      const g = groupCtx || {};
      const req = m.requirements;
      return {
        question_id: m.question_id || m.id || 0,
        question_number: m.question_number || '',
        parent_id: m.parent_id || 0,
        need_review: m.need_review || 0,
        question_content: m.question_content || '',
        options: normalizeOptions(m.options),
        // 契约字段名为 answer_analysis，内部统一叫 analysis
        answer: m.answer || '',
        analysis: m.answer_analysis || m.analysis || '',
        question_type_detail: m.question_type_detail || '选择题',
        difficulty: m.difficulty || '中等',
        score: m.score || 0,
        // 题目要求：string 与 array 两形态都归一成数组，渲染层负责 join
        requirements: Array.isArray(req) ? req.slice() : (req ? [req] : []),
        // 考点标签：契约未强制返回时留空数组，模板 v-if 自然跳过
        kao_points_normalized: Array.isArray(m.kao_points_normalized)
          ? m.kao_points_normalized
          : (Array.isArray(m.kao_points) ? m.kao_points : []),
        subject_category: m.subject_category || m.subject || g.subject || '',
        xingce_subcategory: m.xingce_subcategory || m.subcategory || '',
        // 导入评审态：契约来自已入库数据，一律视为未导入、无重复
        _imported: false,
        _is_duplicate: false,
        _qpl_index: idx
      };
    }

    // 入口 B 归一：把 members[] 写进 questions，使模板的 v-for 直接消费同一份数据。
    // 仅在本组件「拥有」该数组时改写 —— 入口 A（导入预览传 questions）时完全不介入，
    // 因此 question_import.vue 的既有调用行为零变化。
    const ownedQuestions = new Set();

    function syncUnifiedMembers() {
      const list = props.questions || [];
      const incoming = props.members || [];
      if (!incoming.length) return;
      const owns = ownedQuestions.has(list) || (!list.length && !!props.group);
      if (!owns) return;
      const ctx = props.group || {};
      const normalized = incoming.map(function (m, i) { return normalizeMember(m, i, ctx); });
      list.splice(0, list.length);
      Array.prototype.push.apply(list, normalized);
      ownedQuestions.add(list);
    }

    // group 可能在 members 之后异步到位，故一并监听（members 内部变化也要重算）
    watch(
      function () { return [props.members, props.group]; },
      syncUnifiedMembers,
      { immediate: true, deep: true }
    );

    // 组头数据：两个入口归一到同一结构。
    // 入口 A（groups[]）  material_length / material_titles / material_text  原样透传
    // 入口 B（group）     shared_content 的长度即 material_length，小标题从正文还原
    function buildUnifiedHead() {
      const g = props.group;
      if (!g || typeof g !== 'object') return null;
      const text = String(g.shared_content || '');
      const len = text.length;
      const folded = len > MATERIAL_FOLD_THRESHOLD && !isGroupExpanded(0);
      const count = (props.members || []).length || (props.questions || []).length;
      return {
        group_key: 'group_' + (g.id || 0),
        title: g.title || '',
        group_type: g.group_type || '',
        source: g.source || '',
        material_length: len,
        material_titles: extractMaterialTitles(text),
        question_count: count,
        material_preview: folded ? text.slice(0, MATERIAL_CLIP_LEN) : text,
        truncated: folded,
        visible: len > 0 || count > 1
      };
    }

    const groupHeads = computed(function () {
      const unified = buildUnifiedHead();
      const legacy = (props.groups || []).map(function (g, i) {
        const len = g.material_length || 0;
        const text = g.material_text || '';
        const folded = len > MATERIAL_FOLD_THRESHOLD && !isGroupExpanded(i);
        return {
          group_key: g.group_key,
          title: g.title || '',
          material_length: len,
          material_titles: g.material_titles || [],
          question_count: g.question_count || 0,
          material_preview: folded ? text.slice(0, MATERIAL_CLIP_LEN) : text,
          truncated: folded,
          // 单题无材料时不渲染组头，完全退回旧版单卡行为
          visible: len > 0 || (g.question_count || 0) > 1
        };
      });
      return unified ? [unified].concat(legacy) : legacy;
    });

    // 组数变化时补齐默认展开态：新增组默认展开，用户已折叠过的组保持原状
    watch(
      function () { return groupHeads.value.length; },
      function (n) {
        const next = {};
        Object.keys(expandedGroups.value).forEach(function (k) { next[k] = expandedGroups.value[k]; });
        for (let i = 0; i < n; i++) {
          if (!(String(i) in next)) next[String(i)] = true;
        }
        expandedGroups.value = next;
      },
      { immediate: true }
    );

    // F-9b：题目 → 组头索引映射（按组内首题的 question_number 匹配），
    // 供模板把组头渲染在「组内首题上方」，实现材料与子题同框（不再集中堆顶部）。
    const groupHeadIndexByQnum = computed(function () {
      const map = {};
      (props.groups || []).forEach(function (g, gi) {
        const members = g.questions || [];
        for (let k = 0; k < members.length; k++) {
          const qn = members[k] && members[k].question_number;
          if (qn != null && !(String(qn) in map)) {
            map[String(qn)] = gi;
            break;
          }
        }
      });
      return map;
    });
    function groupHeadIndex(qnum) {
      if (qnum == null) return -1;
      const v = groupHeadIndexByQnum.value[String(qnum)];
      return v === undefined ? -1 : v;
    }

    // F-9c：题目 → 组归属（question_number → 组索引，仅计 question_count>1 的组）。
    // 供模板把组内题目卡片渲染成「同一框架」（材料+各子题干+答案+解析不切割）。
    const multiGroupByQnum = computed(function () {
      const map = {};
      (props.groups || []).forEach(function (g, gi) {
        if ((g.question_count || 0) < 2) return;
        (g.questions || []).forEach(function (m) {
          const qn = m && m.question_number;
          if (qn != null && !(String(qn) in map)) map[String(qn)] = gi;
        });
      });
      return map;
    });
    function qnumInMultiGroup(qnum) {
      if (qnum == null) return false;
      return String(qnum) in multiGroupByQnum.value;
    }

    // 归一后的完整契约（便于调用方直接取用，也便于测试断言渲染顺序）
    const normalizedContract = computed(function () {
      const g = props.group || {};
      const members = (props.members || []).map(function (m, i) {
        return normalizeMember(m, i, g);
      });
      return {
        group: {
          id: g.id || 0,
          title: g.title || '',
          shared_content: g.shared_content || '',
          group_type: g.group_type || '',
          subject: g.subject || '',
          source: g.source || ''
        },
        members: members,
        total: members.length
      };
    });

    const hasUnifiedContract = computed(function () {
      return !!props.group && (props.members || []).length > 0;
    });

    // ============================================================
    // 学生端只读（模块 E-2）
    // ============================================================
    // <template> 属设计器领地，禁止手改结构，故只读态的「隐藏编辑控件」在脚本内完成：
    //   1) 写屏障 —— 封死一切写方法与写事件（openEditDialog / pickImage / handlePaste / saveEdit）
    //   2) 运行期只读样式 —— 把编辑/导入控件 display:none（材料折叠按钮保留）
    // 两条互为兜底：样式被外部覆盖时仍有脚本兜底，脚本路径被绕过时仍有样式兜底。
    // 更彻底的方案是在设计器里给这些按钮加 `v-if="!readonly"`，属 UI 结构变更，回设计器操作。
    const isReadonly = computed(function () { return props.readonly === true; });

    const READONLY_STYLE_ID = 'qpl-readonly-style';
    // 注意：.btn-mini-toggle / .btn-mini-expand（材料折叠）在名单之外，学生端仍需折叠材料
    const READONLY_HIDDEN_SELECTORS = [
      '.docs-list-topbar',        // 顶部统计 + 全部入库（导入评审视角）
      '.form-actions',            // 底部全部导入 + 完成
      '.btn-mini-edit',
      '.btn-mini-import',
      '.btn-mini-delete',
      '.btn-mini-reverify',
      '.btn-mini-img',            // +题干图 / 选项+图 / +答案图 / +解析图
      '.docs-q-dup-badge',
      '.docs-q-ans-badge',        // 已匹配答案 / 缺答案 / 缺解析
      '.docs-q-suspicious-badge',
      '.docs-q-conf-badge'
    ];

    // 只读标记打在组件根节点上，样式选择器据此收敛作用域，不污染其他页面
    const instance = getCurrentInstance();

    function ensureReadonlyStyle() {
      if (typeof document === 'undefined') return;
      if (document.getElementById(READONLY_STYLE_ID)) return;
      const styleEl = document.createElement('style');
      styleEl.id = READONLY_STYLE_ID;
      styleEl.textContent = READONLY_HIDDEN_SELECTORS.map(function (sel) {
        return '[data-qpl-readonly] ' + sel + ' { display: none !important; }';
      }).join('\n');
      document.head.appendChild(styleEl);
    }

    onMounted(function () {
      const root = (instance && instance.proxy && instance.proxy.$el) || null;
      if (root && root.nodeType === 1) root.setAttribute('data-qpl-readonly', '');
    });

    // 写事件闸门：只读态一律不外发。模板里直接 $emit 的那几处（导入/删除/重检/完成）
    // 已被只读样式隐藏，这里只兜住脚本侧发出的 attach-image / edit-question。
    function emitWrite(event, payload) {
      if (isReadonly.value) return;
      emit(event, payload);
    }

    watch(isReadonly, function (ro) {
      if (!ro) return;
      ensureReadonlyStyle();
      attachingKey.value = '';
      editDialogVisible.value = false;
    }, { immediate: true });

    function pickImage(idx, target, optionKey) {
      if (isReadonly.value) return;
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/png,image/jpeg,image/gif,image/webp';
      input.style.display = 'none';
      input.onchange = function () {
        const f = input.files && input.files[0];
        if (input.parentNode) input.parentNode.removeChild(input);
        if (!f) return;
        attachingKey.value = idx + ':' + (optionKey || target);
        emitWrite('attach-image', { idx: idx, target: target, optionKey: optionKey || null, file: f });
      };
      // 用户取消选择时不会触发 onchange，需自行清理节点
      input.addEventListener('cancel', function () {
        if (input.parentNode) input.parentNode.removeChild(input);
      });
      document.body.appendChild(input);
      input.click();
    }

    // 父组件上传结束（成功或失败）后调用，解除按钮禁用
    function finishAttach() {
      attachingKey.value = '';
    }

    // 复制粘贴图片快捷添加：监听 paste 事件，从剪贴板取图片文件复用 attach-image 链路
    function handlePaste(idx, target, optionKey, event) {
      if (isReadonly.value) return;
      const cd = event.clipboardData || (event.originalEvent && event.originalEvent.clipboardData);
      if (!cd || !cd.items) return;
      for (let i = 0; i < cd.items.length; i++) {
        const item = cd.items[i];
        if (item.kind === 'file' && item.type.indexOf('image') === 0) {
          const file = item.getAsFile();
          if (file) {
            attachingKey.value = idx + ':' + (optionKey || target);
            emitWrite('attach-image', { idx: idx, target: target, optionKey: optionKey || null, file: file });
            event.preventDefault();
            return;
          }
        }
      }
    }

    // ============================================================
    // W3-1：科目/子科目建议展示 + 一键覆盖（仅脚本，DOM 注入既有渲染位）
    // ============================================================
    // 建议数据由父组件（question_import.vue）从后端响应体的
    //   subject_suggestion { name, confidence, matched_keywords }
    //   subcategory_suggestion { name, confidence }
    // 逐题 stamp 到题目对象（q.subject_suggestion / q.subcategory_suggestion）。
    // 本组件不新增 props、不改模板：在顶部统计区（.docs-list-topbar）末尾注入
    // 「建议 + 置信度 + 命中关键词 + 采用建议/忽略」条，复用既有渲染位。
    //   采用建议 → 把建议科目写入手选字段 subject_name（以及题卡展示字段
    //   subject_category 与子科目 subcategory），后续 /confirm 走手选优先；
    //   忽略 → 隐藏建议条并还原采用前的手选原值。
    // 向后兼容：题目不带建议字段（null / 空名）时完全不入 DOM，旧预览零变化。
    const SUGGESTION_UI_ID = 'qpl-suggestion-ui-' + (instance ? instance.uid : '0');

    function sugPct(c) {
      const n = Number(c);
      return Number.isFinite(n) ? Math.round(n * 100) : 0;
    }

    // 从题目对象读出建议（缺省/空名 → null）
    function suggestionOfQuestion(q) {
      if (!q || typeof q !== 'object') return null;
      const ss = q.subject_suggestion;
      const sc = q.subcategory_suggestion;
      const hasSs = !!(ss && ss.name);
      const hasSc = !!(sc && sc.name);
      if (!hasSs && !hasSc) return null;
      return {
        subject: hasSs ? {
          name: String(ss.name),
          confidence: sugPct(ss.confidence),
          keywords: Array.isArray(ss.matched_keywords) ? ss.matched_keywords.slice() : []
        } : null,
        subcategory: hasSc ? {
          name: String(sc.name),
          confidence: sugPct(sc.confidence)
        } : null
      };
    }

    // 批次级建议状态：同一批题目 stamped 相同，取首个未忽略的
    function suggestionState() {
      const list = props.questions || [];
      let sug = null;
      let withSug = 0;
      let ignored = 0;
      let applied = 0;
      for (let i = 0; i < list.length; i++) {
        const s = suggestionOfQuestion(list[i]);
        if (!s) continue;
        withSug++;
        if (!sug) sug = s;
        if (list[i]._sug_ignored) ignored++;
        else if (list[i]._sug_applied) applied++;
      }
      if (!sug || ignored >= withSug) return { visible: false, sug: null };
      return { visible: true, sug: sug, appliedAll: applied >= withSug };
    }

    function removeSuggestionUI() {
      if (typeof document === 'undefined') return;
      const el = document.getElementById(SUGGESTION_UI_ID);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    // 注入/更新建议条（幂等：内容未变不重建，避免丢事件与闪烁）
    function renderSuggestionUI() {
      if (typeof document === 'undefined') return;
      if (isReadonly.value) { removeSuggestionUI(); return; }
      const state = suggestionState();
      if (!state.visible) { removeSuggestionUI(); return; }
      const root = (instance && instance.proxy && instance.proxy.$el) || null;
      if (!root || root.nodeType !== 1) return;
      const topbar = root.querySelector('.docs-list-topbar');
      if (!topbar) return;

      const ss = state.sug.subject;
      const sc = state.sug.subcategory;
      const key = (ss ? ss.name + '|' + ss.confidence : '') +
        (sc ? '|' + sc.name + '|' + sc.confidence : '') +
        (state.appliedAll ? '|applied' : '|open');

      const existing = document.getElementById(SUGGESTION_UI_ID);
      if (existing && existing.parentNode === topbar &&
          existing.getAttribute('data-sug-key') === key) return;
      removeSuggestionUI();

      const wrap = document.createElement('div');
      wrap.id = SUGGESTION_UI_ID;
      wrap.setAttribute('data-sug-key', key);
      wrap.style.cssText =
        'display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;' +
        'font-size:12px;color:#7cc3ff;background:rgba(74,158,255,0.12);' +
        'border:1px solid rgba(74,158,255,0.32);border-radius:9px;padding:4px 10px;';

      let text = '💡 建议科目：' + (ss ? ss.name + '（' + ss.confidence + '%）' : '—');
      if (ss && ss.keywords.length) {
        text += ' · 命中：' + ss.keywords.slice(0, 4).join('、');
      }
      if (sc) text += ' · 建议子科目：' + sc.name + '（' + sc.confidence + '%）';
      const label = document.createElement('span');
      label.textContent = text;
      wrap.appendChild(label);

      if (state.appliedAll) {
        const done = document.createElement('span');
        done.textContent = '✅ 已采用';
        done.style.cssText = 'color:#4ade80;font-weight:600;';
        wrap.appendChild(done);
      } else {
        const applyBtn = document.createElement('button');
        applyBtn.type = 'button';
        applyBtn.textContent = '采用建议';
        applyBtn.style.cssText =
          'padding:3px 12px;border:none;border-radius:6px;cursor:pointer;' +
          'background:linear-gradient(135deg,#c41e3a 0%,#e8384f 100%);' +
          'color:#fff;font-size:12px;font-weight:600;';
        applyBtn.onclick = function () { applySuggestion(); };
        const ignoreBtn = document.createElement('button');
        ignoreBtn.type = 'button';
        ignoreBtn.textContent = '忽略';
        ignoreBtn.style.cssText =
          'padding:3px 12px;border:1px solid rgba(255,255,255,0.25);' +
          'border-radius:6px;cursor:pointer;background:rgba(255,255,255,0.08);' +
          'color:#b0b8c4;font-size:12px;';
        ignoreBtn.onclick = function () { ignoreSuggestion(); };
        wrap.appendChild(applyBtn);
        wrap.appendChild(ignoreBtn);
      }
      topbar.appendChild(wrap);
    }

    // 采用建议：把建议值写入手选字段（/confirm 手选优先），并同步题卡展示字段
    function applySuggestion() {
      if (isReadonly.value) return;
      const state = suggestionState();
      if (!state.sug) return;
      const list = props.questions || [];
      const ss = state.sug.subject;
      const sc = state.sug.subcategory;
      let n = 0;
      for (let i = 0; i < list.length; i++) {
        const q = list[i];
        if (!q || typeof q !== 'object' || q._sug_ignored) continue;
        if (!suggestionOfQuestion(q)) continue;
        if (!q._sug_backup) {
          q._sug_backup = {
            subject_name: q.subject_name,
            subject_category: q.subject_category,
            subcategory: q.subcategory
          };
        }
        if (ss && ss.name) {
          q.subject_name = ss.name;      // /confirm 手选优先读取
          q.subject_category = ss.name;  // 题卡科目徽章同步展示
        }
        if (sc && sc.name) {
          q.subcategory = sc.name;       // /confirm 子科目读取
        }
        q._sug_applied = true;
        n++;
      }
      renderSuggestionUI();
      if (n > 0) {
        alert('已采用建议：' + (ss ? ss.name : '') +
          (sc ? ' / ' + sc.name : '') + '（' + n + ' 题）。确认入库时将按手选值落库。');
      }
    }

    // 忽略建议：还原采用前的手选原值并隐藏建议条
    function ignoreSuggestion() {
      if (isReadonly.value) return;
      const list = props.questions || [];
      for (let i = 0; i < list.length; i++) {
        const q = list[i];
        if (!q || typeof q !== 'object') continue;
        if (q._sug_backup) {
          const bk = q._sug_backup;
          if (bk.subject_name === undefined) delete q.subject_name;
          else q.subject_name = bk.subject_name;
          if (bk.subject_category === undefined) delete q.subject_category;
          else q.subject_category = bk.subject_category;
          if (bk.subcategory === undefined) delete q.subcategory;
          else q.subcategory = bk.subcategory;
          delete q._sug_backup;
        }
        delete q._sug_applied;
        q._sug_ignored = true;
      }
      renderSuggestionUI();
    }

    // 题目变化（重导入 / 编辑 / 采用写值）后，等 Vue 完成本轮 DOM patch 再幂等注入
    watch(
      function () { return props.questions; },
      function () { renderSuggestionUI(); },
      { deep: true }
    );

    onMounted(renderSuggestionUI);

return {
      provider,
      editDialogVisible,
      editIndex,
      editForm,
      attachingKey,
      // 复合题组总题干展示（用户实测缺陷 D1）
      groupHeads,
      expandedGroups,
      isGroupExpanded,
      toggleGroup,
      // F-9b：组头内嵌到题目流（材料与子题同框）
      groupHeadIndex,
      // F-9c：复合题组同框渲染（组内题目卡片视觉整合）
      qnumInMultiGroup,
      isSectionCollapsed,
      toggleSection,
      showSectionHead,
      sectionCount,
      pickImage,
      handlePaste,
      finishAttach,
      openEditDialog,
      closeEditDialog,
      saveEdit,
      // F-7：编辑弹层内图片粘贴（题干/解析）
      handleEditPaste,
      addOption,
      removeOption,
      isJudgeQuestion,
      isShortAnswer,
      renderQuestionContent,
      readonly: isReadonly,
      normalizedContract,
      hasUnifiedContract
    };
  }
});
</script>

<style scoped>
/* ====== 预览列表 ====== */
.docs-question-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}
.docs-q-section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 8px;
  padding: 7px 12px;
  background: rgba(100, 120, 160, 0.14);
  border-left: 3px solid #4a9eff;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  color: #e8eaf0;
}
.docs-q-section-head:hover { background: rgba(100, 120, 160, 0.24); }
.docs-q-section-caret { color: #4a9eff; font-size: 13px; width: 12px; }
.docs-q-section-name { font-weight: 600; }
.docs-q-section-count { color: #98a2b3; font-size: 12px; margin-left: auto; }

.docs-q-kao-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin: 6px 0 2px;
}
.docs-q-kao-label { color: #98a2b3; font-size: 12px; }
.docs-q-kao-tag {
  font-size: 12px;
  line-height: 18px;
  color: #7cc3ff;
  background: rgba(74, 158, 255, 0.14);
  border: 1px solid rgba(74, 158, 255, 0.3);
  border-radius: 9px;
  padding: 0 8px;
  white-space: nowrap;
}

.docs-q-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  overflow: visible;
  transition: border-color 0.3s, box-shadow 0.3s;
}
/* F-9c：复合题组同框——组内题目卡片共享左侧色带，与组头连成同一框架 */
.docs-q-card.docs-q-card-grouped {
  border-left: 4px solid rgba(200,22,30,0.55);
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}
.docs-q-card:hover { border-color: rgba(200,22,30,0.4); box-shadow: 0 2px 16px rgba(200,22,30,0.12); }
/* P0-3: 异常题定位高亮 */
.docs-q-card.qcard-highlight {
  border-color: #e8384f;
  box-shadow: 0 0 0 3px rgba(232,56,79,0.45), 0 4px 20px rgba(232,56,79,0.35);
  transition: box-shadow 0.3s, border-color 0.3s;
}
.docs-q-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(200,22,30,0.1);
  border-bottom: 1px solid rgba(200,22,30,0.18);
  border-radius: 12px 12px 0 0;
}
.docs-q-num {
  font-size: 14px;
  font-weight: 700;
  color: #e8384f;
  min-width: 60px;
}
.docs-q-type {
  font-size: 12px;
  color: #8899aa;
  flex: 1;
  background: rgba(200,22,30,0.08);
  padding: 2px 10px;
  border-radius: 10px;
}
.docs-q-subject {
  font-size: 11px;
  color: #8899aa;
  background: rgba(26,43,95,0.3);
  padding: 2px 8px;
  border-radius: 8px;
}
.btn-mini-import {
  padding: 6px 16px;
  background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
  border: none;
  border-radius: 6px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}
.btn-mini-import:hover {
  box-shadow: 0 2px 10px rgba(200,22,30,0.4);
  transform: translateY(-1px);
}
.btn-mini-import:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  background: rgba(255,255,255,0.1);
  color: #556677;
}
.docs-q-body {
  padding: 16px 18px;
}
.docs-q-content {
  font-size: 14px;
  color: #e8ecf4;
  line-height: 1.8;
  margin-bottom: 12px;
  word-break: break-word;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  background: rgba(0,0,0,0.15);
  padding: 12px 14px;
  border-radius: 8px;
  border-left: 3px solid rgba(200,22,30,0.3);
}
.docs-q-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin-bottom: 10px;
  padding: 10px 14px;
  background: rgba(0,0,0,0.1);
  border-radius: 8px;
}
.docs-q-opt {
  font-size: 13px;
  color: #b0b8c4;
  line-height: 1.6;
  max-width: 45%;
  word-break: break-word;
}
.docs-q-answer-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.docs-q-ans-label {
  color: #8899aa;
  font-size: 13px;
  font-weight: 600;
}
.docs-q-answer {
  font-size: 13px;
  color: #4ade80;
  margin-top: 4px;
}
.docs-q-ans-input {
  width: 72px;
  padding: 6px 10px;
  background: rgba(26,43,95,0.4);
  border: 1px solid rgba(200,22,30,0.3);
  border-radius: 6px;
  color: #4ade80;
  font-size: 14px;
  font-weight: 700;
  text-align: center;
  text-transform: uppercase;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.docs-q-ans-input:focus {
  border-color: #c41e3a;
  box-shadow: 0 0 0 3px rgba(200,22,30,0.2);
  background: rgba(26,43,95,0.6);
}
.docs-q-ans-input::placeholder {
  color: #556677;
  font-weight: 400;
  font-size: 12px;
}
.docs-q-ans-hint {
  color: #e8384f;
  font-size: 12px;
}
/* ====== 预览列表顶部工具栏 ====== */
.docs-list-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(26,43,95,0.5), rgba(20,30,55,0.4));
  border: 1px solid rgba(200,22,30,0.15);
  border-radius: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
}
.docs-list-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.docs-stat-total {
  font-size: 13px;
  font-weight: 700;
  color: #e8ecf4;
  background: rgba(200,22,30,0.15);
  padding: 4px 12px;
  border-radius: 6px;
}
.docs-stat-answered {
  font-size: 12px;
  color: #4ade80;
  background: rgba(74,222,128,0.1);
  padding: 4px 10px;
  border-radius: 6px;
}
.docs-stat-missing {
  font-size: 12px;
  color: #f59e0b;
  background: rgba(245,158,11,0.1);
  padding: 4px 10px;
  border-radius: 6px;
}
.docs-stat-imported {
  font-size: 12px;
  color: #8899aa;
  background: rgba(255,255,255,0.05);
  padding: 4px 10px;
  border-radius: 6px;
}
.docs-list-actions-top {
  display: flex;
  gap: 8px;
}
.btn-top-import {
  padding: 8px 20px;
  font-size: 13px;
}
.btn-top-close {
  padding: 8px 16px;
  font-size: 13px;
}
/* ====== 无答案卡片高亮 ====== */
.docs-q-card-noans {
  border-color: rgba(245, 158, 11, 0.3);
}
.docs-q-card-noans .docs-q-header {
  background: rgba(245, 158, 11, 0.08);
  border-bottom-color: rgba(245, 158, 11, 0.18);
}
.docs-q-ans-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.docs-q-ans-badge-warn {
  animation: pulse-warn 2s ease-in-out infinite;
}
@keyframes pulse-warn {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.docs-q-answer-row-warn {
  background: rgba(245, 158, 11, 0.05);
  border-radius: 6px;
}
/* ====== 重检按钮 ====== */
.btn-mini-reverify {
  padding: 3px 10px;
  background: rgba(255, 165, 0, 0.15);
  border: 1px solid rgba(255, 165, 0, 0.4);
  border-radius: 6px;
  color: #ffa500;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}
.btn-mini-reverify:hover {
  background: rgba(255, 165, 0, 0.3);
  box-shadow: 0 2px 10px rgba(255, 165, 0, 0.3);
}
/* ====== 解析展示 ====== */
.docs-q-analysis {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(255,255,255,0.1);
}
.docs-q-analysis-text {
  font-size: 13px;
  color: #a0aab4;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(0,0,0,0.15);
  padding: 8px 12px;
  border-radius: 6px;
  margin-top: 4px;
}

/* ====== 编辑对话框 ====== */
.edit-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.edit-dialog {
  background: #1a2332;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.edit-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.edit-dialog-header h3 {
  margin: 0;
  font-size: 18px;
  color: #e8ecf4;
}
.edit-dialog-close {
  background: none;
  border: none;
  color: #8899aa;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}
.edit-dialog-close:hover {
  color: #fff;
}
.edit-dialog-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}
.edit-field {
  margin-bottom: 16px;
}
.edit-field label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #8899aa;
}
.edit-field textarea,
.edit-field input,
.edit-field select {
  width: 100%;
  padding: 8px 12px;
  background: rgba(26, 43, 95, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #e8ecf4;
  font-size: 14px;
  box-sizing: border-box;
}
.edit-field textarea:focus,
.edit-field input:focus,
.edit-field select:focus {
  outline: none;
  border-color: rgba(200, 22, 30, 0.5);
}
.edit-field textarea {
  resize: vertical;
  min-height: 80px;
}
.edit-options-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.edit-option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.edit-option-key {
  font-weight: 700;
  color: #e8ecf4;
  min-width: 24px;
}
.edit-option-item input {
  flex: 1;
}
.edit-option-delete {
  background: rgba(245, 108, 108, 0.2);
  border: none;
  color: #f56c6c;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
.edit-option-delete:hover {
  background: rgba(245, 108, 108, 0.4);
}
.edit-option-add {
  background: rgba(74, 222, 128, 0.2);
  border: none;
  color: #4ade80;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  margin-top: 4px;
}
.edit-option-add:hover {
  background: rgba(74, 222, 128, 0.3);
}
.edit-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.btn-primary {
  padding: 8px 20px;
  background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
  border: none;
  border-radius: 6px;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-primary:hover {
  box-shadow: 0 2px 10px rgba(200, 22, 30, 0.4);
}
.btn-secondary {
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #b0b8c4;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.15);
}

/* ====== 缺失信息提示 ====== */
.field-missing {
  border: 2px solid #f56c6c;
  border-radius: 6px;
  padding: 8px;
  background: rgba(245, 108, 108, 0.05);
}
.field-warning {
  border: 2px solid #e6a23c;
  border-radius: 6px;
  padding: 8px;
  background: rgba(230, 162, 60, 0.05);
}
.required {
  color: #f56c6c;
  font-weight: bold;
}
.field-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: block;
}
.btn-mini-edit {
  padding: 6px 12px;
  background: rgba(64, 158, 255, 0.2);
  border: none;
  border-radius: 4px;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-mini-edit:hover {
  background: rgba(64, 158, 255, 0.3);
}
.btn-mini-delete {
  padding: 6px 12px;
  background: rgba(245, 108, 108, 0.18);
  border: none;
  border-radius: 4px;
  color: #f56c6c;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-mini-delete:hover {
  background: rgba(245, 108, 108, 0.32);
}
.btn-mini-delete:disabled {
  background: rgba(144, 147, 153, 0.15);
  color: #909399;
  cursor: not-allowed;
}

/* ===== 2026-09-29 新增：串题标记 + 题卡贴图 ===== */
.docs-q-suspicious-badge {
  display: inline-block;
  margin-right: 6px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(230, 162, 60, 0.18);
  color: #e6a23c;
  font-size: 13px;
  cursor: help;
}
.docs-q-card-suspicious {
  border-color: rgba(230, 162, 60, 0.55);
  box-shadow: 0 0 0 1px rgba(230, 162, 60, 0.25);
}
.docs-q-card-suspicious .docs-q-header {
  background: rgba(230, 162, 60, 0.08);
}
.btn-mini-img {
  padding: 6px 12px;
  background: rgba(64, 158, 255, 0.2);
  border: none;
  border-radius: 4px;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-mini-img:hover {
  background: rgba(64, 158, 255, 0.34);
}
.btn-mini-img:disabled {
  background: rgba(144, 147, 153, 0.15);
  color: #909399;
  cursor: not-allowed;
}
/* 选项内的「+图」为小尺寸按钮，与题干区的「+题干图」区分 */
.docs-q-opt .btn-mini-img {
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  vertical-align: middle;
}
/* 选项文字改用 v-html 渲染以支持图片，需保持原有排版 */
.docs-q-opt-text {
  white-space: normal;
}
.docs-q-opt-val {
  white-space: normal;
}
.docs-q-opt-val :deep(img) {
  max-width: 100%;
  height: auto;
}
/* ===== 复合题组总题干（用户实测缺陷 D1）=====
   给定资料是所有小题共享的上下文，必须在组内首题上方完整呈现一次，
   否则用户看到的是一堆孤立小题，无从判断它们在问什么。 */
.docs-q-group-head {
  margin-bottom: 10px;
  padding: 10px 12px;
  border: 1px solid #3a4a5e;
  border-left: 3px solid #58a6ff;
  border-radius: 4px;
  background: rgba(88, 166, 255, 0.06);
}
.docs-q-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.docs-q-group-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 700;
  color: #58a6ff;
  background: rgba(88, 166, 255, 0.16);
}
.docs-q-group-meta {
  font-size: 12px;
  color: #8b949e;
}
/* 材料正文：必须保留换行（材料段落是分行排版的），用 pre-wrap 而非普通文本 */
.docs-q-material {
  margin-top: 8px;
}
.docs-q-material-titles {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.docs-q-mt {
  padding: 1px 6px;
  font-size: 11px;
  color: #7ee787;
  background: rgba(63, 185, 80, 0.12);
  border-radius: 2px;
}
.docs-q-material-text {
  max-height: 320px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
  color: #c9d1d9;
  white-space: pre-wrap;
  word-break: break-word;
}
.btn-mini-toggle,
.btn-mini-expand {
  padding: 2px 8px;
  font-size: 12px;
  color: #58a6ff;
  background: transparent;
  border: 1px solid #3a4a5e;
  border-radius: 3px;
  cursor: pointer;
}
.btn-mini-toggle:hover,
.btn-mini-expand:hover {
  background: rgba(88, 166, 255, 0.12);
}
</style>
