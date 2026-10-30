# docs/ 文档索引

> 本索引由 `solve_problems_files/README.md` 迁移而来（目录分层重构）。
> 归档规则：展示方案的同时落盘；定稿当场归档；归档即更新本索引。

## 目录说明

| 目录 | 用途 |
|---|---|
| `design/` | 历史设计方案（95 份，含 v1 旧版容器化方案等） |
| `plans/` | 实施计划与当前活跃设计（24 份） |
| `ops/` | 使用/运维手册（环境、启动、拉取更新、数据库、共享、排错） |
| `archive/` | 已归档的历史文档（37 份） |
| `superpowers/` | Superpowers 工作流产物（specs/plans 子目录） |

## 活跃文档索引

| 文档 | 版本 | 状态 | 说明 |
|---|---|---|---|
| `superpowers/specs/砺安题库终态总体架构_v2.0.md` | v2.1 | ✅ 已批准（D1–D17）；F0–F6、F2b-1 与 F2b-2 已执行 | **终态架构 + 多库一致性底座**：1 SoT（SQLite）+ 4 类可重建投影 + 事务 Outbox/幂等投影/对账；对草案 10 处硬修正、F0–F6 主干路线、L7 门禁（当前 21 项）、Agent 规约；端×角色（3×3）一致性与空库审计；**v2.1 新增容量预算(§17)/数据卫生(§18)/写入准确性(§19)/三端通信 SLO(§20)/可落地自证(§21)**；业务功能模块不在此方案 |
| `superpowers/specs/main分支启动阻断与考试链路修复_报告_20261026.md` | v1 | ✅ 已合并 main（2026-10-26） | main 报告 P0-1/2/3 + P1-1 + P1-3 + P3-1 修复：Pydantic v2 `ConfigDict`、考试路由导入收敛、日志目录自建+降级、`question_count` 以关联行数为唯一口径（含存量修复脚本）；3 条新回归测试 + 真机烟测 health/login/取题/开考/交卷全 200；全量 650 passed（8 失败均为既有环境项） |
| `superpowers/specs/资料卡片导入D1类型覆盖缺陷修复_报告_20261027.md` | v1 | ✅ 已修复（2026-10-27，分支 `fix/D1-import-card-type`） | D1 阻断缺陷：xlsx 卡片导入的 `type` 被启发式分类器覆盖成 `article`，卡片进文章区、翻卡 UI 永不触发。修复：卡片分支按输入契约直写 `type='card'` 并删除多余 classify 调用；新增 2 条回归测试（xlsx→card、长 docx→article），资料域 39 passed；附存量清洗 SQL 与 D2–D8 交接说明 |
| `superpowers/plans/F1一致性内核_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-26，Step 1–7 完成，tag `foundation-v1-f1`） | F1：7 表 + Outbox→投递→投影→对账 + `content_integrity.py`/`db_inventory.py` + L7 门禁；21 文件、7 步、每步独立验证与回滚；不改 `api/v1`/`models`/`.vtj` |
| `superpowers/specs/预览数据治理与容量回收_报告_20261026.md` | v1 | ✅ 已执行（2026-10-26） | 571 行 / 257.76 MB 超期预览外置 gzip 后置摘要，`auto_vacuum=INCREMENTAL` + VACUUM，主库 **303.17 → 46.52 MB**；四表行数与指纹不变，`integrity_check=ok` |
| `superpowers/plans/F2通信统一与写入守卫_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-26，Step 1–7 完成，tag `foundation-v1-f2`） | F2：WS 协议 v2（seq/scope）+ Redis 中继 + 多 worker fail-fast + 前端 data-changed 消费/重连重同步 + 92 条路由 roles + 写入守卫 6 类；7 步、无迁移、无新表；F2b 写调用点迁移未做 |
| `superpowers/specs/F2通信统一与写入守卫_报告_20261026.md` | v1 | ✅ 已交付（2026-10-26，tag `foundation-v1-f2`） | F2 交付报告：协议/中继/fail-fast/前端去重/路由 roles/6 类写入守卫；L7 15/15、全量门禁 9/10（L2 既有基线）、62 后端 + 342 前端测试；Redis 双客户端各 1 条无重复；明确 F2b 未做 |
| `superpowers/plans/F3对象存储与媒体资产_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-26，Step 0–8 完成，tag `foundation-v1-f3`） | F3：6 个用户媒体新写入口切 `media_assets` + ObjectStore（local 默认 / MinIO 可选）+ `/media/{asset_id}` 只读代理；只接新增、存量 static/uploads 零搬迁；sha256 物理去重、tombstone、对账/GC、L7-16；37 文件 / 9 步 / A1–A16 全 PASS / 开关回滚 |
| `superpowers/specs/F3对象存储与媒体资产_报告_20261026.md` | v1 | ✅ 已交付（2026-10-26，tag `foundation-v1-f3`） | F3 交付报告：`media_assets` + local/MinIO 对象存储 + `/media/{asset_id}`；A1–A16 逐条证据；42 个 F3 专项测试、后端 695 passed、前端 342、L7 15 PASS/1 既有 WARN、gate_all 9/10（L2 既有）；存量 141321 static 文件字节零变化；遗留与回滚 |
| `superpowers/plans/F2b-1事件总线同事务化_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-27，Step 0–9 完成，tag `foundation-v1-f2b1`） | F2b-1：20 个 `record_user_action` + 2 个 `events.publish` 迁入 Outbox 同事务；Dispatcher 文件锁单写者 + `foundation_inbox` 幂等 + 按用户/角色定向 `data-changed` + L7-17；35 文件；F2b-2（useDataSync/9 组合/?since）未开始 |
| `superpowers/specs/F2b-1事件总线同事务化_报告_20261027.md` | v1 | ✅ 已交付（2026-10-27，tag `foundation-v1-f2b1`） | F2b-1 交付报告：20+2 调用点同事务、文件锁单写者、inbox 幂等、roles 定向；A1–A16 逐条证据；后端 705 passed、前端 342、L7 16P/1W、gate_all 9/10（L2 既有）；明确 A2/A5–A7 服务/协议级限制，F2b-2 未开始 |
| `superpowers/plans/F2b-2断线重连增量补发与前端useDataSync_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-27，Step 0–8 完成，tag `foundation-v1-f2b2`） | F2b-2：`data-changed` 带 Outbox 游标 `oid`；重连发 WS `sync{since}`，服务端按用户/角色补发可见事件；超 200 条/超 24h/开关关闭一律 `truncated` 回退一次全量；新增 `useDataSync` 接 2 个手写页，75 个 VTJ 页模板零改动；L7 17→18；无新表/迁移/依赖；A1–A18 与 9×3 协议矩阵 |
| `superpowers/specs/F2b-2断线重连增量补发_报告_20261027.md` | v1 | ✅ 已交付（2026-10-27，tag `foundation-v1-f2b2`） | F2b-2 交付报告：`oid` 游标、WS `sync{since}` 可见性补发、24h/200 条截断、`useDataSync` 两页接入；A1–A18 证据与 27 行 9×3 协议矩阵（协议级，非真机）；后端 725、前端 354、L7 17P/1W、gate_all 9/10（L2 既有）；明确未做 9 个真实浏览器 |
| `superpowers/plans/F4文档投影与DocumentStore_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-27，Step 0–8 完成，tag `foundation-v1-f4`） | F4：local/Mongo DocumentStore + 3 集合（exam_resources/import_snapshots/forum_contents）+ Outbox 投影 + 回填/对账/双读日志 + L7-19；单文档 8 MiB 上限、pymongo 可选、默认 local；不改读路径/API/.vtj；A1–A18、D1–D9 |
| `superpowers/specs/F4文档投影与DocumentStore_报告_20261027.md` | v1 | ✅ 已交付（2026-10-27，tag `foundation-v1-f4`） | F4 交付报告：DocumentStore 三实现/3 集合/4 事件/回填 1675 条/对账 drift=0/双读 500 条零差异；A1–A18 逐条证据；后端 789 passed、前端 354、L7 18P/1W、gate_all 8/10（L2 既有、L4 服务未启）；偏差与限制见第 6 节 |
| `superpowers/plans/F5图投影与GraphStore_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-27，Step 0–8 完成，tag `foundation-v1-f5`） | F5：GraphStore（local 默认 / Neo4j 可选）+ 迁移 003 两张图投影表 + 知识点/题目节点与三类关系（先修/并行/实例化）+ 回填/对账/只读内部函数 + L7-20；不改 API/.vtj/业务表，不做增量事件；D1–D9 已批准 |
| `superpowers/specs/F5图投影与GraphStore_报告_20261027.md` | v1 | ✅ 已交付（2026-10-27，tag `foundation-v1-f5`） | F5 交付报告：GraphStore 三实现/2 表/3 类关系/回填 3823 节点 4354 边/对账 drift=0/抽样 100 零差异；A1–A16 逐条证据；后端 818 passed、前端 354/typecheck 0、L7 19P/1W、gate_all 8/10（L2/L4 既有）；Neo4j 仅 fake HTTP 契约测试，真实冒烟未执行 |
| `superpowers/plans/F6向量投影与AI端口_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-28，Step 0–8 完成，tag `foundation-v1-f6`） | F6：VectorStore（local/milvus）+ EmbeddingPort（off/hash/http）+ text_questions 3122 题离线索引 + 回填/对账/一致性 + L7-21；默认关闭，hash 仅隔离验证且标 degraded；不改 .vtj/API/表/迁移；真实 Milvus 与语义模型依赖用户环境 |
| `superpowers/plans/复合题材料与答题页滚动修复方案_v1.md` | v1 | ✅ 主体已提交（`7505e13`）；2026-10-29 增量已提交（`9fe62a5`，P1–P6 + 做题/背题/图片渲染/三端吸顶/组卷交互/交卷与重考 + 教师/管理端编辑图片预览 + 2021/2023 复合题回填；targeted 19 passed，quick 4/4） | 教师端复合题材料缺失/子题关联弱、学生答题页滚动不同步的根因+递归拆解：5 条链路（存量 group_id=0、JSON 导入丢材料、图片材料未解析、exam API/智能组卷不认组、paper_answer 滚动与材料）；P0 备份→P1 解析器→P2 存量修复→P3 API/组卷→P4 script-only 滚动+材料注入→P5 导入防丢组/预览警告→P6 验收；另含整组超配显式提示、整组替换、答题页吸顶材料面板与“材料一/资料 2”分层高亮、`questionRender.js` 统一图片渲染、`exam_record` 唯一约束迁移；零 raw 模板改动；实施记录与遗留见方案 §5.1 |
| `superpowers/specs/题目入库知识图谱与四库映射_v1.md` | v1 | 🚧 P0 已批准；P1 已实施（2026-10-30，P2–P5 待执行） | 四库题目域本体：题组/成员/材料图/题干图/选项图/解析图/导入批次六元组；图、文档、向量、图片资产四类投影的 canonical ID、边、集合、入库闸门 P0–P5 与验收 V1–V10；不新增业务事实表；P1 已登记 937 条图片资产（active 896 / missing 41），显式引用可解析率 99.2% |
| `superpowers/specs/F6向量投影与AI端口_报告_20261028.md` | v1 | ✅ 已交付（2026-10-28，tag `foundation-v1-f6`） | F6 交付报告：local/Milvus 适配器、off/hash/http Embedding、3122 题隔离回填、对账/盘点/一致性脚本、/health 与 L7-21；A1–A16 逐条证据；后端全量、前端 354、L7 20P/1W、gate_all 结果；真实 Milvus/语义检索未执行 |
| `ops/外部数据库与中间件手动下载清单_v1.md` | v1 | ✅ 已落盘（2026-10-27） | 明确“当前不需要下载任何外部库”；列出 SQLite/Redis/MinIO/MongoDB/Neo4j/Milvus/PG/MySQL 的用途、F4–F6 前置、官方入口、建议版本、Windows/Docker 安装、端口、许可、自检、凭据与回滚；含本机实测与用户手动勾选清单 |
| `superpowers/specs/F1一致性内核_报告_20261026.md` | v1 | ✅ 已交付（2026-10-26，tag `foundation-v1-f1`） | F1 7 表 + Outbox/投递/投影/对账 + `/health/foundation` + L7 15 项；26 测试通过；13 条验收 10 PASS / 2 PARTIAL / 1 环境项；F0 内容指纹口径修正（以备份库重算，四表 MATCH）；性能增幅未达 5% 与 6 类坏数据校验移交 F2 |
| `superpowers/specs/F0基线冻结与内容完整性_报告_20261026.md` | v1 | ✅ 已执行（2026-10-26） | F0：tag `foundation-v1`@`2ec9cc7`、`sqlite3.backup()` 备份（303.17 MB，integrity ok，四表指纹一致）、`gate_all --quick` 4/4 PASS；内容完整性基线：复合题 33 题挂组、组 11 空、293 图片行中 13 行文件缺失、10 个 `[IMAGE:]` 令牌未解析、申论 24 题未挂组（只登记不删） |
| `superpowers/specs/题库设计模式_v3.md` | v3.0 | ✅ 生效（2026-10-25） | **「题库设计」模式（会话执行版）**：标准/创造/PTC 分层、九角色落地形态（subagent 等价 agent-team）、设计/测试/优化三态管线、声明头扩展、技能+MCP+工作流绑定、12 条实测坑、A21–A26 |
| `superpowers/specs/题库设计模式_v2.md` | v2.0 | ✅ 生效（2026-10-25，用户批准） | **模块层**：25 模块台账、设计 D1–D10 / 优化 O1–O8 / 测试 T1–T8、变更影响面五步、Q0–Q6 裁剪、A14–A20、G6–G10 |
| `superpowers/specs/题库设计模式_模块作战卡_v1.md` | v1 | ✅ 已落盘（2026-10-25） | 热加载一屏版：开工三步、D/O/T 速查、五条硬约束、收尾四问；领到模块任务只读此卡 |
| `design/题库模块台账_v1.md` | v1 | ✅ 机器生成（2026-10-25） | 25 模块 × 端点/页面/测试/事件；由 `scripts/qbdm/gen_module_ledger.py` 从 api_surface + 域卡 + 实际文件生成，`--check` 可查漂移 |
| `superpowers/specs/题库设计模式_v1.md` | v1 | ✅ 生效（2026-10-25，用户批准） | 九角色（ARCH/PM/DATA/BE/API/FE/SEC/QA/DOC）+ 角色切换协议 + Q0–Q6 七阶段 + 五零 token 指标（Z1–Z5）+ 分支拓扑细则 + 门禁矩阵 + 13 条反模式；红线仍以 `AGENTS.md` 为唯一出处 |
| `superpowers/specs/题库设计模式_角色卡_v1.md` | v1 | ✅ 已落盘（2026-10-25） | 热加载版（3.8KB）：每任务只读此卡完成角色切换——声明头模板、九卡速查、预算/装载、一屏流程与分支命令 |
| `design/题库领域词表_v1.md` | v1 | ✅ 已落盘（2026-10-25，§8 两条置信度待复核） | 题库领域唯一事实来源词典：实体 30 条（表.字段精确到列）、计数口径 D1–D6（题目数/复合题组数/试卷题数/正确率/错题数/可见题）、禁用同义词 10 条、端点归属 14 项、实测基线 B1–B11 |
| `plans/学生端模块化设计方案_v1.md` | v1 | ✅ 已定稿（2026-10-18，已修订） | 学生端 20 业务模块化（⑱⑲⑳ 未开发）：星型横向数据流（成就成长枢纽）、三角色+三设备纵向通信、一人一分支协作规范、VTJ 红线守护 |
| `plans/学生端模块化设计方案_v1_实施计划.md` | v1 | 🚧 执行中（P1✅ P2✅ P3 手工验收待执行） | 三阶段 123 任务：基础设施 33 ✅ + 逐域改造 82 ✅ + 验收 8（P3-01~07 真机手工验收待用户执行）；⑱⑲⑳ 排除 |
| `plans/分支使用说明书_v1.md` | v1 | ✅ 已定稿（2026-10-18） | 多人协作独立文档：红线速查+环境准备+一人一分支+20 模块所有权映射+域卡模板+跨域通信规则+合并验收+冲突处置 |
| `ops/整体系统使用和结构说明_v1.md` | v1 | ✅ 现行（2026-10-22） | 系统目录结构、克隆与启动、分支拉取更新、设计完成收尾、SQLite 存储/备份/恢复、多人共享、验收与排错 |
| `plans/学生端模块化基线快照_v1.md` | v1 | ✅ 已定稿（2026-10-18） | P1-01 实测基线：75 页/73 JSON/343 端点/pytest 278-17-3/门禁 7-8/13 调用点 |
| `plans/学生端模块化_P3手工验收核对表_v1.md` | v1 | 📋 待用户执行 | P3-01~07 真机手工验收执行清单：17 域逐项勾选 + 事件观测记录位 + 三设备一致性/WS 兜底演练步骤 + 缺陷记录区 |
| `plans/三端数据流一致性修复方案_v1.md` | v1 | 🚧 执行中（P0 ✅；P1-1 ✅；P1-2~P1-9 待执行） | 6 项三端数据流一致性问题的根因+修复方案：统一可见性/计数口径、主观题渲染、考点 canonical 展示、材料归属与教师编辑、存量修复与验收；P0-P4 分阶段，含 7 个待拍板决策 |
| `plans/三端数据流一致性修复方案_v2.md` | v2 | 🚧 执行中（已批准；T-01~T-12 ✅；P1/P2/P3 完成；RT-1~RT-9 ✅，RT-10 手工验收待执行） | v1 的完整替代版：6 问题全覆盖 + 91 L2/427 L3/518 节点树 + 别名隐藏 + `sub_category_id` + §14 RT 富文本 |
| `superpowers/specs/三端数据流一致性修复方案_v2_验收报告_20261024.md` | v2 | ✅ 已生成（T-12） | 生产迁移前后计数、51 项验收、回滚演练、A1~A10 状态与遗留 |
| `plans/dsh-optimization-master-plan.md` | v1 | ✅ 已落盘（2026-10-25） | dsh×DeepInfer 联合执行总方案：角色↔subagent 矩阵、Token 节流、R1–R12 与五步法、CTC 十问、阶段阻断；含实测校正与本次落地 |
| `superpowers/specs/数据库静默回落事故_报告_20261025.md` | v1 | ✅ 已修复（2026-10-25） | `.env` 缺失→默认库指向 `example_db.sqlite`（旧 schema、0 题、4 账号）导致全站 500/登录失败；真库 3357 题完好；新增启动期 db-guard 与 6 项测试 |
| `superpowers/specs/导入配对与答案卷识别_报告_20261025.md` | v1 | ✅ 已修复（2026-10-25） | 答案卷被按题干切块导致 125 vs 95 计数不一致；新增答案卷识别 + 题号锚点解析（125 条对齐），`/confirm` 增加答案卷闸门；22 套实测 19 套对齐 |
| `superpowers/specs/OCR链路恢复_报告_20261025.md` | v1 | ✅ 已恢复（2026-10-25） | MinerU 3.4.5 / PaddleOCR 2.7 均可用但被参数拖死：固定 600s 超时 vs 71.2s/页、OCR 仅 8 页、缓存跨引擎污染。改为按页超时、30 页上限、CPU 线程/免方向分类、缓存引擎隔离 |

