# 学生端「我的」功能模块设计规格（Spec）

> 版本：v1.0 · 日期：2026-09-16 · 分支：feat/student-profile
> 本文档是实施范围契约，所有实现以本文档 + 真实代码基线的映射为准，取代 `solve_problems_files/学生端"我的"功能模块建设方案.md`（v2.0）中与真实代码不符的部分。

---

## 1. 背景与目标

砺安题库学生端目前「我的」功能在**三端割裂且数据不真实**：

- 电脑端无独立「我的」页，仅有 `navbar.vue` 里的「个人中心」编辑弹窗。
- 手机/平板端「我的」页已存在，但计数（错题/收藏/历史/笔记）与成就徽章、学习趋势、考试日历**全部硬编码**；部分菜单路由（`/achievements`、`/downloads`、`/feedback`、`/help`、`/settings`）在路由表中**不存在，点击 404**。
- 金币仅 `SysUser.total_coins` 单字段 + `CoinRecord` 表，但**无 coins 路由**，签到 `coin_reward` 硬编码 0，`gold_purchase.vue` 全 mock。
- **无成就体系**（零基础）。

**目标**：在真实代码基线上，建成三端统一、数据真实、可运维的「我的」个人中心，覆盖个人资料、学习数据、金币、成就（45 项）、学习等级、设备管理、设置。

---

## 2. 范围

### 2.1 目标（In Scope）

1. **桌面端**：新增 `/profile` 页（三栏布局）；改造 `navbar.vue` 头像点击从「个人中心弹窗」改为进入「我的」页，并新增「我的」导航入口。
2. **平板端**：增强 `tablet_profile.vue`，学习数据/趋势/成就/考试日历接真实 API。
3. **手机端**：增强 `mobile_profile.vue`，计数接真实 API，修复 6 个 404 路由。
4. **金币闭环**：新增 coins 路由（余额 + 流水）；签到真实发币（基础 5 币/天 + 连续 7 天额外 20）。
5. **成就体系**：45 项成就全量实现（目录表 + 用户成就表 + 判定服务 + 6 类触发器埋点 + 独立成就页 + 解锁弹窗）。
6. **学习等级**：成长值模型 + 幂次阈值曲线（10 级）。
7. **设备管理**：复用 `/api/auth/devices`，补 UA 品牌识别。
8. **设置**：通知/隐私偏好（JSON 字段 + 接口）。

### 2.2 非目标（Out of Scope）

- 金币充值支付、金币购商城真实扣币（`gold_purchase.vue` 本次只做「余额 + 流水」接线，商城兑换后置）。
- 成就的 WebSocket 实时推送（本次用「接口轮询 + 行为后即时判定返回」兜底，WebSocket 后置）。
- 头像文件上传（本次仅支持 `avatar` URL 字段编辑，文件上传后置）。
- 密码找回/重置令牌流程（已有，不在本次范围）。

---

## 3. 现状盘点（真实代码基线）

### 3.1 前端三端现状

| 端 | 文件 | 现状 | 本次动作 |
|---|---|---|---|
| 桌面 | `.vtj/vue/navbar.vue` | 深藏蓝+红导航，头像点击弹「个人中心」编辑弹窗（`/api/auth/profile` GET/PUT） | 改为进入 `/profile` 页 |
| 桌面 | 无 | 无独立「我的」页 | 新增 `profile.vue`（三栏） |
| 平板 | `.vtj/vue/tablet_profile.vue` | 三栏，计数/趋势/日历/徽章硬编码，仅 stats 走 API | 接真实 API |
| 手机 | `.vtj/vue/mobile_profile.vue` | 计数硬编码，菜单 6 路由 404 | 接真实 API + 修复路由 |

### 3.2 后端现状

| 模块 | 现状 |
|---|---|
| 用户资料 | `auth.py`：`GET/PUT /api/auth/profile`、`POST /api/auth/change-password` |
| 学习统计 | `stats.py`：`GET /api/stats/`（totalQuestions/accuracyRate/streak/totalStudyHours 等）、`/auto-checkin`、`/weekly`、`/practice-trend` |
| 设备 | `devices.py`：`GET /api/auth/devices`、`DELETE /api/auth/devices/{id}`、`POST /api/auth/devices/revoke-all`，基于 `SysUser.device_sessions`(JSON) |
| 金币 | `SysUser.total_coins`(单字段) + `CoinRecord` 表；**无 coins 路由**（`main.py` 注释 `# coins TODO 待创建`）；签到 `coin_reward` 硬编码 0 |
| 成就 | **无任何表/模型/服务** |
| 签到 | `DailyCheckin` 有 `coin_reward/streak_bonus` 字段但未使用 |

