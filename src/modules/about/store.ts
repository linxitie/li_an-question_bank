/**
 * 关于砺安题库（about）域 Store（P2-69）。
 *
 * 只读消费通用配置：版本号 / 服务名来自 `GET /health`，
 * 联系方式来自 api.ts 静态常量（本域无专属端点）。
 * 无写接口、无事件进出、不写 localStorage。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchAboutProfile,
  type AboutAppInfo,
  type AboutContact
} from './api';

/** 公共状态骨架 */
export interface AboutState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

/** 生成初始状态，保证 reset() 与首次加载口径一致 */
export function createAboutInitialState(): AboutState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

export const useAboutStore = defineStore('about', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const info = ref<AboutAppInfo | null>(null);
  const contact = ref<AboutContact | null>(null);

  /** 只读派生：本域是否可用（已完成初始化且无错误） */
  const ready = computed(() => initialized.value && error.value === null);

  /** 版本号（通用配置只读消费） */
  const version = computed(() => info.value?.version ?? '');

  /** 服务名 */
  const service = computed(() => info.value?.service ?? '');

  /**
   * 加载关于页配置。
   * 失败进入错误态（保留静态联系方式可用性由页面决定）。
   */
  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const profile = await fetchAboutProfile();
      info.value = profile.info;
      contact.value = profile.contact;
    } catch (e) {
      error.value = errorMessage(e);
      info.value = null;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  /** 重置为初始状态 */
  function reset(): void {
    const initial = createAboutInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    info.value = null;
    contact.value = null;
  }

  return {
    loading,
    error,
    initialized,
    info,
    contact,
    ready,
    version,
    service,
    reset,
    load
  };
});
