/**
 * 页面级数据变更订阅（F2b-2）
 *
 * 为什么需要它：auth 在收到 data-changed 时会广播 __VTJ_SYNC__，
 * 但这个事件没有域/类型信息，页面只能"凡有变更就整块重拉"。
 * 三端高频答题时，这会把无关的题库、资讯事件也变成刷新。
 * 这里把 auth 新增的 __VTJ_DATA_CHANGED__ 按 domain/type 过滤并防抖，
 * 让页面只对自己的数据重新取数。
 */
import { onBeforeUnmount, onMounted } from 'vue';

/** auth 广播的 data-changed 详情；entity 是后端 v2 信封里的业务事件类型 */
export interface DataChangedDetail {
  type?: string;
  domain?: string;
  entity?: string;
  id?: number | string;
  data?: Record<string, unknown>;
}

/** 过滤合并后的最小事件，页面只需要知道"哪个域/哪种变更" */
export interface DataSyncEvent {
  domain: string;
  type: string;
  id?: number | string;
}

export interface DataSyncOptions {
  /** 只关心的业务域；不传表示全部 */
  domains?: string[];
  /** 只关心的事件类型（practice.submit 等）；不传表示全部 */
  types?: string[];
  /** 合并窗口，默认 100ms；高频答题页面可调大 */
  debounceMs?: number;
  /** 合并窗口结束后的回调，events 已按 domain/type/id 去重 */
  handler: (events: DataSyncEvent[]) => void;
}

export interface DataSyncListener {
  stop: () => void;
}

function pickType(detail: DataChangedDetail): string | undefined {
  // auth 的 typed 事件把业务类型放在 entity；旧生产者可能直接放在 type
  if (typeof detail.entity === 'string' && detail.entity) return detail.entity;
  if (typeof detail.type === 'string' && detail.type && detail.type !== 'data-changed') {
    return detail.type;
  }
  return undefined;
}

/**
 * 创建独立监听器（不依赖组件生命周期，便于单测与非组件场景复用）。
 * 返回 stop 用于手动清理；重复调用是安全的。
 */
export function createDataSyncListener(options: DataSyncOptions): DataSyncListener {
  const domains = options.domains && options.domains.length ? new Set(options.domains) : null;
  const types = options.types && options.types.length ? new Set(options.types) : null;
  const debounceMs = typeof options.debounceMs === 'number' ? options.debounceMs : 100;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  const pending = new Map<string, DataSyncEvent>();

  const flush = () => {
    timer = null;
    if (stopped || pending.size === 0) return;
    const events = Array.from(pending.values());
    pending.clear();
    options.handler(events);
  };

  const onDataChanged = (event: Event) => {
    if (stopped) return;
    const detail = (event as CustomEvent<DataChangedDetail>).detail;
    if (!detail || typeof detail !== 'object') return;
    const domain = typeof detail.domain === 'string' ? detail.domain : '';
    const type = pickType(detail);
    if (!domain || !type) return;
    if (domains && !domains.has(domain)) return;
    if (types && !types.has(type)) return;

    const id = detail.id;
    const key = domain + '\u0000' + type + '\u0000' + (id === undefined ? '' : String(id));
    pending.set(key, { domain, type, id });
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, debounceMs);
  };

  if (typeof window !== 'undefined') {
    window.addEventListener('__VTJ_DATA_CHANGED__', onDataChanged);
  }

  return {
    stop() {
      stopped = true;
      if (typeof window !== 'undefined') {
        window.removeEventListener('__VTJ_DATA_CHANGED__', onDataChanged);
      }
      if (timer) { clearTimeout(timer); timer = null; }
      pending.clear();
    }
  };
}

/** 组件内使用：挂载时订阅，卸载时自动清理 */
export function useDataSync(options: DataSyncOptions): void {
  let listener: DataSyncListener | null = null;
  onMounted(() => {
    listener = createDataSyncListener(options);
  });
  onBeforeUnmount(() => {
    if (listener) { listener.stop(); listener = null; }
  });
}