### 3.3 设计令牌（桌面一致性基准）

```
导航栏背景：linear-gradient(135deg, #1a2b5f 0%, #1e3470 40%, #1a2b5f 100%)，高 64px，sticky
品牌红：linear-gradient(135deg, #c41e3a, #e8384f)
菜单激活下划线：linear-gradient(90deg, #c41e3a, #ff4d5a)
页面背景：linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%)
卡片：#ffffff，圆角 16–18px，阴影 0 2px 14px rgba(26,43,95,0.05)
主文字：#1a2b5f；次文字：#8a8faa / #8899aa / #5a6488
强调色：红 #c41e3a · 金 #f59e0b · 绿 #10b981 · 蓝 #1890ff · 紫 #8b5cf6
字体：'Noto Sans SC','PingFang SC','Microsoft YaHei'；数字字体 'DIN Alternate'
图标：XIcon(@vtj/ui) + @vtj/icons（少量 emoji）
```

---

## 4. 架构设计

### 4.1 前端架构

- 桌面：`navbar.vue`（改造入口）→ 新增 `profile.vue`（三栏）+ `achievements.vue`（成就页）。
- 平板/手机：在现有 `tablet_profile.vue` / `mobile_profile.vue` 上增强（仅改 `<script>` + 少量 `<style>`；UI 结构变更走 VTJ 设计器或最小化手写，遵守 CLAUDE.md/vtj.md）。
- 所有页面使用 Options API（VTJ 生成页面）或 `<script setup>`（手写页），数据请求走 `window.__VTJ_AUTH__.apiFetch()`。

### 4.2 后端架构

新增两个服务模块 + 一个路由模块：

```
backend/app/
├── api/v1/
│   ├── coins.py           # 新增：金币余额/流水路由
│   ├── achievements.py    # 新增：成就列表/进度/领取路由
│   └── settings.py        # 新增：通知/隐私设置路由（并入 coins 或独立）
├── services/
│   ├── achievement_service.py   # 新增：成就判定/发放（幂等+原子）
│   ├── growth_service.py        # 新增：成长值累加 + 等级计算
│   └── device_service.py        # 新增：UA 品牌识别
└── models/models.py            # 改：新增 Achievement / UserAchievement 表；SysUser 加 growth_points / settings 字段
```

### 4.3 数据流

```
用户行为（答题/签到/斩题/发帖/收藏/笔记）
  → 行为接口（practice/forum/wrong_questions/collection/notes）内联调用 achievement_service.check_and_grant(user_id, trigger_type)
  → 判定满足 → 事务内 [插入 user_achievement(唯一约束) + 更新 total_coins + 写 CoinRecord] + 累加 growth_points
  → 返回 { newly_unlocked: [...] } 供前端弹窗
```

---

## 5. 数据模型

### 5.1 新增表

```sql
-- 成就目录表（静态，启动/迁移时预置 45 行）
CREATE TABLE achievement (
    achievement_id INT PRIMARY KEY AUTO_INCREMENT,
    category       VARCHAR(32)  NOT NULL,          -- 坚持/数量/正确率/错题/社交/综合
    name           VARCHAR(50)  NOT NULL,
    icon           VARCHAR(16)  DEFAULT '',        -- emoji
    condition_desc VARCHAR(200) NOT NULL,          -- 获得条件描述
    reward_coins   INT          DEFAULT 0,
    trigger_type   VARCHAR(32)  NOT NULL,          -- do_question/sign_in/chop/review/post/favorite/note/level/coin
    condition_key  VARCHAR(32)  DEFAULT NULL,      -- 判定条件参数（如 1000 表示累计1000题）
    condition_extra VARCHAR(32) DEFAULT NULL,      -- 附加参数（如正确率 80、时段 8:00）
    sort_order     INT          DEFAULT 0
);

-- 用户成就表（幂等核心：唯一约束）
CREATE TABLE user_achievement (
    id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id        BIGINT NOT NULL,
    achievement_id INT    NOT NULL,
    obtained_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_achievement (user_id, achievement_id)
);
```

