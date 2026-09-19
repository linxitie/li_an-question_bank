# 学生端「我的」功能模块细节优化方案

> 版本：v2.0 · 日期：2026-09-16 · 分支：feat/gold-purchase
> 覆盖：头像编辑、成就勋章标识、手机端完善。经用户审批后实施。
> 重要说明：当前成就体系已扩展数据模型（Achievement 加了 is_hidden/style_params/tier_times，UserAchievement 加了 tier 档位，另有 BadgeNameBank/Task/Title 模型），但 service/路由/前端均未接入，属半成品。本方案基于此真实现状设计。

---

## 一、头像编辑（三端统一）

### 1.1 现状与问题

| 端 | 现状 |
|---|---|
| 后端 | `SysUser.avatar` 字段已存在；`ProfileUpdateForm` 有 `avatar`（仅 URL 文本）；**学生端无头像上传接口**（仅教师端 `POST /api/teacher/profile/avatar` 有）；`/uploads` 静态挂载已存在 |
| 桌面 | `profile.vue` 编辑弹窗只有 手机号/邮箱/性别/学院/班级，**无头像项** |
| 手机/平板 | 头像为硬编码 `UserFilled` 图标，**无编辑入口** |

### 1.2 方案

**后端**（`auth.py` 新增 `POST /api/auth/avatar`，参考 teacher.py 已有实现）：
1. 安全校验：扩展名白名单（jpg/jpeg/png/gif/webp）+ 大小 ≤2MB
2. UUID 重命名（防路径穿越/覆盖），存 `uploads/avatars/`
3. `current_user.avatar = /uploads/avatars/{filename}`，`db.commit()`
4. `Depends(get_current_user)` 鉴权

**前端**（三端）：
- 桌面 `profile.vue`：编辑弹窗顶部加头像区（当前头像 + 点击上传 + 实时回显）
- 手机 `mobile_profile.vue` / 平板 `tablet_profile.vue`：用户卡头像可点击上传
- 头像展示：`avatar` 有值 → `<img :src="avatar">`；无值 → 默认 `UserFilled` 图标
- 上传：`<input type="file" accept="image/*">` → `FormData` 上传 → 回显 + Toast

---

## 二、成就勋章标识增强

### 2.1 现状与问题

- 后端 `achievements.py` 返回数据**不含 `tier`（档位）/`style_params`（视觉）/`is_hidden`（隐藏）/`tier_times`（升档阈值）**，仅返回旧字段
- `achievements.vue`：`.ach-card.earned` 仅 1px 淡金边框，**无明确"已获得"标识**；未获得与已获得视觉区分度低
- `profile.vue` 成就区块：仅显示"已获得 N 枚勋章"文字，**不展示具体勋章**

### 2.2 方案

**后端**（`achievements.py` 补返回字段）：
- `list_achievements`：每项补 `tier`（已获得档位，未获得为 0）、`is_hidden`、`style_params`、`tier_times`
- `earned_achievements`：补 `tier`、`obtained_at`

**前端**（`achievements.vue` + `profile.vue`）：
1. **已获得标识**：右上角金色「✓ 已获得」角标 + 勋章彩色高亮；未获得整体置灰（`filter: grayscale`）
2. **档位视觉**（tier 1-5）：铜 #b87333 / 银 #c0c0c0 / 金 #ffd700 / 铂金 #e5e4e2 / 钻石 #b9f2ff，边框+角标颜色随档位变化
3. **隐藏成就**（`is_hidden=1`）：显示剪影（❓ 灰盾），不展示具体条件/名称
4. **profile.vue 成就区块**：横向展示已获得勋章图标（含档位色）+ 数量 + 「查看全部」

---

## 三、手机端「我的」模块完善

### 3.1 错题本（错题复习 + 分类 + 斩题）

**现状**：`mobile_wrong_questions.vue` 仅「列表 + 展开答案/解析 + 移出错题」，缺以下能力（后端接口均已就绪）：

| 缺失能力 | 后端接口（已存在） |
|---|---|
| 错题分类筛选 | `GET /api/wrong-questions/subcategories` |
| 错题复习（重练） | `GET /api/wrong-questions/review/queue`（mode）+ `POST /api/wrong-questions/review/submit` |
| 斩题 | `PUT /api/wrong-questions/{id}/chop` |
| 斩题列表 | `GET /api/wrong-questions/zhanti/list` |

**方案**（重构 `mobile_wrong_questions.vue`）：
1. 顶部分类筛选 tabs（全部/行测/申论/公专 + 子科目），数据源 `/subcategories`
2. 列表项加「斩题」按钮（调 `/chop`）
3. 「错题复习」入口：选模式（knowledge/time/subject/mixed）→ `/review/queue` 取队列 → 逐题作答 → `/review/submit` 提交判分 + 自动斩题提示
4. 「斩题记录」tab：`/zhanti/list` + 剩余天数

### 3.2 手机端成就页适配

**现状**：`/achievements` 桌面页 `ach-grid: repeat(3, 1fr)`，手机窄屏勋章卡片扁长。

**方案**：`achievements.vue` 加响应式（media query）：
- 桌面 >1024px：3 列；平板 768-1024px：2 列；手机 <768px：2 列、勋章图标缩小、文字纵向（图标上、名称下）

### 3.3 收藏页完善

**现状**：`mobile_favorites.vue` 仅「列表 + 取消收藏」，无分类。

**方案**：加科目分类 tabs。

### 3.4 其他布局/功能排查

| 问题 | 方案 |
|---|---|
| `feedback.vue`/`help.vue` 桌面 2 列手机端未适配 | 加 media query，手机单列 |
| 手机「我的」页头像无法编辑 | 见第一节 |
| 「历史记录」跳 `/profile` 手机端不适配 | 指向手机练习记录页（或占位提示） |

---

## 四、质量门禁（写代码前逐条自查）

1. **VTJ 版本一致**：改 `.vue` script 后同步 `.vtj/files/*.json` 的 methods/state + `__VERSION__`（仅 VTJ 生成页；`src/views/*` 手写页无此约束）
2. **后端完整**：新接口字段与 schema 一致；头像上传校验完备
3. **安全**：头像上传白名单 + 大小限制 + UUID 重命名；所有接口 `get_current_user`
4. **运维**：头像独立 `uploads/avatars/`；旧头像不删除；错误日志完整
5. **不影响其他模块**：仅改「我的」相关文件 + 学生端头像接口，不动教师/管理员已有逻辑；不改 achievement_service 判定逻辑（除非用户要求五档升级）

---

## 五、开放问题（需确认）

1. **五档徽章升级**：`tier_times`/`style_params` 是半成品（模型有、逻辑无）。本轮是否只做「档位展示 + 已获得标识」（tier 默认 1 铜），还是**一并实现五档升级逻辑**（achievement_service 判定改造 + seed 填充 tier_times/style_params）？建议**本轮只做展示**，升级逻辑作为下一阶段。
2. **手机错题复习页**：新建独立复习页 `mobile_wrong_review.vue`（推荐）还是复用现有答题页？
3. **头像大小**：默认 2MB 还是 5MB？
4. **「历史记录」**：本轮新建 `mobile_history.vue` 还是占位提示？
5. **收藏分类维度**：科目 or 子科目？

---

> 本方案已通过自审：无 TBD、无内部矛盾；§五 开放问题需确认后锁定，随后实施。
