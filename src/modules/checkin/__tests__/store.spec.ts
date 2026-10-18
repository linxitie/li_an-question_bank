import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useCheckinStore } from '../store';
import {
  fetchTodayStatus,
  submitCheckin,
  type CheckinResult,
  type CheckinStatus
} from '../api';
import { clearAllEvents, EVENT_NAMES, onEvent } from '@/stores/event-bus';

vi.mock('../api', () => ({
  fetchTodayStatus: vi.fn(),
  submitCheckin: vi.fn(),
  refreshCheckin: vi.fn()
}));

const mockedStatus = vi.mocked(fetchTodayStatus);
const mockedSubmit = vi.mocked(submitCheckin);

function makeStatus(overrides: Partial<CheckinStatus> = {}): CheckinStatus {
  return {
    date: '2026-10-18',
    checked_in: false,
    continuous_days: 2,
    today_reward: 0,
    next_reward: { coins: 5, growth: 5 },
    ...overrides
  };
}

function makeResult(overrides: Partial<CheckinResult> = {}): CheckinResult {
  return {
    date: '2026-10-18',
    checked_in: true,
    is_today_first: true,
    continuous_days: 3,
    today_reward: 5,
    reward_growth: 5,
    message: '签到成功，连续3天',
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
});

describe('checkin store 状态加载', () => {
  it('每次 load 都向后端查询并写入今日状态', async () => {
    mockedStatus.mockResolvedValue(makeStatus());

    const store = useCheckinStore();
    await store.load();
    await store.load();

    expect(mockedStatus).toHaveBeenCalledTimes(2);
    expect(store.status?.checked_in).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
  });

  it('加载失败进入错误态', async () => {
    mockedStatus.mockRejectedValue(new Error('网络连接失败'));

    const store = useCheckinStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.status).toBeNull();
    expect(store.ready).toBe(false);
  });
});

describe('checkin store 签到', () => {
  it('签到成功更新状态并广播 reward:coins-changed', async () => {
    mockedStatus.mockResolvedValue(makeStatus());
    mockedSubmit.mockResolvedValue(makeResult());
    const events: Array<{ coins?: number; delta?: number; reason?: string }> = [];
    onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => events.push(payload));

    const store = useCheckinStore();
    await store.load();
    const result = await store.checkin();

    expect(result).toEqual(makeResult());
    expect(store.status).toMatchObject({
      checked_in: true,
      continuous_days: 3,
      today_reward: 5
    });
    expect(store.checkingIn).toBe(false);
    expect(events).toEqual([{ delta: 5, reason: 'checkin.done' }]);
  });

  it('今日已签到后重复点击不再请求后端', async () => {
    mockedStatus.mockResolvedValue(makeStatus({ checked_in: true }));
    mockedSubmit.mockResolvedValue(makeResult({ is_today_first: false }));

    const store = useCheckinStore();
    await store.load();
    const result = await store.checkin();

    expect(result).toBeNull();
    expect(mockedSubmit).not.toHaveBeenCalled();
  });

  it('签到请求进行中重复点击只发起一次请求', async () => {
    mockedStatus.mockResolvedValue(makeStatus());
    let resolveSubmit!: (value: CheckinResult) => void;
    mockedSubmit.mockImplementation(
      () =>
        new Promise<CheckinResult>((resolve) => {
          resolveSubmit = resolve;
        })
    );

    const store = useCheckinStore();
    await store.load();

    const first = store.checkin();
    const second = await store.checkin();

    expect(second).toBeNull();
    expect(mockedSubmit).toHaveBeenCalledTimes(1);

    resolveSubmit(makeResult());
    await expect(first).resolves.toEqual(makeResult());
    expect(store.checkingIn).toBe(false);
  });

  it('后端返回今日已签时不广播金币事件', async () => {
    mockedStatus.mockResolvedValue(makeStatus());
    mockedSubmit.mockResolvedValue(makeResult({ is_today_first: false }));
    const events: unknown[] = [];
    onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => events.push(payload));

    const store = useCheckinStore();
    await store.load();
    const result = await store.checkin();

    expect(result?.is_today_first).toBe(false);
    expect(store.status?.checked_in).toBe(true);
    expect(events).toEqual([]);
  });

  it('签到失败写入错误且不广播事件', async () => {
    mockedStatus.mockResolvedValue(makeStatus());
    mockedSubmit.mockRejectedValue(new Error('签到失败'));
    const events: unknown[] = [];
    onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => events.push(payload));

    const store = useCheckinStore();
    await store.load();
    const result = await store.checkin();

    expect(result).toBeNull();
    expect(store.error).toBe('签到失败');
    expect(store.checkingIn).toBe(false);
    expect(events).toEqual([]);
  });
});
