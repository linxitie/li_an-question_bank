# 管理员端各模块优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现管理员端Dashboard真实数据对接、题库管理表格增强、头像下拉菜单、消息中心动态UI等优化

**Architecture:** 基于现有AdminLayout+8个admin页面重构，添加NotificationService响应式服务层，对接后端真实API

**Tech Stack:** Vue 3, ECharts, VTJ.PRO, TypeScript

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `src/services/NotificationService.ts` | 通知服务层（Mock数据+轮询） | 新建 |
| `src/layouts/AdminLayout.vue` | 头像下拉菜单+消息中心 | 修改 |
| `.vtj/vue/admin_dashboard.vue` | Dashboard真实数据对接 | 修改 |
| `.vtj/vue/admin_questions.vue` | 题库表格增强（题型/难度列） | 修改 |
| `.vtj/vue/admin_users.vue` | 批量操作实现 | 修改 |
| `.vtj/vue/admin_backup.vue` | 统计加载 | 修改 |
| `.vtj/vue/admin_logs.vue` | 导出功能 | 修改 |
| `.vtj/vue/admin_settings.vue` | 选项卡补全 | 修改 |
| `.vtj/vue/paper_approval.vue` | 审批统计指标 | 修改 |
| `src/router/index.ts` | 新增profile路由 | 修改 |

---

## Task 1: 创建NotificationService服务层

**Files:**
- Create: `src/services/NotificationService.ts`

- [ ] **Step 1: 创建通知服务文件**

```typescript
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
```

- [ ] **Step 2: 提交**

```bash
git add src/services/NotificationService.ts
git commit -m "feat: add NotificationService with mock data and polling"
```

---

## Task 2: AdminLayout头像下拉菜单

**Files:**
- Modify: `src/layouts/AdminLayout.vue`

- [ ] **Step 1: 添加导入和状态**

在 `<script lang="ts">` 的 `import` 部分后、`setup()` 内添加：

```typescript
import { notificationService, type Notification } from '@/services/NotificationService';

// 在 setup() 内添加
const showUserMenu = ref(false);
const showNotifications = ref(false);
const showPasswordDialog = ref(false);
const notifications = ref<Notification[]>([]);
const unreadCount = ref(0);
const newPassword = ref('');
const confirmPassword = ref('');
const avatarUrl = ref('');

onMounted(() => {
  // ... 已有的 onMounted 逻辑
  notificationService.startPolling();
  notificationService.subscribe((notifs: Notification[]) => {
    notifications.value = notifs;
    unreadCount.value = notificationService.getUnreadCount();
  });
});

onUnmounted(() => {
  notificationService.stopPolling();
});
```

- [ ] **Step 2: 替换header-actions区域**

将原来的：
```html
<div class="header-actions">
  <span class="user-name">{{ username }}</span>
  <button class="logout-btn" @click="handleLogout">退出</button>
</div>
```

替换为：
```html
<div class="header-actions">
  <div class="notification-bell" @click.stop="showNotifications = !showNotifications">
    <span class="bell-icon">🔔</span>
    <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
    <div v-if="showNotifications" class="notification-dropdown">
      <div class="notification-header">消息中心</div>
      <div v-for="n in notifications" :key="n.id" class="notification-item" :class="{ unread: !n.read }" @click="notificationService.markAsRead(n.id)">
        <span class="notification-type">{{ {system:'系统',approval:'审批',security:'安全'}[n.type] }}</span>
        <span class="notification-title">{{ n.title }}</span>
        <span class="notification-time">{{ n.time }}</span>
      </div>
      <div v-if="!notifications.length" class="notification-empty">暂无消息</div>
    </div>
  </div>
  <div class="user-menu" @click.stop="showUserMenu = !showUserMenu">
    <div class="avatar-circle">{{ username?.charAt(0) || 'A' }}</div>
    <span class="user-name">{{ username }}</span>
    <span class="menu-arrow">▼</span>
    <div v-if="showUserMenu" class="user-dropdown">
      <a class="dropdown-item" @click="$router.push('/admin/profile')">📋 个人信息</a>
      <a class="dropdown-item" @click="showPasswordDialog = true">🔑 修改密码</a>
      <a class="dropdown-item" @click="$router.push('/admin/settings')">⚙️ 系统设置</a>
      <a class="dropdown-item" @click="$router.push('/admin/logs')">📝 我的操作日志</a>
      <a class="dropdown-item" href="https://help.example.com" target="_blank">📖 帮助文档</a>
      <div class="dropdown-divider"></div>
      <a class="dropdown-item logout-item" @click="confirmLogout">🚪 退出登录</a>
    </div>
  </div>
</div>
```

