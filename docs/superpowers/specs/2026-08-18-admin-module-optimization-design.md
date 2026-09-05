# 管理员端各模块优化 — 设计规格文档

**日期**: 2026-08-18  
**版本**: v1.0  
**状态**: 待审批

## 1. 背景与目标

当前管理员端8个页面已完成基础重构（移除侧边栏、骨架屏、AdminLayout统一布局），但存在以下问题：

1. **Dashboard硬编码假数据**：趋势图和饼图使用写死的模拟数组，未消费后端真实API数据
2. **头像下拉菜单未实现**：AdminLayout只有用户名文本+退出按钮，缺少设计文档2.7要求的全局头像下拉菜单
3. **题库管理表格信息不完整**：只显示题干前60字符，缺少题型、难度等关键列，与教师端对齐不足
4. **多处功能为TODO占位**：批量操作、导出、统计加载等

**目标**：在现有重构基础上，实现设计方案的完整预期效果。

---

## 2. 模块设计

### 2.1 Dashboard 真实数据对接

#### 2.1.1 趋势图数据

**当前问题**：第121行硬编码 `data:[12,19,15,22,18,25,21]`

**设计方案**：
- 消费后端 `weekly_trend` 字段
- 使用 `weekly_trend.dates` 作为x轴标签
- 使用 `weekly_trend.active_counts` 作为y轴数据
- 图表配置项动态生成，不硬编码

```typescript
// 替换硬编码
trendInstance.setOption({
  xAxis: { data: data.weekly_trend.dates },
  series: [{ data: data.weekly_trend.active_counts }]
});
```

#### 2.1.2 饼图数据

**当前问题**：第130行硬编码 `[{value:350,name:'行测'},{value:280,name:'申论'},{value:180,name:'公专'}]`

**设计方案**：
- 消费后端 `subject_distribution` 数组
- 动态映射 `{name: item.subject, value: item.count}`
- 颜色预定义映射表

```typescript
const colorMap = { '行测': '#1A3C6D', '申论': '#C41E3A', '公专': '#E6A23C' };
pieInstance.setOption({
  series: [{
    data: data.subject_distribution.map(item => ({
      name: item.subject,
      value: item.count,
      itemStyle: { color: colorMap[item.subject] || '#999' }
    }))
  }]
});
```

#### 2.1.3 统计卡片

**当前问题**：缺少"待审批"卡片，磁盘使用永远显示0%

**设计方案**：
- 新增第5张卡片"待审批试卷"，使用 `stats.pending_approval_papers`
- 移除"磁盘使用"卡片（后端不支持）
- 保留4张核心卡片：总用户、总题目、总试卷、今日活跃

#### 2.1.4 系统状态栏

**当前问题**：全硬编码文本，🔴Redis写"正常"是bug

**设计方案**：
- 轮询 `/api/admin/health` 接口获取真实状态
- 如后端无健康检查接口，改为静态展示但标注"状态检查功能开发中"
- 移除Redis磁盘等不确定状态项，只显示"系统运行中"

---

### 2.2 题库管理表格增强

#### 2.2.1 表格列对齐教师端

**当前问题**：只显示复选框、ID、科目、题干、审核状态、操作

**设计方案**（与教师端teacher_questions.vue一致）：

| 列名 | 内容 | 说明 |
|------|------|------|
| 复选框 | 批量选择 | 已实现 |
| ID | `q.id` | 升序排列，已实现 |
| 题干摘要 | `stripPromoText(q.question_content).substring(0,80)` | 需清理推广文本 |
| 科目 | `subjectName(q.subject_id)` | 已实现 |
| 题型 | `q.type_name` 彩色徽章 | 新增 |
| 难度 | `q.difficulty` 星级显示 | 新增 |
| 审核状态 | 状态标签 | 已实现 |
| 操作 | 详情/通过/驳回 | 已实现 |

#### 2.2.2 题干清理逻辑

复用教师端的 `stripPromoText` 函数，清理以下内容：
- 推广来源文本（"来源：xxx"）
- 图片标记（`[图片]`）
- HTML标签残留

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

#### 2.2.3 题型徽章样式

与教师端一致的4色徽章：
- 单选题：蓝色 `#1A3C6D`
- 多选题：橙色 `#E6A23C`
- 论述题：红色 `#C41E3A`
- 写作题：绿色 `#52c41a`