`SysUser` 新增字段：
- `growth_points INT DEFAULT 0` — 累计成长值
- `settings JSON DEFAULT NULL` — 通知/隐私偏好（`{"notify_achievement":1,"notify_checkin":1,"privacy_show_stats":1}`）

### 5.2 现有表改动

- 复用 `CoinRecord`（字段已满足流水需求：`coin_change`、`current_balance`、`transaction_type`、`source_type`、`description`）。
- `source_type` 枚举需扩展 `ACHIEVEMENT`（若枚举限制，用现有 `SYSTEM` 兜底并在 `description` 标注来源）。

---

## 6. API 接口设计

### 6.1 复用（不改路径）

| 接口 | 说明 |
|---|---|
| `GET/PUT /api/auth/profile` | 个人资料 |
| `POST /api/auth/change-password` | 改密码 |
| `GET /api/stats/` | 学习数据概览 |
| `GET /api/stats/practice-trend` | 学习趋势 |
| `GET /api/auth/devices` / `DELETE /{id}` / `POST /revoke-all` | 设备管理 |

### 6.2 新增

**金币 `coins.py`（prefix `/api/coins`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/coins/overview` | 余额 + 本月收入/支出 |
| GET | `/api/coins/transactions?page&page_size` | 分页流水 |

**成就 `achievements.py`（prefix `/api/achievements`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/achievements` | 全部 45 项 + 已获得标记 + 未获得进度 |
| GET | `/api/achievements/earned` | 已获得列表 |
| GET | `/api/achievements/progress` | 未获得成就的实时进度 |

