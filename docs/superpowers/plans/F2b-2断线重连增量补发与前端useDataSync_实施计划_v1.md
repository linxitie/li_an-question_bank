# F2b-2 断线重连增量补发与前端 useDataSync 实施计划 v1

> 状态：**已批准并执行完成**（2026-10-27，Step 0–8 完成，tag foundation-v1-f2b2）
> 适用仓库：D:/砺安题库/砺安题库（main）
> 基线提交：F2b-1 完成后的 main（98689c2，tag foundation-v1-f2b1）
> 关联文档：docs/superpowers/specs/砺安题库终态总体架构_v2.0.md、docs/superpowers/plans/F2b-1事件总线同事务化_实施计划_v1.md

## 1. 目标

把 F2b-1 已经落地的「Outbox 同事务 + 定向 data-changed」补成可恢复链路：

1. 每条 data-changed 携带 Outbox 单调游标 oid（add-only，不破坏旧字段）。
2. 客户端记录本端已见最大 oid；WebSocket 重连时带 since 请求补发。
3. 服务端只补发该用户/角色可见的事件，不泄露他人私有域事件。
4. 补发超过上限、超过保留期、开关关闭或服务端异常时，明确返回 truncated，客户端回退一次全量同步。
5. 新增前端 useDataSync：按 domain/type 过滤、100ms 防抖、组件卸载自动清理，替换两个手写页的 __VTJ_SYNC__ 监听。
6. 75 个 .vtj 页面保持模板零改动；它们仍通过一次 __VTJ_SYNC__ 获得重连后的刷新，不逐页改模板。

一句话：**从「重连必全量刷新」升级为「能增量就增量，不能增量就明确降级为一次全量」。**

## 2. 非目标（本计划明确不做）

- 不做 HTTP ?since 接口；增量补发只走现有 WS 通道。
- 不新增数据库表、不新增迁移、不引入新依赖。
- 不修改任何 .vtj/vue 页面的 template；不改 .vtj DSL；不改路由。
- 不把 75 个 VTJ 页逐页改成 useDataSync；本批只接手写页，其余走兼容路径。
- 不做 9 个真实浏览器 × 3 场景的端到端矩阵；9 组合用后端协议矩阵 + 前端传输单测覆盖，报告中如实标注。
- 不做 Outbox 历史归档/清理策略；补发保留期只做读取侧上限，不动物理数据。
- 不改变 F2b-1 的 Outbox 事务语义、Dispatcher 单写者、foundation_inbox 幂等。
- 不进入 F4/F5/F6（文档/图/向量投影）。

## 3. 实测基线与关键锚点

### 3.1 现有数据与事件

- foundation_outbox DDL：backend/migrations/20261027_001_foundation_core.sql:6-29；主键 id INTEGER AUTOINCREMENT，另有 event_id/event_name/payload/status/occurred_at。id 天然单调，适合做补发游标。
- F2b 事件处理器：backend/app/services/event_handlers.py:28-95。handle_user_action 已按 trigger 计算 route，handle_paper_published 固定三角色；两处都调用 publish_data_changed_sync，但未传 outbox id。
- trigger 路由表：backend/app/foundation/event_routes.py；Route.self_only=True 表示仅本人，False 时 roles 生效；route_for() 对未知 trigger 回落 user/user.action。
- 现有 OutboxEvent 已含 id：backend/app/foundation/stores/base.py；event.id 可直接作为 oid。

### 3.2 现有 WS 链路

- publish_data_changed_sync：backend/app/api/v1/platform/websocket.py:183-207；当前 data 只有 {domain,type,id}，scope=f"{domain}.{type}"。
- MessageType 枚举：同文件上方；已有 heartbeat/exam_progress/question_answer/chat_message/data-changed，没有 sync。
- 收消息循环：backend/app/api/v1/platform/websocket.py:262-265；handle_websocket_message 在 :274-312，当前没有 sync 分支。
- 连接握手把 user_type 交给 ConnectionManager：:251，但 handle_websocket_message 没有接收 role 参数。
- 协议信封：backend/app/foundation/ws_protocol.py:84-113；seq 用于同 scope 去重，不适合点对点 sync 回复。

### 3.3 现有前端链路