#### 2.2.4 难度星级显示

复用教师端的星级逻辑：
- 1星：⭐
- 2星：⭐⭐
- 3星：⭐⭐⭐
- 4星：⭐⭐⭐⭐
- 5星：⭐⭐⭐⭐⭐

---

### 2.3 头像下拉菜单（2.7全局组件优化）

#### 2.3.1 组件结构

**位置**：`src/layouts/AdminLayout.vue`

**当前问题**：只有 `<span class="user-name">{{ username }}</span>` + `<button class="logout-btn">退出</button>`

**设计方案**：

```
┌─────────────────────────────────────┐
│  AdminLayout Header                │
│  ┌─────────────────────────────┐   │
│  │ [头像] 张明（管理员） ▼      │   │
│  │ ┌───────────────────────┐   │   │
│  │ │ 📋 个人信息            │   │   │
│  │ │ 🔑 修改密码            │   │   │
│  │ │ ⚙️ 系统设置            │   │   │
│  │ │ 📝 我的操作日志        │   │   │
│  │ │ 📖 帮助文档            │   │   │
│  │ │ 🔔 消息中心 (3)        │   │   │
│  │ │ ─────────────────     │   │   │
│  │ │ 🚪 退出登录            │   │   │
│  │ └───────────────────────┘   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

#### 2.3.2 头像显示

- **无真实头像时**：用户名首字母圆形背景（取名字第一个字）
- **有真实头像时**：`<img>` 显示
- 首字母颜色：根据用户名hash生成固定颜色

```vue
<div class="avatar-circle" v-if="!avatarUrl">
  {{ username?.charAt(0) || 'A' }}
</div>
<img v-else :src="avatarUrl" class="avatar-img" />
```

#### 2.3.3 下拉菜单项

| 菜单项 | 图标 | 行为 | 路由 |
|--------|------|------|------|
| 个人信息 | 📋 | 跳转 | `/admin/profile`（新增路由） |
| 修改密码 | 🔑 | 弹窗 | 不跳转，显示修改密码弹窗 |
| 系统设置 | ⚙️ | 跳转 | `/admin/settings` |
| 我的操作日志 | 📝 | 跳转 | `/admin/logs` |
| 帮助文档 | 📖 | 外部链接 | `_blank` 打开帮助文档URL |
| 消息中心 | 🔔 | 下拉子菜单 | 显示最近5条通知 |
| 退出登录 | 🚪 | 确认弹窗 | 清理存储 → 跳转登录页 |

#### 2.3.4 退出确认弹窗

**当前问题**：直接 `router.push('/login')` 无确认

**设计方案**：
1. 点击"退出登录"显示确认弹窗
2. 确认后清理：localStorage、sessionStorage、cookie
3. 调用后端登出API（如有）
4. 跳转到 `/login`

```typescript
async function confirmLogout() {
  try {
    await auth().apiFetch('/api/auth/logout', { method: 'POST' });
  } catch (e) { /* 忽略 */ }
  localStorage.clear();
  sessionStorage.clear();
  router.push('/login');
}
```

---

### 2.4 消息中心动态UI设计

#### 2.4.1 NotificationService 服务层

**位置**：`src/services/NotificationService.ts`

**核心接口**：
```typescript
interface Notification {
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
  private pollingInterval = 30000; // 30秒轮询
  private timer: any = null;

