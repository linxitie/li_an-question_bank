// src/utils/desktopNotify.ts
// 模块4/7 v2 - 桌面通知：今日任务未完成提醒 / 周日复盘提醒（Web Notification API）
// 用法：ensurePermission() 先请求授权；startTodayReminderPolling(fetchFn) 启动轮询。

export function isSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export async function ensurePermission(): Promise<boolean> {
  if (!isSupported()) return false;
  if (Notification.permission === 'granted') return true;
  if (Notification.permission === 'denied') return false;
  try {
    const p = await Notification.requestPermission();
    return p === 'granted';
  } catch (e) {
    return false;
  }
}

export function notifyDesktop(title: string, body: string, tag: string, onClickUrl?: string): void {
  if (!isSupported() || Notification.permission !== 'granted') return;
  try {
    const n = new Notification(title, { body, tag, icon: undefined });
    if (onClickUrl) {
      n.onclick = () => {
        window.focus();
        if (onClickUrl) window.location.hash = onClickUrl;
        n.close();
      };
    }
    setTimeout(() => n.close(), 15000);
  } catch (e) { /* 通知失败不影响主流程 */ }
}

// 每日提醒轮询：fetchTodayTasks 需返回 { items: [{ is_completed }] } 或 { today: [...] }
// 规则：今日有未完成任务 且 本地时间 >= remindHour → 弹桌面通知（每日一次 tag 去重）
export function startTodayReminderPolling(
  fetchTodayTasks: () => Promise<any[]>,
  opts?: { remindHour?: number; weeklyReviewHour?: number },
): { stop: () => void } {
  const remindHour = opts?.remindHour ?? 19;
  const weeklyReviewHour = opts?.weeklyReviewHour ?? 20;
  const poll = async () => {
    try {
      const items = await fetchTodayTasks();
      const pending = (items || []).filter((t: any) => !t.is_completed).length;
      const now = new Date();
      const todayTag = 'today-' + now.toISOString().slice(0, 10);
      // 未完成任务提醒（>= remindHour）
      if (pending > 0 && now.getHours() >= remindHour) {
        notifyDesktop('砺安题库 · 今日任务提醒', `今天还有 ${pending} 项任务未完成，记得完成领取金币`, todayTag, '/study-plan');
      }
      // 周日复盘提醒（>= weeklyReviewHour）
      if (now.getDay() === 0 && now.getHours() >= weeklyReviewHour) {
        notifyDesktop('砺安题库 · 每周复盘', '本周备考复盘已生成，找联考小智聊聊你的备考轨迹吧', 'weekly-review', '/ai-assistant');
      }
    } catch (e) { /* 轮询失败静默 */ }
  };
  poll();
  const timer = setInterval(poll, 10 * 60 * 1000); // 每10分钟
  return { stop: () => clearInterval(timer) };
}
