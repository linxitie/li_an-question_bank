/**
 * 每日签到（checkin）域 Store（P2-48）。
 *
 * - 今日状态每次 `load()` 都向后端查询，不做本地持久化或布尔缓存；
 * - 签到中重复点击直接拒绝，避免并发重复请求（后端仍以唯一约束兜底）；
 * - 成功签到后广播 `reward:coins-changed`，供「我的」与商城余额快照刷新；
 * - 重复签到（is_today_first=false）不发事件。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchTodayStatus,
  submitCheckin,
  type CheckinResult,
  type CheckinStatus
} from './api';
import { notifyCoinsChanged } from './events';

export interface CheckinState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createCheckinInitialState(): CheckinState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message);
  }
  return '请求失败，请稍后重试';
}

export const useCheckinStore = defineStore('checkin', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const status = ref<CheckinStatus | null>(null);
  const checkingIn = ref(false);
  const lastResult = ref<CheckinResult | null>(null);

  const ready = computed(() => initialized.value && error.value === null);
  const checkedInToday = computed(() => status.value?.checked_in === true);

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      status.value = await fetchTodayStatus();
    } catch (e) {
      error.value = errorMessage(e);
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function checkin(): Promise<CheckinResult | null> {
    if (checkingIn.value) return null;
    if (status.value?.checked_in) return null;

    checkingIn.value = true;
    error.value = null;
    try {
      const result = await submitCheckin();
      lastResult.value = result;
      status.value = {
        date: result.date,
        checked_in: true,
        continuous_days: result.continuous_days,
        today_reward: result.today_reward,
        next_reward: status.value?.next_reward ?? { coins: 0, growth: 0 }
      };
      if (result.is_today_first) {
        notifyCoinsChanged({
          delta: result.today_reward,
          reason: 'checkin.done'
        });
      }
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      return null;
    } finally {
      checkingIn.value = false;
      initialized.value = true;
    }
  }

  function reset(): void {
    const initial = createCheckinInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    status.value = null;
    checkingIn.value = false;
    lastResult.value = null;
  }

  return {
    loading,
    error,
    initialized,
    status,
    checkingIn,
    lastResult,
    ready,
    checkedInToday,
    reset,
    load,
    checkin
  };
});
