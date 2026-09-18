# 金币购功能模块实现计划（v3.1）

> 基于 spec `docs/superpowers/specs/2026-09-18-gold-purchase-design.md`
> 工作区：`feat/gold-purchase` 分支，root = `D:\砺安题库\砺安题库`

## 任务分解（按依赖顺序）

### A. 后端数据模型

- [ ] **T1** `backend/app/models/models.py`：新增 `ShopProduct`、`CoinExchange` 模型；扩展 `CoinRecord.source_type` 枚举(+RANDOM_TASK/GOAL/SHOP)、`SysUser` +avatar_frame、`StudyGoal` +四维加权字段（base_reward/reward_coins/difficulty_factor/quality_score/persistence_score/improvement_score/baseline_accuracy/baseline_count）。— 验收：模型可 import，字段完整。

### B. 后端服务

- [ ] **T2** `backend/app/services/deliverable_service.py`：权益发放分发（title→UserTitle；avatar_frame→SysUser.avatar_frame）。— 验收：deliver() 按类型正确写入。

- [ ] **T3** `backend/app/services/goal_completion_service.py`：四维加权算法（完成率40%/质量25%/坚持20%/进步15% + 难度系数封顶3.0 + 保底10）。— 验收：给定输入返回正确 reward。

### C. 后端 API

- [ ] **T4** `backend/app/api/v1/shop.py`：GET products / GET products/{id} / POST exchange（幂等 request_id + 事务扣币 + 写流水 + 写兑换 + 触发 deliverable）。— 验收：兑换成功/余额不足/重复请求三态正确。

- [ ] **T5** `backend/app/api/v1/tasks.py`：GET overview / POST random/refresh / POST {task_id}/claim（calc 模式实时进度 + claimed 防重）。— 验收：进度达标可领、重复领取拒绝。

- [ ] **T6** `backend/app/api/v1/goals.py`：新增 POST /{goal_id}/complete，集成四维加权发币（source_type=GOAL）。— 验收：完成触发正确奖励。

- [ ] **T7** `backend/app/api/v1/admin.py` 或新 `admin_shop.py`：商品 CRUD（admin 权限）。— 验收：管理员可增删改查商品。

- [ ] **T8** `backend/app/main.py`：注册 shop/tasks 路由 + 自动迁移（shop_products/coin_exchanges 表、sys_user.avatar_frame、study_goal 扩展字段、coin_record 枚举）。— 验收：启动无报错，表/字段就绪。

### D. Seed

- [ ] **T9** seed 脚本：商品目录（限定称号 + 头像框）+ 任务目录（每日/随机池/周常）幂等初始化。— 验收：重复执行无副作用。

### E. 前端（VTJ 规范：只改 script，版本号一致）

- [ ] **T10** `.vtj/vue/gold_purchase.vue`：PC 页内 Tab（商城/明细/任务/目标/成就），接真实 API。— 验收：兑换后余额/明细联动刷新。

- [ ] **T11** `.vtj/vue/tablet_gold_purchase.vue`：平板端，顶部 Tab + 卡片流。— 验收：与 PC 数据同源。

- [ ] **T12** `.vtj/vue/mobile_gold_purchase.vue`：手机端，单列卡片流 + 底部抽屉。— 验收：与 PC 数据同源。

- [ ] **T13** `.vtj/vue/admin_shop.vue`：后台商品 CRUD 表格。— 验收：增删改查可用。

### F. 验证

- [ ] **T14** 后端接口验证（启动 + 关键接口冒烟）+ 前端 VTJ 版本一致性核对（.vue version ↔ DSL __VERSION__）。— 验收：接口通、版本一致、不影响其他模块。