| `superpowers/specs/多人协作Git网络稳定方案_v1.md` | v1 | ✅ 已定稿（2026-10-29） | 同伴 ghproxy 镜像停服导致 pull 失败：清镜像改写 + canonical/SSH-443 回退 + 过滤克隆（`.git` 917 MB → 1.1 MB）+ bundle 离线交接 + 一任务一分支规约；配套 `scripts/dev/git-collab-doctor.ps1` |

## 变更记录

- 2026-10-30：**四库 P1 图片资产登记已实施**：新增 `backend/app/services/question_media.py`、`backend/scripts/register_question_media.py`、`backend/tests/test_question_media.py`；`media_service.KINDS` 增加题干图/选项图/解析图/组材料图四类；扫描 1171 条引用，登记 937 条资产（active 896 + missing 41），对象存储 896 个文件 27.7 MB；显式引用可解析率 99.2%，32 条 bare legacy marker 与 9 条缺失文件全部标 missing；二次 `--apply` inserted=0 验证幂等；真实库执行前已用 `sqlite3.backup()` 备份（`question_bank_pre_media_register_20261030_153622.db`）；未改题目数据与 `/static` 原文件
- 2026-10-29：**题目入库知识图谱与四库映射设计落盘**：新增 `superpowers/specs/题目入库知识图谱与四库映射_v1.md`；实测 3489 题/103 挂组/38 组/`media_assets` 0 行，定位“四库底座已有、题目域本体缺失”；定义 QuestionGroup/Question/MediaAsset/ImportBatch 节点与 HAS_MEMBER/HAS_*_IMAGE/IMPORTED 边、`question_documents`/`group_documents` 文档集合、`text_materials` 向量集合、图片资产登记与 G0–G8 入库闸门；分 P0–P5 实施，D1–D6 待用户拍板；同轮教师/管理端编辑弹窗图片预览与 2021/2023 复合题回填补齐已提交 `9fe62a5`
- 2026-10-29：**多人协作 Git 网络稳定方案落盘**：同伴 `git pull` 报 `Failed to connect to mirror.ghproxy.com port 443`，实测为客户端 remote/`url.insteadOf` 指向已停服镜像（`mirror.ghproxy.com` DNS 已不解析），叠加 `.git` 917 MB 全量传输超时被误判为网络故障；方案含清镜像改写、canonical/SSH-443 三级回退、过滤克隆（实测 23.7 s / `.git` 1.1 MB）、bundle 离线交接、一任务一分支 + rebase 规约与验收清单；新增 `scripts/dev/git-collab-doctor.ps1`（诊断 / `-Fix` / `-Bundle` / `-FromBundle`）；报告见 `superpowers/specs/多人协作Git网络稳定方案_v1.md`
- 2026-10-29：**做题/背题、图片渲染、三端材料吸顶、智能组卷交互、交卷与重考修复（已提交 `6a2a3c5`）**：新增 `src/utils/questionRender.js` 统一还原 `<img>/[IMAGE:]/&lt;img&gt;` 三种形态并统一 `paper_result/exercise/solution` 渲染；`exercise.vue` 增加做题/背题切换与交卷内联成绩条；新增 `src/utils/materialDock.js` 供学生/教师/管理三端材料吸顶共用（raw 页零模板改动）；`smart_exam.vue` 修正题型预设 ID、内联超配提示/组统计/题组徽标，`smart_exam.py` 支持整组替换并返回 `group_id`；`paper_answer.vue` 交卷请求体改为整映射，修复 422；新增并执行 `backend/scripts/migrate/migrate_exam_record_drop_unique.py` 移除历史库 `uk_paper_user`，`start_exam` 复用未完成记录；targeted 18 passed、typecheck 0 错误、build:prod 成功、quick 门禁 4/4
- 2026-10-28：**复合题材料、P5 防丢组、整组超配提示、答题页吸顶材料已完成并提交（`7505e13`）**：解析器支持“（三）[IMAGE:…]”图片材料并新增回归测试；存量重建组 24–32、挂组题 69（2024 申论 16、2025 行测 20，组 31 含 2 图）；exam API 返回组字段；新增 `paper_group_selector.py` 并接入三处组卷整组抽样；P5 在缺材料时仍建组保留子题关联并标 `need_review`，预览/导入显式警告；组卷响应带 `over_quota/over_quota_reason` 并前端提示；`paper_answer.vue` 仅改 script 实现工具栏 fixed、滚动↔索引↔吸顶材料面板联动、材料一/资料 2 分层高亮、图片去重；真实 2025 安徽行测 PDF 与浏览器 paper 54/55 验收通过；残余风险：纯图片材料整段丢失且题干无组头文本时规则警告抓不到；targeted 16 passed、quick 门禁 4/4，已提交
- 2026-10-28：**复合题材料与答题页滚动修复方案落盘（待批准）**：新增 `superpowers/plans/复合题材料与答题页滚动修复方案_v1.md`；实测 2024/2025 申论与 2025 行测 `group_id` 全为 0，`exam` 取题不返回组字段，`auto_generate_paper` 扁平抽题拆组，`paper_answer` 滚动不更新索引；方案按 P0 备份→P1 解析器（含图片材料）→P2 存量修复→P3 API/智能组卷→P4 script-only 滚动+材料注入→P5 导入防丢组→P6 验收，零 raw 模板改动
- 2026-10-28：**F6 向量投影与 AI 端口执行完成**：VectorStore 协议 + local/Milvus 实现 + EmbeddingPort（off/hash/http）+ text_questions 投影/回填/对账/盘点/一致性 + `/health/foundation` vector 段 + L7-21；隔离根 hash 验证 planned=3122/written=3122（生产向量索引未写入，真实语义检索本次不做）；默认 `VECTOR_BACKEND=off`、`EMBEDDING_ENABLED=false`，Milvus 实机冒烟未执行；无新表/迁移/依赖、无 .vtj/API 改动；main 单提交 + tag `foundation-v1-f6`；报告见 `superpowers/specs/F6向量投影与AI端口_报告_20261028.md`
- 2026-10-28：**F6 向量投影与 AI 端口实施计划落盘（已批准并执行）**：新增 `superpowers/plans/F6向量投影与AI端口_实施计划_v1.md`；范围限定 VectorStore（local/milvus）+ EmbeddingPort（off/hash/http）+ text_questions 3122 题离线索引 + 回填/对账/一致性脚本 + L7-21；默认 `VECTOR_BACKEND=off`、`EMBEDDING_ENABLED=false`，hash 仅用于验证并标 degraded；不改 .vtj/API/业务表/迁移；D1–D9 待用户批准，真实 Milvus 与语义模型依赖用户环境
- 2026-10-27：**F5 图投影与 GraphStore 执行完成**：GraphStore 协议 + local/Neo4j 实现 + 迁移 003 两张图投影表 + 知识点/题目节点与先修/并行/实例化三类关系 + 回填/对账/只读内部函数 + `/health/foundation` graph 段 + L7-20；生产回填 3823 节点/4354 边，二次 apply 节点 0 写入，对账 run_id=ac79a8836136480c status=ok、抽样 100 零差异；后端 818 passed、前端 354/typecheck 0、L7 19P/1W、gate_all 8/10（L2/L4 既有）；无新依赖、无 .vtj/API/业务表改动；main 单提交 + tag `foundation-v1-f5`；报告见 `superpowers/specs/F5图投影与GraphStore_报告_20261027.md`
- 2026-10-27：**F5 图投影与 GraphStore 实施计划落盘（待批准）**：新增 `superpowers/plans/F5图投影与GraphStore_实施计划_v1.md`；范围限定 GraphStore（local 默认 / Neo4j 可选）、迁移 003 两张图投影表、知识点/题目节点与三类派生关系、回填/对账/只读内部函数与 L7-20；不改 API/.vtj/业务表，不做增量事件，不实现 F6；D1–D9 待用户批准
- 2026-10-27：**F4 文档投影与 DocumentStore 执行完成**：local/Mongo DocumentStore + 3 集合（exam_resources/import_snapshots/forum_contents）+ 4 个 Outbox 事件同事务接入（试卷发布/更新、题目/资料导入、论坛发帖/删帖/评论）+ 回填/对账/双读抽样 + L7-19；生产回填 1675 条、二次 apply 全 0，对账 drift=0，双读 500 条零差异；后端 789 passed、前端 354/typecheck 0、L7 18P/1W、gate_all 8/10（L2 既有、L4 服务未启）；无新表/迁移/依赖、无 .vtj 改动；main 单提交 + tag `foundation-v1-f4`；报告见 `superpowers/specs/F4文档投影与DocumentStore_报告_20261027.md`
- 2026-10-27：**F4 文档投影实施计划落盘（待批准）**：新增 `superpowers/plans/F4文档投影与DocumentStore_实施计划_v1.md`；范围限定 local/Mongo DocumentStore、3 个文档集合、4 个 Outbox 事件、回填/对账/双读日志与 L7-19；现有读路径/API/表结构/.vtj 零改动，pymongo 可选，默认 local；D1–D9 待用户批准
- 2026-10-27：**前端端口统一 9527**：删除 5173 引用（12 个文档 + Playwright 用例），`vite.config.ts` 显式固定 dev/preview 端口 9527；Playwright 导入用例默认跳过，仅 `RUN_PLAYWRIGHT_E2E=1` 且 9527/8000 就绪时运行；全量后端 755 passed/4 skipped/2 xfailed；main 单提交 `f0d9ea5`
- 2026-10-27：**F2b-2 断线重连增量补发执行完成**：`data-changed` 带 Outbox 游标 `oid`；WS 重连 `sync{since}` 按用户/角色补发可见事件；超 200 条/超 24h/开关关闭回 `truncated` 并全量兜底；新增 `useDataSync` 并接 `RecentPracticeRecords` 与 `profile.vue`，75 个 VTJ 页模板零改动；L7 17→18；后端 725 passed、前端 354 passed/typecheck 0；main 单提交 + tag `foundation-v1-f2b2`；报告见 `superpowers/specs/F2b-2断线重连增量补发_报告_20261027.md`
- 2026-10-27：**F2b-2 实施计划落盘（待批准）**：`data-changed` 增加 Outbox 游标 `oid`；WS 重连 `sync{since}` 增量补发，服务端按用户/角色过滤；超 200 条/超 24h/开关关闭回 `truncated` 并全量兜底；新增 `useDataSync`，只接 `RecentPracticeRecords` 与 `profile.vue`，75 个 VTJ 页模板零改动；L7 17→18；无新表/迁移/依赖；计划见 `superpowers/plans/F2b-2断线重连增量补发与前端useDataSync_实施计划_v1.md`
- 2026-10-27：**外部数据库与中间件手动下载清单落盘**：明确当前不需要下载任何外部库；给出 SQLite/Redis/MinIO/MongoDB/Neo4j/Milvus/PG/MySQL 的 F4–F6 前置、官方入口、建议版本、Windows/Docker、端口、许可、自检、凭据规则与回滚；含本机实测与用户勾选清单；见 `ops/外部数据库与中间件手动下载清单_v1.md`
- 2026-10-27：**F2b-1 事件总线同事务化执行完成**：20 个 `record_user_action` + 2 个 `events.publish` 迁入 Outbox 同事务；Dispatcher 文件锁单写者 + `foundation_inbox` 幂等 + 按用户/角色定向 `data-changed`；L7 16→17；后端 705 passed/2 xfailed、前端 342/typecheck 0、L7 16P/1W、gate_all 9/10（仅 L2 既有）；main 单提交 + tag `foundation-v1-f2b1`；F2b-2 未开始。报告见 `superpowers/specs/F2b-1事件总线同事务化_报告_20261027.md`
- 2026-10-27：**F2b-1 实施计划获批并开始执行**：20 个 `record_user_action` + 2 个 `events.publish` 迁入 `foundation_outbox` 同事务；Dispatcher 文件锁单写者 + `foundation_inbox` 幂等 + 按用户/角色定向 `data-changed` + L7-17；不改 API 出入参、不新增表/迁移/依赖、前端零改动；F2b-2（useDataSync、9 组合、?since）另立计划；执行结果见上一条。
- 2026-10-26：**F3 对象存储与媒体资产执行完成**：37 文件（19 改 + 18 新增）单提交 main，tag `foundation-v1-f3`；`media_assets` 1 表 + ObjectStore（local/MinIO，零新依赖）+ `/media/{asset_id}` 代理；6 个 /uploads 新写入口接线；存量 static 141321 文件与 uploads 5673 文件字节零变化；A1–A16 全 PASS；后端 695 passed、前端 342 passed、L7 15 PASS/1 既有 WARN、gate_all 9/10（L2 既有）；报告见 `superpowers/specs/F3对象存储与媒体资产_报告_20261026.md`
- 2026-10-27：**F3 对象存储与媒体资产实施计划已批准并开始执行**：新增 `docs/superpowers/plans/F3对象存储与媒体资产_实施计划_v1.md`；范围限定 6 个 /uploads 新写入口，`media_assets` 1 表 + ObjectStore(local/MinIO) + `/media/{asset_id}` 代理，存量 static 4.3 GB 与旧 uploads 零搬迁；物理 sha256 去重、tombstone、对账/GC、L7 15→16、A1–A16 验收与开关回滚。
- 2026-10-26：**F2 通信统一与写入守卫交付完成**：WS 协议 v2（seq/scope）、Redis 中继与多 worker fail-fast、统一 `ws_relay.emit` 出口、前端 `data-changed` 消费/seq 去重/重连重同步、92 条路由 roles 补全、写入守卫 6 类；L7 PASS=15/WARN=0/FAIL=0，全量门禁 9/10（L2 既有基线），62 后端 + 342 前端测试通过，tag `foundation-v1-f2`；新增交付报告并明确 **F2b（13 个写调用点迁 Outbox / Redis Stream / 定向派生）未做**。
- 2026-10-26：**F2 实施计划落盘（待批准）**：WS 协议 v2（seq/scope）、Redis 中继与多 worker fail-fast、前端 `data-changed` 消费与重连重同步、57 条路由 roles 补全、写入守卫 6 类；21 个文件 + 7 步 + 13 条验收；无新表、无迁移。
- 2026-10-26：**F1 一致性内核交付完成**：7 表 + 事务 Outbox + 投递/投影 + 对账 + `/health/foundation` + L7 门禁 15 项；26 个测试通过，L7 PASS=13/WARN=2/FAIL=0，tag `foundation-v1-f1`；新增交付报告（含 F0 指纹口径修正：以受 R8 保护的备份库重算，四表与主库 MATCH）。
- 2026-10-26：**F1 实施计划落盘（待批准）**：21 文件 / 7 步 / CTC 十问 / §9.2.1 13 条验收映射；`gc_previews.py` 归档路径统一为 `scripts/audit/`。
- 2026-10-26：**预览数据治理完成**：571 行 / 257.76 MB 超期预览 gzip 外置（571 个文件 / 36.76 MB）并置摘要；主库 303.17 MB → 46.52 MB（−84.7%），`auto_vacuum=INCREMENTAL`、`freelist=0`、`integrity_check=ok`；四表指纹与 F0 基线一致。新脚本 `backend/scripts/audit/gc_previews.py`（默认 dry-run，`--baseline-db` 强制基线比对）。
- 2026-10-26：**F0 基线冻结完成**：tag `foundation-v1`@`2ec9cc7`；`sqlite3.backup()` 备份 303.17 MB（integrity/quick ok、73 表行数与四表指纹一致、SHA-256 已记）；`gate_all --quick` 4/4 PASS。内容完整性基线落盘（13 条悬空图片行、10 个未解析图令牌、1 个空组、24 题申论未挂组，全部只登记）；方案新增 D17 + §19.8 六条不变量 + L7-15。
- 2026-10-26：**终态架构升级 v2.1**（用户批准 D1–D16）：新增 §17 容量预算（实测 303.17 MB 中 262.99 MB 是 `question_import_record.preview_data`；537 条超期 PREVIEW = 257.07 MB）、§18 数据卫生与保留期、§19 写入准确性、§20 三端×角色通信 SLO（seq/scope/Redis 中继/轮询回退）、§21 可落地性自证；L7 扩到 14 项（容量/preview/多 worker/事件契约）；新增 `foundation_preview_ref` 第 7 表。
- 2026-10-26：新增《砺安题库终态总体架构 v2.0（实测适配版）》：把草案“五库并列+双写”修正为“1 事实源 + 4 可重建投影 + Outbox + 对账”，给出 F0–F6 主干路线、L7 门禁与 dsh Agent 规约；**待用户审批 D1–D7，未批准前不动代码**。
- 2026-10-25：**OCR 链路恢复**：MinerU 超时改按页放大（75s/页、封顶 3600s），Paddle 页数上限 8→30、超时 240→600s，Paddle 按核数开线程并关方向分类；文本缓存键加引擎作用域（MinerU/Paddle 互不污染，2 个长期失败用例清零）。26 passed。
- 2026-10-25：**行测资料分析材料绑定**：按 `（一）（二）` 材料段把 material_text 回填给段内 4~5 道小题（22 套 blocks 2603 零漂移，76 组/272 题绑定，原仅 64 题）；限「资料分析」分段 + 题数 [2,6] 安全阈值，漏检边界宁可不挂。**前向生效**，存量 235 题仍需重导或回填。
- 2026-10-25：**导入配对修复**：答案 PDF 不再按题干切块，改为题号锚点解析（安徽 2025 实测 125→125 对齐）；预览新增 `file_role=answer` 与 `ANSWER_ONLY`，`/confirm` 禁止答案卷入库；新增探针 `scripts/probe/probe_import_match_quality.py`（行测 10 套匹配率 100%）。
- 2026-10-25：**数据库静默回落修复**：`backend/.env` 缺失使 `SQLITE_PATH` 回落 `example_db.sqlite`（旧 schema、0 题），全站 500/登录失败；合入 main 的默认库修复 + 新增 `app/core/db_guard.py` 启动校验（路径/关键列/行数），重启后 `/api/questions/` 200（total=3122）。事故报告已归档。
- 2026-10-25：`build:prod` 恢复：58 条 typecheck 错误清零，`.vtj` 页仅动 `<script>`；`verify:health` 阻断 0、`test:unit` 331 passed、构建 25.75s。
- 2026-10-25：dsh 侧能力就绪：`.dsh/skills` 联接 20 个项目技能（33→53 条）；`mcp-vtj` 19 工具免重启可用；`gate_all.py` 修复 GBK 假 FAIL 与落盘路径。
- 2026-10-24：T-12 完成：新增 `docs/superpowers/specs/三端数据流一致性修复方案_v2_验收报告_20261024.md`；生产迁移 KP 1049 / 题 3357 / 关系 2775，51 项验收全绿。
- 2026-10-23：新增 `plans/三端数据流一致性修复方案_v2.md` 并追加 §14 RT 富文本（答题卡/教师端/导入/管理员端）。
- 2026-10-22：合并远端“题库设计前必看”内容，保留文档索引。
- 2026-10-22：恢复《整体系统使用和结构说明》10.4、11–15 节，同步根目录、`docs/ops`、归档三份副本（818 行）；补充数据流一致性报告图片附件。
- 2026-10-22：新增 `ops/整体系统使用和结构说明_v1.md`（系统目录结构、克隆与启动、拉取更新、设计收尾、SQLite 存储/备份/恢复、多人共享、验收与排错）；同步根目录 `整体系统使用和结构说明.md`。
- 2026-10-20：三端修复 P0 全部完成：P0-3 解析门禁基线（公专 L1 PASS；行测 L1 既有 FAIL，材料指纹 364/1.0 与基线一致）；5 个真实案例入库（commit `a634820`），第 3 类“材料在答案解析之后”标 `not_found`，未使用合成案例；P0-4 golden corpus（commit `4f291ed`）；P0-5 `MATERIAL_OWNERSHIP_V2=False` 灰度开关（commit `54de949`）。
- 2026-10-20：三端修复 P1-1 完成：`QuestionStatsService.visible_query` 统一三端默认可见性为 `status=1 AND audit_status=1`，新增 `visible_total`、教师 `my_total`、管理端 `include_offline/include_pending`；`backend/tests/test_question_stats_service.py` 4 passed（commit `fa3683a`）。
- 2026-10-19：新增 `plans/三端数据流一致性修复方案_v1.md`（三端数据流一致性 6 问题修复方案；数据库实测 + 代码逐行核对；待用户审批后实施）。
- 2026-10-19：三端修复方案获批；P0-1 备份完成、P0-2 基线脚本完成（commit `db4a5c2`）；基线修正：2 组无可见成员、组 24 仅 1 个 source。
- 2026-10-18：⑱⑲⑳ 三未开发模块补目录定位：`src/modules/{ai-assistant,mock-exam,mini-exam}` 占位外壳落地（四件套×3、零事件、不认领），生成器 17→20 域，shells.spec 161 全绿；规格 5.1 目录树与《分支使用说明书》⑱⑲⑳ 三行同步更新。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1.md`（学生端功能模块化设计终稿，用户已批准）。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1_实施计划.md`（123 个原子任务；P1 33 任务、P2 82 任务已全部完成并逐任务双提交；P3 真机手工验收待执行）。
- 2026-10-18：新增 `plans/分支使用说明书_v1.md` 与 `plans/学生端模块化基线快照_v1.md`。

