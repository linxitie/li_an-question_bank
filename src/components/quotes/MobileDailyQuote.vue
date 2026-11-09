<template>
  <section class="mobile-quote-card">
    <div class="mobile-quote-card__head">
      <div>
        <span class="eyebrow">每日金句</span>
        <QuoteCategoryTag :category="category" />
      </div>
      <button
        type="button"
        class="refresh-btn"
        :disabled="loading"
        @click="refresh">
        {{ loading ? '加载中…' : '换一句' }}
      </button>
    </div>
    <blockquote>{{ quote }}</blockquote>
    <p class="attribution">{{ attribution }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import QuoteCategoryTag from '@/components/quotes/QuoteCategoryTag.vue';

const quote = ref('正在加载今日金句...');
const author = ref('');
const source = ref('');
const category = ref('');
const loading = ref(false);

const attribution = computed(() => {
  const a = author.value.trim();
  const s = source.value.trim();
  if (a && s) return `${a} · ${s}`;
  return a || s || '暂无出处';
});

async function loadDaily(): Promise<void> {
  try {
    const response = await fetch('/api/quotes/quote/daily');
    if (!response.ok) throw new Error('获取金句失败');
    const data = await response.json();
    quote.value = data.content || '暂无金句';
    author.value = data.author || '';
    source.value = data.source || '';
    category.value = data.category || '';
  } catch {
    quote.value = '暂无金句';
  }
}

async function refresh(): Promise<void> {
  if (loading.value) return;
  loading.value = true;
  try {
    const response = await fetch(
      `/api/quotes/random?exclude=${encodeURIComponent(quote.value)}`
    );
    if (!response.ok) throw new Error('获取金句失败');
    const data = await response.json();
    quote.value = data.content || quote.value;
    author.value = data.author || '';
    source.value = data.source || '';
    category.value = data.category || '';
  } catch {
    // 保留当前金句
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadDaily();
});
</script>

<style scoped>
.mobile-quote-card {
  margin: 14px 16px 0;
  padding: 18px;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  background: linear-gradient(145deg, #ffffff 0%, #fbfcff 100%);
  box-shadow: 0 4px 16px rgba(16, 42, 71, 0.06);
}

.mobile-quote-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.eyebrow {
  display: inline-block;
  margin-right: 6px;
  color: #2f5d50;
  font-size: 12px;
  font-weight: 700;
}

.refresh-btn {
  flex: 0 0 auto;
  padding: 4px 8px;
  border: 1px solid #e3ded4;
  border-radius: 999px;
  background: #fff;
  color: #8a928b;
  font-size: 11px;
}

.mobile-quote-card blockquote {
  margin: 16px 0 12px;
  color: #1f2d3d;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.75;
}

.attribution {
  margin: 0;
  color: #9aa3ad;
  font-size: 12px;
  text-align: right;
}
</style>
