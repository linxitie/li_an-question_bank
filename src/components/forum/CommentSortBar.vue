<template>
  <div class="comment-sort-bar">
    <button
      v-for="option in SORTS"
      :key="option.key"
      type="button"
      :class="['csb-btn', { active: sortBy === option.key }]"
      @click="emit('update:sortBy', option.key)"
    >
      {{ option.name }}
    </button>
    <button type="button" class="csb-btn order" @click="toggleOrder">
      {{ order === 'desc' ? '最新在前' : '最早在前' }}
    </button>
  </div>
</template>

<script setup lang="ts">
const SORTS = [
  { key: 'time', name: '时间' },
  { key: 'likes', name: '点赞' },
  { key: 'replies', name: '回复' }
] as const;

const props = withDefaults(
  defineProps<{
    sortBy?: 'time' | 'likes' | 'replies';
    order?: 'asc' | 'desc';
  }>(),
  { sortBy: 'time', order: 'desc' }
);

const emit = defineEmits<{
  (event: 'update:sortBy', value: 'time' | 'likes' | 'replies'): void;
  (event: 'update:order', value: 'asc' | 'desc'): void;
}>();

const toggleOrder = () => {
  emit('update:order', props.order === 'desc' ? 'asc' : 'desc');
};
</script>

<style scoped>
.comment-sort-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.csb-btn {
  border: 1px solid #e0e6f0;
  background: #fff;
  color: #5a6488;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.csb-btn.active {
  background: #1a365d;
  border-color: #1a365d;
  color: #fff;
}
.csb-btn.order {
  margin-left: auto;
  border-style: dashed;
}
</style>