---

## 附：题库设计前必看（远端新增）

### 一、系统目录结构分层说明

## 1.根目录分层
```
/ 仓库根
│
├── 【A】VTJ 应用根 ── 冻结，不可重组
│   ├── src/                 前端源码（内部按 §4.2 分层）
│   ├── .vtj/                低代码资产（92 处 import 硬绑定）
│   ├── public/              静态资源（favicon / logo）
│   ├── packages/            前端共享包（已获批准：保持根目录，不并入 deploy/）
│   ├── dist/                构建产物（已 gitignore）
│   └── package.json  vite.config.ts  proxy.config.ts  tsconfig*.json  index.html
│
├── 【B】应用后端
│   └── backend/             FastAPI + 运维脚本 + 测试 + 迁移
│
├── 【C】原始语料 ── 🚫 红线，禁动
│   └── 题库/                662 MB PDF（行测重导依赖）
│
├── 【D】文档 ── 全部收归此处
│   ├── docs/
│   │   ├── design/          方案设计（按业务域）
│   │   ├── plans/           实施计划
│   │   ├── ops/             使用/运维手册（环境 / 启动 / 拉取更新 / 数据库 / 共享 / 排错）
│   │   ├── archive/         历史版本（题目导入 v1~v9 归此）
│   │   └── ai-commands/     原 CLAUDE.md/ 目录改名而来
│   └── README.md  CHANGELOG.md
│
├── 【E】工程化
│   ├── deploy/              Dockerfile / docker-compose.yml / nginx.conf
│   │                        / .env.development / .env.school / .env.example
│   ├── parser/              MinerU + OCR sidecar（python:3.11）
│   └── tools/               开发辅助工具（bg-monitor / sfc-check / git-hooks）
│
├── 【F】AI 工具记录 ── 归并为单一目录
│   └── .agent/{skills,tools,plans}/ + README.md 索引
│
└── 构建缓存 ── 全部 gitignore
    ├── node_modules/  .worktrees/  logs/  .pytest_cache/  .playwright-mcp/
    └── .idea/  .vscode/  .sisyphus/  .omo/
```
## 2.后端分层

