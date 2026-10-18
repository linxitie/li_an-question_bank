/**
 * 金币商城（reward）域 Store（P2-41）
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * products / balance / records / exchanging 为本域业务状态。
 * 约定：
 *   - 余额以后端 `sys_user.total_coins` 为唯一事实来源，前端只读快照；
 *   - 兑换中 exchanging 为真时直接拒绝，防止重复点击造成双扣；
 *   - 兑换成功广播 `reward:coins-changed`，供 user-profile 刷新余额快照；
 *   - 不写 localStorage，流水与商品均以后端为准。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  exchangeRewardProduct,
  fetchCoinTransactions,
  fetchCoinsOverview,
  fetchRewardList,
  type RewardCoinRecord,
  type RewardExchangeResult,
  type RewardListQuery,
  type RewardProduct
} from './api';
import { notifyCoinsChanged } from './events';

export interface RewardState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createRewardInitialState(): RewardState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export interface RewardStoreQuery extends RewardListQuery {}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

function createRequestId(): string {
  return `ex-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const useRewardStore = defineStore('reward', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const products = ref<RewardProduct[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(100);

  const balance = ref(0);
  const monthIncome = ref(0);
  const monthExpense = ref(0);

  const records = ref<RewardCoinRecord[]>([]);
  const recordTotal = ref(0);
  const recordPage = ref(1);
  const recordPageSize = ref(20);

  const selected = ref<RewardProduct | null>(null);
  const exchanging = ref(false);
  const lastExchange = ref<RewardExchangeResult | null>(null);

  const ready = computed(() => initialized.value && error.value === null);

  async function load(query: RewardStoreQuery = {}): Promise<void> {
    loading.value = true;
    error.value = null;
    page.value = query.page && query.page > 0 ? query.page : 1;
    pageSize.value =
      query.pageSize && query.pageSize > 0 ? query.pageSize : pageSize.value;
    try {
      const result = await fetchRewardList({
        category: query.category,
        search: query.search,
        page: page.value,
        pageSize: pageSize.value
      });
      products.value = result.items ?? [];
      total.value = result.total ?? products.value.length;
    } catch (e) {
      error.value = errorMessage(e);
      products.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadBalance(): Promise<number> {
    try {
      const overview = await fetchCoinsOverview();
      balance.value = overview.balance ?? 0;
      monthIncome.value = overview.month_income ?? 0;
      monthExpense.value = overview.month_expense ?? 0;
    } catch (e) {
      error.value = errorMessage(e);
    }
    return balance.value;
  }

  async function loadRecords(
    nextPage = 1,
    nextPageSize = recordPageSize.value
  ): Promise<void> {
    loading.value = true;
    error.value = null;
    recordPage.value = nextPage > 0 ? nextPage : 1;
    recordPageSize.value = nextPageSize > 0 ? nextPageSize : 20;
    try {
      const result = await fetchCoinTransactions(
        recordPage.value,
        recordPageSize.value
      );
      records.value = result.items ?? [];
      recordTotal.value = result.total ?? records.value.length;
    } catch (e) {
      error.value = errorMessage(e);
      records.value = [];
      recordTotal.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  function selectProduct(product: RewardProduct | null): void {
    selected.value = product;
  }

  async function exchange(
    productId: number
  ): Promise<RewardExchangeResult | null> {
    if (exchanging.value) return null;
    exchanging.value = true;
    error.value = null;
    try {
      const result = await exchangeRewardProduct(productId, createRequestId());
      balance.value = result.balance;
      lastExchange.value = result;
      notifyCoinsChanged({
        coins: result.balance,
        delta: -result.coin_cost,
        reason: 'shop.purchase'
      });
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    } finally {
      exchanging.value = false;
    }
  }

  function reset(): void {
    const initial = createRewardInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    products.value = [];
    total.value = 0;
    page.value = 1;
    pageSize.value = 100;
    balance.value = 0;
    monthIncome.value = 0;
    monthExpense.value = 0;
    records.value = [];
    recordTotal.value = 0;
    recordPage.value = 1;
    recordPageSize.value = 20;
    selected.value = null;
    exchanging.value = false;
    lastExchange.value = null;
  }

  return {
    loading,
    error,
    initialized,
    products,
    total,
    page,
    pageSize,
    balance,
    monthIncome,
    monthExpense,
    records,
    recordTotal,
    recordPage,
    recordPageSize,
    selected,
    exchanging,
    lastExchange,
    ready,
    load,
    loadBalance,
    loadRecords,
    selectProduct,
    exchange,
    reset
  };
});
