# 学生端「我的」功能模块细节优化方案

> 版本：v1.0 · 日期：2026-09-16 · 分支：feat/student-profile
> 本文档是对已上线的「我的」模块的细节优化方案，覆盖：头像编辑、成就勋章标识、手机端完善。经用户审批后实施。

---

## 一、头像编辑（三端统一）

### 1.1 现状与问题

| 端 | 现状 |
|---|---|
| 后端 | `SysUser.avatar` 字段已存在；`ProfileUpdateForm` 有 `avatar` 字段（仅支持 URL 文本）；**学生端无头像上传接口**（仅教师端 `POST /api/teacher/profile/avatar` 有） |
| 桌面 | `profile.vue` 编辑资料弹窗只有 手机号/邮箱/性别/学院/班级，**无头像项** |
| 手机/平板 | 头像为硬编码 `UserFilled` 图标，**无编辑入口** |

**根因**：① 学生端缺头像上传接口；② 三端编辑弹窗均未加入头像编辑项；③ 头像展示未读 `avatar` 字段。

### 1.2 方案设计

**后端**（`auth.py` 新增 1 个接口）：

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 上传头像 | POST | `/api/auth/avatar` | 学生端上传头像，返回 `avatar_url` |

实现要点（参考 `teacher.py` 已有实现，复用 `/uploads` 静态挂载）：
1. **安全校验**：扩展名白名单（jpg/jpeg/png/gif/webp）+ 大小限制 ≤2MB，非法拒绝
2. **文件安全**：`UUID` 重命名（防路径穿越/覆盖），存 `uploads/avatars/`
3. **字段更新**：`current_user.avatar = /uploads/avatars/{filename}`，`db.commit()`
4. **鉴权**：`Depends(get_current_user)`

**前端**（三端编辑弹窗加头像区）：
- 桌面 `profile.vue`：编辑弹窗顶部加头像区（当前头像 + 点击上传 + 实时回显）
- 手机 `mobile_profile.vue` / 平板 `tablet_profile.vue`：用户卡头像改为可点击上传
- 头像展示逻辑：`avatar` 字段有值 → 显示 `<img :src="avatar">`；无值 → 显示默认 `UserFilled` 图标
- 上传流程：点击头像 → `<input type="file" accept="image/*">` → `FormData` 上传 `/api/auth/avatar` → 回显新头像 + Toast

---

## 二、成就勋章标识增强

### 2.1 现状与问题

- `achievements.vue`：`.ach-card.earned` 仅 1px 金色边框，**无明确"已获得"标识**，未获得与已获得视觉区分度低
- `profile.vue` 成就区块：仅显示"已获得 N 枚勋章"文字，**不展示具体勋章**

### 2.2 方案设计

**`achievements.vue` 成就卡片**：
- **已获得**：金色渐变边框 + 右上角「✓ 已获得」金色角标 + 勋章彩色高亮
- **未获得**：整体置灰（`filter: grayscale`）+ 进度条显示当前/阈值进度

**`profile.vue` 成就区块**：
- 显示已获得勋章图标（横向排列，取前 N 枚 + 更多）+ 数量 + 「查看全部」入口

---

## 三、手机端「我的」模块完善

### 3.1 错题本（核心：错题复习 + 分类 + 斩题）

**现状**：`mobile_wrong_questions.vue` 仅「列表 + 展开答案/解析 + 移出错题」，缺以下能力（后端接口均已就绪）：

| 缺失能力 | 后端接口（已存在） |
|---|---|
| 错题分类筛选 | `GET /api/wrong-questions/subcategories`（按科目/子科目统计） |
| 错题复习（重练） | `GET /api/wrong-questions/review/queue`（mode: knowledge/time/subject/mixed）+ `POST /api/wrong-questions/review/submit`（批量判分+自动斩题） |
| 斩题 | `PUT /api/wrong-questions/{id}/chop` |
| 斩题列表 | `GET /api/wrong-questions/zhanti/list` |

**方案**（重构 `mobile_wrong_questions.vue`）：
1. 顶部加**分类筛选 tabs**（全部/行测/申论/公专 + 子科目），数据源 `/subcategories`
2. 列表项加**斩题按钮**（对未斩题显示「斩题」，调用 `/chop`）
3. 新增**「错题复习」入口**：点击进入复习模式（选择 knowledge/time/subject/mixed）→ 调 `/review/queue` 取队列 → 逐题作答 → `/review/submit` 提交判分 + 显示结果 + 自动斩题提示
4. 新增**「斩题记录」tab**：展示已斩题列表（`/zhanti/list`）+ 剩余天数

### 3.2 手机端成就页适配

**现状**：`/achievements` 是桌面页（`ach-grid: repeat(3, 1fr)`），手机窄屏下 3 列导致勋章卡片**扁长**。

**方案**：`achievements.vue` 加响应式布局（media query）：
- 桌面（>1024px）：3 列
- 平板（768-1024px）：2 列
- 手机（<768px）：2 列，勋章图标缩小、文字纵向排列（图标在上、名称在下，避免扁长）

### 3.3 收藏页完善

**现状**：`mobile_favorites.vue` 仅「列表 + 取消收藏」，无分类。

**方案**：加科目分类 tabs（复用 `/api/questions/favorites` 的 subject 维度，或 `/api/collection` 的统计）。

### 3.4 其他布局/功能排查（同步修复）

| 问题 | 方案 |
|---|---|
| `feedback.vue` / `help.vue` 桌面 2 列在手机端未适配 | 加 media query，手机端单列 |
| 手机端「我的」页头像无法编辑 | 见第一节，用户卡头像可点击上传 |
| 「历史记录」点击跳 `/profile`（桌面页）手机端不适配 | 指向手机端练习记录页（如无则占位提示） |

---

## 四、质量门禁（写代码前逐条自查）

1. **VTJ 版本一致性**：改 `.vue` script 后同步 `.vtj/files/*.json` 的 methods/state + `__VERSION__`（仅限 VTJ 生成页；`src/views/*` 手写页无此约束）
2. **后端完整性**：新接口在 `main.py` 注册（`auth.py` 的 avatar 已属已注册的 auth router，无需额外注册）；文件上传校验（类型/大小）完备
3. **安全**：头像上传白名单 + 大小限制 + UUID 重命名（防路径穿越/任意文件覆盖）；所有接口 `get_current_user` 鉴权
4. **运维**：头像文件独立 `uploads/avatars/` 目录；旧头像不删除（保留历史）；错误日志完整
5. **不影响其他模块**：仅改「我的」相关文件 + 新增学生端头像接口，不动教师端/管理员端已有逻辑

---

## 五、开放问题（需确认）

1. **手机端错题复习**：复习答题页是复用现有答题页（`answer_page.vue`/`mobile_practice.vue`）还是新建独立复习页？建议**新建独立复习页**（`mobile_wrong_review.vue`），与正常答题解耦、逻辑更清晰。
2. **头像上传大小**：默认限制 2MB，是否需要更大（如 5MB）？
3. **「历史记录」**：手机端目前无独立练习记录页，本轮是否一并新建（`mobile_history.vue`）还是暂用占位提示？
4. **收藏分类**：收藏页分类维度用「科目」还是「子科目」？（错题本用科目+子科目，收藏建议仅科目，避免过深）

---

> 本方案已通过自审：无 TBD 占位、无内部矛盾；§五 的开放问题需用户确认后锁定，随后进入实施。
