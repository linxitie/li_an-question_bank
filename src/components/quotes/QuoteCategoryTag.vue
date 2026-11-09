<template>
  <span
    v-if="category"
    :class="['quote-category', categoryClass]"
    role="link"
    tabindex="0"
    title="浏览金句库"
    @click="openBrowser"
    @keydown.enter="openBrowser">
    {{ category }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

const props = defineProps<{ category?: string }>();
const router = useRouter();

function openBrowser(): void {
  router.push('/quotes');
}

const categoryClass = computed(() => {
  const value = (props.category || '').toLowerCase();
  if (value.includes('法治') || value.includes('法律')) return 'is-law';
  if (value.includes('政治') || value.includes('党建')) return 'is-politics';
  if (value.includes('公安') || value.includes('警察')) return 'is-police';
  if (value.includes('民生') || value.includes('民心')) return 'is-livelihood';
  return 'is-default';
});
</script>

<style scoped>
.quote-category {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
}

.is-law {
  background: #eef6ee;
  color: #3d724e;
}

.is-politics {
  background: #fff1ea;
  color: #a45f38;
}

.is-police {
  background: #eef3ff;
  color: #4b659c;
}

.is-livelihood {
  background: #f5f0e5;
  color: #8a6a32;
}

.is-default {
  background: #f0f2f1;
  color: #65706a;
}
</style>
