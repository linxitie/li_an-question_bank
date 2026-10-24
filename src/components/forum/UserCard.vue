<template>
  <Teleport to="body">
    <div v-if="visible" class="uc-overlay" @click.self="emit('close')">
      <div class="uc-card">
        <button type="button" class="uc-close" title="关闭" @click="emit('close')">×</button>
        <UserBadge
          :src="src"
          :name="name"
          :user-id="userId"
          :user-type="userType"
          :level="level"
          :frame="frame"
          :badges="badges"
          size="lg"
        />
        <p v-if="signature" class="uc-signature">{{ signature }}</p>
        <div class="uc-stats">
          <span><b>{{ postCount ?? 0 }}</b> 发帖</span>
          <span><b>{{ likeReceived ?? 0 }}</b> 获赞</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import UserBadge from './UserBadge.vue';

withDefaults(
  defineProps<{
    visible: boolean;
    src?: string;
    name?: string;
    userId?: number | string | null;
    userType?: string;
    level?: number | null;
    frame?: string | null;
    badges?: string[];
    signature?: string;
    postCount?: number;
    likeReceived?: number;
  }>(),
  { visible: false, badges: () => [] }
);

const emit = defineEmits<{ (event: 'close'): void }>();
</script>

<style scoped>
.uc-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: rgba(8, 12, 24, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.uc-card {
  position: relative;
  width: min(340px, 92vw);
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
}
.uc-close {
  position: absolute;
  top: 10px;
  right: 12px;
  border: none;
  background: none;
  font-size: 22px;
  color: #8a94ad;
  cursor: pointer;
}
.uc-signature {
  margin: 14px 0 0;
  color: #5a6488;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.uc-stats {
  display: flex;
  gap: 18px;
  margin-top: 16px;
  color: #6b7896;
  font-size: 12px;
}
.uc-stats b {
  color: #1a2b5f;
  font-size: 15px;
  margin-right: 2px;
}
</style>
