/**
 * 用户档案 Pinia Store（P1-11）
 *
 * 定位：**只读缓存**，后端（reward / identity 域）才是余额与档案的事实来源。
 *   - 保存 nickname / avatar / coins / role / device 的内存快照；
 *   - 订阅 `EVENT_NAMES.REWARD_COINS_CHANGED`，事件到达即刷新余额快照（不主动写业务接口）；
 *   - `refreshCoins()` 仅走 reward 域的只读 GET；失败时保留旧值（stale 优于清空）。
 *   - 不写 localStorage，不与 identity store 抢会话状态（token 归 stores/auth.ts）。
 */
import { computed, onScopeDispose, ref } from 'vue';
import { defineStore } from 'pinia';
import { fetchCoinsOverview } from '@/modules/reward/api';
import { EVENT_NAMES, onEvent } from './event-bus';

/** 用户档案快照（缺省字段允许为空，表示尚未拉取） */
export interface UserProfileSnapshot {
  nickname?: string;
  avatar?: string;
  coins?: number;
  role?: string | null;
  device?: string;
}

export const useUserProfileStore = defineStore('user-profile', () => {
  // ===== 只读快照 =====
  const user = ref<UserProfileSnapshot | null>(null);
  const nickname = ref<string>('');
  const avatar = ref<string>('');
  const coins = ref<number>(0);
  const role = ref<string | null>(null);
  const device = ref<string>('pc');

  /** 余额是否已从后端 / 事件取得过真实值 */
  const coinsLoaded = ref(false);
  const loading = ref(false);

  const displayName = computed(() => nickname.value || user.value?.nickname || '');

  /** 用一份快照覆盖缓存（供 identity store / 后端返回体调用） */
  function applySnapshot(snapshot: UserProfileSnapshot): void {
    user.value = { ...(user.value ?? {}), ...snapshot };
    if (typeof snapshot.nickname === 'string') nickname.value = snapshot.nickname;
    if (typeof snapshot.avatar === 'string') avatar.value = snapshot.avatar;
    if (typeof snapshot.coins === 'number') {
      coins.value = snapshot.coins;
      coinsLoaded.value = true;
    }
    if (snapshot.role !== undefined) role.value = snapshot.role;
    if (typeof snapshot.device === 'string' && snapshot.device) device.value = snapshot.device;
  }

  /**
   * 拉取余额（只读）。
   * 失败、超时或接口未就绪时静默保留旧值，并返回当前缓存值。
   */
  async function refreshCoins(): Promise<number> {
    loading.value = true;
    try {
      const overview = await fetchCoinsOverview();
      if (typeof overview?.balance === 'number') {
        coins.value = overview.balance;
        coinsLoaded.value = true;
      }
    } catch {
      // 缓存语义：后端不可用时不打断调用方，保留 stale 值
    } finally {
      loading.value = false;
    }
    return coins.value;
  }

  /** 清空缓存（登出时调用） */
  function reset(): void {
    user.value = null;
    nickname.value = '';
    avatar.value = '';
    coins.value = 0;
    role.value = null;
    device.value = 'pc';
    coinsLoaded.value = false;
  }

  // ===== 订阅：金币变更由 reward 域广播，档案只做缓存更新 =====
  const offCoins = onEvent(EVENT_NAMES.REWARD_COINS_CHANGED, (payload) => {
    if (typeof payload?.coins === 'number') {
      coins.value = payload.coins;
      coinsLoaded.value = true;
    } else if (typeof payload?.delta === 'number') {
      coins.value += payload.delta;
      coinsLoaded.value = true;
    }
    void refreshCoins();
  });
  onScopeDispose(offCoins);

  return {
    // state
    user,
    nickname,
    avatar,
    coins,
    role,
    device,
    coinsLoaded,
    loading,
    // getters
    displayName,
    // actions
    applySnapshot,
    refreshCoins,
    reset
  };
});
