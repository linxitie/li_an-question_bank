# 题库设计模式 · QBDM 命令行工具 设计方案 v1

> 状态：**✅ 已实施（2026-10-26，提交 `76a36b8`）**——`scripts/qbdm/qbdm.py` 已建（293 行，只读零依赖），`module` / `gate` 两条子命令可用，交叉校验与基线三项均通过。
> 日期：2026-10-26
> 背景：旧版 QBDM 文档（v1/v2/v3 + 角色卡）把 `python scripts/qbdm/qbdm.py …` 写成开工第一步，但 **`scripts/qbdm/` 目录根本不存在**（事实基线 R3）。
> 目标：把这个空头承诺变成**真能跑、只读、零依赖**的小工具。

---

## §0 一句话

以后要了解某个模块，不用翻 5 个文件，敲一条命令就打印出：**端点 / 页面（含 raw 标记）/ 测试 / 该跑哪些门禁 / 红线提醒**。

---

## §1 它到底长什么样（用 forum 模块的真实数据预演）

```
PS D:\...\li_an-question_bank> python scripts/qbdm/qbdm.py module forum

┌─ 模块 forum（社区论坛） ────────────────────────────────
│ 数据源：api_surface.json（2026-10-26）｜.vtj/projects（50 页）｜git fecffd5
└─────────────────────────────────────────────────────────

端点 12 条（前缀 /api/forum，来源 api_surface.json → forum.py）
  GET    /api/forum/posts                    get_forum_posts     L143
  GET    /api/forum/posts/{post_id}          get_post_detail     L197
  POST   /api/forum/posts                    create_post         L231
  DELETE /api/forum/posts/{post_id}          delete_post         L306
  POST   /api/forum/posts/{post_id}/like     toggle_post_like    L335
  GET    /api/forum/posts/{post_id}/comments get_post_comments   L385
  POST   /api/forum/posts/{post_id}/comments create_comment      L434
  POST   /api/forum/comments/{comment_id}/like toggle_comment_like L507
  POST   /api/forum/upload                   upload_attachment   L552
  GET    /api/forum/users/{user_id}/public   get_user_public     L610
  GET    /api/forum/my-posts                 get_my_posts        L655
  GET    /api/forum/stats                    get_forum_stats     L684

页面 6 个（3 个 raw + 3 个手写）
  ⚠ raw  .vtj/vue/forum.vue                        PC 论坛
  ⚠ raw  .vtj/vue/mobile_forum.vue                 手机列表
  ⚠ raw  .vtj/vue/tablet_forum.vue                 平板列表
    SFC  src/views/teacher/teacher_forum.vue        教师端
    SFC  src/views/student/mobile/mobile_forum_detail.vue
    SFC  src/views/student/tablet/tablet_forum_detail.vue

测试 6 个
  backend/tests/test_forum_moderation.py
  backend/tests/test_forum_p1.py
  backend/tests/test_forum_posting.py
  backend/tests/test_forum_report.py
  backend/tests/test_forum_upload.py
  src/views/student/tablet/__tests__/tablet_forum_detail.spec.ts

改这个模块要跑的门禁
  python backend/scripts/gates/gate_l4_api_contract.py      ← 端点契约（343 条基准）
  python backend/scripts/gates/check_module_boundary.py     ← 跨域 import
  python backend/scripts/gates/gate_l5_frontend_contract.py ← 改了 .vtj 页时
  cd backend; python -m pytest tests -q -k forum            ← 域测

红线提醒（自动生成，不是死文案）
  · 3 个 .vtj 页 raw=true → 禁 vtj_sync_vue_to_dsl（R2）
  · 改 .vtj 的 <template> 需用户逐次授权 + .bak_<日期>（R3）
  · 新增接口前缀必须是 /api/forum，不得新开 /api/v1（R11）
```

> 上面每个数字都是**刚从仓库实测得来**（`api_surface.json` 里 `forum.py` 的 prefix 与 12 条 endpoints、3 个 raw 页标记、6 个测试文件），不是编的示例。

---

## §2 三个子命令

| 命令 | 作用 | 主要数据源 |
|---|---|---|
| `qbdm.py module <关键字>` | 一个模块的全貌（端点/页面/测试/门禁/提醒） | `api_surface.json`、`.vtj/projects/*.json`、`src/router/index.ts`、`backend/tests`、`src/**/*.spec.ts` |
| `qbdm.py design <关键字> --state design\|test\|optimize` | 打印该模块的 D1–D10 / T1–T8 / O1–O8 清单（带验收命令） | 上述 + 内置模板（来自作战卡 v2，不重复维护） |
| `qbdm.py gate --role BE\|FE\|API\|DATA` | 打印该角色**必跑**的门禁命令清单 | 门禁脚本目录 + v4 §8 矩阵 |

