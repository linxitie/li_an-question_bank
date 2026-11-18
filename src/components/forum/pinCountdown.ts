/**
 * 置顶倒计时（2026-11-15）。
 *
 * 背景：卡片上原来只显示「置顶 至 2026-11-18」，管理员要自己算还剩几天。
 * 这里把到期时间换算成「剩 2 天 3 小时」，同时给 title 提供精确时间。
 *
 * 实现要点：模块级 30 秒 ticker + 模板内直接调用。Vue 会在渲染时收集 now 的依赖，
 * 因此同一页面上所有卡片会随 tick 一起刷新，不需要每个页面自己起定时器。
 */
import { ref } from 'vue';

const now = ref(Date.now());

if (typeof window !== 'undefined') {
  const timer = window.setInterval(() => {
    now.value = Date.now();
  }, 30_000);
  // vitest / node 环境下别拖住进程
  (timer as unknown as { unref?: () => void })?.unref?.();
}

/** 置顶剩余时长文案：永久 / 已到期 / 剩 N 天 M 小时 / 剩 N 小时 / 剩 N 分钟 */
export function pinCountdown(pinUntil?: string | null): string {
  const tick = now.value; // 依赖收集：tick 变了模板会重渲染
  if (!pinUntil) return '永久';
  const end = new Date(pinUntil).getTime();
  if (Number.isNaN(end)) return '永久';
  const diff = end - tick;
  if (diff <= 0) return '已到期';
  const minutes = Math.floor(diff / 60000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  if (days > 0) return hours > 0 ? `剩 ${days} 天 ${hours} 小时` : `剩 ${days} 天`;
  if (hours > 0) return `剩 ${hours} 小时`;
  return `剩 ${Math.max(1, minutes)} 分钟`;
}

/** 卡片 hover 提示：精确到期时间 */
export function pinTitle(pinUntil?: string | null): string {
  if (!pinUntil) return '永久置顶（不会自动取消）';
  const date = new Date(pinUntil);
  if (Number.isNaN(date.getTime())) return '永久置顶（不会自动取消）';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `置顶到期：${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
