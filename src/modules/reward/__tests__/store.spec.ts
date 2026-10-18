import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useRewardStore } from '../store';
import {
  exchangeRewardProduct,
  fetchCoinTransactions,
  fetchCoinsOverview,
  fetchRewardList,
  type RewardExchangeResult,
  type RewardProduct
} from '../api';
import { clearAllEvents, EVENT_NAMES, onEvent } from '@/stores/event-bus';

vi.mock('../api', () => ({
  fetchRewardList: vi.fn(),
  fetchRewardDetail: vi.fn(),
  exchangeRewardProduct: vi.fn(),
  fetchCoinsOverview: vi.fn(),
  fetchCoinTransactions: vi.fn(),
  refreshReward: vi.fn()
}));

const mockedFetchList = vi.mocked(fetchRewardList);
const mockedExchange = vi.mocked(exchangeRewardProduct);
const mockedOverview = vi.mocked(fetchCoinsOverview);
const mockedTransactions = vi.mocked(fetchCoinTransactions);

function makeProduct(
  id: number,
  overrides: Partial<RewardProduct> = {}
): RewardProduct {
  return {
    id,
    name: `商品 ${id}`,
    category: '限定称号',
    product_type: 'virtual',
    coin_price: 120,
    stock: 3,
    image_url: '🎁',
    description: '描述',
    deliverable_type: 'none',
    deliverable_payload: {},
    status: 'on_sale',
    sort_order: id,
    ...overrides
  };
}

function makeExchange(
  overrides: Partial<RewardExchangeResult> = {}
): RewardExchangeResult {
  return {
    exchange_id: 1,
    balance: 380,
    product_name: '商品 1',
    coin_cost: 120,
    message: '兑换成功',
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
});

describe('reward store 商品与余额', () => {
  it('加载商品列表并写入总数', async () => {
    mockedFetchList.mockResolvedValue({
      total: 2,
      page: 1,
      page_size: 100,
      items: [makeProduct(1), makeProduct(2)]
    });

    const store = useRewardStore();
    await store.load({ pageSize: 100 });

    expect(mockedFetchList).toHaveBeenCalledWith({
      category: undefined,
      search: undefined,
      page: 1,
      pageSize: 100
    });
    expect(store.products).toHaveLength(2);
    expect(store.total).toBe(2);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('商品加载失败进入错误态', async () => {
    mockedFetchList.mockRejectedValue(new Error('网络连接失败'));

    const store = useRewardStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.products).toEqual([]);
    expect(store.ready).toBe(false);
  });

  it('拉取金币概览写入余额与月度收支', async () => {
    mockedOverview.mockResolvedValue({
      balance: 880,
      month_income: 1000,
      month_expense: 120
    });

    const store = useRewardStore();
    const balance = await store.loadBalance();

    expect(balance).toBe(880);
    expect(store.balance).toBe(880);
    expect(store.monthIncome).toBe(1000);
    expect(store.monthExpense).toBe(120);
  });

  it('加载金币流水', async () => {
    mockedTransactions.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 50,
      items: [
        {
          record_id: 1,
          coin_change: -120,
          current_balance: 380,
          transaction_type: 'SPEND',
          source_type: 'SHOP',
          description: '兑换商品',
          transaction_time: '2026-10-18T10:00:00'
        }
      ]
    });

    const store = useRewardStore();
    await store.loadRecords(1, 50);

    expect(mockedTransactions).toHaveBeenCalledWith(1, 50);
    expect(store.records).toHaveLength(1);
    expect(store.recordTotal).toBe(1);
  });
});

describe('reward store 兑换', () => {
  it('兑换成功刷新余额并广播 reward:coins-changed', async () => {
    mockedExchange.mockResolvedValue(makeExchange());
    const events: Array<{ coins?: number; delta?: number; reason?: string }> = [];
    onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => events.push(payload));

    const store = useRewardStore();
    const result = await store.exchange(1);

    expect(result).toEqual(makeExchange());
    expect(store.balance).toBe(380);
    expect(store.exchanging).toBe(false);
    expect(mockedExchange).toHaveBeenCalledTimes(1);
    const [productId, requestId] = mockedExchange.mock.calls[0];
    expect(productId).toBe(1);
    expect(requestId).toMatch(/^ex-/);
    expect(events).toEqual([
      { coins: 380, delta: -120, reason: 'shop.purchase' }
    ]);
  });

  it('兑换中重复点击只发起一次请求', async () => {
    let resolveExchange!: (value: RewardExchangeResult) => void;
    mockedExchange.mockImplementation(
      () =>
        new Promise<RewardExchangeResult>((resolve) => {
          resolveExchange = resolve;
        })
    );

    const store = useRewardStore();
    const first = store.exchange(1);
    const second = await store.exchange(1);

    expect(second).toBeNull();
    expect(mockedExchange).toHaveBeenCalledTimes(1);

    resolveExchange(makeExchange());
    await expect(first).resolves.toEqual(makeExchange());
    expect(store.exchanging).toBe(false);
  });

  it('兑换失败写入错误且不广播余额变更', async () => {
    mockedExchange.mockRejectedValue(new Error('金币不足'));
    const events: unknown[] = [];
    onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => events.push(payload));

    const store = useRewardStore();
    const result = await store.exchange(1);

    expect(result).toBeNull();
    expect(store.error).toBe('金币不足');
    expect(store.exchanging).toBe(false);
    expect(events).toEqual([]);
  });
});
