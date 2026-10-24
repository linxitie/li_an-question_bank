<template>
  <Teleport to="body">
    <div v-if="visible" class="fd-overlay" @click.self="close">
      <div class="fd-card">
        <button type="button" class="fd-close" @click="close">×</button>
        <h3 class="fd-title">题目报错 / 反馈</h3>
        <p v-if="questionId" class="fd-context">关联题目 #{{ questionId }}</p>

        <div v-if="ticketNo" class="fd-success">
          <p>已提交，工单号：<b>{{ ticketNo }}</b></p>
          <p class="fd-hint">可在「我的 - 意见反馈」中查看处理进度。</p>
          <button type="button" class="fd-submit" @click="close">关闭</button>
        </div>

        <template v-else>
          <label class="fd-label">问题类型</label>
          <select v-model="type" class="fd-input">
            <option value="answer">答案错误</option>
            <option value="analysis">解析错误</option>
            <option value="question_content">题目内容错误</option>
            <option value="function">功能异常</option>
            <option value="other">其他</option>
          </select>

          <label class="fd-label">问题描述</label>
          <textarea
            v-model="content"
            class="fd-textarea"
            rows="4"
            maxlength="500"
            placeholder="请描述你遇到的问题，便于我们快速定位"
          ></textarea>

          <label class="fd-label">截图（最多 5 张）</label>
          <ImageUploader v-model="images" :max="5" />

          <p v-if="error" class="fd-error">{{ error }}</p>
          <button
            type="button"
            class="fd-submit"
            :disabled="submitting || !content.trim()"
            @click="submit"
          >
            {{ submitting ? '提交中…' : '提交反馈' }}
          </button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import { apiClient } from '@/services/api/client';
import ImageUploader from './ImageUploader.vue';
import type { ForumImageAttachment } from './imageUtils';

const props = withDefaults(
  defineProps<{
    visible: boolean;
    questionId?: number | null;
    practiceRecordId?: number | null;
    source?: string;
  }>(),
  { questionId: null, practiceRecordId: null, source: 'practice' }
);

const emit = defineEmits<{ (event: 'close'): void }>();

const type = ref('answer');
const content = ref('');
const images = ref<ForumImageAttachment[]>([]);
const submitting = ref(false);
const error = ref('');
const ticketNo = ref('');

const close = () => {
  emit('close');
};

const submit = async () => {
  if (!content.value.trim() || submitting.value) return;
  error.value = '';
  submitting.value = true;
  try {
    const categoryMap: Record<string, string> = {
      answer: '数据错误',
      analysis: '数据错误',
      question_content: '数据错误',
      function: '功能异常',
      other: '其他'
    };
    const response = await apiClient.request({
      url: '/api/feedback',
      method: 'POST',
      baseURL: '',
      data: {
        category: categoryMap[type.value] || '其他',
        feedback_type: type.value,
        content: content.value.trim(),
        question_id: props.questionId,
        practice_record_id: props.practiceRecordId,
        source: props.source,
        attachments: images.value.length ? images.value : undefined
      }
    });
    ticketNo.value = response.data?.ticket_no || '';
    content.value = '';
    images.value = [];
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '提交失败';
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.fd-overlay {
  position: fixed;
  inset: 0;
  z-index: 9100;
  background: rgba(8, 12, 24, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.fd-card {
  position: relative;
  width: min(460px, 94vw);
  max-height: 90vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 16px;
  padding: 22px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.24);
}
.fd-close {
  position: absolute;
  top: 10px;
  right: 12px;
  border: none;
  background: none;
  font-size: 22px;
  color: #8a94ad;
  cursor: pointer;
}
.fd-title {
  margin: 0 0 4px;
  font-size: 17px;
  color: #1a2b5f;
}
.fd-context {
  margin: 0 0 14px;
  font-size: 12px;
  color: #6b7896;
}
.fd-label {
  display: block;
  margin: 12px 0 6px;
  font-size: 13px;
  color: #3b4a6b;
}
.fd-input,
.fd-textarea {
  width: 100%;
  border: 1px solid #d9e1ee;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
  box-sizing: border-box;
  font-family: inherit;
}
.fd-textarea {
  resize: vertical;
}
.fd-submit {
  width: 100%;
  margin-top: 16px;
  border: none;
  border-radius: 10px;
  background: #c41e3a;
  color: #fff;
  padding: 11px;
  font-size: 14px;
  cursor: pointer;
}
.fd-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.fd-error {
  margin: 8px 0 0;
  color: #c41e3a;
  font-size: 12px;
}
.fd-success {
  padding: 12px 0 4px;
  color: #1a2b5f;
  font-size: 14px;
}
.fd-hint {
  color: #6b7896;
  font-size: 12px;
}
</style>