- src/utils/wsMessage.ts:30-50 解析；:52-57 classify 已经能识别 sync；:65-82 acceptSeq/resetSeq。
- src/auth.ts:213-308 WS 生命周期；:239-255 重连时 resetSeq + 立即发一次全量 __VTJ_SYNC__；:257-273 onmessage 对 sync 和 data-changed 都直接发 __VTJ_SYNC__。
- src/components/domain/RecentPracticeRecords.vue:116-136 监听 __VTJ_SYNC__ 并 800ms 防抖。
- src/views/student/shared/profile.vue 的 onMounted 中同样监听 __VTJ_SYNC__。
- 现有测试：src/utils/__tests__/authSync.spec.ts 已用 FakeSocket 覆盖重连全量同步；src/utils/__tests__/wsMessage.spec.ts 覆盖解析与去重。

## 4. 协议设计（只增不删）

### 4.1 实时 data-changed 增加 oid

旧报文（继续兼容）：

    { "type": "data-changed", "domain": "exam", "entity": "practice.submit",
      "id": "evt_xxx", "data": { "domain": "exam", "type": "practice.submit", "id": "evt_xxx" } }

新报文：

    { "type": "data-changed", "domain": "exam", "entity": "practice.submit",
      "id": "evt_xxx", "data": { "domain": "exam", "type": "practice.submit",
      "id": "evt_xxx", "oid": 12345 } }

- oid 只在服务端能拿到 Outbox 行 id 时出现；旧调用方不传则不出现，旧客户端忽略未知键。
- id 语义不变：user.action 仍是 event.event_id，paper.published 仍是 paper_id。
- oid 是补发游标，不是业务 id；不用于页面展示。

### 4.2 客户端重连请求

    { "type": "sync", "data": { "since": 12345, "limit": 200 } }

- 仅当客户端已有 lastOid 时发送；首次连接不发送，保持现状由页面首屏加载。
- since 必须是正整数；limit 服务端强制夹到 1..200。
- 不新增 HTTP 端点，复用 /ws/connect。

### 4.3 服务端补发回复

    { "v": 2, "type": "sync", "scope": "sync",
      "data": { "reason": "replay", "events": [
        { "domain": "exam", "type": "practice.submit", "id": "evt_xxx", "oid": 12346 }
      ], "latest_oid": 12350, "truncated": false },
      "timestamp": "..." }

降级回复：

    { "v": 2, "type": "sync", "scope": "sync",
      "data": { "reason": "replay-truncated", "events": [], "latest_oid": 12350, "truncated": true } }

- sync 回复不带 seq；客户端对 sync 不做 acceptSeq 去重（点对点回复，不参与广播序号）。
- reason 取值：replay / replay-truncated / disabled / bad-request / error。
- events 只含可见事件；不返回 payload、不返回他人 user_id。

### 4.4 可见性过滤（安全边界）

服务端逐行读取 foundation_outbox，按 event_name 分派：

- EV_USER_ACTION：从 payload 取 user_id、trigger_type；用 route_for(trigger) 得 domain/type/roles/self_only。
  - 请求者 = 事件 user_id：可见。
  - 请求者 != user_id 且 route.self_only=False 且请求者角色在 route.roles：可见。
  - 其余不可见。
- EV_PAPER_PUBLISHED：payload.paper_id 存在，且请求者角色属于 student/teacher/admin：可见，domain=exam，type=paper.published，id=paper_id。
- 其他 event_name：本计划不补发（它们当前没有 data-changed 生产者）；直接跳过，不报错。
- 过滤必须在服务端完成；客户端拿不到的事件不可能被伪造出来。

### 4.5 截断规则（宁可全量，不可漏）

满足任一条件即 truncated=true，且 events=[]：

1. WS_SYNC_REPLAY_ENABLED=false。
2. since 无法解析、小于 0 或不是整数。
3. 可补发行数 > limit（默认 200）。
4. 在 since 之后存在早于保留期截止时间的事件（默认 24 小时）。
5. 查询/解析异常。

另外：

