import { beforeEach, describe, expect, it, vi } from 'vitest';
import { effectScope, type EffectScope } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import { fetchCoinsOverview } from '@/modules/reward/api';
import { clearAllEvents, EVENT_NAMES, emitEvent } from '@/stores/event-bus';
import { useUserProfileStore } from '@/stores/user-profile';

vi.mock('@/modules/reward/api', () => ({
  fetchCoinsOverview: vi.fn()
}));

const mockedOverview = vi.mocked(fetchCoinsOverview);

let scope: EffectScope;

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
  scope = effectScope();
});

describe('user-profile 金币快照', () => {
  it('广播 reward:coins-changed 后调用一次只读拉取', async () => {
    mockedOverview.mockResolvedValue({
      balance: 360,
      month_income: 0,
      month_expense: 0
    });

    scope.run(() => useUserProfileStore());

    emitEvent(EVENT_NAMES.REWARD_COINS_CHANGED, { coins: 380, delta: -120 });

    await vi.waitFor(() => {
      expect(mockedOverview).toHaveBeenCalledTimes(1);
    });

    const store = useUserProfileStore();
    await vi.waitFor(() => {
      expect(store.coins).toBe(360);
    });
    expect(store.coinsLoaded).toBe(true);

    scope.stop();
  });

  it('接口失败时保留事件载荷快照', async () => {
    mockedOverview.mockRejectedValue(new Error('网络连接失败'));

    const store = scope.run(() => useUserProfileStore())!;

    emitEvent(EVENT_NAMES.REWARD_COINS_CHANGED, { coins: 120 });

    await vi.waitFor(() => {
      expect(mockedOverview).toHaveBeenCalledTimes(1);
    });
    expect(store.coins).toBe(120);
    expect(store.coinsLoaded).toBe(true);

    scope.stop();
  });

  it('refreshCoins 成功后写入余额', async () => {
    mockedOverview.mockResolvedValue({
      balance: 500,
      month_income: 500,
      month_expense: 0
    });

    const store = scope.run(() => useUserProfileStore())!;
    const balance = await store.refreshCoins();

    expect(balance).toBe(500);
    expect(store.coins).toBe(500);
    expect(store.coinsLoaded).toBe(true);

    scope.stop();
  });
});
