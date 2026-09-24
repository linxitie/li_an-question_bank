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
    <div class="docs-q-card" v-for="(q, idx) in questions" :key="idx" :id="'qcard_' + idx" :class="{ 'docs-q-card-noans': !q.answer || q.answer === '待补充' }">
      <div class="docs-q-header">
        <span class="docs-q-num">第 {{ idx + 1 }} 题</span>
        <span class="docs-q-type">{{ q.question_type_detail || '单选题' }}</span>
        <span class="docs-q-subject">{{ q.subject_category || '公专' }}</span>
        <span class="docs-q-dup-badge" v-if="q._is_duplicate" style="color:#f56c6c;font-size:15px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'该题目已存在（相似度 ' + Math.round((q._similarity || 0) * 100) + '%），将自动跳过导入'">⚠ 该题目已存在</span>
        <span class="docs-q-ans-badge" v-if="q.answer && q.answer !== '待补充'" style="color:#4ade80;font-size:15px;margin-right:8px;" title="已匹配答案">已匹配答案 ✓</span>
        <span class="docs-q-ans-badge docs-q-ans-badge-warn" v-else style="color:#f59e0b;font-size:15px;margin-right:8px;" title="缺少答案，请在下方手动录入">⚠ 缺答案</span>
        <span class="docs-q-conf-badge" v-if="q.confidence !== undefined && q.confidence < 0.5" style="color:#f56c6c;font-size:13px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'匹配置信度仅 ' + Math.round((q.confidence||0)*100) + '%，建议人工核对'">🔴 低置信度({{ Math.round((q.confidence||0)*100) }}%)</span>
        <button class="btn-mini-reverify" @click="$emit('reverify', idx)" title="重新校验选项分割">重检</button>
        <button class="btn-mini-edit" @click="openEditDialog(idx)" title="编辑题目">编辑</button>
        <button class="btn-mini-import" @click="$emit('import-one', idx)" :disabled="q._imported">
          {{ q._imported ? '已导入' : '导入此题' }}
        </button>
      </div>
      <div class="docs-q-body">
        <div class="docs-q-content">{{ q.question_content }}</div>
        <div class="docs-q-options" v-if="q.options && q.options.length">
          <span class="docs-q-opt" v-for="opt in q.options" :key="opt.key">{{ opt.key }}. {{ opt.value }}</span>
        </div>
        <div class="docs-q-answer-row" :class="{ 'docs-q-answer-row-warn': !q.answer || q.answer === '待补充' }">
          <span class="docs-q-ans-label">答案：</span>
          <input class="docs-q-ans-input" v-model="q.answer" placeholder="A/B/C/D" maxlength="4" />
          <span class="docs-q-ans-hint" v-if="!q.answer || q.answer === '待补充'">（必填 — 请输入选项字母）</span>
        </div>
        <div class="docs-q-answer-row" v-if="!q.answer || q.answer === '待补充'" style="border-top:none;padding-top:4px;margin-top:0;">
          <span class="docs-q-ans-label" style="font-size:15px;color:#8899aa;">解析：</span>
          <input v-model="q.analysis" placeholder="可选，补充答案解析" style="flex:1;padding:5px 10px;background:rgba(26,43,95,0.3);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:#b0b8c4;font-size:15px;outline:none;" />
        </div>
        <div class="docs-q-analysis" v-if="q.analysis && (q.answer && q.answer !== '待补充')">
          <div class="docs-q-ans-label" style="margin-bottom:4px;">解析：</div>
          <div class="docs-q-analysis-text">{{ q.analysis }}</div>
        </div>
      </div>
    </div>
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
            <textarea v-model="editForm.question_content" rows="4" placeholder="请输入题干内容"></textarea>
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
            <textarea v-model="editForm.analysis" rows="3" placeholder="请输入答案解析（可选）"></textarea>
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
import { defineComponent, ref, reactive } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'QuestionPreviewList',
  props: {
    questions: { type: Array, default: function() { return []; } },
    mode: { type: String, default: 'combined' },
    loading: { type: Boolean, default: false }
  },
  emits: ['import-one', 'import-all', 'reverify', 'close', 'edit-question'],
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

    // 打开编辑对话框
    function openEditDialog(idx) {
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
    function saveEdit() {
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
      emit('edit-question', {
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

    return {
      provider,
      editDialogVisible,
      editIndex,
      editForm,
      openEditDialog,
      closeEditDialog,
      saveEdit,
      addOption,
      removeOption
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
.docs-q-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  overflow: visible;
  transition: border-color 0.3s, box-shadow 0.3s;
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
</style>
