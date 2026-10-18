/**
 * 成绩分析（analytics）域 Store 外壳 —— scripts/scaffold-module.mjs 生成（P1-13）
 *
 * 状态契约为最小公共骨架，字段与 README.md「store 状态契约」保持一致；
 * 本文件只提供可实例化的空签名，业务逻辑与真实数据加载在 P2 阶段实现。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

/** 本域状态契约（外壳字段） */
export interface AnalyticsState {
  /** 是否正在加载数据 */
  loading: boolean;
  /** 最近一次错误信息（无错误为 null） */
  error: string | null;
  /** 是否已完成首次初始化 */
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createAnalyticsInitialState(): AnalyticsState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export const useAnalyticsStore = defineStore('analytics', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 重置为初始状态（外壳实现，P2 阶段按需扩展） */
  function reset(): void {
    const initial = createAnalyticsInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
  }

  /**
   * 加载本域数据。
   * P2 阶段实现：调用 api.ts 中的封装方法，成功后置 initialized 为 true。
   */
  async function load(): Promise<void> {
    throw new Error('analytics 域 load() 尚未实现（P2 阶段实现）');
  }

  return {
    loading,
    error,
    initialized,
    ready,
    reset,
    load
  };
});