- [ ] **Step 3: 添加修改密码弹窗**

在 `</div>` (admin-main结束)后、`</div>` (admin-layout结束)前添加：

```html
<!-- 修改密码弹窗 -->
<div class="modal-overlay" v-if="showPasswordDialog" @click.self="showPasswordDialog = false">
  <div class="modal-content">
    <h3>修改密码</h3>
    <input type="password" v-model="newPassword" placeholder="新密码" />
    <input type="password" v-model="confirmPassword" placeholder="确认密码" />
    <div class="modal-actions">
      <button @click="showPasswordDialog = false">取消</button>
      <button @click="changePassword">确认</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: 添加退出确认和修改密码方法**

在 `handleLogout` 函数后添加：

```typescript
function confirmLogout() {
  if (confirm('确定要退出登录吗？')) {
    handleLogout();
  }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) {
    alert('两次密码不一致');
    return;
  }
  try {
    const auth = (window as any).__VTJ_AUTH__;
    await auth.apiFetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: newPassword.value })
    });
    alert('密码修改成功');
    showPasswordDialog.value = false;
    newPassword.value = '';
    confirmPassword.value = '';
  } catch (e) {
    alert('密码修改失败');
  }
}
```

- [ ] **Step 5: 添加CSS样式**

在 `<style scoped>` 末尾添加：

```css
/* 用户菜单 */
.user-menu { position: relative; cursor: pointer; display: flex; align-items: center; gap: 8px; }
.avatar-circle { width: 32px; height: 32px; border-radius: 50%; background: #C41E3A; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.menu-arrow { font-size: 10px; color: #999; }
.user-dropdown { position: absolute; top: 100%; right: 0; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.15); min-width: 180px; z-index: 1000; padding: 8px 0; }
.dropdown-item { display: block; padding: 10px 16px; color: #333; text-decoration: none; cursor: pointer; font-size: 14px; }
.dropdown-item:hover { background: #f5f7fa; }
.logout-item { color: #C41E3A; }
.dropdown-divider { height: 1px; background: #e8e8e8; margin: 4px 0; }

/* 通知铃铛 */
.notification-bell { position: relative; cursor: pointer; padding: 8px; }
.bell-icon { font-size: 18px; }
.badge { position: absolute; top: 2px; right: 2px; background: #C41E3A; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 10px; }
.notification-dropdown { position: absolute; top: 100%; right: 0; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.15); width: 300px; z-index: 1000; }
.notification-header { padding: 12px 16px; font-weight: 600; border-bottom: 1px solid #e8e8e8; }
.notification-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; display: flex; align-items: center; gap: 8px; }
.notification-item:hover { background: #f5f7fa; }
.notification-item.unread { background: #f0f9eb; }
.notification-type { font-size: 12px; padding: 2px 6px; border-radius: 4px; background: #e8e8e8; }
.notification-title { flex: 1; font-size: 13px; }
.notification-time { font-size: 12px; color: #999; }
.notification-empty { padding: 20px; text-align: center; color: #999; }

/* 密码弹窗 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 400px; }
.modal-content h3 { margin: 0 0 16px; color: #1A3C6D; }
.modal-content input { width: 100%; padding: 10px; border: 1px solid #d9d9d9; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.modal-actions button { padding: 8px 16px; border-radius: 6px; border: 1px solid #d9d9d9; cursor: pointer; }
.modal-actions button:last-child { background: #1A3C6D; color: #fff; border-color: #1A3C6D; }
```

- [ ] **Step 6: 提交**

```bash
git add src/layouts/AdminLayout.vue
git commit -m "feat: add avatar dropdown menu with notifications and password dialog"
```

---

## Task 3: Dashboard真实数据对接

**Files:**
- Modify: `.vtj/vue/admin_dashboard.vue`

- [ ] **Step 1: 替换趋势图硬编码数据**

找到 `trendInstance.setOption` 中的 `data` 数组，替换为：

```typescript
// 替换前: data:[12,19,15,22,18,25,21]
// 替换后:
data: data.weekly_trend?.active_counts || []
```

同时替换 xAxis data：
```typescript
// 替换前: Array.from({length:7},(_,i)=>{...})
// 替换后:
data: data.weekly_trend?.dates || []
```

- [ ] **Step 2: 替换饼图硬编码数据**

找到 `pieInstance.setOption` 中的 `data` 数组，替换为：

```typescript
// 替换前: [{value:350,name:'行测',...},{value:280,name:'申论',...},{value:180,name:'公专',...}]
// 替换后:
data: (data.subject_distribution || []).map((item: any) => ({
  name: item.subject,
  value: item.count,
  itemStyle: { color: { '行测': '#1A3C6D', '申论': '#C41E3A', '公专': '#E6A23C' }[item.subject] || '#999' }
}))
```

- [ ] **Step 3: 添加待审批卡片**

在 `cards.value` 数组中添加第5张卡片：

```typescript
{ label: '待审批试卷', value: String(data.stats?.pending_approval_papers ?? '--'), icon: '📝', route: '/admin/papers', change: '' }
```

- [ ] **Step 4: 修复系统状态栏**

将硬编码的系统状态改为：
```html
<div class="system-status">
  <span class="status-item">🟢 系统状态：正常运行</span>
  <span class="status-item" v-if="diskUsage > 0">💿 磁盘：{{ diskUsage }}%</span>
</div>
```

- [ ] **Step 5: 提交**

```bash
git add .vtj/vue/admin_dashboard.vue
git commit -m "feat: integrate real dashboard data from backend API"
```

---

## Task 4: 题库管理表格增强

**Files:**
- Modify: `.vtj/vue/admin_questions.vue`

- [ ] **Step 1: 添加stripPromoText函数**

在 `setup()` 内添加：

```typescript
function stripPromoText(text: string): string {
  if (!text) return '';
  return text
    .replace(/来源[:：].*$/gm, '')
    .replace(/\[图片\]/g, '')
    .replace(/<[^>]+>/g, '')
    .trim();
}
```

- [ ] **Step 2: 添加题型徽章样式函数**

```typescript
function typeBadgeClass(typeName: string): string {
  const map: Record<string, string> = {
    '单选题': 'type-single',
    '多选题': 'type-multi',
    '论述题': 'type-essay',
    '写作题': 'type-writing'
  };
  return map[typeName] || 'type-default';
}

function difficultyStars(level: number): string {
  return '⭐'.repeat(Math.min(level || 1, 5));
}
```

- [ ] **Step 3: 更新表格列（template部分）**

将表格头从：
```html
<th>科目</th><th>题干</th><th>审核状态</th>
```

改为：
```html
<th>科目</th><th>题干摘要</th><th>题型</th><th>难度</th><th>审核状态</th>
```

- [ ] **Step 4: 更新表格body（template部分）**

将题干列从：
```html
<td>{{ q.question_content?.substring(0,60) }}...</td>
```

改为：
```html
<td class="question-summary">{{ stripPromoText(q.question_content)?.substring(0,80) }}...</td>
<td><span class="type-badge" :class="typeBadgeClass(q.type_name)">{{ q.type_name }}</span></td>
<td>{{ difficultyStars(q.difficulty) }}</td>
```

- [ ] **Step 5: 添加CSS样式**

在 `<style scoped>` 末尾添加：

```css
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.type-single { background: #e6f7ff; color: #1890ff; }
.type-multi { background: #fff7e6; color: #fa8c16; }
.type-essay { background: #fff1f0; color: #f5222d; }
.type-writing { background: #f6ffed; color: #52c41a; }
.type-default { background: #f5f5f5; color: #999; }
.question-summary { max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
```

- [ ] **Step 6: 提交**

```bash
git add .vtj/vue/admin_questions.vue
git commit -m "feat: enhance question table with type badge and difficulty stars"
```

---

## Task 5: 其他模块补全

**Files:**
- Modify: `.vtj/vue/admin_users.vue`
- Modify: `.vtj/vue/admin_backup.vue`
- Modify: `.vtj/vue/admin_logs.vue`

- [ ] **Step 1: admin_users批量删除实现**

找到 `batchDelete` 函数，替换TODO为：

```typescript
async function batchDelete() {
  if (!selectedUsers.value.length) { alert('请先选择用户'); return; }
  if (!confirm(`确定删除 ${selectedUsers.value.length} 个用户？`)) return;
  const auth = (window as any).__VTJ_AUTH__;
  await auth.apiFetch('/api/admin/users/batch', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: selectedUsers.value })
  });
  selectedUsers.value = [];
  load();
}
```

- [ ] **Step 2: admin_backup统计加载**

找到 `load()` 函数，在 `items.value = d.items || [];` 后添加：

```typescript
try {
  const statsRes = await auth().apiFetch('/api/admin/backup/stats');
  const statsData = await statsRes.json();
  if (statsData.success) {
    dbSize.value = statsData.db_size || '--';
    backupSize.value = statsData.backup_size || '--';
    autoBackup.value = statsData.auto_backup ?? true;
  }
} catch (e) { /* 统计接口可选 */ }
```

- [ ] **Step 3: admin_logs导出实现**

找到 `exportLogs` 函数，替换TODO为：

```typescript
function exportLogs() {
  const auth = (window as any).__VTJ_AUTH__;
  const params = new URLSearchParams();
  if (dateRange.value?.[0]) params.append('start_date', dateRange.value[0]);
  if (dateRange.value?.[1]) params.append('end_date', dateRange.value[1]);
  window.open(auth.apiBaseUrl + '/api/admin/logs/export?' + params.toString());
}
```

- [ ] **Step 4: 提交**

```bash
git add .vtj/vue/admin_users.vue .vtj/vue/admin_backup.vue .vtj/vue/admin_logs.vue
git commit -m "feat: implement batch delete, backup stats, and log export"
```

---

## Task 6: DSL同步

- [ ] **Step 1: 同步所有修改的页面**

```bash
# 通过VTJ MCP工具执行同步
vtj_sync_vue_to_dsl id=admin_dashboard
vtj_sync_vue_to_dsl id=admin_questions
vtj_sync_vue_to_dsl id=admin_users
vtj_sync_vue_to_dsl id=admin_backup
vtj_sync_vue_to_dsl id=admin_logs
vtj_sync_vue_to_dsl id=admin_permissions
vtj_sync_vue_to_dsl id=admin_settings
vtj_sync_vue_to_dsl id=paper_approval
```

- [ ] **Step 2: 验证DSL一致性**

```bash
vtj_check_consistency
```

- [ ] **Step 3: 提交**

```bash
git add .vtj/files/*.json
git commit -m "chore: sync DSL files after admin module optimization"
```

---

## Task 7: 最终验证

- [ ] **Step 1: 检查无硬编码残留**

```bash
grep -rn "\[12,19,15" .vtj/vue/ || echo "No hardcoded trend data found"
grep -rn "350.*行测" .vtj/vue/ || echo "No hardcoded pie data found"
```

- [ ] **Step 2: 检查路由完整性**

确认 `src/router/index.ts` 中 admin 路由包含所有8个子路由

- [ ] **Step 3: 检查AdminLayout导航项**

确认 navItems 数组包含8个菜单项，与路由匹配
