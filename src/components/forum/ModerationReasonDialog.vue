<template>
  <Teleport to="body">
    <div v-if="visible" class="mrd-overlay" @click.self="close">
      <div class="mrd-card">
        <h3 class="mrd-title">{{ title }}</h3>
        <p class="mrd-hint">{{ hint }}</p>
        <textarea
          v-model="reason"
          class="mrd-textarea"
          rows="4"
          maxlength="200"
          placeholder="请填写原因（1-200 字）"
        ></textarea>
        <p v-if="error" class="mrd-error">{{ error }}</p>
        <div class="mrd-actions">
          <button class="mrd-cancel" @click="close">取消</button>
          <button class="mrd-confirm" :disabled="submitting" @click="submit">
            {{ submitting ? '提交中…' : '确认' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title?: string;
    hint?: string;
    submitting?: boolean;
  }>(),
  { title: '填写原因', hint: '', submitting: false }
);

const emit = defineEmits<{
  (event: 'confirm', reason: string): void;
  (event: 'close'): void;
}>();

const reason = ref('');
const error = ref('');

watch(
  () => props.visible,
  (value) => {
    if (value) {
      reason.value = '';
      error.value = '';
    }
  }
);

const close = () => emit('close');

const submit = () => {
  const value = reason.value.trim();
  if (!value) {
    error.value = '原因不能为空';
    return;
  }
  if (value.length > 200) {
    error.value = '原因不能超过 200 字';
    return;
  }
  emit('confirm', value);
};
</script>

<style scoped>
.mrd-overlay {
  position: fixed;
  inset: 0;
  z-index: 9500;
  background: rgba(8, 12, 24, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.mrd-card {
  width: min(420px, 94vw);
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.24);
}
.mrd-title {
  margin: 0 0 4px;
  font-size: 17px;
  color: #1a2b5f;
}
.mrd-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #6b7896;
}
.mrd-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d9e1ee;
  border-radius: 8px;
  padding: 9px 10px;
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
}
.mrd-error {
  margin: 6px 0 0;
  color: #c41e3a;
  font-size: 12px;
}
.mrd-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.mrd-cancel,
.mrd-confirm {
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
}
.mrd-cancel {
  background: #f2f5fa;
  color: #3b4a6b;
}
.mrd-confirm {
  background: #c41e3a;
  color: #fff;
}
.mrd-confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
