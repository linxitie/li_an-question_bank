// src/services/NotificationService.ts

export interface Notification {
  id: number;
  type: 'system' | 'approval' | 'security' | 'message';
  title: string;
  content: string;
  time: string;
  read: boolean;
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

  markAsRead(id: number) {
    const notification = this.notifications.find(n => n.id === id);
    if (notification) {
      notification.read = true;
      this.notify();
    }
  }

  private async fetchNotifications() {
    // 后端API就绪后，替换为真实调用
    // const res = await fetch('/api/notifications');
    // this.notifications = await res.json();
    this.notifications = this.generateMockNotifications();
    this.notify();
  }

  private generateMockNotifications(): Notification[] {
    const templates: Record<string, string[]> = {
      system: ['系统已更新至最新版本', '数据库备份完成', '新功能已上线'],
      approval: ['3份试卷待审批', '本周已通过12份试卷', '有新提交的试卷'],
      security: ['检测到异常登录', '密码修改成功', '登录IP变更提醒']
    };
    const types: Array<'system' | 'approval' | 'security'> = ['system', 'approval', 'security'];
    return Array.from({ length: 5 }, (_, i) => {
      const type = types[Math.floor(Math.random() * 3)];
      return {
        id: i + 1,
        type,
        title: templates[type][Math.floor(Math.random() * 3)],
        content: '',
        time: `${Math.floor(Math.random() * 24)}小时前`,
        read: Math.random() > 0.5
      };
    });
  }
}

export const notificationService = new NotificationService();
