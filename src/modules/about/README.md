# 关于砺安题库（about）域卡

> P2-69 ~ P2-70 已完成：**已实现**（版本号 / 服务名 / 联系方式只读消费）。
> 本域为纯静态展示，**无写接口、无事件进出**，不写 localStorage。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/about.vue`（非 raw，VTJ 生成页） | `/page/about` | PC | P2 已实现 api + store；页面模板无版本号 / 联系方式绑定位，按「零模板改动」约束本阶段未改 `<script>` 与 DSL，**页面接入待 P3** |

> 页面接入策略：`.vtj/vue/about.vue` 的页脚联系方式为模板硬编码，模板中无 `{{ version }}` / `{{ contact }}` 插槽。
> 要真正展示 store 数据必须改 `<template>`，与「不得改 .vtj 模板」冲突，故登记为 P3 待接入，不在本阶段做无效的 script-only 改动。

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/health` | `main.py` | 通用只读配置：`status` / `service` / `version`（无需登录） |

> 本域**无专属端点**。联系方式与版权为前端静态常量（`api.ts` 的 `ABOUT_CONTACT`），与 about.vue 页脚口径一致。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| info | AboutAppInfo \| null | 通用配置（status / service / version） | 否 |
| contact | AboutContact \| null | 联系方式（email / hotline / copyright） | 否 |
| version（派生） | string | 版本号 | 否 |
| service（派生） | string | 服务名 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| （无） | — | 本域不发布前端事件，也不上报 trigger_type | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅任何事件 | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 前端单元测试 | `src/modules/about/__tests__/store.spec.ts` | 已创建（只读配置 / 错误 / 重置 / 零事件） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | `/page/about` 静态内容正常；版本号展示待 P3 接入 | 待人工验收 |
| 平板 | 关于页路由可达、静态内容正常 | 待人工验收 |
| 手机 | 关于页路由可达、静态内容正常 | 待人工验收 |

## 附：页面接入待办

P3 需在 `.vtj` 设计器中为 about 页模板增加版本号 / 联系方式绑定位（由用户在设计器完成），
再把 `useAboutStore().load()` 接入 `<script>`，最后跑 `vtj_check_consistency(id="about")`。