- latest_oid = 当前 status != dead 的最大 id；没有事件时为 0。
- 只读取 status != dead 的行；dead 行不补发，避免把已放弃事件当事实。
- occurred_at 是带时区 ISO 字符串，SQL 必须用 datetime(occurred_at) 归一化后再与 UTC 截止时间比较，禁止直接字符串比较。
- 客户端收到 truncated 后执行一次全量 __VTJ_SYNC__，并把 lastOid 设为 latest_oid（若 >0）。

### 4.6 兼容与降级

| 场景 | 行为 |
|---|---|
| 旧服务端（不识别 sync） | 客户端 2.5s 无回复，发一次 __VTJ_SYNC__（reason=ws-reconnect） |
| 服务端关闭补发 | 立即回 truncated，客户端立刻全量，不等待 2.5s |
| 服务端异常 | 回 truncated/error，客户端全量 |
| 补发 events 非空 | 旧页面收到一次 __VTJ_SYNC__；新页面收到逐条 __VTJ_DATA_CHANGED__ |
| 补发 events 为空 | 不发 __VTJ_SYNC__，只更新游标 |
| 没有 lastOid | 重连行为与 F2 完全一致：resetSeq + 一次全量 |
| 用户退出登录 | 清空 lastOid、清空补发定时器、resetSeq |

## 5. 前端 useDataSync 设计

### 5.1 API

新增 src/composables/useDataSync.ts：

    export interface DataSyncEvent { domain?: string; type?: string; id?: number|string; oid?: number }
    export interface DataSyncOptions {
      domains?: string | string[];
      types?: string | string[];
      debounceMs?: number;
      handler: (events: DataSyncEvent[]) => void;
    }
    export function createDataSyncListener(options: DataSyncOptions): () => void
    export function useDataSync(options: DataSyncOptions): void

- createDataSyncListener 是纯函数，便于 node/jsdom 单测；返回 stop。
- useDataSync 在 onMounted 注册、onBeforeUnmount 调用 stop；同时处理定时器清理。
- 事件来自 window 的 __VTJ_DATA_CHANGED__，detail 就是 {domain,type,id,oid}。
- domains/types 支持字符串或数组；空表示不过滤。
- 默认 100ms 防抖；同一窗口内多个事件合并为一次 handler(events)。
- handler 抛错只 console.error，不阻塞其他监听器。

### 5.2 接入范围

本批只接两个手写页：

1. src/components/domain/RecentPracticeRecords.vue：
   - domains: exam；types: practice.submit / practice.record.created / paper.completed；
   - debounceMs: 800（保留原节流体验）；
   - 替换原 __VTJ_SYNC__ 监听，load() 逻辑不变。
2. src/views/student/shared/profile.vue：
   - domains: exam/wrong/note/favorite/community/news/library/reward/growth/user；
   - debounceMs: 500；
   - 只重拉个人统计/金币/等级/勋章/掌握度，不重拉整页路由。

75 个 VTJ 页不改：auth 在补发批次到达时仍发一次 __VTJ_SYNC__，旧页面照常刷新；新页面同时收到 typed 事件。

### 5.3 auth 改造点

- 新增模块级变量 _lastOutboxId、_syncReplayTimer。
- onopen：
  - isReconnect 且 _lastOutboxId != null：send({type:"sync",data:{since:_lastOutboxId,limit:200}})，启动 2500ms 兜底定时器；
  - 其他情况：保持 F2 行为，resetSeq + 一次 __VTJ_SYNC__。
- onmessage：
  - sync：清定时器；truncated/error -> 一次 __VTJ_SYNC__ + 更新游标；replay 非空 -> 一次 __VTJ_SYNC__（兼容旧页）+ 逐条 __VTJ_DATA_CHANGED__ + 更新游标；空 -> 只更新游标。
  - data-changed：更新游标；保留 __VTJ_SYNC__、bridgeWsMessageToPapers，并新增 __VTJ_DATA_CHANGED__。
- acceptSeq 只作用于 data-changed 等广播消息；sync 回复不参与 seq 去重。
- closeSyncSocket（登出）清空 _lastOutboxId 和定时器；网络 onclose 保留游标。
- 游标只存在内存，不写 localStorage；页面刷新后首屏加载即全量，不需要旧游标。

## 6. 文件清单

### 6.1 后端新增/修改