```
backend/
├── app/
│   ├── main.py                  ★ 唯一入口，只做装配
│   │
│   ├── core/                    平台内核 ── 零业务
│   │   ├── config.py  database.py  security.py  redis_client.py
│   │   ├── events.py            【新】事件总线契约
│   │   ├── contracts.py         【新】跨域公开契约注册
│   │   ├── module_registry.py   【新】域清单一处声明
│   │   ├── middleware.py        ← 从 app/ 根移入
│   │   ├── monitoring.py        ← 从 app/ 根移入
│   │   ├── exceptions.py        ← 从 app/ 根移入
│   │   ├── cache.py             ← 从 app/ 根移入
│   │   └── db_router.py         ← 从 app/ 根移入
│   │
│   ├── modules/                 【新】十域，各自自包含
│   │   └── <domain>/{__init__, router, schema, models, service, contract}.py
│   │
│   ├── shared/                  【新】跨域基础件 ── 非业务
│   │   └── parser/  ocr/  scraper/  image/  matcher/
│   │
│   ├── models/                  Base + 过渡期（P3 后仅留 Base）
│   ├── schemas/                 平台级共享 schema
│   ├── services/                过渡期（P2–P4 后按域迁入 modules/）
│   ├── api/v1/                  过渡期（P3 后清空）
│   │
│   ├── static/                  题图 4.3 GB ── 卷，不入 Git 不入镜像
│   └── uploads/                 702 MB ── 卷
│
├── scripts/                     运维脚本（6 类子目录，见 §7.5）
│   └── gates/  migrate/  repair/  probe/  admin/  verify/
├── tests/                       conftest.py + 用例
├── migrations/                  SQL + Python 迁移
├── data/                        SQLite + gates + audit + archive ── 卷
├── logs/                        运行日志
├── Dockerfile  .dockerignore
├── .env  .env.example
├── requirements.txt
└── README.md  REPORTS.md
```