  startPolling() { /* 启动轮询 */ }
  stopPolling() { /* 停止轮询 */ }
  subscribe(listener: Function) { /* 订阅更新 */ }
  getUnreadCount(): number { /* 获取未读数 */ }
  markAsRead(id: number) { /* 标记已读 */ }
}
```

#### 2.4.2 Mock数据生成（过渡方案）

**当前状态**：后端无消息API

**设计方案**：
- 服务层内置Mock数据生成器
- 模拟3种类型通知：系统通知、审批提醒、安全警告
- 生成逻辑：随机时间、随机内容、50%已读/未读
- **关键**：Mock数据由服务层生成，UI组件不硬编码任何消息内容

```typescript
function generateMockNotifications(): Notification[] {
  const types = ['system', 'approval', 'security'];
  const templates = {
    system: ['系统已更新至最新版本', '数据库备份完成', '新功能已上线'],
    approval: ['3份试卷待审批', '本周已通过12份试卷', '有新提交的试卷'],
    security: ['检测到异常登录', '密码修改成功', '登录IP变更提醒']
  };
  return Array.from({ length: 5 }, (_, i) => ({
    id: i + 1,
    type: types[Math.floor(Math.random() * 3)],
    title: templates[types[Math.floor(Math.random() * 3)]][Math.floor(Math.random() * 3)],
    content: '',
    time: `${Math.floor(Math.random() * 24)}小时前`,
    read: Math.random() > 0.5
  }));
}
```

#### 2.4.3 API适配器模式

```typescript
// 当前：Mock数据
async function fetchNotifications(): Promise<Notification[]> {
  // 后端API就绪后，替换为真实调用
  // const res = await auth().apiFetch('/api/notifications');
  // return res.json();
  return generateMockNotifications();
}
```

**渐进增强**：后端API就绪后，只需修改 `fetchNotifications` 函数，UI层无需改动。

---

### 2.5 其他模块补全

#### 2.5.1 admin_users 批量操作

**当前问题**：`batchImport`、`exportUsers`、`batchEnable`、`batchDisable`、`batchDelete` 全是 TODO

**设计方案**：
- `batchDelete`：调用 `DELETE /api/admin/users/batch` 传入选中ID列表
- `batchEnable/Disable`：调用 `PUT /api/admin/users/batch-status` 传入 `{ids, status}`
- `exportUsers`：调用 `GET /api/admin/users/export` 下载CSV
- `batchImport`：显示文件上传弹窗，调用 `POST /api/admin/users/import`

#### 2.5.2 admin_backup 统计加载

**当前问题**：`dbSize`、`backupSize`、`autoBackup` 永远显示占位符

**设计方案**：
- 在 `load()` 函数中额外请求 `/api/admin/backup/stats`
- 填充 `dbSize`、`backupSize`、`autoBackup` 真实值
- 如后端无统计接口，移除统计卡片，只保留备份列表

#### 2.5.3 admin_logs 导出功能

**当前问题**：`exportLogs` 是 console.log

**设计方案**：
- 调用 `GET /api/admin/logs/export` 下载CSV
- 前端触发下载：`window.open(url)`

#### 2.5.4 admin_settings 选项卡补全

**当前问题**：只有基本/安全/考试/通知4个选项卡，缺功能开关/公告管理/敏感词

**设计方案**：
- 新增"功能开关"选项卡：控制注册开关、验证码开关等
- 新增"公告管理"选项卡：管理首页公告内容
- 新增"敏感词"选项卡：配置敏感词过滤规则
- 如后端无对应API，先做UI占位，数据为空

#### 2.5.5 paper_approval 审计统计

**当前问题**：缺少"今日待审批/本周通过率/平均处理时长"

**设计方案**：
- 在页面顶部添加统计卡片区域
- 调用 `/api/admin/approval/stats` 获取统计数据
- 显示：今日待审批数、本周通过率、平均处理时长

---

## 3. 实施优先级

| 优先级 | 模块 | 理由 |
|--------|------|------|
| P0 | Dashboard真实数据对接 | 硬编码假数据严重影响可信度 |
| P0 | 头像下拉菜单 | 设计方案2.7核心功能 |
| P1 | 题库管理表格增强 | 与教师端对齐，用户体验 |
| P2 | 消息中心动态UI | 需要服务层架构设计 |
| P2 | 其他模块补全 | TODO占位功能 |

---

## 4. 验证标准

1. Dashboard图表显示后端真实数据，无硬编码数组
2. 头像下拉菜单包含7个菜单项，退出有确认弹窗
3. 题库表格显示题型徽章和难度星级，题干经清理后显示
4. 消息中心badge显示未读数，数据由服务层驱动
5. 所有TODO占位功能有实际API调用
6. DSL一致性检查通过（admin页面全部consistent）

---

## 5. 风险与注意事项

1. **后端API依赖**：部分功能（消息中心、统计加载）需要后端支持，需确认接口就绪时间
2. **VTJ规范**：所有页面修改后需执行 `vtj_sync_vue_to_dsl`
3. **LSP错误**：`$vtj` 别名的LSP错误是预期行为，Vite运行时解析正常
4. **缓存清理**：部署前需清除Vite缓存并重启开发服务器
