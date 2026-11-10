<template>
  <div class="mex-panel" :class="{ 'is-compact': compact }">
    <nav class="mex-tabs" role="tablist">
      <button
        v-for="t in TABS"
        :key="t.value"
        class="mex-tab"
        :class="{ 'is-on': tab === t.value }"
        role="tab"
        :aria-selected="tab === t.value"
        @click="tab = t.value"
      >
        {{ t.label }}
      </button>
      <span class="mex-balance" v-if="balance !== null">🪙 {{ balance }}</span>
    </nav>

    <div v-if="loading" class="mex-empty">加载中…</div>

    <div v-else-if="error" class="mex-empty mex-error">
      <p>{{ error }}</p>
      <button class="mex-btn" @click="load">重试</button>
    </div>

    <div v-else-if="!visibleItems.length" class="mex-empty">
      <p>还没有兑换记录。</p>
      <p class="mex-hint">去商城兑换你的第一个商品吧。</p>
    </div>

    <ul v-else class="mex-list">
      <li v-for="item in visibleItems" :key="item.id" class="mex-item">
        <div class="mex-item-head">
          <span class="mex-name">{{ item.product_name }}</span>
          <span class="mex-tag" :class="`is-${item.status}`">{{ item.status_text }}</span>
        </div>

        <div class="mex-meta">
          <span>订单号 #{{ item.id }}</span>
          <span>消耗 {{ item.coin_cost }} 金币</span>
          <span v-if="item.created_at">兑换于 {{ formatTime(item.created_at) }}</span>
        </div>

        <div v-if="item.delivered_code" class="mex-code">
          <span class="mex-code-label">卡密</span>
          <code class="mex-code-value">{{ item.delivered_code }}</code>
          <button class="mex-btn mex-btn-sm" @click="copy(item)">
            {{ copiedId === item.id ? '已复制' : '复制' }}
          </button>
        </div>

        <div v-else-if="item.status === 'pending'" class="mex-pending">
          已收到你的兑换，处理后会在这里更新状态。
          <span v-if="item.deliverable_type === 'manual'">（实物发货 / 权益开通由运营处理）</span>
        </div>

        <div v-if="item.shipped_at" class="mex-meta">
          <span>发货/开通时间：{{ formatTime(item.shipped_at) }}</span>
        </div>
      </li>
    </ul>

    <footer v-if="total > pageSize" class="mex-foot">
      <button class="mex-btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
      <button class="mex-btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchCoinsOverview,
  fetchMyExchanges,
  type RewardExchangeItem
} from '@/modules/reward/api';

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });

const TABS = [
  { value: 'all', label: '全部' },
  { value: 'completed', label: '已交付' },
  { value: 'pending', label: '待处理' }
] as const;
type TabValue = (typeof TABS)[number]['value'];

const items = ref<RewardExchangeItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const tab = ref<TabValue>('all');
const loading = ref(false);
const error = ref('');
const balance = ref<number | null>(null);
const copiedId = ref<number | null>(null);

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const visibleItems = computed(() =>
  tab.value === 'all' ? items.value : items.value.filter((i) => i.status === tab.value)
);

function formatTime(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    const res = await fetchMyExchanges(page.value, pageSize);
    items.value = res.items || [];
    total.value = res.total || 0;
  } catch (e: any) {
    error.value = e?.message || '加载失败，请稍后重试';
  } finally {
    loading.value = false;
  }
}

async function loadBalance(): Promise<void> {
  try {
    const res = await fetchCoinsOverview();
    balance.value = res.balance;
  } catch {
    balance.value = null;
  }
}

function go(next: number): void {
  if (next < 1 || next > totalPages.value) return;
  page.value = next;
  load();
}

async function copy(item: RewardExchangeItem): Promise<void> {
  const code = item.delivered_code || '';
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = code;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
  copiedId.value = item.id;
  setTimeout(() => {
    copiedId.value = null;
  }, 1500);
}

onMounted(() => {
  load();
  loadBalance();
});
</script>

<style scoped>
.mex-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mex-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid #e5e7eb;
}
.mex-tab {
  border: none;
  background: none;
  padding: 8px 12px;
  font-size: 14px;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.mex-tab.is-on {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 500;
}
.mex-balance {
  margin-left: auto;
  font-size: 13px;
  color: #b45309;
  font-weight: 600;
}

.mex-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mex-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
}
.mex-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.mex-name {
  font-size: 15px;
  font-weight: 500;
  color: #1a1a1a;
}
.mex-tag {
  flex: 0 0 auto;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
}
.mex-tag.is-completed {
  background: #ecfdf5;
  color: #047857;
}
.mex-tag.is-pending {
  background: #fff7ed;
  color: #c2410c;
}
.mex-tag.is-refunded {
  background: #fef2f2;
  color: #b91c1c;
}

.mex-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.mex-code {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
}
.mex-code-label {
  font-size: 12px;
  color: #64748b;
}
.mex-code-value {
  flex: 1 1 auto;
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 14px;
  letter-spacing: 0.5px;
  word-break: break-all;
  color: #0f172a;
}

.mex-pending {
  margin-top: 10px;
  font-size: 12px;
  color: #c2410c;
}

.mex-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.mex-btn:hover:not(:disabled) {
  border-color: #2563eb;
  color: #2563eb;
}
.mex-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mex-btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.mex-empty {
  padding: 36px 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}
.mex-hint {
  font-size: 12px;
  color: #9ca3af;
}
.mex-error {
  color: #b91c1c;
}

.mex-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

/* 弹窗内更紧凑 */
.is-compact .mex-item {
  padding: 10px 12px;
}
.is-compact .mex-empty {
  padding: 24px 12px;
}
</style>