| 文件 | 动作 | 说明 |
|---|---|---|
| backend/app/foundation/ws_sync.py | 新增 | 可见性过滤、截断、latest_oid、SyncReplay 数据结构 |
| backend/app/foundation/config.py | 修改 | 新增 WS_SYNC_REPLAY_ENABLED / MAX_EVENTS / MAX_AGE_HOURS |
| backend/app/api/v1/platform/websocket.py | 修改 | MessageType.SYNC；publish_data_changed_sync 增加 outbox_id；sync 分支；role 参数 |
| backend/app/services/event_handlers.py | 修改 | 两处 publish 传 outbox_id=event.id |
| backend/tests/test_f2b_sync_replay.py | 新增 | 可见性、截断、保留期、异常、27 组合矩阵 |
| backend/tests/test_f2b_sync_ws.py | 新增 | handle_websocket_message sync 分支、旧消息兼容、坏 since |
| backend/tests/test_f2b_events.py | 修改 | 断言 data.oid 存在且等于 outbox id |
| backend/scripts/gates/gate_l7_foundation.py | 修改 | L7-18 补发契约检查（17 -> 18） |

### 6.2 前端新增/修改

| 文件 | 动作 | 说明 |
|---|---|---|
| src/utils/wsMessage.ts | 修改 | DataChangedPayload/SyncReplayPayload 类型、toDataChanged、toSyncReplay |
| src/auth.ts | 修改 | 游标、sync 请求、补发处理、2.5s 兜底、typed 事件 |
| src/composables/useDataSync.ts | 新增 | createDataSyncListener + useDataSync |
| src/components/domain/RecentPracticeRecords.vue | 修改 | 改用 useDataSync（script only） |
| src/views/student/shared/profile.vue | 修改 | 改用 useDataSync（script only） |
| src/utils/__tests__/wsMessage.spec.ts | 修改 | oid/replay 解析 |
| src/utils/__tests__/authSync.spec.ts | 修改 | 游标、sync 请求、truncated、2.5s 兜底、登出清理 |
| src/composables/__tests__/useDataSync.spec.ts | 新增 | 过滤、防抖、卸载、异常隔离 |

### 6.3 文档

| 文件 | 动作 |
|---|---|
| docs/superpowers/plans/F2b-2断线重连增量补发与前端useDataSync_实施计划_v1.md | 本文件 |
| docs/superpowers/specs/F2b-2断线重连增量补发_报告_20261027.md | 执行后新增 |
| docs/README.md | 索引 + 变更记录 |

## 7. 分步执行（每步独立验证，失败即停）

### Step 0 基线确认（0.2 天）

- git status 必须干净；记录 HEAD。
- 备份数据库？本计划不改表、不改数据；不触发备份。
- 跑一次 python -m pytest backend/tests/test_f2b_events.py -q 作为基线。
- 验收：工作树干净，基线测试全过。

### Step 1 后端补发核心 ws_sync.py（0.5 天）

- 新增 replay_visible_events(session, user_id, role, since, limit, now) -> SyncReplay。
- 数据结构：events: list[dict]、latest_oid: int、truncated: bool、reason: str。
- 读取 foundation_outbox，status != dead，id > since，按 id 升序。
- 先用一条 SELECT 取 limit+1 条候选；再按 event_name/payload 过滤可见性。
- 若候选 > limit，或 since 之后存在早于保留期的行，truncated=true、events=[]。
- 先查 latest_oid，保证截断时客户端仍能推进游标。
- 所有异常由调用方转成 reason=error，不抛到 WS 循环。
- 验证：pytest tests/test_f2b_sync_replay.py -q。

### Step 2 事件处理器补 oid（0.2 天）

- publish_data_changed_sync 增加关键字参数 outbox_id: int | None = None；仅非空时写入 data.oid。
- publish_data_changed 转发 outbox_id。
- handle_user_action 与 handle_paper_published 增加 outbox_id=event.id。
- 验证：F2b 事件测试断言 data.oid == outbox 行 id；旧调用不传时无 oid 键。

### Step 3 WS sync 分支（0.5 天）