## 3.数据目录分层
```
backend/data/                    全部不纳入 Git，容器化后为卷
├── question_bank.db             生产库 292 MB（+ -wal / -shm）
├── gates/                       门禁基线 ── 反选入库（CI 复现必需）
├── audit/                       回填/去重审计流水（14 文件：.jsonl + .csv）── 数据变更追溯凭证
├── archive/                     备份归档（41 份唯一内容，按「最近 7 天 + 每周一份」保留）
├── text_cache/                  PDF 文本提取缓存（74 文件，可重建）
├── xingce_cache/                行测探测缓存（170 文件，可重建）
├── refactor_baseline/           重构基线 JSON（6 份）── force-add 入库
└── backup_audit_report.json     备份审计报告 ── force-add 入库
```

## 4.前端目录分层
```
src/
├── router/index.ts              # 主路由表（roles + platform 双重门控）
│
├── views/
│   ├── student/                 学生端
│   │   ├── shared/              6 页（achievements exercise solution profile feedback help）
│   │   ├── pc/                  PC 专属（当前 0，主要在 .vtj）
│   │   ├── tablet/              平板专属（当前 0）
│   │   └── mobile/              ★ 19 个 mobile_* 页全部归此
│   │
│   ├── teacher/                 教师端【预留】
│   │   ├── shared/
│   │   ├── pc/                  PC 专属（当前 0；教师端 8 页在 .vtj/vue）
│   │   ├── tablet/              平板教师端（当前 0）
│   │   └── mobile/              手机教师端（当前 0）
│   │
│   ├── admin/                   管理端【预留】
│   │   ├── shared/
│   │   ├── pc/                  ★ 管理端 11 页目前在 .vtj/vue
│   │   ├── tablet/              平板管理端（当前 0）
│   │   └── mobile/              手机管理端（当前 0）
│   │
│   └── system/                  无角色归属的系统页
│       ├── not-found.vue
│       └── unauthorized.vue
│
├── components/
│   ├── common/                  HelloWorld / VtjErrorBoundary（无角色无设备归属）
│   ├── mobile/                  MobileTabBar（设备专属）
│   └── domain/                  RecentPracticeRecords（域内）
│
├── services/
│   └── api/<domain>.ts          # ★ 按十域归口，不按角色/设备
│
├── layouts/
│   ├── AdminLayout.vue          管理端（位置已正确）
│   └── TeacherLayout.vue        教师端（位置已正确）
│
└── utils/                       device.ts 等 7 个（原样保留）
```
## 5.前端模块化目录分层
```
src/
├── modules/                     # 新增：20 个模块外壳
│   ├── identity/                ##  认证 + 个人中心
│   │   ├── store.ts             # 域内状态
│   │   ├── api.ts               # 域内 HTTP 封装
│   │   ├── events.ts            # 本域发布/订阅的事件声明
│   │   └── README.md            # 域卡（见 7.4）
│   ├── catalog/                 ## 题库浏览
│   ├── practice/                ## 答题练习
│   ├── records/                 ## 练习记录
│   ├── papers/                  ## 智能组卷 + 历年试卷
│   ├── wrongbook/               ## 错题集
│   ├── notes/                   ## 笔记 + 收藏
│   ├── analytics/               ## 成绩分析
│   ├── community/               ## 论坛社区
│   ├── news/                    ## 每日新闻
│   ├── calendar/                ## 考试日历
│   ├── recruitment/             ## 招考信息
│   ├── about/                   ## 关于砺安题库
│   ├── library/                 ## 备考资料
│   ├── growth/                  ## 成就成长（枢纽）
│   ├── reward/                  ## 金币商城
|   ├── mini-exam                ## 小模考
|   ├── mock-exam                ## 模拟上机考试
|   ├── ai-assistant             ## 联考小智
│   └── checkin/                 ## 每日签到
|
├── stores/                      # 新增：全局共享层
│   ├── auth.ts                  # 登录态、当前用户、角色
│   ├── user-profile.ts          # 跨域只读的用户画像快照
│   └── event-bus.ts             # mitt 实例 + 事件常量表
├── services/
│   └── api/                     # 激活：统一 axios 实例与拦截器
│       ├── client.ts            # baseURL、超时、重试
│       ├── interceptors.ts      # 鉴权头、401 跳转、错误归一化
│       └── types.ts             # 通用响应外壳类型
├── utils/
│   └── device.ts                # 原样保留（R4）
└── router/
    └── index.ts                 # 原样保留 92 处 .vtj 动态 import（R1）
```


