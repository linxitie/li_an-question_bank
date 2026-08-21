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
          缺答案 {{ questions.filter(function(q){return !q.answer || q.answer === '待补充'}).length }}
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
    <div class="docs-q-card" v-for="(q, idx) in questions" :key="idx" :class="{ 'docs-q-card-noans': !q.answer || q.answer === '待补充' }">
      <div class="docs-q-header">
        <span class="docs-q-num">第 {{ idx + 1 }} 题</span>
        <span class="docs-q-type">{{ q.question_type_detail || '单选题' }}</span>
        <span class="docs-q-subject">{{ q.subject_category || '公专' }}</span>
        <span class="docs-q-dup-badge" v-if="q._is_duplicate" style="color:#f56c6c;font-size:15px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'该题目已存在（相似度 ' + Math.round((q._similarity || 0) * 100) + '%），将自动跳过导入'">⚠ 该题目已存在</span>
        <span class="docs-q-ans-badge" v-if="q.answer && q.answer !== '待补充'" style="color:#4ade80;font-size:15px;margin-right:8px;" title="已匹配答案">已匹配答案 ✓</span>
        <span class="docs-q-ans-badge docs-q-ans-badge-warn" v-else style="color:#f59e0b;font-size:15px;margin-right:8px;" title="缺少答案，请在下方手动录入">⚠ 缺答案</span>
        <span class="docs-q-conf-badge" v-if="q.confidence !== undefined && q.confidence < 0.5" style="color:#f56c6c;font-size:13px;margin-right:6px;background:rgba(245,108,108,0.15);padding:2px 6px;border-radius:4px;" :title="'匹配置信度仅 ' + Math.round((q.confidence||0)*100) + '%，建议人工核对'">🔴 低置信度({{ Math.round((q.confidence||0)*100) }}%)</span>
        <button class="btn-mini-reverify" @click="$emit('reverify', idx)" title="重新校验选项分割">重检</button>
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
  </div>
</template>

<script>
// @ts-nocheck
import { defineComponent } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'QuestionPreviewList',
  props: {
    questions: { type: Array, default: function() { return []; } },
    mode: { type: String, default: 'combined' },
    loading: { type: Boolean, default: false }
  },
  emits: ['import-one', 'import-all', 'reverify', 'close'],
  setup() {
    const provider = useProvider({ id: 'question_preview_list', version: '1785406000000' });
    return { provider };
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
</style>