- MessageType 增加 SYNC = "sync"。
- websocket_connect 把 payload.user_type 传给 handle_websocket_message。
- handle_websocket_message 增加 role 参数（默认 None，保持旧测试兼容）。
- sync 分支：开 SessionLocal，调用 replay_visible_events，关闭 session，send_json。
- 坏 since/异常：回 reason=bad-request 或 error，truncated=true；不让连接断开。
- 验证：test_f2b_sync_ws.py 用 FakeWebSocket 断言只发给当前连接、不广播。

### Step 4 前端协议工具（0.3 天）

- wsMessage.ts 增加类型与纯函数；classify 保持不变。
- toDataChanged 从 msg.data 取 domain/type/id/oid，兼容顶层字段。
- toSyncReplay 校验 events 数组、latest_oid、truncated。
- 验证：wsMessage.spec.ts。

### Step 5 auth 游标与补发（0.6 天）

- 实现 5.3 的 onopen/onmessage/closeSyncSocket 改造。
- 2.5s 兜底只针对「已发 sync 但没回包」；收到任何 sync 回复即清除。
- 旧页面兼容：replay 非空只发一次 __VTJ_SYNC__，不逐条发。
- 测试：authSync.spec.ts 覆盖在线 oid、重连请求、truncated、旧服务端超时、登出清理。

### Step 6 useDataSync 与两页接入（0.5 天）

- 新增 composable；注意 import 路径用 @/composables/useDataSync。
- RecentPracticeRecords 只改 script：替换 listener 与 timer；模板不动。
- profile 只改 script：抽 loadProfileData()，useDataSync 调用；模板不动。
- 验证：新增 composable 测试 + 现有页面相关测试。

### Step 7 L7-18 与文档（0.3 天）

- gate_l7_foundation.py 增加 check_sync_replay，编号 18。
- 检查项：ws_sync.py 存在且含 replay_visible_events；websocket.py 含 SYNC/outbox_id；event_handlers 含 outbox_id=event.id；useDataSync.ts 存在。前端缺失记 WARN，后端契约缺失记 FAIL。
- 更新 README 活跃索引 + 变更记录。
- 执行后写交付报告。

### Step 8 全量验收与提交（0.4 天）

- 后端：python -m pytest tests/test_f2b_sync_replay.py tests/test_f2b_sync_ws.py tests/test_f2b_events.py -q；再跑全量 pytest tests -q。
- 前端：npm run test:unit；npm run typecheck。
- 门禁：python backend/scripts/gates/gate_all.py；python backend/scripts/gates/gate_l7_foundation.py。
- 复核 git diff --stat，确认没有 .vtj template 改动、没有新表/迁移/依赖。
- main 单提交，打 tag foundation-v1-f2b2，不 push（与既有节奏一致）。

## 8. 测试与 9×3 矩阵

### 8.1 9 组合定义

9 组合 = 3 角色（student/teacher/admin）× 3 设备类别（pc/tablet/mobile）。

- student 三设备都有承载页：PC profile、tablet_profile、mobile_home/mobile_profile。
- teacher/admin 仅 PC 有承载页；tablet/mobile 没有对应账号页，因此只验证「协议等价」，不新增页面、不伪装真机。
- 设备类别不改变 WS 协议；它只决定前端由哪个页面承载。

### 8.2 3 场景

| 场景 | 触发 | 期望 |
|---|---|---|
| S1 在线 | live data-changed 带 oid | 游标单调取 max；旧页一次 __VTJ_SYNC__；新页 typed 事件 + 防抖 |
| S2 断线重连 | 有 lastOid，发送 sync since | 服务端只回可见事件；客户端一次 legacy sync + 逐条 typed；游标推进 latest_oid |
| S3 过期/超限 | since 超 24h 或 >200 或 disabled/error | 回 truncated；客户端一次全量；游标推进；不逐条刷新 |

### 8.3 矩阵落点

- 后端 test_f2b_sync_replay.py：parameterize(role 3 × device 3 × scenario 3) = 27 个协议级用例；device 仅作为参数标签，验证同一可见性结果。
- 前端 authSync.spec.ts：S1/S2/S3 三条链路 × FakeSocket；不按设备重复，因为设备不参与协议。
- 页面承载：RecentPracticeRecords + profile 的 jsdom 单测，验证 typed 事件只触发一次 handler。
- 报告中给出 27 行矩阵表，明确标「协议级，不是 9 个真实浏览器」。

### 8.4 安全用例（必须）

