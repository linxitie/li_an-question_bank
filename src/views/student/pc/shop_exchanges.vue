<template>
  <div class="ex-page">
    <header class="ex-head">
      <div>
        <h1>我的兑换</h1>
        <p class="ex-sub">
          金币兑换的订单都在这里。虚拟卡类当场发卡密，实物/需开通的商品显示「待发货/待开通」。
        </p>
      </div>
      <div class="ex-balance" v-if="balance !== null">
        <span class="ex-balance-label">我的金币</span>
        <span class="ex-balance-num">🪙 {{ balance }}</span>
      </div>
    </header>

    <nav class="ex-tabs" role="tablist">
      <button
        v-for="t in TABS"
        :key="t.value"
        class="ex-tab"
        :class="{ 'is-on': tab === t.value }"
        role="tab"
        :aria-selected="tab === t.value"
        @click="tab = t.value"
      >
        {{ t.label }}
      </button>
    </nav>

    <div v-if="loading" class="ex-empty">加载中…</div>

    <div v-else-if="error" class="ex-empty ex-error">
      <p>{{ error }}</p>
      <button class="ex-btn" @click="load">重试</button>
    </div>

    <div v-else-if="!visibleItems.length" class="ex-empty">
      <p>还没有兑换记录。</p>
      <p class="ex-hint">去金币购商城兑换你的第一个商品吧。</p>
    </div>

    <ul v-else class="ex-list">
      <li v-for="item in visibleItems" :key="item.id" class="ex-item">
        <div class="ex-item-main">
          <div class="ex-item-head">
            <span class="ex-name">{{ item.product_name }}</span>
            <span class="ex-tag" :class="`is-${item.status}`">{{ item.status_text }}</span>
          </div>

          <div class="ex-meta">
            <span>订单号 #{{ item.id }}</span>
            <span>消耗 {{ item.coin_cost }} 金币</span>
            <span v-if="item.created_at">兑换于 {{ formatTime(item.created_at) }}</span>
          </div>

          <!-- 卡密：能复制 -->
          <div v-if="item.delivered_code" class="ex-code">
            <span class="ex-code-label">卡密</span>
            <code class="ex-code-value">{{ item.delivered_code }}</code>
            <button class="ex-btn ex-btn-sm" @click="copy(item.delivered_code)">
              {{ copiedId === item.id ? '已复制' : '复制' }}
            </button>
          </div>

          <div v-else-if="item.status === 'pending'" class="ex-pending">
            已收到你的兑换，处理后会在这里更新状态。
            <span v-if="item.deliverable_type === 'manual'">（实物发货 / 权益开通由运营处理）</span>
          </div>

          <div v-if="item.shipped_at" class="ex-meta">
            <span>发货/开通时间：{{ formatTime(item.shipped_at) }}</span>
          </div>
        </div>
      </li>
    </ul>

    <footer v-if="total > pageSize" class="ex-foot">
      <button class="ex-btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
      <button class="ex-btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
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

async function copy(code: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(code);
  } catch {
    // 非安全上下文下 clipboard 不可用，退回 textarea 选中复制
    const ta = document.createElement('textarea');
    ta.value = code;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
  const item = items.value.find((i) => i.delivered_code === code);
  copiedId.value = item ? item.id : null;
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
.ex-page {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}

.ex-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.ex-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}
.ex-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
.ex-balance {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  padding: 8px 14px;
  border-radius: 12px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}
.ex-balance-label {
  font-size: 11px;
  color: #9a3412;
}
.ex-balance-num {
  font-size: 18px;
  font-weight: 600;
  color: #ea580c;
}

.ex-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.ex-tab {
  border: none;
  background: none;
  padding: 8px 12px;
  font-size: 14px;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.ex-tab.is-on {
  color: #2563eb;
  border-bottom-color: #2563eb;
  font-weight: 500;
}

.ex-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ex-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 14px 16px;
}
.ex-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ex-name {
  font-size: 15px;
  font-weight: 500;
}
.ex-tag {
  flex: 0 0 auto;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
}
.ex-tag.is-completed {
  background: #ecfdf5;
  color: #047857;
}
.ex-tag.is-pending {
  background: #fff7ed;
  color: #c2410c;
}
.ex-tag.is-refunded {
  background: #fef2f2;
  color: #b91c1c;
}

.ex-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.ex-code {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
}
.ex-code-label {
  font-size: 12px;
  color: #64748b;
}
.ex-code-value {
  flex: 1 1 auto;
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 14px;
  letter-spacing: 0.5px;
  word-break: break-all;
  color: #0f172a;
}

.ex-pending {
  margin-top: 10px;
  font-size: 12px;
  color: #c2410c;
}

.ex-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.ex-btn:hover:not(:disabled) {
  border-color: #2563eb;
  color: #2563eb;
}
.ex-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ex-btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.ex-empty {
  padding: 48px 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}
.ex-hint {
  font-size: 12px;
  color: #9ca3af;
}
.ex-error {
  color: #b91c1c;
}

.ex-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
  font-size: 13px;
  color: #6b7280;
}
</style>
