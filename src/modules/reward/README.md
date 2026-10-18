# 金币商城（reward）域卡

> 状态：**P2 已接入**（P2-40 ~ P2-44）。商品 / 兑换 / 流水走 reward 域封装；余额以后端为唯一事实来源。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/gold_purchase.vue` | `/gold-purchase` | PC | 已接入（raw，仅改 `<script>`） |
| `.vtj/vue/tablet_gold_purchase.vue` | `/tablet/gold-purchase` | 平板 | 已接入（raw，仅改 `<script>`） |
| `.vtj/vue/mobile_gold_purchase.vue` | `/mobile/gold-purchase` | 手机 | 已接入（raw，仅改 `<script>`） |

三端共用一个 Pinia store（`src/modules/reward/store.ts`），平板与手机页面不新建重复组件。

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/shop/products` | `backend/app/api/v1/reward/shop.py` | 在售商品分页列表 |
| GET | `/api/shop/products/{id}` | 同上 | 商品详情 |
| POST | `/api/shop/exchange` | 同上 | 金币兑换（幂等 `request_id`，事务提交后发 E9） |
| GET | `/api/coins/overview` | `backend/app/api/v1/reward/coins.py` | 余额 + 月度收支 |
| GET | `/api/coins/transactions` | 同上 | 金币流水分页 |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading / error / initialized / ready | 公共骨架 | 加载 / 错误 / 初始化 / 可用 | 否 |
| products / total / page / pageSize | 商品列表 | 服务端分页 | 否 |
| balance / monthIncome / monthExpense | 金币概览 | 只读快照 | 否 |
| records / recordTotal / recordPage / recordPageSize | 金币流水 | 服务端分页 | 否 |
| selected / lastExchange | 交互态 | 当前详情 / 最近一次兑换结果 | 否 |
| exchanging | 交互态 | 兑换中防重复点击 | 否 |

不写 localStorage，任何业务数据均以后端为准。

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `reward:coins-changed` | 兑换成功后由 store 广播 | `{ coins, delta, reason: 'shop.purchase' }` | 已接入 |
| `shop.purchased`（E9） | 后端兑换事务提交后 `record_user_action` | `{ exchange_id, product_id, product_name, coin_cost, balance }` | 已接入 |

失败 / 余额不足 / 库存不足 / 权益异常回滚时**不发布**任何事件。

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| — | — | 本域不订阅前端事件 | — |

`src/stores/user-profile.ts` 订阅 `reward:coins-changed` 并调用 `GET /api/coins/overview` 刷新余额快照。

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端单测 | `backend/tests/test_reward_module.py` | 5 passed |
| 前端单测 | `src/modules/reward/__tests__/store.spec.ts` | 已覆盖商品 / 余额 / 流水 / 防重复 / 事件广播 |
| 余额快照单测 | `src/modules/reward/__tests__/user-profile.spec.ts` | 已覆盖事件触发只读拉取 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 商品列表 / 兑换 / 流水 / 余额刷新 | 待人工验收 |
| 平板 | 同上（复用 `meta.platform` 路由） | 待人工验收 |
| 手机 | 同上 | 待人工验收 |
