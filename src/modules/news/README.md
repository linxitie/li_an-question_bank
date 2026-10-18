# 每日新闻（news）域卡

> P2-33 / P2-34 已完成：**已实现**（列表 / 详情 / 已读标记 / 阅读上报）。
> 三端入口不再提示「功能还未开发」。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/daily_news.vue`（raw，仅改 `<script>`） | `/page/daily_news` | PC | 已接入 store |
| `src/views/student/mobile/mobile_news.vue`（手写） | `/mobile/news`、`/mobile/news/:id` | 手机 / 平板 | 已接入 store |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/news` | content/news.py | 新闻列表（按来源 / 分类筛选，`limit` 1–50）；**只读，不上报阅读** |
| GET | `/api/news/today` | content/news.py | 今日新闻；**只读，不上报阅读** |
| GET | `/api/news/{id}` | content/news.py | 新闻详情；登录用户首次打开即记录已读并发布 E7 `news.read`（同篇幂等） |
| POST | `/api/news/{id}/favorite` | content/news.py | 收藏 / 取消收藏 |
| GET | `/api/news/favorites` | content/news.py | 收藏列表 |
| POST | `/api/news/{id}/note` | content/news.py | 保存划线 / 想法笔记 |
| GET | `/api/news/{id}/notes` | content/news.py | 笔记列表 |
| DELETE | `/api/news/notes/{note_id}` | content/news.py | 删除笔记 |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| items | NewsItem[] | 当前筛选条件下的全部列表项 | 否 |
| total | number | 列表总数 | 否 |
| page | number | 当前页码（客户端分页） | 否 |
| pageSize | number | 每页条数，默认 20 | 否 |
| selected | NewsItem \| null | 当前打开的新闻详情 | 否 |
| isEmpty（派生） | boolean | 加载完成且无数据 | 否 |
| totalPages / pageItems / hasPrevPage / hasNextPage（派生） | — | 客户端分页派生值 | 否 |
| is_read | boolean（条目字段） | **后端权威已读状态**，不写 localStorage | 后端 `news_read` 表 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `news.read`（E7） | 登录用户首次打开某篇新闻详情 | `{user_id, trigger_type}` 由后端 `record_user_action` 发布 | 已接入 |
| 前端事件总线事件 | 无 | 本域不发布前端事件 | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅任何事件 | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端单测 | `backend/tests/test_news_module.py` | 已创建（去重 / 只读不发 / 匿名不发 / is_read） |
| 前端单测 | `src/modules/news/__tests__/store.spec.ts` | 已创建（分页 / 空态 / 错误态 / 阅读） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 列表 / 筛选 / 分页 / 详情打开正常，打开详情后已读上报 | 待验收 |
| 平板 | 复用 `/tablet/news` 路由，列表与详情正常 | 待验收 |
| 手机 | 列表 / 详情 / 划线笔记正常，打开详情后已读上报 | 待验收 |
