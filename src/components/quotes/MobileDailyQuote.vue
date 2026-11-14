<template>
  <section class="mobile-quote-card">
    <div class="mobile-quote-card__head">
      <div class="quote-heading">
        <span class="eyebrow">每日金句</span>
        <QuoteCategoryTag :category="category" />
      </div>
      <div class="quote-actions">
        <router-link :to="libraryPath" class="library-link">金句库</router-link>
        <button
          type="button"
          class="favorite-btn"
          :class="{ active: favorited }"
          :aria-label="favorited ? '取消收藏' : '收藏金句'"
          @click="toggleFavorite">
          {{ favorited ? '★' : '☆' }}
        </button>
        <button
          type="button"
          class="refresh-btn"
          :disabled="loading"
          @click="refresh">
          {{ loading ? '…' : '换一句' }}
        </button>
      </div>
    </div>
    <blockquote>{{ quote }}</blockquote>
    <p class="attribution">{{ attribution }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import QuoteCategoryTag from '@/components/quotes/QuoteCategoryTag.vue';
import { quoteAttribution as formatAttribution } from '@/utils/quote';

const route = useRoute();
const libraryPath = computed(() =>
  route.path.startsWith('/tablet') ? '/tablet/quotes' : '/mobile/quotes'
);

const quote = ref('正在加载今日金句...');
const author = ref('');
const source = ref('');
const category = ref('');
const quoteId = ref(0);
const obsidianSource = ref('');
const favorited = ref(false);
const loading = ref(false);

const attribution = computed(() =>
  formatAttribution(author.value, source.value)
);

function authHeaders(): Record<string, string> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && auth.isLoggedIn && auth.isLoggedIn()) {
    return auth.getJsonHeaders ? auth.getJsonHeaders() : {};
  }
  return {};
}

function applyQuote(data: any): void {
  quote.value = data.content || '暂无金句';
  author.value = data.author || '';
  source.value = data.source || '';
  category.value = data.category || '';
  quoteId.value = data.quote_id || 0;
  obsidianSource.value = data.obsidian_source || '';
  favorited.value = !!data.favorited;
}

async function loadDaily(): Promise<void> {
  try {
    const response = await fetch('/api/quotes/quote/daily', {
      headers: authHeaders()
    });
    if (!response.ok) throw new Error('获取金句失败');
    applyQuote(await response.json());
  } catch {
    quote.value = '暂无金句';
  }
}

async function refresh(): Promise<void> {
  if (loading.value) return;
  loading.value = true;
  try {
    const response = await fetch(
      `/api/quotes/random?exclude=${encodeURIComponent(quote.value)}`,
      { headers: authHeaders() }
    );
    if (!response.ok) throw new Error('获取金句失败');
    applyQuote(await response.json());
  } catch {
    // 保留当前金句
  } finally {
    loading.value = false;
  }
}

async function toggleFavorite(): Promise<void> {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) {
    return;
  }
  try {
    const url = quoteId.value
      ? `/api/quotes/${quoteId.value}/favorite`
      : `/api/quotes/obsidian/${encodeURIComponent(obsidianSource.value)}/favorite`;
    const response = await fetch(url, {
      method: 'POST',
      headers: authHeaders()
    });
    if (!response.ok) throw new Error('收藏失败');
    const data = await response.json();
    favorited.value = !!data.favorited;
  } catch {
    // 不阻断阅读
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

.quote-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.eyebrow {
  color: #2f5d50;
  font-size: 12px;
  font-weight: 700;
}

.quote-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.library-link {
  padding: 3px 5px;
  color: #2f5d50;
  font-size: 11px;
  text-decoration: none;
}

.favorite-btn {
  width: 25px;
  height: 25px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #b1bac3;
  font-size: 17px;
  line-height: 1;
}

.favorite-btn.active {
  color: #d9a72d;
}

.refresh-btn {
  padding: 4px 7px;
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
