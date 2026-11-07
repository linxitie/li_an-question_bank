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
| `superpowers/specs/砺安题库终态总体架构_v2.0.md` | v2.1 | ✅ 已批准（D1–D17）；F0–F2 已执行（2026-10-26） | **终态架构 + 多库一致性底座**：1 SoT（SQLite）+ 4 类可重建投影 + 事务 Outbox/幂等投影/对账；对草案 10 处硬修正、F0–F6 主干路线、L7 门禁（15 项）、Agent 规约；端×角色（3×3）一致性与空库审计；**v2.1 新增容量预算(§17)/数据卫生(§18)/写入准确性(§19)/三端通信 SLO(§20)/可落地自证(§21)**；业务功能模块不在此方案 |
| `superpowers/specs/main分支启动阻断与考试链路修复_报告_20261026.md` | v1 | ✅ 已合并 main（2026-10-26） | main 报告 P0-1/2/3 + P1-1 + P1-3 + P3-1 修复：Pydantic v2 `ConfigDict`、考试路由导入收敛、日志目录自建+降级、`question_count` 以关联行数为唯一口径（含存量修复脚本）；3 条新回归测试 + 真机烟测 health/login/取题/开考/交卷全 200；全量 650 passed（8 失败均为既有环境项） |
| `superpowers/specs/资料卡片导入D1类型覆盖缺陷修复_报告_20261027.md` | v1 | ✅ 已修复（2026-10-27，分支 `fix/D1-import-card-type`） | D1 阻断缺陷：xlsx 卡片导入的 `type` 被启发式分类器覆盖成 `article`，卡片进文章区、翻卡 UI 永不触发。修复：卡片分支按输入契约直写 `type='card'` 并删除多余 classify 调用；新增 2 条回归测试（xlsx→card、长 docx→article），资料域 39 passed；附存量清洗 SQL 与 D2–D8 交接说明 |
| `superpowers/plans/F1一致性内核_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-26，Step 1–7 完成，tag `foundation-v1-f1`） | F1：7 表 + Outbox→投递→投影→对账 + `content_integrity.py`/`db_inventory.py` + L7 门禁；21 文件、7 步、每步独立验证与回滚；不改 `api/v1`/`models`/`.vtj` |
| `superpowers/specs/预览数据治理与容量回收_报告_20261026.md` | v1 | ✅ 已执行（2026-10-26） | 571 行 / 257.76 MB 超期预览外置 gzip 后置摘要，`auto_vacuum=INCREMENTAL` + VACUUM，主库 **303.17 → 46.52 MB**；四表行数与指纹不变，`integrity_check=ok` |
| `superpowers/plans/F2通信统一与写入守卫_实施计划_v1.md` | v1 | ✅ 已执行（2026-10-26，Step 1–7 完成，tag `foundation-v1-f2`） | F2：WS 协议 v2（seq/scope）+ Redis 中继 + 多 worker fail-fast + 前端 data-changed 消费/重连重同步 + 92 条路由 roles + 写入守卫 6 类；7 步、无迁移、无新表；F2b 写调用点迁移未做 |
| `superpowers/specs/F2通信统一与写入守卫_报告_20261026.md` | v1 | ✅ 已交付（2026-10-26，tag `foundation-v1-f2`） | F2 交付报告：协议/中继/fail-fast/前端去重/路由 roles/6 类写入守卫；L7 15/15、全量门禁 9/10（L2 既有基线）、62 后端 + 342 前端测试；Redis 双客户端各 1 条无重复；明确 F2b 未做 |
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
| `plans/备考资料_二轮UI与学生自建卡_方案与验收_v1.md` | v1 | ✅ 已交付（2026-11-01，分支 `feat/Study-Material-Management-r2`，`main` 未动） | 二轮 UI 修正：①徽章「设为精选」无效的根因是 `/api/badges/my` 漏返 `pinned` → 契约补齐 + 金色五角星（卡片左上角/弹层右侧）+ 按钮文案切换；②右下角铅笔悬浮钮确认是 `@vtj/pro` 注入的 `#vtjLink`，全局 CSS 隐藏且保留 `/__vtj__/` 设计器；③手机端学生新增「＋创建」入口 + 两步弹层（选科目→正面/背面/分类/考点/1~2 配图）→ `POST /api/materials/my/card` 免审批直接公开，学生端 Excel 上传下线；④管理员端「智能导入」Excel 批量链路复核可用；⑤顺带修徽章页 13px 横向裁切、筛选胶囊换行、CSP 禁 `blob:` 导致配图缩略图空白。验收：CDP 脚本 15/15 + 6/6、pytest +23、vitest 31 文件 440 通过、vue-tsc 0 error，11 张效果图 |
| `plans/备考资料_三轮PC建卡与全图_方案与验收_v1.md` | v1 | ✅ 已交付（2026-11-02，分支 `feat/Study-Material-Management-r3`，`main` 未动） | 三轮 PC 修整：①三个科目资料页顶栏下方注入「Excel 批量导入 / ＋ 创建卡片」操作条（R3 合规：VTJ 页不改模板，DOM 注入）；②「返回首页」文字镜像的根因是同页 `.back` 类名冲突（翻卡背面带 `rotateY(180deg)`），用定向 CSS 复位；③PC 卡片配图新增「全图查看器」（缩放 ≤300% / 左右切换 / Esc / 滚轮），并让列表 `_item_brief` 返回 `image_urls`（封面 + 正文附图，一卡两图才拿得全）；④还原学生端 Excel 批量上传，与逐张创建双 Tab 并存（逐张=免审即时公开，批量=待审队列），手机端弹层底部同入口。验收：CDP 13/13 + 4/4、pytest material 157、vitest 33 文件 454、gate_all 10/10、vue-tsc 0 error，9 张效果图 |
| `plans/备考资料_四轮卡片栈与配图入口_方案与验收_v1.md` | v2 | ✅ 已交付（2026-11-02，分支 `feat/Study-Material-Management-r4`，`main` 未动） | 四轮手机端：①「查看配图（N）」入口从列表移到卡片底部（无图时显示「查看详情」），点开直接全屏看图，复用电脑端 ImageLightbox；②翻页白框先按「5 张完整白卡叠加」改成 3 片渐变纸片仍复现 → 真根因是 `.stack-card` 容器自身 `background:#fff`，最终改「后面放 3 张真卡片 + 容器 transparent + 显式 z-index」，翻转时能直接看到后卡正文；③翻转无 3D 的根因是 `perspective` 挂错层级（旋转元素是孙级），移到 `.stack-card` 后是真透视，背面加 `translateZ(1px)` 防重影；④翻页方向统一向右：下一页 `translateX(+118%)` 飞出，上一页新增 `entering-prev` 相位 + `sm-enter-right`（62% → 0）从右侧飞入；⑤手机端建卡弹层第一步加「Excel 批量导入」显性入口，直达 `#/materials/upload?tab=excel`。验收：CDP 20/20 断言（含几何位移 409px）、vitest 33 文件 457、vue-tsc 0 error、gate_all 10/10，10 张效果图 |
| `plans/备考资料_平板端设计构建现状_核查报告_v1.md` | v3 | ✅ A 档 + 全图手势已实施（2026-11-02，分支 `feat/Study-Material-Management-r4`，`main` 未动） | 平板端原本是**「复用手机页 + 零适配代码」**：21 条平板路由 = 7 平板原生 + 14 复用手机页（67%，守 R12）；`src` 里 **0 处**按平台分支；备考资料只有 `/tablet/materials`（复用 `mobile_materials.vue`），徽章走 PC `/badges`，`/materials/upload` 无平台前缀；平板首页无入口，唯一入口「我的 → 离线下载」。实测原尺寸 768×1024 卡片 **735×226（3.25）**、1024×768 **991×226（4.39）**。**已修**：①`@media (min-width:700px)` 卡片 600×307（1.95）/ 600×330（1.82），`.stack-wrap` 必须 `width:100%`+`max-width` 才不被 flex `margin:auto` 收缩；②`@media (pointer:coarse)` 把 `.mc-*`/`.bd-chip`/`.bd-page-btn`/`.bd-coins-link`/`.lb-tool`/`.lb-nav` 补到 44px；③新增 `/tablet/badges` + `DEVICE_ROUTE_MAP` 的 `/materials`、`/badges` 映射（页面路由 99→100、L6 动态 import 99→100）；④**全图查看器补双指缩放 + 左右滑动**（`lightboxGesture.ts` 纯函数 + 14 条单测 + CDP 触摸断言 9/9：捏合 180%、放大态不误切、1:1 左滑切到 2/2、切图后回到 100%）。结果：资料页/Excel 页/徽章页小于 44px 的可点元素 **全部归零**，横向溢出 0px，手机 390 回归 **20/20**、vitest **34 文件 471**、vue-tsc 0、gate_all 10/10。**唯一未做**：平板首页入口受红线 R3 限制（需设计器拖或授权 DOM 注入） |
| `plans/备考资料_分支结构与合并计划_v1.md` | v2 | ✅ 已合并（2026-11-02，`main` `da218d1 → e3e2e54`，**未推送**） | **已执行（见文末 §8 执行记录）**：先 `backup/main-pre-r4` 分支 + `pre-r4-merge` tag（= `da218d1`），再 `ce19649 → e3e2e54`（父分支）、`da218d1 → e3e2e54`（main）两条 fast-forward 指针推进（等价 `--ff-only`，无 merge commit、工作区零抖动）。合后验证：**gate_all 10/10**、vue-tsc 0 error、vitest 35 文件 479、PC 7/7、平板 31/31、手机 20/20、手势 9/9；`/health` healthy、`/health/foundation` ok、openapi 331 路径、登录 200、Vite 代理 200、`/ws/connect` 握手成功；演示卡 111/112 已删（102 已发布 + 5 下线）。一处环境口径：L4 默认探测 8000（本机后端 8010）→ 首次 9/10，设 `OPENAPI_URL` 后 10/10，非代码回归。**未推送 origin/main、未删 27 个子分支、未动 4 个未合并远端分支**。分支梳理实测（并纠正语义坑：`rev-list --left-right --count main...b` 第一位是 **main 独有**，第一位=0 才叫「已并入 main」）。31 个本地分支里只有 4 个在 main：`ai-lecturer`、`multi-device`（原都指向 main）、`qbdm-v4/integration`、`feature/question-seed/integration`（后两者落后 main 27 提交，内容早就在 main，属陈旧分支）；**未进 main 的 27 个模块分支全部已包含在 r4 里（未被 r4 包含的 = 0）**。拓扑：`main@da218d1 → feat/Study-Material-Management@ce19649(+114) → r2(+115) → r3(+118) → r4@7333222(+143)`，main 是 r4 祖先 → **可 fast-forward**（384 文件 / +31,171 −10,085）。**AI 讲师分支位已留**：`feat/…-ai-lecturer` 由 main 前移到 `r4@7333222`（空位，未写代码）。完成度核对：需求① ② ③ ⑤ ⑥ 完成，④ AI 讲师未开工；`gate_all 10/10`、vitest 479、vue-tsc 0、手机 20/20、平板同版 31/31、PC 7/7、手势 9/9、工作区 clean。给出合并路径（先 `backup/main-pre-r4` 分支 + `pre-r4-merge` tag，再 r4 → 父分支 → main 的 `--ff-only`）、合后必跑门禁、风险回退，以及 6 条已知遗留（视频 0 条、竖屏 S2、旧平板脚本待删、207 张待录入、OCR 未装、3 张测试卡）。**待批准**：是否推送到 `origin/main`（当前领先 145 提交）、是否删除 27 个已并入的子分支 |
| `plans/先合并后AI讲师_影响评估_v1.md` | v1 | 🟡 评估结论（2026-11-02，未执行合并） | 你的问题「把其他任务合并后再做 AI 讲师会不会有不良影响」。实测：**合并动作本身零副作用**——`main@da218d1` 是 `r4@267da9f` 的祖先（落后 0 / 领先 144，385 文件 +31,306 −10,085），`--ff-only` 只移动分支指针；AI 讲师分支位已在 r4 HEAD，合并后 main 与它指向同一 commit。**真正的风险在别处**：29 个远端分支里有 4 个带 main 之外的提交——`feature/ai-assistant`(+2) 带 `llm_client.py`(171 行)、`platform/llm.py`（5 个 `/api/llm/*`）、`ChatSession/ChatMessage`、`.vtj/vue/ai_chat.vue` 与 `src/modules/ai-assistant` 的真实实现（现 HEAD 只是占位外壳）；`feature/study-plan`(+3) 用**同一 blob** 的 `llm_client.py`；`fix/D1-import-card-type`(+1) 修的东西**已在 r4**（`materials.py:1955-1957` + `type="card"` @1974）应丢弃；`feat/teacher-optimization`(+1) 改的是已迁走的 `api/v1/teacher.py`（现 `platform/teacher.py`），盲合会 modify/delete 冲突。给出 5 个必改协调点（L6 `EXPECTED_DYNAMIC_IMPORTS=98` 与 `test_route_roles.py` 的 `98` 是**双改点**、R11 白名单 36 条/基线 343 冻结、迁移序号连续、`docs/README.md` 索引、`.vtj/**` 会触发 CI）、推荐顺序（备份 → FF 父分支 → FF main → 跑门禁 → 取零件 → 再开 AI）、A/B/C 三方案与 5 条已知不足 |
| `plans/本地开发端口_8010改8000_方案_v1.md` | v1 | ✅ 已执行（2026-11-02，分支 `chore/dev-port-8000`） | 你的「把本机后端改到 8000」。实测 **8000 本来就是工程默认口径**（`backend/start.py:21`、`proxy.config.ts:5`、`gate_l4_api_contract.py:7` 全是 8000），8010 只由 `scripts/dev-restart.ps1:34` 的 `$BE_PORT` 引入。**改动 22 个文件**：`$BE_PORT → 8000`（`DEV_BACKEND_ORIGIN` 由变量推导自动跟随）、16 个验收脚本的 `API` 常量 30 处、`seed_material_cards.py`、L4 注释、2 份 ops 手册；历史 plans 里的 8010 按当时事实留档。**验收**：8000 监听/8010 空、`/health` healthy、`/health/foundation` ok、登录 200、代理 200、`/ws/connect` 收到「连接成功」、**不带 `OPENAPI_URL` 直接 `gate_all` 10/10**（核心收益）、`pc_desktop_regression` 7/7、`tablet_unified_shots` 31/31、vitest 479、vue-tsc 0。**踩坑 3 条**：①`edit` 工具会抹掉 `.ps1` 的 UTF-8 BOM → PowerShell 5.1 中文注释语法崩，已字节级补回；②后台作业被 kill 会连带杀掉 `Start-Process` 拉起的 uvicorn/vite，须把输出重定向到文件再跑（别套 `\| Select-Object`，管道被子进程句柄挂住永不返回）；③旧后端未被 `Stop-Port` 杀掉时出现 8010+8000 双后端同写一个 SQLite，须核对命令行里的 `--port` |
| `plans/VTJ版本一致性修复_报告_v1.md` | v1 | ✅ 已修复（2026-11-02，分支 `fix/vtj-version-consistency`） | 推 `main` 前按你的要求先修 VTJ 版本一致性。**根因不是版本漂移，是分类错误**：`.vtj/vue/` 有两类文件——设计器页面（`useProvider({id,version})` + 同名 JSON 的 `__VERSION__`，实测 `home_page.vue:199`）与手写页面/组件（4 个 `teacher_*` 页 `useProvider` 命中 **0**、`TeacherNavHeader.vue` 无 JSON、`smart_recommend.vue` 有 provider 无 JSON），后者没有「设计器版本」可对齐；4 个 `teacher_*` 的残留 JSON 是历史遗留。**更隐蔽的问题**：CI 原先调的是同步模式——即使真有漂移，也会在 CI 的 checkout 里被改掉再判通过，**这个检查从未真正拦住过任何东西**。**修复**：`scripts/vtj_version_sync.py` 主流程重写（`classify()` 分三类、新增 `--check` 只读、`--strict` 保留旧严格语义、汇总计数与跳过明细）；CI 改跑 `--check`；ops 手册新增 §2.1（三种用法 + 跳过口径表 + 基线 69/6）。**验收**：默认与 `--check` 均 `69 一致 / 0 失败 / 跳过 6` exit 0；`--strict` exit 1；把 `home_page.json` 的 `__VERSION__` 改成 `1` → `--check` 精确报 `Vue=1785750000100 JSON=1` 且 exit 1，同步模式能修，`git checkout` 还原。`.vtj/vue` 一字节未动（守 R1/R3） |
| `plans/分支清理清单_v1.md` | v1 | ✅ 已执行（2026-11-02，分支 `chore/branch-cleanup`） | 删 26 个已并入 `main` 的本地分支前的**存档清单**：每个分支名对应 commit sha、末次提交日期/主题、是否在远端（**全为 no**，纯本地标签）。判定口径 `git rev-list --count main..<branch>` = 0；本地 34 个分支里 33 个已并入，本次删 26（19 个模块子分支 + `archive/…classify`、`data/seed-cards-3subjects`、`qbdm-v4/integration`、`question-seed/integration`、3 个 `fix/*`），保留父分支/r2/r3/r4/ai-lecturer/backup/dev-port/VTJ 修复/清理分支。用 `git branch -d`（非 `-D`，自带「未合并拒绝」保险）。恢复：`git branch <名字> <sha>` |
| `plans/远端main合并_报告_v1.md` | v1 | ✅ 已合并 + 已验收 + **已推送**（2026-11-04，远端 `main` = `88c0bd9`） | 推 `origin/main` 时发现远端已前进：基点 `a9e44d9`，本地独有 149 提交、远端独有 174 提交（模块4 学习计划/成就/能力雷达/遗忘曲线、模块7 联考小智/知识图谱/记忆/仪表盘、论坛治理、练习管理员、F3 媒体资产）。**8 个冲突逐个解**（models.py 310 行取并集后 92 类无重名；白名单补登记远端 88 个端点；README 按本地结构保留并把远端 29 行集中附录）。**合并后暴露 5 个真问题并修复**：媒体库存会话缺失（建卡 500）、`SESSIONS_UPDATED` 未登记、exam 直读 catalog 模型触发 L4 cross_write（改走新契约 `question_groups_by_ids`）、媒体/图 DDL 的 CRLF checksum、20261027 迁移撞号（本地两支改 004/005）。**推送前远端又前进 10 提交**（新闻模块恢复、3D 日历、AI 错题本/学习对战等），再并一次（冲突仅 models.py，99 类取并集；页面路由 101→105、白名单再补 93 条），最终 `05857d8..88c0bd9 main -> main` 推送成功。验收：`gate_all 10/10`、守卫测试 7 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9 |
| `plans/徽章展示模块下线_报告_v1.md` | v1 | ✅ 已删除并验收（2026-11-04，同分支） | 你的指令「再上传远端前把徽章模块涉及的部分删除掉」。**先划边界再动手**：删的是**徽章展示层**（徽章页/徽章墙/精选/徽章组件/`/api/badges/*` 六端点/`user_badge_top` 表），**保留成就与金币引擎**（`badge_task` 驱动成就任务、`BadgeNameBank` 供成就命名、`badge_service` 供奖励档位、`Title/UserTitle` 供金币商城称号发放——删了会连带废掉需求⑥）。共删 **24 文件 + 6 端点 + 3 路由 + 1 表**，删前打 tag `badge-module-before-delete` 并导出表数据 JSON。门禁双改点 104→101。验收：`gate_all 10/10`、守卫测试 17 passed、vitest **42 文件 481**、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9、openapi 414→409、库内 107 行（102 发布 + 5 下线） |
| `plans/远端main新增页面与接口_v1.md` | v1 | ✅ 已生成（2026-11-04） | 从全量清单里**挑出新增项**（用 `git worktree` 检出 `da218d1` 老 main、`8f03a7d` 合并前本地 main、`89363f5` 当前 main 三个快照，各自导出 `openapi()` 与路由表后取差集）：接口 349 → 373 → **462**，页面 92 → 98 → **105**。**相对老 main 新增 113 个接口 / 15 个页面、删除 0 个接口**；**相对合并前本地 main 新增 95 个接口 / 11 个页面、删除 6 个接口（徽章）**。新增页面里远端线 11 条（`/admin/forum`、`/teacher/forum`、`/ai-assistant`、`/study-plan`、`/knowledge`、`/memories`、`/profile-quiz`、`/news`、`/news/:id`、`/mobile/news/timeline`、`/tablet/news/timeline`）、本地线 4 条（`/materials/detail`、`/materials/upload`、`/materials-preview`、`/admin/material-rules`）。新增接口分域：模块7 28、论坛治理 37、模块4 12、备考资料 16、练习管理员 6、新闻 5、题库/OCR 4、平台反馈 3、媒体资产 2 |
| `plans/备考资料模块成果总结_v1.md` | v1 | ✅ 已交付（2026-11-04，已合入并推送 `main`） | 你要求「就备考资料模块做的并提交 GitHub 的任务成果总结」。规模：**149 提交合入 main（模块相关 135，`materials.py` 改 30 次）、36 个 `/api/materials/*` 端点、7 张相关表、110 条分类规则、库内 102 已发布（99 卡 + 3 篇科目说明）+ 5 下线、15 个后端测试文件 151 条断言、27 份文档**。六项需求：①卡片制作（PC 三科网格+翻转+详情+全图+字号三档、手机 5 层卡片栈、学生自建卡免审/Excel 批量待审）✅；②科目说明（行测 2214 字/申论 2008 字/公专 1857 字）✅；③上传格式+分类机制（格式规范、校验器、110 条规则后台、F1/F2 回归、D1/D2/D4/D5 缺陷、去重）✅；④AI 讲师/AI 视频 **未开工**（仅留分支位）；⑤三端（平板与电脑同版 redirect+44px+横屏收紧，手机卡片栈，守 R12）✅；⑥成就金币/徽章联动 🟡（成就→金币→展示链路完整，徽章展示层已下线，引擎保留）。验收：`gate_all 10/10`、后端 151 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9。已知不足：207 张待录入、2 份扫描 PDF 待 OCR、库内 0 视频、5 条测试卡未清 |
| `plans/AI讲师开工可行性_评估_v1.md` | v1 | 🟡 评估（未建分支、未动代码） | 你的问题「原来设计的 AI 能否在现有 main 上开分支构建，还是已有搭好的分支」。实测：**没有现成的讲师分支**——本地 `feat/…-ai-lecturer` 只是 `e3e2e54` 占位、**落后 main 209 提交**；远端唯一相关的 `feature/ai-assistant`（`de68f4a`）已并入 main，是对话助手不是讲师；代码里 `ai-lecture`/`lectureProvider`/`render_job` 命中 **0**，需求④ 完成度 **0%**。**但可以在 main 上开分支**，且**第①步（契约+`ai_lecture_job` 表+状态机+讲稿生成+501 降级）不依赖外部服务**。main 已具备：LLM 客户端（`chat`/`chat_plan`，3 场景 prompt）+ 6 个 `/api/llm` 端点（含 `context/assemble`）+ 会话表 + 知识图谱 14 端点 + Agent 6 端点 + 视频 8 端点（`video_resource` 0 行）+ F3 媒体资产 + `ai_chat.vue` 参照页。缺口：无契约/任务表/seam、无 TTS/数字人/合成（本机 ffmpeg 未装）、**LLM_API_KEY 未配置**（仅 `.env.example`）、`study_material.video_id` 0 使用。给出三步走与首批 6 项任务、需你确认的 4 件事 |
| `plans/AI讲师功能需求理解与初步设计_v1.md` | v1 | 🟡 需求理解 + 设计待确认（未建分支、未写码） | 你提出 AI 讲师 4 条要求并给了 3 张交互截图（讲解画面/答对/答错解析）。文档做了四件事：①**逐条复述 4 条要求**并点出隐含约束（先做「预写知识点清单」的样板 + 必须预留「按题/按卡自动生成」的底座；老师与场景画风「卡通+正式并存」；讲解要拆段+场景跳转；检查点题目数量不限、正误各有动画）；②把截图反推成**可验收的交互规格**（左侧讲解区+右侧题目面板、胶囊选项、正确绿/错误橙、答案解析块、大对勾水印、烟花粒子、章节时间轴、重播、紫色继续）；③**诚实说明我无法直接“看”视频**，给出两条学习路径（你给参考视频/字幕我用时间轴拆解；否则按讲授法微课模板 + 参数化动作库 gesture/expression）；④**技术取舍 A/B/C**（A 网页交互播放器=推荐、B 真视频/数字人、C 先 A 后录制导出）+ **讲稿 DSL 与播放器状态机**架构 + P0–P3 分期 + 需要你提供的 6 项材料（知识点清单/互动题/参考视频/形象设定/音色/交付形态） |
| **`plans/AI讲师功能总体设计方案_v1.md`** | v1 | 🟡 **待你审批**（未建分支、未写业务代码） | **AI 讲师的正式总体方案**。已按你的三项拍板（A 网页交互播放器 / 你给知识点清单 / 形象另定）展开：**§4 内容模型**（知识点清单模板 + 题目格式 + 讲稿 DSL 字段字典 + JSON Schema 校验）；**§5 学真人讲解的方法论**（微课 7 段式时长占比、5 条拆解规则、7 类动作触发词库——并如实说明我无法直接看视频，需参考素材或按模板基线）；**§6 视觉体系**（参数化 SVG 讲师：性别/发型/服装/表情/动作；4 类场景 board/formula/police/custom + 统一线宽色板实现「卡通+正式并存」）；**§7 交互规格**（状态机 idle→playing→paused_dim→answering→feedback_correct/wrong→resume→ended、三端布局、检查点规则、4 类反馈动画与降级）；**§8 前端落位**（`src/views/lecture/*` 全部新增手写页，不动 `.vtj`；路由 `/lecture/:id`，页面路由 104→105 需同步 L6/L7）；**§9 后端与数据**（P1 零后端静态 JSON；P2 `lecture_script`/`lecture_job` 两表 + 4 个端点 + R11 白名单）；**§10 底座**（`LectureSource` 适配器：清单/题目/卡片 → 同一 DSL → 同一播放器）；**§11 安全合规**（禁 v-html、DSL 注入校验、原创形象、LLM 内容必须 approved、埋点隐私）；**§12 运维**（版本化/灰度预览/埋点/降级/回滚）；**§13 测试验收**（DSL 校验/时间轴/答题/组件/E2E/三端/性能）；**§14 分期**（P1 3–5 天出 3 个可交互知识点样板）；**§16 写码前 7 问自检**；**§17 开工条件**；**§18 附录**（二分法完整脚本示例 + 组件树 + 状态机表） |
| `plans/远端main页面与接口清单_v1.md` | v1 | ✅ 已生成（2026-11-04，基线 `main@1864593`） | 你要的「按模块列出页面/接口 + 代码文件」。**页面 105 条**（管理端 14 / 教师端 8 / 手机端 28 / 平板端 21 / 备考资料 5 / 模块4 学习计划 1 / 模块7 三页 3 / AI 错题本 1 / 新闻 2 / 论坛 1 / 成长 1 / 个人中心 1 / 其它 19，另有 5 条 redirect），**接口 465 个操作 / 14 个后端域**（platform 103 / catalog 83 / community 56 / exam 54 / library 48 / growth 36 / content 16 / identity 16 / knowledge 14 / personal 14 / reward 9 / app-main 7 / agent 6 / post 3）。接口用**静态解析** `@router.<method>` 得到**文件:行号**并生成带锚点链接；页面用嵌套 children 展开得到真实完整路径。脚本 `_gen_inventory.py` 可重复运行刷新 |
| `plans/CI红色作业修复_报告_v1.md` | v1 | ✅ 已修复（2026-11-04，`VTJ` 工作流 6/6 全绿） | 修掉两个红作业：①**Python Code Quality** 根因是 `black --check` 命中 453 个历史文件（仓库从未全面格式化）→ 改为「阻断层 = 注解前瞻检查 + `compileall`；提示层 = black/isort/flake8/mypy」；②**Frontend Code Quality** 根因是 CI node 20 自带 npm 10 与 npm 11 生成的 lock 不兼容（`EUSAGE: Missing vue-tsc@2.2.12`）→ node 升 24 对齐。**顺带修真 bug**：`materials.py` 的 `UploadFile` 在 744 行才导入、340/520 行签名已用 → Python <3.14（CI 3.13）导入即 `NameError`，本地 3.14 的惰性注解把问题掩盖了；新增 `backend/scripts/gates/check_eager_annotations.py` 作为通用守卫（当前 0 问题，对旧版本能精确报 2 处）。另修 container-ci：L1-G 需要真实题库（CI 无库）→ 改跑不依赖 DB 的静态门禁；并给 VTJ 工作流加 `workflow_dispatch` 便于单独验证 |
| `plans/备考资料_平板横屏与电脑同版_可行性与预期效果_v2.md` | v3 | ✅ 已实施（2026-11-02，分支 `feat/Study-Material-Management-r4`，`main` 未动） | 你的要求「平板横屏 + 与电脑同版」，三条决定：①允许横屏收紧顶部 ②竖屏 S2 不提示 ③首页也切电脑版并采纳 V3（右栏下移）。**实施**：`/tablet/materials`、`/tablet/materials/detail`、`/tablet/badges` 三条改 **redirect** 到电脑端路径（页面路由 101→98、L6 同步）；`/tablet/home` 的 component 换成 `$vtj/vue/home_page.vue`（不能 redirect 到 `/home`，device.ts 的 `/home→/tablet/home` 会死循环，且 R4 不许动该文件）；`src/style/index.scss` 加横屏样式（≤1366 触控 44px、≤1200 资料页收紧顶部、首页 ≤1100 两栏/1101–1280 收窄），**必须用 `#app` 前缀**才压得过 `.vtj` 页面的 scoped 样式（实测踩坑）；`tabletMaterialsEntry` 改为往电脑首页 `.navbar-menu` 注入「📚 备考资料」（112×44）；删掉 `mobile_materials.vue` 整个平板分支（1433→812 行，手机不变）。验收 `tablet_unified_shots.mjs` **31/31**：三种横屏尺寸首页=电脑首页+入口、三栏不溢出（1024 变 260+1fr）、<44px=0；资料页 1024 **5 列 179×170、gridTop 421、首屏 2 行**、1366 七列、溢出 0；详情两栏(row)、上传 860、徽章 4 列；旧地址 302 生效；`pc_desktop_regression` 7/7、手机 20/20、手势 9/9、vitest 479、vue-tsc 0、gate_all 10/10 |
| `plans/备考资料_平板与电脑同版_可行性与预期效果_v1.md` | v1 | 📌 已被 v2 取代（竖屏口径，保留存档） | 你的要求「平板与电脑同一套页面、所有布局相同」。**实测结论：可行且代价小**——电脑端资料页用的 `repeat(auto-fill,minmax(150px,1fr))`，平板 768 自动落 **3 列（227×140）**、1024 落 **6 列（152×170）**，**横向溢出 0px**；详情/上传/徽章页在 768 同样 0 溢出。唯一必须补的是触控：共 **5 个 <44px**，全局补完 → **0 个，且列数/卡尺寸一像素未变**。方案 A（推荐）：三条 `/tablet/*` 改 `redirect` 到电脑端路径 + 首页入口与「离线下载」改指 `#/materials/xingce` + 全局触控 CSS + 删平板专用分支。附 7 张真实渲染预期效果图（`assets/备考资料_平板PC同版预览/`）。**注：竖屏口径已被 v2 横屏版取代，两份并存仅供对照。** |
| `plans/备考资料_平板端补齐三项_方案_v1.md` | v2 | ✅ 已实施（2026-11-02，分支 `feat/Study-Material-Management-r4`，`main` 未动） | 你点的 ①②③ 全部落地：①平板补 PC 的「入门讲解视频/深度拓展视频/备考指南」分区 + 只看收藏（逐 type 拉 `/api/materials?subject=&type=&page_size=50`，与 PC 同源，未新增端点）——实测 `blockCount=2`（视频/指南）、收藏筛选 `2 → 0`、视频弹层 `<video>` 有 src、文章弹层正文 1331 字；**库内实际 0 条视频**，视频路径用 CDP Fetch 域 mock 验证（不写库，跑完 disable）。②平板首页 `.quick-actions` DOM 注入「备考资料」入口（守 R3 不碰 `.vtj` 模板）——实测 `present=true`、**放在 `.quick-actions` 之后的独立一行 107×93**（塞进它那 4 列网格会被挤成 62px 宽），纯函数判定 + 8 条单测 + `hashchange`/`resize`/1.2s/`MutationObserver` 四重兜底；③新增 `/tablet/materials/detail` 复用 PC 详情页（守 R12）+ `@media(max-width:900px)` 单栏——实测 `sideW=735`、`flexDirection=column`、`overflowX=0`、返回键 44px，并修掉单列下「5 层堆叠卡装饰层向上溢出 60px 盖住字号行」的遮挡。门禁同步：页面路由 100→101、L6 101；`vitest 35 文件 479`、`vue-tsc 0`、`gate_all 10/10`、手机 20/20、全图手势 9/9 |
| `plans/备考资料_平板端模仿PC布局_方案_v1.md` | v2 | ✅ 已实施（2026-11-02，分支 `feat/Study-Material-Management-r4`，`main` 未动） | 你的要求「平板端模仿电脑端、按平板比例排布」，三条决定：**A 同页两套布局 / 保留上一页下一页 / 要 hero 进度条**。实测 PC 结构：`.top-bar` → `.hero` → 分区块，卡片是 `repeat(auto-fill,minmax(150px,1fr))` 网格 + 点击原地翻转。**实施**（`mobile_materials.vue` 内 `matchMedia('(min-width:700px)')` / `(min-width:1000px)` 双断点）：768 宽 **3 列 × 2 行 = 6 张/页**、卡片 **236×260（比例 0.91，贴近 PC 150×170 的 0.88）**；1024 宽 **4 列 × 2 行 = 8 张/页**、237×215；hero 走 `/api/materials/progress-summary`（未新增端点，守 R11）；下方列表只留视频/文章不重复；手机 390 仍是卡片栈 + 上一张/下一张 **20/20 不回退**。实测：网格翻页 `1/7 页 → 2/7 页`、点击翻转 `matrix3d(-1,0,0,0)`、查看配图接全图手势 9/9、横向溢出 0px、vitest 34 文件 471、vue-tsc 0、gate_all 10/10 |
| `plans/备考资料模块总体方案_v1.md` | v1 | 🟡 待用户审批（2026-10-27） | 备考资料 6 项需求的总方案。实测结论：**后端家底已厚**（`study_material` 23 列已含 `card_front/card_back/cover_image/badge`、`material_classification_rules` 规则骨架、18 个 `/api/materials/*` 端点、`achievement`45/`badge_task`14/`badge_name_bank`/`coin_record` 奖励引擎齐备），真正缺口是**前端视觉（卡片/翻页/3D/三端）、格式规范与自动分类、AI 视频（外部阻塞）、奖励接线**。含 6 子分支依赖图、R3（template 由设计器拖拽）/R11（3 个新端点待批）落地规程、分阶段验收、K1–K6 风险、D1–D8 待拍板 |

