/**
 * `src/utils/recruitmentRefresh.js` 的类型声明。
 *
 * 该模块是无类型 JavaScript（不依赖 Vue，Options API 与 <script setup> 共用），
 * 此处按实际导出签名补声明，避免 TS7016（隐式 any）污染 5 个调用点。
 */

/** fetchFn 收到的上下文：signal 用于取消，ts 用于破缓存 */
export interface RecruitmentRefreshContext {
  signal: AbortSignal;
  ts: number;
}

export interface CreateRecruitmentRefresherOptions {
  /** 实际取数函数，必须自行使用 ctx.signal 与 ctx.ts */
  fetchFn: (ctx: RecruitmentRefreshContext) => Promise<unknown>;
  /** 数据回调 */
  onData?: (data: unknown, meta: unknown) => void;
  onError?: (err: Error) => void;
  /** 轮询间隔，默认 15 分钟 */
  pollMs?: number;
  /** 同源刷新最小间隔（防抖/聚焦节流），默认 60 秒 */
  minIntervalMs?: number;
  /** 关注的广播消息名，默认「招考信息更新」 */
  syncMessage?: string;
}

export interface RecruitmentRefresher {
  /** 主动刷新；reason 仅用于日志定位触发源 */
  refresh: (reason?: string) => void;
  /** 清理全部监听器与定时器（常驻页必须调用） */
  destroy: () => void;
  /** 上次成功取数的时间戳 */
  getLastLoaded: () => number;
}

/** 创建招考信息统一刷新内核 */
export function createRecruitmentRefresher(
  options: CreateRecruitmentRefresherOptions
): RecruitmentRefresher;
export default createRecruitmentRefresher;