可选第 4 个（默认关闭）：`--json` 输出机器可读结果，给 subagent 用，省一次人工转述。

---

## §3 数据从哪来（全部只读，零依赖）

| 要什么 | 从哪读 | 为什么不用别的 |
|---|---|---|
| 端点 + 函数名 + 行号 | `backend/data/refactor_baseline/api_surface.json` | 已冻结的契约基线，比 grep 源码稳 |
| 页面是否 raw | `.vtj/projects/*.json` 的 `pages[].raw` | 这是唯一权威标记（实测 47 个 raw） |
| 页面归属哪个端 | 文件名前缀 + `src/router/index.ts` | 与 R5（前缀不改名）一致 |
| 测试清单 | `backend/tests/test_*.py`、`src/**/*.spec.ts` | 文件名约定 |
| 门禁清单 | `backend/scripts/gates/*.py` | 目录即事实 |

不读 `题库/`、不读 `static/`、不连数据库、不联网络。

---

## §4 实现约束

| # | 约束 | 理由 |
|---|---|---|
| 1 | 纯 Python 标准库（`json/os/pathlib/re/sys`），不装任何依赖 | 换机器就能跑 |
| 2 | **只读**：绝不写任何文件 | 工具不该有副作用 |
| 3 | 输出 UTF-8（`PYTHONIOENCODING` 兜底），Windows 控制台不崩 | 实测坑 F18 |
| 4 | 找不到模块时**明确报错并列候选**，不返回空表 | 防止"看起来成功" |
| 5 | 每个数据源打印**时间戳/提交号** | 数据过期能一眼看出 |
| 6 | 单文件 ≤ 300 行 | 可维护 |

---

## §5 验收标准

| # | 命令 | 期望 |
|---|---|---|
| 1 | `python scripts/qbdm/qbdm.py module forum` | 输出 12 条端点、3 个 raw 页、6 个测试，与本文 §1 预演一致 |
| 2 | `python scripts/qbdm/qbdm.py module 不存在的名字` | 退出码 1 + 候选模块列表 |
| 3 | `python scripts/qbdm/qbdm.py gate --role FE` | 列出 `gate_l5_frontend_contract.py` 等 3–4 条 |
| 4 | 交叉校验 | 脚本统计的端点条数 == 手工从 `api_surface.json` 求和的条数（12）；页面 raw 标记 == `.vtj/projects` 实测值 |
| 5 | 与现有基线不冲突 | 不改任何业务文件；`npx vitest run` / `npm run typecheck` / pytest 基线不变 |

---

## §6 风险

| # | 风险 | 对策 |
|---|---|---|
| 1 | `api_surface.json` 过期（改了端点没回填基线） | 输出里打印基线文件时间；并对源码做一次轻量 cross-check（可选 `--verify`） |
| 2 | 模块关键字匹配不到（中英文命名不一致） | 支持中文别名表（forum/论坛、错题/wrongbook…），别名表单独一个小节维护 |
| 3 | 工具被当成"事实来源" | 输出头部永远打"数据源 + 时间"，与事实基线 v1 交叉引用 |
| 4 | 有人拿它当门禁跑 | 明确写：它**不执行**任何门禁，只打印命令 |

---

## §7 分期

| 阶段 | 内容 | 预计 |
|---|---|---|
| v1（本方案） | `module` + `gate` 两个子命令 | ✅ 已完成（`76a36b8`） |
| v1.1 | `design` 三态清单 + `--json` | 后续按需 |
| 不做 | 自动跑门禁、自动改代码（明确拒绝：工具只读） | — |

---

## §8 需要你确认（2 条）

1. **§1 的输出格式**：就按这个样子（中文标题 + 分类 + 行号 + 红线提醒），还是要更短/更长？
2. **是否要 `--json` 模式**：给 subagent 用能省一次转述；不要也行。

---

## §9 与既有文档的关系

- 本工具**替代**旧文档里不存在的 `scripts/qbdm/qbdm.py` 承诺（事实基线 G2）。
- 它只**打印**事实，不做判断：判断规则仍在 `题库设计模式_v4.md` 与角色卡 v2。
- 建立后需回填：事实基线 F10 补一行"qbdm CLI 存在"；缺口 G2 状态改为"已建"。