### 二、拉取项目并打开项目的一般步骤
## 1.打开 VS Code，按下 Ctrl+Shift+P（Mac 为 Cmd+Shift+P）打开命令面板。

## 2.输入 gitcl，选择 Git: Clone 命令。

## 3.选择 Clone from GitHub，VS Code 会引导你登录 GitHub 账户进行授权。

## 4.在仓库 URL 输入框中，粘贴 GitHub 项目的链接（就是这个项目--https://github.com/linxitie/li_an-question_bank.git）。

## 5.选择一个本地文件夹作为项目的保存位置，然后点击 Select as Repository Destination。

## 6.克隆完成后，VS Code 会询问你是否打开该项目，点击 Open 即可。

## 7. 启动系统（首次与日常）

# > 先下载项目内容："npm install"；前端依赖应在**仓库根**安装。按 7.1 → 7.6 的顺序执行，不要先跑前端再装后端。

### 7.1 环境要求与检查

| 组件 | 要求 | 检查命令 |
|---|---|---|
| Windows | 10/11 64 位 | `winver` |
| PowerShell | 5.1 及以上 | `$PSVersionTable.PSVersion` |
| Node.js | ≥ 20（本机实测 v24.14.0） | `node -v` |
| npm | ≥ 10 | `npm -v` |
| Python | ≥ 3.10（本机实测 3.13.5） | `python --version` |
| Git | 2.40 及以上 | `git --version` |
| 磁盘 | 建议 ≥ 15 GB 空闲 | `Get-PSDrive D` |

建议把仓库放在**不含空格**的路径；本项目当前路径含中文可以运行，但 PowerShell 日志可能出现编码乱码，执行前可先设 UTF-8：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
```

### 7.2 克隆后确认

克隆步骤见本节 1–6。完成后在仓库根执行：

```powershell
git status
git branch -a
git log --oneline -5
```

### 7.3 启动后端（FastAPI）

**下载项目内容完毕后**

# ```powershell
# cd D:\砺安题库\砺安题库\backend
# 输入命令"python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",entre即可
# ```

### 7.4 启动前端（Vite + VTJ）

**必须从仓库根启动**（`vite.config.ts` 有 `workspaceRoot` 强制校验，不能从 `backend/` 或子目录启动）：

# ```powershell
# cd D:\砺安题库\砺安题库
# npm run dev
# ```

-
- `npm run dev` 实际执行 `cross-env ENV_TYPE=local vite`，端口 **9527**，`host: '0.0.0.0'`，手机/平板可通过局域网访问。
- 打开：
  - 前端：`http://localhost:9527`
  - VTJ 设计器：`http://localhost:9527/__vtj__/`
- Vite 代理默认把 `/api` 转发到 `http://127.0.0.1:8000`；需要连别的后端时设：
  ```powershell
  $env:DEV_BACKEND_ORIGIN = "http://192.168.1.10:8000"
  npm run dev
  ```
- 后端没起来时，前端会收到 `503/502` 和 `BACKEND_UNAVAILABLE`，先回去启动 7.3，不要先怀疑前端页面。
- 端口被占用：
  ```powershell
  netstat -ano | findstr :9527
  taskkill /PID <PID> /F
  ```

### 7.5 手机端 / 平板端访问

1. 电脑和手机连同一个 Wi-Fi/局域网。
2. 在 PowerShell 执行 `ipconfig`，找到“无线局域网适配器 WLAN”的 IPv4 地址（如 `10.213.3.206`）。
3. 手机浏览器访问：`http://10.213.3.206:9527`（英文冒号）。
4. 打不开时依次检查：Windows 防火墙是否放行 Node.js；是否连错 Wi-Fi；IP 是否变化；Vite 是否仍在运行。
5. 前端页面走 9527，API 由 Vite 代理转发；一般不需要在手机上单独访问 8000。

<!-- ### 7.6 Docker 部署（可选，生产/演示）

> 实际编排文件是**仓库根**的 `docker-compose.yml`，不是 `deploy/docker-compose.yml`（后者不存在）。

