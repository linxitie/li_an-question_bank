# 金币购功能模块设计规格（v3.1）

> 版本：v3.1　日期：2026-09-18　状态：已批准
> 范围：金币核心闭环（赚币 → 花币 → 看明细）。充值 / 实物混合支付后置。

## 1. 概述与范围

「金币购」是砺安题库的学习激励模块，构建「学习 → 赚金币 → 兑换奖励」正向闭环。本期实现金币核心闭环，**复用现有后端基础设施，只补缺口**。

### 1.1 本期范围（IN）

| 模块 | 内容 |
|---|---|
| 金币商城 | 限定称号 + 专属头像框 兑换（装饰类，100% 可兑现） |
| 金币明细 | 复用 coin_record 流水，真实数据打通 |
| 任务中心 | 每日签到（状态展示）+ 每日任务 + 随机任务 + 周常任务 |
| 个人目标 | 四维加权完成度算法发币 |
| 我的成就 | 复用 45 枚成就，前端展示 + 已解锁弹窗 |
| 三端 | PC / 平板 / 手机独立页面 |
| 管理后台 | 商品 CRUD |

### 1.2 本期排除（OUT，预留扩展点）

RMB 充值、实物混合支付、备考资料解锁、VIP、错题导出/组卷配额类权益、风控（实名/设备指纹/验证码）。

## 2. 数据模型

### 2.1 复用（不重建）

| 能力 | 表/模型 | 说明 |
|---|---|---|
| 金币余额 | `sys_user.total_coins` | 唯一事实来源 |
| 金币流水 | `coin_record`(CoinRecord) | record_id/user_id/coin_change/current_balance/transaction_type(GAIN\|SPEND)/source_type(CHECKIN\|TASK\|EXAM\|SYSTEM\|PURCHASE)/related_id/description/transaction_time |
| 签到 | `daily_checkin`(DailyCheckin) | 已发金币 |
| 成就 | `achievement`(45枚) + `user_achievement`(唯一约束幂等) | |
| 任务 | `badge_task`(Task) + `user_task_progress`(UserTaskProgress, UNIQUE(user_id,task_id,period_key)) | 模型已有，缺 API |
| 称号 | `badge_title`(Title) + `user_title`(UserTitle, UNIQUE(user_id,title_id)) | |
| 成长值 | `growth_service` | 10 级 |

### 2.2 新增 `shop_products`（商品表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK AUTO | |
| name | VARCHAR(200) | 商品名 |
| category | VARCHAR(20) | 限定称号 / 专属头像框 |
| product_type | VARCHAR(20) | virtual / physical（本期仅 virtual） |
| coin_price | INT | 金币价 |
| cash_price | DECIMAL(10,2) NULL | 现金价（后置预留） |
| stock | INT | 库存（-1=不限） |
| image_url | VARCHAR(300) | 封面（emoji 或 URL） |
| description | TEXT | 详情 |
| deliverable_type | VARCHAR(30) | title / avatar_frame |
| deliverable_payload | JSON | 权益参数（如 {title_id:1} / {frame_id:"badge_gold"}） |
| status | VARCHAR(20) | on_sale / off_shelf |
| sort_order | INT | 排序 |
| created_at / updated_at | DATETIME | |

### 2.3 新增 `coin_exchanges`（兑换记录表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK AUTO | |
| user_id | BIGINT | |
| product_id | INT | |
| product_name | VARCHAR(200) | 商品名快照 |
| product_type | VARCHAR(20) | 快照 |
| coin_cost | INT | 消耗金币 |
| cash_cost | DECIMAL(10,2) NULL | 后置预留 |
| status | VARCHAR(20) | pending / completed / refunded |
| deliverable_type | VARCHAR(30) | 快照 |
| deliverable_payload | JSON | 快照 |
| request_id | VARCHAR(64) UNIQUE | 幂等键 |
| created_at / completed_at | DATETIME | |

### 2.4 扩展

- `coin_record.source_type` 枚举新增：`RANDOM_TASK` / `GOAL` / `SHOP`
- `sys_user` 新增：`avatar_frame` VARCHAR(50)（头像框标识）
- `study_goal` 新增：`base_reward` INT、`reward_coins` INT、`difficulty_factor` FLOAT、`quality_score` FLOAT、`persistence_score` FLOAT、`improvement_score` FLOAT、`baseline_accuracy` FLOAT、`baseline_count` INT

## 3. API 契约

### 3.1 复用（不改）

