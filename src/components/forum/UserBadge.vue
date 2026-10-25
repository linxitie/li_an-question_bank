<template>
  <component
    :is="clickable ? 'button' : 'span'"
    class="user-badge"
    :class="[`size-${size}`, { clickable }]"
    :type="clickable ? 'button' : undefined"
    @click="clickable && emit('click')"
  >
    <span class="ub-avatar" :class="frameClass" :style="{ background: gradient }">
      <img v-if="src && !failed" :src="src" :alt="name || '头像'" @error="failed = true" />
      <span v-else class="ub-initial">{{ initial }}</span>
    </span>
    <span v-if="!avatarOnly" class="ub-main">
      <span class="ub-name">{{ name || '匿名' }}</span>
      <span v-if="badges.length || level" class="ub-meta">
        <span v-for="badge in shownBadges" :key="badge" class="ub-chip">{{ badge }}</span>
        <span v-if="level" class="ub-level">Lv.{{ level }}</span>
      </span>
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import { avatarInitial } from '@/modules/community/avatar';

const props = withDefaults(
  defineProps<{
    src?: string;
    name?: string;
    userId?: number | string | null;
    userType?: string;
    level?: number | null;
    frame?: string | null;
    badges?: string[];
    size?: 'sm' | 'md' | 'lg';
    clickable?: boolean;
    avatarOnly?: boolean;
  }>(),
  { size: 'md', clickable: false, avatarOnly: false, badges: () => [] }
);

const emit = defineEmits<{ (event: 'click'): void }>();

const failed = ref(false);
const initial = computed(() => avatarInitial(props.name));

const PALETTES = [
  ['#1A365D', '#2a5298'],
  ['#10b981', '#059669'],
  ['#f59e0b', '#d97706'],
  ['#8b5cf6', '#7c3aed'],
  ['#ef4444', '#b91c1c'],
  ['#0ea5e9', '#0369a1']
];

const gradient = computed(() => {
  const seed = `${props.userId ?? ''}${props.name ?? ''}`;
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  const [from, to] = PALETTES[hash % PALETTES.length];
  return `linear-gradient(135deg, ${from} 0%, ${to} 100%)`;
});

const frameClass = computed(() => (props.frame ? `frame-${props.frame}` : ''));

const shownBadges = computed(() => {
  const base = [...props.badges];
  if (props.userType === 'teacher' && !base.includes('教师')) base.push('教师');
  if (props.userType === 'admin' && !base.includes('管理员')) base.push('管理员');
  return base.slice(0, 2);
});
</script>

<style scoped>
.user-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  padding: 0;
  text-align: left;
  color: inherit;
  font: inherit;
}
.user-badge.clickable {
  cursor: pointer;
}
.ub-avatar {
  position: relative;
  border-radius: 50%;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px #fff, 0 0 0 4px rgba(26, 54, 93, 0.08);
}
.size-sm .ub-avatar {
  width: 28px;
  height: 28px;
}
.size-md .ub-avatar {
  width: 38px;
  height: 38px;
}
.size-lg .ub-avatar {
  width: 64px;
  height: 64px;
}
.ub-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ub-initial {
  color: #fff;
  font-weight: 600;
  font-size: 13px;
}
.size-lg .ub-initial {
  font-size: 20px;
}
.frame-gold {
  box-shadow: 0 0 0 2px #f6d365, 0 0 0 4px rgba(246, 211, 101, 0.35);
}
.frame-blue {
  box-shadow: 0 0 0 2px #60a5fa, 0 0 0 4px rgba(96, 165, 250, 0.3);
}
.ub-main {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ub-name {
  font-size: 13px;
  color: #1a2b5f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ub-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.ub-chip {
  font-size: 10px;
  line-height: 1;
  padding: 2px 5px;
  border-radius: 4px;
  background: #eef3fb;
  color: #3b5b8c;
}
.ub-level {
  font-size: 10px;
  color: #b8860b;
}
</style>