```powershell
# 1. 准备环境变量（真实密钥只写在本地，不提交）
Copy-Item deploy\.env.example deploy\.env.development
# 编辑 deploy\.env.development，至少填写 JWT_SECRET_KEY

# 2. 构建前端产物（nginx 挂载仓库根 dist/）
npm run build:prod

# 3. 启动
docker compose --env-file deploy\.env.development up -d --build
docker compose ps
docker compose logs -f backend
```

- 服务：`nginx`（80）、`backend`（127.0.0.1:8000）、`parser`（127.0.0.1:8080）。
- 卷：`db_data`（SQLite + 门禁基线）、`uploads`、`qimg`（题图）、`parser_cache`（MinerU 权重）。**不要执行 `docker compose down -v`**，否则会删除数据库、上传文件和题图。
- `qimg` 卷首次需要导入 `backend/app/static/` 的题图（约 4.3 GB）；不导入会全站裂图。
- `deploy/.env.development` / `.env.school` 含真实密钥，已被 `.gitignore` 排除，禁止提交；仓库只保留 `deploy/.env.example`。
 -->
**进行项目克隆完毕之后**
# 打开自己最适合最常用的AI编码工具（推荐使用claude终端版、opencode终端版、gpt、cursor等等） ,并进行所有提前配置完毕后再进行具体项目设计（后面一一提及，大大和大大大的字体就是要特别关注的）

# 8.进行分支独立设计的提示词约束：
```
## 分支拓扑约定（必须严格遵守）

当前项目使用“模块工作域 + 子分支”的链式分支模型：

main（稳定基线）
 └── feature/<模块名>        ← 模块工作域（父分支），只接受经过测试的子分支合并
      └── feature/<模块名>/<子任务>  ← 子分支，每次只做一件优化/测试任务

## 你的当前工作域

- 你当前所在的分支：feature/<模块名>/<子任务>
- 该分支的父分支：feature/<模块名>
- 禁止直接从当前分支向 main 发起合并或 PR。
- 所有代码修改、测试、提交，都只在你当前所在的子分支中进行。

## 操作规则

1. **拉取与同步**：开始工作前，先 `git pull` 当前子分支；如果子分支尚未创建，从 `feature/<模块名>` 拉出，命名格式为 `feature/<模块名>/<子任务简述>`。
2. **只做一件事**：当前子分支只负责一个具体的优化或测试任务。不要在其中混合无关的改动。
3. **测试先行或并行**：每次提交前，至少运行与当前模块相关的测试命令（如果项目有测试套件）。如果测试失败，先修复，再提交；不要提交测试失败的代码。
4. **提交粒度**：一个逻辑变更一个提交，提交信息使用 `feat/fix/test/refactor: <简述>` 格式。
5. **合并回父分支**：当前子任务完成且测试通过后，只向 `feature/<模块名>` 发起合并/PR，不要直接向 main 操作。
6. **如果父分支有更新**：在子分支中 `git rebase feature/<模块名>`（或 merge），解决冲突后再继续，保持子分支建立在父分支最新状态之上。

## 合并顺序（链式分支专用）

如果存在多层嵌套（例如孙分支），合并顺序必须是：
- 孙分支 → 子分支 → 模块工作域 → main。
- 永远从最外层向内合并，不得跳层
```
**不同的编码AI的内置技能不同：**
# 1.Trae
利用“工作树”做隔离，提示词侧重“任务边界”
Trae 内置了工作树（Worktree） 模式，可以为每个任务自动创建独立的分支和目录，并在任务完成后通过“AI 合并”将代码合回目标分支。这意味着你不需要在提示词里让 AI 手动执行 git checkout -b，而是在 Trae 中启动任务时选择工作树模式，然后让提示词聚焦于“这个工作树里做什么”：

text
你当前在一个独立的工作树中，对应分支 feature/<模块名>/<子任务>。
你的任务：<具体优化或测试目标>。
约束：
- 只修改与该目标直接相关的文件。
- 完成后，将变更合并回父分支 feature/<模块名>，不要合并到 main。
- 如果测试失败，在当前工作树中继续修复，不要标记任务完成。

# 2.opencode
用 opencode-worktree 插件自动管理子分支
OpenCode 可以通过 opencode-worktree 插件为每个任务自动创建 agent/<task> 格式的子分支，并在退出时自动合回父分支。提示词需要让 AI 理解 agent/ 分支是“临时执行分支”，它的生命周期绑定于当前任务：

text
你正在一个由 opencode-worktree 创建的隔离工作树中，当前分支为 agent/<task>。
该分支的父分支是 feature/<模块名>。
你的任务：<目标>。
规则：
- 所有改动只提交到当前 agent 分支。
- 任务完成后，通过工作树机制合回父分支；如果合并不需要保留，直接退出即可。
- 在退出/合并前，运行相关测试并确认通过。

# 3.Claude
原生 Git 操作，提示词需明确“禁止直接碰 main”
Claude Code 具备原生 Git 提交能力，也可以被 MCP Git 工具赋予分支、rebase 等完整操作权限。它的风险在于权限较大，可能直接执行 git push origin main。因此提示词必须包含一条硬性禁止：

text
严禁直接向 main 分支执行 push、merge 或创建 PR。
你只被允许在 feature/<模块名>/<子任务> 分支上提交和推送。
完成子任务后，只向 feature/<模块名> 发起合并请求（PR 或本地 merge）。

- 其他的我没有深入使用，不太了解

---

## 9. 后期拉取分支更新后的操作步骤

> 这一节解决“别人合并了新代码/新设计，我本地怎么安全跟上”的问题。完整的多人协作规则见 `docs/plans/分支使用说明书_v1.md`，这里只给拉取前后必须执行的动作。

### 9.1 拉取前：先保证工作区干净

```powershell
cd D:\砺安题库\砺安题库
git status --short
git branch --show-current
```

- 有未提交改动时，先提交到当前功能分支；不想提交就暂存：
  ```powershell
  git stash push -u -m "wip: 拉取更新前暂存"
  git stash list
  ```
- **不要**用 `git reset --hard`、`git clean -fd` 清工作区；这会直接丢代码和未跟踪文档。
- 确认当前分支：`main` 只做同步，不直接开发；开发在 `feature/<模块>` 或 `feature/<模块>/<子任务>`。

### 9.2 拉取 main 与模块分支

**情况 A：只更新 main**

```powershell
git switch main
git fetch origin --prune
git pull --ff-only origin main
```

`--ff-only` 失败说明本地 main 与远端分叉了，不要强行 merge；先看：

```powershell
git log --oneline --left-right main...origin/main
```

把本地多出来的提交移到功能分支，或找维护者确认后再处理。

**情况 B：更新模块父分支**

```powershell
git switch feature/<模块名>
git fetch origin --prune
git merge origin/main
git push origin feature/<模块名>
```

**情况 C：更新自己的子分支（最常用）**

```powershell
git switch feature/<模块名>/<子任务>
git fetch origin --prune
git merge origin/feature/<模块名>
git merge origin/main
git push origin feature/<模块名>/<子任务>
```

先合父分支，再合 main；不要反过来。合并冲突时：

```powershell
git status
# 手工编辑冲突文件，确认没有残留 <<<<<<< ======= >>>>>>>
git add <冲突文件>
git commit
```

想放弃这次合并、回到合并前：

```powershell
git merge --abort
```

冲突处置细节（保留谁、怎么验证）见 `docs/plans/分支使用说明书_v1.md` 第 7 章。

### 9.3 拉取后：先看“变了什么”，再启动

```powershell
git log --oneline --graph --decorate -20
git diff --stat ORIG_HEAD..HEAD
git diff --name-only ORIG_HEAD..HEAD
```

# 每次完成自己模块的预期目标或者效果一定一定要合并并推送至github中否则会出现内容过多，项目冗余的情况，严重会破坏整个项目(可以手动进行分支合并和推送，也可以让AI执行命令合并推送)

### 9.3.1附加手动实现分支合并并推送
- 第一步 保存并提交自己的代码
  ### 查看自己改了哪些文件
  git status
  ### 添加并提交（注意：一定要确认没有把 .db、.env 等无用文件加进去）
  git add .
  git commit -m "feat: 完成功能设计与测试"
- 第二步 切回主干，拉取你的最新代码（极其关键）
  为了防止他推送时覆盖掉你刚写的代码，他必须先同步你的最新进度。
  ### 1. 切回主干
  git checkout main
  ### 2. 拉取你（负责人）在 GitHub 上的最新代码
  git pull origin main
- 第三步 将分支合并进主干
  ### 把 feat/my-feature 合并进当前的 main 分支
  git merge feat/my-feature
  **如果成功：终端会显示 Merge made by...。直接进入第四步。**
  **如果有冲突：终端会报错 CONFLICT。让他立刻停止，并通知你。让他用 VS Code 解决完冲突，执行 git add . 和 git commit 后再继续。**