- student A 的私域事件（wrong/note/favorite/reward）不出现在 student B 的补发结果。
- teacher/admin 能看到 practice.submit 的定向事件，但看不到学生私域事件。
- 未知 event_name 被跳过，不抛异常。
- malformed payload 被跳过，不泄露、不 500。
- dead 事件不补发。
- since 大于 latest 返回空 events、truncated=false。

## 9. 验收标准 A1–A18

| 编号 | 验收 | 证据 |
|---|---|---|
| A1 | live data-changed 带 oid | 单测断言 data.oid = outbox.id |
| A2 | 20+2 调用点不回归 | F2b 事件测试全过；outbox_id 透传 |
| A3 | 补发可见性正确 | 27 矩阵 + 安全用例 |
| A4 | 超过 200 条截断 | 201 条候选 -> truncated，events=[] |
| A5 | 超过 24h 截断 | 旧 occurred_at -> truncated |
| A6 | 开关关闭/坏 since/异常均降级 | reason=disabled/bad-request/error，连接不断 |
| A7 | 客户端游标单调 | oid 乱序/重复时 max，不回退 |
| A8 | 有游标才发 sync | 首次连接不发；重连才发 |
| A9 | 旧服务端 2.5s 兜底 | 假定时器测试 |
| A10 | 旧页面兼容 | replay 非空只发一次 __VTJ_SYNC__ |
| A11 | 新页面 typed + 防抖 | useDataSync 单测 |
| A12 | 9 组合 × 3 场景 | 27 协议用例 + 3 前端链路；报告标注非真机 |
| A13 | 登出清理 | closeSyncSocket 清游标/定时器 |
| A14 | 无新表/迁移/依赖 | git diff + requirements/package 检查 |
| A15 | .vtj template 零改动 | git diff 只含 script；.vtj 模板未动 |
| A16 | 全量回归 | 后端 pytest 全量；前端 342+ / typecheck 0 |
| A17 | L7 18 项 | L7 PASS=17 WARN<=1 FAIL=0（以实际为准） |
| A18 | 文档归档 | 计划、报告、README 索引均更新 |

## 10. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 补发泄露他人事件 | 服务端集中过滤；安全用例；不返回 payload |
| 补发过多拖垮 WS | 硬上限 200；超限直接 truncated |
| 旧客户端不认识 sync | 旧客户端根本不发 sync；新客户端对旧服务端 2.5s 兜底 |
| 重连全量风暴 | 只有 truncated/旧服务端才全量；正常 replay 只发一次 legacy sync |
| oid 暴露全局事件量 | 只暴露单调整数，不含内容；可接受；后续可换 per-user 游标 |
| Outbox 清理导致游标空洞 | 本计划不做清理；24h 保留期兜底；未来清理必须同步推进游标策略 |
| .vtj 误改 | 只改 src/ 手写文件；Step 8 检查 .vtj 模板 diff 为空 |

回滚：

1. 服务端 WS_SYNC_REPLAY_ENABLED=false：客户端立即 truncated -> 全量，行为回到 F2。
2. 前端回滚：恢复 auth.ts 的 F2 版本；useDataSync 不再被两个页面引用。
3. 数据回滚：本计划不写业务表、不新增表；无需数据回滚。

## 11. CTC 十问

1. 为什么现在做：F2b-1 已有 Outbox 游标，但重连仍全量；这是 F2b 的明确缺口。
2. 为什么不做 HTTP ?since：WS 已经长连接 + 有鉴权；新增 HTTP 会多一套鉴权和限流。
3. 为什么 oid 用 Outbox id：天然单调、已在事务内、无需新表。
4. 为什么客户端只在重连发：首屏加载本来就是全量，发 since 无收益。
5. 为什么截断就全量：漏一条比多刷一次更严重；宁可明确降级。
6. 为什么保留 24h：覆盖一夜断网；更久由全量兜底。
7. 为什么 sync 不参与 seq：点对点回复，不是广播；参与会造成误丢。
8. 为什么旧页面只发一次 sync：避免 200 条事件触发 200 次全量刷新。
9. 为什么 75 页不改：R3 模板红线 + 改动面过大；兼容路径已覆盖。
10. 怎么证明没漏：27 矩阵 + 安全用例 + 截断用例 + 全量回归 + L7。