**等级（并入 stats 或独立）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/stats/level` | 当前等级 + 成长值 + 进度 |

**设置 `settings.py`（prefix `/api/user/settings`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET / PUT | `/api/user/settings` | 通知/隐私偏好 |

> 说明：原方案 §7 的 `/api/user/*` 路径**废弃**，统一用上表真实路径。

---

## 7. 成就体系（45 项，严格照搬方案 §3.2）

### 7.1 成就完整表

#### 学习坚持类（8 项，trigger = sign_in / daily）

| 名称 | 条件 | 奖励 | 图标 | condition_key |
|---|---|---|---|---|
| 初来乍到 | 首次登录系统 | 10 | 🌱 | first_login |
| 连续学习3天 | 连续3天有学习记录 | 30 | 🔥 | 3 |
| 连续学习7天 | 连续7天有学习记录 | 80 | 🔥 | 7 |
| 连续学习15天 | 连续15天有学习记录 | 150 | 🔥 | 15 |
| 连续学习30天 | 连续30天有学习记录 | 300 | 🔥 | 30 |
| 月度学霸 | 单月学习≥25天 | 200 | 📅 | 25 |
| 早起鸟 | 连续7天8:00前学习 | 50 | 🐦 | 7(时段 08:00 前) |
| 夜猫子 | 连续7天22:00后学习 | 50 | 🦉 | 7(时段 22:00 后) |

#### 做题数量类（10 项，trigger = do_question）

| 名称 | 条件 | 奖励 | 图标 |
|---|---|---|---|
| 初试身手 | 累计做题10道 | 10 | 📝 |
| 小试牛刀 | 累计做题50道 | 20 | 📝 |
| 渐入佳境 | 累计做题100道 | 40 | 📝 |
| 勤学苦练 | 累计做题500道 | 80 | 📝 |
| 千题斩 | 累计做题1,000道 | 150 | ⚔️ |
| 三千题 | 累计做题3,000道 | 300 | ⚔️ |
| 五千题 | 累计做题5,000道 | 500 | ⚔️ |
| 万题王 | 累计做题10,000道 | 1,000 | 👑 |
| 单日百题 | 单日做题100道 | 50 | 🚀 |
| 周做题达人 | 单周做题500道 | 100 | 🏃 |

#### 正确率类（8 项，trigger = do_question）

| 名称 | 条件 | 奖励 | 图标 |
|---|---|---|---|
| 首战告捷 | 首次全部答对 | 20 | ✅ |
| 满分王 | 单次练习全部答对（≥20题） | 50 | 🥉 |
| 精准射手 | 单次练习正确率≥90% | 40 | 🎯 |
| 稳如泰山 | 连续3次练习正确率≥80% | 60 | 🧘 |
| 正确率之星 | 周正确率≥85%（≥100题） | 80 | ⭐ |
| 常胜将军 | 连续10次练习正确率≥80% | 100 | 🏆 |
| 完美主义 | 连续5次练习全部答对 | 150 | 💎 |
| 正确率大师 | 月正确率≥85%（≥500题） | 200 | 👑 |

#### 错题管理类（6 项，trigger = chop / review）

| 名称 | 条件 | 奖励 | 图标 |
|---|---|---|---|
| 直面错误 | 首次查看错题集 | 10 | 👀 |
| 错题复习者 | 完成10道错题重练 | 30 | 🔄 |
| 错题终结者 | 完成50道错题重练 | 80 | 🏅 |
| 斩题新手 | 首次斩题 | 20 | 🎯 |
| 斩题达人 | 累计斩题50道 | 100 | 🎖️ |
| 斩题大师 | 累计斩题200道 | 300 | 👑 |

#### 社交互动类（6 项，trigger = post）

| 名称 | 条件 | 奖励 | 图标 |
|---|---|---|---|
| 初次发声 | 首次发布帖子/评论 | 15 | 💬 |
| 论坛活跃者 | 发布10条帖子/评论 | 50 | 🎖️ |
| 热门楼主 | 单帖获得50个赞 | 80 | 🔥 |
| 获赞达人 | 累计获得100个赞 | 100 | ⭐ |
| 解答高手 | 回答被采纳10次 | 150 | 🏆 |
| 社区领袖 | 发布100条帖子/评论 | 200 | 👑 |

#### 综合成就类（7 项，trigger = 多源）

| 名称 | 条件 | 奖励 | 图标 |
|---|---|---|---|
| 全能选手 | 完成行测/申论/公专各100题 | 150 | 🌟 |
| 三科精通 | 三科正确率均≥75% | 200 | 🎓 |
| 等级达人 | 学习等级达到Lv.10 | 300 | 📈 |
| 金币富翁 | 累计获得10,000金币 | 200 | 💰 |
| 收藏家 | 收藏100道题目 | 100 | ⭐ |
| 笔记达人 | 添加50条学习笔记 | 80 | 📓 |
| 金句收藏家 | 收藏100条金句 | 60 | 📚 |

### 7.2 判定引擎设计

核心函数（同步风格，匹配项目 Session）：

```python
# backend/app/services/achievement_service.py
def check_and_grant(user_id: int, trigger_type: str, db: Session) -> list[dict]:
    """判定并发放成就，返回 newly_unlocked 列表（供前端弹窗）"""
    stats = _gather_stats(user_id, db)               # 聚合当前统计
    obtained_ids = _obtained_ids(user_id, db)        # 已获得
    newly = []
    for ach in _achievements_by_trigger(trigger_type):
        if ach.achievement_id in obtained_ids:
            continue
        if _check_condition(user_id, ach, stats, db):
            _grant(user_id, ach, db)                 # 事务：插入 user_achievement + 加金币 + 写流水 + 加成长值
            newly.append({"achievement_id": ach.achievement_id, "name": ach.name,
                          "reward_coins": ach.reward_coins, "icon": ach.icon})
    return newly
```

`_grant` 内事务关键点：

1. `INSERT user_achievement`（`uk_user_achievement` 唯一约束防重）
2. `UPDATE SysUser.total_coins += reward`（行锁 `with_for_update()` 防并发超发）
3. `INSERT CoinRecord`（`source_type='ACHIEVEMENT'`，`description=f'获得成就：{name}'`）
4. `UPDATE SysUser.growth_points += 15`（成就成长值）
5. `db.commit()`；捕获 `IntegrityError` → `db.rollback()`（并发重复发放被唯一约束拦截）

### 7.3 触发埋点（6 处，内联调用 `check_and_grant`）

| 行为点 | 触发类型 | 埋点位置 |
|---|---|---|
| 答题记录 | `do_question` | `practice.py` `POST /record`、`POST /batch-record`（各题型提交后） |
| 签到 | `sign_in` | `stats.py` `ensure_daily_checkin` / `POST /auto-checkin` 成功后 |
| 斩题 | `chop` | `wrong_questions.py` `PUT /{id}/chop` 成功后 |
| 错题重练 | `review` | `wrong_questions.py` `POST /review/submit` 成功后 |
| 发帖/评论/点赞 | `post` | `forum.py` 发帖/评论/点赞后 |
| 收藏/笔记/金句 | `favorite` / `note` | `collection.py`、`news.py`、`notes.py` 成功后 |

### 7.4 幂等 / 原子性

- **幂等**：`uk_user_achievement(user_id, achievement_id)` 唯一约束，重复触发自动跳过。
- **原子**：成就插入 + 金币 + 流水 + 成长值在同一事务；任一失败整体回滚。
- **可追溯**：每次发放 `logger.info`；金币流水有 `description`。

---

## 8. 学习等级算法

### 8.1 成长值（只增不减）

| 行为 | 成长值 |
|---|---|
| 做对一题 | +2 |
| 做错一题 | +1 |
| 完成一次签到 | +5 |
| 连续签到满 7 天 | +20 |
| 获得一枚成就 | +15 |
| 完成一套试卷/模考 | +10 |

### 8.2 等级阈值

`Lv.n 累计成长值 = round(100 × (n-1)^1.6)`（n=2..10，Lv.1 = 0）

| 等级 | 称号 | 累计成长值 |
|---|---|---|
| Lv.1 | 新手学员 | 0 |
| Lv.2 | 入门学员 | 100 |
| Lv.3 | 进阶学员 | 303 |
| Lv.4 | 勤学学员 | 580 |
| Lv.5 | 专注学员 | 919 |
| Lv.6 | 资深学员 | 1,313 |
| Lv.7 | 优秀学员 | 1,758 |
| Lv.8 | 精英学员 | 2,253 |
| Lv.9 | 学霸 | 2,786 |
| Lv.10 | 砺安大师 | 3,363 |

### 8.3 进度计算

- `等级 = max{n : growth_points ≥ threshold[n]}`
- `进度 = (growth_points - threshold[当前级]) / (threshold[下一级] - threshold[当前级])`
- 满级（≥3363）进度 = 100%

### 8.4 稳定性保障

- 成长值只增不减，每次行为**增量写入** `growth_points`，可全量重算。
- 每日定时任务重算校准（防统计漂移）。
- 历史数据回填脚本：按 `PracticeRecord`（对/错题数）+ `DailyCheckin` 回填存量用户初始 `growth_points`，`--dry-run` → `--apply`。

---

## 9. 三端页面设计

### 9.1 桌面端（新增 `profile.vue`，三栏）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ navbar.vue（深藏蓝+红，头像 → 进入本页）                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ 左栏 280px         │ 中栏自适应                 │ 右栏 320px                    │
│ ┌──────────────┐   │ ┌────────────────────┐   │ ┌────────────────────┐        │
│ │ 个人资料      │   │ │ 学习数据            │   │ │ 成就与激励          │        │
│ │ 头像/姓名/    │   │ │ 总做题 正确率       │   │ │ 已获得 N 枚勋章     │        │
│ │ 学号/班级     │   │ │ 学习时长 完成试卷   │   │ │ [查看全部 →]        │        │
│ │ [编辑资料]    │   │ │ [详细成绩分析 →]    │   │ │ 学习等级 Lv.N +进度 │        │
│ └──────────────┘   │ └────────────────────┘   │ └────────────────────┘        │
│ ┌──────────────┐   │ ┌────────────────────┐   │                                │
│ │ 我的金币      │   │ │ 学习内容管理        │   │                                │
│ │ 余额 + 明细   │   │ │ 练习/错题/收藏/笔记 │   │                                │
│ └──────────────┘   │ └────────────────────┘   │                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ 备考资料（行测/申论/公专） │ 设置（个人/通知/隐私/设备/关于/退出）               │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 严格套用 §3.3 设计令牌（卡片白底 + 深藏蓝文字 + 红色强调）。
- 学习内容管理入口复用已有路由：错题集 `/page/wrong_questions`、收藏 `/page/favorites`、笔记 `/page/notes`、练习记录 `/page/...`（以 router 实际为准）。

### 9.2 平板端（增强 `tablet_profile.vue`）

- 学习数据四卡片（错题/收藏/历史/笔记）接真实计数 API。
- 学习趋势 `weekData` → 接 `/api/stats/practice-trend?days=7`。
- 成就徽章 `badges` → 接 `/api/achievements/earned`。
- 考试日历 → 接 `/api/stats/calendar` 或 `/api/calendar/exams`。

### 9.3 手机端（增强 `mobile_profile.vue`）

- 计数接真实 API：错题 `/api/wrong-questions`、收藏 `/api/collection`、笔记 `/api/notes`（`stats` 汇总）。
- 修复菜单路由：
  - 我的成就 → `/achievements`（新增成就页路由）
  - 离线下载 → `/page/download_client`（复用已有）
  - 意见反馈 → 暂指向 `/about` 或空态提示（反馈后端本次不做）
  - 帮助中心 → `/about` 或空态
  - 关于砺安题库 → `/page/about`
  - 设置 → 新增 `/profile/settings` 或复用桌面设置区块

---

## 10. 设备管理

- 复用 `/api/auth/devices`（列表/移除/下线全部）。
- 补 UA 品牌识别：在登录时（`auth.py login`）解析 `User-Agent` 写入 `device_sessions` JSON（新增 `device_name`/`device_type`/`browser`/`os_version` 字段）。
- 新增 `services/device_service.py`：`parse_device_info(user_agent) -> dict`（品牌/类型/OS/浏览器识别），供登录埋点与设备列表展示。

---

## 11. 设计令牌与视觉规范

（完整令牌见 §3.3，实现时必须复用，禁止引入新色值破坏一致性。）

- 桌面导航/页面沿用 `navbar.vue` + `gold_purchase.vue` + `home_page.vue` 的令牌。
- 手机/平板沿用其现有浅色主题（主色 `#1A365D`，渐变 `#1A365D→#2a5298`），不改变既有视觉。
- 图标统一 `XIcon(@vtj/ui)` + `@vtj/icons`；成就不用 emoji 与图标混用时，保持列表内的 `icon` 字段为 emoji 字符串。

---

## 12. 错误处理

| 场景 | 处理 |
|---|---|
| 成就重复发放 | 唯一约束拦截 → 静默跳过 + warn 日志 |
| 金币并发超发 | `total_coins` 行锁 `with_for_update()` |
| 金币不一致 | 每日校验任务，`actual = Σ(CoinRecord)` 与 `total_coins` 比对并修正 |
| 前端显示滞后 | 行为接口即时返回 `newly_unlocked`，前端弹窗；列表页轮询兜底 |
| 未登录访问 | 所有新接口 `Depends(get_current_user)` |

---

## 13. 测试与验证计划

1. **成就幂等**：同一行为触发两次，`user_achievement` 仅 1 条，金币不重复加。
2. **成就原子**：模拟金币更新失败，成就插入回滚。
3. **签到发币**：首签 +5；连续第 7 天 +25（5+20）；断签重置。
4. **等级**：成长值增量写入后，等级/进度按公式精确计算；满级 100%。
5. **三端数据**：桌面/平板/手机「我的」页均展示真实计数（非硬编码）。
6. **路由**：手机端菜单点击不再 404。
7. **VTJ 一致性**：改 `.vue` script 后同步 `.vtj/files/*.json` 与 `__VERSION__`；清 Vite 缓存验证前端生效。

---

## 14. 验收质量门禁（写代码前逐条自查）

1. **VTJ 版本一致**：`.vue` 的 `<script>` 改动同步 `.vtj/files/*.json` 的 methods/state/lifeCycles，`__VERSION__` 与 `useProvider({version})` 一致。
2. **前端显示效果**：确认改的是正确 `.vue`（`ContextMode.Raw` 直接加载），改完清 Vite 缓存 + 强刷验证。
3. **后端完整性**：新路由在 `main.py` 注册；模型字段与 schema 一致；接口返回字段与前端解构一致。
4. **安全**：新接口全部 `get_current_user`；金币/成就用事务 + 唯一约束 + 行锁。
5. **运维**：成就/金币流水全量日志；幂等可重跑；回填脚本 `--dry-run` → `--apply`。
6. **代码风格**：后端同步 `db.query()/commit()`（**不用**方案里的 `async with db.begin()`）；前端 Options API + `window.__VTJ_AUTH__.apiFetch()`。

---

## 15. 开放问题（实施前确认）

1. 「解答高手（回答被采纳10次）」依赖论坛「采纳」机制，当前 `forum.py` 无采纳功能 → 建议**降级为「累计获赞 100 次」**或本轮暂不判定，需确认。
2. 「单日百题/周做题达人」的「单日/单周」窗口口径按自然日/自然周计算，需确认。
3. 手机端「意见反馈/帮助中心」本轮无后端，是否用空态提示占位（推荐）或暂隐藏入口。

---

> 本 spec 已通过自审：无 TBD 占位、无内部矛盾、范围聚焦单次实施计划；§15 的开放问题需用户确认后锁定。