- 第四步 推送到 GitHub
  git push origin main


### 9.4 数据库有变更时：先备份，再启动

```powershell
cd D:\砺安题库\砺安题库\backend
python scripts/admin/backup_db.py --label 拉取更新前
python start.py
```


### 9.5 前端依赖与缓存

```powershell
cd D:\砺安题库\砺安题库
npm ci
npm run dev -- --force
```

- `--force` 让 Vite 重新预构建依赖；也可以删除 `node_modules/.vite` 后重启。
- **不要随手执行 `npm run clean`**：该脚本会删除 `node_modules`、`dist`、`package-lock.json`、`pnpm-lock.yaml`，不是普通的清缓存。
- 浏览器用 `Ctrl+F5` 强刷；设计器页面同样要强刷，避免旧 chunk 缓存。

### 9.6 设计完成后的收尾（合并前）

1. **文档**：设计/方案写入 `docs/plans/` 或 `docs/superpowers/specs/`；更新 `docs/README.md` 索引；按 `AGENTS.md` 归档规则留档。
2. **计划**：把实施计划里的任务勾选、状态、验证结果更新掉；代码提交与计划状态提交分开。
3. **VTJ**：`.vtj/` 不移动、不改名、不删除；`raw: true` 页面禁止 `vtj_sync_vue_to_dsl`；`.vtj/vue/*.vue` 的 `<template>` 只能由设计器改，AI 只改 `<script>` 且先 `dryRun: true`。
4. **验证**：
   ```powershell
   cd D:\砺安题库\砺安题库
   npm run typecheck
   npm run build
   npm run test:unit

   cd backend
   python -m pytest tests -q
   python scripts/gates/gate_all.py --quick
   ```
   全量门禁用 `python scripts/gates/gate_all.py`；行测 L1 等既有 FAIL 以基线为准，**新增失败必须修复**。
5. **提交**：一个逻辑变更一个提交，提交信息用 `feat/fix/test/refactor: <简述>` 或模块前缀（如 `wrongbook: ...`）。
6. **合并顺序**：子分支 → 模块父分支 → `main`，禁止跳层，禁止直接 push `main`；合并前必须再合一次最新 `origin/main` 并重跑门禁。
7. **合并后**：删除已合并的临时分支，切回 main `git pull --ff-only`，确认远端与本地一致。

### 9.7 不要提交的东西 【必须要看和注意】

- `backend/data/question_bank.db`、`-wal`、`-shm`、`backend/data/*.bak*`、`backend/data/backups/`
- `backend/uploads/`、`backend/app/static/` 的题图、`题库/` 原始 PDF
- `.env`、`deploy/.env.development`、`deploy/.env.school`、`.obsidian_mcp.json`、`admin_token.txt`
- `node_modules/`、`dist/`、`backend/logs/`、`.vtj/logs/`、`.vtj/histories/`

---

## 10. 数据库数据的存储说明

### 10.1 默认数据库：SQLite（WAL）

| 项 | 实际值 |
|---|---|
| 类型 | SQLite，`DB_TYPE=sqlite`（默认） |
| 主库 | `backend/data/question_bank.db`（当前约 302.7 MB） |
| WAL | `backend/data/question_bank.db-wal`（当前约 5.4 MB） |
| 共享内存 | `backend/data/question_bank.db-shm` |
| 日志模式 | WAL；已提交数据可能还在 `-wal` 里，**不能只拷主库** |
| 连接串 | 由 `backend/app/core/config.py` 的 `DATABASE_URL` 生成；`start.py` 会先切到 `backend/`，所以相对路径以 `backend/` 为基准 |

`backend/data/` 不是普通缓存目录，里面同时有：

- `backups/`：`backup_db.py` 的新备份
- `audit/`：数据变更追溯凭证（R9，不是垃圾）
- `gates/`：门禁基线与 `last_run.json`
- `refactor_baseline/`：API/模型/耦合/表使用基线
- `snapshots/`、`text_cache/`、`xingce_cache/`：解析缓存与快照
- `question_bank.db.bak_*`：历史备份（R8，禁止清理）

### 10.2 大体积数据放在哪里

| 数据 | 位置 | 体量（实测口径） | 是否进 Git |
|---|---|---|---|
| 原始 PDF 语料 | `题库/` | 约 662 MB | 否（R6，禁止删除/移动） |
| 题图 | `backend/app/static/` | 约 4.3–5.5 GB | 否（R7，禁止删除；新题图已忽略） |
| 用户上传 | `backend/uploads/` | 约 0.8 GB | 否 |
| SQLite 主库 + 备份 | `backend/data/` | 主库约 300 MB，备份数十份 | 否 |
| 示例库 | `backend/data/example_db.sqlite` | 约 13 MB | 否（本地示例库，已被 `.gitignore` 忽略） |

这些数据**不通过 Git 共享**。换机器/多人协作时用移动硬盘、内网共享、`rsync` 或对象存储；Docker 部署用命名卷持久化。

####  10.3 Docker 下的数据库

`docker-compose.yml` 把数据挂到命名卷：

- `db_data:/app/data`：SQLite 主库、WAL/SHM、备份、门禁基线
- `uploads:/app/uploads`：用户上传
- `qimg:/app/app/static`：题图（约 4.3 GB，必须单独导入）
- `parser_cache:/root/.cache`：MinerU 模型权重

**不要 `docker compose down -v`**，否则上述卷会被删除。备份要在容器内执行，再把备份文件取出：

```powershell
docker compose exec backend python scripts/admin/backup_db.py --label docker
docker compose cp backend:/app/data/backups/<备份文件>.db .\backup_from_docker.db
```


### 三、项目的必须认识内容

## 1. 前端设计器
由于前端是由VTJ页面设计的，但是该网页需要额外充钱使用，所以我制定了一个D:\砺安题库\砺安题库\vtj-mcp-server的设计器；到时候使用时需要进行前端页面修改时需要进行提示词约束（后面我会将几个关键约束提示词提供）

## 2.MCP-SERVER和skills、工作流
- （1）vtj-mcp-server,不再赘述
- （2）playwright-MCP--用于模拟人的行为进行查看浏览器内容，可以用来让AI测试前端设计效果、也可以用来进行爬虫应对反爬机制等等
- （3）superpower（skills）--主要使用模块是其brainstorm、writting-plans，它是用一套可组合的“工程纪律”技能，保证设计的可靠性、多维、多方面、全方位的思考要求。
强制让AI走完思考 → 计划 → 编码 → 验证 → 审查的完整工程闭环
- （4）工作流--大家可以去多问一下其他AI（deepseek、千问、智普等等），让他们来设计针对你使用的AI设计你相应的功能模块的必须工作流，保证使用时可以按照工作流的内容设计、不至于让其胡思乱下、偷工减料、出现AI幻觉等（这个可能需要在不断地测试，摸索之后才有点头绪）
-（5）大家若有其他好的skills、MCP-server、工作流或者其他的能够高效使用AI的方法都可以交流分享

## 3.我自己一般使用的约束提示词（大家参考着用吧，可以天马行空的想其他的约束词，高效能用就是好的）
全局规则：
- 1.深度分析以上问题和要求，设计出完整的解决方案同时支持我可以对方案进行更深层次要求的提出，设计的方案需要考虑细节、内容下钻、方案可落地性、内容的可靠性等。
- 2.将完整方案经过我的审核批准后才能进行具体设计，将解决方案呈现出来并统一存档在D:\砺安题库\砺安题库\docs\plans文件夹（这个路径需要大家复制自己保存的文件夹的路径中的\plans即可）
- 3.涉及具体代码编写时请在编写的前一步多角度的思考为什么这样编写代码？这样编写代码有什么好处？这样写代码会不会存在安全问题？这样编写代码能不能为后期的运维提供便利？怎样编写代码才能将系统的未来运维管理等更加便捷？将代码编写在此文件中是否正确是否能保证修改后前端能显示出修改效果？修改的代码所处的文件是否正确，能否达到提示词所预期的效果？后端字段是否完善？后端路由是否注册和调用和接口是否完整？前端显示是否能达到预期效果？vtj版本是否一致？
- 4.严格遵照VTJ中设计器--D:\砺安题库\砺安题库\vtj-mcp-server（这个路径需要大家复制自己保存的文件夹的路径中的\vtj-mcp-server即可）
- 5.每次执行命令时请严格遵循该工作流D:\砺安题库\砺安题库\.opencode\skills\li-an-workflow\SKILL.md（同4和1）

## 4.用户账号和手机端、平板端的登录查看
- 1.学生账号：202516001；test123456
- 2.教师账号：ycc5678；ycc5678
- 3.管理员账号：cbrycc；cbrycc

**手机端登录**（平板端同理）
在cmd终端中输入“ipconfig”，查看“无线局域网适配器 WLAN的IPv4地址”，输入到手机浏览器中再加上“:9527”，比如我的是（10.213.3.206:9527）【英文冒号】
