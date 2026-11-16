// src/services/NotificationService.ts

export interface Notification {
  id: number;
  type: 'system' | 'approval' | 'security' | 'message' | 'feedback' | 'forum';
  title: string;
  content: string;
  time: string;
  read: boolean;
  link?: string | null;
  relatedType?: string | null;
  relatedId?: number | null;
}

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
}

class NotificationService {
  private listeners: Function[] = [];
  private notifications: Notification[] = [];
  private pollingInterval = 30000;
  private timer: any = null;

  startPolling() {
    this.fetchNotifications();
    this.timer = setInterval(() => this.fetchNotifications(), this.pollingInterval);
  }

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  subscribe(listener: Function) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify() {
    this.listeners.forEach(listener => listener(this.notifications));
  }

  getUnreadCount(): number {
    return this.notifications.filter(n => !n.read).length;
  }

  async markAsRead(id: number) {
    const notification = this.notifications.find(n => n.id === id);
    if (notification && !notification.read) {
      notification.read = true;
      this.notify();
      try {
        await apiFetch('/api/notifications/' + id + '/read', { method: 'PUT' });
      } catch {
        /* 标记失败不阻塞跳转 */
      }
    }
  }

  async markAllAsRead() {
    this.notifications.forEach(n => (n.read = true));
    this.notify();
    try {
      await apiFetch('/api/notifications/read-all', { method: 'PUT' });
    } catch {
      /* 忽略 */
    }
  }

  private async fetchNotifications() {
    try {
      const res = await apiFetch('/api/notifications?page=1&page_size=20');
      if (!res.ok) return;
      const data = await res.json();
      this.notifications = (data.items || []).map((n: any) => ({
        id: n.notification_id,
        type: n.type || 'system',
        title: n.title || '',
        content: n.content || '',
        time: n.created_at ? String(n.created_at).replace('T', ' ').slice(5, 16) : '',
        read: !!n.is_read,
        link: n.link || null,
        relatedType: n.related_type || null,
        relatedId: n.related_id || null
      }));
      this.notify();
    } catch {
      /* 轮询失败保留上一次数据 */
    }
  }
}

export const notificationService = new NotificationService();
export default notificationService;
