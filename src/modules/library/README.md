# 备考资料（library）域卡

> P2-36 ~ P2-39 已完成：**已实现**（列表 / 详情 / 视频学习进度 / 收藏 / 打开上报）。
> 三端入口不再提示「功能还未开发」。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/materials_xingce.vue`（raw，仅改 `<script>`） | `/page/materials_xingce` | PC | 已接入 store |
| `src/views/student/mobile/mobile_materials.vue`（手写） | `/mobile/materials` | 手机 / 平板 | 已接入 store |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/materials` | library/materials.py | 资料列表（`subject` 必填，可按 `type` 筛选，`page` / `page_size` 分页）；**只读，不上报打开** |
| GET | `/api/materials/{id}` | library/materials.py | 资料详情；登录用户首次打开即发布 E8 `material.opened`（同资料幂等） |
| GET | `/api/materials/progress-summary` | library/materials.py | 科目学习进度概览（登录）；**只读** |
| POST | `/api/materials/progress` | library/materials.py | 上报学习进度（UPSERT 幂等，进度只存后端）；**不发布打开事件** |
| POST | `/api/materials/{id}/favorite` | library/materials.py | 收藏切换（登录） |
| GET | `/api/materials/favorites` | library/materials.py | 我的收藏（登录） |
| POST | `/api/materials/admin/upload/image` | library/materials.py | 封面 / 插图上传（**仅管理员**，学生 403） |
| POST | `/api/materials/admin/import/upload` | library/materials.py | 素材导入上传（**仅管理员**） |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| subject / type | string \| null | 当前科目 / 类型筛选 | 否 |
| items | LibraryMaterial[] | 当前页列表 | 否 |
| total / page / pageSize | number | 服务端分页状态 | 否 |
| selected | LibraryMaterialDetail \| null | 当前打开的资料详情 | 否 |
| summary | LibraryProgressSummary | 科目进度概览 | 后端 `user_material_progress` |
| isEmpty / totalPages / hasPrevPage / hasNextPage（派生） | — | 空态与分页派生值 | 否 |
| is_studied / progress_percent / is_favorite | 条目字段 | **后端权威状态**，不写 localStorage | 后端 `user_material_progress` |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `material.opened`（E8） | 登录用户首次打开某条资料详情 | `{user_id, trigger_type}` 由后端 `record_user_action` 发布；同资料二次打开不重复 | 已接入 |
| 前端事件总线事件 | 无 | 本域不发布前端事件 | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅任何事件 | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端单测 | `backend/tests/test_library_module.py` | 已创建（打开去重 / 只读不发 / 匿名不发 / 学生上传 403） |
| 前端单测 | `src/modules/library/__tests__/store.spec.ts` | 已创建（列表参数拼装 / 空态 / 错误态 / 详情 / 进度 / 收藏） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 行测资料四栏加载 / 详情弹窗 / 视频进度 / 收藏正常，首次打开后事件上报 | 待验收 |
| 平板 | 复用手机资料页路由，列表与详情正常 | 待验收 |
| 手机 | 科目切换 / 详情弹层 / 标记已学正常，进度只存后端 | 待验收 |