`GET /api/coins/overview`、`GET /api/coins/transactions`、`GET /api/achievements`、`GET /api/achievements/earned`、`GET /api/achievements/progress`、`/api/goals/*`(CRUD)、`POST /api/stats/auto-checkin`、`GET /api/stats/weekly-checkin`

### 3.2 新增 shop.py

| 接口 | 方法 | 请求 | 响应/错误 |
|---|---|---|---|
| `/api/shop/products` | GET | query: category/search/page/page_size | 仅 on_sale；分页列表 |
| `/api/shop/products/{id}` | GET | path: id | 详情；404 不存在 |
| `/api/shop/exchange` | POST | body: product_id, request_id | 校验余额≥价格 → 事务扣币 + 写 CoinRecord(SHOP) + 写 coin_exchanges + 触发 deliverable；错误：余额不足(400)/重复请求(409)/下架或不存在(404) |

### 3.3 新增 tasks.py

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/tasks/overview` | GET | 聚合：签到状态 + 每日任务 + 随机任务 + 周常任务（含进度与领取状态） |
| `/api/tasks/random/refresh` | POST | 每日免费 1 次；超出返回 400 |
| `/api/tasks/{task_id}/claim` | POST | 校验进度达标 + 未领取 → 发币(CoinRecord TASK/RANDOM_TASK) + 标记 claimed；否则 400 |

### 3.4 扩展 goals / 新增 admin

- `POST /api/goals/{id}/complete`：触发四维加权计算发币（source_type=GOAL）
- `/api/admin/shop/products` GET/POST/PUT/DELETE：admin 权限，商品 CRUD

## 4. 前端页面

| 端 | 文件 | 结构 |
|---|---|---|
| PC | `.vtj/vue/gold_purchase.vue` | 重构（当前硬编码 mock，id=gold_purchase, raw:false）→ 页内 Tab：商城（称号+头像框卡片+详情弹窗）、金币明细、任务中心、个人目标、我的成就 |
| 平板 | `.vtj/vue/tablet_gold_purchase.vue` | 新建，顶部 Tab + 卡片流 |
| 手机 | `.vtj/vue/mobile_gold_purchase.vue` | 新建，单列卡片流 + 底部抽屉 |
| 后台 | `.vtj/vue/admin_shop.vue` | 新建，商品 CRUD 表格 |

VTJ 约束：只改 `<script>`(methods/state/lifeCycles) 不改 `<template>`；`.vtj/files/*.json` 的 `__VERSION__` 与 `.vue` 的 `useProvider({version})` 一致；用 `window.__VTJ_AUTH__.apiFetch()`；三端读同一组后端 API，前端零硬编码价格/商品。

## 5. 四维加权目标算法

- completion_rate（40%）= current_count / target_count
- quality_score（25%）= 范围内正确率分档：>=85%→1.0，>=70%→0.7，>=60%→0.5，否则 0.3
- persistence_score（20%）= 连续学习天数分档：>=30→1.0，>=21→0.9，>=14→0.75，>=7→0.6，>=3→0.4，否则 0.2
- improvement_score（15%）= (当前正确率 − 基线正确率) / max(基线正确率, ε)，截断 [0,1]
- difficulty_factor 按 goal_type + target_value，封顶 3.0
- reward = max(base_reward × overall_completion × difficulty_factor, 10)
- 发币走 CoinRecord(source_type=GOAL)

## 6. 权益发放服务

`deliverable_service.deliver(exchange)` 按 deliverable_type 分发：
- `title` → 插入 UserTitle(title_id=payload.title_id, equipped=0) → 「我的」页佩戴
- `avatar_frame` → 设置 SysUser.avatar_frame = payload.frame_id → 「我的」页头像框展示

## 7. 幂等 / 并发 / 对账

- 兑换：事务内 `WHERE total_coins >= price` 防并发扣超；`request_id` 唯一防重复
- 每次币变动必写 CoinRecord + current_balance 快照，可对账
- 任务 claim 用 claimed 标志位；成就用唯一约束

## 8. Seed 脚本

商品目录 + 任务目录幂等初始化（重复执行无副作用）。

## 9. 验收标准

1. 兑换后余额正确扣减，明细新增 SHOP 流水
2. 称号 / 头像框兑现（写入 user_title / sys_user.avatar_frame）
3. 任务进度达标可领取，重复领取被拒绝
4. 目标完成按四维加权发币，保底 10 币
5. 三端读同一组 API，数据一致