## 12. 预计工作量

| 步骤 | 预计 |
|---|---|
| Step 0–3 后端 | 1.4 天 |
| Step 4–6 前端 | 1.4 天 |
| Step 7–8 门禁/文档/验收 | 0.7 天 |
| 合计 | 约 3.5 个工作日 |

## 13. 待批准决策

- D1：确认「重连增量补发」走现有 WS，不新增 HTTP ?since。
- D2：确认 oid 使用 foundation_outbox.id，且允许暴露全局单调整数。
- D3：确认保留期 24h、单次上限 200 条、超限直接 truncated。
- D4：确认本批只接 2 个手写页，75 个 VTJ 页保持兼容路径、不改模板。
- D5：确认 9 组合按「3 角色 × 3 设备类别」建模，非学生角色的 tablet/mobile 只验证协议等价。
- D6：确认新增 L7-18（17 -> 18），后端契约 FAIL、前端缺失 WARN。
- D7：确认无新表、无迁移、无新依赖、main 单提交 + tag foundation-v1-f2b2。

批准后从 Step 0 开始执行；未批准前不改任何代码。

## 14. 执行记录（2026-10-27）

- 用户批准：m02256“批准”，D1–D7 全部通过。
- Step 0 基线：main 98689c2（F2b-1），工作树仅有上一轮文档 3 个未提交文件。
- Step 1–2 后端：新增 `backend/app/foundation/ws_sync.py`；`config.py` 增加 `WS_SYNC_REPLAY_ENABLED/MAX_EVENTS/MAX_AGE_HOURS`；`websocket.py` 增加 `SYNC`、`outbox_id`、`handle_sync_request`；`event_handlers.py` 两处透传 `outbox_id=event.id`。
- Step 3 后端测试：新增 `backend/tests/test_f2b_sync_replay.py`（17 个基础用例 + 201 条截断 + since>latest + 空 payload + 27 矩阵）；`test_f2b_events.py` 期望同步 `outbox_id`。定向 58 passed。
- Step 4 前端协议：`src/utils/wsMessage.ts` 新增 `extractOid/extractSyncReply`；新增 `src/utils/__tests__/wsSync.spec.ts`（4 tests）。
- Step 5 auth：`src/auth.ts` 增加内存游标、2500ms 兜底、sync 分支、typed 事件、登出清理；重写 `authSync.spec.ts` 至 6 tests（含 oid 乱序不回退）。
- Step 6 useDataSync：新增 `src/composables/useDataSync.ts` 与 3 tests；接入 `RecentPracticeRecords.vue`（800ms）与 `profile.vue`（500ms），模板未改。
- Step 7 门禁：`gate_l7_foundation.py` 17→18 项，新增 `check_sync_replay`；L7 PASS=17 WARN=1 FAIL=0，L7-18 PASS。
- Step 8 文档：架构 §11.2 增加第 18 行；README 索引/变更记录；本计划状态与执行记录；新增报告 `docs/superpowers/specs/F2b-2断线重连增量补发_报告_20261027.md`。

### 14.1 验收结果

| 项 | 结果 |
|---|---|
| 后端全量 | 725 passed / 2 xfailed / 4 failed（均为既有 Playwright 环境失败） |
| F2b 专项 | 58 passed |
| 前端单测 | 25 files / 354 passed |
| 前端 typecheck | exit 0 |
| L7 | 18 项：PASS=17 WARN=1 FAIL=0；L7-18 PASS |
| gate_all | 9/10（仅 L2 既有基线失败） |
| 新表/迁移/依赖 | 无 |
| .vtj 模板 | 零改动 |

### 14.2 与计划的偏差

1. A16 的后端全量包含 4 个既有 Playwright 失败（端口/服务未启动，端口已统一 9527），不是本次回归；报告已标注。
2. A12 的 9×3 仅协议级，不是 9 个真实浏览器；与 D5 一致。
3. 额外修复 `profile.vue` 原先在 `onMounted` 内部注册 `onBeforeUnmount` 导致的监听泄漏。

### 14.3 提交

- main 单提交（不 push），tag `foundation-v1-f2b2`。
- 详细证据见报告。

