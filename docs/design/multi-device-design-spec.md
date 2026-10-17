# 砺安题库 - 多端适配与二维码登录系统设计规范

> **版本**: v1.0  
> **日期**: 2026-09-07  
> **状态**: 设计确认完成，准备实施

---

## 目录

1. [项目概述](#1-项目概述)
2. [总体架构设计](#2-总体架构设计)
3. [二维码扫码登录系统](#3-二维码扫码登录系统)
4. [三端数据同步机制](#4-三端数据同步机制)
5. [平板端页面设计](#5-平板端页面设计)
6. [手机端页面设计](#6-手机端页面设计)
7. [视觉设计系统](#7-视觉设计系统)
8. [后端接口变更清单](#8-后端接口变更清单)
9. [VTJ设计器工作流](#9-vtj设计器工作流)
10. [实施计划](#10-实施计划)

---

## 1. 项目概述

### 1.1 项目背景

砺安题库是一个面向警务考试的在线学习平台，提供题库练习、模拟考试、成绩分析、招考信息等功能。现有系统支持PC端学生端、教师端和管理后台。

### 1.2 设计目标

1. **多端适配**：基于现有PC端功能，扩展平板端和手机端支持
2. **二维码扫码登录**：将PC端"下载客户端"模块替换为二维码扫码登录功能
3. **数据同步**：实现三端数据实时同步，保证用户在任何设备上的学习进度一致
4. **功能对齐**：保持PC端所有功能模块风格样式、功能实现、界面交互为主，不得随意修改成其他风格

### 1.3 核心原则

- **PC端是主体**：手机端、平板端的所有功能模块风格样式、功能实现、界面交互均以PC端为主
- **功能同步确认**：
  - 平板端和手机端都不需要"模拟上机"和"关于砺安题库"
  - 平板端保留"考试日历"和"招考信息"
  - 手机端按设计方案精简展示
- **二维码扫码登录**：采用纯前端二维码生成 + 后端验证（UUID + Redis，无第三方SDK）
- **数据同步**：需分析后端API现状和缺口，设计完整同步逻辑
- **VTJ前端规范**：必须严格遵照 `CLAUDE.md\vtj.md` 和 `vtj-mcp-server` 文件夹的前端编写规则
- **代码编写前需多角度思考**：安全性、可维护性、前端展示效果、后端字段/路由/接口完整性、VTJ版本一致性
- **最终方案需用户同意后才能实施**

---

## 2. 总体架构设计

### 2.1 三端分离架构

```
linxitie.policy-exam-bank/          # PC端（现有，保持不变）
linxitie.policy-exam-bank-tablet/   # 平板端（新建）
linxitie.policy-exam-bank-mobile/   # 手机端（新建）

packages/                           # 共享核心层（monorepo或npm）
├── shared-types/       # TypeScript类型定义
├── shared-api/         # 统一API客户端（基于fetch + window.__VTJ_AUTH__）
├── shared-store/       # Pinia stores（auth, questions, practice, user等）
├── shared-utils/       # 工具函数、常量、验证
└── design-tokens/      # CSS变量、Tailwind配置、组件主题
```

### 2.2 共享核心层

| 包名 | 职责 | 复用范围 |
|------|------|----------|
| `@linxi/shared-types` | 后端API响应类型、实体类型、DTO定义 | 三端共用 |
| `@linxi/shared-api` | 统一API调用层、请求/响应拦截器、错误处理 | 三端共用 |
| `@linxi/shared-store` | Pinia状态管理（用户、题目、练习记录等） | 三端共用 |
| `@linxi/shared-utils` | 工具函数、常量、验证逻辑、日期处理 | 三端共用 |
| `@linxi/design-tokens` | 设计令牌（颜色、间距、圆角、字体） | 三端共用 |

### 2.3 部署策略

- **三端独立部署**：独立域名/子路径
- **共享后端**：三端共用同一FastAPI后端服务
- **统一认证**：JWT + 刷新令牌体系
- **域名规划**：
  - PC端：`exam.linxi.com`
  - 平板端：`tablet.exam.linxi.com`
  - 手机端：`m.exam.linxi.com`

---

## 3. 二维码扫码登录系统

### 3.1 后端接口设计

#### 3.1.1 接口清单

| 方法 | 路径 | 说明 | 请求参数 | 响应格式 |
|------|------|------|----------|----------|
| POST | `/api/auth/qrcode/generate` | PC端生成二维码 | 无（从请求头提取设备信息） | `{uuid, qr_url, expires_in, qr_image_base64}` |
| GET | `/api/auth/qrcode/{uuid}/info` | 移动端获取PC端信息 | 无 | `{device, location, login_time}` |
| POST | `/api/auth/qrcode/{uuid}/confirm` | 移动端确认登录 | `{token: string}` | `{success, redirect_url}` |
| GET | `/api/auth/qrcode/{uuid}/status` | PC端长轮询检测状态 | 无 | `{status: 'pending'|'confirmed'|'expired', token?}` |

#### 3.1.2 Redis数据结构

```
# 二维码状态（TTL 60秒）
qr:{uuid} = {
    status: 'pending',
    pc_device_info: {browser, os, ip, location},
    created_at: timestamp
}

# 确认登录信息（TTL 5分钟）
qr:{uuid}:confirmed = {
    user_id: number,
    token: string,
    confirmed_at: timestamp
}
```

#### 3.1.3 安全机制

1. **二维码60秒强制过期**：防重放攻击
2. **同一UUID仅允许确认一次**：防重复登录
3. **异地登录检测**：IP变化时推送通知
4. **设备管理**：支持"我的→设备管理"查看/移除设备

### 3.2 PC端登录页集成

#### 3.2.1 Tab切换设计

在现有登录页新增Tab切换：

```
[账号密码登录] | [验证码登录] | [扫码登录]
```

#### 3.2.2 扫码登录页设计

- **大尺寸二维码**：280px × 280px
- **倒计时显示**：60秒倒计时，剩余10秒变红
- **刷新按钮**：倒计时结束后显示刷新按钮
- **状态提示**：
  - 初始：`请使用砺安题库APP扫描二维码登录`
  - 已扫码：`已扫码，请在手机上确认登录`（绿色对勾动画）
  - 确认中：`正在验证，请稍候...`
  - 过期：`二维码已过期，请刷新`

#### 3.2.3 长轮询实现

```javascript
// PC端轮询逻辑
const pollStatus = async (uuid) => {
  const interval = setInterval(async () => {
    const res = await fetch(`/api/auth/qrcode/${uuid}/status`)
    const data = await res.json()
    
    if (data.status === 'confirmed') {
      clearInterval(interval)
      // 保存token并跳转首页
      localStorage.setItem('token', data.token)
      router.push('/')
    } else if (data.status === 'expired') {
      clearInterval(interval)
      // 显示刷新按钮
    }
  }, 1500) // 每1.5秒轮询
}
```

### 3.3 移动端确认页设计

#### 3.3.1 全屏模态弹窗

扫码后弹出全屏确认弹窗，显示：

- **设备信息**：设备型号、浏览器类型
- **地理位置**：IP归属地（通过高德API获取）
- **登录时间**：当前时间
- **操作按钮**：
  - `[取消]` - 次要按钮（灰色）
  - `[确认登录]` - 主要按钮（深蓝 #1A365D）

#### 3.3.2 确认流程

```
用户扫码 → 检测到请求 → 弹出全屏确认弹窗
    ↓
显示PC端设备信息
    ↓
用户点击[确认登录]
    ↓
调用 /confirm 接口携带当前用户token
    ↓
PC端自动登录跳转首页
```

---

## 4. 三端数据同步机制

### 4.1 核心原则

**后端单一数据源，三端实时API查询，无本地持久化冲突**

### 4.2 同步策略矩阵

| 数据类型 | 同步方式 | 实时性 | 缓存策略 | 冲突处理 |
|---------|---------|--------|---------|----------|
| 用户信息/Token | 登录时获取 | 实时 | 内存+localStorage | 以最新登录为准 |
| 题目/试卷数据 | API按需查询 | 实时 | 无缓存(或5min) | 服务端权威 |
| 答题进度 | 每题提交即时同步 | 实时 | 无 | 乐观锁(version) |
| 错题集/收藏/笔记/标记 | 增删改即时API | 实时 | 本地乐观更新 | 最后写入胜出 |
| 练习记录/成绩分析 | API查询聚合 | 近实时 | 5min缓存 | 服务端聚合 |
| 签到/目标/金币 | API触发即时 | 实时 | 无 | 服务端幂等 |

### 4.3 多设备在线管理

#### 4.3.1 SysUser模型扩展

```python
class SysUser(Base):
    # 现有字段...
    device_sessions = Column(JSON, default=list)  # 新增：设备会话列表
```

#### 4.3.2 设备会话数据结构

```json
{
  "device_sessions": [
    {
      "device_id": "uuid",
      "platform": "pc|tablet|mobile",
      "browser": "Chrome 120",
      "os": "Windows 11",
      "ip": "192.168.1.100",
      "location": "北京市",
      "token_hash": "sha256...",
      "last_active": "2026-09-07T10:30:00Z",
      "is_current": false
    }
  ]
}
```

#### 4.3.3 设备管理规则

- **登录时注册设备会话**：每次登录更新`last_active`
- **心跳更新**：定期更新`last_active`字段
- **超时清理**：超过30天无活跃自动清理
- **设备限制**：单用户最多3设备同时在线（PC+平板+手机）

### 4.4 设备管理API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/devices/` | 获取设备列表 |
| DELETE | `/api/auth/devices/{device_id}` | 移除指定设备 |
| POST | `/api/auth/devices/revoke-all` | 强制下线所有设备 |

### 4.5 WebSocket实时同步（可选增强）

#### 4.5.1 连接认证

```javascript
// 前端连接
const ws = new WebSocket('wss://exam.linxi.com/ws/sync?token=xxx')
```

#### 4.5.2 事件类型

| 事件 | 说明 | 数据格式 |
|------|------|----------|
| `sync:practice` | 练习进度同步 | `{type, question_id, is_correct}` |
| `sync:favorite` | 收藏同步 | `{type, question_id, favorited}` |
| `sync:note` | 笔记同步 | `{type, question_id, note_text}` |
| `sync:wrong_question` | 错题同步 | `{type, question_id, wrong_count}` |
| `sync:checkin` | 签到同步 | `{type, streak, coins}` |

#### 4.5.3 降级方案

无WebSocket时，依赖以下方式触发刷新：
- 页面切换/下拉刷新
- 定时轮询（5分钟间隔）
- 手动刷新按钮

### 4.6 离线支持策略

1. **Service Worker缓存**：静态资源 + 已加载题目数据
2. **离线答题队列**：离线答题本地队列，联网后批量提交
3. **冲突处理**：离线期间的操作，联网后用服务端版本覆盖
4. **本地缓存**：关键只读数据（错题、收藏、笔记）本地IndexedDB缓存

---

## 5. 平板端页面设计

### 5.1 布局模板

- **顶部导航栏**：60px高度
- **底部Tab栏**：56px高度
- **主内容区**：栅格8列，双列/混合布局
- **断点**：768px - 1024px

### 5.2 底部Tab栏

```
[首页 🏠] | [题库 📚] | [练习 ✏️] | [论坛 💬] | [我的 👤]
```

### 5.3 页面清单

#### 5.3.1 首页

- 签到卡片
- 个人目标卡片
- 倒计时组件
- 每日金句
- 每日新闻
- 学习趋势图
- 待办事项
- 快捷入口（双列布局）

#### 5.3.2 题库

- 搜索栏
- 四大入口：快速练习/历年试卷/智能组卷/联考小智
- 学习进度雷达图
- 子科目网格
- 热门推荐

#### 5.3.3 答题页

- 左侧题目区域（60%宽度）
- 右侧答题卡/笔记区域（40%宽度）
- 横屏自动双栏显示

#### 5.3.4 其他页面

- 历年试卷、智能组卷、联考小智、快速练习：完整保留PC功能
- 练习记录、错题集、收藏、笔记、成绩分析（完整图表）
- 备考资料、论坛、考试日历、招考信息

#### 5.3.5 我的

- 个人信息
- 学习数据
- 成绩分析入口
- 备考资料入口
- 设置（含设备管理、关于砺安题库）

### 5.4 交互差异

- **触控目标**：≥44px
- **悬停态→点击态**
- **侧边栏→抽屉抽屉**
- **表格横向滚动**
- **卡片堆叠布局**
- **支持左右滑动切换Tab**

---

## 6. 手机端页面设计

### 6.1 布局模板

- **顶部导航栏**：48px高度（含返回/标题/操作）
- **底部Tab栏**：52px高度
- **主内容区**：栅格4列，单列布局
- **断点**：<768px

### 6.2 底部Tab栏

```
[首页 🏠] | [题库 📚] | [练习 ✏️] | [论坛 💬] | [我的 👤]
```

### 6.3 页面清单（精简展示）

**删除功能**：模拟上机、考试日历、招考信息、关于砺安题库

#### 6.3.1 首页

- 签到卡片
- 个人目标（折叠显示）
- 倒计时
- 每日金句
- 每日新闻（列表）
- 学习趋势简化图
- 四统计卡片（2×2布局）
- 快捷入口

#### 6.3.2 题库

- 搜索栏
- 四大入口卡片（2×2）
- 我的进度条
- 快捷入口（错题/收藏/笔记/记录）

#### 6.3.3 快速练习/历年试卷/智能组卷/联考小智

- 完整功能，单列卡片流

#### 6.3.4 答题页

- 全屏题目显示
- 底部固定操作栏
- 答题卡/笔记通过模态/Sheet展开

#### 6.3.5 练习页面

- 科目切换Tabs
- 知识点树形列表（可展开）
- 点击进入练习模式选择（随机/专项/错题重练）

#### 6.3.6 其他页面

- 练习记录、错题集、收藏、笔记
- 成绩分析（简化图表）
- 备考资料、论坛

#### 6.3.7 我的

- 个人信息
- 学习数据概览
- 成绩分析/备考资料入口
- 设置（个人/通知/设备管理/关于砺安题库/退出登录）

### 6.4 未实现功能占位

所有PC端有但移动端暂未开发的模块，显示：

> "该功能模块正在设计中，敬请期待！"

### 6.5 交互亮点

- **单手操作区**：底部50%
- **下拉刷新**
- **左滑返回**
- **骨架屏加载**
- **虚拟滚动长列表**
- **横屏答题**：自动切换双栏（题目+答题卡）
- **手势支持**：左滑返回、右滑前进（答题）、双击回顶部

---

## 7. 视觉设计系统

### 7.1 设计令牌（CSS变量）

```css
:root {
  /* ========== 色彩系统 ========== */
  /* 主色 - 深蓝色（权威、专业、稳重） */
  --color-primary: #1A365D;
  --color-primary-hover: #152C4A;
  --color-primary-active: #0F2035;
  
  /* 强调色 - 金色（激励、收获） */
  --color-accent: #D4A843;
  --color-accent-hover: #C49A35;
  --color-accent-active: #B08C2A;
  
  /* 状态色 */
  --color-success: #52C41A;
  --color-warning: #FAAD14;
  --color-error: #FF4D4F;
  --color-info: #1890FF;
  
  /* 业务色 */
  --color-xingce: #3B82F6;         /* 行测标识 - 蓝色 */
  --color-shenlun: #10B981;        /* 申论标识 - 绿色 */
  --color-gongzhuan: #F59E0B;      /* 公专标识 - 橙色 */
  
  /* 中性色 */
  --color-text-primary: #1F2937;
  --color-text-secondary: #6B7280;
  --color-text-tertiary: #9CA3AF;
  --color-border: #E5E7EB;
  --color-divider: #F3F4F6;
  
  /* ========== 背景系统 ========== */
  /* 页面背景 */
  --bg-primary: #F0F2F5;           /* PC/平板背景 */
  --bg-secondary: #F5F7FA;         /* 手机背景 */
  --bg-tertiary: #FAFBFC;          /* 最浅背景 */
  
  /* 组件背景 */
  --bg-card: #FFFFFF;              /* 卡片背景 */
  --bg-card-hover: #FAFAFA;        /* 卡片悬停背景 */
  --bg-card-active: #F5F5F5;       /* 卡片点击背景 */
  
  /* ========== 间距系统 ========== */
  /* 基础单位 4px */
  --space-unit: 4px;
  --space-xs: 8px;
  --space-sm: 12px;
  --space-md: 16px;
  --space-lg: 20px;
  --space-xl: 24px;
  --space-2xl: 32px;
  --space-3xl: 40px;
  --space-4xl: 48px;
  
  /* ========== 圆角系统 ========== */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-2xl: 20px;
  --radius-full: 9999px;           /* 完全圆形 */
  
  /* ========== 字体系统 ========== */
  --font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-size-xs: 12px;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-base-tablet: 15px;
  --font-size-base-mobile: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 18px;
  --font-size-2xl: 20px;
  --font-size-3xl: 24px;
  --font-size-4xl: 30px;
  --font-size-5xl: 36px;
  
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.6;
  
  /* ========== 阴影系统 ========== */
  --shadow-xs: 0 1px 2px rgba(26, 43, 95, 0.02);
  --shadow-light: 0 1px 4px rgba(26, 43, 95, 0.04);
  --shadow-medium: 0 4px 16px rgba(26, 43, 95, 0.1);
  --shadow-heavy: 0 8px 28px rgba(26, 43, 95, 0.12);
  --shadow-xl: 0 12px 40px rgba(26, 43, 95, 0.15);
  
  /* ========== 动画系统 ========== */
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);
  
  /* ========== 触控目标 ========== */
  --touch-target-min: 44px;
  
  /* ========== 断点 ========== */
  --breakpoint-mobile: 768px;
  --breakpoint-tablet: 1024px;
  --breakpoint-desktop: 1280px;
}
```

### 7.2 组件库规范

#### 7.2.1 Button 按钮

| 变体 | 颜色 | 用途 |
|------|------|------|
| Primary | 深蓝 #1A365D | 主要操作（确认、提交） |
| Secondary | 白色边框 | 次要操作（取消、返回） |
| Ghost | 透明背景 | 文字链接、辅助操作 |
| Danger | 红色 #FF4D4F | 删除、危险操作 |

尺寸：Large(48px) / Default(40px) / Small(32px)

#### 7.2.2 Card 卡片

- 统一阴影：`--shadow-medium`
- 统一圆角：`--radius-lg`
- 内边距：`--space-lg`
- Hover态：`--bg-card-hover` + `--shadow-heavy`
- Active态：`--bg-card-active`

#### 7.2.3 Input/Search 输入框

- 统一高度：40px（PC/平板）/ 44px（移动端）
- 焦点态：主色边框 + 浅蓝背景
- 错误态：红色边框 + 错误提示

#### 7.2.4 Tab/Nav 标签

- 底部Tab：图标 + 文字
- 激活态：主色 + 加粗
- 未激活态：次色 + 常规

#### 7.2.5 Modal/Sheet/Drawer 弹窗

- 统一动画：300ms
- 背景遮罩：半透明黑色
- 关闭手势：点击遮罩/滑动

#### 7.2.6 Skeleton 骨架屏

- 卡片骨架
- 列表骨架
- 图表骨架

#### 7.2.7 Empty State 空状态

- 插画 + 标题 + 描述 + 行动按钮
- "正在设计中"专用变体：`该功能模块正在设计中，敬请期待！`

### 7.3 三端差异

**仅在布局与密度上有差异**：颜色、圆角、阴影、字体族完全一致

| 属性 | PC端 | 平板端 | 手机端 |
|------|------|--------|--------|
| 栅格列数 | 12列 | 8列 | 4列 |
| 字号基准 | 14px | 15px | 14px |
| 内边距 | 24px | 20px | 16px |
| 卡片圆角 | 12px | 12px | 16px |
| 触控目标 | 32px | 44px | 44px |

---

## 8. 后端接口变更清单

### 8.1 新增接口

#### 8.1.1 二维码扫码登录模块

```
POST   /api/auth/qrcode/generate          # PC端生成二维码
GET    /api/auth/qrcode/{uuid}/info       # 移动端获取PC端信息
POST   /api/auth/qrcode/{uuid}/confirm    # 移动端确认登录
GET    /api/auth/qrcode/{uuid}/status     # PC端长轮询检测状态
```

#### 8.1.2 设备管理模块

```
GET    /api/auth/devices/                 # 获取设备列表
DELETE /api/auth/devices/{device_id}      # 移除指定设备
POST   /api/auth/devices/revoke-all       # 强制下线所有设备
```

### 8.2 现有接口复用（无需变更）

| 模块 | 接口路径 | 说明 |
|------|----------|------|
| 题目 | `/api/questions/*` | 题目CRUD、搜索、分类 |
| 试卷 | `/api/papers/*` | 试卷管理、生成、导出 |
| 考试 | `/api/exams/*` | 模拟考试、联考 |
| 练习 | `/api/practice/*` | 快速练习、专项练习 |
| 统计 | `/api/stats/*` | 学习统计、成绩分析 |
| 错题 | `/api/wrong-questions/*` | 错题集、重练 |
| 笔记 | `/api/notes/*` | 题目笔记 |
| 收藏 | `/api/collection/*` | 题目收藏 |
| 论坛 | `/api/forum/*` | 帖子、评论、点赞 |
| 新闻 | `/api/news/*` | 每日新闻 |
| 招考 | `/api/recruitment/*` | 招考信息 |
| 日历 | `/api/calendar/*` | 考试日历 |
| 资料 | `/api/materials/*` | 备考资料 |
| 金句 | `/api/quotes/*` | 每日金句 |
| 目标 | `/api/goals/*` | 学习目标 |

### 8.3 SysUser模型变更

```python
class SysUser(Base):
    # 现有字段
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    real_name = Column(String(50), nullable=True)
    role = Column(String(20), default='student', nullable=False)
    is_disabled = Column(Boolean, default=False)
    disabled_reason = Column(String(500), nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    password_reset_token = Column(String(200), nullable=True)
    password_reset_expire = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey('sys_user.user_id'), nullable=True)
    school_id = Column(Integer, ForeignKey('school.id'), nullable=True)
    
    # 新增字段
    device_sessions = Column(JSON, default=list)  # 设备会话列表
```

### 8.4 迁移脚本

```python
# alembic migration
def upgrade():
    op.add_column('sys_user', 
        sa.Column('device_sessions', sa.JSON(), nullable=True, default=list))

def downgrade():
    op.drop_column('sys_user', 'device_sessions')
```

---

## 9. VTJ设计器工作流

### 9.1 VTJ项目创建流程

1. **在VTJ设计器中创建平板/手机项目**
   - 项目名：`linxitie.policy-exam-bank-tablet` / `linxitie.policy-exam-bank-mobile`
   - 平台：Web
   - 模板：Blank

2. **导入共享设计令牌**
   - 将CSS变量注入全局样式
   - 配置Tailwind主题（可选）

3. **复用PC端区块**
   - 通用区块：NavBar、SignInCard、GoalCard、CountdownTimer、QuoteBanner、ExamCalendar、RecruitmentInfo、StudyMaterials、AppNavigation、Footer等
   - 业务区块：按端适配布局后重新设计

4. **创建页面**
   - 在设计器中拖拽布局
   - 配置响应式类名（`.hide-on-mobile`, `.show-on-tablet`等）
   - 出码生成`.vue`文件

5. **Claude Code补充业务逻辑**
   - 调用共享store/API
   - 实现交互逻辑
   - 同步更新`.vtj/files/*.json`的methods/state/lifeCycles

### 9.2 共享区块复用策略

| 区块类型 | 复用方式 | 说明 |
|----------|----------|------|
| 通用区块（导航栏、卡片类） | 直接复用`.vtj/files/*.json` | 无需修改 |
| 业务页面区块 | 按端适配布局后重新设计 | 需要调整布局 |
| 响应式可见性 | 使用类名控制显示/隐藏 | `.hide-on-mobile`, `.show-on-tablet` |

### 9.3 VTJ开发规范

**必须严格遵照以下文件**：
- `CLAUDE.md\vtj.md` - VTJ前端开发规范
- `vtj-mcp-server` 文件夹 - VTJ MCP Server规范

**核心规则**：
- 所有页面必须通过VTJ设计器生成DSL JSON
- DSL JSON必须包含完整的methods/state/lifeCycles
- 业务逻辑通过<script>标签补充
- 组件引用必须使用正确的路径格式

---

## 10. 实施计划

### 10.1 P0阶段（第1-2周）：核心基础设施

| 任务 | 负责人 | 产出 |
|------|--------|------|
| 后端新增二维码登录模块 | 后端开发 | auth_qrcode.py, Redis集成 |
| 后端新增设备管理接口 | 后端开发 | devices.py, API文档 |
| SysUser.device_sessions字段迁移 | 后端开发 | alembic migration |
| 共享核心层初始化 | 前端开发 | shared-types, shared-api, design-tokens |
| PC端登录页VTJ新增"扫码登录"Tab | 前端开发 | login.vue更新 |
| 二维码展示/轮询逻辑 | 前端开发 | qrcode.js组件 |
| 移动端扫码确认页（全屏模态） | 前端开发 | qr-confirm.vue |

### 10.2 P0阶段（第2-3周）：三端VTJ项目创建

| 任务 | 负责人 | 产出 |
|------|--------|------|
| 创建平板端VTJ项目 | 前端开发 | linxitie.policy-exam-bank-tablet |
| 导入设计令牌、复用通用区块 | 前端开发 | 基础布局、通用组件 |
| 创建手机端VTJ项目 | 前端开发 | linxitie.policy-exam-bank-mobile |
| 平板端：首页、题库、答题页、我的 | 前端开发 | 核心页面 |
| 手机端：首页、题库、答题页、练习页、我的 | 前端开发 | 核心页面 |

### 10.3 P1阶段（第3-4周）：核心业务页面

| 任务 | 负责人 | 产出 |
|------|--------|------|
| 平板端：历年试卷、智能组卷、联考小智、快速练习 | 前端开发 | 练习模块 |
| 平板端：练习记录、错题集、收藏、笔记、成绩分析 | 前端开发 | 数据模块 |
| 平板端：备考资料、论坛、考试日历、招考信息 | 前端开发 | 资讯模块 |
| 手机端：快速练习、历年试卷、智能组卷、联考小智 | 前端开发 | 练习模块 |
| 手机端：练习页面（含知识点下钻） | 前端开发 | 深度练习 |
| 手机端：练习记录、错题集、收藏、笔记、成绩分析 | 前端开发 | 数据模块 |
| 手机端：备考资料、论坛 | 前端开发 | 资讯模块 |
| 未实现模块占位组件 | 前端开发 | "正在设计中"空状态 |

### 10.4 P2阶段（第4-5周）：体验打磨与同步增强

| 任务 | 负责人 | 产出 |
|------|--------|------|
| 触控交互优化 | 前端开发 | 手势、反馈、骨架屏 |
| 虚拟滚动长列表 | 前端开发 | 性能优化 |
| 横竖屏适配 | 前端开发 | 响应式布局 |
| 离线缓存 | 前端开发 | Service Worker |
| WebSocket实时同步（可选） | 全栈开发 | ws/sync模块 |
| 多端联调 | 测试 | 兼容性测试 |
| 性能测试 | 测试 | Lighthouse报告 |
| 异常场景覆盖 | 测试 | 异常用例 |

### 10.5 P3阶段（第5-6周）：验收与部署

| 任务 | 负责人 | 产出 |
|------|--------|------|
| 全功能回归测试 | 测试 | 测试报告 |
| 三端数据同步验证 | 测试 | 同步测试用例 |
| 独立部署配置 | 运维 | 域名/子路径 |
| HTTPS配置 | 运维 | SSL证书 |
| 文档整理 | 全员 | 技术文档 |
| 运维手册 | 运维 | 运维指南 |
| 监控告警 | 运维 | 监控配置 |

### 10.6 里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| M1：核心基础设施完成 | 第2周末 | 后端API + 共享层 + PC端扫码登录 |
| M2：三端VTJ项目创建完成 | 第3周末 | 平板/手机端基础框架 + 核心页面 |
| M3：核心业务页面完成 | 第4周末 | 三端全功能页面 |
| M4：体验优化完成 | 第5周末 | 交互优化 + 性能优化 |
| M5：验收部署完成 | 第6周末 | 全功能上线 + 监控 |

### 10.7 人力资源

| 角色 | 人数 | 职责 |
|------|------|------|
| 前端开发（VTJ） | 2人 | 平板/手机端页面开发 |
| 后端开发 | 1人 | 二维码登录、设备管理、API |
| 测试 | 1人 | 多端测试、数据同步验证 |

**总工期：6周**

---

## 附录A：术语表

| 术语 | 说明 |
|------|------|
| VTJ | Vue低代码开发框架 |
| DSL | 领域特定语言，VTJ的页面描述格式 |
| JWT | JSON Web Token，身份认证令牌 |
| Redis | 内存数据库，用于二维码状态存储 |
| PWA | 渐进式Web应用 |
| Service Worker | 浏览器后台线程，用于离线缓存 |
| WebSocket | 全双工通信协议 |
| Pinia | Vue 3状态管理库 |

---

## 附录B：参考文件

| 文件 | 路径 | 说明 |
|------|------|------|
| VTJ开发规范 | `CLAUDE.md\vtj.md` | VTJ前端开发规范 |
| VTJ MCP Server | `vtj-mcp-server/` | VTJ MCP Server规范 |
| PC端设计文档 | `solve_problems_files/手机端、平板端设计方案.md` | 原始设计方案 |
| 后端模型 | `backend/app/models/models.py` | 数据库模型定义 |
| 后端认证 | `backend/app/api/v1/auth.py` | 认证API |
| 后端安全 | `backend/app/core/security.py` | JWT/权限管理 |
| VTJ路由 | `.vtj/router.js` | 前端路由配置 |

---

**文档结束**