## 变更记录

- 2026-11-07：**A2 上传时间 / 发布者 / 最近 7·30 天 已落地（后端 + 前端 API 层）**（`plans/A2_上传时间与发布者_交付记录_v1.md`）。`/api/materials/admin/list` 新增 `created_within=7d|30d`（**滚动窗口**）、`order=created_desc|created_asc`、`publisher_id`；item 增 `created_at`（补 `+08:00`，空值为 null）与 `publisher{id,name,role,role_label}`（一次查询，无 N+1）；排序改按入库时间且 **`create_time` 为空的行恒定排最后**（否则正序时 NULL 会顶到最前）。实测真库：7d=17 / 30d=61 / 全库 119；正序最早 = id 1（2026-10-27）；`created_within=5d`、`order=id_desc` 均 422。前端 `fetchAdminMaterialList()` + 类型（空串参数不下发，避免 422）；pytest 13 passed（同批回归 61 passed）、vitest 6 passed。**数据发现**：119 行里 **58 行 `create_time` 为 NULL**（id 48–105，全是卡片）→ 显示 `—`、不进窗口筛选，**不回填**（无可靠来源，硬填等于伪造）；另记一项待核：`init_material_data.py` 用 SQLite `CURRENT_TIMESTAMP`（UTC）写时间，与 ORM 的本地时间口径不一致，现有 61 行未发现异常时段，E1 渲染时再核。页面上要看到这两列仍需 **A4 换页**
- 2026-11-07：**侧栏配色定 D `#33465F` 并落到真机**（E2 复议收口）。`admin-tokens.css` 新增 `--adm-sidebar/--adm-sidebar-active/--adm-sidebar-active-shadow`；`AdminLayout.vue` 的 `.admin-sidebar` 从写死 `#1A3C6D` 改为 `var(--adm-sidebar)`；激活态由「半透明白 + 红色左竖条 `#C41E3A`」改为**品牌蓝圆角块**（`rgba(64,84,224,.92)` + 9px 圆角 + 阴影），`sidebar-nav` 左右内边距 0→8px。实测（无头 Chrome 读计算样式）：`sidebarBg=rgb(51,70,95)`、`activeBg=rgba(64,84,224,0.92)`、`activeRadius=9px`、`activeBorderLeft=transparent`。示意图 02/04 已同步换色，真机截图存 `assets/管理端画风/06_侧栏新配色_真机落地.png`。**注意**：只改了颜色与激活态，**侧栏「滚动时不动」仍未修**（A5 的 `fixed + margin-left`，因 sticky 被 VTJ 三层 overflow 容器破坏）
- 2026-11-07：**侧栏配色复议（E2 重开）**。你反馈「侧栏颜色过于深沉」→ 出 `assets/管理端画风/05_侧栏配色_六选一.png`：现状 `#1A3C6D`（白字对比度 10.99）+ 5 个候选——A 中蓝 `#24487D`（9.14）/ **B 亮蓝 `#2B5AA0`（6.83，推荐；激活块翻白底更像"选中"）** / C 天蓝 `#3A6BB5`（5.32）/ D 蓝灰 `#33465F`（9.62，不偏纯蓝）/ F 浅色整条 `#FFFFFF`（深字 12.79，最轻）。全部按 WCAG 算过对比度（AA ≥4.5 均满足）。**待你选定**后改 `--adm-sidebar` + `AdminLayout.vue` 里写死的底色（A5 一并换 `var()`）
- 2026-11-07：**画风底座确定后的「各界面预期效果图」出图**（`plans/assets/管理端画风/03_全站12页总览.png`、`04_用户与权限_新画风.png`；配套 `01_令牌与组件`、`02_画风对照`）。12 个管理页**结构全部取自源码实测**（表头列名/页签/按钮文案原样），只换画风：统一后每页只剩三件套 `AdminPageHeader` + `AdminToolbar`/`AdminStatCard` 行 + `AdminTable`；emoji 保留（E3=C）但尺寸对齐由组件统一。逐页对照表已写入 `plans/管理端画风统一_方案_v1.md` §8（页面/现网问题/新画风要点/对应图 四列）；**E2 验收口径明确为「只换皮不换功能」**——列、页签、批量操作、权限判定一个都不减（最重的 users 页 1214 行、8 列 + 4 页签 + 批量条已出全尺寸图）。备注：资料管理页的预期效果早已有图（`assets/资料管理v3/01,05,06`），本批不再重画
- 2026-11-07：**A0 画风基座已落地**（`plans/A0_画风基座_交付记录_v1.md`；裁定 E1=A/E2=A/**E3=C 保留 emoji**/E4=B/E5=A 已回填进 `plans/管理端画风统一_方案_v1.md` §7.1）。新增 `src/styles/admin-tokens.css`（12 色 + 圆角/阴影/字号/间距 + `.adm-btn/.adm-input/.adm-empty/.adm-card` 工具类，**用纯 CSS 变量而非 scss**——仓库未直接依赖 sass）、`src/components/admin/` 6 个组件（Tag/StatCard/PageHeader/Toolbar/Table/FormItem，全部只读 `var(--adm-*)`）、组件库预览页 `/admin/dev/style`；顺手修：面包屑回落到 `route.meta.title`（原先无菜单项的页面只显示"管理端"）、统计卡空值显示 `—` 而非 0。**门禁数字变更**：新增 1 条页面路由 → L6/L7 页面计数 **104 → 105**（两处已同步并写明原因，可回滚）。验证：vitest **20 passed**、`verify-modularization-constraints` 通过（105 处 import 均存在）、`pytest test_route_roles` 5 passed、typecheck 0 新增；真机实测 `--adm-primary=#4054e0`、tone=warn 数值色 `rgb(179,83,9)`；截图 `assets/管理端画风/A0/`。自查出 3 个缺陷并修（模板未定义变量静默失败 / `withDefaults` 把 undefined 变 0 / 面包屑兜底错）
- 2026-11-07：**管理员端画风统一方案 v1（并行轨 E 批 + 前置基座 A0）**（`plans/管理端画风统一_方案_v1.md`）。你要求「维持现有方案，建新版界面的同时把管理员端所有界面换成新画风」→ 不改 A 批顺序，插 A0 基座 + E 批。**实测三条决定性结论**：管理端 12 页里 9 个 `.vtj`（R3 禁改模板）/ 3 个手写页；全仓 **0 个 Element Plus 组件**（"改 el 主题变量"这条路不存在）；**0 个 scss 变量**、新主色 `#4054e0` 出现 0 次。因此定为**三层落地**：令牌（12 色/6 档间距/5 档圆角）→ 6 个 admin 组件 → 页面（4 手写页直接换、9 个 `.vtj` 页用 `.admin-layout` 作用域覆盖层洗一版）。**诚实边界**：覆盖层只能做到"观感统一"、做不到像素级（scoped 特异性 2 需子孙选择器对抗；设计器 iframe 里看不到新画风）。工期 8.2 → **约 14.2 天**，其中 A0 后 1.5 天有组件库、A4 后 3.5 天能看到第一个新画风真页、A5 后外框全站统一。另附 11 张管理端现状真机截图用于走查，起出 6 条现网画风毛病（emoji 当图标/标题与面包屑重复/时间裸 ISO/激活态红竖条/圆角阴影不统一/图表空窗）。**待拍板 E1–E5**（统一程度/侧栏配色/emoji 处置/图表空窗是否本轮修/可读性缺陷是否顺手修）
- 2026-11-07：**A1 类型扩展（讲义/试卷）已落地**（`plans/A1_类型扩展_交付记录_v1.md`）。后端 `materials.py:30 TYPES` 加 `lecture`/`paper`、`admin_stats.by_type` 补两键（零迁移）；前端新增**类型登记表单一真源** `src/modules/library/materialTypes.ts`（6 类 + 中文名 + 徽标色 + 视频/双格式标记），并按 R3 **不改 `.vtj` 模板**、用 DOM 注入 `src/utils/adminMaterialTypes.ts` 给管理页补「讲义/试卷」下拉项与两格统计卡。实测：stats 6 键（lecture 0 / paper 0）、`?type=lecture` 由 400 变 200、非法类型仍 400；vitest 17 passed（含 6 条 jsdom 注入用例）、pytest 29 passed（api_surface/route_roles 证明 R11 343 与 L7 104 未变）、typecheck 0 新增、gate_all **9/10**（唯一 FAIL 为既有 L1-G 题量护栏，与本批无关）；真机截图 2 张（`plans/assets/资料管理v3/A1/`）
- 2026-11-06：**19 条待决策全部裁定，方案冻结为 v3.1**（`plans/待决策裁定结果_v1.md`；`plans/资料管理v3_预览发布者类型双格式试卷讲义_方案_v1.md` 升 v3.1）。你的回法：D28–D31 / D33–D37 / D39 / D21–D24 / D26–D27 全按建议；**D32 改写**（去掉表单必填，只从文件名取科目/年份/地区/题本，没有的先空着，并新增"列表内改信息"弹窗）、**D25 参照 D32**（元数据表降级为可选批量补录）、**D38 改写**（筛选栏加"最近 7/30 天"）。净增量：+1 端点 `PATCH /api/materials/admin/{id}/meta`、+1 组件 `MaterialMetaDialog`、+0.4 天；迁移次数不变；DoD 9→12 条；新增效果图 `05_试卷改信息_弹窗.png`、`06_筛选栏_最近7天30天.png`
- 2026-11-06：**试卷文件名解析实测（517 份真实文件）**（探针 `scripts/probe_paper_filenames.py`，逐文件明细 `plans/assets/试卷文件名解析_实测_v1.csv`）。命中率：科目 100%、年份 100%、地区 99.4%、题本/答案 99.8%、**四要素齐 99.2%（513/517）**、题量与满分 **0%**（文件名里根本没有）→ 支撑 D32「有就读、没有留空、入库后再改」；仅 4 份命名特例解析不齐；`paper_code` 人读码实测 517 份只出现 11 个重复（多为同卷重复件）。
- 2026-11-01：新增 `plans/备考资料_二轮UI与学生自建卡_方案与验收_v1.md`（已交付）。三条实测根因：`/api/badges/my` 漏返 `pinned`（精选点了没反应）、`#vtjLink` 是 `@vtj/pro` 开发期注入的设计器入口（手机端右下角铅笔钮）、学生端建卡缺的是「入口+单卡表单+配图通道」而非整条链路（`POST /api/materials/my` 早已存在）。新增 `POST /api/materials/my/card`（免审批 `status=1`，2 张图分别落 `cover_image` 与 `content`，零表结构变更）与 `GET /api/materials/taxonomy`（只经 catalog 契约取数，声明在 `/{material_id}` 之前）。顺带修徽章页 13px 横向裁切、筛选胶囊换行、CSP `img-src` 无 `blob:` 导致缩略图空白。
- 2026-11-02：新增 `plans/备考资料_三轮PC建卡与全图_方案与验收_v1.md`（已交付）。三条实测结论：「返回首页」镜像源于 `.vtj` 页内 `.back` 类名冲突（顶栏链接与翻卡背面同名）；PC 建卡入口受 R3 约束只能用 DOM 注入（`.mat-page > .top-bar` 之后插一行操作条）；一卡两图拿不全是因为列表 brief 不返回 `content`，已补 `image_urls`。学生端 Excel 批量上传按「还原」口径保留待审（`status=0`），与逐张创建（免审 `status=1`）并存，页面两处文案写明差异。
- 2026-11-02：四轮卡片栈文档升 v2。补四条实测结论：①翻页白框真根因是 `.stack-card` 容器自身 `background:#fff`（不是背景纸片），最终用「后置 3 张真卡片 + 容器透明 + 显式 z-index」解决，翻转时能看到后卡正文；②翻页方向原先两键共用朝左的 `is-leaving`，上一页根本没有独立动效 → 扩出 `entering-prev` 相位，两方向都向右（下一页 `+118%` 飞出，上一页关键帧 `62% → 0` 飞入）；③手机端 Excel 入口藏在弹层里等于没有，弹层第一步底部加显性入口直达 `#/materials/upload?tab=excel`；④浏览器窗口被遮挡时不产帧、CSS 过渡不插值，方向验收改用「样式规则 + 几何位移」而不是读 `transform`。
- 2026-11-02：新增 `plans/备考资料_平板端设计构建现状_核查报告_v1.md`。结论：平板不是「设计过的第三端」，而是「复用手机页 + 零适配代码」——21 条平板路由中 14 条直接复用手机页；`src` 无任何平台分支；卡片在 768 下被拉成 735×226（比例 3.25）、横屏 991×226（4.39）；触控目标最小 28px；平板首页没有备考资料入口（唯一入口「我的 → 离线下载」）。功能全部跑通、横向溢出 0px。附 `scripts/verify/tablet_audit_shots.mjs` 与 11 张平板截图。
- 2026-11-02：平板端 A 档整改落地（同上报告升 v2）。三处关键：①`@media (min-width:700px)` 里给 `.stack-wrap` 写 `max-width` **必须同时写 `width:100%`**——`.page` 是 flex 列容器，光靠 `margin:auto` 会让子项收缩到内容宽（实测被压成 203px，卡片成了细条）；②触控目标用 `@media (pointer:coarse)` 补到 44px，PC 鼠标端零影响；③新增 `/tablet/badges`（复用 PC 徽章页）并把页面路由数 99→100、L6 动态 import 期望 99→100 同步，避免 L6/L7 门禁误判。整改后资料页与 Excel 页小于 44px 的可点元素归零，手机端 390 回归 20/20、gate_all 10/10。
- 2026-11-02：全图查看器补触摸手势（报告升 v3）。`ImageLightbox.vue` 增加单指左右滑动切图 + 双指捏合缩放，算法抽成纯函数 `lightboxGesture.ts`（`clampScale` / `pinchScale` / `swipeDirection`）配 14 条单测；`.lb-stage` 加 `touch-action:none` 避免浏览器抢手势；放大 >1.05 倍时忽略滑动（防止和缩放打架）。验证据 `scripts/verify/tablet_lightbox_gesture.mjs` 用 CDP `Input.dispatchTouchEvent` 真发触摸事件：**9/9 通过**（捏合 180%、放大态左滑不切图、1:1 左滑到 2/2 且缩放复位、右滑回 1/2、捏合不小于 100%）。同时修正一条误报：上传页 `.mc-page` 一直有 `max-width:860px`，上一版量到了 `#app` 才得出「通栏无上限」，已撤回并修脚本选择器。
- 2026-11-02：平板端改为「模仿电脑端布局」（方案 v2 已实施，你的三条决定：A / 保留翻页 / 要进度条）。`mobile_materials.vue` 用 `matchMedia('(min-width:700px)')`、`(min-width:1000px')` 双断点切换：平板渲染 hero（标题+描述+进度，走 `/api/materials/progress-summary`）+ **卡片网格**（768 三列×2 行 = 6 张/页、1024 四列×2 行 = 8 张/页，卡片 236×260 比例 0.91、237×215），点击卡片原地 3D 翻转，网格下方保留「上一页/下一页」并按页翻；手机继续用卡片栈 + 上一张/下一张。下方列表在平板只留视频/文章，不重复卡片。实测：`1/7 页 → 2/7 页`、翻转终态 `matrix3d(-1,0,0,0)`、配图接全图手势 9/9、横向溢出 0px、手机 390 回归 20/20、vitest 34 文件 471、vue-tsc 0、gate_all 10/10。踩坑：CDP 触摸事件在窗口遮挡时会挂住，脚本需 `Page.bringToFront` + `Emulation.setFocusEmulationEnabled`。
- 2026-11-02：新增 `plans/备考资料_分支结构与合并计划_v1.md`（合并待批）。**先纠正语义坑**：`git rev-list --left-right --count main...branch` 第一位是「main 独有」，用第二位判「已合并」会得出「全部已合并」的错误结论；按正确语义，31 个分支里仅 4 个在 main（2 个还是落后 main 27 提交的陈旧集成分支），模块 27 个分支全部未进 main、但**已被 r4 完整包含**。拓扑 `main@da218d1 → 父分支@ce19649 → r2 → r3 → r4@7333222`，main 是 r4 祖先，可 FF。**AI 讲师分支位**：`feat/…-ai-lecturer` 已由 main 前移到 r4（`git branch -f`，空提交位）。完成度：需求 ① ② ③ ⑤ ⑥ 完成、④ 未开工；`gate_all 10/10`、vitest 35 文件 479、vue-tsc 0、手机 20/20、平板同版 31/31、PC 7/7、手势 9/9、工作区 clean。合并方案：先 `backup/main-pre-r4` + `pre-r4-merge` tag → r4 FF 到父分支 → FF 到 main → 合后跑门禁；另列风险回退与 6 条遗留。
- 2026-11-02：**本地开发后端端口统一为 8000**（`chore/dev-port-8000`，已合入 main）。实测 8000 本是工程默认值（`start.py` / `proxy.config.ts` / L4 门禁），8010 仅由 `scripts/dev-restart.ps1` 的 `$BE_PORT` 引入。改 22 个文件：`$BE_PORT=8000`、16 个验收脚本 API 常量 30 处、`seed_material_cards.py`、L4 注释、2 份 ops 手册（加「旧口径 8010」说明）。验收：8000 监听、`/health` healthy、foundation ok、登录 200、代理 200、WS「连接成功」、**`gate_all` 不带 `OPENAPI_URL` 直接 10/10**、PC 7/7、平板 31/31、vitest 35 文件 479、vue-tsc 0。踩坑记录：`edit` 工具抹掉 `.ps1` 的 BOM（PowerShell 5.1 按 ANSI 读 → 语法崩，已补回并在文档里写明）；后台作业 kill 会连带杀掉 `Start-Process` 子进程，重启脚本须重定向到文件运行；`Stop-Port` 未杀掉旧后端时会出现双后端同写 SQLite，须核对命令行 `--port`。
- 2026-11-02：**合并执行完成**（`main` `da218d1 → e3e2e54`，未推送）。备份 `backup/main-pre-r4` + tag `pre-r4-merge` 均指向 `da218d1`；祖先校验通过后两条 fast-forward（父分支 `ce19649 → e3e2e54`、main `da218d1 → e3e2e54`），无 merge commit、工作区零变更（用 `git branch -f` 避免先检出 main 导致 dev server 整模块消失的窗口；前提是祖先校验必须通过）。合后验证：`gate_all 10/10`（首次 9/10 是 L4 默认探测 `127.0.0.1:8000`，本机后端在 8010，设 `OPENAPI_URL` 后 10/10，非代码回归）、vue-tsc 0 error、vitest 35 文件 479、PC 7/7、平板同版 31/31、手机 20/20、全图手势 9/9；`/health` healthy、`/health/foundation` ok（pending 0/dead 0）、openapi 331 路径、`/api/auth/login` 200、Vite 代理 `/api/materials` 200、`/ws/connect` 收到「连接成功」。清理：验证脚本产生的演示卡 111/112 已删除（恢复 102 已发布 + 5 下线 = 107 行），脚本重写的 17 张验收 PNG 已 `git checkout --` 还原。边界：**未推送 origin/main、未删 27 个子分支、未动 4 个未合并远端分支**（`feature/ai-assistant`、`feature/study-plan`、`fix/D1-import-card-type`、`feat/teacher-optimization`）。
- 2026-11-05：**AI 讲师功能要求与目标 v3（需求基准，待确认冻结）**（`plans/AI讲师功能_要求与目标_v3.md`）。你要求「重新梳理要求与目标」。重写原因：需求经 4 次追加（4 条口述 → 3 张截图 → 三项拍板 → 知识库接入 + 限制重查），旧文档里「用户提供知识点清单」「我读不到视频」等表述已过期。文档结构：**4 层来源逐条可追溯**；**13 条要求 R1–R13**（R1 样板+底座、R2 讲解风格/动作/场景跳转/画风、R3 拆解模板化、R4 检查点+正误动画、R5 **专利交底书 B**、R6 版权与法条可核、R7 三端、R8 视觉规范、R9 数据可追溯、R10 性能、R11 工程红线、R12 可维护、R13 可观测降级）每条都配验收方式；**6 个可度量目标**（检查点作答率 ≥70%、单点产出 ≤30 分钟、三种来源可切不换播放器、专利权利要求 3 组、门禁全绿、P1 预留 TTS/导出口子）；**7 条反目标**（不做数字人/现场对话/全自动批量/TTS/导出 mp4/切片真人课/模仿具体老师）；P1–P3 分期 DoD（P1 判定：3 节可在三端播完 + 门禁绿 + 可反查来源 + 关动效仍可读）；**旧文档 6 处表述的取代关系表**（含「AI 视频」口径澄清为网页交互微课、mp4 导出归 P3）；待确认 D1–D5。
- 2026-11-05：**资料导入 P0 实施计划（待最后确认开工）**（`plans/资料多格式导入_实施计划_P0_v1.md`）。你拍板 IMP-5 选 **B（共享组件 + 两个薄壳页）**、其余全部按建议 → 据此出 P0 计划：迁移 `20261105_006` 加 7 列（batch_id / progress_percent / current_phase / total_units / done_units / unit_name / retry_count）；状态机 7 态 + 失败重试 + 重启超时重置；进度 10/10–70/70–90/90/100 分段（PDF 页级、docx 段级、xlsx 行级）；后端只改 `library/materials.py` 并新增 `material_import_queue.py`、`ocr_provider.py`；新增 3 端点（batch 上传 / batch 汇总 / retry）并登记 R11 白名单；前端 `MaterialImporter.vue` 单点维护 + `admin/material_import.vue`（双列）+ `teacher/material_import.vue`（单列）+ 路由 104→106 双改点 + 沿用 `materialsCreateEntry.ts` 的 DOM 注入入口；顺手修 `material_parser.py` 里 `parse_pdf_text` **重复定义**（L159/L253，后者生效）；T1–T8 共 5.5 天，含 3 张真实渲染效果图 `assets/资料导入_P0/`。
- 2026-11-05：**待决策清单 v1（全部决策集中一处）**（`plans/待决策清单_v1.md`）。你要求「把要决策的事情全部列出来」→ 汇总 **27 条**：**A 本轮资料导入 9 条**（IMP-1 MinerU 形态 / IMP-2 单文件 250MB / IMP-3 上限分级 / IMP-4 学生端是否开放 PDF / IMP-5 教师端同页 / IMP-6 轮询 vs SSE / IMP-7 扫描件必须能导 / IMP-8 远端 sidecar / IMP-9 服务器有无 GPU）+ **B 数据运维 7 条**（OPS-1 生产题库怎么弄进来 / OPS-2 删 14.8GB zip 与 3 个 `.part` / OPS-3 合并 BN2027-p01 / OPS-4 大纲 4 条疑似笔误是否改名 / OPS-5 87 知识点入图谱 / OPS-6 Dataview 静态化 / OPS-7 2 个 docs 提交先合 main）+ **C AI 讲师 11 条**（暂停中，恢复再答：交付口径/3 试点/金币/形象/专利/单元粒度/8 个细目归属/别名表/产物落位/无题能否上线/转写范围）。每条含「选项 / 影响 / 建议 / 何时必须答」+ §E 决策→任务映射（谁卡谁）。两种回法：`全部按建议` 或逐条点名。
- 2026-11-05：**资料多格式导入方案 + 三件套安装落地**。①新分支 `feat/material-multi-format-import` 创建，AI 讲师暂停归档（`plans/AI讲师_阶段性成果与暂停记录_v1.md`）。②按你要求先读资料内部格式：`备考资料\` 57 文件 = **30 Excel / 1277 卡**（表头统一 正面·背面·分类·考点·封面）+ **26 PDF / 1619 页**（24 文字型、2 扫描型，最大 204 MB/90 页 0 字符）+ **1 docx / 297 段**；`题库\` 另有 480 PDF（473 文字型/7 扫描）。③**关键发现：后端早就支持 docx/xlsx/文字 pdf，并给扫描件留了 MinerU 异步通道**（`mineru_material_service.py`），但 `C:\mineru_env` 不存在、前端只有学生 Excel 页、导入记录无进度字段 → 真正的缺口是「前端入口 + 批量队列 + 进度模型 + MinerU 环境」，不是"从零做导入"。方案见 `plans/资料多格式导入_现状实测与方案_v1.md`（含新增 3 端点、迁移 `20261105_006`、页面路由 104→105 双改点、P0–P2、D1–D6）。④**E1/E2/E3 已执行**：winget 装 ffmpeg 因走 github releases 失败（github 000）→ 改用 pypi `imageio-ffmpeg`（wheel 内含 9.0.2，复制到 `%LOCALAPPDATA%\hermes\bin\ffmpeg.exe`）；`uv` 不读 pip 镜像配置导致 20+ 分钟下不完 ~100 MB → 加 `--default-index 清华` 后 **53 秒装完** faster-whisper 1.2.1 + rapidocr 1.4.4 + av 18.1.0；OCR 10 帧实测 **45.67 s**，印刷体近乎全对、红笔手写为乱码（与预判一致）；`medium` 模型仍在下载。
- 2026-11-05：**AI 讲师的「看视频」能力已实测跑通**（`plans/AI讲师_视频学习能力方案_v1.md`）。你问「哪个插件能让你获得视觉能力、看视频学讲解风格」——答案是**不需要视觉插件**：`read_image` 本来就是通的，缺的是**视频解码器**；已装的 4 个 DSH 插件（dshmarket/dsh-context/dsh-obsidian/superpowers）都不提供视频能力。**POC 已成功**：`pip install --target %TEMP%` 隔离装 `imageio-ffmpeg`（得到 ffmpeg 9.0.2，未改系统/PATH），从 `桐哥 p06 传唤`（358 MB / 90 min）抽 3 帧并生成 **12 帧 contact sheet**（`assets/AI讲师_视频风格/`），我读出：标题「调查取证——传唤」、三行法条表格、**红笔圈注/下划线/侧边竖排结论**、底部口语字幕、以及**空白《传唤证》实物 + 老师现场填写"2027年1月10日10时5分…15时45分"**。据此已得出 6 条可落地观察（版式固定/标注是主要手段/书面+口语双文本通道/需 `document` 文书场景/`compare` 对比表逐行高亮/单页仅 4–5 分钟 → 微课应 3–5 分钟）。路线对比：A 本机 ffmpeg+我读图（推荐，0 成本）｜B 云 VLM（智谱 200/火山 401/通义 404/硅基 404 可达，但需 key、花钱、粗描述、上传付费课程有版权风险）｜C 本地 VLM（5–15 GB、6 GB 显存需 int4，性价比低）。待批 E1 装 ffmpeg / E2 建 ASR 环境 / E3 OCR。
- 2026-11-05：**限制与缺口清单 v2（重列，纠错版）**（`plans/AI讲师_限制与缺口清单_v2.md`）。你要求「不要因为没有视频之类的就判定为无解」，重查后 **v1 有 3 条判定错、2 条事实错**，已全部更正（媒体不在 E 盘而在 `桌面\名师讲解视频`；台账是**相对路径**、75/76 命中；ffmpeg 未装但 pypi/清华/aliyun 全 200、winget/choco 在位、`imageio-ffmpeg` 免管理员；无 ASR 但本机 RTX 4050 6GB + uv Python 3.11 + hf-mirror 200 → faster-whisper 可跑；法条从 `flk.npc.gov.cn` 取，200）。清单结构：**8 条环境限制（全部可解，含具体命令）+ 20 条资产缺口（A-01~A-20，每条写解法/产出物/优先级）+ 4 条翻案 + 仅 2 条真不可逆（生产题库 10,171 题不在本机、网课版权不可二创分发）**。新增任务 T9（媒体体检与修复：装 ffmpeg、合并 BN2027-p01、抽 12 帧样例）/T10（转写试点 TG2027-p06）；D7 媒体根更正已执行（改 首页 §八 + §一，变更日志已记），D8 是否现在装 ffmpeg+ASR 待你定。
- 2026-11-05：**AI 讲师知识供给适配器方案 v1（待审批）**（`plans/AI讲师_知识供给适配器与播放器衔接_方案_v1.md`）。你的问题是「先做适配器（JSON 树 → point_id + 可讲清单 → `lecture_source.json`，不写前端），再立刻进播放器行不行」。**结论：可以，且应先做**，但实测发现一个会让方案落空的事实——12 个试点单元里 **8 个在 87 知识点里没有对应节点**（立案/管辖/回避/传唤/听证/当场处罚/处罚执行/新旧法对比都是 `GZ-JC-010 行政执法基础知识` 下的程序细目），所以必须加 **topic 教学切片**第三层，否则「一知识点=一节微课」要讲 30 分钟。方案给出：5 条限制解法（`curl github.com` 实测 000 → Dataview 改**静态表**而非装插件；`ffmpeg/ffprobe/whisper` 全无 → P1 不依赖转写；`question_bank` 仅 **200 题**、`question_knowledge` 126 行覆盖 **26/94** 知识点、`point_id` 全 NULL → 检查点题分 `bank/hand/none` 三态）、三层键（`point_id` 87 个 + `topic_id` + `exam_point_id`，冻结 + 墓碑）、可讲清单 5 字段规则、JSON 契约 + sha256 自证、`--check` 防漂移、T0–T8 任务表（含估时与回滚）、写码前 11 问自检、D1–D6 待拍板；另附 3 张真实渲染效果图（`assets/AI讲师_知识供给/`）。顺带纠偏：库内《创新设计》举例 `SL-GN-004 = 影响概括` 实为 `特点概括`（影响概括是 `SL-GN-005`），佐证 ID 必须脚本生成。
- 2026-11-05：**AI 讲师知识库迁入 Obsidian**（`superpowers/specs/AI讲师知识库_迁入Obsidian与知识供给_报告_v1.md`）。库从桌面搬到 `…\OneDrive\文档\Obsidian Vault\AI讲师知识库`，作为现有 vault 的子目录（这样库内 73 个 Canvas `file` 节点仍写 `AI讲师知识库/…` 全前缀、继续解析）；127 文件 240,694 字节搬迁前后一致，`dsh-obsidian@0.2.6` 实测可列/读/搜/写（不走 Local REST API）。**价值判断**：它把 AI 讲师 P1 缺的「知识点清单」直接备好了——3 科目/15 模块/**87 知识点/403 考点**（JSON 树）+ 10 个首批试点考点 + 3 篇讲师范式（桐哥四步：条文定位→程序时序→要件拆解→对比与陷阱）+ 画面渲染规范（1920×1080、96px 安全边距、页脚「模块名·考点ID·页码」、动效 200–400ms + 静态降级、**禁止生成式模型产文字/公式/法条**）。**顺带抓到 3 处缺陷**：①`首页.md` 分科目知识点数 29/28/30 与 JSON 实测 27/25/35 不符（已按铁律「数字必须实测」修正并写 `变更日志.md`）；②`AI讲师数据库创新设计_v1` 声称知识点 ID 表已写入大纲 §3，实测大纲 §3 是「疑似笔误」表、全库无 ID 映射 → DSL `point_id` 暂无可填值；③403 考点仅 312 个不同名，「其他」出现 86 次，另 14 个知识点零考点 → 需可讲清单筛选规则。另修 `docs/README.md` 一条**悬空索引**（`AI讲师知识库_搭建说明_v1.md` 从未入库）。
- 2026-11-04：**AI 讲师功能总体设计方案 v1**（`plans/AI讲师功能总体设计方案_v1.md`，待审批）。按你拍板的三项（A 网页播放器 / 你给清单 / 形象另定）给出可落地全案：知识点清单模板 + 题目格式 + **讲稿 DSL**（segments 六类型、avatar gesture/expression、scene kind、checkpoint question）+ JSON Schema 校验；**微课 7 段式**讲解逻辑（时长占比 + 5 条拆解规则 + 7 类动作触发词库）；参数化 SVG 讲师与 4 类场景（board/formula/police/custom）实现「卡通+正式并存」；播放器**状态机**与三端布局、检查点规则、正误动画（烟花+对勾 / 继续努力+解析）；前端全部新增 `src/views/lecture/*`（不动 `.vtj`，路由 /lecture/:id，页面路由 104→105 需同步）；P2 数据表与 4 个端点 + R11 白名单；**LectureSource 底座**（清单/题目/卡片 → 同一 DSL）；安全合规（禁 v-html、原创形象、LLM 内容须 approved）、运维（版本化/灰度/埋点/降级/回滚）、测试验收矩阵、P1–P3 分期、写码前 7 问自检、开工条件与完整示例脚本。
- 2026-11-04：**AI 讲师功能需求理解与初步设计**（`plans/AI讲师功能需求理解与初步设计_v1.md`，待确认）。把你的 4 条要求逐条复述并落成可执行规格：①先做「预写知识点清单」的样板 + 预留按题/按卡自动生成的底座；②学真人讲解风格/逻辑/肢体动作 + 场景跳转（法条现场/公式动画），画风「卡通+正式并存」；③总结真人拆解讲解的逻辑模板；④检查点弹题（数量不限）+ 正误反馈动画（答对烟花对勾 / 答错解析）。把 3 张截图反推成交互规格（左讲解 2/3 + 右题目 1/3、胶囊选项、绿/橙反馈、答案解析块、大对勾水印、章节时间轴、重播、紫色继续）。**诚实边界**：我无法直接看视频，需你给参考视频/字幕，或按讲授法微课模板 + 参数化动作库（gesture/expression）设计。技术取舍 A/B/C（推荐 A 网页交互播放器，无外部依赖、天然是底座），并给出讲稿 DSL、播放器状态机、P0–P3 分期、需要你提供的 6 项材料。
- 2026-11-04：**AI 讲师开工可行性评估**（`plans/AI讲师开工可行性_评估_v1.md`）。结论：无现成讲师分支（本地占位 `e3e2e54` 落后 main 209 提交；远端 `feature/ai-assistant` 已并入 main 且是对话助手；代码 `ai-lecture/lectureProvider/render_job` 命中 0），**但可在 main 上开分支，第①步不依赖外部服务**。main 可复用：`llm_client`（chat/chat_plan）+ 6 个 `/api/llm` 端点（含 `context/assemble`）+ ChatSession 表 + 知识图谱 14 端点 + Agent 6 端点 + 视频 8 端点 + F3 媒体资产 + `ai_chat.vue`。缺口：契约/任务表/seam 未建、无 TTS/数字人/合成（本机无 ffmpeg）、**LLM_API_KEY 为空**、库内 0 视频。建议从 main 切 `feat/ai-lecturer`，先做「契约+`ai_lecture_job`+状态机+讲稿生成+501 降级+白名单登记+详情页入口」。
- 2026-11-04：**备考资料模块成果总结**（`plans/备考资料模块成果总结_v1.md`）。实测规模：149 提交合入 main（模块相关 135，`materials.py` 改 30 次）、36 个 `/api/materials/*` 端点（全站 462 的 7.8%）、7 张相关表、110 条分类规则、库内 102 已发布（99 卡 + 3 篇科目说明）+ 5 下线、15 个后端测试文件 **151 条断言**、27 份文档。六项需求：①②③⑤ 完成、⑥ 部分（徽章展示层下线、成就金币引擎保留）、**④ AI 讲师/AI 视频未开工**。验收：`gate_all 10/10`、后端 151 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9。顺带修：`test_materials_my_card` 断言旧 `/uploads/…` 路径，F3 媒体资产开启后应认 `/media/{asset_id}`，改成按 `MEDIA_STORE_ENABLED` 二选一。
- 2026-11-04：**挑出本次新增的页面/接口**（`plans/远端main新增页面与接口_v1.md`）。做法：`git worktree` 分别检出 `da218d1`（10-26 老 main）、`8f03a7d`（合并前本地 main）、`89363f5`（当前 main），各自 `openapi()` + 路由表导出后取差集。结果：接口 349→373→**462**、页面 92→98→**105**；**相对老 main 新增 113 接口 / 15 页面、删除 0**；**相对合并前本地 main 新增 95 接口 / 11 页面、删除 6（徽章）**。远端线新增页面 11 条（论坛管理/教师论坛、联考小智、学习计划、知识图谱、AI 记忆、AI 错题本、新闻三端三页），本地线 4 条（资料详情/上传/预览、分类规则后台）。
- 2026-11-04：**修两个红 CI 作业 + 生成页面/接口清单**。①python 质量作业：`black --check` 命中 453 个历史文件（从未全面格式化、开发机也装不上这些工具）→ 拆成「阻断层（新增 `check_eager_annotations.py` 注解前瞻检查 + `compileall`）+ 提示层（black/isort/flake8/mypy 改 `continue-on-error`）」；②前端质量作业：CI node 20 自带 npm 10 与 npm 11 生成的 `package-lock` 不兼容（`EUSAGE: Missing vue-tsc@2.2.12`）→ node 20/22 统一升 **24**。**顺带抓到真 bug**：`materials.py` 的 `UploadFile` 在 744 行才导入、340/520 行签名已引用 → Python < 3.14 导入即 `NameError`（CI 3.13 崩、本地 3.14 因 PEP 649 惰性注解没暴露），已提到顶部导入；新增的注解检查对旧版本能精确报 2 处、对当前 219 文件 0 问题。另：container-ci 的 `gate_all --quick` 含需真实题库的 L1-G（CI 无 DB 必然红）→ 改跑静态门禁；VTJ 工作流加 `workflow_dispatch` 便于验证。结果：VTJ 工作流 **6/6 全绿**。同时产出 `plans/远端main页面与接口清单_v1.md`（页面 105 条 + 接口 465 个操作，带文件:行号链接）。
- 2026-11-04：**合并远端 main + 徽章展示模块下线 + 推送成功**（远端 `main` 已对齐 `88c0bd9`）。① 推送时发现远端已前进 174 提交（模块4/模块7、论坛治理、F3 媒体资产），与本地 149 提交分叉于 `a9e44d9`；先把本地推到远端备份分支 `backup/local-main-1104`，再合并，8 个冲突按「取并集/保留语义」逐个解（models.py 92 类无重名、白名单补登记远端 88 端点、README 远端 29 行集中附录）。② 合并暴露 5 个真问题并修：建卡 500「媒体存储缺少数据库会话」（补 `db/user_id`）、`SESSIONS_UPDATED` 未登记、exam 直读 catalog `QuestionGroup` 触发 L4 cross_write（新增契约 `question_groups_by_ids`）、媒体/图 DDL 的 CRLF checksum、`20261027` 迁移撞号（本地两支改 004/005；本地库补建 graph 两表）。③ 按你要求删除**徽章展示层**：24 文件 + 6 端点 + 3 路由 + `user_badge_top` 表（删前 tag `badge-module-before-delete` + 表数据 JSON 备份），**保留成就/金币/称号引擎**（`badge_task`/`BadgeNameBank`/`badge_service`/`Title`），门禁双改点 104→101。验收：`gate_all 10/10`、守卫 17 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9、openapi 409、库内 107 行。
- 2026-11-02：**分支清理**（`chore/branch-cleanup`）。先存档再删：`plans/分支清理清单_v1.md` 记录 26 个待删分支的 commit sha / 末次提交 / 远端状态（全为本地标签）。判定口径 `main..<branch>` = 0；本地 34 个分支中 33 个已完全并入 main，删除其中 26 个（19 个模块子分支 + 7 个历史分支），保留父分支、r2/r3/r4、ai-lecturer、`backup/main-pre-r4`、端口与 VTJ 修复分支。恢复方式：`git branch <名字> <sha>`；删除命令用 `git branch -d`（未合并会被拒绝）。
- 2026-11-02：**VTJ 版本一致性修复**（`fix/vtj-version-consistency`）。原脚本把「非设计器页面」判成「版本漂移」：`.vtj/vue/` 里 69 个设计器页面（有 `useProvider({id,version})` + 同名 JSON 的 `__VERSION__`）版本一致，但 4 个手写 `teacher_*` 页（`useProvider` 命中 0）与 `TeacherNavHeader.vue`（无 JSON）、`smart_recommend.vue`（有 provider 无 JSON）永远「提取不到版本」→ 脚本 exit 1 → CI 每次 `.vtj/**` 变更必红。同时发现 **CI 跑的是同步模式**：即使有真漂移也会在 CI 的 checkout 里被自动改掉再判通过，等于没拦。修复：`scripts/vtj_version_sync.py` 加 `classify()` 三类判定（设计器页面/无 JSON/无 provider），默认只同步真漂移、`--check` 只读比对并 exit 1、`--strict` 保留旧语义；CI workflow 改跑 `--check`；ops 手册新增 §2.1。验收：默认与 `--check` 均 **69 一致/0 失败/跳过 6**；`--strict` exit 1；注入 `__VERSION__=1` → `--check` 报 `home_page（Vue=1785750000100 JSON=1）` exit 1、同步模式可修、`git checkout` 还原（`.vtj/vue` 零改动）。
- 2026-11-02：新增 `plans/先合并后AI讲师_影响评估_v1.md`（评估，未执行合并）。结论：**先合并对 AI 讲师无副作用**（`main` 是 r4 祖先、`--ff-only` 只移指针、AI 分支位已在 `r4@267da9f`，合后两者同一 commit）；**但远端有 4 个从未进 main 的分支**，其中 `origin/feature/ai-assistant` 已含 `backend/app/services/llm_client.py`(171 行)、`backend/app/api/v1/platform/llm.py`（`/api/llm/chat`、`/api/llm/sessions` GET/POST、`/sessions/{id}/messages`、`DELETE /sessions/{id}`）、`ChatSession`/`ChatMessage` 模型、`.vtj/vue/ai_chat.vue` 与 `src/modules/ai-assistant/*` 实现，`origin/feature/study-plan` 复用**同一 blob** 的 `llm_client.py`（两分支均落后 main 127 提交）——AI 讲师开工前不定处置，必然做出第三份 LLM 客户端。反向两支：`fix/D1-import-card-type` 的修复**已在 r4**（`materials.py:1955-1957`、`type="card"` @1974，测试文件同名不同 blob）应丢弃；`feat/teacher-optimization`(2026-09-01) 改的是已不存在的 `backend/app/api/v1/teacher.py`（现 `platform/teacher.py`），盲合必 modify/delete 冲突。另给 5 个必改协调点（路由计数双改点 98/98、R11 白名单 36 条 + 基线 343 不动、迁移 `YYYYMMDD_NNN` 序号连续、README 索引、`.vtj/**` 触发 VTJ 版本 CI）与 §7 执行顺序（待批）。
- 2026-11-02：**平板与电脑同版落地**（方案 v3 已实施，三条决定：允许收紧顶部 / 竖屏 S2 / 首页切电脑版并采纳 V3）。三条 `/tablet/*`（materials、材料详情、badges）改 **redirect** 到电脑端路径（页面路由 101→98，L6 同步）；`/tablet/home` 的 component 换成电脑首页（**不能 redirect**：device.ts 的 `/home→/tablet/home` 会死循环，R4 不许动）；`src/style/index.scss` 加横屏样式：≤1366 触控 44px、≤1200 资料页收紧顶部、首页 ≤1100 两栏（右栏下移）/1101–1280 收窄。**关键坑**：`.vtj` 页面是 scoped 样式（`.top-section[data-v-x]`，0,2,0），全局 `.home-page .top-section` 同权重且后注入 → 覆盖不生效（首页仍 280/482/320、右栏被裁 131px），必须用 `#app` 前缀（1,2,0）。验收 `tablet_unified_shots.mjs` **31/31**：1024 资料页 **5 列 179×170 / gridTop 421 / 首屏 2 行**、1366 七列、详情两栏(row)、上传 860、徽章 4 列、旧地址 302、首页入口 112×44 且 <44px 元素 3 种尺寸全为 0；`pc_desktop_regression` 7/7、手机 20/20、手势 9/9、vitest 479、vue-tsc 0、gate_all 10/10。同时删除 `mobile_materials.vue` 平板分支（1433→812 行），并把手机验收脚本加 `Page.bringToFront` + `setFocusEmulationEnabled` + 主动 lifecycle，修掉「窗口被遮挡时页面定时器被节流导致翻页断言假失败」。
- 2026-11-02：新增 `plans/备考资料_平板横屏与电脑同版_可行性与预期效果_v2.md`（待拍板，取代 v1 的竖屏口径）。横屏实测：1024×768 / 1180×820 / 1366×1024 打开电脑端资料页分别是 **6 / 7 / 7 列，溢出 0**；但顶部占 474px → **首屏仅 1 行**（1366 为 3 行）。触控 44px 补齐后小目标 5→**0**（顶栏抬高会让 1366 首屏 3→2 行）；再叠「横屏 ≤1200 收紧顶部」的紧凑版 → 1024 变 **5 列 179×170、网格距顶 407、首屏 2 行**。详情页横屏是**左右两栏**（row/侧栏 184，`≤900` 单栏规则不触发），上传 860 居中、徽章 4 列、首页入口 363×69，全部 0 溢出。竖屏无法用 Web 强制锁横屏，建议「请横屏使用」提示（可跳过）。10 张真实渲染图入 `assets/备考资料_平板横屏预览/`，脚本 `scripts/verify/tablet_landscape_preview.mjs`（注入候选 CSS 现场对比基线/触控/紧凑三态）。
- 2026-11-02：新增 `plans/备考资料_平板与电脑同版_可行性与预期效果_v1.md`（待拍板）。你要求「平板与电脑同一套页面、布局相同」。**关键实测**：电脑端资料页用的是 `repeat(auto-fill,minmax(150px,1fr))`，平板 768 自动 3 列（卡片 227×140）、1024 自动 6 列（152×170），**横向溢出 0px**；详情页（单列 + 侧栏 735）、上传页（`.mc-page` 860 上限）、徽章页（3 列）在 768 同样 0 溢出。唯一必须补的是触控：5 个元素 17–34px，全局 `@media(max-width:1024px)` 补完 → **0 个且布局一像素未变**。据此方案 A：三条 `/tablet/*` 改 `redirect` 到电脑端路径、首页入口与「离线下载」改指 `#/materials/xingce`、全局触控 CSS、删平板专用分支，约 0.5 天；7 张**真实渲染**的预期效果图已存入 `assets/备考资料_平板PC同版预览/`，脚本 `scripts/verify/pc_on_tablet_preview.mjs`（注入候选 CSS 现场对比基线/预期）。
- 2026-11-02：平板端补齐三项（你批准后实施，方案 v2）。①「入门讲解视频 / 深度拓展视频 / 备考指南」分区 + 「只看收藏」：逐 type 拉 `/api/materials?subject=&type=&page_size=50`（与 PC 同源、零新端点），视频/文章点击后页内弹层（`<video>` / `renderQuestionContent` 清洗后的正文）；**库内实际 0 条视频**，视频路径靠 CDP `Fetch` 域 mock 验证（不写库）。② 平板首页 DOM 注入「📚 备考资料」入口（守 R3 不碰 `.vtj` 模板）——放在 `.quick-actions` **之后的独立一行**（实测该网格所在中间栏仅 ~107px、4 列每列 80px，塞第 5 列会把卡挤成 62px），`hashchange`/`resize`/1.2s 定时/`MutationObserver` 四重兜底，判定纯函数 8 条单测。③ 新增 `/tablet/materials/detail` 复用 PC 详情页 + `@media(max-width:900px)` 单栏（侧栏 735px 全宽、返回键 44px），并修掉「5 层堆叠卡装饰层向上 60px 盖住字号行」的遮挡。门禁：页面路由 100→101、L6 动态 import 101；vitest 35 文件 479、vue-tsc 0、gate_all 10/10、手机 20/20、全图手势 9/9。
- 2026-10-27：新增 `plans/备考资料模块总体方案_v1.md`（待审批）。六项需求拆成 6 条交付线并给出依赖顺序（doc-content → card → multi-device → growth-link → upload-format → ai-lecturer），父分支 `feat/Study-Material-Management`、子分支 `feat/Study-Material-Management-<子任务>`（因 Git 分支名不能同时是目录）。关键取舍：科目说明复用 `study_material` 的 `type='GUIDE'`（零新表）；卡片分类由 `material_classification_rules` 驱动而非前端硬编码；三端差异在同页按 `meta.platform` 适配（R12 禁复制页）；3D 用 CSS 视差并强制降级；AI 讲评只落契约 + 501 占位（无可用服务前不写实现）；奖励复用 `achievement.condition_code` + 幂等 `coin_record` 防刷。
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

---

## 备考资料模块 · 文档索引（2026-10-27）

| 文档 | 位置 | 说明 |
|---|---|---|
| 模块总体方案 v1 | `docs/plans/备考资料模块总体方案_v1.md` | 6 需求 → 6 交付线，D1–D8 决策，P0–P4 阶段 |
| 真实完成度台账 v1 | `docs/plans/备考资料模块_真实完成度台账_v1.md` | 12 任务逐条核验（11 已完成 / 1 未完成）+ 5 项横切发现 |
| 科目说明 细案 v1 | `docs/plans/备考资料_科目说明文档_细案_v1.md` | 7 条契约实测、T-01~T-07、A1~A7 |
| 科目说明 内容规范 v1 | `docs/plans/备考资料_科目说明内容规范_v1.md` | 落库字段、HTML 白名单、5 节模板、六步校验流水线 |
| 科目说明 验收报告 | `docs/superpowers/specs/备考资料_科目说明_验收报告_20261027.md` | A1–A7（A6 已由用户手机端实测 PASS） |
| 成就金币联动 细案 v1 | `docs/plans/备考资料_成就金币联动_细案_v1.md` | 复用 45 成就引擎，5 个新成就 + 金币幂等/日封顶 |
| 资料卡片视觉 细案 v1 | `docs/plans/备考资料_资料卡片视觉_细案_v1.md` | 管理员端上传实跑、D1 缺陷、翻转/翻页/字号范式 |
| **资料卡片三端视觉 v2** | `docs/plans/备考资料_资料卡片视觉_细案_v2.md` | PC/平板/手机布局、设计令牌、R3 分工 |
| **资料卡片导入缺陷报告** | `docs/superpowers/specs/资料卡片导入缺陷_报告_v1.md` | 8 个缺陷（D1 阻断级）+ 实测证据 + 修复顺序 |
| 预期效果图（科目说明） | `docs/plans/assets/备考资料_科目说明/` | 3 张：PC 列表页 / 弹窗 / 手机端 |
| 预期效果图（卡片） | `docs/plans/assets/备考资料_卡片/` | 5 张：翻转 / 翻页堆叠 / 字号三档 / PC / 手机（平板复用手机页，不单独出图） |

> 归档规则见 `AGENTS.md` §1；`solve_problems_files/` 已不存在，故统一归档至 `docs/`。

---

## 备考资料模块 · 卡片与分享 方案索引（2026-10-27）

| 文档 | 位置 | 说明 |
|---|---|---|
| **卡片与分享 总体解决方案 v1** | `docs/superpowers/specs/备考资料_卡片与分享_总体解决方案_v1.md` | 六批次路线（B1 个人库→B2 分享→B3 配图→B4 手机栈→B5 PC 页→B6 内容）、写码前 11 问自检、风险 R-1~R-6、待决 Q1–Q10 |
| 卡片 v5 设计 | `docs/plans/备考资料_卡片v5_堆叠3D与分享_设计方案_v1.md` | 堆叠口径修正、3D 视差、配图上传、分享表设计 |
| 卡片 v5 效果图 | `docs/plans/assets/备考资料_卡片_v5/` | 2 张：5 层堆叠+配图卡、3D 视差说明 |
| 卡片 v4 效果图 | `docs/plans/assets/备考资料_卡片_v4/` | 7 张：三端进入页、行测 TAB、申论长文本、公专配图、动效四阶段 |
| 导入缺陷与修复 | `docs/superpowers/specs/资料卡片导入缺陷_报告_v1.md`、`…D2-D5修复_报告_20261027.md` | D1–D8 台账（D3 已勘误）、D2/D4/D5 修复 |

### 运维手册

- [备考资料_部署与数据初始化_v1.md](ops/备考资料_部署与数据初始化_v1.md) — 部署/初始化/自检/回滚/故障对照

- [分类规则维护页_设计器拖拽清单_v1.md](plans/分类规则维护页_设计器拖拽清单_v1.md) — R3 合规：容器/类名清单 + 接口契约，用户拖模板、AI 写 script

- [学生端退出登录_方案B_设计与效果图_v1.md](plans/学生端退出登录_方案B_设计与效果图_v1.md) — 全局悬浮退出按钮：可行性、位置比选、三态与验收

- [PC详情页外观v2_方案与效果图_v1.md](plans/PC详情页外观v2_方案与效果图_v1.md) — 题干灰底块/三列信息/两行列表：字段映射、边界处理、V1–V8 验收

- [徽章设计_风格与数量_v1.md](plans/徽章设计_风格与数量_v1.md) — 四类形状×三档品质、总量 72 枚规划、badge_name_bank 命名依赖

- [徽章设计_风格与数量_v2.md](plans/徽章设计_风格与数量_v2.md) — 四类形状×**五档**品质（全渐变，钻石加光晕星芒）、阶段一 54 枚、积分阈值 200/400/600/800

- [徽章页面设计_分析与效果图_v1.md](plans/徽章页面设计_分析与效果图_v1.md) — 我的徽章页/详情弹层/主页徽章墙的页面级分析与三态设计

- [门禁红灯根因分析_L1G与L2_v1.md](plans/门禁红灯根因分析_L1G与L2_v1.md) — L1-G 数据事故（本机备份不可用）+ L2 判据 bug（4/85→65/85）

- [P0-P3缺陷处置总体方案_v1.md](plans/P0-P3缺陷处置总体方案_v1.md) — 题库恢复三方案/ L2 白名单 / P1-P3 逐项设计与波次计划（待批准）

- [备考资料模块_后续工作流程_v2.md](plans/备考资料模块_后续工作流程_v2.md) — 题库不上线前提下的 A–E 五阶段工作流（门禁收口/内容/徽章/专利/交付）

- [备考资料模块_六项需求对照与工作流程_v3.md](plans/备考资料模块_六项需求对照与工作流程_v3.md) — **以六项需求图为纲**：实测覆盖（55/95/45/0/70/65%）+ 三个架构判断（考点层缺位/学生端无上传/AI 讲师边界）+ P1–P7 十三个工作日排期 + D1–D5 决策

- [备考资料_上传格式规范_v1.md](plans/备考资料_上传格式规范_v1.md) — 表头/别名/上限 + 错误码 E001–E010 + 阻断与跳过的分级 + 与分类机制的衔接

- [备考资料_徽章收尾与剩余任务方案_v1.md](plans/备考资料_徽章收尾与剩余任务方案_v1.md) — P5 徽章收尾五项 + 除 AI 讲师外全部剩余任务 + 完成顺序 + 六轮可行性检验 + D1–D4 决策

- [备考资料_三端操作视觉验收_报告_v1.md](plans/备考资料_三端操作视觉验收_报告_v1.md) — CDP 驱动三端实操作截图 9 张、横向溢出 0 处、脚本缺陷复盘与未覆盖项

- [备考资料_P4验收_字号与性能_报告_v1.md](plans/备考资料_P4验收_字号与性能_报告_v1.md) — 字号三档实测 11.7/13/14.95px、FCP 36ms、接口 10–25ms、动画 62fps（6 项全 PASS）

- [专利交底书A_文档格式规范化与分类机制_v1.md](plans/专利交底书A_文档格式规范化与分类机制_v1.md) — 需求(3)【专利申请】交底书：表头归一/三级校验/两级分类/权利要求草案 7 条

- [备考资料_分类准确率回归_F1F2_v1.md](plans/备考资料_分类准确率回归_F1F2_v1.md) — 30 样本回归：考点 100%、子类 93%；未分类兜底实现与取舍

- [备考资料_科目说明抽检_报告_v1.md](plans/备考资料_科目说明抽检_报告_v1.md) — 三篇 1078/1117/1275 字、0 套话 0 异名、子类覆盖 15/16（缺空类目科学推理）

- [备考资料_本地开发与门禁手册_v1.md](ops/备考资料_本地开发与门禁手册_v1.md) — 一键重启(dev-restart/LAN IP 探测)、10 层门禁、分类词表维护、上传与待审、验证脚本清单

---

## 远端 main 新增文档（合并收集，2026-11-04）

> 来源：`origin/main` 在合并基点 `a9e44d9` 之后新增的索引行（F1/F2/F3 底座、D1 报告等）。
> 这些行原本在远端 `docs/README.md` 里，合并时本文档按本地结构重整，故在此集中保留，避免索引丢条目。

| `superpowers/specs/砺安题库终态总体架构_v2.0.md` | v2.1 | ✅ 已批准（D1–D17）；F0–F6、F2b-1 与 F2b-2 已执行 | **终态架构 + 多库一致性底座**：1 SoT（SQLite）+ 4 类可重建投影 + 事务 Outbox/幂等投影/对账；对草案 10 处硬修正、F0–F6 主干路线、L7 门禁（当前 21 项）、Agent 规约；端×角色（3×3）一致性与空库审计；**v2.1 新增容量预算(§17)/数据卫生(§18)/写入准确性(§19)/三端通信 SLO(§20)/可落地自证(§21)**；业务功能模块不在此方案 |
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
| `superpowers/specs/多人协作Git网络稳定方案_v1.md` | v1 | ✅ 已定稿（2026-10-29） | 同伴 ghproxy 镜像停服导致 pull 失败：清镜像改写 + canonical/SSH-443 回退 + 过滤克隆（`.git` 917 MB → 1.1 MB）+ bundle 离线交接 + 一任务一分支规约；配套 `scripts/dev/git-collab-doctor.ps1` |
| `superpowers/specs/容器化部署方案_v2.0.md` | v2.0 | ✅ P1–P6 已完成（2026-10-31）；真实学校上线待维护窗口 | **纯容器化版**：web + backend 两容器核心，SQLite 不容器化；parser/Redis/MinIO/Neo4j/Milvus 全部 profile 可选；四库映射的挂载/备份/可重建边界；七条硬约束（安全左移、资源生命周期、状态有家、网络可控、不可变镜像、可观测、协作变更）；旧 compose 12 项缺陷 C1–C12；迁移/备份/恢复、P0–P6 路线、DoD 与风险 K1–K12；P1 已落盘 `deploy/docker-compose.yml`、`deploy/Dockerfile.web`、`deploy/preflight.sh` 与根 `.dockerignore` |
| `superpowers/specs/容器化P1实施与验收_报告_v1.md` | v1 | ✅ 已完成（2026-10-30） | P1 交付记录：新增 `deploy/docker-compose.yml`、`deploy/Dockerfile.web`、`deploy/preflight.sh`、根 `.dockerignore`；parser 改非 root；web 镜像 105MB，backend 镜像 `b420c0f20afb`/1.8GB（无 Chromium）；staging 双容器登录、3268 题、题图、开考、交卷、重启持久化全通过；修复 passlib/bcrypt、pydantic-settings、email-validator、种子 scripts、nginx `^~ /static/` 与 `$http_host` 六处部署缺陷 |
| `superpowers/specs/容器化P2_staging核心启动与隔离_报告_v1.md` | v1 | ✅ 已完成（2026-10-30） | P2 交付记录：staging 用 `sqlite3.backup()` 复制数据库（58,130,432 B / sha256 c06a4144…），独立复制 static（151,457 文件）与 uploads（5,960 文件）；web/backend 双容器 healthy，登录、3268 题、题图、复合题 5/5 同组材料、开考/交卷、`down` 不加 `-v` 后 `up` 数据仍在全部通过；生产/staging 六表计数逐项一致；容器非 root、read_only、cap_drop、limits 实测生效；记录“宿主直写 SQLite 后需重启 backend”这一 staging 操作约束 |
| `superpowers/specs/容器化P3_OCR与导入_报告_v1.md` | v1 | ✅ 已完成（2026-10-30） | P3 交付记录：parser 非 root（10001）+ CPU torch 2.8.0 + MinerU 3.4.5 + 离线模型卷；扫描件 OCR 220.9s 出 8 题，4 张图回传并作为真实 PNG 落盘（题 113 的图 GET 200 / 16,421 B）；停 parser 与 PARSER_URL 置空时文本导入仍为 pdfplumber 12 题 4 组；单测 28 passed、gate quick 4/4；记录 OCR 材料分组限制与 WAL checkpoint 运维要求 |
| `superpowers/specs/容器化P4_OCR归一化与nginx动态解析_报告_v1.md` | v1 | ✅ 已完成（2026-10-31） | P4 交付记录：OCR ASCII 材料序号/粘连题号归一化后，真实扫描件从 8 题 8 单题组恢复为 10 题 2 组×5（106–115）；nginx 改 Docker DNS + 变量 proxy_pass，占旧 IP 逼 backend 换 IP 后不重启 web 仍 200；可选 TLS overlay（自签 8443/healthz 200）；P5 脚本（checkpoint/backup/restore/inspect）与 CI 骨架已落盘；镜像扫描因 trivy-db 下载被网络拒绝而未完成 |
| `superpowers/plans/容器化P4-P6实施计划_v1.md` | v1 | ✅ P4–P6 已执行（2026-10-31） | 把 P3 后的残留问题分为 S1–S7：P4 做 OCR 归一化/nginx 动态解析/可选 TLS/扫描压测；P5 做 WAL checkpoint、宿主级备份与恢复演练、inspect、CI；P6 做 production env、release 脚本与学校服务器切换 Runbook |
| `superpowers/specs/容器化P5_备份恢复与巡检_报告_v1.md` | v1 | ✅ 已完成（2026-10-31） | P5 交付记录：`checkpoint.sh` WAL 强制落盘（busy/log/checkpointed 实测）；`backup.sh` 用 `sqlite3.backup()` 产出 56.43 MB 一致性备份 + sha256 + manifest + latest.json，并支持资产/异地副本；`restore.sh` dry-run 与真实恢复演练（marker 表被覆盖、四表计数复原、backend 自动 healthy）；`inspect.sh` 正常 0 FAIL/0 WARN、人为过期备份返回 1；CI workflow YAML 通过；trivy 仍受网络限制未完成 |
| `superpowers/specs/容器化P6_生产切换准备_报告_v1.md` | v1 | ✅ 已完成（2026-10-31；上线待服务器） | P6 交付记录：生产 env 模板、`release.sh`（preflight→checkpoint→backup→pull/build→up→healthy→smoke，失败回滚上一 tag）、preflight 拒绝 `latest`/`CHANGE_ME*`/`REPLACE_*`；`release.sh --dry-run` 在临时 production env 下全绿；明确未做真实 registry/生产目录/域名切换/RTO 实测，Chromium 镜像与 trivy 扫描仍受限 |
| `ops/容器化生产切换Runbook_v1.md` | v1 | ✅ 已落盘（2026-10-31） | 学校服务器切换操作手册：切前检查、目录权限、`sqlite3.backup()` 迁移、静态/上传 rsync、生产 env、首次启动、13 项烟测、DNS/网关、24h 观察、发布与回滚、RTO/RPO 目标、禁止事项与故障速查 |
| `ops/GitHub协作与容器化交付手册_v1.md` | v1 | ✅ 已落盘（2026-10-30） | 面向同伴与学校运维的操作层：Git remote 清理/canonical/SSH-443、过滤克隆、一任务一分支、提交与 PR、禁止入库清单、容器镜像发布/服务器更新/备份/烟测/回滚、常见故障排查与检查清单 |
| `superpowers/specs/教师端题目展示与成绩管理整改方案_v1.md` | v1 | ✅ 已实施并验收（2026-10-31） | 教师端四大类整改：图片/答案解析渲染、申论多材料分层+要求保留、小图 OCR 原位、成绩管理合并、试卷编辑 1:1；含 7 条实测根因、D1–D8 决策、P0–P7 路线、I1–I10 创新点（推荐 I1–I5+I7）、A1–A16 验收；raw 页零模板改动，新建 2 个手写页 |
| `superpowers/plans/教师端题目展示与成绩管理整改实施计划_v1.md` | v1 | ✅ P0–P7 已完成（2026-10-31） | 与方案配套的 35 个任务：P0 基线/备份→P1 解析与 requirements→P2 统一渲染→P3 OCR 审阅→P4 成绩→P5 试卷编辑→P6 三端→P7 验收；每任务含文件、角色、预算、验收命令与回滚点 |

---

## 远端 main 追加条目（2026-11-04 二次合并）

> 来源：`origin/main` 本次 141 个提交（模块4/7、媒体资产、门禁）新增的索引行与变更记录；
> 本地 README 结构优先，这些条目集中保留，避免索引丢项。

| `superpowers/specs/AI名师讲解视频_v1.md` | v1 | 📋 方案（待审批，未实施） | AI 名师讲解视频全链路方案：角色定位/图谱三图族/7 工位生产引擎/五库职责/管理员端→学生端/可视化治理；14 章 + 证据表；D1–D8 待批 |
| `superpowers/specs/AI讲师知识库_搭建说明_v1.md` | — | ⚠️ **索引悬空（文件不在仓库）** | 本条引自远端 2026-11-04 追加块，但 `git ls-files`/`git log` 均无此文件——从未入库。库本体在 Obsidian vault：`C:\Users\35709\OneDrive\文档\Obsidian Vault\AI讲师知识库`（2026-11-05 起），仓库侧记录改看下一行 |
| `plans/AI讲师_知识供给适配器与播放器衔接_方案_v1.md` | v1 | 🟡 **待你审批**（未写代码、未建分支、未改库内笔记） | 回答「先做知识供给适配器、再立刻进播放器行不行」。实测结论：**可以且应先做**，但必须有 **topic（教学切片）** 第三层——12 个试点里 8 个（立案/管辖/回避/传唤/听证/当场处罚/处罚执行/新旧法对比）在大纲 87 知识点中**没有对应节点**（它们是 `GZ-JC-010 行政执法基础知识` 下的程序细目），只有 point 一层则无处安放。方案含：5 条限制的逐条解法（Dataview 因 `github.com` 实测不可达 → 改**静态表**；无 ffmpeg/whisper → P1 不依赖转写；题库仅 200 题/26 个知识点有题 → 检查点题三态 bank/hand/none；ID 表由脚本生成；索引悬空已修）、三层键体系（`point_id` / `topic_id` / `exam_point_id`，发布后冻结+墓碑）、可讲清单 5 字段分级规则（lectureable/granularity/tier/coverage/est_minutes）、`lecture_source.json` 契约与 sha256 自证、生成器 CLI（build/--check/--stats）、三道离线校验、T0–T8 任务分解（含预期效果/估时/回滚）、写码前 11 问自检、6 条风险与 D1–D6 待拍板；附 3 张真实渲染预期效果图（数据流 / 可讲清单 / 播放器首屏） |
| `plans/AI讲师功能_要求与目标_v3.md` | v3 | 📋 **需求基准，待确认后冻结** | 因需求经 4 次追加（4 条口述 → 3 张截图 → 三项拍板 → 知识库接入+限制重查）而重写，作为此后设计与验收的唯一基准。含：**4 层来源可追溯**（业务需求④【专利】/4 条口述/3 张截图/4 次决策）、**13 条要求 R1–R13 每条带验收方式**（样板+底座、学讲解风格与场景跳转、拆解模板化、检查点+正误动画、专利交底书 B、版权与法条可核、三端、视觉规范、数据可追溯、性能、工程红线、可维护、可观测降级）、**6 个可度量目标 G1–G6**（检查点作答率≥70%、单点产出≤30 分钟、三种来源可切、专利权利要求 3 组、门禁全绿、P1 不埋死路）、**7 条反目标 N1–N7**（不做数字人/现场对话/全自动/TTS/导出 mp4/切片真人课/模仿具体老师）、P1–P3 分期 DoD、旧文档 6 处表述的**取代关系表**、5 个待确认口径 D1–D5（AI 视频验收口径 / 3 个试点 / 金币计入 / 形象草案 / 交底书范围） |
| `plans/资料多格式导入_现状实测与方案_v1.md` | v1 | 📋 **待审批**（分支 `feat/material-multi-format-import`，未改代码） | 你要求「不要只靠 Excel 导入，按实际资料格式扩充三端上传 + 进度条」。**实测发现后端早已支持 docx/xlsx/文字型 pdf，甚至给扫描件留了 MinerU 异步通道**（`POST /admin/import/upload`、`/status`、`/preview`、`/confirm`、`/import-records`），但：①前端只有学生页 `material_upload.vue` 且 `accept=".xlsx,.csv"`，管理员低代码页无导入入口；②`C:\mineru_env` **不存在** → 扫描件必失败；③`material_import_record` **无进度字段**（对照 `question_import_record` 早有 `progress_percent`+`current_phase`）；④单文件、仅管理员。**资料格式实测**（`备考资料\` 57 文件 223.8 MB）：**30 Excel / 1277 张卡**（sheet 名 4 种但表头统一 5 列：正面/背面/分类/考点/封面，5–201 行）、**26 PDF / 1619 页**（24 文字型 1594 页 + **2 扫描型 25 页，其中 204 MB/90 页 0 字符**）、**1 docx / 297 段 0 表格**（带"高频考点★★"）；题库另有 480 PDF（473 文字型/7 扫描）。现状只能导入 30 个文件 ≈53%。方案：三段式进度（上传 0-10 / 解析 10-70 / 提取 70-90 / 待确认 90-100，PDF 页级、docx 段级、xlsx 行级）、批量批次 `batch_id` + 队列 + 失败重试、格式→解析器映射表（含 .doc/.md/.txt/.pptx/图片）、新增 3 端点 + 1 迁移（`20261105_006`）+ 页面路由 104→105 双改点、MinerU 本地 venv vs 在线 API 对比（建议本地，代码已按本地写好且要求纯 ASCII 路径）、P0–P2 分期与验收、D1–D6 待拍板 |
| `plans/待决策事项_逐条说明_v1.md` | v1 | ✅ 已全部裁定（2026-11-06，结论见 `plans/待决策裁定结果_v1.md`） | 把 19 个待决策问题逐个讲清楚「到底在定什么」：**A 组开工阻塞 12 条**（D28 新建手写管理页 vs 设计器改造 / D29 类型键名与中文统一 / D30 双格式=一条资料两份文件 / D31 主文件 docx / D32 试卷元数据表单必填 / D33 申论 4 题本轮不拆题 / D34 旧 `.vtj` 页保留 / D35 侧栏冻结用全局 CSS / D36 批量 50 个 / D37 上传时间取入库时间 / D38 不加时间筛选 / D39 先做 v3 A 批、进度迁移并入 B 批）；**B 组下一阶段 7 条**（D21 拆题归 P2 / D22 三份样例 / D23 原卷与题目双存 / D24 人读 paper_code / D25 元数据落库 / D26 新建手写页承接归属试卷 / **D27 原建议作废：`study_material` 无 `source` 列，改为新增 `paper_code` 列**）；**C 组 AI 讲师 11 条暂停**。每条含「背景 / 要决定的事 / 选项差异与后果 / 我的建议 / 影响范围」，末尾附一页速查表 |
| `plans/资料管理v3_预览发布者类型双格式试卷讲义_方案_v1.md` | v3.1 | ✅ **裁定后终稿、已冻结**（未写业务代码；不动 main） | 按你 4 条要求重构：**实测先抓出 3 个真问题**——①`04_讲义_正常` 被存成 `card` 且导入两条（ID 121/122，前端 select 默认值 `card` 与唯一选项 `article` 不匹配）；②类型白名单只有 `video_intro/video_advanced/article/card`（`materials.py:30`），**没有讲义/试卷**；③列表无发布者、无预览（`creator_id` 119/119 有值）。**页面**：新建手写页 `src/views/admin/materials.vue` 替换路由（不动 `.vtj` 模板，旧页保留可回滚）+ 统一预览抽屉（6 类型各自渲染）+ 发布者列 + 6 项类型筛选 + 试卷/讲义行显示元数据 + 批量双格式导入弹层。**后端**：类型加 `lecture`/`paper`（零迁移）；新增 `material_file`（一资料多文件，pdf+docx 配对，主文件优先 docx）；`study_material.paper_code` 一列（唯一迁移）；4 个新端点（preview/batch/batch 汇总/publishers）+ 列表增 `publisher/files/paper` 字段；试卷三科格式（行测·公专全选择题，申论 4 道论述题）；侧栏冻结走全局 CSS（不改模板）。**分支**：`feat/material-admin-v2` 从现有导入分支切出，A/B/C/D 四批提交，**不合并 main**。T1–T12 约 8 天；附 4 张效果图；**含「上传时间」列功能规格**（语义区分上传/入库时间、格式/排序/空值/时区、接口新增 created_at、3 条验收用例）；待拍板 D28–D38 |
| `plans/待决策裁定结果_v1.md` | v1 | ✅ 19 条全部裁定（2026-11-06） | 把 D21–D39 一次落定：**17 条按建议 + 2 条你改写（D32/D38）+ 1 条跟随（D25）**。核心三处细则：①**D32 试卷元数据「只读文件名」**——取消表单必填，只解析科目/年份/地区/题本·答案，解析不出的**留空不阻断入库**；附实测命中率（517 份文件名：科目/年份 100%、地区 99.4%、题本答案 99.8%、四要素齐 99.2%、题量/满分 0%）与 `paper_code` 人读码生成/去重规则；②**「改信息」编辑弹窗**——列表操作列新增按钮，弹窗全字段非必填、只做格式校验，保存走新端点 `PATCH /api/materials/admin/{id}/meta`，同步 `exam_paper/exam_paper_tag`、按需重建 `paper_code`、写审计 jsonl、乐观锁 409；③**D38 时间范围筛选**——筛选栏加「全部/最近 7 天/最近 30 天」，滚动窗口口径、可与其他筛选叠加、右侧显条数。另含 v3→v3.1 增量表（端点 4→5、白名单 +4→+5、组件 2→3、工时 8→8.2 天、DoD 9→12）与证据复现命令 |
| `plans/A1_类型扩展_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07） | v3.1 方案 **A 批第 1 项**的交付记录。**改了什么**：后端 `TYPES` 白名单加 `lecture`/`paper` + `admin_stats.by_type` 补两键（零迁移、 筛选 L86 与新增/编辑 L898 共用同一白名单）；前端建**类型登记表单一真源**（6 类 + 中文名 + 徽标色 + 视频/双格式标记，消灭"下拉/徽标/统计"三处各写一遍文案的老问题）；按 **R3 不改 `.vtj` 模板**、用 **DOM 注入** 给管理页补「讲义/试卷」下拉项与两格统计卡（`select` 节流 15s、20s 刷新、单例幂等、离开页面自动移除，A4 换手写页后删一个文件+一行安装即可）。**证据**：真机 DOM 证据（7 个类型选项 / 6 格统计卡）+ 2 张真实截图；`?type=lecture` 400→200、非法类型仍 400；vitest 17 / pytest 29 / typecheck 0 / gate_all 9-10（唯一 FAIL 为既有 L1-G 题量护栏）。含**没做什么**清单（徽标配色归 A4、导入向导仍旧 4 类归 B3、改信息弹窗归 C2b）与三种粒度回滚方案 |
| `plans/A2_上传时间与发布者_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，后端+前端API层；页面待 A4） | A 批第 2 项。**后端**：`admin/list` 增 `created_within`（滚动窗口 7d/30d）、`order`（created_desc/asc）、`publisher_id`；item 增 `created_at`（naive 本地时间补 `+08:00`）与 `publisher`（nickname→username 回退，一次查询无 N+1）；**NULL 时间行恒定排最后**。**前端**：`fetchAdminMaterialList` + 类型，空串参数不下发。**实测**：7d=17 / 30d=61 / 119；正序最早 id 1；非法值 422；pytest 13 + 回归 61、vitest 6。**数据发现**：58/119 行 `create_time` 为 NULL（id 48–105 全卡片）→ 显示 `—`、不进窗口筛选，决定**不回填**；另记一待核项（`init_material_data.py` 用 UTC `CURRENT_TIMESTAMP`）。**未做**：页面列/排序/时间范围下拉（A4）、预览抽屉（A3） |
| `plans/管理端画风统一_方案_v1.md` | v1 | 📋 **待你拍板 E1–E5**（未写业务代码） | 回答「建新版界面的同时把管理员端所有界面换新画风」。**实测盘点**：`/admin` 下 12 个真实页面（9 个 `.vtj`：dashboard 455 / questions 942 / materials 728 / profile 451 / help 294 / papers 214 / backup 111 / settings 97 / logs 90 行；3 个手写：users 1214 / material_rules 622 / forum 359）+ 2 条 redirect + **3 个已无路由的死页**（不参与改造）；全仓 **0 个 `<el-` 组件**、**0 个 scss 变量**、`#4054e0` 出现 0 次 → 没有"一键换肤"捷径。**三层架构**：`src/styles/tokens.scss`（12 色 + 形状/字号/间距）+ `src/styles/admin-theme.scss`（仅 `.admin-layout` 作用域覆盖 9 个 `.vtj` 页）+ `src/components/admin/` 6 个组件（StatCard/Toolbar/Table/Tag/PageHeader/FormItem）。**排期**：前置 A0 1.5 天（零风险纯新增）→ A2/A3 → A4 用组件做样板页（+0.5）→ A5 与 AdminLayout 重绘合并（+0.2）→ E1 覆盖层 1.5 天 → E2 三页换组件 2 天 → E3 走查 0.5 天；总 8.2 → **14.2 天**，可见里程碑：A4 后 3.5 天见第一个新画风真页、A5 后外框全站统一。**6 条风险**（特异性战争、`!important` 误伤弹窗、泄漏到学生端、users 1214 行回归、设计器预览看不到、拖慢 B/C 批）+ 六条 DoD；**E1–E5 待拍板**，附 11 张现状真机截图与 2 张设计稿（`assets/管理端画风/`） |
| `plans/A0_画风基座_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07） | 画风轨第 1 项交付记录。**内容**：`admin-tokens.css`（12 色 + 5 档圆角 + 2 档阴影 + 字号 + 6 档间距 + 4 个工具类）、6 个 admin 组件（`AdminTag` 6 类徽标 / `AdminStatCard` 含 emoji 与 `—` 空值 / `AdminPageHeader` / `AdminToolbar` / `AdminTable` 表格壳 / `AdminFormItem`）、组件库预览页 `#/admin/dev/style`（E1/E2 的唯一视觉基准）、`AdminLayout` 面包屑回落 `meta.title`。**为什么不用 scss**：仓库未直接依赖 `sass`，CSS 变量在 `.vtj` 旧页的覆盖层里同样可读。**门禁变更**：新增 1 条页面路由 → L6/L7 **104→105** 两处同步（历史同类变更有先例，注释写明原因，可回滚）。**验证**：vitest 20 passed（含模板未定义变量、undefined→0 两个真实缺陷的回归用例）、L6/L7 通过、typecheck 0、真机 DOM 证明令牌生效（`#4054e0` / `rgb(179,83,9)`）。**没做**：12 页实际改造（E1/E2）、侧栏冻结（A5）、图表空窗（E4=B 另开单）、时间批量格式化（随 E1） |
| `plans/试卷元数据与题目导入关联_方案_v1.md` | v1 | 📋 待确认（P2 题目线，本轮不动） | 回答「题目导入怎么和试卷元数据关联」。**核心：用 `exam_paper.paper_code` 做唯一关联键**——①上传模板 3（7 列）→ upsert `exam_paper` + `exam_paper_tag`（年份/地区/类型/科目）；②题目导入时把 `paper_id`/`paper_code` 传进 `/confirm`（现只按 `paper_name` 猜）→ 题目进 `question_bank` 并由 `paper_question_relation` 挂卷；③原卷 `study_material(type='paper')` 用 `source` 写同一 `paper_code`，实现「看原卷↔练题目」且**一份卷只存一份文件**。实测现状：`exam_paper` 3 行（含 1 条测试）、`exam_paper_tag` 2 行且 **exam_province 全 NULL**、`paper_question_relation` 200 行、`question_bank` 200 题 **point_id 全 NULL**；`/batch-parsed` 已有「自动创建/复用 ExamPaper + 建 relation」能力，但试卷名靠 `_extract_paper_name` 猜。需新增 6 项小能力（元数据导入端点、paper_code 生成器与地区码表、confirm 支持 code、归属试卷下拉（R3 下建议新建手写页）、题目回填考点、重复导入保护）；待拍板 D24–D27 |
| `plans/资料_素材体检报告_v1.md` | v1 | ✅ 已生成（2026-11-05，T0.3） | 预检器 `scripts/precheck_materials.py` 对 `备考资料\` 全量跑：**52 个正式素材 0 阻断、14 条提示**（W208 混合型 PDF ×10、INFO ×7、W201 无 Heading ×1（`公安基础知识.docx` 149 段）、W205 法条缺条号 ×6、W206 章节不可切分 ×1（`100条中国历史文化常识.pdf`）、W207 页数 576>300 ×1（`申论金词500.pdf`））。首轮曾出 4 个阻断，全在 `_模板`/`_测试文件` → 据此新增 4 条豁免规则（X1 跳过 `_` 前缀目录、X2 单页/总图不要求章节、X3 无 Heading 允许入库走兜底切章、X4 模板不计阻断），已写入规范 v2 §11。CSV 明细同目录 |
| `plans/资料上传_管理员端全员可见_方案_v2.md` | v2 | 📋 **待确认后开工**（取代 v1） | 按你「先做管理员上传→所有人可见，教师端与班级/个人下发推迟」重写：**不建 `material_target` 表、不加可见性服务、不做教师页**，路由 104→**105**，权限沿用 `_require_admin`，学生端**零改动**（上传即 `status=1`，与现有 107 行同语义）。**第二问的审计结论**：统一格式「有规划待落地」（规范 v2 + 预检 T0）；**传输流畅性 3 个缺口**——nginx `client_max_body_size 200m` < 业务 250MB、单请求 250MB 无进度回调/无断点续传、单队列被大文件堵塞；**存储 4 个缺口**——tmp 无 TTL 清理、无磁盘水位、写盘非原子、批量入库可能长事务锁库。全部补法已排入 **T7 传输与存储治理（1 天）**：300m、XHR 进度+整文件重试、fast/slow 双队列、24h TTL、5GB 水位、`fsync+os.replace`+sha256、每 100 条提交。总估时 **8 天**（T0 1 + 实现 6 + 验收 1）。教师/下发留档于 §7，D11/D13/D15/D16 推迟 |
| `plans/资料内容格式与分类规范_v2.md` | v2 | 📋 **草案，待批准**（P0 前置 T0） | 回答「方案里是否有健全严格的文档格式与分类机制」：**只有卡片这一类健全**（表头 5 列 + E001–E010 + 110 条规则 + 两轮自动分类 + 30 样本回归 考点 100%/子类 93%），**讲义与试卷是空白**。本规范补齐三类：卡片（别名表、多 sheet、>500 行自动分批、2000 行硬上限）、讲义（Heading 1/2/3 必用、段落≤500 字、表格≤8 列、图片≤20 张、法条引用格式、章节切分规则、PDF ≥300dpi）、试卷（7 项元数据必填、命名规范、题本/答案成对校验、不参与卡片分类只建索引）；附机检错误码表（E 阻断 / W 提示）、3 个模板、预检接口与脚本（上传前就能看到问题）、分类机制总览与「未分类队列」；验收用现有 25 xlsx / 26 pdf / 1 docx 实跑。待拍板 D18–D20 |
| `plans/资料上传与下发_管理员教师端_方案_v1.md` | v1 | 📋 **待你审核批准**（未写业务代码） | 你要求「管理员/教师上传三科目四类资源，并按下发对象（班级/学生）下发；学生端不加功能」。实测结论：**骨架在、数据空、权限窄**——①`services/class_scope.py` 已有 `teacher_class_names()`/`is_my_student()` 可复用；②论坛 `visibility=ALL/CLASSES + visible_classes` 是现成的按班可见范式（含中文班级名 JSON 转义坑）；③但 **`banji` 表 0 行、`sys_user.class_name` 30/30 为 NULL**，今天点开班级选择器会是空的；④上传只有 `_require_admin`（教师完全不能用）、前端只有学生 Excel 页。方案：新表 `material_target`（all/class/student + 唯一索引，**无记录=全员可见**，存量零回填）＋ `services/material_scope.py`（唯一判据，列表/详情/进度三处复用）＋3 个 targets 端点（classes/students/preview）＋ `confirm` 扩展 targets ＋ 前端 `MaterialTargetPicker`（三 Tab，教师受 `class_scope` 限制、越权后端 403、学生未命中 404、游客不可见）；**分支结构：P0 导入分支合完再从 main 切 `feat/material-distribution`**；P1 新增 T9–T14 共 4.5 天；附 3 张效果图（管理员确认入库下发 / 教师仅我的班级 / 学生端可见性矩阵）；待拍板 D10–D16 |
| `plans/资料导入_按科目分类清单_v1.md` | v1 | ✅ 实测盘点（2026-11-05） | 按你「三科目 × 卡片/讲义/试卷」的划分重排待导入资料：**行测** 卡片 14 文件/196 行、讲义 12 PDF/191 页、试卷 170（85 题本 + 85 答案）、视频 8 集；**申论** 卡片 5 文件/611 行、讲义 6 PDF/898 页、试卷 254（120 题本 + 134 答案）、视频 0；**公专** 卡片 6 文件/351 行、讲义 8 PDF/530 页 + 1 Word/297 段、试卷 93（47 题目 + 46 答案）、视频 68 集。合计 **卡片 25 文件/1158 行｜讲义 26 PDF/1619 页 + 1 Word｜试卷 517 文件｜视频 76 集**。含「通道映射」（卡片与文字型讲义 → 资料导入 P0；扫描件 → MinerU P1；试卷 → 题目导入 P2；视频 → 台账）与 5 批导入建议；**§8 关键发现：`_待录入` 与 `_待录入_v2` 是同一批内容的两版——抽查 4 个文件，v2 全部为 v1 子集、0 条独有 → 两版都导必然重复，需你确认 v2 用途（D10）** |
| `plans/资料导入_待导入清单_v1.md` | v1 | ✅ 实测盘点（2026-11-05） | 你要的「现在有哪些资料需要导入」：**Excel 25 个文件 / 1158 行卡**（`_待录入` 13 个 951 行 + `_待录入_v2` 12 个 207 行，表头统一 正面/背面/分类/考点/封面）＋**PDF 26 个 / 1619 页**（公专 8 个 530 页、申论 6 个 898 页、行测 12 个 191 页；**24 文本型可直导，2 扫描型需 MinerU**：`三色笔记-申论.pdf` 204MB/90 页、`言语理解与表达（总图）.pdf` 1 页）＋**Word 1 个 / 297 段**（`公安基础知识.docx`）；**不导入**：`_模板` 3 个 110 行、`_测试文件` 2 个 9 行。库内现状 `study_material` 107 行（102 上架 + 5 下架 = 3 篇科目说明 + 104 张卡）→ **距 1158 张还差 ≈1054 张**。另列：仓库 `题库/` 480 个 PDF（473 文本/7 扫描）是**题目来源**、`名师讲解视频` 76 集是**媒体**，均不属"资料导入" |
| `plans/资料多格式导入_实施计划_P0_v1.md` | v1 | 📋 **待你最后确认后开工**（分支 `feat/material-multi-format-import`，代码未写） | 按你已拍板的 IMP-1~9（本地 MinerU / 250MB / 按类型+流式 / 学生端不开放 / **IMP-5 B：共享组件 + 两薄壳页** / 1s 轮询 / 扫描件必须 / parser sidecar / GPU 未知按 CPU）编制 P0 计划：**数据模型**（`material_import_record` +7 列 + 迁移 `20261105_006`，LF 写入防 DDL checksum）＋**状态机**（pending→queued→parsing/ocr→extracting→preview_ready→committing→done，失败可重试、重启超时重置）＋**进度口径**（10 / 10–70 / 70–90 / 90 / 100 分段）＋**后端 8 处改造**（`_require_staff`、流式落盘、分级上限、3 个新端点、队列服务、解析进度回调、OCR provider 抽象、白名单 +3）＋**接口契约**（batch / status / batch 汇总 / retry 完整 JSON）＋**前端 7 处**（共享 `MaterialImporter.vue` + `useImportJobs` + 管理员双列页 + 教师单列页 + 路由 104→106 + DOM 注入入口）＋**测试矩阵 8 条** + **写码前 11 问** + **T1–T8 共 5.5 天** + 风险 6 条 + DoD 7 条；附 3 张真实渲染效果图（管理员双列 / 教师单列 / 手机端） |
| `plans/待决策清单_v1.md` | v1 | ⏳ 待你逐条拍板（2026-11-05） | 集中列出 **27 条待决策**，避免散落在 8 份文档里：**A 本轮资料导入 9 条（IMP-1~9）**——MinerU 形态（建议本地）、单文件上限（建议 250MB，实测最大件 204MB）、上限分级、学生端是否开放 PDF、教师端同页、进度协议（轮询 vs SSE）、扫描件是否必须、远端 sidecar、服务器有无 GPU；**B 数据运维 7 条（OPS-1~7）**——生产题库如何弄进来、删除 14.8GB zip+3 个 `.part`（需签字，铁律第 7 条）、合并 BN2027-p01、大纲 4 条疑似笔误改名、87 知识点入图谱、Dataview 静态化、2 个 docs 提交先合 main；**C AI 讲师 11 条（AI-1~11，暂停中）**——交付口径/3 个试点/金币计入/形象/专利交底书范围/单元粒度/8 个细目归属/别名表/产物落位/无题能否上线/转写范围。每条给「选项 / 影响 / 我的建议 / 何时必须答」，末尾附**决策→任务映射**（谁卡谁）。
| `plans/AI讲师_阶段性成果与暂停记录_v1.md` | v1 | ⏸ 暂停归档（2026-11-05） | 按你指令暂停 AI 讲师，把成果写进记录：**9 份文档 + 5 张图**（需求基准 v3 / 总体设计 / 供给适配器方案 / 限制与缺口 v2 / 视频学习能力 / 迁入 Obsidian 报告 / 可行性评估 / 初步设计 / 本文）；**代码 0 行**；已落地事实（87 知识点 403 考点、14 零考点、8/12 试点无节点、题库仅 200 题、媒体 75/76 命中、ffmpeg 9.0.2 + faster-whisper 1.2.1 + rapidocr 1.4.4 已装、桐哥 p06 风格 6 条观察）；**未完成 T0–T10 / 专利交底书 B / 考点卡 10 / 法条卡 5**；恢复清单 6 步 + D1–D8 决策状态；并提示「播放器会改路由计数 104→105，与资料导入分支不要并行改同一处」 |
| `plans/AI讲师_视频学习能力方案_v1.md` | v1 | ✅ 路线已实测（待批准装 ffmpeg/ASR） | 回答「哪个插件能让你获得视觉能力、能看视频学讲解风格」。结论：**不需要视觉插件**（`read_image` 已通），缺的是**视频解码器**；DSH 已装的 4 个插件（dshmarket/dsh-context/dsh-obsidian/superpowers）**都不提供视频能力**。**已跑通证据**：`pip install --target %TEMP%` 装 `imageio-ffmpeg` 得 ffmpeg 9.0.2（隔离安装、未改系统），从 `桐哥 p06 传唤`（358 MB / 90 min）抽出 3 帧，我**读出**标题「调查取证——传唤」、三行表格、老师红笔圈注与下划线、底部随讲稿变的字幕；同一集 00:02:00 与 00:12:00 对比可见"逐条加红笔"的讲解过程。路线对比：**A 本机 ffmpeg + 我读图（推荐，0 成本，抽帧 1–2 秒/张；contact sheet 24 帧/张；ASR faster-whisper 1.2.1 + uv Python 3.11 + hf-mirror，90 min 音频 GPU 约 8–15 分钟）**；B 云 VLM（智谱 200/火山 401/通义 404/硅基 404 可达，但需 key、花钱、粗描述、上传付费课程有版权风险）；C 本地 VLM（Qwen2.5-VL 5–15 GB、6 GB 显存需 int4，性价比低）。含四层提取法（画面/语言/动作/结构）+ 3 集样本策略 + E1–E3 待批 + 风险边界 |
| `plans/AI讲师_限制与缺口清单_v2.md` | v2 | 📋 清单（2026-11-05，供审批） | 按你「不要因为没视频就判无解」重查：**v1 里 3 条判定错、2 条事实错**。纠错：①媒体不在 E 盘（本机无 E 盘），实际 `C:\Users\35709\OneDrive\Desktop\题库\名师讲解视频` **80 文件/37.97 GB**；②台账 `file_path` 是**相对路径**，按新根 **75/76 命中**，仅 `BN2027-p01` 缺成片（两个分片均在，ffmpeg 无损合并即可）；③ffmpeg 虽未装但 pypi/清华/aliyun **全 200**、`winget`/`choco` 在位、`pip install imageio-ffmpeg` 免管理员；④无转写但本机 **RTX 4050 6GB + i7-14650HX 16C**、uv 自带 **Python 3.11**、hf-mirror **200** → faster-whisper 可跑（112.6h 音频 GPU 约 6–12 小时）；⑤法条可从 `flk.npc.gov.cn`（200）取。清单含 **8 条环境限制（全部可解）+ 20 条资产缺口（每条给解法/产出/优先级）+ 4 条翻案 + 2 条真不可逆（生产题库不在本机、视频版权）**；并新增 T9（媒体体检与修复）/T10（转写试点）与 D7（媒体根更正，已执行）/D8（是否现在装 ffmpeg+ASR） |
| `superpowers/specs/AI讲师知识库_迁入Obsidian与知识供给_报告_v1.md` | v1 | ✅ 已执行（2026-11-05） | 把「AI讲师知识库」迁入现有 Obsidian vault（`…\OneDrive\文档\Obsidian Vault\AI讲师知识库`，127 文件/240,694 字节 0 丢失、Canvas 73 节点 0 断链、`dsh-obsidian` 直接可读写）；说明其真实价值 = **已备好 AI 讲师 P1 缺的三样输入**（87 知识点+403 考点清单 / 3 篇讲师范式含桐哥四步讲法 / 教学画面渲染规范）；实测抓出 3 处缺陷：首页分科目知识点数错（29/28/30 → 27/25/35，已修并记变更日志）、创新设计声称「已写入大纲 §3」的知识点 ID 表**实际不存在**（DSL `point_id` 无值可填，待批补生成）、403 考点中 86 个叫「其他」+ 14 个零考点知识点（需筛选规则）；并给出对总体方案 v1 的 5 处修订建议（1080p+96px 安全边距、segment 增考点归属字段、7 段式↔桐哥四步对照、scene.kind 增 flow/compare、法条原文禁由 LLM 生成） |
| `superpowers/specs/学生端练习记录可视化与未完成答题卡续答_v1.md` | v1 | ✅ 已落地并验收（2026-11-01）；P1 导航高亮已修 | 练习记录可视化（7 日柱状题量+折线正确率、知识点进度改柱/折线、类型点击跳答题卡）、「我的」页新增两卡片（科目比例饼+对错环形、错题知识点 TOP N）、未完成答题卡按 `record_id` 续答；新增 3 个只读端点（`/api/exams/records/{id}/resume`、`/api/stats/subject-distribution`、`/api/wrong-questions/point-stats`）；零 DDL、零新表；记录写入链路与重复计数/静默空白/草稿丢失 3 项风险对策 |
| `ops/变更清单_学生端练习记录可视化_v1.md` | v1 | ✅ 已归档（2026-11-01） | 按功能主题拆分的改动清单（env / db 迁移 / 草稿与 type-summary / 续答端点 / 统计端点 / 前端图表与卡片 / 导航高亮 / 文档 / 启动脚本）+ 第 10 节按主题回滚指引；仓库新建后首提交为整仓基线，此清单保留原「按功能拆分」意图 |
| `superpowers/specs/联考小智功能开发中与前后端版本一致性_报告_20261102.md` | v1 | ✅ 已落地（2026-11-02） | 「功能开发中/请求参数验证失败」根因是旧 bundle 与旧后端进程，非代码缺失；新增前后端版本自检（`buildStamp` 注入 SHA、`/health.revision`、前端不一致弹窗）+ 排障规约（父子进程、端口残留、硬刷新）；改用 SSH deploy key 推送，合并远端 27+ 提交后 main 同步 |
| `superpowers/specs/论坛图片上传接口405排查_报告_20261102.md` | v1 | ✅ 已修复（2026-11-02） | `POST /api/media/image` 405 根因：`60ca515` 合并时丢掉了 `app.include_router(image_media.router)`，请求落到 `GET /api/media/{asset_id}` 兜底路由；修复后 openapi 恢复该路由、无 token 401、教师实传 200；新增 `tests/test_router_registration.py` 关键路由清单守卫（媒体/论坛/小智/计划/考试/登录/健康），防止同类「合并丢注册」静默复发 |
| `superpowers/specs/向量投影Embedding服务配置与故障治理_v1.md` | v1 | 📋 方案（待批准实施） | `embedding_error … HTTP 404` 根因：DeepSeek 官方无 `/embeddings`（模型清单仅 deepseek-flash / deepseek-v4-pro），被误当向量服务。含 A/B/C/D/E 五套方案（SiliconFlow bge-m3 / DashScope text-embedding-v3 / 智谱 embedding-3 / 本地 Ollama / 关闭降级）、维度一致性规则、三步自检、索引重建与 4 项代码加固计划 |
| `superpowers/specs/学习计划大模型401与503修复_报告_20261031.md` | v1 | ✅ 已修复（2026-10-31） | 学习计划 `POST /api/plan/generate` 503、前端「大模型返回错误（401）」：根 .env 用 `DEEPSEEK_API_KEY`、后端只认 `LLM_API_KEY` 且只读 `backend/.env`（该文件缺失），叠加 config.py 中重复的大模型配置块互相覆盖；改为 `AliasChoices` 双名兼容 + `env_file=(".env","../.env")` + 去重 + 缺密钥/401 分别报 `llm_no_key`/`llm_unauthorized`；实测 generate 200（49 天 4 任务），新增 4 条回归测试 |
| `superpowers/specs/教师账号无法登录排查_报告_20261101.md` | v1 | ✅ 已修复（2026-11-01） | 教师账号 `ycc5678` 登录报「用户名不存在」：备份对照证明 `sys_user.user_id=3` 的 `username` 在 10-26 之后被从 `ycc5678` 改成中文姓名（密码哈希、注册时间未变），而登录只匹配 username/phone；登录代码自创建起即如此、应用内无任何写 username 的代码 → 属数据层改动而非代码回归。修复：按 R10 用 `sqlite3.backup()` 快照后把 username 复原，并把 `user_no` 纳入登录标识；新增 5 条回归测试 |
| `superpowers/specs/试卷管理交互缺陷修复与拖拽设计_v1.md` | v1 | ✅ 已实施 / 已验收（2026-11-01） | 教师端试卷管理 5 项缺陷：删除闭环/空白按钮/拖拽排序/左栏预览/状态科目徽章；实测根因、D1–D6、I1–I4 微创新、DoD 与待拍板 4 项；不改后端 API/DB 与 .vtj raw 模板 |
| `superpowers/plans/试卷管理交互缺陷修复与拖拽实施计划_v1.md` | v1 | ✅ P0–P7 已完成（2026-11-01） | 与设计配套的 P0–P7：纯函数+vitest→按钮/徽章→删除回收站→右栏拖拽→左栏拖入→预览→验证→归档；含依赖顺序、风险检查点与只提交本任务文件的约束 |
| `superpowers/specs/管理员端用户与权限合并设计_v1.md` | v1 | ✅ 已实施（2026-11-02） | 管理员端「用户管理」+「权限管理」合并：用户列表/权限模板/授权审计/权限健康四 Tab；批量增删改查 + 单/多用户 Tri-state 权限；角色基线+能力包+个人加授−拒绝；软删除+回收站+匿名化 purge；500 人批量上限、差异预览、10 分钟批次撤销；含实测根因、数据模型、API 契约、A1–A16 验收与 D1–D7 待拍板 |
| `superpowers/plans/管理员端用户与权限合并实施计划_v1.md` | v1 | ✅ 已实施（2026-11-02） | 与设计配套的 P0–P5：备份/修编辑坏点/权限元数据→模型迁移/权限引擎/详情 API→工作台/抽屉/模板→批量/审计/回收站→健康扫描/解释器/套餐→验收归档；含任务依赖、风险检查点与 raw 页约束 |
| `superpowers/specs/管理员端头像与回收站批量注销体验_v1.md` | v1 | ✅ 已实施并验收（2026-11-03） | 管理员端用户列表真实头像（`sys_user.avatar` + `@error` 首字母回退）、头像资料卡、回收站批量彻底注销（仅超管/仅回收站/原因+固定词确认/影响面预览）、暂存图清理 DB 引用保护；含根因表、D1–D5、DoD、风险与关键文件 |
| `superpowers/plans/管理员端头像与回收站批量注销实施计划_v1.md` | v1 | ✅ P0–P3 已完成并验收（2026-11-03） | 恢复 469 张误删题图→图片清理引用保护→后端批量 purge/匿名化→前端头像与确认交互→定向测试/typecheck/build/gate/浏览器验收→归档提交合并 |
| `superpowers/specs/题目展示与导入完整性整改方案_v1.md` | v1 | ✅ 已实施并验收（2026-11-03） | 五项整改根因树：管理员列表 ID 改展示序号、来源以导入文档标题为单一真源、题组选项对象契约、统一阅读态富文本排版、申论要求/图片选项解析与编辑不清空；D1–D12、P0–P6、DoD、风险与 I1–I4 创新点；raw 页零模板改动 |
| `superpowers/plans/题目展示与导入完整性整改实施计划_v1.md` | v1 | ✅ P0–P6 已完成并验收（2026-11-03） | 与方案配套的 P0–P6：备份/清单→统一渲染层→选项契约与解析器→来源真源→管理端 ID/编辑→历史数据修复（dry-run）→定向测试/typecheck/build/gate/三端验收/归档；含任务文件、测试矩阵与回滚 |
- 2026-11-04：把 feat/teacher-administrator 的管理员端用户与权限、管理员头像/回收站批量注销、题目展示与导入完整性三组整改合并入主线；索引保留 6 份对应设计/计划与 9 份本分支历史文档。
