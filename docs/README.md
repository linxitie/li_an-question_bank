# docs/ 文档索引

> 本索引由 `solve_problems_files/README.md` 迁移而来（目录分层重构）。
> 归档规则：展示方案的同时落盘；定稿当场归档；归档即更新本索引。

## 目录说明

| 目录 | 用途 |
|---|---|
| `design/` | 历史设计方案（95 份，含 v1 旧版容器化方案等） |
| `plans/` | 实施计划与当前活跃设计（119 份） |
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
| `superpowers/specs/模块4与7炫技功能方案_v1.md` | v1 | 📋 待挑选（2026-11-15） | 12 个炫技功能（模块4：热力图/记忆曲线/签到星图/沉浸专注/反馈音效/周报卡；模块7：3D力导向图谱/画像雷达/溯源气泡/方案diff/多角色互评/知识定位）+ S/A/B/C/D 性价比排序 + 零新依赖技术底线 |
| `superpowers/specs/模块4与7全面升级方案_v1.md` | v1 | 📋 待审批（2026-11-14） | 注册画像询问（动画/动态问题/自述）+ 备考方案回流 + 3D签到日历 + 番茄钟 + 遗忘曲线复习 + 三端补齐；联考小智 Obsidian 知识库与知识图谱框架；P0–P6 分阶段、20 工作日、6 项未决需拍板 |
| `superpowers/specs/AI讲师知识库_搭建说明_v2.md` | v2 | 🗄️ 历史版本（被 v3 取代） | 资源清理与实测总量（76 文件/22.3 GB/112.6 小时）、177 双链 0 断链 |
| `superpowers/specs/AI讲师知识库_搭建说明_v3.md` | v3 | 🟡 已搭建待评审（2026-11-04） | 3 科目/15 模块/87 知识点/403 考点分类导入、5 张 Canvas 路径修复、73 文件节点 0 缺失 |
| `superpowers/specs/评论区舆情监控与内容安全智能体_M1-0能力对齐_v1.md` | v1 | 📋 待批准（2026-11-05） | 一页纸：content_guard（已上线闸门/判定/任务/审计/红队/对账/投影/31 端点）与 M0 `policy_compiler` 的 16 段能力矩阵 + 3 处冲突裁定（政策源 / Obsidian 双库 / 台账）+ A0–A5↔四档映射 + M1 五步与 3 项待拍板（D1–D3） |
| `superpowers/specs/评论区舆情监控与内容安全智能体_v2.0.md` | v2.0 | 📋 方案（待审批，未实施） | 论坛评论区实时舆情监控与内容安全智能体：5 条硬判断（J1–J5）、9 处对第一版修正（C1–C9）、动作梯度 A0–A5、四库=1 SoT+4 可重建投影、三层知识图谱本体、Obsidian 子库「AI舆情审核知识库」+ Policy-as-Markdown 编译闭环、创新 I1–I8、路线 M0–M5；17 章 |
| `superpowers/specs/AI舆情审核知识库_搭建说明_v1.md` | v1 | ✅ 已搭建并接入（2026-11-05，69 文件/65 md + 4 canvas，断链 0） | Obsidian 子库 `D:\Obsidian仓库\AI舆情审核知识库`：14 个一级区、政策库扩至 10 域 29 条款（critical 4 / high 16 / medium 8 / low 1）、三色状态灯、政策护照卡、三段式收件箱、双轨日志、A0–A5 动作梯度卡、知识健康度 H1–H5；已由 `policy_compiler.py` 编译为运行期规则 |
| `superpowers/specs/评论区舆情监控与内容安全智能体_M0实施记录_v1.md` | v1 | ✅ M0 已完成（2026-11-05，分支 `feat/teacher-administrator`） | M0 系统侧接入：`policy_compiler.py`（540 行）、`knowledge_ops.py`（210 行）、12 项定向测试通过；4 个开关全默认 off；已知问题与 M1 五步清单 |
| `plans/AI真功能_实施与验收_v1.md` | v1 | ✅ 已实施并静态验收（2026-11-04，分支 feature/ai-assistant-ai-real） | 模块4/7 AI 演示态转真功能：作文批改/模拟面试/学习教练走 /api/llm/chat 一次性任务（persist=false + essay/interview/coach 三场景，零新增端点，R11 不变）；前端只改 script（R3）；pytest 5 passed、L0 7/7、L5 PASS、VTJ 版本一致；真实 LLM 与前端运行时未验证 |
| `superpowers/specs/资料模块500与Schema漂移修复_报告_20261105.md` | v1 | ✅ 已修复并浏览器验收（2026-11-05，`main`） | 管理员资料/成就 500 根因是模型新增 5 列未迁移到存量 SQLite（`study_material.point_id` 等）；新增启动列自愈 `schema_heal.py`、成就成色回填、32 张资料卡种子数据；四个 500 接口均 200，资料页 32 行、编辑弹窗可用 |
| `superpowers/specs/快速练习知识分层知识图谱与Obsidian自生长知识库_v1.md` | v1 | 📜 历史版本（分类层与 Obsidian 结构均被 v2 取代，仅存档） | 快速练习四层知识图谱 + Obsidian 自生长知识库：6 处第一版硬校正、8 条关系、14 区目录、qp_kg_* 覆盖层 + 编译器、H1–H13 健康度、P0–P4 路线；Obsidian 骨架已搭建 |
| `superpowers/specs/快速练习知识分层Obsidian知识库_搭建报告_v1.md` | v1 | 📜 历史版本（v2 已重建，v1 仅存档） | 交付位置 `D:/Obsidian仓库/快速练习知识分层`：14 区 + 首页、1049 知识节点、13 张 Dataview 看板、5 张 Canvas、6 个图谱颜色组；只写设计态，不改 DB/API/代码。**v2 建库后由新报告取代** |
| `superpowers/specs/快速练习知识分类体系_v2.md` | v2 | ✅ P1 已按默认 D1–D10 实施（2026-11-06，main） | 全中文、科学严谨的知识分类层重构：446 张规范卡（3 科目 + 16 域 + 42 分组 + 220 知识点 + 165 考点）、甲乙两族、8 关系、10 区 Obsidian、P0–P5 迁移；不写 DB/代码。归档副本 `design/快速练习知识分类体系_v2.md` |
| `superpowers/plans/快速练习知识分类体系_v2_实施计划.md` | v2 | ✅ P1 已实施，P2–P5 待批（2026-11-06，main） | P0–P5 实施计划：P1 只读建 446 卡、P2 乙类 771 回链、P3 甲类 1208 题簇、P4 1285 残差定性、P5 写库单独审批；含 V1–V21 校验、回滚、RACI、D1–D10。归档副本 `plans/快速练习知识分类体系_v2_实施计划.md` |
| `superpowers/specs/快速练习知识分类体系_v2_搭建报告.md` | v2 | ✅ P1 已实施并验收（2026-11-06，547 文件 / 446 卡 / 828 边 / 断链 0） | Obsidian 库 `D:/Obsidian仓库/快速练习知识分层`：10 区 + 首页、446 张规范卡、828 条基础边、5 Canvas、8 看板、10 模板、9 治理、9 归档；V1–V21 全过，数据库哈希前后一致。**165 考点 0 题、171 甲类无考点、4 张 Canvas 待逐张视觉验收** |
| `superpowers/specs/快速练习周任务设计分配Obsidian知识库_搭建报告_v1.md` | v1 | ✅ 设计已批准（2026-11-06）；P1 已验收，P2–P3 待启动 | Obsidian 子库 `D:/Obsidian仓库/周任务设计分配`：10 区 + 首页、55 主题、165 模板、12 周、84 日批、216 实例、5 Canvas、8 看板、10 模板、9 治理、15 接口契约；每日审批铃 + 今日任务栏 + Windows 通知脚本；**6 个模板可试点、159 待补题、42 主题无考点**。归档副本 `design/快速练习周任务设计分配Obsidian知识库_搭建报告_v1.md` |
| `superpowers/specs/快速练习周任务设计分配_设计批准记录_v1.md` | v1 | ✅ 设计要求已批准（2026-11-06，main） | 记录批准范围：三科大纲框架、12 周 × 18 任务、周批 + 日批 + 状态机、Obsidian 设计态/审批态、15 篇接口契约；明确不含写 DB、改后端/前端、P3 API 实现与 P5 写库。归档副本 `design/快速练习周任务设计分配_设计批准记录_v1.md` |
| `superpowers/plans/2026-11-06-未分类题目可答题与分类回填.md` | v1 | ✅ 已批准并实施（可答题链路 + 160 回填，2026-11-06，main） | 未分类题实测 668（行测 341 / 申论 11 / 公专 316）；160 题高置信回填已 apply，未分类降至 508（行测 192 / 申论 0 / 公专 316）；508 题保留「未分类」可答题通道；0 号范围、PC/手机入口、sqlite3.backup()、dry-run、逐行复核已完成。归档副本 `plans/2026-11-06-未分类题目可答题与分类回填.md` |
| `superpowers/specs/快速练习未分类题目可答题与分类回填_实施报告_v1.md` | v1 | ✅ 已实施并验收（2026-11-06，main；未分类 668→508） | 668 未分类拆为 160 可回填 + 508 保留；160 已 apply，未分类降至 508；后端 subjectId + 0 号 sub_category_id IS NULL、PC/手机入口、3 条接口测试；Obsidian 429 文件/断链 0；typecheck 0、生产构建通过、quick gate 4/4；pytest 22/23（1 条既有跳转断言失败）；**PC 真机 20 题交卷 + 20 条记录落库后清理**；**160 行仅改 sub_category_id，核心字段指纹不变**。归档副本 `design/快速练习未分类题目可答题与分类回填_实施报告_v1.md` |
| `superpowers/specs/仓库文件全面扫描_报告_20261113.md` | v1 | 📋 只读盘点（2026-11-13，未跑测试/门禁） | 全仓库目录/文件类型/体积/Git 工作区状态实测；§5 列 11 项与 AGENTS.md 基线的偏差对照（分支、库体积、static/uploads/题库、modules 目录、VTJ 页数、技能目录、pre-wipe 备份待复核）；标注未实测项（343 端点/72 模型/图片完整性）；未触碰任何红线目录 |
| `superpowers/specs/dsh项目记忆提取_报告_20261113.md` | v1 | 📋 只读提取（2026-11-13，未回写 dsh） | dsh 三层记忆（neuron/switchman 交接/.memory 长期档案）中的砺安题库事实：远端与代理、9527/8001 端口真相、三套账号、12 红线与门禁口径、模块4/7 十条改造的已完成/待办/代码定位/遗留杂物；§6 列 6 项 dsh 记忆与当前实测的漂移口径；dsh 人格层未纳入 |
| `superpowers/specs/模块4-7全面升级方案_v1.md` | v1 | 🟡 待批准（2026-11-13，未进入实施） | 注册画像 7 条 + 联考小智 3 条 + 三端补齐的升级方案：实测盘点（画像/计划/小智/签到/错题/图谱/Obsidian 现状与 file:line）、逐条方案与归属、最小后端变更、P0–P5 分期路线、红线约束与 6 项待拍板问题；跨域（签到/错题/图谱）只列接入建议不改他模块代码 |

## 变更记录



---

- 2026-10-18：⑱⑲⑳ 三未开发模块补目录定位：`src/modules/{ai-assistant,mock-exam,mini-exam}` 占位外壳落地（四件套×3、零事件、不认领），生成器 17→20 域，shells.spec 161 全绿；规格 5.1 目录树与《分支使用说明书》⑱⑲⑳ 三行同步更新。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1.md`（学生端功能模块化设计终稿，用户已批准）。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1_实施计划.md`（123 个原子任务；P1 33 任务、P2 82 任务已全部完成并逐任务双提交；P3 真机手工验收待执行）。
- 2026-10-18：新增 `plans/分支使用说明书_v1.md` 与 `plans/学生端模块化基线快照_v1.md`。
- 2026-10-19：新增 `plans/三端数据流一致性修复方案_v1.md`（三端数据流一致性 6 问题修复方案；数据库实测 + 代码逐行核对；待用户审批后实施）。
- 2026-10-19：三端修复方案获批；P0-1 备份完成、P0-2 基线脚本完成（commit `db4a5c2`）；基线修正：2 组无可见成员、组 24 仅 1 个 source。
- 2026-10-20：三端修复 P0 全部完成：P0-3 解析门禁基线（公专 L1 PASS；行测 L1 既有 FAIL，材料指纹 364/1.0 与基线一致）；5 个真实案例入库（commit `a634820`），第 3 类“材料在答案解析之后”标 `not_found`，未使用合成案例；P0-4 golden corpus（commit `4f291ed`）；P0-5 `MATERIAL_OWNERSHIP_V2=False` 灰度开关（commit `54de949`）。
- 2026-10-20：三端修复 P1-1 完成：`QuestionStatsService.visible_query` 统一三端默认可见性为 `status=1 AND audit_status=1`，新增 `visible_total`、教师 `my_total`、管理端 `include_offline/include_pending`；`backend/tests/test_question_stats_service.py` 4 passed（commit `fa3683a`）。
- 2026-10-22：合并远端“题库设计前必看”内容，保留文档索引。
- 2026-10-22：恢复《整体系统使用和结构说明》10.4、11–15 节，同步根目录、`docs/ops`、归档三份副本（818 行）；补充数据流一致性报告图片附件。
- 2026-10-22：新增 `ops/整体系统使用和结构说明_v1.md`（系统目录结构、克隆与启动、拉取更新、设计收尾、SQLite 存储/备份/恢复、多人共享、验收与排错）；同步根目录 `整体系统使用和结构说明.md`。
- 2026-10-23：新增 `plans/三端数据流一致性修复方案_v2.md` 并追加 §14 RT 富文本（答题卡/教师端/导入/管理员端）。
- 2026-10-24：T-12 完成：新增 `docs/superpowers/specs/三端数据流一致性修复方案_v2_验收报告_20261024.md`；生产迁移 KP 1049 / 题 3357 / 关系 2775，51 项验收全绿。
- 2026-10-25：**OCR 链路恢复**：MinerU 超时改按页放大（75s/页、封顶 3600s），Paddle 页数上限 8→30、超时 240→600s，Paddle 按核数开线程并关方向分类；文本缓存键加引擎作用域（MinerU/Paddle 互不污染，2 个长期失败用例清零）。26 passed。
- 2026-10-25：**行测资料分析材料绑定**：按 `（一）（二）` 材料段把 material_text 回填给段内 4~5 道小题（22 套 blocks 2603 零漂移，76 组/272 题绑定，原仅 64 题）；限「资料分析」分段 + 题数 [2,6] 安全阈值，漏检边界宁可不挂。**前向生效**，存量 235 题仍需重导或回填。
- 2026-10-25：**导入配对修复**：答案 PDF 不再按题干切块，改为题号锚点解析（安徽 2025 实测 125→125 对齐）；预览新增 `file_role=answer` 与 `ANSWER_ONLY`，`/confirm` 禁止答案卷入库；新增探针 `scripts/probe/probe_import_match_quality.py`（行测 10 套匹配率 100%）。
- 2026-10-25：**数据库静默回落修复**：`backend/.env` 缺失使 `SQLITE_PATH` 回落 `example_db.sqlite`（旧 schema、0 题），全站 500/登录失败；合入 main 的默认库修复 + 新增 `app/core/db_guard.py` 启动校验（路径/关键列/行数），重启后 `/api/questions/` 200（total=3122）。事故报告已归档。
- 2026-10-25：`build:prod` 恢复：58 条 typecheck 错误清零，`.vtj` 页仅动 `<script>`；`verify:health` 阻断 0、`test:unit` 331 passed、构建 25.75s。
- 2026-10-25：dsh 侧能力就绪：`.dsh/skills` 联接 20 个项目技能（33→53 条）；`mcp-vtj` 19 工具免重启可用；`gate_all.py` 修复 GBK 假 FAIL 与落盘路径。
- 2026-10-26：**F2 通信统一与写入守卫交付完成**：WS 协议 v2（seq/scope）、Redis 中继与多 worker fail-fast、统一 `ws_relay.emit` 出口、前端 `data-changed` 消费/seq 去重/重连重同步、92 条路由 roles 补全、写入守卫 6 类；L7 PASS=15/WARN=0/FAIL=0，全量门禁 9/10（L2 既有基线），62 后端 + 342 前端测试通过，tag `foundation-v1-f2`；新增交付报告并明确 **F2b（13 个写调用点迁 Outbox / Redis Stream / 定向派生）未做**。
- 2026-10-26：**F2 实施计划落盘（待批准）**：WS 协议 v2（seq/scope）、Redis 中继与多 worker fail-fast、前端 `data-changed` 消费与重连重同步、57 条路由 roles 补全、写入守卫 6 类；21 个文件 + 7 步 + 13 条验收；无新表、无迁移。
- 2026-10-26：**F1 一致性内核交付完成**：7 表 + 事务 Outbox + 投递/投影 + 对账 + `/health/foundation` + L7 门禁 15 项；26 个测试通过，L7 PASS=13/WARN=2/FAIL=0，tag `foundation-v1-f1`；新增交付报告（含 F0 指纹口径修正：以受 R8 保护的备份库重算，四表与主库 MATCH）。
- 2026-10-26：**F1 实施计划落盘（待批准）**：21 文件 / 7 步 / CTC 十问 / §9.2.1 13 条验收映射；`gc_previews.py` 归档路径统一为 `scripts/audit/`。
- 2026-10-26：**预览数据治理完成**：571 行 / 257.76 MB 超期预览 gzip 外置（571 个文件 / 36.76 MB）并置摘要；主库 303.17 MB → 46.52 MB（−84.7%），`auto_vacuum=INCREMENTAL`、`freelist=0`、`integrity_check=ok`；四表指纹与 F0 基线一致。新脚本 `backend/scripts/audit/gc_previews.py`（默认 dry-run，`--baseline-db` 强制基线比对）。
- 2026-10-26：**F0 基线冻结完成**：tag `foundation-v1`@`2ec9cc7`；`sqlite3.backup()` 备份 303.17 MB（integrity/quick ok、73 表行数与四表指纹一致、SHA-256 已记）；`gate_all --quick` 4/4 PASS。内容完整性基线落盘（13 条悬空图片行、10 个未解析图令牌、1 个空组、24 题申论未挂组，全部只登记）；方案新增 D17 + §19.8 六条不变量 + L7-15。
- 2026-10-26：**终态架构升级 v2.1**（用户批准 D1–D16）：新增 §17 容量预算（实测 303.17 MB 中 262.99 MB 是 `question_import_record.preview_data`；537 条超期 PREVIEW = 257.07 MB）、§18 数据卫生与保留期、§19 写入准确性、§20 三端×角色通信 SLO（seq/scope/Redis 中继/轮询回退）、§21 可落地性自证；L7 扩到 14 项（容量/preview/多 worker/事件契约）；新增 `foundation_preview_ref` 第 7 表。
- 2026-10-26：新增《砺安题库终态总体架构 v2.0（实测适配版）》：把草案“五库并列+双写”修正为“1 事实源 + 4 可重建投影 + Outbox + 对账”，给出 F0–F6 主干路线、L7 门禁与 dsh Agent 规约；**待用户审批 D1–D7，未批准前不动代码**。
- 2026-10-27：新增 `plans/备考资料模块总体方案_v1.md`（待审批）。六项需求拆成 6 条交付线并给出依赖顺序（doc-content → card → multi-device → growth-link → upload-format → ai-lecturer），父分支 `feat/Study-Material-Management`、子分支 `feat/Study-Material-Management-<子任务>`（因 Git 分支名不能同时是目录）。关键取舍：科目说明复用 `study_material` 的 `type='GUIDE'`（零新表）；卡片分类由 `material_classification_rules` 驱动而非前端硬编码；三端差异在同页按 `meta.platform` 适配（R12 禁复制页）；3D 用 CSS 视差并强制降级；AI 讲评只落契约 + 501 占位（无可用服务前不写实现）；奖励复用 `achievement.condition_code` + 幂等 `coin_record` 防刷。
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
- 2026-11-02：**分支清理**（`chore/branch-cleanup`）。先存档再删：`plans/分支清理清单_v1.md` 记录 26 个待删分支的 commit sha / 末次提交 / 远端状态（全为本地标签）。判定口径 `main..<branch>` = 0；本地 34 个分支中 33 个已完全并入 main，删除其中 26 个（19 个模块子分支 + 7 个历史分支），保留父分支、r2/r3/r4、ai-lecturer、`backup/main-pre-r4`、端口与 VTJ 修复分支。恢复方式：`git branch <名字> <sha>`；删除命令用 `git branch -d`（未合并会被拒绝）。
- 2026-11-02：**VTJ 版本一致性修复**（`fix/vtj-version-consistency`）。原脚本把「非设计器页面」判成「版本漂移」：`.vtj/vue/` 里 69 个设计器页面（有 `useProvider({id,version})` + 同名 JSON 的 `__VERSION__`）版本一致，但 4 个手写 `teacher_*` 页（`useProvider` 命中 0）与 `TeacherNavHeader.vue`（无 JSON）、`smart_recommend.vue`（有 provider 无 JSON）永远「提取不到版本」→ 脚本 exit 1 → CI 每次 `.vtj/**` 变更必红。同时发现 **CI 跑的是同步模式**：即使有真漂移也会在 CI 的 checkout 里被自动改掉再判通过，等于没拦。修复：`scripts/vtj_version_sync.py` 加 `classify()` 三类判定（设计器页面/无 JSON/无 provider），默认只同步真漂移、`--check` 只读比对并 exit 1、`--strict` 保留旧语义；CI workflow 改跑 `--check`；ops 手册新增 §2.1。验收：默认与 `--check` 均 **69 一致/0 失败/跳过 6**；`--strict` exit 1；注入 `__VERSION__=1` → `--check` 报 `home_page（Vue=1785750000100 JSON=1）` exit 1、同步模式可修、`git checkout` 还原（`.vtj/vue` 零改动）。
- 2026-11-02：新增 `plans/先合并后AI讲师_影响评估_v1.md`（评估，未执行合并）。结论：**先合并对 AI 讲师无副作用**（`main` 是 r4 祖先、`--ff-only` 只移指针、AI 分支位已在 `r4@267da9f`，合后两者同一 commit）；**但远端有 4 个从未进 main 的分支**，其中 `origin/feature/ai-assistant` 已含 `backend/app/services/llm_client.py`(171 行)、`backend/app/api/v1/platform/llm.py`（`/api/llm/chat`、`/api/llm/sessions` GET/POST、`/sessions/{id}/messages`、`DELETE /sessions/{id}`）、`ChatSession`/`ChatMessage` 模型、`.vtj/vue/ai_chat.vue` 与 `src/modules/ai-assistant/*` 实现，`origin/feature/study-plan` 复用**同一 blob** 的 `llm_client.py`（两分支均落后 main 127 提交）——AI 讲师开工前不定处置，必然做出第三份 LLM 客户端。反向两支：`fix/D1-import-card-type` 的修复**已在 r4**（`materials.py:1955-1957`、`type="card"` @1974，测试文件同名不同 blob）应丢弃；`feat/teacher-optimization`(2026-09-01) 改的是已不存在的 `backend/app/api/v1/teacher.py`（现 `platform/teacher.py`），盲合必 modify/delete 冲突。另给 5 个必改协调点（路由计数双改点 98/98、R11 白名单 36 条 + 基线 343 不动、迁移 `YYYYMMDD_NNN` 序号连续、README 索引、`.vtj/**` 触发 VTJ 版本 CI）与 §7 执行顺序（待批）。
- 2026-11-02：**平板与电脑同版落地**（方案 v3 已实施，三条决定：允许收紧顶部 / 竖屏 S2 / 首页切电脑版并采纳 V3）。三条 `/tablet/*`（materials、材料详情、badges）改 **redirect** 到电脑端路径（页面路由 101→98，L6 同步）；`/tablet/home` 的 component 换成电脑首页（**不能 redirect**：device.ts 的 `/home→/tablet/home` 会死循环，R4 不许动）；`src/style/index.scss` 加横屏样式：≤1366 触控 44px、≤1200 资料页收紧顶部、首页 ≤1100 两栏（右栏下移）/1101–1280 收窄。**关键坑**：`.vtj` 页面是 scoped 样式（`.top-section[data-v-x]`，0,2,0），全局 `.home-page .top-section` 同权重且后注入 → 覆盖不生效（首页仍 280/482/320、右栏被裁 131px），必须用 `#app` 前缀（1,2,0）。验收 `tablet_unified_shots.mjs` **31/31**：1024 资料页 **5 列 179×170 / gridTop 421 / 首屏 2 行**、1366 七列、详情两栏(row)、上传 860、徽章 4 列、旧地址 302、首页入口 112×44 且 <44px 元素 3 种尺寸全为 0；`pc_desktop_regression` 7/7、手机 20/20、手势 9/9、vitest 479、vue-tsc 0、gate_all 10/10。同时删除 `mobile_materials.vue` 平板分支（1433→812 行），并把手机验收脚本加 `Page.bringToFront` + `setFocusEmulationEnabled` + 主动 lifecycle，修掉「窗口被遮挡时页面定时器被节流导致翻页断言假失败」。
- 2026-11-02：新增 `plans/备考资料_平板横屏与电脑同版_可行性与预期效果_v2.md`（待拍板，取代 v1 的竖屏口径）。横屏实测：1024×768 / 1180×820 / 1366×1024 打开电脑端资料页分别是 **6 / 7 / 7 列，溢出 0**；但顶部占 474px → **首屏仅 1 行**（1366 为 3 行）。触控 44px 补齐后小目标 5→**0**（顶栏抬高会让 1366 首屏 3→2 行）；再叠「横屏 ≤1200 收紧顶部」的紧凑版 → 1024 变 **5 列 179×170、网格距顶 407、首屏 2 行**。详情页横屏是**左右两栏**（row/侧栏 184，`≤900` 单栏规则不触发），上传 860 居中、徽章 4 列、首页入口 363×69，全部 0 溢出。竖屏无法用 Web 强制锁横屏，建议「请横屏使用」提示（可跳过）。10 张真实渲染图入 `assets/备考资料_平板横屏预览/`，脚本 `scripts/verify/tablet_landscape_preview.mjs`（注入候选 CSS 现场对比基线/触控/紧凑三态）。
- 2026-11-02：新增 `plans/备考资料_平板与电脑同版_可行性与预期效果_v1.md`（待拍板）。你要求「平板与电脑同一套页面、布局相同」。**关键实测**：电脑端资料页用的是 `repeat(auto-fill,minmax(150px,1fr))`，平板 768 自动 3 列（卡片 227×140）、1024 自动 6 列（152×170），**横向溢出 0px**；详情页（单列 + 侧栏 735）、上传页（`.mc-page` 860 上限）、徽章页（3 列）在 768 同样 0 溢出。唯一必须补的是触控：5 个元素 17–34px，全局 `@media(max-width:1024px)` 补完 → **0 个且布局一像素未变**。据此方案 A：三条 `/tablet/*` 改 `redirect` 到电脑端路径、首页入口与「离线下载」改指 `#/materials/xingce`、全局触控 CSS、删平板专用分支，约 0.5 天；7 张**真实渲染**的预期效果图已存入 `assets/备考资料_平板PC同版预览/`，脚本 `scripts/verify/pc_on_tablet_preview.mjs`（注入候选 CSS 现场对比基线/预期）。
- 2026-11-02：平板端补齐三项（你批准后实施，方案 v2）。①「入门讲解视频 / 深度拓展视频 / 备考指南」分区 + 「只看收藏」：逐 type 拉 `/api/materials?subject=&type=&page_size=50`（与 PC 同源、零新端点），视频/文章点击后页内弹层（`<video>` / `renderQuestionContent` 清洗后的正文）；**库内实际 0 条视频**，视频路径靠 CDP `Fetch` 域 mock 验证（不写库）。② 平板首页 DOM 注入「📚 备考资料」入口（守 R3 不碰 `.vtj` 模板）——放在 `.quick-actions` **之后的独立一行**（实测该网格所在中间栏仅 ~107px、4 列每列 80px，塞第 5 列会把卡挤成 62px），`hashchange`/`resize`/1.2s 定时/`MutationObserver` 四重兜底，判定纯函数 8 条单测。③ 新增 `/tablet/materials/detail` 复用 PC 详情页 + `@media(max-width:900px)` 单栏（侧栏 735px 全宽、返回键 44px），并修掉「5 层堆叠卡装饰层向上 60px 盖住字号行」的遮挡。门禁：页面路由 100→101、L6 动态 import 101；vitest 35 文件 479、vue-tsc 0、gate_all 10/10、手机 20/20、全图手势 9/9。
- 2026-11-04：**AI 讲师功能总体设计方案 v1**（`plans/AI讲师功能总体设计方案_v1.md`，待审批）。按你拍板的三项（A 网页播放器 / 你给清单 / 形象另定）给出可落地全案：知识点清单模板 + 题目格式 + **讲稿 DSL**（segments 六类型、avatar gesture/expression、scene kind、checkpoint question）+ JSON Schema 校验；**微课 7 段式**讲解逻辑（时长占比 + 5 条拆解规则 + 7 类动作触发词库）；参数化 SVG 讲师与 4 类场景（board/formula/police/custom）实现「卡通+正式并存」；播放器**状态机**与三端布局、检查点规则、正误动画（烟花+对勾 / 继续努力+解析）；前端全部新增 `src/views/lecture/*`（不动 `.vtj`，路由 /lecture/:id，页面路由 104→105 需同步）；P2 数据表与 4 个端点 + R11 白名单；**LectureSource 底座**（清单/题目/卡片 → 同一 DSL）；安全合规（禁 v-html、原创形象、LLM 内容须 approved）、运维（版本化/灰度/埋点/降级/回滚）、测试验收矩阵、P1–P3 分期、写码前 7 问自检、开工条件与完整示例脚本。
- 2026-11-04：**AI 讲师功能需求理解与初步设计**（`plans/AI讲师功能需求理解与初步设计_v1.md`，待确认）。把你的 4 条要求逐条复述并落成可执行规格：①先做「预写知识点清单」的样板 + 预留按题/按卡自动生成的底座；②学真人讲解风格/逻辑/肢体动作 + 场景跳转（法条现场/公式动画），画风「卡通+正式并存」；③总结真人拆解讲解的逻辑模板；④检查点弹题（数量不限）+ 正误反馈动画（答对烟花对勾 / 答错解析）。把 3 张截图反推成交互规格（左讲解 2/3 + 右题目 1/3、胶囊选项、绿/橙反馈、答案解析块、大对勾水印、章节时间轴、重播、紫色继续）。**诚实边界**：我无法直接看视频，需你给参考视频/字幕，或按讲授法微课模板 + 参数化动作库（gesture/expression）设计。技术取舍 A/B/C（推荐 A 网页交互播放器，无外部依赖、天然是底座），并给出讲稿 DSL、播放器状态机、P0–P3 分期、需要你提供的 6 项材料。
- 2026-11-04：**AI 讲师开工可行性评估**（`plans/AI讲师开工可行性_评估_v1.md`）。结论：无现成讲师分支（本地占位 `e3e2e54` 落后 main 209 提交；远端 `feature/ai-assistant` 已并入 main 且是对话助手；代码 `ai-lecture/lectureProvider/render_job` 命中 0），**但可在 main 上开分支，第①步不依赖外部服务**。main 可复用：`llm_client`（chat/chat_plan）+ 6 个 `/api/llm` 端点（含 `context/assemble`）+ ChatSession 表 + 知识图谱 14 端点 + Agent 6 端点 + 视频 8 端点 + F3 媒体资产 + `ai_chat.vue`。缺口：契约/任务表/seam 未建、无 TTS/数字人/合成（本机无 ffmpeg）、**LLM_API_KEY 为空**、库内 0 视频。建议从 main 切 `feat/ai-lecturer`，先做「契约+`ai_lecture_job`+状态机+讲稿生成+501 降级+白名单登记+详情页入口」。
- 2026-11-04：**备考资料模块成果总结**（`plans/备考资料模块成果总结_v1.md`）。实测规模：149 提交合入 main（模块相关 135，`materials.py` 改 30 次）、36 个 `/api/materials/*` 端点（全站 462 的 7.8%）、7 张相关表、110 条分类规则、库内 102 已发布（99 卡 + 3 篇科目说明）+ 5 下线、15 个后端测试文件 **151 条断言**、27 份文档。六项需求：①②③⑤ 完成、⑥ 部分（徽章展示层下线、成就金币引擎保留）、**④ AI 讲师/AI 视频未开工**。验收：`gate_all 10/10`、后端 151 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9。顺带修：`test_materials_my_card` 断言旧 `/uploads/…` 路径，F3 媒体资产开启后应认 `/media/{asset_id}`，改成按 `MEDIA_STORE_ENABLED` 二选一。
- 2026-11-04：**挑出本次新增的页面/接口**（`plans/远端main新增页面与接口_v1.md`）。做法：`git worktree` 分别检出 `da218d1`（10-26 老 main）、`8f03a7d`（合并前本地 main）、`89363f5`（当前 main），各自 `openapi()` + 路由表导出后取差集。结果：接口 349→373→**462**、页面 92→98→**105**；**相对老 main 新增 113 接口 / 15 页面、删除 0**；**相对合并前本地 main 新增 95 接口 / 11 页面、删除 6（徽章）**。远端线新增页面 11 条（论坛管理/教师论坛、联考小智、学习计划、知识图谱、AI 记忆、AI 错题本、新闻三端三页），本地线 4 条（资料详情/上传/预览、分类规则后台）。
- 2026-11-04：**修两个红 CI 作业 + 生成页面/接口清单**。①python 质量作业：`black --check` 命中 453 个历史文件（从未全面格式化、开发机也装不上这些工具）→ 拆成「阻断层（新增 `check_eager_annotations.py` 注解前瞻检查 + `compileall`）+ 提示层（black/isort/flake8/mypy 改 `continue-on-error`）」；②前端质量作业：CI node 20 自带 npm 10 与 npm 11 生成的 `package-lock` 不兼容（`EUSAGE: Missing vue-tsc@2.2.12`）→ node 20/22 统一升 **24**。**顺带抓到真 bug**：`materials.py` 的 `UploadFile` 在 744 行才导入、340/520 行签名已引用 → Python < 3.14 导入即 `NameError`（CI 3.13 崩、本地 3.14 因 PEP 649 惰性注解没暴露），已提到顶部导入；新增的注解检查对旧版本能精确报 2 处、对当前 219 文件 0 问题。另：container-ci 的 `gate_all --quick` 含需真实题库的 L1-G（CI 无 DB 必然红）→ 改跑静态门禁；VTJ 工作流加 `workflow_dispatch` 便于验证。结果：VTJ 工作流 **6/6 全绿**。同时产出 `plans/远端main页面与接口清单_v1.md`（页面 105 条 + 接口 465 个操作，带文件:行号链接）。
- 2026-11-04：**合并远端 main + 徽章展示模块下线 + 推送成功**（远端 `main` 已对齐 `88c0bd9`）。① 推送时发现远端已前进 174 提交（模块4/模块7、论坛治理、F3 媒体资产），与本地 149 提交分叉于 `a9e44d9`；先把本地推到远端备份分支 `backup/local-main-1104`，再合并，8 个冲突按「取并集/保留语义」逐个解（models.py 92 类无重名、白名单补登记远端 88 端点、README 远端 29 行集中附录）。② 合并暴露 5 个真问题并修：建卡 500「媒体存储缺少数据库会话」（补 `db/user_id`）、`SESSIONS_UPDATED` 未登记、exam 直读 catalog `QuestionGroup` 触发 L4 cross_write（新增契约 `question_groups_by_ids`）、媒体/图 DDL 的 CRLF checksum、`20261027` 迁移撞号（本地两支改 004/005；本地库补建 graph 两表）。③ 按你要求删除**徽章展示层**：24 文件 + 6 端点 + 3 路由 + `user_badge_top` 表（删前 tag `badge-module-before-delete` + 表数据 JSON 备份），**保留成就/金币/称号引擎**（`badge_task`/`BadgeNameBank`/`badge_service`/`Title`），门禁双改点 104→101。验收：`gate_all 10/10`、守卫 17 passed、vitest 42 文件 481、vue-tsc 0、PC 8/8、平板 31/31、手机 20/20、手势 9/9、openapi 409、库内 107 行。
- 2026-11-04：**模块 4/7 AI 演示态转真功能**（分支 `feature/ai-assistant-ai-real`）。后端 `/api/llm/chat` add-only 扩 3 场景 + `persist=false` 一次性通道（不落会话/不写消息，零新增端点）；前端作文批改/模拟面试/AI学习教练接真 LLM，失败自动回退旧示例；只改 `<script>`（R3，模板零改动）。验收：pytest 5 passed、L0 7/7、L5 PASS、VTJ 版本 70 一致；如实标注 3 条限制（教练统计模板硬编码、面试作答输入框缺失、真实 LLM/前端运行时未验证）。
- 2026-11-05：**AI 讲师功能要求与目标 v3（需求基准，待确认冻结）**（`plans/AI讲师功能_要求与目标_v3.md`）。你要求「重新梳理要求与目标」。重写原因：需求经 4 次追加（4 条口述 → 3 张截图 → 三项拍板 → 知识库接入 + 限制重查），旧文档里「用户提供知识点清单」「我读不到视频」等表述已过期。文档结构：**4 层来源逐条可追溯**；**13 条要求 R1–R13**（R1 样板+底座、R2 讲解风格/动作/场景跳转/画风、R3 拆解模板化、R4 检查点+正误动画、R5 **专利交底书 B**、R6 版权与法条可核、R7 三端、R8 视觉规范、R9 数据可追溯、R10 性能、R11 工程红线、R12 可维护、R13 可观测降级）每条都配验收方式；**6 个可度量目标**（检查点作答率 ≥70%、单点产出 ≤30 分钟、三种来源可切不换播放器、专利权利要求 3 组、门禁全绿、P1 预留 TTS/导出口子）；**7 条反目标**（不做数字人/现场对话/全自动批量/TTS/导出 mp4/切片真人课/模仿具体老师）；P1–P3 分期 DoD（P1 判定：3 节可在三端播完 + 门禁绿 + 可反查来源 + 关动效仍可读）；**旧文档 6 处表述的取代关系表**（含「AI 视频」口径澄清为网页交互微课、mp4 导出归 P3）；待确认 D1–D5。
- 2026-11-05：**资料导入 P0 实施计划（待最后确认开工）**（`plans/资料多格式导入_实施计划_P0_v1.md`）。你拍板 IMP-5 选 **B（共享组件 + 两个薄壳页）**、其余全部按建议 → 据此出 P0 计划：迁移 `20261105_006` 加 7 列（batch_id / progress_percent / current_phase / total_units / done_units / unit_name / retry_count）；状态机 7 态 + 失败重试 + 重启超时重置；进度 10/10–70/70–90/90/100 分段（PDF 页级、docx 段级、xlsx 行级）；后端只改 `library/materials.py` 并新增 `material_import_queue.py`、`ocr_provider.py`；新增 3 端点（batch 上传 / batch 汇总 / retry）并登记 R11 白名单；前端 `MaterialImporter.vue` 单点维护 + `admin/material_import.vue`（双列）+ `teacher/material_import.vue`（单列）+ 路由 104→106 双改点 + 沿用 `materialsCreateEntry.ts` 的 DOM 注入入口；顺手修 `material_parser.py` 里 `parse_pdf_text` **重复定义**（L159/L253，后者生效）；T1–T8 共 5.5 天，含 3 张真实渲染效果图 `assets/资料导入_P0/`。
- 2026-11-05：**待决策清单 v1（全部决策集中一处）**（`plans/待决策清单_v1.md`）。你要求「把要决策的事情全部列出来」→ 汇总 **27 条**：**A 本轮资料导入 9 条**（IMP-1 MinerU 形态 / IMP-2 单文件 250MB / IMP-3 上限分级 / IMP-4 学生端是否开放 PDF / IMP-5 教师端同页 / IMP-6 轮询 vs SSE / IMP-7 扫描件必须能导 / IMP-8 远端 sidecar / IMP-9 服务器有无 GPU）+ **B 数据运维 7 条**（OPS-1 生产题库怎么弄进来 / OPS-2 删 14.8GB zip 与 3 个 `.part` / OPS-3 合并 BN2027-p01 / OPS-4 大纲 4 条疑似笔误是否改名 / OPS-5 87 知识点入图谱 / OPS-6 Dataview 静态化 / OPS-7 2 个 docs 提交先合 main）+ **C AI 讲师 11 条**（暂停中，恢复再答：交付口径/3 试点/金币/形象/专利/单元粒度/8 个细目归属/别名表/产物落位/无题能否上线/转写范围）。每条含「选项 / 影响 / 建议 / 何时必须答」+ §E 决策→任务映射（谁卡谁）。两种回法：`全部按建议` 或逐条点名。
- 2026-11-05：**资料多格式导入方案 + 三件套安装落地**。①新分支 `feat/material-multi-format-import` 创建，AI 讲师暂停归档（`plans/AI讲师_阶段性成果与暂停记录_v1.md`）。②按你要求先读资料内部格式：`备考资料\` 57 文件 = **30 Excel / 1277 卡**（表头统一 正面·背面·分类·考点·封面）+ **26 PDF / 1619 页**（24 文字型、2 扫描型，最大 204 MB/90 页 0 字符）+ **1 docx / 297 段**；`题库\` 另有 480 PDF（473 文字型/7 扫描）。③**关键发现：后端早就支持 docx/xlsx/文字 pdf，并给扫描件留了 MinerU 异步通道**（`mineru_material_service.py`），但 `C:\mineru_env` 不存在、前端只有学生 Excel 页、导入记录无进度字段 → 真正的缺口是「前端入口 + 批量队列 + 进度模型 + MinerU 环境」，不是"从零做导入"。方案见 `plans/资料多格式导入_现状实测与方案_v1.md`（含新增 3 端点、迁移 `20261105_006`、页面路由 104→105 双改点、P0–P2、D1–D6）。④**E1/E2/E3 已执行**：winget 装 ffmpeg 因走 github releases 失败（github 000）→ 改用 pypi `imageio-ffmpeg`（wheel 内含 9.0.2，复制到 `%LOCALAPPDATA%\hermes\bin\ffmpeg.exe`）；`uv` 不读 pip 镜像配置导致 20+ 分钟下不完 ~100 MB → 加 `--default-index 清华` 后 **53 秒装完** faster-whisper 1.2.1 + rapidocr 1.4.4 + av 18.1.0；OCR 10 帧实测 **45.67 s**，印刷体近乎全对、红笔手写为乱码（与预判一致）；`medium` 模型仍在下载。
- 2026-11-05：**AI 讲师的「看视频」能力已实测跑通**（`plans/AI讲师_视频学习能力方案_v1.md`）。你问「哪个插件能让你获得视觉能力、看视频学讲解风格」——答案是**不需要视觉插件**：`read_image` 本来就是通的，缺的是**视频解码器**；已装的 4 个 DSH 插件（dshmarket/dsh-context/dsh-obsidian/superpowers）都不提供视频能力。**POC 已成功**：`pip install --target %TEMP%` 隔离装 `imageio-ffmpeg`（得到 ffmpeg 9.0.2，未改系统/PATH），从 `桐哥 p06 传唤`（358 MB / 90 min）抽 3 帧并生成 **12 帧 contact sheet**（`assets/AI讲师_视频风格/`），我读出：标题「调查取证——传唤」、三行法条表格、**红笔圈注/下划线/侧边竖排结论**、底部口语字幕、以及**空白《传唤证》实物 + 老师现场填写"2027年1月10日10时5分…15时45分"**。据此已得出 6 条可落地观察（版式固定/标注是主要手段/书面+口语双文本通道/需 `document` 文书场景/`compare` 对比表逐行高亮/单页仅 4–5 分钟 → 微课应 3–5 分钟）。路线对比：A 本机 ffmpeg+我读图（推荐，0 成本）｜B 云 VLM（智谱 200/火山 401/通义 404/硅基 404 可达，但需 key、花钱、粗描述、上传付费课程有版权风险）｜C 本地 VLM（5–15 GB、6 GB 显存需 int4，性价比低）。待批 E1 装 ffmpeg / E2 建 ASR 环境 / E3 OCR。
- 2026-11-05：**限制与缺口清单 v2（重列，纠错版）**（`plans/AI讲师_限制与缺口清单_v2.md`）。你要求「不要因为没有视频之类的就判定为无解」，重查后 **v1 有 3 条判定错、2 条事实错**，已全部更正（媒体不在 E 盘而在 `桌面\名师讲解视频`；台账是**相对路径**、75/76 命中；ffmpeg 未装但 pypi/清华/aliyun 全 200、winget/choco 在位、`imageio-ffmpeg` 免管理员；无 ASR 但本机 RTX 4050 6GB + uv Python 3.11 + hf-mirror 200 → faster-whisper 可跑；法条从 `flk.npc.gov.cn` 取，200）。清单结构：**8 条环境限制（全部可解，含具体命令）+ 20 条资产缺口（A-01~A-20，每条写解法/产出物/优先级）+ 4 条翻案 + 仅 2 条真不可逆（生产题库 10,171 题不在本机、网课版权不可二创分发）**。新增任务 T9（媒体体检与修复：装 ffmpeg、合并 BN2027-p01、抽 12 帧样例）/T10（转写试点 TG2027-p06）；D7 媒体根更正已执行（改 首页 §八 + §一，变更日志已记），D8 是否现在装 ffmpeg+ASR 待你定。
- 2026-11-05：**AI 讲师知识供给适配器方案 v1（待审批）**（`plans/AI讲师_知识供给适配器与播放器衔接_方案_v1.md`）。你的问题是「先做适配器（JSON 树 → point_id + 可讲清单 → `lecture_source.json`，不写前端），再立刻进播放器行不行」。**结论：可以，且应先做**，但实测发现一个会让方案落空的事实——12 个试点单元里 **8 个在 87 知识点里没有对应节点**（立案/管辖/回避/传唤/听证/当场处罚/处罚执行/新旧法对比都是 `GZ-JC-010 行政执法基础知识` 下的程序细目），所以必须加 **topic 教学切片**第三层，否则「一知识点=一节微课」要讲 30 分钟。方案给出：5 条限制解法（`curl github.com` 实测 000 → Dataview 改**静态表**而非装插件；`ffmpeg/ffprobe/whisper` 全无 → P1 不依赖转写；`question_bank` 仅 **200 题**、`question_knowledge` 126 行覆盖 **26/94** 知识点、`point_id` 全 NULL → 检查点题分 `bank/hand/none` 三态）、三层键（`point_id` 87 个 + `topic_id` + `exam_point_id`，冻结 + 墓碑）、可讲清单 5 字段规则、JSON 契约 + sha256 自证、`--check` 防漂移、T0–T8 任务表（含估时与回滚）、写码前 11 问自检、D1–D6 待拍板；另附 3 张真实渲染效果图（`assets/AI讲师_知识供给/`）。顺带纠偏：库内《创新设计》举例 `SL-GN-004 = 影响概括` 实为 `特点概括`（影响概括是 `SL-GN-005`），佐证 ID 必须脚本生成。
- 2026-11-05：**AI 讲师知识库迁入 Obsidian**（`superpowers/specs/AI讲师知识库_迁入Obsidian与知识供给_报告_v1.md`）。库从桌面搬到 `…\OneDrive\文档\Obsidian Vault\AI讲师知识库`，作为现有 vault 的子目录（这样库内 73 个 Canvas `file` 节点仍写 `AI讲师知识库/…` 全前缀、继续解析）；127 文件 240,694 字节搬迁前后一致，`dsh-obsidian@0.2.6` 实测可列/读/搜/写（不走 Local REST API）。**价值判断**：它把 AI 讲师 P1 缺的「知识点清单」直接备好了——3 科目/15 模块/**87 知识点/403 考点**（JSON 树）+ 10 个首批试点考点 + 3 篇讲师范式（桐哥四步：条文定位→程序时序→要件拆解→对比与陷阱）+ 画面渲染规范（1920×1080、96px 安全边距、页脚「模块名·考点ID·页码」、动效 200–400ms + 静态降级、**禁止生成式模型产文字/公式/法条**）。**顺带抓到 3 处缺陷**：①`首页.md` 分科目知识点数 29/28/30 与 JSON 实测 27/25/35 不符（已按铁律「数字必须实测」修正并写 `变更日志.md`）；②`AI讲师数据库创新设计_v1` 声称知识点 ID 表已写入大纲 §3，实测大纲 §3 是「疑似笔误」表、全库无 ID 映射 → DSL `point_id` 暂无可填值；③403 考点仅 312 个不同名，「其他」出现 86 次，另 14 个知识点零考点 → 需可讲清单筛选规则。另修 `docs/README.md` 一条**悬空索引**（`AI讲师知识库_搭建说明_v1.md` 从未入库）。
- 2026-11-05：新增快速练习知识分类体系 v2（设计 + 实施计划）。全中文命名，446 张规范卡，甲乙两族，8 关系，10 区 Obsidian；明确 91 个“其他”不建卡、531 个停用节点只建索引；P1–P4 不写 DB/代码，P5 单独审批。v1 设计文档标记为历史版本。
- 2026-11-05：Obsidian 子库「快速练习知识分层」搭建完成（1164 文件 / 1150 md + 5 canvas，断链 0），交付于 `D:/Obsidian仓库/快速练习知识分层`；新增 `superpowers/specs/快速练习知识分层Obsidian知识库_搭建报告_v1.md`，设计文档状态改为「设计完成，待批 D1–D10」。
- 2026-11-05：新增 `superpowers/specs/快速练习知识分层知识图谱与Obsidian自生长知识库_v1.md`（待审批）。快速练习四层知识图谱 + Obsidian 自生长知识库方案：6 处第一版硬校正、8 条关系、14 区目录、qp_kg_* 覆盖层 + 编译器、H1–H13 健康度、P0–P4 路线、D1–D10 待拍板；本轮只设计不实施。
- 2026-11-05：**修复管理员端资料/成就 500 与存量库列漂移**。根因：模型新增 5 列（`achievement.badge_tier`、`user_achievement.tier_snapshot/snapshot_estimated`、`study_material.point_id/source_material_id`）未迁移到存量 SQLite，`create_all` 不会 ALTER 已有表，ORM SELECT 直接 `no such column`。新增 `backend/app/core/schema_heal.py` 启动自愈（只补可空缺列、幂等），`main.py` 启动调用；成就播种回填 `badge_tier`；执行 `init_material_data.py`（32 卡/3 成就/16 规则）与 `init_badge_names.py`（84 名）。四个 500 接口全部 200，管理员资料页 32 行、编辑弹窗可用；报告见 `superpowers/specs/资料模块500与Schema漂移修复_报告_20261105.md`。
- 2026-11-06：**19 条待决策全部裁定，方案冻结为 v3.1**（`plans/待决策裁定结果_v1.md`；`plans/资料管理v3_预览发布者类型双格式试卷讲义_方案_v1.md` 升 v3.1）。你的回法：D28–D31 / D33–D37 / D39 / D21–D24 / D26–D27 全按建议；**D32 改写**（去掉表单必填，只从文件名取科目/年份/地区/题本，没有的先空着，并新增"列表内改信息"弹窗）、**D25 参照 D32**（元数据表降级为可选批量补录）、**D38 改写**（筛选栏加"最近 7/30 天"）。净增量：+1 端点 `PATCH /api/materials/admin/{id}/meta`、+1 组件 `MaterialMetaDialog`、+0.4 天；迁移次数不变；DoD 9→12 条；新增效果图 `05_试卷改信息_弹窗.png`、`06_筛选栏_最近7天30天.png`
- 2026-11-06：**试卷文件名解析实测（517 份真实文件）**（探针 `scripts/probe_paper_filenames.py`，逐文件明细 `plans/assets/试卷文件名解析_实测_v1.csv`）。命中率：科目 100%、年份 100%、地区 99.4%、题本/答案 99.8%、**四要素齐 99.2%（513/517）**、题量与满分 **0%**（文件名里根本没有）→ 支撑 D32「有就读、没有留空、入库后再改」；仅 4 份命名特例解析不齐；`paper_code` 人读码实测 517 份只出现 11 个重复（多为同卷重复件）。
- 2026-11-06：**「未分类题目可答题与分类回填」已批准并实施可答题链路，PC 浏览器真机验收通过**。668 题 `sub_category_id IS NULL`（行测 341 / 申论 11 / 公专 316）；160 题有旧字段/qk 证据，**已 apply，未分类 668→508**（行测 192 / 申论 0 / 公专 316）；508 题保留「未分类」可答题；已改 0 号 API（`subjectId` + `sub_category_id IS NULL`）、PC/手机入口、回填脚本、3 条接口测试；Obsidian 429 文件/断链 0；**PC 真机 20 题进入→作答→交卷，控制台 20 条记录，落库后按 ID 清理**；**160 行仅改 sub_category_id，核心字段指纹不变**。报告 `superpowers/specs/快速练习未分类题目可答题与分类回填_实施报告_v1.md`。
- 2026-11-06：**快速练习周任务设计分配设计要求已获用户批准**。批准范围为设计框架、周任务配比、审批闭环、Obsidian 设计态/审批态、接口契约；不包含写 DB、改后端/前端、P3 API 实现与 P5 写库。批准记录 `superpowers/specs/快速练习周任务设计分配_设计批准记录_v1.md`。
- 2026-11-06：**周任务设计分配 Obsidian 知识库 P1 已搭建并验收**（设计态，未写 DB/代码）。`D:/Obsidian仓库/周任务设计分配` 427 文件 = 413 Markdown + 5 Canvas + 6 JSONL + 2 JSON + 1 PowerShell；220 张任务卡（55 主题 + 165 模板）、12 周、84 日批、216 实例；532 节点 / 1033 边，断链 0、Canvas 断链 0；5 Canvas、8 看板、15 篇接口契约、9 篇治理；`每日审批提醒.ps1 -Test` 实测待批 7 天；数据库 sha256 前后一致。已知：6/165 模板可试点、159 待补题、42/55 主题无考点、33 个相邻周重复主题；报告 `superpowers/specs/快速练习周任务设计分配Obsidian知识库_搭建报告_v1.md`。
- 2026-11-06：**快速练习知识分类体系 v2 P1 已实施并验收**（Obsidian 设计态，未写 DB/代码）。`D:/Obsidian仓库/快速练习知识分层` 由 v1 的 1164 文件重建为 v2 的 547 文件（446 规范卡 + 5 Canvas + 8 数据文件），10 区 + 首页；边 828 = 包含 278 + 实例 165 + 大纲映射 385；断链 0、Canvas 断链 0、V1–V21 全过、数据库 sha256 前后一致。已知：165 考点 0 题、171 甲类知识点无考点、候选语义边 0；报告 `superpowers/specs/快速练习知识分类体系_v2_搭建报告.md`。
- 2026-11-07：**B2 批量上传 + 双格式配对 + 队列进度（B 批 3/3 收尾）**（`plans/B2_批量上传与双格式配对_交付记录_v1.md`）。新端点 `POST /api/materials/admin/files/upload`（**一次一个文件**：不带 `material_id` 建未上架资料 + 原件主文件，带则挂附件）；同内容 `sha256` 命中返回 `duplicate=true` 不新建；扩展名 + magic bytes + 20MB 三重校验。前端新增 `MaterialBatchUpload.vue`（选文件 → 统一入库参数 → 逐条队列）与纯函数 `batchUploadPlan.ts`（同名 docx+pdf **合并一条**、docx 主文件 / pdf 附件、≤50 文件 / ≤2GB、重复同扩展名只留第一个），两个按钮从"灰的"变成可用（批量导入预置讲义、＋上传试卷预置试卷），完成后自动刷新。**实测**：真实对话框选同名 docx+pdf → `将创建 1 条资料（含 1 组双格式）` → 队列「上传中」带进度 → 列表出现 ID **122**（讲义/公专/基础知识），抽屉两行原件（docx 主文件 35KB + pdf 附件 70B，附件可下载 `%PDF-`），重复上传 `duplicate=true`、total 仍 114。pytest **15 新增 / 106 回归**、vitest **590**、typecheck 0、gate 9/10（**跑门禁须带 `OPENAPI_URL=http://127.0.0.1:8001/openapi.json`**，8000 被 Docker `om-ai-service` 占用，否则 L4 假红）。截图 `B2_01_批量导入_队列与双格式.png`、`B2_02_双格式原件_主文件与附件.png`
- 2026-11-07：**B1 资料原件留档（material_file + 鉴权下载）**（`plans/B1_资料原件留档_交付记录_v1.md`）。原来导入解析完就把源文件删了，库里只有正文没有原件。新增 `material_file` 表 + `material_files` 服务（`.part`+`os.replace` 原子写、sha256 **内容寻址**、`resolve_abs_path` 越界防护、`orphan_count` 对账）；导入确认**先落档再删临时文件**；预览抽屉「原件（N）」区可点「下载」。**位置按裁定 A** 放 `backend/storage/material_files/`（**不放 `/uploads` 公开挂载**），下载走 `GET /api/materials/files/{file_id}/download`：管理员不限（含未上架/已删除），其他角色仅已上架（`can_download` 纯函数守边界，R11 白名单 +1、基线仍 343）。**实测**：material 121 原件 35898 字节、管理员下载与源文件字节级一致（Content-Disposition 带 UTF-8 原名）、学生未上架 403、匿名 401；抽屉显示 `DOCX 04_讲义_正常.docx 主文件·35 KB 下载`。**顺带两个根因修复**：①`UPLOAD_IMG_DIR/UPLOAD_TMP_DIR` 原写死 `uploads/...`，改为跟随 `settings.UPLOAD_DIR`；②OneDrive 同步扫描锁库导致 pytest 第 4 个用例后整进程卡死 30s（`faulthandler` 栈指向 `_save_tmp → write_bytes`），`conftest.py` 在 import app 前把上传/原件目录指到 `%TEMP%` 后 27 用例 9 秒跑完。pytest **27 新增 / 98 回归**、vitest **569**、typecheck 0、gate 9/10（唯一 FAIL 为既有 L1-G）。截图 `assets/资料管理v3/B1_01_预览抽屉_原件下载.png`
- 2026-11-07：**B3 讲义落 card 修复 + 重复导入拦截（B 批第 1 项）**（`plans/B3_讲义类型修复与重复导入拦截_交付记录_v1.md`）。**根因两处**：①`import_confirm` 只接受 `type=article` 却在建行时用分类器结果覆盖了它；②分类器把「字数<500 的文档」一律判 `card` → 短讲义落进卡片区（实测 `04_讲义_正常.docx` 两次导入 = material 121/122 都是 card）。**改法**：文档类 `type` 白名单 article/lecture、**不传默认 lecture**、分类器不再参与判定；分类器文档分支改为恒 `lecture`；上传阶段按「同名+同大小+sha256」拦同文件重复（409 且消息带旧记录号），confirm 阶段按 `content_hash` 拦同内容重复（409，`force=true` 放行）；旧页向导经 DOM 注入补「作为讲义」并默认选中 + 徽标英文 key 中文化（R3 不动模板）。**实测**：真实样本导入 → material 121 `type=lecture`、统计 112→113 / 讲义 3-0→3-1；同文件再传 409；换名同内容 confirm 409；旧页徽标由 `lecture` 变「讲义」，向导内联显示 409 原文。测试 pytest **17 新增 / 106 回归**、vitest **567**、typecheck 0、`gate_all 9/10`（唯一 FAIL 为既有 L1-G）。截图 `assets/资料管理v3/B3_01_重复上传被拦_讲义徽标.png`、`B3_02_入库类型_作为讲义.png`。**事故已披露**：清理演示记录时一条未限定 `import_id` 的 delete 误删 11 条历史解析记录，已从 10-28 备份恢复 2 条（1/5），另 9 条（12–18、22、23）无备份可依、无法重建；**资料/题目/考试数据零影响**（详见记录 §4）
- 2026-11-07：**A4b 管理端删除改软删除 + 回收站**（`plans/A4b_删除改软删除与回收站_交付记录_v1.md`）。清理两条测试资料（121/122）时实测发现：`DELETE /api/materials/admin/{id}` 与 `/admin/batch` 都是 `db.delete()` **物理删除**（还清学习进度），与已批准方案 §2.2「-1=软删除」相反；**顺带查出既有缺陷：`/admin/batch` 因声明在 `/admin/{material_id}` 之后，永远被当成 `material_id="batch"` → 422，批量删除从未调通**。按你裁定 **B** 改：单条/批量删除都置 `status=-1`、保留 `user_material_progress`、已删行重复删幂等（`already_deleted`）；恢复 = `PUT /admin/{id}/status {status:0}`（回到未上架，需再上架才对学生可见），审计单列「恢复资料」；前端状态下拉加「回收站（已删除）」，已删行只留「预览/恢复」，删除文案改为「移入回收站…可随时恢复」。**实测**：DELETE 110 → total 112→111 / published 102→101 / deleted 5→6，默认列表不含、回收站含 → 恢复 → 再上架后 `data restored=True`；回收站视图 5 行（47/46/25/20/16）标签「已删除」、恢复链接色 `rgb(15,122,77)`、无上架开关；两个确认弹窗文案与按钮全部实测。新增 `test_materials_soft_delete.py` **13 passed**，资料四套 **45 passed**，vitest **545 passed**，typecheck 0，`gate_all 9/10`（唯一 FAIL 为既有 L1-G）。截图 `assets/资料管理v3/A4b_回收站视图.png`、`A4b_恢复确认弹窗.png`
- 2026-11-07：**A5 侧栏冻结完成，A 批 6/6 全部收尾**（`plans/A5_侧栏冻结_交付记录_v1.md`）。`sticky` 实测被 VTJ 三层 overflow 容器打破（滚动 600px 后 rectTop 0→−600），改为 **`position:fixed`**：侧栏 `left:0;width:220px`、`.admin-right` `margin-left:220px`、折叠态 64px 联动（根节点加 `is-collapsed`）；**顶栏也改 fixed**（第一版只改 sticky，实测同样失效 −380→−486），用 `.admin-right{padding-top:56px}` 补偿高度，页面视觉位置不变；顶栏描边/阴影/面包屑统一到 `--adm-*` 令牌。实测：`sidebar moved=false`（滚动 600px 后 top 仍 0）、`header moved=false`、折叠态 64px/偏移 65px；`.vtj` 页回归无重叠（headerBottom 56 < firstContentTop 105，dashboard/logs 两页）；typecheck 0 新增。截图 `assets/管理端画风/A5/A5_01_侧栏与顶栏固定.png`。**A 批交付完成，等人工验收**
- 2026-11-07：**A4 资料管理新页已上线**（`plans/A4_资料管理新页_交付记录_v1.md`）。`/admin/materials` 从 `.vtj` 低代码页换成手写页：**5 格统计**（总资料/试卷/文章·讲义/卡片/已上架·未上架）、6 类筛选、发布者列、上传时间列（表头点按切换正/倒序）、**时间范围（7/30 天）**、每行「预览」直接开 A3 抽屉、**上架开关=审批通过**（带后果确认）；旧页保留在 `/admin/materials/legacy`（智能导入/富文本/批量操作过渡用）。**试卷收敛 P0–P5 全部按建议落地**：删「试卷审批」菜单项、`/admin/papers` 改 redirect 到 `/admin/materials?type=paper`（旧书签不 404）。**门禁数字没变**：`materials` 换 component ±0、`materials/legacy` +1、`papers` 去 component −1 → 净 0，仍 **105**（实测 L6 105 处 import 全在、L7 5 passed）。实测：新页 DOM（5 格统计 114/0/3-0/111/103-11、9 列表头、20 行、菜单 10 项无试卷审批）、`/admin/papers` → `#/admin/materials?type=paper`、legacy 页可达、点「预览」抽屉出真实数据（04_讲义_正常/知识卡片/公专/已上架）；typecheck 0 新增。**v1 边界**：上传试卷置灰（等 B 批 `material_file`）、改信息等 C2b、批量/智能导入走旧版页
- 2026-11-07：**统计口径修正（你裁定 A）：统一「不含已删除」**，修掉「已上架 + 未上架 ≠ 总资料」。根因：`admin_stats` 的 `total = count(*)` 把软删除（status=-1，实测 5 条：ID 16/20/25/46/47）也算进总数，而 `by_status` 只取 1/0；`by_type`（卡片 116）同样含这 5 条；`admin_list` 不传 status 时也不过滤 -1 → 删掉的资料仍在列表里。**改法**：`admin_stats` 的 total/by_type/by_subject/by_status 统一 `.filter(status >= 0)`，并新增 `by_status.personal`（学生个人库单列）与 `by_status.deleted`（追溯用、不进 total）；`admin_list` 默认 `status >= 0`，显式 `status=-1` 仍可查已删除。**实测**：total=114、by_type 合计=114、published+draft=114、list total=114、`status=-1` 查得 5 条；新增 `test_materials_stats_scope.py` 9 passed，同批回归 77 passed。截图 `assets/资料管理v3/06b_统计行5格_口径修正后.png`；mockup 07 数字已同步为"补录后"的自洽值（116 / 2 / 3/1 / 111 / 105/11）
- 2026-11-07：**资料管理统计行改为 5 格（用户指定顺序与双值形态）**并已落到真机。规格：`总资料 119 ｜ 试卷 0 ｜ 文章/讲义 3/0 ｜ 卡片 116 ｜ 已上架/未上架 103/11`；**双值卡**（`AdminStatCard` 新增 `value2` / `value2Tone`，左值主色、右值弱色/橙）；"视频"不再单列（并入总资料）。实现方式：A1 的 DOM 注入从"追加 2 格"升级为"整行接管 5 格"——给 `.stats-overview` 加 `a1-stats-overridden` 隐藏原 4 格，离开页面自动还原；数据仍取 `/api/materials/admin/stats`（15s 节流 + 20s 刷新）。实测（无头 Chrome 读 DOM）：`injected=5`、`originalsVisible=0`、`doc=3/0`、`status=103/11`、试卷色 `#b35309`、已上架 `#0f7a4d`；vitest 52 passed（含 11 条注入用例与 `buildStatValues` 纯函数用例）、typecheck 0 新增。**注意**：试卷当前真实值为 **0**（库内还没有 `type=paper` 的资料，需 C 批补录那 2 套原卷），不是统计错误
- 2026-11-07：**试卷管理收敛方案 v1（单一入口 + 上架即审批）**（`plans/试卷管理收敛_单一入口与上架即审批_方案_v1.md`）。你要求「不要多种上传试卷的方式，只保留资料管理页的试卷管理，审批改成批准上架=审批通过」。**实测盘点**：试卷有 **6 条链路 / 8 处建卷调用**（`papers.py:88`、`paper_generation.py:186/354/464`、`question_import.py:3680`、`smart_exam.py:320`、`teacher.py:776/1243`）；**两套状态机并存**（`study_material.status` -1/0/1 = 5/11/103；`exam_paper.paper_type` ENDED 1 / PUBLISHED 2）；独立审批页 `#/admin/papers`（214 行）+ 菜单项 `AdminLayout.vue:112`。**方案**：试卷=一条资料（`type=paper` + `material_file` + `paper_code`），只留**两态**（未上架=未通过 / 已上架=通过），**上架动作即审批**；`exam_paper` 降为投影（上架→PUBLISHED、下架→DRAFT，`exams.py` 三处过滤依赖）；审批页与菜单下线。含变更清单（前端 4 / 后端 4 / 数据 3）、6 条风险（含"下架了但学生还能考"）、7 条 DoD；**待拍板 P0–P5**（默认状态 / 收敛范围 / 下架是否填理由 / 现有 2 套卷补录 / 旧路由 redirect / 教师上传预留）；附效果图 `assets/资料管理v3/07_…png`
- 2026-11-07：**A3 统一预览契约 + 预览抽屉 已落地**（`plans/A3_预览抽屉_交付记录_v1.md`）。新端点 `GET /api/materials/admin/{id}/preview`（`_require_admin`，含未上架；正文**二次 sanitize**）在 TS 与 Python 两侧定死同一契约；`MaterialPreviewDrawer.vue` **一个组件覆盖 6 类**（卡片正/背/配图、文章正文、视频、以及 B/C 批的 chapters/files/paper 占位）。组件**不发请求**（受控：preview/loading/error），组件库页 `#/admin/dev/style` 加了可点的演示区（3 个样例 + 用真实 ID 打开），**不新增路由**。实测真库：id 120 卡片（未上架可见、uploaded_at=null）、id 1 文章（正文 2214 字符含 h2 与表格）、999999→404、非管理员→403；`pytest 12 passed`（含 api_surface 白名单 +1）、`vitest 30 passed`、typecheck 0 新增；截图 3 张存 `assets/管理端画风/A3/`。**两个如实说明**：①`uploaded_at` 恒 null —— `material_import_record` 无 `material_id` 外键，无法可靠反查，B 批补；②过程中 Vite dev server 因编辑器原子写临时目录 `EBUSY` 崩溃（表现为"页面还是旧的"），已重启并清理，建议后续给 `server.watch.ignored` 加 `**/.*.tmpdir/**`
- 2026-11-07：**A2 上传时间 / 发布者 / 最近 7·30 天 已落地（后端 + 前端 API 层）**（`plans/A2_上传时间与发布者_交付记录_v1.md`）。`/api/materials/admin/list` 新增 `created_within=7d|30d`（**滚动窗口**）、`order=created_desc|created_asc`、`publisher_id`；item 增 `created_at`（补 `+08:00`，空值为 null）与 `publisher{id,name,role,role_label}`（一次查询，无 N+1）；排序改按入库时间且 **`create_time` 为空的行恒定排最后**（否则正序时 NULL 会顶到最前）。实测真库：7d=17 / 30d=61 / 全库 119；正序最早 = id 1（2026-10-27）；`created_within=5d`、`order=id_desc` 均 422。前端 `fetchAdminMaterialList()` + 类型（空串参数不下发，避免 422）；pytest 13 passed（同批回归 61 passed）、vitest 6 passed。**数据发现**：119 行里 **58 行 `create_time` 为 NULL**（id 48–105，全是卡片）→ 显示 `—`、不进窗口筛选，**不回填**（无可靠来源，硬填等于伪造）；另记一项待核：`init_material_data.py` 用 SQLite `CURRENT_TIMESTAMP`（UTC）写时间，与 ORM 的本地时间口径不一致，现有 61 行未发现异常时段，E1 渲染时再核。页面上要看到这两列仍需 **A4 换页**
- 2026-11-07：**侧栏配色定 D `#33465F` 并落到真机**（E2 复议收口）。`admin-tokens.css` 新增 `--adm-sidebar/--adm-sidebar-active/--adm-sidebar-active-shadow`；`AdminLayout.vue` 的 `.admin-sidebar` 从写死 `#1A3C6D` 改为 `var(--adm-sidebar)`；激活态由「半透明白 + 红色左竖条 `#C41E3A`」改为**品牌蓝圆角块**（`rgba(64,84,224,.92)` + 9px 圆角 + 阴影），`sidebar-nav` 左右内边距 0→8px。实测（无头 Chrome 读计算样式）：`sidebarBg=rgb(51,70,95)`、`activeBg=rgba(64,84,224,0.92)`、`activeRadius=9px`、`activeBorderLeft=transparent`。示意图 02/04 已同步换色，真机截图存 `assets/管理端画风/06_侧栏新配色_真机落地.png`。**注意**：只改了颜色与激活态，**侧栏「滚动时不动」仍未修**（A5 的 `fixed + margin-left`，因 sticky 被 VTJ 三层 overflow 容器破坏）
- 2026-11-07：**侧栏配色复议（E2 重开）**。你反馈「侧栏颜色过于深沉」→ 出 `assets/管理端画风/05_侧栏配色_六选一.png`：现状 `#1A3C6D`（白字对比度 10.99）+ 5 个候选——A 中蓝 `#24487D`（9.14）/ **B 亮蓝 `#2B5AA0`（6.83，推荐；激活块翻白底更像"选中"）** / C 天蓝 `#3A6BB5`（5.32）/ D 蓝灰 `#33465F`（9.62，不偏纯蓝）/ F 浅色整条 `#FFFFFF`（深字 12.79，最轻）。全部按 WCAG 算过对比度（AA ≥4.5 均满足）。**待你选定**后改 `--adm-sidebar` + `AdminLayout.vue` 里写死的底色（A5 一并换 `var()`）
- 2026-11-07：**画风底座确定后的「各界面预期效果图」出图**（`plans/assets/管理端画风/03_全站12页总览.png`、`04_用户与权限_新画风.png`；配套 `01_令牌与组件`、`02_画风对照`）。12 个管理页**结构全部取自源码实测**（表头列名/页签/按钮文案原样），只换画风：统一后每页只剩三件套 `AdminPageHeader` + `AdminToolbar`/`AdminStatCard` 行 + `AdminTable`；emoji 保留（E3=C）但尺寸对齐由组件统一。逐页对照表已写入 `plans/管理端画风统一_方案_v1.md` §8（页面/现网问题/新画风要点/对应图 四列）；**E2 验收口径明确为「只换皮不换功能」**——列、页签、批量操作、权限判定一个都不减（最重的 users 页 1214 行、8 列 + 4 页签 + 批量条已出全尺寸图）。备注：资料管理页的预期效果早已有图（`assets/资料管理v3/01,05,06`），本批不再重画
- 2026-11-07：**A0 画风基座已落地**（`plans/A0_画风基座_交付记录_v1.md`；裁定 E1=A/E2=A/**E3=C 保留 emoji**/E4=B/E5=A 已回填进 `plans/管理端画风统一_方案_v1.md` §7.1）。新增 `src/styles/admin-tokens.css`（12 色 + 圆角/阴影/字号/间距 + `.adm-btn/.adm-input/.adm-empty/.adm-card` 工具类，**用纯 CSS 变量而非 scss**——仓库未直接依赖 sass）、`src/components/admin/` 6 个组件（Tag/StatCard/PageHeader/Toolbar/Table/FormItem，全部只读 `var(--adm-*)`）、组件库预览页 `/admin/dev/style`；顺手修：面包屑回落到 `route.meta.title`（原先无菜单项的页面只显示"管理端"）、统计卡空值显示 `—` 而非 0。**门禁数字变更**：新增 1 条页面路由 → L6/L7 页面计数 **104 → 105**（两处已同步并写明原因，可回滚）。验证：vitest **20 passed**、`verify-modularization-constraints` 通过（105 处 import 均存在）、`pytest test_route_roles` 5 passed、typecheck 0 新增；真机实测 `--adm-primary=#4054e0`、tone=warn 数值色 `rgb(179,83,9)`；截图 `assets/管理端画风/A0/`。自查出 3 个缺陷并修（模板未定义变量静默失败 / `withDefaults` 把 undefined 变 0 / 面包屑兜底错）
- 2026-11-07：**管理员端画风统一方案 v1（并行轨 E 批 + 前置基座 A0）**（`plans/管理端画风统一_方案_v1.md`）。你要求「维持现有方案，建新版界面的同时把管理员端所有界面换成新画风」→ 不改 A 批顺序，插 A0 基座 + E 批。**实测三条决定性结论**：管理端 12 页里 9 个 `.vtj`（R3 禁改模板）/ 3 个手写页；全仓 **0 个 Element Plus 组件**（"改 el 主题变量"这条路不存在）；**0 个 scss 变量**、新主色 `#4054e0` 出现 0 次。因此定为**三层落地**：令牌（12 色/6 档间距/5 档圆角）→ 6 个 admin 组件 → 页面（4 手写页直接换、9 个 `.vtj` 页用 `.admin-layout` 作用域覆盖层洗一版）。**诚实边界**：覆盖层只能做到"观感统一"、做不到像素级（scoped 特异性 2 需子孙选择器对抗；设计器 iframe 里看不到新画风）。工期 8.2 → **约 14.2 天**，其中 A0 后 1.5 天有组件库、A4 后 3.5 天能看到第一个新画风真页、A5 后外框全站统一。另附 11 张管理端现状真机截图用于走查，起出 6 条现网画风毛病（emoji 当图标/标题与面包屑重复/时间裸 ISO/激活态红竖条/圆角阴影不统一/图表空窗）。**待拍板 E1–E5**（统一程度/侧栏配色/emoji 处置/图表空窗是否本轮修/可读性缺陷是否顺手修）
- 2026-11-07：**A1 类型扩展（讲义/试卷）已落地**（`plans/A1_类型扩展_交付记录_v1.md`）。后端 `materials.py:30 TYPES` 加 `lecture`/`paper`、`admin_stats.by_type` 补两键（零迁移）；前端新增**类型登记表单一真源** `src/modules/library/materialTypes.ts`（6 类 + 中文名 + 徽标色 + 视频/双格式标记），并按 R3 **不改 `.vtj` 模板**、用 DOM 注入 `src/utils/adminMaterialTypes.ts` 给管理页补「讲义/试卷」下拉项与两格统计卡。实测：stats 6 键（lecture 0 / paper 0）、`?type=lecture` 由 400 变 200、非法类型仍 400；vitest 17 passed（含 6 条 jsdom 注入用例）、pytest 29 passed（api_surface/route_roles 证明 R11 343 与 L7 104 未变）、typecheck 0 新增、gate_all **9/10**（唯一 FAIL 为既有 L1-G 题量护栏，与本批无关）；真机截图 2 张（`plans/assets/资料管理v3/A1/`）
- 2026-11-08：**C3 试卷筛选（年份 / 地区 / 卷别）**（`plans/C3_试卷筛选_交付记录_v1.md`）。资料管理页「类型=试卷」时多出三个下拉，支持 `?type=paper&year=2019&region=BJ&book_kind=T` 深链。后端 `admin_list` 新增 `paper_year/region/book_kind`，口径与预览一致（`paper_meta` 订正 > 文件名解析），**带试卷筛选时非试卷类一律排除**；因两种元数据来源 SQL 表达不了，改为「SQL 预筛 + Python 精筛 + 手动分页」（百级数据可接受，>5000 条应改落库列+索引）。**实测**：3 套试卷里 `year=2019`→125、`year=2017`→126、`region=BJ`→125、`region=江苏`→126、`year=2019+region=BJ`→1、`year=2020`→0。**自查出的坑**：前端 `fetchAdminMaterialList` 手工拼参数，只加了类型没加进 params → 筛选不生效（三处必须同改）。pytest **11 新增 / 74 回归**、vitest **56 文件 619 用例**、typecheck 0、gate 9/10。截图 `C3_01_试卷筛选.png`
- 2026-11-08：**C 批第二轮验收缺陷修复：确认框被压在对话框下面**（`plans/C批验收反馈修复记录_v1.md` 缺陷 3）。根因是两套浮层各算各的：管理端自绘浮层 3000/3100，而 Element Plus 弹层**从 2000 起算**，且 `ElMessageBoxOptions`（2.13.7）**没有 `zIndex`** 选项 → 弹窗里的确认框必然在下面。修法：`main.ts` 在 mount 前 `provideGlobalConfig({ zIndex: 5000 }, app)` 抬高整族 EP 浮层；新增 `utils/overlay.ts` 集中定义层级（OVERLAY_Z/DIALOG_Z/EP_Z）并提供 `confirmOverlay()`/`notify()`，改信息、资料管理页、预览抽屉全部切过去。**真机验证**：`.mmd-root=3100`、`.el-overlay=5002`、`elementFromPoint(确认框中心)=.el-message-box`。vitest **56 文件 613 用例**（新增 overlay 3 例不变量）、typecheck 0、gate 9/10。截图 `C2b_03_确认框在弹窗之上.png`
- 2026-11-08：**C1 讲义大纲（章节树 + 字数）+ 删原件**（`plans/C1_讲义大纲与删原件_交付记录_v1.md`）。①`services/doc_outline.py` 从 docx 抽 `{字数, 章节数, chapters[]}`（Heading 样式优先，无样式退识别「第X章/第X节/一、」，都没有就只给字数不编目录），存 `study_material.doc_meta`（启动期自动补列）；上传/导入落档后自动抽，存量用 `scripts/backfill_doc_outline.py` 回填（已回填 5 条）；列表讲义行显示「3 章 · 120 字」，抽屉「章节（N）· 共 M 字」两级目录 + 元信息加字数。②`DELETE /admin/{material_id}/files/{file_id}` + 「改信息」原件行「删除」（二次确认）：只删登记行，同一 sha256 无其他引用才删物理文件。**实测**：121 = 3 章 120 字、目录 `第一章/1.1 传唤/1.1.1 要件`；删原件后 `physical_deleted=true` 且磁盘文件消失。**两个坑**：正则 `\b?` 触发 PatternError；「第X节」被「第X章」分支吃掉（单测抓到）。pytest **17 新增 / 138 回归**、vitest **55 文件 610 用例**、typecheck 0、gate 9/10。截图 `C1_01_讲义目录与字数.png`、`C1_02_改信息_删原件入口.png`
- 2026-11-08：**C 批验收反馈修复（2 个缺陷）**（`plans/C批验收反馈修复记录_v1.md`）。①**C2a 上传后试卷没编号**：`paper_code` 之前只在 C4 补录与 C2b 改信息时生成，**B2 上传端点漏了调用解析器** → 上传 `2024国考·公专题本.docx` 生成的 material 127 编号为空。已在上传建资料时按文件名解析并同时写 `paper_code`/`badge`（解析不出仍留空）；127 已用 PATCH 补成 `GZ-2024-GK-T`。新增 3 例 pytest。②**红字只有「保存失败」**：`apiClient` 的 rejection 是**普通对象不是 Error**，`e instanceof Error` 恒 false → 兜底文案吞掉了后端原因。新增 `utils/apiError.errorMessage()`（兼容 Error/归一化对象/后端原始体/details/字符串），替换 5 个文件里 9 处 `instanceof Error` 判断；真机验证 400 文案现在完整显示「year 需在 1990–2100 之间，收到 1800」。pytest **121 passed**、vitest **54 文件 605 用例**、typecheck 0、gate 9/10。截图 `C2b_02_错误原因显示具体文案.png`
- 2026-11-08：**C2b「改信息」弹窗 + `PATCH /admin/{id}/meta`**（`plans/C2b_改信息弹窗_交付记录_v1.md`）。列表「改信息」不再是灰的：①`study_material.paper_meta`（JSON，启动期自动补列）存**人工订正**；②`services/paper_meta_edit.py` 字段白名单 + 范围校验（年份 1990–2100、题量 1–500、总分 0.5–1000、时长 1–600）+ 地区/卷别枚举 + 编号自动生成；③预览 `paper` 改**三级合并**（订正 > 文件名解析 > 可作答卷）并新增 `source`（edit/exam）与 `override`（表单回填只用订正值，避免把解析结果固化）；④`POST /admin/files/upload` 带 `material_id` 时，资料**还没有原件**则落 `primary` → 这就是给 2 套真题补原卷的入口；⑤`MaterialMetaDialog.vue` 三列表单 + 试卷区块 + 上传原件。**实测**：material 126 订正 120 题/120 分/150 分钟 → `source=edit`、编号 `GZ-2017-JS-T` 不变、关联不断；非法年份与未知地区均 400；`paper_meta_reset` 回退到 `exam`。pytest **16 新增 / 150 回归**、vitest **53 文件 599 用例**、typecheck 0、gate 9/10。截图 `C2b_01_改信息弹窗.png`
- 2026-11-08：**C2/C4 试卷元数据 + 反向补录 + 编号关联**（`plans/C2C4_试卷元数据与编号关联_交付记录_v1.md`）。你上传的 **2 套真实公专真题**（2019 北京 / 2017 江苏，各 100 题、已发布）原来只在题库、资料库 `type=paper` 是 0 条 → 现在补录成资料：①`services/paper_meta_parser.py` 文件名解析（年份/地区/科目/题本或答案/卷别 → 人读编号 `GZ-2019-BJ-T`，**缺项不生成**）；②`study_material.paper_code` 列（启动期自动补列 + 索引）；③`services/paper_backfill.py` + `POST /api/materials/admin/papers/backfill`（**默认 dry-run、幂等**，两侧 `paper_code` 相等即关联）；④预览 `paper` 区块 + 抽屉「试卷信息」+「已关联 · 可考 / 未发布 / 题库没有」三态。**实测**：material **#125/#126**，`GZ-2019-BJ-T`/`GZ-2017-JS-T`，100 题/100 分/120 分钟，`answerable=true`；`?type=paper` 出 2 条；复跑全 skip。**两个坑**：`total_score` 是 Decimal（不转 float 会 500）；`library` 直接 import `ExamPaper` 被 L4 模块边界门禁拦 → 收敛到 `services/paper_registry.py`（基线仍只有 1 条历史违规）。pytest **28 新增/134 回归**、vitest **593**、typecheck 0、gate 9/10。截图 `C2C4_01_试卷列表与信息.png`
- 2026-11-12（夜 5）：**OCR P2（文章/讲义扫描件）方案已出，待批准**（`plans/扫描件OCR_P2_文章讲义_方案_v1.md`，未写业务代码）。**审计抓到 3 个硬点**：①扫描分支现在走不存在的 `C:\mineru_env`（实测 MinerU 71.2s/页）；②`material_import_record` **没有进度列**，前端只能显示"解析中"；③前端 `ArticleBatchUpload` **180 秒就判超时**，而 24 页扫描件要 **3.4–6.6 分钟** → 现在就算接了 OCR，界面也会先报超时。**PoC 实测**（河南 17 页扫描件前 2 页）：**35.3s / 16.5s 每页 / 3542 字 / 64 段**，重排后标题、题号、正文各自成段（贴了真实样例）。**设计**：复用 P1 sidecar（不装新东西）+ 新增纯函数 `services/ocr_html.py`（去页眉页脚 / 断行合并 / 按句断段 / HTML 转义）+ 进度塞 `parse_result._ocr`（**零迁移**）+ `status` 回包加 `progress`（**零新端点**）+ 前端等待 30 分钟并显示「OCR 12/24 页 · 已用 1:36」+ 部分失败成文并标注 + 60 页/30 分钟上限 + 惰性超时兜底 + `OCR_ENGINE=sidecar\|mineru` 可切回。**T1–T7 ≈1.9 天**，DoD 明确（真实 24 页件走通全链路、≥13 后端例 + ≥3 前端例、gate 仍 9/10）。**待拍板 D1–D6**（重排强度/页图/上限/部分失败/并发/僵尸记录），默认全按建议。附真机现状图 + 预期效果标注图 `assets/扫描件OCR_P2/`
- 2026-11-12（夜 4）：**S4 交付：旧版资料页路由已下线，方案 B 全链路完成**。`src/router/index.ts` 删 `materials/legacy` 路由（`.vtj/vue/admin_materials.vue` 按 R1 **一字未动**，只是不再挂路由，注释里写了怎么临时找回）；门禁双改点同步 `EXPECTED_DYNAMIC_IMPORTS` **105→104** + `test_route_roles` **105→104**。验证：L6「104 处 import 均存在」通过、L7 **5 passed**、真机 `#/admin/materials/legacy` → **404 页面未找到**、`gate_all` **9/10**（唯一红=既有 L1-G 语料下限）。**踩到并记录一个环境坑**：`gate_all` 的 L4 默认探 `127.0.0.1:8000`（本机 8000 是另一套 openapi 24 条路径的服务），首跑误报「缺 7 个 `/api/questions/import/*` 端点」；带 `OPENAPI_URL=http://127.0.0.1:8001/openapi.json` 重跑即 PASS —— 本机跑门禁必须带这个变量。遗留：死文件按 R1 保留；视频分片上传随旧页下线（全库 0 条，D2=A）；`gen_module_ledger --check` 的漂移属既有问题（357 vs 343），未混进本次提交
- 2026-11-12（夜 3）：**S2 交付：手写资料（富文本正文 / 卡片正反面）已搬进新版页**（方案 B 第二步，只差 S4 删路由）。新增 `utils/materialEditor.ts`（纯函数 + 8 例单测：类型块切换、校验、payload 字段隔离——卡片只带正/背/封面、文章只带正文/摘要、编辑不带 type）+ `components/admin/MaterialEditorDialog.vue`（wangeditor 富文本 + 插图上传 + 卡片正/背/封面 + 保存即未上架）；`api.ts` 增 `createMaterial/updateMaterial/uploadMaterialImage`（**无新端点**）；页头「＋ 新建资料」、行内「改正文」/「改内容」。**顺手修掉旧页的误报根因**：`editDlg` 与 `form.type` 双 watcher 在 `await import('wangeditor')` 前都通过了去重判断 → 第二次 create 抛「初始化节点已存在编辑器实例」；新组件单入口 + `mounting` 锁，实测无警告。真机 CDP：新建文章 → 库 `#138 article status=0 content 38 字`；改正文 → 预填 + 追加 → 54 字；卡片模式显示正/背/封面。探针已验证后删除（备份后删，integrity ok）。`vue-tsc` 0；全量 **66 文件 / 723 用例全绿**。记录见 `plans/旧版资料页_覆盖度审计与清理方案_v1.md` §11
- 2026-11-12（夜 2）：**S3 交付：xlsx 卡片智能导入已搬进新版资料管理页**（方案 B 第一步）。新增 `utils/cardXlsx.ts`（列映射纯函数，8 例单测）+ `components/admin/CardXlsxImportDialog.vue`（选表 → 预览表头/前 5 行（正面列绿、背面列蓝）→ 自动猜列映射可改 → 科目/兜底分类/立即上架 → 结果面板含跳过行与分类考点回退警告）；`api.ts` 新增 `fetchMaterialImportPreview`、`confirmMaterialImport` 支持 `type:'card'` + `column_mapping`；页头加「卡片导入（xlsx）」。**零后端改动**（四个端点本来就是旧页在用）。真机 CDP 全链路：2 行测试表 → 预览 2 行 / 自动映射 front=0,back=1,category=2,point=3 → **确认入库 created=2（未上架）**，验证后连探针带导入记录一起删净（先 `sqlite3.backup()`，`integrity ok`）。修掉 3 个坑：警告文案「undefined」（两套 warning 形状都认）、确认后自动关窗看不到结果、dev 代理默认指 8000 需 `DEV_BACKEND_ORIGIN=8001`。**顺带修一条既有红测试**：`AnswerDraftDrawer.spec` 的「确认写入 2 题」是 11-12 早间改口径前的旧断言（现口径=会写入的题数），改后全量 **65 文件 / 715 用例全绿**；`vue-tsc` 0。记录见 `plans/旧版资料页_覆盖度审计与清理方案_v1.md` §10
- 2026-11-12（夜）：**OCR P1 交付：扫描版答案 PDF 能直接出草稿了**。新增 `services/ocr_sidecar.py`（子进程 + JSONL + 单页 60s/总 30 分钟/60 页上限，失败带页号）+ `scripts/ocr/rapidocr_worker.py`（跑在 `C:\ocr-env`，不落临时图）+ 8 例测试；`answer_ingest.read_text_of()` 只加一条分支（**PDF 文字层为空才走 OCR**），草稿 message 写明「扫描件已 OCR 3/3 页（28.1s，200dpi），识别文字请逐题核对」；`extractor.py` 答案字母改**大小写不敏感**（OCR 会出 `c项错误`，L3 排除前先归一）。**0 端点 / 0 表 / 0 迁移**，主环境零新增依赖。真机：24 页扫描件裁 3 页 → `POST .../answers/parse` **HTTP 200 / 29.9s / 13 题全中（L1）**，草稿用完即删（discarded，不留 pending）。差异如实记在 §9.6.3：**逐页进度没做**（要异步任务/新端点，守 R11 → 排 P4）。P2（文章/讲义）、P3（试卷导题）待批
- 2026-11-12（晚）：**OCR P0 已执行通过 + 旧版资料页入口已摘**。①**OCR P0**：装好 `C:\ocr-env`（**仓库外**；py3.11.15 + rapidocr-onnxruntime 1.4.4 + onnxruntime 1.31.1 + PyMuPDF 1.26.4，**287MB**，模型随包自带不联网）。拿你那份 **24 页扫描答案件**跑前 3 页：**25.8s（8.6s/页）**、3959 字、题号 **13/13** 命中、平均置信度 **0.989–0.994**；**现成答案抽取器直接吃 OCR 文本 → 13 题块 13 条答案（L1×12 + L2×1，0 漏 0 错位）**，即"扫描件→答案草稿"不用新写解析器。已知缺陷：错字「要看眼于/驾车外出玩」、`c项错误` **大小写混**（P1 必做大小写不敏感）、按栏宽硬换行。24 页外推 **≈3.4 分钟**（比预估 2 分钟慢，因双栏小字）。**未改任何业务代码**，结果与 P1 范围见 `plans/扫描件OCR能力_方案_v1.md` §9。②**旧版资料页入口已摘（你选的 A）**：`src/views/admin/materials.vue` 删掉页头「旧版（临时）」链接，**路由未删（105 不变）**→ L6 与 `test_route_roles` 零影响；CDP 实测 `hasLegacyLink=false`、`vue-tsc` **0 error**；旧页仍可直达 `#/admin/materials/legacy`（合 R1）；截图 `assets/旧版入口摘除/01_新版页不再有旧版入口.png`；执行记录见 `plans/旧版资料页_覆盖度审计与清理方案_v1.md` §8。③S2（搬「＋新建资料」）/S3（搬「xlsx 智能导入」）/S4（删路由 + 105→104 双改点）**待批**
- 2026-11-12：**扫描件 OCR 方案 + 旧版页审计 + 资料上传指南**（三份新文档）。①`扫描件OCR能力_方案_v1.md`（**待批准**）：扫描件报错的真因是**本机没有任何 OCR 引擎**（`C:\mineru_env`、`D:\ocr-env` 都不存在，主环境无 paddle/onnxruntime/rapidocr，tesseract 未装，easyocr 有包但模型目录空且 jaided.ai/github 不可达，Docker 无 OCR 服务）；实测你那份扫描件 **24 页、0 字**，文字版对照 15 页每页 ~2000 字；选型 **RapidOCR sidecar**（≈4.6s/页，24 页≈2 分钟）对比 MinerU（71.2s/页，≈28 分钟）；方案是 PyMuPDF 渲染→子进程 OCR→回给答案/文章/试卷四条链路，不新增端点与表；**P0 需批准装 venv**。②`旧版资料页_覆盖度审计与清理方案_v1.md`（**待批准**）：旧版**未被完全覆盖**，仍有 4 项独有能力（xlsx 卡片智能导入、＋新建资料[富文本/封面/视频]、视频分片上传、卡片图片上传）；受 R1/R3/R11 限制**不能删 `.vtj` 页面也不能删接口**，只能下线入口（删路由要改 L6 105→104 双改点）；三方案 A 摘入口 / B 摘入口+删路由 / **C 先搬迁再下线（推荐）**。③`资料上传指南_v1.md`（**已整理**）：5 类文件 + 1 类答案的入口/格式/限额/流程/报错处理/库快照，含"扫描件暂不支持、讲义正文未入库"两处如实说明
- 2026-11-12：**补答案「上传后显示 0 题」已修复**（`plans/补答案上传后显示0题_缺陷修复方案_v1.md`，含交付记录）。你上传 `题库\答案解析（不用打印）` 里的 2016 江西答案 PDF，提示「已解析 97 题」但抽屉 `识别答案 0/0`、表格空、按钮「确认写入 0 题」。**根因**：`POST /answers/parse` 回包走 `draft_payload(db, draft)`（`with_items` 默认 False）**不带 `items`**，而 `/latest`、`/drafts/{id}` 都带；前端 `upload()` 只读 `data.items` → 空。**修法**：①parse 回包 `with_items=True` + `can_edit`（与 `/latest` 同形）；②前端无 `items` 时按 `draft_id` 补拉 `fetchAnswerDraft`；③新增 `utils/answerDraft.ts` 把"识别题数"与"将写入题数"拆开——按钮改「确认写入 X 题」，X=0 时**禁用**并说明原因（一致 / 不同但未勾覆盖 / 没解析出答案）；④空表文案区分"没有待确认"与"没有可显示的题"。**验证**：后端 3 + 前端 8 新例、相关回归 **75 passed**、`vue-tsc` 0；真机同一份 PDF → **97 行**、按钮「确认写入 0 题」禁用、提示「97 题与现有答案一致，无需写入」（截图 `assets/补答案修复/`）。解析本身没错：那 97 条答案与库里 **97/97 一致**（11-09 已写入过），所以本该"写 0、保留 97"
- 2026-11-12：**补答案「上传后显示 0 题」缺陷方案（待批准）**（`plans/补答案上传后显示0题_缺陷修复方案_v1.md`）。你上传 `题库\答案解析（不用打印）` 里的 2016 江西答案 PDF，提示「已解析 97 题」但抽屉 `识别答案 0/0`、表格空、按钮「确认写入 0 题」。**是缺陷，且从 P4 上线就存在**：`POST /answers/parse` 的回包走 `draft_payload(db, draft)`（`with_items` 默认 False）**不带 `items`**，而 `/latest`、`/drafts/{id}` 都带；前端 `upload()` 只读 `data.items` → 空。**关掉抽屉重开**走 `/latest` 就正常（CDP 实测：识别 97/97、97 行、按钮 97；截图 `assets/答案上传_实际效果/02_补答案_重开抽屉_97行.png`）。解析本身没错：draft #7 的 97 条 `answer` 齐全，且与库里 `current` **97/97 一致**（11-09 已写入过），所以就算修好，这份 PDF 实际会"写 0、保留 97"。**次要缺陷**：按钮数字按"有答案的题数"算，不是"会写入的题数"。修法：parse 回包带 items（+ 前端兜底 `fetchAnswerDraft`）、拆 `writableCount`（0 时禁用并说明）、空表文案区分；测试 3 后端 + 2 前端 + 1 真机；工期 ≈1.2h
- 2026-11-12：**已批准效果图总览（37 张方案图，两张拼图）**（`plans/已批准效果图_总览_v1.md`）。从 `assets/` **55 个主题目录 / 382 张图**里挑出**方案期效果图 37 张**：**已批准 24 张（7 主题）**——资料管理 v3(7)、管理端画风(5)、资料库 L2(1)、手机双 tab(1)、答案上传(1)、P5 联动(4)、考试开关+定时(5)，每条都写清方案/裁定依据与落地状态；**未批准 13 张（4 主题）**——教师端待审稿徽标（**落点未拍板**，两套方案）、资料下发（待批准）、AI 讲师知识供给（待批+暂停）、**资料多格式导入 P0（已实施但方案文档仍标"待批准"，流程缺口，本次核对才发现）**。拼图 `assets/效果图总览/01_已批准的方案效果图.png`、`02_待批准与未拍板.png`（真实渲染，缩略图顶部裁切）；实测/验收图 345 张按主题列目录，不混进效果图
- 2026-11-12：**11-05 以来工作盘点 v1.2（三项静默错并入）**（`plans/11月5日以来工作盘点与缺陷复核_v1.md`）。①§3 **仍开放 11 → 8 项**（去重盲区 / 文章批量上架 / 模考错题本移入 §5，编号保留 1/2/5/7/8/9/10/11）；②§4 新发现 **N1/N2/N3 标已修、N4/N5 仍开放**；③§5 已闭环 **10 → 11 组**；④提交 **117 → 119**、文档 **84 → 85**；⑤服务 revision **`d27369a`**（19:2x 重启）；⑥数据：`content_hash` 空 **98 → 5**（无正文行）、资料 **124**（回收站 5，含去重探针 #129 已软删）、活行重复哈希 0 组、`integrity ok`；⑦新增 §11.2「v1.1 → v1.2」9 条差异
- 2026-11-12：**三条「静默错」已修**（`plans/三条静默错_修复方案与交付记录_v1.md`）。**①模考错题不进错题本**：根因是 session `autoflush=False`，交卷代码在 commit 前重查刚 `add` 的明细 → 恒 `None`（`wrong_question_personal` 一直 0 行）；改为遍历内存 `created_details`、只收"答错且作答"（空白不算错题）。**②老资料去重失效**：98 条 `content_hash` 为 NULL + 7 条老卡片哈希与当前口径不一致；新增回填/归一脚本（先备份、幂等、integrity）与"只扫 NULL 行"的去重兜底；实测 93 条回填 + 7 条重算，NULL 只剩 5 条无正文行；端到端复验：拿 #4 同内容新建 → **409「与已有资料 #4 内容重复」**。**③文章批量没有「立即上架」**：后端文档分支写死 `status=0`（`publish` 只对 xlsx 生效）且回包谎报 `published`；改为 `status=(1 if publish else 0)`，前端加勾选（默认关、文案随勾选变、confirm 带 `publish`）。验证：新增 **10 passed**、合计 **67 passed**、`vue-tsc` 0、文章弹层真机勾选截图
- 2026-11-12：**11-05 以来工作盘点 v1.1 复核更新**（`plans/11月5日以来工作盘点与缺陷复核_v1.md`）。不是改字，是**逐条重跑证据**：①提交数 116 → **117**；②已闭环 9 → **10 组**（并入当天的考试开关修复 `f2f5d2d`）；③§3 的 **11 项仍开放逐条复跑、状态无变化**（4 处直写 `PUBLISHED` 仍在、`_require_admin` 仍在、`ArticleBatchUpload` 里 `publish` 命中 0、`mobile_answer.vue:805` 仍跳 `/paper-result`、`exams.py` 无错题写入且 `wrong_question_personal=0`、去重仍只比 `content_hash`、`batch-meta` 端点不存在、题量 397 < 3085）；④服务 revision 更新为 **`f2f5d2d`**（17:42 重启）；⑤数据 17:45 快照：5 张卷 `exam_open=1`、窗口全空、`exam_record=4`、`exam_answer_detail=388`、`content_hash` 空 98、`integrity ok`；⑥新增 §11「v1 → v1.1 更新记录」8 条差异，可直接看出改了什么
- 2026-11-12：**考试开关「点一下卡死」已修复**（方案 `plans/考试开关点击后卡死_缺陷修复方案_v1.md`，交付记录 `plans/考试开关点击后卡死_交付记录_v1.md`）。你反馈「点开关后显示已关闭但按钮没滑回去、再也打不开、设置定时也没用」。**真机 CDP 复现 4 步**（`_run/repro_exam_switch.js`）：点 1 下 → 标签变「已关闭」但 class 仍 `is-on`、副文案仍「手动开启」；点第 2 下 → 仍「已关闭」；设 20:00–22:00 → toast「已保存考试时间」、副文案变 `20:00-22:00 定时`，但标签仍「已关闭」。**根因**：写端点 `PUT /admin/{id}/exam-open` 与 `/exam-window` 返回 `contract.exam_state()`，比列表的 `exam_gate.state_of()` **少 `manual_open/paper_code/paper_id`**（实测回包键对比），前端 `row.exam = state` 整体替换 → `manual_open=undefined` → `is-on` 恒真、`nextOpen` 恒假（永远发关闭）、副文案/aria 同错；定时本身能用，卡在手动闸打不开。**修法**：后端 `exam_gate._enrich()` 单一真源（`state_of/set_open/set_window` 三处共用），写端点回包与列表**同形**；前端 `examSwitchOn/nextExamOpen/mergeExamState` + `onExamWindowSaved` 合并（优先级 回包 > 本次意图 > closed > 上一份）。**验证**：真机 5 态（关→灰/已关闭/已手动关闭；再点→开/可进入；设定时→未开始/20:00-22:00；清空→可进入）+ 5 张截图（`assets/考试开关修复/`）；后端 22 passed、相关回归 38 passed、前端 23 passed、`vue-tsc` 0、`gate_all` 9/10（仅既有 L1-G）。数据：5 张卷全部 `exam_open=1`、窗口清空、`integrity ok`
- 2026-11-12：**11 月 5 日以来工作盘点 + 逐项缺陷复核 + AI 讲师方案汇报**（`plans/11月5日以来工作盘点与缺陷复核_v1.md`）。**盘点**：`feat/material-multi-format-import` 自 11-05 起 **116 个提交 / 84 份新文档**，按六段（11-05 方案日 → 11-06 裁定 → 11-07 A+B 批 → 11-08 C 批+P5+真卷 → 11-09 L/P/W 线 → 11-10~12 考试收口与页面细节）逐项列到提交号。**复核方式不是复述历史**：按当前代码行号、当前库、真机接口回包重新判定——**仍开放 11 项**（4 处直写 `PUBLISHED` 的反向漂移、教师不能上传、去重对 98 条 `content_hash` 为空的老资料失效、文章批量无「立即上架」、手机结果页仍是 PC 页、模考错题不进错题本、批量改信息、L1-G 9/10、分批补录题序错位、验收账号 4/5 次机会、回收站 4 条 + 卷 #1 脏行）、**本轮新发现 5 条**、**已闭环 10 组**（含 11-12 开关卡死）。**AI 讲师**一次讲清：讲稿 DSL `lecture/1.0`（6 段类型/7 动作/5 表情/5 场景）、微课 7 段式与桐哥四步对照、1080p+96px 安全边距、播放器 8 态状态机、三层键 87 知识点/12 topic/403 考点（实测 8/12 试点在知识点层无节点）、`lecture_source.json` 契约与 `--check` 防漂移、T0–T10（T10 转写试点已完成 rtf 0.672）、交底书 B 三组权利要求、能力边界（抽帧读图已跑通、112.6h≈76h CPU 转写、`LLM_API_KEY` 空、生产题库不在本机、网课版权）与 **D1–D6 待拍板**。附取证命令与实测坑（**pytest 必须从 `backend/` 跑**：从仓库根跑相对路径 DB 直接 42 errors）。数据侧：14:17 有人把 4 套卷考试开关关掉（日志为真实 HTTP 调用），已备份 `bak_pre_restore_examopen_20261112_142334` 后恢复为「开」，真机复核 4 套 `ready=True`
- 2026-11-13（夜）：**三件事按「按建议」全部交付（P4 补答案扫描件 / 41 页整卷验收 / P3 界面验收清单）**。①**P4**：`pdf_text_layer_empty` 判扫描 → `create_answer_draft`+`fill_answer_draft` → `answers/parse` **403ms 返回 `parsing`**，进度写 `message`（零迁移）、幂等、40 分钟惰性超时、弃稿不被救活；抽屉加「扫描件 OCR」角标 + `OCR x/43 页` 进度 + 「答案字母可能认错」黄条 + 解析中置灰。真机 43 页扫描答案件（26.79MB）→ 冷 **240.9s** / 热 **144.9s** → **94 题**（有答案 92），验完即弃、题库零变化。②**41 页整卷**：**发现并修掉真问题**——真卷 56.97MB > 原 20MB 上限，**今天根本传不进去**；改成按类型上限（PDF 60MB）+ >8MB **流式落盘**（`_spool_upload`，峰值内存与文件大小无关）→ 上传 **0.9s**、导题 **47ms**、OCR **240.6s（5.9s/页）** → **114 题**（四选项齐全 72）、题号 1–125 缺 32（三位数 101–112 整段丢）、警告 7 条；长任务期间旁路接口 6 次全 200（18–84ms）。③**P3 验收清单** 4 步 + 两份可点探针（41 页看进度、5 页看清单），用「放弃草稿」零写库。**同时纠正自己测错的数**：「22.8s/页 → 15.6 分钟」是与 pytest 并发时测的，被抢占放大 4 倍，干净实测 **4 分钟量级**（效果图已按实测重画）。验收：P4 测试 **7 passed**、`-k "upload or material or answer"` **509 passed**、后端全量 **1617 passed / 6 failed（均为既有环境失败，清单与 11-09 交付记录一致）**、前端 **68 文件 736 用例**、`vue-tsc` 0、`gate_all` 9/10。**诚实结论**：机制全通，整卷拆题质量只够当草稿（63% 四选项齐全），后续专项建议见方案 §11
- 2026-11-13（傍晚）：**下一步三件事方案（P4 补答案扫描件 / 41 页整卷验收 / P3 界面验收清单）已出，待批准**。按你的要求「先出预期效果图」：`docs/plans/P4补答案扫描件与整卷验收_方案_v1.md` + 3 张图（`assets/P4与整卷验收/`：补答案抽屉 3 处新增/1 处置灰、41 页时间线 15.6 分钟与双阈值余量、P3 验收 4 步路线）。**本轮新量出来的两个硬事实**：①答案扫描件 5 份（24/27/20/41/43 页，1.2–26.8MB）都在 30MB 内，但「补答案」是同步 OCR → 每次要卡 **4–7 分钟**；②**41 页真卷 56.97MB > 上传上限 20MB，今天连 UI 都传不进去**（这是验收的拦路石，也是真实用户会撞的缺陷）。方案给了按类型上限（PDF 60MB）等 4 条待确认项，全部默认按建议
- 2026-11-13（下午）：**P3 交付：扫描试卷能直接导题了（异步 OCR + 进度 + 逐题核对）**。`read_pdf` 先 `parse_pdf_once` 判扫描 → `read_pdf_ocr()`（复用 S-C 常驻 OCR，`images=[]`，>60 页截断）→ 同一套 `split_questions`；草稿新增 `parsing` 态，`POST /admin/{id}/parse` **0.14s 返回**、OCR 在后台跑、进度写 `draft.message`（**零迁移**）、40 分钟惰性判失败、**重复点击幂等**（返回同一份草稿，不起第二个 OCR）；前端抽屉 2.5s 轮询显示 `OCR x/y 页`，完成后同一张表逐题改。**真机（真实 41 页扫描试卷取前 5 页）**：`OCR 1/5→5/5` → **114.0s（22.8s/页）** → **19 题 / 四选项齐全 15**，警告如实报「缺号 [6]」「选项不全 [3,9,17,20]」。**真机暴露并修掉 4 个缺陷**：①页脚广告粘进选项行尾（「…武装全党 常加微信 txw1663 赠送最新」）→ 新增 `strip_inline_noise()` 按联系人/推广/扫码三种锚点切尾，并兜住 OCR 吞字后的裸号 `xwl663赠送最`；②`PAPER_NOISE` 的 `扫码` 会整行误杀正常题干（「A、扫码支付」）→ 收紧为「扫码+引导动作」；③解析中抽屉写「没有可显示的题目（可能都被过滤了）」→ 改为「扫描件正在 OCR…」；④双击「导题」会起两份 OCR、前一份白等 → 路由幂等。验收：P3 **9 passed**、`-k "paper or upload or import or material"` **550 passed / 0 failed**（**必须 `cd backend` 跑**）、`vue-tsc` 0、`gate_all` 9/10；探针资料与草稿已清、`study_material` 回 132、`orphan_count=0`、`integrity ok`。真机图 `docs/plans/assets/OCR_P3/03–05`。下一步：**P4 补答案扫描件**（可选）或 **AI 讲师/TTS 预生成（T9）**
- 2026-11-13（中午）：**O5 交付：上传即返回、解析转后台**。`import/upload` 只落盘+建记录+写指纹即返回 `processing`；新增 `_import_job` 统一解析 docx/xlsx/文字 PDF/扫描 PDF（扫描复用 S-C 常驻 OCR），进度写 `parse_result._progress`（OCR 另带页级 `_ocr`），`status` 优先读 `_progress`；去重口径扩为 `("consumed","success","processing")`（解析中也拦）；`IMPORT_INLINE=1` 供测试同步执行。前端进度文案按 `phase` 区分「解析中」/「OCR x/y 页」。**真机前后对照**：docx 响应 **91ms**（原同步 391ms）→ 0.7s 解析完；文字版 PDF 响应 **48ms**（原 143ms）→ 0.3s；扫描件 1 页响应 **23ms** → 30.9s（重启首篇含模型加载）。`pytest -k "import or article or material or ocr"` **497 passed / 4 skipped**、`vue-tsc` 0。**xlsx 未单独跑真机**（仓库无干净样本），由既有导入用例覆盖。下一步：**P3 试卷导题扫描件**
- 2026-11-13（上午）：**上传提速 S-A/S-B/S-C 全部交付（每批都有前后对照）**。①**S-A 单遍解析**：新增 `material_parser.parse_pdf_once()`（一次 pymupdf 同时判扫描+构建 HTML），上传改用它 → 17 页文字版 PDF 端到端 **4,132ms → 143ms（−96.5%，≈29×）**，扫描件仍正确转 OCR；与旧 `parse_pdf_text` 输出**逐字节等价**（5 例单测）。②**S-B 2 路并发**：`utils/concurrency.ts` + `ArticleBatchUpload` → 6 份 docx **1,615ms → 1,429ms（1.13×）**，如实记录"S-A 之后并发只剩 13% 收益（CPU+GIL）"，故 `MaterialBatchUpload` 不动。③**S-C OCR 常驻 worker**：`rapidocr_worker --serve` + `_Daemon`（复用/超时回收/崩溃重启/空闲 30 分钟回收）+ `OCR_MODE=daemon|oneshot` → 1 页扫描件 **17.6s（冷）→ 4.7s（热）**，每篇之后省 **12.9s（≈3.7×）**；新增 3 例常驻单测（同 pid 复用/崩溃重启/超时杀进程）。验收：`pytest` 24 passed、相关回归 **119 passed**、`vitest` **68 文件 / 735 用例**全绿、`vue-tsc` 0；探针全部删除、库回 132 行、`integrity ok`。O5（上传即返回）按 D4 暂不做
- 2026-11-13（早）：**OCR P2 交付（文章/讲义扫描件）+ 上传提速方案（待批）**。①**P2 按批准落地**：新增 `services/ocr_html.py`（去页眉页脚/断行合并/新块断段/超长切分/HTML 转义，10 例单测）+ `_ocr_sidecar_job`（后台 OCR → `<p>` 段落 → 回写，失败页号进 `_ocr.failed_pages`）+ 进度写 `parse_result._ocr`（**零迁移**）+ `status` 回包加 `progress`（**零新端点**）+ 40 分钟惰性超时（3 例）+ 前端等待 180s→**30 分钟**与「OCR 12/24 页 · 已用 1:36」（`ocrProgress.ts` 7 例）。**真机**：24 页扫描件 上传→进度 1/24→24/24 **272s** → `success`，**28,632 字 / 492 段 / html 32KB** → confirm 建未上架文章 → 探针删净（备份+integrity）；3 页界面链路截图「成功 · 已 OCR 3/3 页」，同文件重传仍 409。`pytest` 13 passed、`vitest` 67 文件 **730** 全绿、`vue-tsc` 0。②**上传提速方案**（未写代码）：实测文字版 PDF 17 页端到端 **4,132ms** vs docx **391ms**，拆解出 PDF 被**两次解析**（pdfplumber 3,102ms 只为判扫描 + pymupdf 911ms）→ O1 单遍解析 **4.1s→≈0.9s**、O3 OCR 常驻 worker 省掉每篇 **20–25s** 模型加载；D1–D4 待拍板
- 2026-11-13：**模块 4/7 全面升级方案 v1 归档（待批准，未实施）**。覆盖注册人物画像 7 条（询问页动画、动态问题+自由自述、方案首页/我的回显、3D 日历并入签到、番茄钟首页弹窗、遗忘曲线错题提醒、三端补齐）与联考小智 3 条（Obsidian 自生长知识库、知识图谱框架、三端补齐）。实测结论：后端画像/计划/签到/两套图谱/Obsidian 导出管线已具备，缺口主要在前端回显、体验动效、知识沉淀与三端适配；错题表缺 SM-2 字段、画像表缺自述字段；分 P0（已落地）–P5 六批，跨域项待与签到域、昕蕾对齐。方案 `superpowers/specs/模块4-7全面升级方案_v1.md`。
- 2026-11-13：**仓库文件全面只读扫描**。实测顶层体积（`.git` 946.6 MB / `node_modules` 708.3 MB / `backend` 608.9 MB / `题库` 497.3 MB / `docs` 65.6 MB）、2461 个业务文件类型分布、后端 `api/v1` 十子域与 foundation/core/services 分层、前端 20 模块 + `.vtj` 80 页（PC66/手机7/平板7）、Git 工作区改动；报告 `superpowers/specs/仓库文件全面扫描_报告_20261113.md`。11 项与基线偏差待复核，其中 pre-wipe 行测备份位置需人工确认，清理前一律不得动。
- 2026-11-13：**提取 dsh（大模型服务 Harness）侧砺安题库记忆**。覆盖 neuron 运行记忆、仓库内 switchman 交接（10 份 handover + tasks + artifacts）、`.memory` 跨会话档案三层；梳理出远端 `linxitie/li_an-question_bank` 与 socks5h 代理 7897、前端 9527/后端 8001（8000 WinError 10013 拒绑、5173/8000 为 svchost 假监听）、三套测试账号、模块4/7 十条改造进度（A3 注册建画像已三层验证、台账已刷新 25 模块/343 端点、A2 动态问题前端 12/12 断言通过，待 commit+push）、关键 file:line 定位与禁提交杂物清单；报告 `superpowers/specs/dsh项目记忆提取_报告_20261113.md`。dsh 记忆里的旧克隆路径、19999 端口、26 模块等过期口径已在报告 §6 标注漂移。
- 2026-11-14（夜）：**扫描件「缺行恢复」v1 已交付（S1–S4，按你「按建议，严格遵守全局规则」）**。你问的「第 9 题 OCR 直接跳过的缺陷能否解决」→ **能，已修好**。**根因再确认**：那一页行距中位数 60.1px，第 9 题 A/B/D 在 932.5/991.5/1111.7，**B→D 120.2px = 2.0×**，中间那行（C）被斜向水印压住，rapidocr **连框都不出** → 补标签（T3）与水印过滤（T2）都救不了"行不存在"。**四步**：①`find_holes()` 判洞（缺选项字母 + 间距 ≥1.6×中位行距，1/题·8/页·40/篇）；②worker 新增 `crop` 命令 + `ocr_sidecar.read_region_text()`，只把那道缝（±6px、整幅文字宽）按 **300dpi 原样**重跑（实验证明二值化/400dpi 会掉字）；③`merge()` 把回收行**原位插入**并两道去重（坐标 / 文本相似），补回行仍过水印几何判定；④`meta.ocr_retry` + 草稿体检一句「有 N 处整行漏检已局部重跑补回（第 9 题）」，`PAPER_OCR_RETRY=0` 一行关掉。**真机**：5 页探针 **四选项齐全 17/19 → 18/19**，#9 C=`小孙因个人原因拒绝所长安排的外出交流`（逐字），单条带 2.7s、行数 +1 无重复行；**41 页整卷**同机跑两遍：**题数 113 不变**、四选项齐全 **84 → 88**、判 14 洞补回 10 处（25.9s），**逐题只有 4 处变好、0 处变差**（题号 9/56/63/73）。**如实**：41 页里 6 处"补回了行但本题没变完整"（补回的是题干/图表行或页脚），#20 仍空（探针只裁 p1–p5，选项在 p6，属数据边界）。验收：新增 **18 例**、相关回归 **642 passed / 0 failed**、`gate_all` **9/10**（唯一红仍是既有 L1-G）。方案与预期效果图：`docs/plans/扫描件缺行恢复_方案_v1.md`、`assets/扫描件选项与水印加固/04_预期效果_第9题缺行回收.png`。**界面真机（13:10–13:12 重新导题 → draft #7，119s）**：抽屉里第 9 题 A/B/C/D 齐全、**没有「选项不全(C)」标签**，体检多一条「有 1 处整行漏检（水印遮挡）已局部重跑补回（第 9 题）」；**注意旧草稿是快照**——draft #6 生成于 11:05（本版代码上线前），代码修好后它不会自动变好，必须重新导题（或手工补那一格），这就是「代码已修、界面还是空」的唯一原因。图：`assets/扫描件缺行恢复/05_真机_第9题C已补回_抽屉.png`
- 2026-11-14（傍晚）：**扫描件选项与水印加固 v1 已交付（S1–S5，按你「按建议」）**。①**T1 坐标透传**：worker `ocr_page(with_layout=)` 回传 `text/x/y/w/h/score`，sidecar `read_pdf_text(with_layout=)` 把每页框放进 `meta["layout"]`（**默认关**，文章/答案链路零影响），常驻模式读 `with_layout`、一次性模式加 `--with-layout`。②**T2 水印几何过滤**：框高 > 2.5×本题行高中位数（实测水印 187/343px vs 正文 30–34）、孤立低置信小框（`X` 34×24 / 0.866）、≤8 字短词兜底 —— 先看几何后看字。③**T3 缩进补标签**：`splitter.repair_option_tags()` 用本题已有选项的 `x` 中位数当缩进带（实测 264 vs C 行 278，差 12–14px）按序补 C/D；页首无题号也成块。④**T4 结构校验**：某选项 >3×中位数且 >120 字 → 打「选项可能粘连」。**真机前后对照（同一份 5 页件，直跑管线、不动你的草稿）**：四选项齐全 **15/19 → 17/19**；**#3 的 C 回位、B 不再带「五星好」**；#1 D 去掉尾巴 `X`。**为什么不是 18/19（如实）**：#20 属跨页截断（探针只裁 5 页）；**#9 的 C 是 OCR 整行漏检**（同题 A/B/D 的 y=932.5/991.5/1111.7，B→D 间距 120px 缺一行；200dpi 与 300dpi 各跑一遍都没有「小孙」）—— 原图上斜向水印正压着该行，需「检测缺行 → 去水印/定向重跑」专项（≈0.3–0.5d，未做）。**按你「走 2」重新导题真机复验（material 139）**：draft #6、19 题、115s；**四选项齐全 17/19**、缺/空只剩 `[9, 20]`；**#3 四选项齐全（C 回位、B 无水印）、#1 的 D 已无 `X`**；体检提示从 4 条问题降为「缺号 [6] + 选项不全 2 题 [9,20]」。验收：新增 **10 例**、`-k "ocr or paper or splitter"` **207 passed / 0 failed**、`gate_all` 9/10。证据图：`assets/扫描件选项与水印加固/02_真机_第9题C行被水印遮挡.png`
- 2026-11-14（下午 · 方案）：**扫描件选项与水印识别加固 v1（待批准，未改代码）**。你指出第 3 题「选项本来没换行，C 却丢了」，并且要能辨别水印。**坐标级诊断**（`_run/diag_q3_ocr.py`，rapidocr 200dpi 原始 32 个文本框）：C 行是**独立水平一行**（`坚持以人民安全为宗旨`，x=278.4 / h=30.7 / score **0.9993**），只是**`C.` 标签被 OCR 吃掉**；而 `五星好`（h=**187.5**）、`xwl663赠送最`（h=**343.1**）、`X`（w=34 / score 0.866）是**斜向水印框**。根因三处：①`rapidocr_worker.ocr_page` 只回文本、**丢坐标与置信度**；②水印框按 (y,x) 混进正文流；③`splitter` 对无标签行**无条件当上一选项续行** → C 被并进 B、水印再并到尾巴。**修法**：S1 坐标透传（`with_layout`，默认不改变旧行为）+ S2 水印按「框高 > 2.5×行高中位数 / 孤立低置信小框 / ≤6 字短词兜底」过滤 + S3 用**选项缩进带**（实测差 12–14px）把丢标签的行按序补 C/D + S4 选项结构校验（不猜内容、加「可能粘连」标记）+ S5 `PAPER_OCR_LAYOUT=0` 可回滚。≈**0.9d**；预期 5 页探针四选项齐全 **15/19 → 18/19**（#20 属跨页截断，数据边界）。**待确认 D1/D2/D3**（是否按方案开工 / 补位策略 / 41 页图表页另立项），默认全按建议
- 2026-11-14（下午 · 对照）：**探针来源与页码对照表（供你对照验收）**。两份探针同出 `题库/公安题目（打印）/2025多省联考公安《公安专业》.pdf`（41 页 56.97MB）：5 页探针 = 它的 **p1–p5**（页图**像素级一致**，已核对 5/5），41 页探针 = **整份**。**19 题**逐题页码已 OCR 比对出来（19/19 命中）；**重要发现**：41 页那份「114 条」**不是 114 道不同题**——实际只有 **93 个不同题号**、**16 组重复（多出 21 条）**、1–100 缺 **8 个**（6/27/45/46/58/86/87/92）、多出题号 **125**（解析编号被当题号），39 页有题、p16/p33 无题 → 结论：41 页只适合看「整卷自动拆题的边界」，**不建议直接入库**；要真用需先做题号识别 + 跨页选项合并专项。附 2 份 CSV（5 页 19 行 / 41 页 114 行，含每条题干前 40 字与标记），见 `docs/plans/验收对照/`
- 2026-11-14（下午）：**缺陷修复批次 P0+P1 完成（D1 / D2 / D3 / D4 / D9；D5 按你指示不做，D6–D8 待拍板）**。①**D2** P3 弃稿复活：`paper_ingest.fill_draft` 进门先判 `discarded`（与 P4 同款 3 行），探针反证「修前 pending/1 题 → 修后 discarded/0 题」，P3 测试 **10 passed**。②**D3** 文章/讲义导入限额：`_save_tmp` 从「20MB 一刀切」改为按扩展名（**PDF 60MB** / docx 20MB / xlsx 5MB）+ >8MB **流式写 + 边写边算 sha256**；真机 26.79MB 扫描 PDF → **200 / 653ms**（修前 400「文件超过 20MB 上限」）。③**D4** 答案上传：同样按扩展名取上限 + 流式落盘，不再整读内存；真机同一份 26.79MB 答案件 → **200 / 943ms、status=parsing**（验完即弃）。④**D1** 反向漂移护栏：`exam_gate._enrich` 补 `paper_type`，新增纯函数 `utils/materialDrift.ts`（ENDED 不参与），列表上架列渲染红标「上架不一致」+ 方向化 tooltip；**真机构造不一致并截图**（`04_真机_D1_漂移红标.png`），随后复原（`check_material_paper_drift.py` → drift 0）。⑤**D9** 文档口径：docstring 20MB→按类型、README **校准 5 行**过期状态、排查报告补 §10 修复记录。验证：新增后端 7 + P3 10、前端 5 例、相关回归 **585 passed / 0 failed**、前端全量 **69 文件 / 741 用例**、`vue-tsc` 0、`gate_all` 9/10。**未做**：D5（你指示）、D6 手机结果页（要新增路由）/D7 批量改信息（新端点）/D8 题序根治（动热路径）
- 2026-11-14（上午）：**已交付功能缺陷全面排查（不含 AI 讲师与未开工方案）→ 8 项缺陷 + 5 类环境债**。每条都在**当前代码**上重新定位行号、复跑回归/门禁、只读快照，不复述旧结论。**结论：无新的静默数据损坏**（`integrity ok`、孤儿 0、资料与卷逐条一致、题库 397 未变），但真缺陷仍在：**D1** 4 处仍直写 `PUBLISHED`（`papers.py:450`/`paper_generation.py:771`/`admin_approval.py:245`/`teacher.py:1383`）；**D2（今天用探针复现）** P3「放弃草稿」后后台任务把草稿**救活成 pending**（`paper_ingest/service.py:171`，探针断言 `缺陷复现：草稿被救活成 pending`；P4 同款已修，3 行可补齐）；**D3** 文章导入仍卡 20MB（`materials.py:3492`，与材料 PDF 60MB 不一致）；**D4** 答案上传仍整读内存 + 30MB（`:2487/:2490`）；**D8** 分批补录题序错位（追加模型）；产品缺口 **D5** 教师不能上传 / **D6** 手机结果页仍 PC 页 / **D7** 批量改信息未做；文档债 **D9** docstring 与 README 39 行状态过期。**建议批次**：P0（D2+D3+D9，**0.3d**，风险极低）、P1（D1 巡检护栏 0.4d）、P2 需你拍板。同时回答两问：**两份探针干什么**（41 页看真实质量/进度、5 页看 19 题+警告；今早 08:09 已有一次导题留下 114 题 pending 草稿）、**除 AI 讲师外未推进的既定任务 9 项**（试卷收敛接口层、教师上传、按班下发、规范 v2 机检、手机结果页、批量改信息、题序根治、画风 E1–E5、教师端待审稿徽标）。报告 + 2 图：`docs/plans/备考资料模块_已交付功能缺陷排查_v1.md`、`assets/备考资料缺陷排查/`
- 2026-11-15（深夜 · 导题缺号定位，你选的备选 A）：**Q1–Q5 已交付**。P1 之后整卷只剩 3 个缺号，但抽屉里仍只有一行字「题号缺号 3 个：[46, 86, 92]」，管理员得在 41 页 / 56.97MB 的 PDF 里自己翻。**交付**：①解析收尾把「仍缺号的页/坐标」写 `meta.qno_gaps` + `<draft_dir>/qno_gaps.json`（零迁移、原子写、无缺口删旧）；②**新端点** `GET …/parse-drafts/{id}/page-image?no=&dpi=&page=`（admin、PDF only、`resolve_abs_path` 防越界、JSON+base64、0–1 相对高亮框、6 个错误码 + `PAGE_NOT_ALLOWED`）；③抽屉把缺号渲染成可点 chips + 手写弹窗（原卷页 + 红框 + 上一题/下一题 + 看第 N 页 + Esc/←→）；④降级：旧草稿置灰不发请求、docx 不渲染 chips、原件已删给明确文案。**真机两次探针**（41 页原卷栅格化的扫描件）：p1–p17 先暴露 3 处缺陷 → **p30–p41（12 页）修复后** 26 题、缺号 `[86,92]`；sidecar `86 → page 6 + alt_page 7`，`page-image?no=86` 红框在页尾，`&page=7` 返回 `on_alt_page=true`。**三条修复**：①缺号下界 `min(nos)`（拆分上传不再报「缺号 1..43」）；②跨页缺口从「上一题最后一行」起算、主选上一题所在页 + `alt_page`；③`locate_qno_in_line()` 处理「的46.为提升…」半句起框，补回的行真正成为题号起点。**如实**：p1–p17 那次带缺陷的证据保留；备选页只给「提示范围」；86 仍会「补回提示 + 缺号清单」并存（已知残余）。验收：后端 **24 例**、前端 **8 例**、`vitest` **74 文件/770 用例**、`vue-tsc` 0、后端子集 **351 passed**、`gate_all` **9/10**（唯一红仍是既有 L1-G）、OpenAPI **461 → 462**、路由 105 不变；探针已清理（127/13/397/0）。方案：`docs/plans/导题缺号定位_方案_v1.md`（§12 交付记录）；图：`assets/备考资料缺陷排查/21_预期效果_缺号定位_点题号看原卷页.png`
- 2026-11-15（深夜 · P2 复核）：**结论「不立项、不修」，并更正我自己之前的错误判断**。我在 D6 交付时口头报过「手机端右侧有模板外壳（XMask）悬浮操作条压住成绩卡」，还列进了建议。这次按你要求先出方案，我先做了复核，结果**这条报错了**：①26 个 `/mobile` 路由逐个干净加载（390×844@2）→ **横向溢出 0、越界元素 0**；②`/mobile/home`、`/mobile/paper-result` 三点快照（0.9/2.1/3.5s）+ 全站 fixed/sticky 扫描 → 只有页面自己的 sticky 顶栏与 fixed 底部 tab 栏，**没有任何 action bar**；③1440×900 对照 → `x-mask` 容器在、里面**没有 actions 节点**（`#vtjLink` 0×0）；④**用 D6 那张图的完全相同参数重放 2 次，截图都是 290,082 B（与干净版同尺寸），图标不复现**；⑤唯一越界是 `/mobile/recruit` 的 2 个分类 tab，复核 `.tabs` `clientWidth 383 / scrollWidth 544 / maxScrollLeft 161` → **可横滑**，不是缺陷。**错在哪（如实）**：当时那两个 DOM 探针因 `-Out ""` 被 PowerShell 吞掉、参数整体左移（`deviceScaleFactor` 变 13000、宽变 844），测的不是正常视口，输出为空我没察觉，就把一张截图当成了结论。本报告**不含代码改动**，只归档复核方法与证据（`docs/plans/P2窄屏遮挡复核_报告_v1.md` + `assets/备考资料缺陷排查/20_复核_P2_窄屏体检结论.png`）；建议关闭 P2，下一步按你选的做 P3（D7 清空分类）或备选（导题缺号定位 / 分类条滚动条美化）
- 2026-11-15（深夜 · P1）：**题号缺号/重号治理已交付**（你回「按建议」：D1 先只读实验再合并 / D2 自动丢重复页 / D3 连 ① 文档一起改）。41 页整卷原来 **缺号 8 个 `[27,39,45,46,47,86,87,92]`、重号 5 组 `[1,4,79,80,98]`**。只读诊断（785.6s / 1244 行）把 6 类根因全部落到原卷坐标：**39 是我们自己的页过滤误丢的真题**（p11 被判 chart 整页丢，原图确有「39.公安机关的人民警察…」）；**27/45 原卷印的是「27在…」「45东江市…」，题号后没有分隔符**；**47/87 题号行整行没出框**；**1/4 是图内数字**（p28「1.12-2」楼层图、p12「4.小时以内数封定神」流程图串读）；**79/80 是影印重复页**（p32/p33 题号行 y、x、文本逐字相同）；**98 是题号行被拆成两框**。**交付**：①`page_kind()` 加「真题行」判定（图表页含真题就整页保留，假题号交给行级自洽）；②`guard_qno_starts()` 题号自洽（必须像题干 + 同号只认一次 + 分段重编号例外）；③`_dedup_pages()`（相邻页 Jaccard ≥0.95 丢后页）+ `merge_split_qno_rows()`（折行同号合并取长行）；④**缺号补回收** `find_number_holes()`（按缺号算 300dpi 条带，上限 12，`recover_into(holes=)` 只收本组缺号）；⑤**无分隔符题号** `QNO_LOOSE_RE`（仅在题号连续 +1~+3 窗口且未被占用时采纳，记 `qno_issues.loose`）；⑥被挡的假题号行**不丢字**（`split_options(body_from=)` 当正文）；⑦`meta.qno_issues` / `ocr_qno_retry` / `dedup_pages` / `merged_half_qno` + 体检 6 条 + `PAPER_QNO_GUARD=0` 回滚。**实测（同机同参数）**：缺号 **8 → 3 `[46,86,92]`**、重号 **5 → 0**、不同题号 **91 → 96**、四选项齐全 **87 → 88/96（91.7%）**、第 39 题**回来**、题号 125 仍然没有（改由自洽挡掉，不再靠牺牲真题换）；**5 页探针完全不变**（20 题/19 齐全/无任何处置）。**如实三条**：①候选题目数**仍是 96**（补回 5 条的同时清掉 5 条假题/重复题，方案里写的 ≥97 没达成，真正该看的是「不同题号 96 + 重号 0」）；②**39/47/87 题号回来但选项没回来**（39 的 A–D 原卷画在流程图里，47/87 条带只捞回题号行），草稿会标「选项不全」；③**46/86/92 连 300dpi 也捞不到**，体检点名交人工，不算修好。验收：新增 **31 例**（`test_ocr_qno_guard.py` 21 + `test_ocr_qno_recover.py` 10）、OCR 子集 **316 passed / 0 failed**、`gate_all` 9/10（唯一红仍是既有 L1-G）、OpenAPI 461 不变。方案与图：`docs/plans/P1题号缺号重号治理_方案_v1.md`、`assets/备考资料缺陷排查/17_预期效果_P1_题号缺号重号治理.png`、`18_证据_P1_根因4处原图.png`、`19_实测_P1_题号治理前后对照.png`；① 文档已补 §9 回归修正
- 2026-11-15（深夜 · 三缺陷第 3 项，**三项已全部完成**）：**D6 手机结果页已交付**。手机答完卷 `mobile_answer.vue:807` 直接 `router.replace('/paper-result')` → **落到 PC 结果页**（桌面版式）；390×844 真机视口实测：卷名折 **3 行**、「返回试卷列表」折 **3 行**、4 个 meta 挤成 2 行、没有手机顶栏/返回。**交付**：①新增手写页 `src/views/student/mobile/mobile_paper_result.vue`（顶栏 / 成绩卡 / 再考一次·查看错题·回首页 / 可折叠逐题回顾），**不新建 `.vtj` 页**（守 R1/R3）；②新路由 `/mobile/paper-result`（`meta.platform='mobile'`、`roles:['student']`），插在 `MobileAnswer` 之后；③交卷成功跳转改到新路由；④**口径零新增**：同一接口 `GET /api/exams/records/{id}` + 同一 `buildExamSummary()`，满分取记录里的 `max_score`（**不 `|| 100` 兜底**）；⑤路由计数 **104 → 105** 双点同步（`backend/tests/test_route_roles.py` + `scripts/verify-modularization-constraints.mjs`）。**真机（学生 202516001 / record 4，97 题卷）**：`2 / 97 分`、得分率 **2.06%**、用时 `00:17`、正确/错误 `2 / 95 题`、已答 `4 / 97`、未答 **93**（未答按错计）、答对率（按已答）**50%**；逐题回顾展开 **97 条**（2 ✓ / 95 ✗，第 97 条「你的答案：未答 · 正确答案：C」+ 解析）。**如实**：第一版成绩卡做成「答对 2 / 答错 95 / 未答 93」三个 chip，三项相加 **190 ≠ 97**（「错误」口径含未答，与「未答」重复计数）—— 真机截图当场发现，改成与 PC 结果页同款的 2×2 meta + 「已答 4/97 · 未答 93（未答按错计）」一行；「再考一次」**未在真机点击**（会新建考试记录，避免污染现有 4 条干净记录；代码走的是与 PC `retakeExam()` 相同的 `POST /api/exams/{id}/start`）。验收：前端新增 **4 例**（`mobilePaperResult.spec.ts`）、`vitest` **72 文件 / 762 用例** 全绿、`vue-tsc` **0**、`pytest tests/test_route_roles.py` **5 passed**（页面路由 **105**）、L6 通过（105 处动态 import 均存在）、`gate_all` **9/10**（唯一红仍是既有 L1-G：397 < 3085/3632）、OpenAPI **461 不变**（本项无新端点）。方案与图：`docs/plans/D6手机结果页_方案_v1.md`、`assets/备考资料缺陷排查/14_预期效果_D6_手机结果页.png`、`15_真机_D6_手机结果页.png`、`16_真机_D6_逐题回顾.png`
- 2026-11-15（深夜 · 三缺陷第 2 项）：**D7 批量改信息已交付**。列表早有"勾选 + 批量上架/下架/删除"，但没有批量改信息 —— 38 份卡片统一改科目只能逐条点「改信息」。**交付**：①新端点 `PATCH /api/materials/admin/batch-meta`（ids 1–100、三字段至少一项、逐条 `skipped` 原因 `deleted`/`not_paper`、投放位变更逐条 `material_paper_sync`、审计 `batch_update_meta`；**路由声明在 `/admin/{material_id}` 动态段之前** —— 与批量删除那次 422 的坑同一约定）；②批量条加「批量改信息」按钮 + 弹窗（科目/分类/投放位，**三项都可"不改"**，只提交改过的字段）+ 回执 toast「已更新 N 条；跳过 M 条」；③`src/utils/batchMeta.ts` 纯函数（全空返回 null，不发空 body）。**真机**：勾 2 条 → 弹窗 → 分类填 `D7验证分类` → 「已更新 2 条」、列表即时生效，验完已用接口改回原值（库核对 `category=None`）。验收：后端新增 **10 例**（含"投放位 both→library 卷立刻落回 DRAFT"）、前端 **7 例**、`vitest` **71 文件 / 758 用例**、`vue-tsc` 0、`-k "material or batch"` **444 passed**；OpenAPI 端点 **460 → 461**（新增 1 个，R11 已在方案与 README 登记）。方案与真机图：`docs/plans/D7批量改信息_方案_v1.md`、`assets/备考资料缺陷排查/12_预期效果_D7_批量改信息.png`、`13_真机_D7_批量改信息弹窗.png`
- 2026-11-15（深夜 · 三缺陷第 1 项）：**41 页图表/答案页排除已交付**。41 页真卷里图表页/答案页会被拆成大量假题：p11 61 行里 47 行短标签、32 行纯数字，**16 个数字被误认成题号**（连 "125.60%" 都成了"第 125 题"）；p41 答案页 121 行里 104 行短标签。**交付**：①`page_kind()` 整页丢两类 —— **答案页**（短行≥0.7 且 数字行≥0.2 且 题号≤4，命中 p41）与**数字图表页**（数字行≥0.2 且 正文长行≤4，命中 p11）；②**表格页（p16/p19/p25）不整页动** —— 首版整页丢后真题 39/47/50/66 跟着消失，被实测否掉，改为交给 F3 按题兜底；③F3：题干无中文、或四选项全空且题干<15 字 → 丢（**有选项的一律保留**，避免误伤"题干（）"这种短判断题）；④`meta.ocr_pages` 回传 + 草稿体检两条（"已跳过 N 页图表/答案页"、"已丢弃 N 条疑似图表/答案行"）；⑤`PAPER_OCR_PAGE_FILTER=0` 一键回滚。**实测**：41 页 **114 → 96 题**、**题号 125 消失**、重复题号组 **16 → 5（多 21 条 → 5 条）**、四选项齐全 **72/114 → 87/96（63% → 91%）**；**5 页探针完全不变**（20 题 / 19 齐全 / 无跳页）。**如实**：39/47 仍缺号，但它们**不在被跳过的两页上**（p19/p25 整页保留），不是页过滤造成，更像题号行本身没被 OCR 认出（T6 不覆盖"整题消失"）。验收：新增 **15 例**、`-k "ocr or paper or splitter"` **263 passed / 0 failed**、`gate_all` 9/10（唯一红仍是既有 L1-G）。方案与预期图：`docs/plans/41页图表答案页排除_方案_v1.md`、`assets/备考资料缺陷排查/11_预期效果_41页图表答案页排除.png`
- 2026-11-15（深夜）：**D8 题序根治已交付（D8-1..4 全做）**。分批补录会让第二批题排到卷尾 —— 两处导入（`/batch-parsed`、确认导入）都是 `order_base = next_question_order()`（**纯追加模型**），不看题号；历史实证 2024 国考卷 #4 **100 条里 60 条错位**。**交付**：①`paper_stats.normalize_question_orders()`：前提是「该卷全部关联题都有**纯数字题号**且**互不重复**」，满足才按 `question_order = 题号` 重写，否则**一条不改**；②两处导入写完关联后各调一次（`try/except`，失败只记日志、绝不阻断导入），`/batch-parsed` 回包加 `order_fixed`；③P3 导题建题时补 `question_number`（以前只写 order），让"按题号定序"对导题入库的卷也成立；④`fix_relation_order.py` 改为调用同一服务函数（规则只写一处，保留 `--apply` dry-run）；⑤单测 **9 例**，其中 1 例专锁"导入模块真的拿到了这个函数"（防被 try/except 吞成静默失效）。**真实库只读验证**：卷 #2/#4 各 100 题 `changed=0`（一条不动）、卷 #5 97 题全部无题号 → `skipped_reason=non-numeric`（跳过，保持原顺序）。验收：`-k "paper or import or ingest or order"` **272 passed / 4 skipped**、`gate_all` **9/10**（唯一红仍是既有 L1-G：397<3085/3632）。方案与预期图：`docs/plans/D8题序根治_方案_v1.md`、`assets/备考资料缺陷排查/10_预期效果_D8_题序自动对齐.png`
- 2026-11-15（晚）：**D10 已交付（按你「按建议全做 D10-1/2/3」）**。今天验收探针时踩的那条死路：**资料没编号 → 列表连「建卷」都不显示 → 点「确认入库」被 400 打回 → 无路可走**。**三条根因**：①`_item_brief` 只回 `badge`、不回 `paper_code`（改信息补的编号列表看不见）；②前端建卷按钮 `v-if` 要求编号、`paperCodeOf` 只读 `badge`、`ensurePaper` 无编号时**静默 return**；③`confirm_draft` 无卷直接抛错、一句引导都没有。**交付**：列表带 `paper_code`（material 139 的 `GZ-2025-LK-5P` 现在列表里可见）；**无编号也显示「建卷」**，点开弹「先给这份资料一个编号」（预填后端建议值 `MAT-20261115-140` 这类，可改）→ 生成；`confirm` 无卷时**自动建卷**（编号规则：已有编号 → 标题解析 → `MAT-{YYYYMMDD}-{id}` 兜底；卷固定 **DRAFT**；编号写回资料；审计写明"自动建卷"），成功 toast「已自动建卷 X（草稿），记得上架」，`auto_paper=false` 回到旧报错（文案带引导）。**真机**：临时资料 140（`D10探针_无编号.pdf`）→ 列表出现「建卷」→ 弹窗预填 `MAT-20261115-140` → 生成 → `study_material.140.paper_code` 写回 + `exam_paper #8 DRAFT`；验完**已删卷 #8 + 软删资料 140**，库回到 **129 份在架资料 / 7 张卷 / 417 题**、无 `MAT-%` 残留。验收：后端新增 **10 例**（A2 里那条"无编号必须 400"的旧契约测试按新行为改写）、前端新增 **10 例**（`src/utils/paperCode.ts` 纯函数）、`vitest` **70 文件 / 751 用例**、`vue-tsc` 0、后端相关回归 **646 passed / 0 failed**、`gate_all` **9/10**（唯一红仍是既有 L1-G：417 < 3085/3632）。方案与真机图：`docs/plans/D10无编号资料建卷与入库_方案_v1.md`、`assets/备考资料缺陷排查/09_真机_D10_无编号也能建卷.png`
- 2026-11-15（下午）：**扫描件「题号行漏检」v1 已交付（T6，按你「按建议实施 S1–S4」）**。你指出「探针第 5 题的选项是第 6 题的、第 6 题整题没了」。**诊断**：第 2 页 34 个原始框里**根本没有「6.2024年9月9日…」这一行**（题号 6 就在这行），而 `D.第6个(966.7) → 下一行(1088.2) = 121.5px = 2.0×` 中位行距；**300dpi 条带重跑能逐字捞回**（`6.2024年9月9日，以“变局下的合作共赢：造全球公共安全共同体”为主题`）。**根因三条**：①OCR 行级漏检 ②`split_questions` 只认题号 → 第 6 题整段并进第 5 题 ③`split_options` 同字母**静默覆盖**（第 5 题"看起来四选项齐全"、零 flag，最难发现）。**S1–S4**：①块内出现**第二组 `A.`** → 取该 A 之前最大的 y 缝（≥1.6×中位）当洞；②复用 T5 的 300dpi 条带重跑；③**收行只认题号行**（`qno_of` 不命中直接丢，记 `rejected`）；④**页码过滤**（实测 `#7 C=「忠诚 2」→「忠诚」`）+ `选项被覆盖(A/B/C/D)` 全新标记。**真机 5 页**：**19→20 题、题号缺号 `[6]` 消失、#5 恢复「第3/4/5/6个」、#6 独立成题、#7 C=忠诚、四选项齐全 17→19/20**（`holes=2 recovered=2 rejected=0`、13.7s）。**41 页**（第一版按下标比出 20+ 条假差异，已改成按「题号+题干」对齐）：**113→115 题、84→90 齐全、变好 4 / 变差 0**，另 6 条"选项文字变了但完整度没变"逐条看过全是纠错（#5/#57/#79×2/#84/#98）。验收：新增 **11 例**、相关回归 **654 passed / 0 failed**、`gate_all` **9/10**（唯一红仍是既有 L1-G）。方案与预期图：`docs/plans/扫描件题号行漏检_方案_v1.md`、`assets/扫描件选项与水印加固/06_预期效果_第6题题号行回收.png`
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
- （4）工作流--大家可以去多问一下其他AI（大模型服务、千问、智普等等），让他们来设计针对你使用的AI设计你相应的功能模块的必须工作流，保证使用时可以按照工作流的内容设计、不至于让其胡思乱下、偷工减料、出现AI幻觉等（这个可能需要在不断地测试，摸索之后才有点头绪）
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
| `plans/资料多格式导入_现状实测与方案_v1.md` | v1 | ✅ **已实施**（实际形态与原计划不同：单页三弹层 + O5 异步导入 + 零迁移；2026-11-14 校准） | 你要求「不要只靠 Excel 导入，按实际资料格式扩充三端上传 + 进度条」。**实测发现后端早已支持 docx/xlsx/文字型 pdf，甚至给扫描件留了 MinerU 异步通道**（`POST /admin/import/upload`、`/status`、`/preview`、`/confirm`、`/import-records`），但：①前端只有学生页 `material_upload.vue` 且 `accept=".xlsx,.csv"`，管理员低代码页无导入入口；②`C:\mineru_env` **不存在** → 扫描件必失败；③`material_import_record` **无进度字段**（对照 `question_import_record` 早有 `progress_percent`+`current_phase`）；④单文件、仅管理员。**资料格式实测**（`备考资料\` 57 文件 223.8 MB）：**30 Excel / 1277 张卡**（sheet 名 4 种但表头统一 5 列：正面/背面/分类/考点/封面，5–201 行）、**26 PDF / 1619 页**（24 文字型 1594 页 + **2 扫描型 25 页，其中 204 MB/90 页 0 字符**）、**1 docx / 297 段 0 表格**（带"高频考点★★"）；题库另有 480 PDF（473 文字型/7 扫描）。现状只能导入 30 个文件 ≈53%。方案：三段式进度（上传 0-10 / 解析 10-70 / 提取 70-90 / 待确认 90-100，PDF 页级、docx 段级、xlsx 行级）、批量批次 `batch_id` + 队列 + 失败重试、格式→解析器映射表（含 .doc/.md/.txt/.pptx/图片）、新增 3 端点 + 1 迁移（`20261105_006`）+ 页面路由 104→105 双改点、MinerU 本地 venv vs 在线 API 对比（建议本地，代码已按本地写好且要求纯 ASCII 路径）、P0–P2 分期与验收、D1–D6 待拍板 |
| `plans/待决策事项_逐条说明_v1.md` | v1 | ✅ 已全部裁定（2026-11-06，结论见 `plans/待决策裁定结果_v1.md`） | 把 19 个待决策问题逐个讲清楚「到底在定什么」：**A 组开工阻塞 12 条**（D28 新建手写管理页 vs 设计器改造 / D29 类型键名与中文统一 / D30 双格式=一条资料两份文件 / D31 主文件 docx / D32 试卷元数据表单必填 / D33 申论 4 题本轮不拆题 / D34 旧 `.vtj` 页保留 / D35 侧栏冻结用全局 CSS / D36 批量 50 个 / D37 上传时间取入库时间 / D38 不加时间筛选 / D39 先做 v3 A 批、进度迁移并入 B 批）；**B 组下一阶段 7 条**（D21 拆题归 P2 / D22 三份样例 / D23 原卷与题目双存 / D24 人读 paper_code / D25 元数据落库 / D26 新建手写页承接归属试卷 / **D27 原建议作废：`study_material` 无 `source` 列，改为新增 `paper_code` 列**）；**C 组 AI 讲师 11 条暂停**。每条含「背景 / 要决定的事 / 选项差异与后果 / 我的建议 / 影响范围」，末尾附一页速查表 |
| `plans/资料管理v3_预览发布者类型双格式试卷讲义_方案_v1.md` | v3.1 | ✅ **裁定后终稿、已冻结**（未写业务代码；不动 main） | 按你 4 条要求重构：**实测先抓出 3 个真问题**——①`04_讲义_正常` 被存成 `card` 且导入两条（ID 121/122，前端 select 默认值 `card` 与唯一选项 `article` 不匹配）；②类型白名单只有 `video_intro/video_advanced/article/card`（`materials.py:30`），**没有讲义/试卷**；③列表无发布者、无预览（`creator_id` 119/119 有值）。**页面**：新建手写页 `src/views/admin/materials.vue` 替换路由（不动 `.vtj` 模板，旧页保留可回滚）+ 统一预览抽屉（6 类型各自渲染）+ 发布者列 + 6 项类型筛选 + 试卷/讲义行显示元数据 + 批量双格式导入弹层。**后端**：类型加 `lecture`/`paper`（零迁移）；新增 `material_file`（一资料多文件，pdf+docx 配对，主文件优先 docx）；`study_material.paper_code` 一列（唯一迁移）；4 个新端点（preview/batch/batch 汇总/publishers）+ 列表增 `publisher/files/paper` 字段；试卷三科格式（行测·公专全选择题，申论 4 道论述题）；侧栏冻结走全局 CSS（不改模板）。**分支**：`feat/material-admin-v2` 从现有导入分支切出，A/B/C/D 四批提交，**不合并 main**。T1–T12 约 8 天；附 4 张效果图；**含「上传时间」列功能规格**（语义区分上传/入库时间、格式/排序/空值/时区、接口新增 created_at、3 条验收用例）；待拍板 D28–D38 |
| `plans/待决策裁定结果_v1.md` | v1 | ✅ 19 条全部裁定（2026-11-06） | 把 D21–D39 一次落定：**17 条按建议 + 2 条你改写（D32/D38）+ 1 条跟随（D25）**。核心三处细则：①**D32 试卷元数据「只读文件名」**——取消表单必填，只解析科目/年份/地区/题本·答案，解析不出的**留空不阻断入库**；附实测命中率（517 份文件名：科目/年份 100%、地区 99.4%、题本答案 99.8%、四要素齐 99.2%、题量/满分 0%）与 `paper_code` 人读码生成/去重规则；②**「改信息」编辑弹窗**——列表操作列新增按钮，弹窗全字段非必填、只做格式校验，保存走新端点 `PATCH /api/materials/admin/{id}/meta`，同步 `exam_paper/exam_paper_tag`、按需重建 `paper_code`、写审计 jsonl、乐观锁 409；③**D38 时间范围筛选**——筛选栏加「全部/最近 7 天/最近 30 天」，滚动窗口口径、可与其他筛选叠加、右侧显条数。另含 v3→v3.1 增量表（端点 4→5、白名单 +4→+5、组件 2→3、工时 8→8.2 天、DoD 9→12）与证据复现命令 |
| `plans/A1_类型扩展_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07） | v3.1 方案 **A 批第 1 项**的交付记录。**改了什么**：后端 `TYPES` 白名单加 `lecture`/`paper` + `admin_stats.by_type` 补两键（零迁移、 筛选 L86 与新增/编辑 L898 共用同一白名单）；前端建**类型登记表单一真源**（6 类 + 中文名 + 徽标色 + 视频/双格式标记，消灭"下拉/徽标/统计"三处各写一遍文案的老问题）；按 **R3 不改 `.vtj` 模板**、用 **DOM 注入** 给管理页补「讲义/试卷」下拉项与两格统计卡（`select` 节流 15s、20s 刷新、单例幂等、离开页面自动移除，A4 换手写页后删一个文件+一行安装即可）。**证据**：真机 DOM 证据（7 个类型选项 / 6 格统计卡）+ 2 张真实截图；`?type=lecture` 400→200、非法类型仍 400；vitest 17 / pytest 29 / typecheck 0 / gate_all 9-10（唯一 FAIL 为既有 L1-G 题量护栏）。含**没做什么**清单（徽标配色归 A4、导入向导仍旧 4 类归 B3、改信息弹窗归 C2b）与三种粒度回滚方案 |
| `plans/A2_上传时间与发布者_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，后端+前端API层；页面待 A4） | A 批第 2 项。**后端**：`admin/list` 增 `created_within`（滚动窗口 7d/30d）、`order`（created_desc/asc）、`publisher_id`；item 增 `created_at`（naive 本地时间补 `+08:00`）与 `publisher`（nickname→username 回退，一次查询无 N+1）；**NULL 时间行恒定排最后**。**前端**：`fetchAdminMaterialList` + 类型，空串参数不下发。**实测**：7d=17 / 30d=61 / 119；正序最早 id 1；非法值 422；pytest 13 + 回归 61、vitest 6。**数据发现**：58/119 行 `create_time` 为 NULL（id 48–105 全卡片）→ 显示 `—`、不进窗口筛选，决定**不回填**；另记一待核项（`init_material_data.py` 用 UTC `CURRENT_TIMESTAMP`）。**未做**：页面列/排序/时间范围下拉（A4）、预览抽屉（A3） |
| `plans/A3_预览抽屉_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07；列表按钮待 A4） | A 批第 3 项。**后端**：`GET /api/materials/admin/{id}/preview`（管理员、含未上架、HTML 二次 sanitize），返回 `type/type_label/subject_label/status/publisher/created_at/uploaded_at/content_html/card/video/chapters/files/paper`；`chapters/files/paper` 先给空值但**字段固定存在**（B/C 批只填数据不改契约）；R11 白名单 +1 条。**前端**：`MaterialPreview` 类型 + `fetchMaterialPreview`；`MaterialPreviewDrawer.vue` 一个组件覆盖 6 类，Teleport 到 body、ESC/遮罩/按钮三种关闭、受控（不发请求）；组件库页加演示区（3 样例 + 真实 ID），不新增路由。**实测**：id 120 卡片（下架可见）、id 1 文章（含 h2/表格）、999999→404、403；pytest 12 + vitest 30 + typecheck 0。**坑**：Vite 因编辑器原子写 `EBUSY` 崩溃，表现为"页面还是旧的"，已重启清理并记录 |
| `plans/A4_资料管理新页_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，v1 范围） | A 批第 4 项，**第一个新画风真页面**。`src/views/admin/materials.vue`（~470 行）替换 `/admin/materials`：5 格统计 / 6 类筛选 / 发布者 / 上传时间（可排序）/ 时间范围 / 预览抽屉 / **上架=审批** / 删除；旧 `.vtj` 页原样保留在 `/admin/materials/legacy`（R1），`/admin/papers` 改 **redirect**（P4=A，无 component）。**门禁净变化 0**（换 component ±0、legacy +1、papers −1 → 仍 105），实测 L6/L7 通过。**P0–P5 全按建议**（默认未上架 / 只收敛资料侧 / 下架不填理由 / 2 套卷 C 批补录 / redirect / 教师预留）。实测：5 格 114/0/3-0/111/103-11、9 列、20 行、菜单 10 项、redirect 生效、legacy 可达、抽屉出真实数据。**未做**：上传试卷（等 B 批 material_file）、改信息（C2b）、批量与智能导入（走旧版页）、侧栏 fixed（A5） |
| `plans/A5_侧栏冻结_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07）—— **A 批 6/6 收尾** | `src/layouts/AdminLayout.vue` 一个文件：侧栏与顶栏由 `sticky` 改 **`fixed`**（sticky 被 VTJ 三层 `overflow` 祖先打破，实测 0→−600），`.admin-right` 用 `margin-left:220px` + `padding-top:56px` 让位，折叠态 64px 通过根节点 `is-collapsed` 联动；顶栏描边/阴影/面包屑统一到令牌。**实施中自查出一个坑**：第一版顶栏只加 sticky 同样失效（−380→−486），故一并改 fixed。实测：sidebar/header `moved=false`、折叠 64/65、`.vtj` 页无重叠；typecheck 0。影响面：12 个管理页共用布局，一次生效。回滚=改回 sticky 或 revert 单文件 |
| `plans/A4b_删除改软删除与回收站_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，用户裁定 B） | A 批补丁（A4 的删除闭环）。**问题**：管理端删除是 `db.delete()` 物理删除 + 清学习进度，与方案 §2.2「-1=软删除」相反；**连带修掉既有 bug**：`DELETE /admin/batch` 声明在 `/admin/{material_id}` 之后 → 恒被解析为 `material_id="batch"` → 422，批量删除从未调通。**改法**：单条/批量都置 `status=-1`、保留进度、重复删幂等；恢复走 `PUT /admin/{id}/status {status:0}`（未上架，需再上架可见），审计「恢复资料」；前端下拉加「回收站（已删除）」、已删行只留「预览/恢复」。**实测**：DELETE→112/111、published 102→101、deleted 5→6，恢复+上架后 `data restored=True`；回收站视图 5 行、恢复色 `rgb(15,122,77)`；两弹窗文案实测。pytest 13 新增/45 合计、vitest 545、typecheck 0、gate 9/10（L1-G 既有红）。**未做**：彻底删除（purge） |
| `plans/试卷管理收敛_单一入口与上架即审批_方案_v1.md` | v1 | 🟡 **部分交付**：页面层已收敛（审批页下线 / `/admin/papers` redirect）；**接口层 4 处直写 PUBLISHED 未收**（=D1；2026-11-14 已加列表红标护栏） | 回答「不要多种上传试卷的方式，只保留资料管理页的试卷管理，审批改成批准上架=审批通过」。**实测**：6 条链路 / 8 处 `ExamPaper(` 建卷调用（5 个文件）；两套状态机（资料 status -1/0/1 = 5/11/103 与试卷 paper_type DRAFT→PENDING→APPROVED→PUBLISHED→ENDED，实测 ENDED 1 / PUBLISHED 2）；审批页 `paper_approval.vue` 214 行 + 菜单项 `AdminLayout.vue:112`；试卷相关页面还有 teacher_papers 1305 / paper_answer 1121 / student_papers 386 / paper_result 314 行。**目标模型**：一份试卷=一条资料；两态（0 未上架=未通过 / 1 已上架=通过 / -1 软删）；**上架这一个动作=审批**，没有单独通过/驳回按钮；`exam_paper` 退为投影并跟随 status（学生考试链路 `exams.py:46/104/141` 依赖 PUBLISHED，联动是最大风险）。**变更**：删菜单项、`/admin/papers` 按 P4 redirect 或移除（L6/L7 105→104）、A4 增「上传试卷」入口与试卷列（+0.5 天）。**6 条风险**：下架未联动导致还能考 / 8 处建卷绕过 / 旧书签 404 / 现有 2 套卷短期仍为 0 / 误下架中断考试 / 遗留页误改。**7 条 DoD**；**P0–P5 待拍板** |
| `plans/A批_人工验收清单_v1.md` | v1 | 📋 验收指引（2026-11-07） | A 批（A0–A5 + A4b）的**人工验收剧本**：0 节强刷/账号/基线数字（112·0·3/0·109·102/10，回收站 5 条=47/46/25/20/16）；1 节快速版 6 条（Q1–Q6，8 分钟）；2 节完整清单（A0-1~2 / A1-1~3 / A2-1~4 / A3-1~4 / A4-1~6 / A5-1~4 / **A4b-1~5 删除·回收站·恢复闭环 + 学生端核对**）；3 节列出「排期内未做」6 项（上传试卷/批量导入置灰、改信息、试卷与讲义 0 条、无 purge、58 条 `—`）；4 节给出回执格式；5 节服务重启命令。**关键提示**：回收站 5 条是历史软删数据，点「恢复」会真的改数据 |
| `plans/B3_讲义类型修复与重复导入拦截_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，B 批第 1 项） | docx/pdf 导入**默认落「讲义」**（原来被分类器的"短文档→card"规则吞成卡片）+ **重复导入明确拦截**。**检查点**：①文档 `type` 白名单 article/lecture、不传默认 lecture；②分类器文档分支恒 lecture；③同文件（同名+同大小+sha256，仅比 `consumed`）重复上传 409、消息带旧记录号；④同内容（content_hash，排除软删）重复 confirm 409、`force=true` 放行；⑤旧页向导注入「作为讲义」并默认选中、徽标英文 key 中文化（R3 不动模板）。**实测**：真实样本 → material 121 lecture、112→113、讲义 3/0→3/1；两次 409 文案原文；旧页徽标 `lecture`→「讲义」。17+106 pytest、567 vitest、typecheck 0、gate 9/10。**§4 事故**：误删 11 条历史解析记录，恢复 2 条、**9 条不可重建**（资料/题目/考试零影响） |
| `plans/B1_资料原件留档_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，B 批第 2 项） | 导入的 docx/pdf **原件不再被删掉**。新增 `material_file` 表（11 列/3 索引/唯一 `(material_id,sha256,role)`）+ `material_files` 服务（原子写、sha256 内容寻址、越界防护、`can_download` 权限纯函数、`orphan_count`）；`import_confirm` 先落档再删临时文件；预览抽屉「原件」区可下载。**安全检查点**：原件放 `backend/storage/material_files/`（非 `/uploads` 公开挂载）、下载必须登录、管理员不限/其他仅已上架、`storage_path` 绝对或越界一律 404。**实测**：121 原件 35898 字节、下载字节级一致、学生 403、匿名 401。**根因修复**：`UPLOAD_*` 写死路径改为跟随 `settings.UPLOAD_DIR`；OneDrive 锁库导致 pytest 卡死 → conftest 指 `%TEMP%`。27 新增 + 98 回归 pytest、vitest 569、gate 9/10 |
| `plans/B1_人工验收清单_v1.md` | v1 | 📋 验收指引（2026-11-07） | B1 的 5 分钟验收剧本：0 节说明"只有 ID 121 带原件"（其余 112 条是 B1 前的数据，源文件已清）；1 节三步快速版（`?type=lecture` → 预览 → 底部「原件（1）」→ 下载 35 KB docx）；2 节完整性 5 项（文件大小/磁盘哈希/其它类型不受影响/统计不变/软删后管理员仍可下）；3 节列出 4 项"看不到是正常"；4 节给 PowerShell 核对命令（`Test-Path`/`Length`/`Get-FileHash`/`git check-ignore`）；5 节可选"从零跑一遍真实导入"；6 节回执格式 |
| `plans/B2_批量上传与双格式配对_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07，B 批第 3 项 / B 批收尾） | 一次最多 50 文件、合计 ≤2GB；**同名 docx+pdf 合并一条**（docx 主文件 / pdf 附件）；逐条队列带进度、重复跳过、失败原因。**检查点**：①端点一次一个文件（`material_id` 区分建资料/挂附件）；②同 `sha256` 返回 `duplicate=true` 不建行；③扩展名+magic+20MB；④编排纯函数（16 例）+ 组件（5 例）；⑤完成后自动刷新统计。**实测**：对话框 `将创建 1 条资料（含 1 组双格式）` → 队列上传中 → ID 122、两行原件、附件 70B 可下载、重复上传 total 仍 114。**跑门禁须带 `OPENAPI_URL`（8000 被 Docker 容器占用，否则 L4 假红 7 个端点）** |
| `plans/B2_批量导入测试数据_清单_v1.md` | v1 | 📋 测试数据（2026-11-07） | `assets/测试上传数据/B2批量导入/` 下 **16 个文件**：①`01_正常用例/` 4 组同名 docx+pdf（2 套题本 + 2 章讲义）+ 3 单文件，分 3 批导 → 创建 **7 条**（114→121，试卷 3、文章·讲义 3/6）；②`02_重复用例/04_讲义_正常.docx` 与 121 字节相同 → 标「重复」不新增；③`03_同名冲突/A|B/同名资料.docx` 同名不同内容 → 两条独立资料；④`04_异常用例/` txt 前端拦、假 docx 后端 400。含三套剧本、统计对账表、5 条"别把正常当异常"、清理办法。所有 docx/pdfs 已校验可正常打开（假 docx 除外，故意损坏） |
| `plans/交卷用时与满分_缺陷修复记录_v1.md` | v1 | ✅ 已修（2026-11-09，你交卷后发现的） | 你问"用时 0 秒是缺陷吗"→ **两个真缺陷 + 一个真实结果**。①**用时单位错位**：老提交端点 `POST /api/exams/{id}/submit` 把"分钟数"写进按"秒"解释的 `duration_used`（结果页 `formatTime` 按秒拆时/分/秒）→ 9 秒交卷显示「0 秒」，90 分钟的卷会记成 90 秒（少 60 倍）；已改成落库秒、超时判定仍用分钟。②**满分与题量不一致**：#128 是 97 题 × 1 分（上限 97），卷满分却是 100 → 显示「0 / 100」像是被扣 3 分；新增 `sync_total_score`（取 `question_bank.score` 之和，即实际打分那一列）在确认入库时同步；我第一版按关系表 `question_score` 求和，把 #2/#3 误改成 500，当场回滚重算。③得分 0 / 正确 0 / 错误 97 **不是缺陷**：那次只答了 2 题（B→D、A→C 都错），其余 95 题空=错。数据修正（带备份）：记录 #1 `duration_used` 0→9 秒、卷 #5 满分 100→97、#2/#3 恢复 100。测试：交卷用时分秒 2 例、P3 确认入库补满分断言；`gate_all` 9/10。截图 `assets/交卷用时与满分修复/交卷结果页_修复后_9秒_满分97.png`。**追加（2026-11-09 晚，按你指示）**：①关系表残值一次性归一——#2/#3 的 `paper_question_relation.question_score` 5.0→1.0 各 100 行（`_run/normalize_relation_score.py`，备份 `bak_pre_norm_relation_score_20261109_184333`），归一后满分复核 #2 100/100、#3 100/100、#4 100/100、#5 97/97，不一致关系行 = 0、integrity ok，两张表口径彻底一致；②结果页加「分 / 题」后缀区分——纯 CSS `::after`（`<template>` 零改动，守 R3），实测 DOM「0 / 97 分」「0 / 97 题」，截图 `assets/交卷用时与满分修复/交卷结果页_修复后_0满分97_0答对97.png`。**仍未做**：`is_scored` 口径 |
| `plans/考试评分口径_is_scored统一_方案_v1.md` | v1 | ✅ **已批准并交付**（2026-11-09 你定：A + 三字段 + 回填现在做） | 回答「`is_scored` 口径统一」。**先自曝**：我上一份记录里写的「`scored_count=97` 而 `questions=2` 时算 0」与代码不符——老交卷端点 `exams.py:361` 的 `question_ids = list(answers.keys())` 让 `scored_count == len(questions)` **恒成立**，那是个恒真式，真实问题是**三处写点三种口径**（老端点=恒 1 / `smart_exam.py:1039`=建记录即 1 / `exam_service.py:368`=无条件 1 且**该方法全仓 0 调用是死代码**）。**读点只有 2 处**：`agent_router.py:470`（AI 学情取最近 3 条模考成绩）+ `ExamRecordResponse.is_scored`（前端全仓 0 命中）。**实测**：`exam_record` 仅 1 行且 `is_scored=1`、明细 97 行无 `is_correct IS NULL`、397 题全客观题 → 该字段今天恒 1、零区分度。**三种候选语义**：A=分数已完全确定（推荐，主观题待人工评分时天然为 0）/ B=提交即已评分（=现状，等于冗余列）/ C=只加新列。**推荐 A**：新增 `services/exam_scoring.finalize_record()` 做唯一写点，三处调用它；只增不改地补 `manual_pending_count / answered_count / question_total` 三个派生字段（API 路径 0 改动，守 R11）；数据回填预计 **0 行变更**。**测试**：3 新例（全客观=1 / 部分作答也算已评分 / 主观题=0 + 待评 1）。**附教师端「待审稿」徽标预期效果图两套**（工作台·资料稿版 = 主方案；试卷管理版 = 备选且实测「待审批」徽标**已存在**，缺的只是导航角标）——图在 `assets/教师端待审稿徽标/`，落点三条路径（设计器拖 / 手写页替换 / DOM 注入）与 R3 约束写在 §9 |
| `plans/考试评分口径_is_scored统一_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，按你拍板三条） | `is_scored` 口径 A 落地的交付记录。**7 个文件**：新增 `services/exam_scoring.py`（`scoring_flags()` 纯函数 + `finalize_record()` **唯一写点**）与 `scripts/migrate/migrate_add_exam_scoring_fields.py`（`ALTER TABLE ADD COLUMN`×3，dry-run 默认 / 自动 `sqlite3.backup()` / integrity 校验 / **只用 ASCII 标记**避开 GBK 控制台 emoji 崩）；`ExamRecord` 加 3 列；三处写点全部改调用 `finalize_record`（老交卷端点删掉恒真式、`smart_exam` 不再建记录即写 1、`exam_service.submit_exam` 死代码一并收口）；`ExamRecordResponse` 与两个手写序列化补 3 字段；新增 **8 例**测试。**实测**：迁移备份 `backups/before_exam_scoring_fields_20261109_192848.db`、回填备份 `before_backfill_is_scored_20261109_193035.db`；回填前 dry-run 显示 `#1 answered_count 0→2、question_total 0→97`（`is_scored` 保持 1），写入后剩余不一致 0 行、`integrity ok`；**200 passed**（原 192 + 8）；`gate_all` **9/10**（唯一红=既有 L1-G）；线上接口 `GET /exams/records` 与 `GET /exams/records/1` 均返回 `is_scored=1 pending=0 answered=2 total=97`，与结果页「0 / 97 分 / 0 / 97 题」口径一致 |
| `plans/断点续答与倒计时_列表未开放_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09 你点单两项） | ①**手机断点续答 + 倒计时**：开考后先打 `GET /records/{id}/resume`（题目 + `saved_answers` + `remaining_seconds`），答案回填（`"A,C"` 字母→下标）、自动跳到第一道未答、顶栏 `mm:ss` 倒计时（最后 5 分钟变红呼吸）、到 0 **不再确认直接交卷**、监听作答防抖 1.2s 调 `PUT /{id}/progress`、`onUnmounted` 停表（否则退出后定时器还在跑并触发交卷）。实测：答 2 题→关页面→重进，DOM 读到 `progress=3/97`、`timer=1:59:10`、答题卡 `done=2`（格子 1、2 绿），库内 2 行 `A`/`B`。②**PC 列表显示「未开放」**：`/api/papers/list` 删掉对学生会话的 gate 过滤，改为逐行下发 `exam`/`answerable`/`exam_hint`（`exam_gate.paper_state()` 走服务层避免跨域 import）；`student_papers.vue` 只改 `<script>`/`<style>`（守 R3）—— `getPaperStatus` 加"不可考"优先级显示琥珀「未开放」、`startExam` 先拦并弹原因、新增 `.status-off`。实测临时关掉 2019 北京卷：学生列表 total 仍 4、状态「未开放」+ 文案，截图后立刻恢复（`exam_open` 五套卷全 1）。**测试口径同步改写 3 条**（隐藏→显示+原因）。验证：34 passed、`vue-tsc` 0、`gate_all` 9/10；续答测试记录已按守卫删除（备份 `before_cleanup_mobile_exam_test_20261110_162227.db`）。**已知边界**：倒计时以进页面时的剩余秒数为准（休眠会偏慢，交卷仍按服务器时间判）；自动保存只存已答题 |
| `plans/考试结果口径修复_交付记录_v1.md` | v1 | ✅ **已完成（2026-11-11，全批 P0+P1+P2）** | 你回「全批，闸门要」之后的落地记录。**修复前 → 后**（同一份成绩：97 题、答 2 题全对）：弹窗「正确/错误 **97/0**」→ **2/95**；「正确率 2%」→ **得分率 2.06%（2 ÷ 97）**；用时 客户端 45s → **服务端 time_used**；逐题「全部 ✗ 错误」→ **✓ 正确 / ✗ 错误 / — 未作答** 三态 + 错题给正确答案；结果页同步 `2 / 95 题`、`用时 2分19秒`；成绩分析 `accuracy` 1 位 → **2 位小数**。**P0 后端**交卷回包补 `correct_count / wrong_count / unanswered_count / details[]`（三数互不重叠、相加=总题数；空白归未答，不算 wrong）；**前端**逐题状态改查 `details`、正确选项按 `correct_answer` 高亮。**P1** 新增 `src/utils/examSummary.ts` 作**唯一口径真源**（弹窗/结果页共用，`percent2` 两位小数）；结果页去 `\|\| 100` 兜底 + 加"已答/未答/答对率（按已答）"；PC 续答改走 `GET /records/{id}/resume` + `PUT /progress`（与手机端同一接口，跨设备可续）。**P2** 待人工评分提示、自动交卷 `_submitting` 守卫、**答案覆盖率闸门**（`contract.answer_gap()` + `exam_ready(exam_state(..., answers_missing=))`，`no_answers` / `answers_incomplete` 带「还差 N 题」文案，`/start` 直接 400）。**验证**：新增后端 6 例 + 前端 8 例；后端 `-k "exam or paper or material"` **544 passed**；全量 vitest **63 文件/687**；`vue-tsc` 0；`gate_all` **9/10**；真机复核截图 2 张（弹窗 `2/95`+`2.06%`，结果页同口径）。**数据**：我造的测试记录已按守卫删除（备份 `before_cleanup_mobile_exam_test_20261111_1907/1908*.db`），保留你自己的 3 条（#1 0 分、#2/#3 各 2 分）；卷 #5 `max_attempts=5` 已用 3 次 |
| `plans/考试功能逻辑审计与修复方案_v1.md` | v1 | ✅ 已批准并交付（见上一条） | 你在真机验收交卷后看到「正确/错误 97 / 0」「两题都标错误」「正确率 2%」，本文给**审计 + 修复方案**。**先给账**：record #3 库里是**对的**——97 行明细中 `is_correct=1` 共 2 行（Q301 答 D=正解 D、Q302 答 C=正解 C）、`total_score=2.0/97`、`duration_used=139`，页面那三个数是**前端渲染 bug**。**答案已传**：4 套卷答案/解析覆盖率 100/100/100/97（= 题量）。**11 条问题**：P0 两条（`submitCorrect=scored_count` 把"参与评分题数"当答对数 → 97/0；`isCorrect(){return false}` + 考试取题不含答案 → 逐题恒显错误、正确选项不标绿）；P1 四条（"正确率"其实是得分率 2/97 未标注、用时取客户端 45s 而库内 139s、计时器每次进页面重置、PC 续答只写 localStorage 与手机端服务端 resume 不一致、未答 95 题无提示）；P2 五条（结果页 `max_score \|\| 100` 兜底、待人工评分无提示、超时自动交卷失败每秒重试、**无答案的卷也能开考**、`scored_count` 命名误导）。**附 3 条"不是 bug"**：空白按错计、得分 2/97、成绩分析确实能查到。 |
| `plans/备考资料返回首页按钮_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-12 你反馈） | 进 `/materials/xingce` 后没有返回入口、只能用浏览器后退。**一个页面覆盖三科**（`xingce/shenlun/gongzhuan` 都是 `src/views/student/materials.vue`），故只改一处：页面顶部新增 `← 返回首页`（`.mp-crumb` + `.mp-back`，白底 + 主题色描边，行测蓝/申论绿/公专琥珀，hover 反色）。**跳 `/page/home_page`** 而非 `/home` —— 与顶部导航同一个地址，落地后「首页」高亮才对得上；空态里的「返回首页」也一并改过来。顺手让 `navbar.vue` 把 `/home` 也认成首页（同一组件的别名），避免"跳过去了但导航不亮"。**实测**：三条路由都有按钮（颜色分别是蓝/绿/琥珀），点击后 hash→`#/page/home_page`，落地 `.menu-item.active`=首页；`/home` 也点亮首页；`vue-tsc` 0。这个页面本身不渲染全局导航栏，所以必须有页内返回入口 |
| `plans/导航高亮跟随路由_缺陷修复记录_v1.md` | v1 | ✅ 已修（2026-11-11 你反馈） | 点「题库 / 关于砺安题库 / 论坛」后小红线与浅色块仍停在「首页」。**根因**：`navbar.vue` 把选中项存在组件 state（初始 `'home_page'`），而每个页面各自内嵌一份 `<NavBar>`，换页即重新挂载、state 复位 → 高亮永远回首页。**修法**（只改 `<script>`，守 R3）：新增 `menuIdFromRoute(path)`（唯一路由→菜单映射）+ `syncActiveFromRoute()`，`mounted` 与 `watch: '$route.path'` 各对齐一次；菜单外页面（下载客户端/答题/收藏）返回 `''` 不高亮，避免"错误地停在首页"。**实测** 5 条路由 DOM：home→首页、question_bank→**题库**、about→关于砺安题库、forum→论坛、download_client→无高亮；`vue-tsc` 0。**已知现状**：`/news` 那页（`news_timeline.vue`）自带页内「←返回」头、**不渲染全局导航**，所以新闻页看不到高亮属正常，需要的话给它加一行 `<NavBar />` 即可 |
| **`plans/考试开关点击后卡死_缺陷修复方案_v1.md`** | v1 | ✅ **已批准并修复（2026-11-12）** | 「点了考试开关，显示已关闭但按钮没滑回去、再也打不开、设置定时也没用」。**真机 CDP 复现**（4 步 DOM 表）+ **回包对比**定位根因：写端点 `PUT exam-open` / `exam-window` 返回的 `exam` **少了 `manual_open/paper_code/paper_id`**（列表走 `exam_gate.state_of` 才有），前端 `row.exam = state` 整体替换 → `manual_open` 变 `undefined` → `is-on` 恒真（按钮常亮）、`nextOpen` 恒假（永远发"关闭"）、副文案显示"手动开启"、aria 一直念"关闭考试"；定时**保存成功**（toast + `20:00-22:00 定时`）但因手动闸打不开而始终"已关闭"。修法：后端 `exam_gate._enrich()` 单一真源，`state_of/set_open/set_window` 三处共用；前端 `examSwitchOn/nextExamOpen/mergeExamState` 三处防御 + `onExamWindowSaved` 合并。**真机 5 态复验**：关→灰/已关闭/已手动关闭、再点→开/可进入、设定时→未开始/20:00-22:00、清空→可进入。测试 22 后端 + 38 相关回归 + 23 前端、vue-tsc 0、gate 9/10（仅既有 L1-G）。交付记录见下条 |
| **`plans/考试开关点击后卡死_交付记录_v1.md`** | v1 | ✅ **已交付（2026-11-12）** | 根因一句话：**写端点少回 3 个字段，前端拿"缺字段"的状态当开关真值**。改动 3 个代码文件（`exam_gate.py` 新增 `_enrich`；`examGate.ts` 新增 `examSwitchOn/nextExamOpen/mergeExamState`；`materials.vue` 类/aria/`toggleExam`/`onExamWindowSaved` 全部改用它们）+ 2 个测试文件（后端 4 例、前端 +7 例）。含修复前/后 4 步真机对照表、接口键对比、5 张截图（`assets/考试开关修复/`）、门禁与数据说明（5 张卷全部 `exam_open=1`、窗口清空、`integrity ok`）、回滚与已知小瑕疵（窄列 `20:00-22:00` 会截断） |
| **`plans/OCR_P3_试卷导题扫描件_方案_v2.md`** | v2 | ✅ **已交付（2026-11-13，交付记录见文末 §9）** | 你要求「做 P3 前先给方案和预期效果图」。**现状实测**：`read_pdf` 靠文字层，扫描件 `lines=[]` → **拆出 0 题**；导题入口是**同步**，41 页 OCR ≈6.5 分钟会卡住请求。**PoC**：真实 41 页扫描试卷前 2 页 → OCR 9.5s/页、66 行、题号 6 个、**拆出 6 题（4 题四选项齐全）**；缺陷：丢 C 项、页脚/店主微信噪声、选项跨行。**设计**：`read_pdf` 加扫描分支（`parse_pdf_once` 判定 → `ocr_sidecar` → `ocr_html.drop_noise` + 试卷噪声表，`images=[]`）→ 复用现有 `split_questions`；草稿加 `parsing` 状态、后台 job、进度写 `message`（**零迁移**）、40 分钟惰性超时；前端抽屉轮询 + 进度 + 三条警告 + 完成前禁止确认。**T1–T5 ≈2.3d**。**已按 C1=A（进度放 `message`，零迁移）/C2=A 落地**：`read_pdf_ocr` + 试卷噪声 + **行尾广告切除**（真机发现广告会粘进选项行）、草稿 `parsing` + 后台 job + **重复点击幂等**（复用同一份、不起第二个 OCR）+ 40 分钟惰性超时、抽屉 2.5s 轮询与三条警告。**真机（真实 41 页扫描试卷前 5 页）**：「导题」**0.14s** 返回 → `OCR 1/5→5/5 页` → **114.0s（22.8s/页）** → **19 题**（四选项齐全 15）；修掉 4 个真机缺陷（广告粘行、`扫码` 误杀正文、解析中空态文案、双击双份 OCR）。验收：P3 测试 **9 passed**、`-k "paper or upload or import or material"` **550 passed / 0 failed**（**必须 `cd backend` 跑**，从仓库根跑会 47 failed）、`vue-tsc` 0、`gate_all` 9/10 |
| **`plans/OCR_P3与上传即返回O5_方案_v1.md`** | v1 | ✅ O5 已交付（2026-11-13）；P3 见 v2 | 你点名的两件：**①P3 试卷导题扫描件**、**②O5 上传即返回**。**P3 PoC（真实 41 页扫描试卷前 2 页）**：OCR **9.5s/页**、66 行、认到题号 6 个、`split_questions` **拆出 6 题 / 4 题四选项齐全**；缺陷：第 3 题丢 C 项、页脚 `X` 与店主微信噪声、选项跨行截断 → **只能出"文字草稿 + 人工核对"**，图片/版式一律不还原；41 页整份 ≈**6.5 分钟** → 必须异步。**O5**：上传只落盘+建记录+写指纹后立即返回（目标 <300ms），4 类文件解析转后台；复用 P2 的进度口径；去重扩到 `processing` 也拦。**建议顺序 O5 → P3**（P3 复用异步壳），合计 **≈3.7d**；**D1–D5 待拍板**（顺序 / P3 无图 / 异步 / O5 范围 / 去重口径），默认全按建议 |
| **`plans/文件上传提速_方案_v1.md`** | v1 | ✅ **S-A/S-B/S-C 已交付（2026-11-13，D1=C）** | 「不是扫描件的 PDF 也要约 10 秒/个，能否加快」。**根因**：同一份 PDF 被解析两遍（pdfplumber 判扫描 3,685ms + pymupdf 抽取）。**交付与前后对照**：①**S-A 单遍解析**（`parse_pdf_once`，采样前 3 页判扫描）→ 文字版 PDF 端到端 **4,132ms → 143ms（−96.5%，≈29×）**，与旧实现 `html/chapters/word_count` 逐字节等价（5 例单测）；②**S-B 2 路并发**（`forEachConcurrent` + `ArticleBatchUpload`）→ 6 份 docx **1,615ms → 1,429ms（1.13×）**，如实记录"S-A 后并发收益已小"；③**S-C OCR 常驻 worker**（`--serve` + `OCR_MODE` 开关 + 空闲回收）→ 1 页扫描件 **17.6s（冷）→ 4.7s（热）**，每篇之后省 **12.9s（≈3.7×）**（3 例常驻单测：pid 复用/崩溃重启/超时）。验收：`pytest` 24 passed + 相关回归 119 passed；`vitest` **68 文件 / 735 用例**；`vue-tsc` 0；O5（上传即返回）按 D4 暂不做 |
| **`plans/扫描件OCR_P2_文章讲义_方案_v1.md`** | v1 | ✅ **已交付（2026-11-13，D1–D6 全按建议）** | 「续 OCR P2（文章/讲义扫描件）」。**审计三硬点**：前端 180s 判超时（24 页要 3.4–6.6 分钟）、`material_import_record` 无进度列、OCR 硬换行。**交付**：新增 `services/ocr_html.py`（去噪/断行合并/新块断段/超长切分/escape，**10 例单测**）+ `_ocr_sidecar_job`（后台 OCR → `<p>` 段落 → 回写）+ 进度写 `parse_result._ocr`（**零迁移**）+ `status` 回包 `progress`（**零新端点**）+ 40 分钟惰性超时（3 例单测）+ 前端 30 分钟等待与「OCR 12/24 页 · 已用 1:36」（`ocrProgress.ts` **7 例**）。**真机**：24 页扫描件 → 272s / **28,632 字 / 492 段** / confirm 建未上架文章；3 页界面链路截图「已 OCR 3/3 页」，同文件重传仍 409。`pytest` 13 passed、`vitest` 67 文件 730 全绿、`vue-tsc` 0 |
| **`plans/备考资料模块_已交付功能缺陷排查_v1.md`** | v1 | 📋 **排查报告（2026-11-14，等你定 P0/P1）** | 你要求「检查有没有未解决缺陷、做一次全面排查，不含未推进的事」。**方法**：逐条在当前代码重新定位行号 + 全量回归/门禁复跑 + 只读数据快照 + 临时探针复现。**结论：有 8 项未解决缺陷**（真缺陷 D1 反向漂移 4 处 / D2 P3 弃稿被救活（已用探针复现）/ D3 文章导入 20MB 不一致 / D4 答案整读内存 / D8 分批补录题序错位；产品缺口 D5 教师上传 / D6 手机结果页 / D7 批量改信息；文档债 D9）+ 5 类环境数据债，**但无新的静默数据损坏**（integrity ok / 孤儿 0 / 资料与卷一致 / 题 397 未变）。**建议 P0（D2+D3+D9，0.3d，零风险）、P1（D1 巡检护栏 0.4d）**，P2 需拍板。附 2 图：缺陷分级总览、文章导入限额对齐预期效果；并回答「两份探针用途」与「除 AI 讲师外 9 项未推进既定任务」 |
| **`plans/导题缺号定位_方案_v1.md`** | v1 · 深化稿 r2 | ✅ **已交付（2026-11-15，Q1–Q5 全做完；交付记录见 §12）** | 痛点：缺号只显示一行字，管理员要在 41 页 / 57MB 里自己翻。**交付**：①`meta.qno_gaps` + `<draft_dir>/qno_gaps.json`（零迁移、原子写、无缺口删旧）；②**新端点** `GET /api/materials/admin/parse-drafts/{id}/page-image?no=&dpi=&page=`（admin、PDF only、`resolve_abs_path` 防越界、JSON+base64、**0–1 相对高亮框**、6 个错误码 + `PAGE_NOT_ALLOWED`）；③抽屉把「题号缺号 N 个」渲染成可点 chips（`utils/qnoMissing.ts`）+ 手写弹窗（图+红框+上一题/下一题+**看第 N 页**+Esc/←→）；④降级：旧草稿置灰且**不发请求**、docx 不渲染 chips、原件已删给明确文案。**真机两次探针**：p1–p17（17 页，暴露 3 处缺陷）→ **p30–p41（12 页，修复后）** 26 题、缺号 `[86,92]`；sidecar `86 → page 6 + alt_page 7`，`page-image?no=86` 红框在页尾，`&page=7` 返回 `on_alt_page=true`。**三条修复（都是真机撞出来的）**：①缺号下界改 `min(nos)`（拆分上传不再报「缺号 1..43」）；②跨页缺口从「上一题最后一行」起算、主选上一题所在页 + `alt_page`；③`locate_qno_in_line()` 处理「的46.为提升…」这类半句起框，补回的行能真正成为题号起点。**如实**：①p1–p17 那次是带缺陷的证据，保留未删；②备选页只有「提示范围」（整幅宽 + 顶部 18%），`hint` 写明；③86 会出现「补回提示」与「缺号清单」并存 —— 补回的行仍可能没成为题号起点，属已知残余。验收：后端 **24 例**、前端 **8 例**、`vitest` **74 文件 / 770 用例**、`vue-tsc` 0、后端子集 **351 passed**、OpenAPI **461 → 462**、路由 105 不变、探针数据已清理（127 资料 / 13 文件 / 397 题 / 0 pending）。图：`assets/备考资料缺陷排查/21_预期效果_缺号定位_点题号看原卷页.png` |
| **`plans/P2窄屏遮挡复核_报告_v1.md`** | v1 | 📋 **复核完成：不立项、不修（2026-11-15，无代码改动）** | 起因是我在 D6 截图里看到一次右侧三个小图标，就当成了「模板外壳 XMask 悬浮条遮挡」。**复核推翻**：①26 个 `/mobile` 路由逐个干净加载（390×844@2）→ **横向溢出 0、越界元素 0**；②`/mobile/home` 与 `/mobile/paper-result` 三点快照（0.9/2.1/3.5s）+ 全站 fixed/sticky 扫描 → 只有页面自己的顶栏与底部 tab 栏，**没有 action bar**；③1440×900 对照 → `x-mask` 容器在但里面**没有任何 actions 节点**，`#vtjLink` 0×0；④**原样重放 D6 那张图 2 次，截图均 290,082 B（与干净版同尺寸），图标不复现**；⑤唯一越界是 `/mobile/recruit` 的 2 个分类 tab → `.tabs` `clientWidth 383 / scrollWidth 544 / maxScrollLeft 161`，**可横滑**，非缺陷。**如实**：当初两个 DOM 探针因 `-Out ""` 被 PowerShell 吞掉导致参数整体左移（dpr 变 13000、宽变 844），测的是坏视口，我没察觉就拿截图当了结论——在此更正。建议关闭 P2（真要动只有"分类条隐藏滚动条"这一处纯视觉微调）。图：`assets/备考资料缺陷排查/20_复核_P2_窄屏体检结论.png` |
| **`plans/P1题号缺号重号治理_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，你回「按建议」；交付记录见 §9）** | 41 页整卷实测：**缺号 8 个** `[27,39,45,46,47,86,87,92]`、**重号 5 组** `[1,4,79,80,98]`、96 题（不同题号 91）、四选项齐全 87/96。**根因 6 类（带坐标证据）**：**A 整页误丢 → 39**（p11 被判 chart 整页丢，原图确有「39.公安机关的人民警察…」，属 ① 的回归）；**B 表格区题号行未出框 → 45/46/47**；**C 页首页尾丢行 → 27/86/87**；**D 图内数字成假题号 → 1、4**（p28「1.12-2」、p12「4.小时以内数封定神」）；**E 影印重复页 → 79/80**（p32/p33 题号行 y、x、文本逐字相同）；**F 折行两框 → 98**。**交付**：①`page_kind()` 加「真题行」判定（图表页含真题就保留）；②`guard_qno_starts()` 题号自洽（递增 + 像题干 + 分段重编号例外）；③`_dedup_pages()`（Jaccard≥0.95 丢重复页）+ `merge_split_qno_rows()`（折行同号合并）；④**P1-4 缺号补回收**：`find_number_holes()` 按缺号算 300dpi 条带（上限 12），`recover_into(holes=)` 只收本组缺号；⑤**无分隔符题号**（原卷印的是「27在…」「45东江市…」）走 `QNO_LOOSE_RE`，仅在题号连续 +1~+3 窗口内采纳；⑥被挡的假题号行**不丢字**（`split_options(body_from=)` 当正文）；⑦`meta.qno_issues` / `ocr_qno_retry` / `dedup_pages` / `merged_half_qno` + 体检 6 条 + `PAPER_QNO_GUARD=0` 回滚。**实测（同机同参数）**：缺号 **8 → 3** `[46,86,92]`、重号 **5 → 0**、不同题号 **91 → 96**、四选项齐全 **87 → 88/96**、第 39 题**回来**、题号 125 仍无（改由自洽挡，不再牺牲真题）；**5 页探针完全不变**（20 题/19 齐全/无处置）。**如实**：候选题目数仍是 **96**（补回 5 条同时清掉 5 条假题/重复题，方案里写的 ≥97 未达成，改以「不同题号 96 + 重号 0」为准）；39/47/87 **题号回来但选项没回来**（39 是图选项），46/86/92 连 300dpi 也捞不到 → 体检点名交人工。新增 **32 例**（21 + 10 + 体检透传 1）、OCR 子集 **316 passed / 0 failed**。图：`assets/备考资料缺陷排查/17_预期效果_P1_题号缺号重号治理.png`、`18_证据_P1_根因4处原图.png`、`19_实测_P1_题号治理前后对照.png` |
| **`plans/D6手机结果页_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，三个缺陷的第 3 项）** | 手机答完卷 `mobile_answer.vue:807` 直接跳 **PC 结果页** `/paper-result`：390×844 实测卷名折 3 行、「返回试卷列表」折 3 行、4 个 meta 挤成 2 行、无手机顶栏/返回。**交付**：①新增手写页 `mobile_paper_result.vue`（顶栏 / 成绩卡 / 三个动作 / 可折叠逐题回顾；**不碰 `.vtj/`**，守 R1/R3）；②新路由 `/mobile/paper-result`（platform=mobile, roles=[student]）；③交卷跳转改到新路由（全仓只有这一个手机入口）；④**口径零新增**——同一接口 + 同一 `buildExamSummary()`，满分取 `max_score` 不 `\|\|100` 兜底；⑤路由计数 **104 → 105** 双点同步（pytest + L6 脚本，L6 会真的 `import()` 新页）。**真机（record 4）**：`2 / 97 分`、**2.06%**、`00:17`、`2 / 95 题`、已答 `4/97`、未答 **93**、答对率 **50%**，回顾展开 **97 条**。**如实**：第一版三个 chip（答对2/答错95/未答93）相加 190≠97 —— 「错误」含未答导致重复计数，真机截图当场发现并改成 PC 同款 2×2 meta；「再考一次」未点（会新建记录）。验收：新增 **4 例**、`vitest` **72 文件/762 用例**、`vue-tsc` 0、`gate_all` 9/10、OpenAPI **461 不变** |
| **`plans/D7批量改信息_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，三缺陷第 2 项）** | 列表早有"勾选 + 批量上架/下架/删除"，但**没有批量改信息** —— 38 份卡片统一改科目只能逐条点。**交付**：①新端点 `PATCH /api/materials/admin/batch-meta`（ids 1–100、三字段至少一项、逐条 `skipped`：`deleted`/`not_paper`、投放位变更逐条同步卷、审计 `batch_update_meta`；**声明在 `/admin/{material_id}` 动态段之前**，与批量删除同一约定）；②批量条加「批量改信息」+ 弹窗（科目/分类/投放位，三项都可"不改"）+ 回执 toast；③`src/utils/batchMeta.ts` 纯函数（只带改过的字段，全空返回 null 不发请求）。**真机**：勾 2 条 → 弹窗 → 分类填 `D7验证分类` → **「已更新 2 条」**、列表立刻生效，验完已改回原值。验收：后端 **10 例**、前端 **7 例**、`vitest` **71 文件/758 用例**、`vue-tsc` 0、`-k "material or batch"` **444 passed**；OpenAPI **460 → 461**（新增 1 端点，已在方案与 README 登记）|
| **`plans/41页图表答案页排除_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，三个缺陷的第一项）** | 41 页整卷里图表页/答案页被拆成大量假题（p11 61 行里 47 行短标签、32 行纯数字，被认成 **16 个假题号**，还带出题号 125；p41 答案页 121 行里 104 行短标签）。**交付**：①`page_kind()` 只整页丢两类 —— **答案页**（短行≥0.7 且 数字行≥0.2 且 题号≤4，命中 p41）与**数字图表页**（数字行≥0.2 且 正文长行≤4，命中 p11）；②**表格页（p16/p19/p25）不整页动**（首版整页丢后真题 39/47/50/66 跟着消失，实测否掉）；③F3 按题兜底：题干无中文、或四选项全空且题干<15 字 → 丢；④`meta.ocr_pages` + 体检两条；⑤`PAPER_OCR_PAGE_FILTER=0` 回滚。**实测**：41 页 **114 → 96 题**、**题号 125 消失**、重复题号组 **16 → 5**、四选项齐全 **72/114 → 87/96（63%→91%）**；5 页探针**完全不变**（20 题/19 齐全/无跳页）。**如实**：39/47 仍缺号，但不在被跳的两页上，不是页过滤造成。新增 **15 例**、回归 **263 passed / 0 failed**、`gate_all` 9/10 |
| **`plans/D8题序根治_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，按你「按方案全做 D8-1..4」；交付记录见 §8）** | 分批补录时第二批题被排到卷尾：两处导入（`/batch-parsed`、确认导入）都用 `order_base = next_question_order()`（**纯追加模型**），不看题号。**交付**：①`paper_stats.normalize_question_orders()`（前提「全部纯数字题号 + 互不重复」，否则**一条不改**）②两处导入写完关联后各调一次（`try/except`，失败只记日志、不阻断），`/batch-parsed` 回包加 `order_fixed` ③P3 导题补写 `question_number` ④`fix_relation_order.py` 改为调用同一服务（规则只写一处）⑤单测 9 例，其中 1 例专门锁"导入模块真的拿到了这个函数"（防静默失效）。**真实库只读验证**：卷 #2/#4 各 100 题 `changed=0`（一条不动）、卷 #5 97 题无题号 `skipped_reason=non-numeric`（跳过）。回归 **272 passed / 4 skipped**、`gate_all` 9/10 |
| **`plans/D10无编号资料建卷与入库_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，按你「按建议全做 D10-1/2/3」；交付记录见 §7）** | 今天验收探针时真实撞上：material 139 没有 `paper_code` → 列表里**连「建卷」都没有** → 点「确认入库」被打回「这条资料还没有可作答卷」→ **死路**。**三条根因**：①后端 `_item_brief` 只回 `badge`、不回 `paper_code`，改信息补的编号在列表里"看不见"；②前端建卷按钮 `v-if` 要求编号、`paperCodeOf` 只读 `badge`、`ensurePaper` 无编号时**静默 return**；③`paper_ingest/service.py` 无卷直接 400、无引导。**交付**：列表带 `paper_code`（139 的 `GZ-2025-LK-5P` 现在看得见）；**无编号也显示「建卷」**，点开弹「先给这份资料一个编号」（预填后端建议值 `MAT-20261115-140` 这类）；`confirm` 无卷时**自动建卷**（已有编号 → 标题解析 → `MAT-{YYYYMMDD}-{id}` 兜底，卷 DRAFT，编号写回资料），回包 `paper_auto_created` + toast「已自动建卷 X，记得上架」，`auto_paper=false` 回到旧报错。**真机**：临时资料 140 上传→列表出现「建卷」→弹窗预填→生成 → `paper #8 DRAFT`（验完已删卷+回收资料，库回 129/7/417）| 后端 **10 例**、前端 **10 例**、`vitest` **70 文件/751 用例**、`vue-tsc` 0、后端相关回归 **646 passed / 0 failed**、`gate_all` 9/10 |
| **`plans/扫描件题号行漏检_方案_v1.md`** | v1 | ✅ **已交付（2026-11-15，按你「按建议实施 S1–S4」；交付记录见 §9）** | 你指出「探针第 5 题的选项是第 6 题的、第 6 题整题没了」。**证据**：第 2 页 34 个原始框里**没有「6.2024年9月9日…」这一行**（题号 6 就在这行），`D.第6个(966.7) → 下一行(1088.2)` = **121.5px = 2.0×** 中位行距；**300dpi 条带重跑逐字捞回**该行。**根因三条**：①OCR 整行漏检 ②`split_questions` 只认题号 → 第 6 题并进第 5 题 ③`split_options` 同字母重复**静默覆盖**（所以第 5 题"看起来四选项齐全"、无 flag）。**S1–S4**：块内出现第二个 `A.` → 取该 A 之前最大的 y 缝当洞 → 复用 T5 的 300dpi 条带重跑 → **收行只认题号行**（不命中记 `rejected`）；**页码过滤**（实测 `#7 C=「忠诚 2」` → `忠诚`）与「选项被覆盖」标记。**真机**：5 页探针 **19→20 题、缺号 `[6]` 消失、#5 恢复「第3/4/5/6个」、#6 独立成题、#7 C=`忠诚`、四选项齐全 17→19/20**（`holes=2 recovered=2 rejected=0`，13.7s）；**41 页**按「题号+题干」对齐：**113→115 题、84→90 齐全、变好 4 / 变差 0**，另 6 条"选项文字变了"逐条看过全是纠错。验收：新增 **11 例**、相关回归 **654 passed / 0 failed**、`gate_all` **9/10** |
| **`plans/扫描件缺行恢复_方案_v1.md`** | v1 | ✅ **已交付（2026-11-14，按你「按建议，严格遵守全局规则」；交付记录见 §9）** | 你问「第 9 题 OCR 直接跳过的缺陷能否解决」——**能**。**坐标级根因**：第 3 页行距中位数 60.1px，第 9 题 A/B/D 的 y=932.5/991.5/1111.7，**B→D 是 120.2px（2.0×）中间空了一行**；200dpi 与 300dpi 整页各跑一遍都没有「小孙」的框 → **不是标签丢失，是斜向水印把整行压没了**（T1–T4 都修不了"行不存在"）。**方案 S1–S4**：①**检测**（纯内存）本题缺选项字母 **且** 间距 ≥1.6×中位行距 → 判"洞"，1/题 · 8/页 · 40/篇封顶；②**定向重跑**：worker 新增 `crop` 命令 + sidecar `read_region_text`，只渲染那条缝（上下行框外侧 ±6px、整幅文字宽）×**300dpi 原样**（实测二值化 120/150、400dpi 全部掉字）；③**回填**：pt→px 换回版面坐标**原位插入**（不整篇重排，41 页实测整篇重排会顺带改 100+ 处行序），坐标 + 文本两道去重（同带重跑会多吐半截 `D小杰去级批准…`，已挡），补回行仍过水印几何过滤；④**观测**：`meta.ocr_retry` 统计 + 草稿体检「有 N 处整行漏检已局部重跑补回（第 9 题）」，`PAPER_OCR_RETRY=0` 可关。**真机**：5 页探针 **17/19 → 18/19**，#9 的 C 逐字补回 `小孙因个人原因拒绝所长安排的外出交流`，单条带 **2.7s**、行数 +1；**41 页整卷**（同机两遍）题数 **113 不变**、四选项齐全 **84 → 88**、判到 14 洞补回 10 处（25.9s），**逐题只有 4 处变好、0 处变差**（题号 9 C / 56 A / 63 C / 73 A）。验收：新增 **18 例**、`-k "ocr or paper or splitter or material or upload or answer"` **642 passed / 0 failed**、`gate_all` **9/10**（唯一红仍是既有 L1-G） |
| **`plans/扫描件选项与水印加固_方案_v1.md`** | v1 | ✅ **已交付（2026-11-14，D1–D3 全按建议；交付记录见 §8）** | 你指出「第 3 题选项没换行、C 却丢了」「要能辨别水印」。**诊断（rapidocr 原始 32 个文本框）**：C 行是独立水平行（x=278.4 / h=30.7 / score 0.9993），只是 `C.` 标签被吃掉；`五星好`(h=187.5)、`xwl663赠送最`(h=343.1)、`X`(w=34 / score 0.866) 是斜向水印框。**根因三处**：`rapidocr_worker.ocr_page` 只回文本丢坐标 → 水印框按 (y,x) 混进正文流 → `splitter` 把无标签行无条件当上一选项续行（C 并进 B，水印再并到尾巴）。**方案 S1–S5**：坐标透传（`with_layout`，旧行为不变）、水印按「框高 > 2.5×行高中位数 + 孤立低置信小框 + ≤6 字短词兜底」过滤、选项缩进带补 C/D（实测差 12–14px）、选项结构校验 + 「可能粘连」标记、`PAPER_OCR_LAYOUT=0` 可回滚。≈**0.9d**，预期 5 页探针四选项齐全 **15/19 → 18/19**。**D1–D3 待拍板**（开工 / 补位策略 / 41 页图表页另立项） |
| **`plans/P4补答案扫描件与整卷验收_方案_v1.md`** | v1 | ✅ **已交付（2026-11-13，D1–D4 全按建议，交付记录见 §10）** | 你要求「把下一步三件事做完，先出预期效果图」，随后回「按建议」。**三件事全部落地**：①**P4 补答案扫描件异步化**（`pdf_text_layer_empty()` 判扫描 → `create_answer_draft/fill_answer_draft` → 路由 0.4s 返回 `parsing`、进度写 `message`、幂等、40 分钟惰性超时、弃稿不被救活；抽屉加角标/进度条/警告条/置灰/轮询）；②**41 页整卷真机验收**（顺带发现并修掉真问题：**真卷 56.97MB > 原 20MB 上限，今天根本传不进去** → 按类型上限 PDF 60MB + >8MB **流式落盘**）；③**P3 4 步界面验收清单** + 两份可点探针。**真机数字**：57MB 上传 **0.9s**、导题 **47ms**、41 页 OCR **240.6s（5.9s/页）** → **114 题**（四选项齐全 72）；43 页扫描答案件 **403ms 返回** → 冷 240.9s / 热 144.9s → **94 题**（有答案 92）；长任务期间旁路接口 6 次全 200（18–84ms）。**同时纠正一个自己测错的数**：原「22.8s/页 → 15.6 分钟」是与 pytest 并发测的，被抢占放大 4 倍，干净实测是 **4 分钟量级**。**诚实结论**：机制全通，但整卷拆题只有 63% 四选项齐全、题号缺 32 个（三位数 101–112 整段丢）→ 只能当草稿，后续建议见 §11。验收：P4 测试 **7 passed**、`-k "upload or material or answer"` **509 passed**、前端 **68 文件/736 用例**、`vue-tsc` 0、`gate_all` 9/10 |
| **`plans/P3扫描件导题_界面验收清单_v1.md`** | v1 | 📋 **给你点着验收用（2026-11-13）** | 4 步、约 3 分钟、**不写库**（用「放弃草稿」收尾）：①搜 `探针` 找到两份探针；②在 41 页那份点「导题」看**实时 OCR 进度**（1 秒出抽屉、`OCR x/41 页`）；③在 5 页那份看**19 题表格 + 4 条体检提示**（缺号 [6] / 选项不全 [3,9,17,20] / 无原图 / OCR 逐题核对）；④抽查 3 题后放弃草稿。附**预期内瑕疵 4 条**（多出的 `X`、选项不全、缺号、错别字）、**6 条「算不通过」判据**、回执模板与取证办法 |
| **`plans/扫描件OCR能力_方案_v1.md`** | v1 | ✅ **P0–P4 全部交付（P3 2026-11-13、P4 2026-11-13 晚；状态 2026-11-14 校准）** | 「扫描件无法上传，能否做 OCR」。**审计结论：链路位置早就留好了，但本机没有任何可用 OCR 引擎**——`C:\mineru_env\Scripts\mineru.exe` 不存在（报错文案就来自这里 `mineru_material_service.run_mineru`）、`D:\ocr-env`（PaddleOCR 子进程）不存在、主环境无 paddle/onnxruntime/rapidocr、tesseract 未装、easyocr 装了但**模型目录为空且 jaided.ai/github 不可达**、Docker 无 OCR 服务。**实测样本**：你那份扫描件 **24 页、前 5 页 0 字**；文字版对照 15 页每页 ~2000 字。**选型**：RapidOCR sidecar（py3.11 + 自带模型，CPU **≈4.6s/页**，24 页≈2 分钟）优于 MinerU（**71.2s/页**，24 页≈28 分钟）；easyocr/tesseract/云 OCR 均排除。**方案**：主后端 PyMuPDF 渲染 → 子进程 OCR → 文本回给 4 个消费方（答案 P1 / 文章讲义 P2 / 试卷导题 P3 / 运维 P4），不新增端点与表。**待拍板**：D1 是否批准 P0 装 venv（≈300–500MB）、D2 是否保留页图、D3 试卷导题是否一起、D4 以后是否接云 OCR |
| **`plans/旧版资料页_覆盖度审计与清理方案_v1.md`** | v1 | ✅ **A + S2 + S3 + S4 全部交付（2026-11-12），旧页路由已下线** | 「旧版是否已被新版覆盖、能否清除」。**结论：没有完全覆盖**——旧版还有 **4 项新版没有**的能力：xlsx 卡片智能导入、＋新建资料（富文本正文/封面配图/视频）、视频分片上传、卡片图片上传；管理面（列表/审批/试卷/考试/答案/导题/补答案）新版全面超过旧版。**红线**：R1 `.vtj` 页面禁止删除（只能不挂入口）、R3 禁改模板、R11 API 冻结（`/admin`、`/upload/image`、`/import/*`、`/video/upload/chunk` 不能删）、删路由要改 L6 105→104 与 `test_route_roles` 双改点。**三方案**：A 只摘入口（10 分钟、零风险）、B 摘入口+删路由（0.5h、暂时丢 4 项能力）、C 先搬迁再下线（2–2.5d、推荐）。**建议**：先 A 眼不见，再 S2 搬"新建资料"、S3 搬"xlsx 智能导入"，最后 B；视频 D2 建议不做 |
| **`plans/资料上传指南_v1.md`** | v1 | ✅ **已整理（2026-11-12 你要求）** | 「现在有哪些资料可以上传、怎么上传」的**可照做文档**：①四个按钮各干什么；②**5 类文件 + 1 类答案**表（试卷 / 讲义 / 文章 / 卡片批量 / 卡片单条 / 视频[无入口] / 答案），每类写入口、格式、限额、上传后是什么；③三条标准流程（试卷→建卷→上架→导题→补答案→开关；文章带正文；讲义只留档）；④上架=审批与 P5 联动；⑤限额速查（20MB/50 个/2GB/30MB/500 行）；⑥常见报错处理表；⑦当前库快照（124 行资料、上架 106/未上架 13/回收 5）；⑧如实标注两处缺口（扫描件暂不支持、讲义正文未入库） |
| **`plans/补答案上传后显示0题_缺陷修复方案_v1.md`**（含交付记录） | v1 | ✅ **已修复（2026-11-12 你反馈当天）** | 「上传答案 PDF 提示已解析 97 题，抽屉里却 0 行、确认写入 0 题」。**是缺陷，从 P4 上线就存在**：`POST /answers/parse` 回包走 `draft_payload(db, draft)` **不带 `items`**，而 `/latest`、`/drafts/{id}` 都带 → 前端 `upload()` 只读 `data.items` → 空；「关掉抽屉再打开」走 `/latest` 就正常（CDP 实测 97 行）；解析本身没错（draft #7 的 97 条 `answer` 与库 `current` **97/97 一致**）。**次要缺陷**：按钮数字按"有答案的题数"算，不是"会写入的题数"（这张卷实际写 0、保留 97）。**修法**：parse 回包 `with_items=True`+`can_edit`（与 `/latest` 同形）+ 前端无 items 时 `fetchAnswerDraft` 兜底；新增 `answerDraft.ts` 四个纯函数拆口径；按钮改「确认写入 X 题」、X=0 时禁用并解释（一致 / 不同但未勾覆盖 / 没解析出答案 三种原因）；空表文案区分。**验证**：后端 3 + 前端 8 新例、相关回归 **75 passed**、`vue-tsc` 0；真机同一份 PDF → 97 行 / 按钮「确认写入 0 题」禁用 / 提示「97 题与现有答案一致，无需写入」（截图 `assets/补答案修复/`）。验证用 draft #8 已放弃，无 pending 残留 |
| **`plans/已批准效果图_总览_v1.md`** | v1 | 📋 **整理归档（2026-11-12）** | 你要求「把所有批准的效果图整理一下」。把 11-05 以来**方案期**效果图从 55 个主题目录/382 张图里挑出来，按批准状态分两张拼图（真实渲染）：**已批准 24 张 / 7 主题**（资料管理 v3、管理端画风、资料库 L2、手机双 tab、答案上传、P5 联动、考试开关与定时，每条都写方案与裁定依据 + 落地状态）、**未批准 13 张 / 4 主题**（教师端待审稿徽标=落点未拍板、资料下发=待批准、AI 讲师=待批暂停、**资料多格式导入 P0=已实施但文档仍标待批准**的流程缺口）。实测/验收图 345 张另列目录清单；附复核命令与"缩略图按顶部裁切"的说明 |
| **`plans/三条静默错_修复方案与交付记录_v1.md`** | v1 | ✅ **已交付（2026-11-12）** | 你指示「先修这 3 条」。**①模考错题本**：`autoflush=False` 下重查未 flush 明细恒 `None`（`wrong_question_personal` 0 行）→ 改遍历 `created_details`，只收"答错且作答"；**②老资料去重**：98 条 NULL + 7 条哈希口径不一致 → 新增回填/归一脚本（备份、幂等、integrity）+ 只扫 NULL 行的兜底；实测回填 93、重算 7、NULL 剩 5（无正文行），同内容新建 → **409**；**③文章批量上架**：后端文档分支写死 `status=0` → 改为跟随 `publish`，前端加勾选（默认关）。新增 **10 passed**、合计 **67 passed**、`vue-tsc` 0、弹层勾选截图（`assets/文章批量上架/`）。含"老实说"：错题本未用线上卷 #5 复测（只剩 1 次机会）、文章未真上传测试文章 |
| **`plans/11月5日以来工作盘点与缺陷复核_v1.md`** | v1 | 📋 **盘点 + 复核（2026-11-12）** | 回答「11-05 以来做了什么、每项还有没有缺陷、AI 讲师方案是什么」。**盘点**：125 个提交 / 89 份新文档 / 6 条主线（资料上传管理 → 资料库三端 → 试卷考试 → 题库真卷 → 导航细节 → 验收资产），按 11-05/06/07/08/09/10-12 六段列到提交号。**复核（当前代码行号 + 当前库 + 真机接口，不复述历史）**：仍开放 **8 项**（4 处直写 `PUBLISHED` 的反向漂移、教师不能上传、手机结果页仍是 PC 页、批量改信息、L1-G 9/10、分批补录题序错位、验收账号 4/5 次、回收站 5 条 + 卷 #1 脏行）；本轮新发现 **5 条**；已闭环 **11 组**（含交卷 11 条、P5 联动、W2、`is_scored`、导航高亮、返回首页、**考试开关卡死**、**三项静默错**）。**AI 讲师**：DSL `lecture/1.0`、7 段式、SVG 讲师、状态机、三层键 87/12/403、`lecture_source.json`、T0–T10、交底书 B 三组权利要求、能力边界与 D1–D6 待拍板一次讲清。附取证命令与「pytest 必须从 `backend/` 跑」的实测坑 |
| `plans/近期交付_真人验收路线_v1.md` | v1 | 📋 验收路线（2026-11-09，配合三端验收清单） | 回答「这批交付真人在三端上会感知到什么、怎么逐步验」。**先列 9 条可感知变更**（结果页后缀 / 97 分卷不再 0·100 / `is_scored` 口径 / 手机整卷考试 / 断点续答与倒计时 / 手机平板状态标 / **PC 列表"以前看不到现在看得到"是唯一行为变更** / 批量一键上架 / 用时修复）；**分 6 阶段**：0 自检（只读探针 + 基线数字）→ 1 单账号 PC 冒烟 6 步 → 2 跨端续答（手机答 2 题退出再进、平板同卷、手机交卷看结果）→ 3 管理端开关联动（关→「未开放」、定时窗口、0 题卷）→ 4 边界（重复交卷、倒计时归零自动交卷、并发、考中关卷、断网）→ 5 数据对账 + 8 个回滚点；每阶段给预期/判据/耗时；末尾留一个待拍板体验点（"看得到点不了" vs 继续隐藏） |
| `plans/手机整卷考试与试卷列表状态_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09 你点单三项） | ①**手机整卷考试打通**：`mobile_answer.vue` 按 `?paper_id=` 分流（**不新增路由**，避开门禁 105 条基线），复用 `POST /exams/{id}/start` + `GET /exams/{id}/questions` + `POST /exams/{record_id}/submit` 三接口；考试中 `showResult` 恒 false（不泄露答案）、隐藏模式切换、题型行去重（新增 `typeLine`，但多选题的 `question_type_detail` 必须保留「多选题」否则 `isMulti` 失效）；**客观题每题都传（空串补齐）**，否则明细只建已答题、结果页显示「0 / 1 题」（自曝并已修）。②**列表考试状态**：`/api/exams/list` 每条带 `exam`（`contract.exam_state`，含 ready/reason/open_at/close_at/server_now）+ `answerable` + `exam_hint`；前端新增 `fetchExamPapers()`，手机/平板列表显示「可考 / 未开放 + 原因」角标与满分 tag；PC 仍走 `/api/papers/list`（P2 会过滤掉不可考卷，故无状态可言——有意差异）。③**批量一键上架**：先说清「批量上传对话框 / 列表多选批量上架 / 旧页 batchPublish」本来就有，真正缺的是 **API `POST /admin/batch` 只写 status 不联动卷**；已加 `publish` 开关 + `material_paper_sync.sync_materials()` 联动，并给批量建试卷资料补 `paper_code`/`placement` 透传（原来被白名单丢掉→联动取不到卷）。**验证**：`test_exam_p2_gate.py` **18 passed**（+3）、`test_materials_w2_consistency.py` **18 passed**（+2）、`vue-tsc` **0**；手机 390 真实跑通「开考→作答→交卷→结果页 0/97 分、0/97 题」并截图 4 张；联调造的 3 条 exam_record 已按守卫删除（备份 `before_cleanup_mobile_exam_test_*`，剩 1 条、integrity ok）。**已知边界**：无倒计时、无断点续答（`save_progress` 未接）、结果页复用 PC 版面、主观题仍需人工评分 |
| `plans/资料上传上架_学生三端_人工验收清单_v1.md` | v1 | 📋 验收指引（2026-11-09，含 6 张实测截图） | 回答「上传/上架是否完善、上架后学生三端能否查看与考试、怎么完整验收」。**机制盘点 22 个管理端点**（单/批量上传、立即上架走 P5 联动、上架/下架、建资料默认未上架、内容去重、导题草稿→确认、补答案、考试开关与定时窗口、ensure-paper、backfill、原件管理、软删回收站、分类规则、配图）＋**两道闸**（资料 status=1 可见 / `contract.exam_ready()` 才可考，前端只读 `paper.exam{open,ready,reason}` 与 `exam_hint`）。**实测基线**：资料 123（-1:4 / 0:13 / 1:106）、试卷 #1 ENDED + #2–#5 PUBLISHED（100/100/100/**97** 题、满分同值）、题库 397（全客观）、学生可见 行测 38 / 申论 27 / 公专 41（含 4 份试卷）、试卷 4 套、4 套卷 `exam[open=true,ready=true]`。**三端结论**：PC 闭环 ★★★★☆、平板 3.5（资料页=PC 页重定向、试卷/答题复用手机件）、**手机 3.0（查看好，考试跳 PC 试卷页与 PC 答题页——`mobile_answer` 只支持练题，代码注释自认"移动端答题页尚未开放"）**。**本轮顺手修 1 个残余缺陷**：`student_papers.vue:209` 写的是 `data.max_score || 100`（data 是列表响应体，永远没这个字段）→ 97 分卷显示「得分 0 / **100**」，改为 `r.max_score` 由模板 `|| p.total_score` 兜底，现为「0 / **97**」（图 07）；`vue-tsc` 0。含 **A–F 六组 33 步验收剧本**（上传/上架开关/PC/平板/手机/联动异常）+ 回执模板 + **6 条已知边界**（手机无常卷考试页、手机平板试卷列表无考试状态、平板资料页复用 PC、教师不能上传、批量文章不能一键上架、无 force 重建） |
| `plans/一致性收口_W2_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，W2 / 方案 D1·D3） | 把"资料怎么进库"四处口径收成一处：①`POST /admin` **默认未上架**（原来走模型默认 1 = 建好即审批通过）②`POST /admin/batch` 同口径 + **同内容跳过**并回 `skipped_duplicates`③上传新增「**立即上架**」开关（`publish=1`，且**必走 P5 联动**把卷同步 PUBLISHED）④`content_hash` 去重（单条 409 回已有 id / 批量 skip）⑤**教师可预览未上架**（判据用 `user_type` 而非 `role_level`——教师与学生 level 都是 1，按 level 会把教师挡掉）。真机 HTTP 四条全过（默认 0 / 重复 409 / staff 200·学生 404·游客 404 / 上架后 200 / `publish=1` → status 1），测试资料按守卫物理清除，`study_material` 回 123 行、`integrity ok`。**测试**：pytest 新增 **16 例**；连带修 `test_materials_admin_search` 夹具（原来两张卡内容完全相同，被新去重判 409 → 按真实语义改成内容各异）；vitest 62 文件/679、`vue-tsc` 0、`gate_all` **9/10**（唯一红=既有 L1-G，题数已从 300 变 397）。**已知边界**：无 `force` 重建参数、文章批量仍固定未上架、教师端页面还没有"待审稿"标识 |
| `plans/128入库与补答案_执行记录_v1.md` | v1 | ✅ 已执行（2026-11-09，按你授权） | ①确认导题草稿 #1 → **97 题入库**、挂卷 #5、`DRAFT → PUBLISHED`（资料已上架走 P5），学生试卷列表 **3 → 4 套**、`GET /exams/5/questions` 返回 97 题；②用 `2016江西招警…答案及解析（部分）.pdf` 走「补答案」：解析 **97/97**（全 L1）、冲突 0、写入 **filled=97**，卷内 97 题**答案与解析都齐**；题库 300 → **397**。**一处自曝失误**：入库时直接调接口确认，没在界面上删掉第 97 题那两张「有图待核对」的广告图（微信/淘宝横幅），学生能看到 → 已备份后清除（题干、选项、答案、解析未变，`integrity ok`），并写明教训：带「有图待核对」的题必须先处理图片再确认。备份：`question_bank.db.bak_pre_128_import_*` / `bak_pre_clean_q397_*` |
| `plans/答案上传_P4_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，方案 P4） | 答案**按 PDF 上传**：上传 → 四层取答案（L0 题号后直给 / L1 `正确答案为X` / L2 `故本题选X` / L3 `A项正确`）→ 逐题核对 → 「确认写入」只动 `answer` + `answer_analysis` 两列。新服务 `services/answer_ingest/`（extractor 纯函数 + service 读文件/校验/写入/30 天清理）、新表 `paper_answer_draft`、**6 个**管理端端点（API 面 351→357）。**用户 4 条决策落地**：①已有答案不同默认保留（`overwrite` 才覆盖）②推断层只给「采纳」建议不自动填 ③解析正文一起入库（无答案但有解析的单独计 `analysis_only`）④不做文件名自动匹配（只按卷上传，题号越界即阻断）。**最硬证据**：用解析器重算 4 套卷答案，与库里人工核对过的**逐题一致**（2019BJ 100/100、2017JS 100/100 含 #87 从 `A` 修正为 `ABCD`、2024GK 99/100）。**两个实测坑已修**：幻影题号（解析内 `2.重点环节` 被当题号 → 同号保留第一次）、列举被吞（`A、B、C 项：正确` → 列举不进 L0 + 成串推断 + 题型×字母数校验）。**测试**：pytest 新增 19 例、前端新增 5 例；vitest **62 文件/679**、`vue-tsc` 0、`gate_all` **9/10**（L4 曾因 library 直接 import ExamPaper 红过一次，改经服务层取卷后 PASS）。真机 HTTP 全链路跑过（解析 100 题 → 预览 → 放弃草稿，未写生产库），界面截图 `assets/答案上传_实际效果/管理端_补答案抽屉_2017江苏100题.png` |
| `plans/答案上传_PDF与Excel多通道_方案_v1.md` | v1 | ✅ **已批准**（2026-11-09 你回「按建议」；P4 已交付见上条） | 回答「现有答案都是 PDF，能否增加答案上传方式」。**实测 4 套卷对应答案 PDF**：题号覆盖 **397/397**、答案自动识别 **397/397**、仅 **1 题**（2017JS #87）与题型冲突需人工、解析正文中位 255–344 字 → **PDF 可做一等通道**。四层取答案 L0 题号后直给 / L1 `正确答案为A` / L2 `故本题选A` / L3 `A项正确` 推断（实测 L3 在 2024 套卷会错 16 题 → **默认不自动填**只给建议）。**5 个实测坑**：幻影题号（解析里 `2.重点环节` 被当题号，2024/2019 各 1 处，会把真实答案顶掉）、L3 不可靠、`A、B、C 项：正确` 被吞成 `A`（靠题型×字母数校验抓出）、多套卷混排（题号覆盖≠卷题数即阻断）、已有答案冲突（默认保留）。设计：新表 `paper_answer_draft` + 「补答案」抽屉（拖拽上传→四数字体检→逐题改→确认写入，只填空位、不改历史成绩）。工期 1.2d。预期效果图：`assets/答案上传_预期效果/管理端_补答案抽屉_预期效果.png` |
| `plans/上传即导题_P3_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，方案 P3） | 上传 docx/pdf 试卷**当场拆题** → 「解析草稿」（待确认清单）→ 管理端逐题核对（改题号/题型、删误拆、看图片归属）→ 「确认入库」才写题库并挂卷。新服务 `services/paper_ingest/`（`splitter` 纯函数拆题、`readers` docx 段落/pdf 版面坐标抽图、`service` 编排+确认+30 天清理）；新表 `paper_parse_draft`；6 个管理端端点（API 面 345→351）。**拆题口径**：题号 `1./1、/第1题`（"2023 年"不算题号）、选项一行多个/一行一个/跨行续接、题型段落状态机（`【题型】`/章标题/内联`（多选）`）、情境材料组内共享、汉字空格清理。**实测**：#128 2016 江西 docx → **97 题、题号 1–97 连续、四选项齐全 97/97**；2024 国考 pdf → **100 题（单选 70/多选 30）、8 组材料、25 图**，与库里人工核对过的分布一致。**修 4 个真 bug**：章标题被吸进 D 选项、下组材料正文混进上一题、二维码被当题图（改打「有图待核对」交人工）、入库后卷仍 DRAFT（补 P5 联动）。**为什么同步解析而非后台任务**：conftest 只覆盖 `get_db`，`SessionLocal` 仍指真实库 → 后台任务会写生产库。**测试**：pytest 新增 23 例、前端新增 5 例；vitest **61 文件/674**、`vue-tsc` 0、`gate_all` **9/10**（仅既有 L1-G）。**顺手修**：管理端列表 `file_count` 恒 0（补 group by + 2 例回归）、按你要求删除 `exam_record` #1 验证残留（备份 + integrity ok）。**待你确认**：#128 的 97 题是否入库（入库即学生可见第 4 套卷） |
| `plans/上传即建卷_考试开关与定时_P1P2_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，方案 P1+P2） | ①**P1 上传即建卷**：投放位∈{考试页,都投} 的试卷上传时就建草稿卷（卷名=文件名去扩展名；编号=表单科目兜底+文件名年份/地区/卷别；同编号幂等复用；缺年份/地区**不阻断上传**只回 hint；成功与跳过都写审计）②**P2 考试开关+定时**：`exam_paper` +3 列（`exam_open/open_at/close_at`，启动期自动 ALTER）；判定**读取时计算、不靠 cron**（`exam/contract.exam_ready/exam_state/open_conditions`，题量在缓存为 0 时回落关系表实数）；学生端三处同口径（试卷列表过滤、两条开考链路 400+人话原因、资料页「暂不可考」+原因）；管理端新增「考试（可进入）」列（开关+状态+定时摘要，0 题强制灰）+ `ExamGateDialog` 定时弹层（「快速填：今晚」按服务器日期、保存前效果预告、当前状态带 `server_now`）；**S2** 关闭时进行中的仍可继续/交卷（判定放在"复用未完成记录"之后）；开关与上架独立、关闭不删历史成绩。**修掉 3 个真 bug**：`0 or 1` 吞掉"已关闭"（状态算成 expired）、`question_count` 漏更把有题的卷挡在门外、1440 宽 12 列把「操作」顶出卡片。**真机验收**：探针 12 组断言全过（关闭→学生列表 3→2、开考 400「考试已关闭」、管理员仍可见、关闭后继续 `exam_id=1 is_continuation=true`、未到时间/已结束各 400 带具体时间、清空后恢复 3 套），快照式收场把 4 套卷恢复「开+不限时」；3 张真机截图（`assets/考试开关与定时预期效果/` 实现版列表、定时弹层、学生端未到时间暂不可考）。**测试**：新增 pytest 31 例（16+15）、定向回归 77 passed；vitest **60 文件/669 用例**、`vue-tsc` 0；`gate_all` **9/10**（仅既有 L1-G）。API 面按 R11 只登记 +2。**遗留**：P3 导题/P4 答案未动（#128 卷 #5 仍 0 题）、`exam_record` #1 是验证残留（去留待你定）、管理端列表 `file_count` 恒 0 属既有小瑕疵 |
| `plans/上传即建卷_上传即导题_考试开关与定时_方案_v1.md` | v1 | ✅ **已批准**（2026-11-09；P1/P2 已交付，见上条；P3/P4 待做） | 三条需求的完整方案：①**上传即建卷**（仅「考试页/都投」触发；编号=表单科目+文件名年份/地区/卷别，缺年份/地区则不建并提示；卷名=文件名；同编号复用）②**上传即导题**（docx 用 python-docx、pdf 复用已跑通的坐标法拆题 → 生成「解析草稿」→ 管理端「待确认（N 题）」对照页可改题号/题型/删误拆 → 点「确认入库」后挂卷；图片落 `static/questions/{qid}/`）③**考试开关+定时**（`exam_paper.exam_open/open_at/close_at`，判定按时间窗**读取时计算**、不依赖 cron；开关与资料上架独立、关闭保留成绩、0 题强制不可开；只对考试/都投的试卷显示）④**答案先留接口**：推荐 Excel 一行一题（题号｜答案｜解析，多选连写 ABCD），次选纯文本 `1 A`；压缩串/混排/图片答案列为不推荐；校验行数=题数、题号无缺口、单选取1字母多选≥2。含影响面五步（+7 端点需登记 API 面）、约 30 例测试、P1–P4 分批 **3.8–4.5d**、三层回滚、S1–S3 待确认。**#128 已完成**：编号 `GZ-2016-JX-T` + 卷 #5（DRAFT/0 题，未发布避免学生进空卷）。预期效果图：`assets/考试开关与定时预期效果/管理端列表_考试开关与定时_预期效果.png` |
| `plans/资料库L4_投放位与文章批量_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09，方案 L4 / W1 收尾） | ①**上传试卷弹窗**出现「投放位」三选一（仅考试页/仅资料页/都投，默认都投，带白话说明；讲义/文章不显示）②管理端列表新增「投放位」列（试卷显示 考试/资料/都投，非试卷 —），改信息弹窗可改（复用 `PATCH meta`，**不新增端点**，改完立刻同步卷状态）③**文章批量上传**：新组件 `ArticleBatchUpload.vue` 走解析链路（`import/upload`→轮询→`confirm{type:article}`），正文真解析、重复文件 409 逐行标「重复」、扫描件失败即报因不建空文章。后端**零改动**（L1 已提供 placement；解析链路 B3 已有）。抽 `MATERIAL_PLACEMENTS / placementLabel / placementTone / normalizePlacement`（+6 例单测）。**实测**：解析链路 `import→success→confirm created=1 content 162 字 status=0`、同文件再传 409；`vue-tsc` 0 错误；`vitest` **59 文件/653 用例全绿**；门禁 **9/10**（唯一红=既有 L1-G；L4/L6/L7 PASS）；3 张真机截图（`assets/资料库L4投放位与文章批量/`）。**已知边界**：文章入库仍"未上架"、扫描件依赖 OCR、xlsx 走卡片链路。**W1 全部闭环**；下一步 W2 一致性收口（POST /admin 默认未上架、教师可预览待审、上传即上架开关、创建通道去重） |
| `plans/手机端资料类型双tab_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-09） | 手机端科目 tab 下加第二行「讲义/文章/卡片/试卷」类型 tab，两级过滤（`GET /api/materials?subject=&type=`，**零后端改动**）；每类专属渲染（讲义=在线阅读+下载原件、试卷=元数据+下载原卷+去考试/不可考原因、卡片=保留 3D 栈、文章=点开读正文）；空态大字「无资料」+「{科目}还没有『{类型}』资料」垂直居中；深链 `?subject=&type=`，物理非法值回落默认「卡片」；移除 L3 两个横滑区，PC 不动。抽 `MOBILE_TYPE_TABS / DEFAULT_MOBILE_TYPE / normalizeTypeTab / emptyTextOf` 纯函数 **+3 例单测**（该文件 18 例）。**过程中修两个界面问题**：①类型 tab 被科目行 sticky 压掉半截 → 两级 tab 包进 `.tabbar` 统一 sticky；②空态贴屏幕底部 → `main.list` 加 `v-if="materials.length"` + `.empty-page{flex:1;justify-content:center}`。**验证**：`vue-tsc` 0 错误；`vitest` **58 文件/647 用例全绿**；CDP 390×844@2 三张真机截图（`assets/手机端双tab实际效果/`：公专试卷 3 条 / 行测试卷空态 / 公专卡片栈）；验收 8 条全过。**已知边界**：视频无 tab（全库 0 条）、tab 不显示数量、切科目保持类型。**下一步 L4**：上传投放位 + 管理端列 + 文章批量上传 |
| `plans/手机端资料类型双tab_方案_v1.md` | v1 | ✅ **已交付**（L3 双 tab + 后续 L4；见 `手机端资料类型双tab_交付记录_v1.md`） | 回答「手机端科目 tab 下再加资料类型 tab（讲义/文章/卡片/试卷），两级过滤；没资料的科目-类型显示『无资料』」。**实测**：已上架 行测(文1/卡37/讲0/卷0)、申论(1/26/0/0)、公专(1/36/0/`3`)，视频全库 0 条；`GET /api/materials` 早已支持 `type` → **零后端改动**。**做法**：二级 tab（顺序 讲义/文章/卡片/试卷）+ `activeType` + `library.load({subject,type})`；每类一种渲染（讲义=在线阅读/下载原件、试卷=下载原卷/去考试+不可考原因、文章=读正文、卡片=保留 3D 栈+列表）；空态=大字「无资料」+「{科目}还没有『{类型}』资料」；深链 `?subject=&type=`；PC 不动。**推荐移除 L3 两个横滑区**（否则同资料出现两次）。新增 `MOBILE_TYPE_TABS / emptyTextOf / normalizeTypeTab` 纯函数 + 4–5 例单测。**7 个待拍板 D-T1~T7**（视频是否加第5 tab、横滑区去留、卡片栈保留、是否显示数量、空态文案、**默认 tab 建议"卡片"**、PC 是否同步）。验收 8 条；工期 0.4–0.6d；批准后先出预期效果图再动代码 |
| `plans/资料库L3_手机端资料页_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，方案 L3） | 手机 `/mobile/materials` 加「📘 讲义」「📄 试卷资料」两个**横滑区** + 详情弹层补元数据/原件列表/逐个下载/去考试；`typeName` 补讲义与试卷；支持 `?subject=` 深链；`.list` 只排"其余"类避免重复。抽 `groupShelfItems()` 纯函数（讲义/试卷/其余）+ 3 例单测（该文件共 15 例）。**同时修用户反馈**：「点卡片进翻卡页」入口在 L2 丢了 —— 不是文件被删（`src/views/pc/material_detail.vue` 与 `/materials/detail` 路由一直在，实测正常渲染），而是 L2 把卡片改成"就地翻转"没再跳详情；已改回 `openCardDetail → /materials/detail?subject=X&id=N`，角标文案「进入翻卡学习 ›」。**验证**：`vue-tsc` 0 错误；`vitest` **58 文件/644 用例全绿**；**CDP 真机尺寸截图**（390×844@2，`--window-size` 在 Edge headless 有最小宽度会假性裁切，改用 `Emulation.setDeviceMetricsOverride`）三张存 `assets/资料库L3手机端/`；截图时临时上架 #121 拍讲义区，**拍完已复原 status=0**，种子登录页已删除。**已知边界**：手机"在线阅读"用弹层渲染（与 PC 阅读器非同一实现）；手机卡片仍就地翻转+弹层详情；库里 2 条讲义都未上架（上架即现）。**下一步 L4**：上传投放位三选一、管理端列/改信息、文章批量上传 |
| `plans/资料库L2_学生端资料页_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，方案 L2） | 学生端 PC/平板「备考资料」换新页：`src/views/student/materials.vue`（手写，非 `.vtj`）+ 三条既有路由换 component（**不新增路由**，L6/L7 105 不变，旧页保留可一行回滚）。六分区=视频×2/文章/**讲义**/**试卷资料**/卡片；讲义卡〔在线阅读〕〔下载原件〕（无正文时阅读器明确"只有原件"），试卷卡 `2024·国考·题本｜100题·100分·120分钟｜编号` +〔下载原卷〕〔去考试〕，不可考时**给具体原因**（未建卷/卷里没题/未发布/投放位=仅资料页）并置灰。抽 `src/utils/materialShelf.ts` 纯函数（**12 例单测**，L3 手机端复用同一口径）+ `api.ts` 补 9 个类型字段；后端列表补 `paper` 区块与 `chapter_count/word_count`（只加字段，API 面仍 343）。**验证**：`vue-tsc` 0 错误；`vitest` **58 文件/641 用例全绿**（原 57/629）；dev server transform `materials.vue` **200/82,357B**；真实库列表 xingce 38 / shenlun 27 / gongzhuan 40，3 套试卷均带完整元数据与 `answerable=true`。**已知边界**：库里 2 条讲义都 `status=0` 学生暂看不到（上架即现）；#125/#126 无原件故〔下载原卷〕置灰；手机端待 L3；「去考试」跳考试页不直接开考（避免留进行中记录）。**真实截图**：`assets/资料库L2实际效果/学生端公专资料页_仅试卷与文章.png`、`…_含讲义.png`（讲义那张是临时上架 #121 拍的，拍完已复原）。**过程中修掉两个问题**：①`el-dialog` 在本项目不可用（Element Plus 只按需 import，未全局注册 → 插槽内容摊在页面底部）→ 改自绘弹层；②`vite.config.ts` 的 `devRuntimeSafety` 用 `WeakMap.set(response.socket)`，socket 为 null 时抛错**直接把 dev server 干掉** → 加空值守卫（开发期插件，不进产物）。**下一步 L3 预期效果**：手机 `/mobile/materials` 加两个横滑区 + 下载 + `typeName` 补中文名 |
| `plans/资料库投放位_L1地基_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，方案 L1） | 投放位地基（**后端**）：`study_material.placement`（exam/library/both，**NULL=按类型推断**——试卷 both、其余 library；刻意不给 Python 默认值，否则老代码建的试卷行会变成"仅资料页"、上架不发卷，实测会让 5 条既有 P5 用例失败）。启动期自动 `ALTER`+索引+回填（真实库实测：**3 试卷 both / 119 其它 library**）。口径统一为「资料库可见=`status=1` 且 `placement∈{library,both}`；考试可考=`paper_type=PUBLISHED` 且 `placement∈{exam,both}`；原件可下=管理员或（上架且含资料库）」。改 6 文件：models/main/services·material_paper_sync（`placement_of`+`exam_side`，`_has_other_published` 只数含考试页的行）/services·material_files（`can_download` 加 placement，堵住"知道 file_id 就能下仅考试原卷"）/materials.py（`_placement_of`、列表过滤+`placement/file_count/has_files`、详情补 `files/placement/doc_meta`、上传收 placement 并校验、`PATCH meta` 可改并立即同步、预览回 placement、下载传 placement）+ 新测试 13 例。**验证**：13 新例全绿；`-k "material or paper or exam"` **452 passed**；门禁 **9/10**（唯一红仍 L1-G 语料下限，L4/API 面 PASS）；线上核对学生仍 3 套卷/40 条公专资料、#127 详情带 `files[1]` 与 `download_url`、原卷下载 200/1,354,909B、管理端预览 `placement=both`。**未做**：学生端新页（L2）、手机端（L3）、投放位 UI 与文章批量（L4）、`POST /admin` 默认未上架（W2）。**下一步 L2 预期效果图**：`assets/资料库L2预期效果/学生端备考资料_讲义与试卷_预期效果.png` |
| `plans/资料库_讲义与试卷展示及投放位_方案_v1.md` | v1 | ✅ **已批准（2026-11-08），L1+L2 已交付** | 回答「讲义/试卷加学生端页面 + 试卷分考试/资料页 + 上传选投放位 + 讲义三端 + 文章批量上传」。**核心**：新增 `study_material.placement`（`exam`/`library`/`both`），把「审批（status）」与「去向（placement）」正交——资料页可见 = `status=1 且 placement∈{library,both}`；考试页可考 = `paper_type=PUBLISHED 且 placement∈{exam,both}`，P5 只加一个 `exam_side` 判断（ENDED/一码多资料/软删语义全保留），**不新增发布入口**。**学生端**：踩 R3（`.vtj` 模板不能改，且 DSL 实测与模板不同步）→ 新建手写 `src/views/student/materials.vue`，三条既有路由换 component（**不新增路由**，L6/L7 105 不变），六分区=视频×2/文章/**讲义**/**试卷资料**/卡片；讲义抽屉=在线阅读+下载原件，试卷抽屉=年份/地区/卷别/题量/总分/时长/编号+下载+「去考试」；平板走 redirect 自动复用，手机手写页同步加两区（三端）。**后端只加字段**：brief 加 `placement/has_files/file_count`，detail 加 `files/placement/doc_meta` → API 面仍 343。**文章批量**：走解析链路（`import/upload`→轮询→`confirm{type:'article'}`），正文真解析、复用 409 双保险；扫描 PDF 需 OCR，失败即报因不建空文章。**上传选投放位**：`MaterialBatchUpload`（preset=paper）三选一，默认「都投」；改信息复用 `PATCH meta`（不新增端点）。**影响面五步 + 22–26 后端/12–16 前端用例 + 三层回滚 + 分批 L1–L4（3.1–4.0d 含测试文档）+ 8 个待拍板决策 D-L1~L8 + 重构后的四波次下一步建议（W1 本方案 / W2 一致性收口 1d / W3 A1 发布收敛 1–1.5d / W4 语料扩容等）** |
| `plans/资料上传与可见性_现状审计_v1.md` | v1 | 📋 现状审计（2026-11-08，实测） | 回答「上传机制是否完善、上传后是否所有学生可见」。**结论：上传 ≠ 学生可见** —— 实测上传一份 3KB 讲义 → 库 `status=0` → 学生列表 `total=0`、详情 404；管理员点「上架（=审批）」→ 学生列表/详情/原件下载全通（200/3094B/%PDF-）；再下架 → 立刻 404。上传弹窗已明写「导入后为未上架，需再点上架」；`materials.vue:477` 注释「P0 裁定：上传默认未上架，上架这一个动作就是审批」。**库内分布**：122 行 = 上架 105 / 未上架 13 / 回收站 4。**体检 16 项**：原件留档·格式白名单·20MB 上限·magic 校验·sha256 去重·同名 docx+pdf 合并·上架下架·P5 联动·软删恢复·审计·三端入口 均 ✅；**缺**：上传即上架开关（`publish` 后端有前端无）、上传后不自动建卷/导题、类型靠手选、无班级/个人下发（全库无 `material_target`，唯一可见性列是 `status`）、教师看不到未上架资料（详情端点对所有角色都要 `status==1`）。**三个真问题**：D1 三入口默认值不一致（文件上传 0 未上架 / 智能导入 0 / `POST /admin` **创建即上架且忽略 status**）；D2 `publish` 参数事实不可达；D3 教师无法预览待审资料。**建议**：先做 D（0.2d）+ 统一 D1 默认不公开；B（上传即上架开关 0.3–0.5d）/C（按班下发 1.5–2d）待拍板。复现脚本 `_run/probe_upload_visibility.py` 等 3 个。**§8 追加三问**：①上架后接口层全学生+游客可见，但**页面层只有 视频×2/文章/卡片 4 个分区，讲义与试卷无展示位**（手机页不传 type 会混入，但详情 `content=0` → 空白），且学生详情不返回 `files`、前端无原件下载入口；②批量上传覆盖 讲义/试卷（50 文件/2GB 队列，同名 docx+pdf 合并）、卡片（xlsx 词库列映射 + `POST /admin/batch`）、文章仅 API 无按钮、视频不走文件（`video_resource`）；③去重矩阵：文件通道 sha256 去重 + 格式 magic + 20MB 三道防线（实测同文件重传 `duplicate=true` 复用、同名不同内容新建第二条、`.txt`/假 docx 均 400），JSON 创建与批量创建**无去重**（实测各建两条）。**§8.4 事故**：清理探针时 `where title like '_%'`（`_` 是通配符）误清空 `study_material` 122 行 + `material_file` 4 行，已用快照逐行还原并重做 #127 真 PDF，题库 300 题/卷#4 100 条关系未受影响、`integrity_check=ok` |
| `plans/考试开考不落库_修复记录_v1.md` | v1 | ✅ 已修复（2026-11-08，你实测触发） | 学生点「开始考试」→ 交卷弹「考试记录不存在」。**根因**：`services/exam_service.py:start_exam` 只 `db.flush()` 不 `db.commit()`，而 `get_db()` 请求结束 `db.close()` → 未提交 INSERT 被回滚；接口却返回 `exam_id`。前端「开始考试」走新路由 `/api/exams/start`（坏），「再做一次」走老路由 `/{paper_id}/start`（一直有 commit，好）。**复现**：`POST /api/exams/start?paper_id=4` → 200 `exam_id=1`，同时 `select count(*) from exam_record` = **0**；`POST /api/exams/1/submit` → 400「考试记录不存在」。旧现象解释：`exam_record` 长期 0 行 = 谁都考不成。**修法**：flush 后补 `db.commit()` + `db.refresh()`（1 行，不动路由/模型/API 面）。**防回归**：新增 `test_start_exam_persists_record_across_rollback`（`rollback()` 模拟请求结束）——临时去掉 commit 实测 **FAILED**，恢复后本文件 **6 passed**。**端到端**：开考→库内确认记录→交卷 200 `total_score=2.0 / max_score=100 / scored_count=100`→`is_completed=1,is_scored=1`、明细 100 行→`/api/exams/records` 200、`/records/{id}` 200；随后清空复测记录（回 0 行）。**债务**：全仓 73 处 `flush()`，"服务层 flush + 路由直接 return" 组合有同类风险，建议列巡检 |
| `plans/2024国考公专_真卷入库与上架_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，真卷三步全通） | 2024 国考公专真卷「抽图 → 100 题入库 → 资料上架」。**①抽图**：不再靠人眼猜，`attribute_figures.py` 用 PyMuPDF 版面坐标把图归到"上方最近的题/情境段"（锚点＝100 个题号 + 8 个情境段），43 个图对象 → 23 张真图 → **28 题挂图**；丢弃 20 个（文字被切成图片的碎条 110/113/87/89/91/92/93/82–84 等 + 两组重复件 **120↔123**（雨东派出所巡逻警组位置图）/ **136↔139**（诈骗高发类型统计图），各留高清）；**浮图实证**：xref120 版面落在题 74 正文里，但题 74 讲房檐调解、题 75 明写"见下图"→ 归题 75。反向校验"提到图却没图"＝0。**②入库**：`batch-parsed` + `paper_code=GZ-2024-GK-T` 归卷，首轮 95/100，**5 题（41/48/49/75/94）因大图 base64 触发 R-LONG 50000 上限**→ 加 `--static-urls` 把原图落 `static/questions/_seed2024/` 后补录成功（**没有降低校验上限**）。题库 200→**300**、卷 #4 关系 0→**100**、`question_count=100`、28 张图文件 28/28 命中、残留 base64 **0**；选项 4/题 100/100、解析≥30 字 100/100、单选 70/多选 30、总分 100、**答案与解析 PDF 逐题比对 0 处不一致**（99 题原文直取，仅第 81 题推断 D，解析原文"故BC 错误，D 正确"）。**③上架**：#127 原是 36KB **样张 docx**（329 字 2 题）→ 删样张原件、传真 PDF（1,354,909 字节 primary）、`PATCH meta`（2024/国考/题本/100 题/100 分/120 分）、卷名同步、`PUT status=1` → P5 `DRAFT→PUBLISHED`，学生 `/api/exams/list` **2 套→3 套**；学生预览卷 #4 = 100 题 + 28 题含图 + 30 题多选，静态图 200/23289B。**坑**：`book_kind` 只认 `A/J/T`（传 `zhenti` 400）；`answer_analysis` 才是解析字段名。**自查抓到的真错位（已修）**：补录的 5 题把 `question_order` 追加到 96–100，导致 41 之后 60 条题序与题号不一致（预览里题 41 排在第 97 位）→ 按 `question_number` 重排为 1–100 后复核 0 不一致（题干/答案未动，卷 2/3 本来自洽）。**未做**：没跑"真开考"（会在学生账号留进行中记录）、5 张大图文件只在本地 static（原始图已提交在 assets，可重跑复原）、`badge` 仍显示编号。回归 **50 passed**；门禁 **9/10**（唯一红仍是 L1-G 语料下限 300＜3085）；快照 `backend/data/question_bank.db.bak_pre_2024gk_import_20261108_203855` |
| `plans/A2_导题归卷_交付记录_v1.md` | v1 | ✅ 完成（2026-11-08，A2 第二批） | A2 第二批：题目导入按 `paper_code` 归卷。**根因**：`_get_or_create_import_paper` 只会"同名复用"或 `generate_paper_code()` 新建 → "上传真题→建卷→导题"会生成第二张卷（`PAPER-xxxx`），两侧编号对不上。**改法**：加 `paper_code` 入参（命中复用含 ENDED 复活 / 未命中用该编号建卷 / 不传保持旧行为），`batch-parsed` 与 `confirm` 两处调用接上。**同时修掉一个真缺陷**：<5 题阈值原本把"已有卷"也挡了（题数<5 直接返回 None、题目静默不挂卷）→ 把按编号命中挪到阈值之前。**验证**：7 条单测 + 50 条导入回归全绿；线上 6 题带编号 → `paper_id=4` 无新卷；**2 题（<5）→ 关系 0→2**（修复前为 0）；临时题已清理，库回 200 题/200 关系/卷#4=0 题。**未做**：#127 的 119 题（缺题源）、`.vtj` 导入页的归属入口 |
| `plans/A2_试卷资料生成可作答卷_交付记录_v1.md` | v1 | 🚧 第一批完成（2026-11-08，建卷能力） | A2 第一批：把「试卷资料」变成题库里的可作答卷（解决 #127"有资料无卷"）。**新增** `services/material_paper_link.py`（用 `paper_code`→回落 `badge` 建 `exam_paper`，`paper_type` 固定 `DRAFT`，元数据取"订正>解析"缺省 120/100，幂等不覆盖已有卷）+ `POST /api/materials/admin/{id}/ensure-paper`（`_require_admin`，审计「生成可作答卷」，**白名单登记不重算 343 基线**）+ 页面试卷行「建卷」入口（成功/已存在两种提示）。**9 例单测全绿**（含 A2×P5 串联：建卷→上架→自动 PUBLISHED）；线上实测 **#127 → `exam_paper#4 GZ-2024-GK-T DRAFT`(0 题)**、二次点击 `created=false`、学生端仍 2 套、管理员预览 200；`vue-tsc` 0 错误、`vitest` 629 全绿、**门禁 9/10（L4 PASS）**。**未做**：导题按 `paper_code` 归卷；#127 的 119 题（实测题库 200 题全被 #2/#3 占满，需新题目数据） |
| `plans/A7_批量操作搬进新页_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08） | A7：批量操作搬进新资料页。**新增** `src/utils/materialBatch.ts`（选择/全选/半选/目标筛选/结果文案纯函数）+ **9 例单测**；**改** `materials.vue`：首列勾选 + 表头全选（indeterminate）+ 选中后批量条（上架/下架/删除/取消）、逐条 `PUT /admin/{id}/status`（**0 新端点**）、批量删除走 `DELETE /admin/batch`（软删可恢复 + P5 联动卷 DRAFT）、换页/换筛选自动清空勾选、回收站视图不显示勾选、部分失败逐条报因。**验证**：`vitest` **57 文件/629 全绿**（原 620+9）、`vue-tsc` 0 错误、Vite 编译冒烟 200、**线上按页面请求序列实测**（建 3 条临时卡 → 批量上架 → 批量删除 `deleted:3` → 回收站 3 条可恢复 → 物理清理，库回 122 行）。**顺带发现**：`POST /api/materials/admin` 忽略 `publish` 参数（新建即上架），未修已记录 |
| plans/下一步四项工作_范围说明_v1.md | v1 | 📋 范围说明（2026-11-08；**A6 已按你裁定撤销**，剩 A7/A2/A1） | 回答「A6/A7/A1(P0–P4)/A2(P2) 分别要做什么」。**A6 彻底删除**：回收站只软删无 purge，要加 `…/permanent`（仅 `status=-1`、影响面预览、内容寻址原件共用时不删文件、审计记 ID）→ CLI 0.1d / 全量 0.5d（+1~3 端点需登记 API 面）。**A7 批量搬进新页**：新页无勾选，旧页有「批量删除走 `/admin/batch` + 上/下架逐条 status」；要加 checkbox/全选当前页/批量条/二次确认/部分失败提示，0 新端点，0.3d。**A2 P2 题目线**：上传只建资料不建卷（#127 实证），要打通「资料→建卷（复用 paper_code）→导题写 relation（confirm 增 paper_code）→上架即 PUBLISHED（P5 已有）→#127 补成第 3 套可考卷」，1–2d。**A1 P0–P4**：页面层**已基本收敛**（`/admin/papers` 已 redirect、审批页无路由、侧栏无试卷管理），剩下是**接口层**——4 处仍能直写 `PUBLISHED`（`papers.py:442`/`paper_generation.py:748`/`admin_approval.py:245`/`teacher.py:1383`）、`admin_approval` 路由仍注册、教师端 `/teacher/papers/{id}/publish` 仍直发；要做登记式收敛→入口下线→投影化→门禁同步，0.5–1d。含**四条依赖图**与**建议顺序 A7+A6 → A2 → A1**（先建新路再拆旧路，与早前建议相反并给了理由）+ 每条 D-Ax 待拍板 |
| `plans/遗留清理_第一批_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，你批准的「1+2」） | 清测试数据 + 修两条既有红 + 放开教师预览。**数据**：硬删 #123/#124「同名资料」+ #128–131「搜索专用-*」，连带 2 条 `material_file` 与 2 个孤儿原件；`study_material` **128→122**、在用 **119→118**、`material_file` **6→4**、`integrity_check=ok`（快照 `…bak_before_p5_20261108_164420`）。**两条红**：A4 分类器测试断言改 `lecture`（B3 起文档一律讲义）；A5 `exam-records` 守卫改用 `app.openapi()['paths']` —— 原写法在新版 FastAPI 下 `APIRoute` 取不到、**守卫实际已失效**。**教师预览（D9）**：`papers.py` 守卫 `<2`→`<1`、两处 `allow_unpublished >=2`→`>=1`；顺带修掉夹具陷阱（`conftest.test_user` 是 student 但 `role_level=1`，本文件自带 `student_headers` 用 role_level=0）。**线上实测**：学生 preview ENDED 卷 404、教师 **200**（改前 404）、管理员 200。**验证**：3 个被修文件 34 passed；全量 `-k "exam or paper or material"` 420 passed（唯一失败是 `test_invalid_order_is_422` 拿 `id_desc` 当非法值——已改成 `relevance` 并补 `test_id_desc_is_accepted`，复跑 14 passed）；**门禁 9/10**（唯一 FAIL = L1-G 数据红，L4 PASS） |
| `plans/遗留缺陷与未做事项_清单_v1.md` | v1 | 📋 **清点清单**（2026-11-08；A3/A4/A5/C1/C2 已清，**A6 已撤销**，A1/A2/A7/A8 与 B 组未动） | 回答「还有哪些缺陷和未做」。**A 真缺陷 8 条**：A1 反向漂移仍在（4 处可直写 `PUBLISHED`，需 P0–P4）；A2 上传≠可考（#127 至今无卷，需 P2 题目线）；A3 教师看不到草稿卷预览（`role_level` teacher=1 vs 阈值 `<2`，5 分钟）；A4/A5 **两条既有红**（分类器测试没跟上 B3、exam-records 守卫因新版 FastAPI `_IncludedRouter` 实际已失效，均用 `git stash` 证明与本批无关）；A6 **回收站只进不出**（无彻底删除）；A7 批量操作只在旧页；A8 试卷元数据只有单条编辑。**B 计划未做 14 项**（P0–P4 收敛 / P2 题目线 / P5-4 提示 / 批量改信息 / PDF 讲义大纲 / 章节跳正文 / C3 facets / 学生端资料页 / 事件总线 / 画风 E1–E5 / 下发 material_target / 规范 v2 / AI 讲师暂停 / MinerU OCR）。**C 数据环境 6 项**（我造的 4 条 `搜索专用-*` 测试卡 #128–131 与 #123/#124「同名资料」待清、回收站历史 4 条、8000 端口债、3 份 40MB 快照、`_run/` 20+ 探针）。**D 技术债 3 条**（`services/` 跨域写不在扫描面、`list_time` 依赖 ORM 默认、`seq` 口径写死）。附**建议处理顺序**（先清数据+还红 → A3 → A6 → A7 → P0–P4 → P2）与清理命令 |
| `plans/资料管理_ID连续与排序_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，方案 A 落地） | ID 连续与排序的实现与验收记录。**改了什么**：`StudyMaterial` 新增 `list_time`（排序键，默认 now；启动期自动补列 + 回填 128 行）+ `admin_list` 的 `order` 支持 `id_desc`（**默认**）/`id_asc`/`created_*`、排序键 `list_time desc, material_id desc`、响应每行加 `seq`（当前筛选内倒序名次，首行=total）、**恢复时 `list_time=now` 置顶** + 前端「编号」列改显示 `seq`（回收站显示「—」，悬停看真实 ID）+ `scripts/backfill_material_create_time.py` 补回 58 条缺失上传时间（dry-run 默认、标"补记"）。**实测**：`create_time` 空值 58→**0**；默认列表 `total=119`、p1 `seq 119..110`、翻 12 页 **0 重复**、`seq` 连续到 1；恢复 #46 → 首行 `seq=120=total` 且 `create_time` 不变、`list_time` 变新；再删回 → total 回 119。**8 条 pytest 全绿**；`vue-tsc` 0 错误；**vitest 56 文件 / 620 通过**；**门禁 9/10**（唯一 FAIL = 既有红 L1-G；L4 PASS = API 面仍 343、边界新增 0）。**边界**：未重排主键（`material_id` 一行未改）、未补历史缺号 11–13、58 条时间属"补记" |
| `plans/资料管理_ID连续与排序_修复方案_v1.md` | v1 | ✅ **已按方案 A 实施**（D1=A / D2–D5 按建议；见交付记录） | 回答你提的两个缺陷（列表 ID 从第二页起不像降序 / 删除后 ID 不减、最大 ID≠总数、恢复应置顶拿新号）。**诊断抓出真因**：①**58 条历史资料（ID 48–105）`create_time` 为 NULL**，而列表 `null_last` 把它们排到最后 → 页面出现 `107,106 → 45,44` 的跳变；**排序本身稳定**（实测翻 4 页 40 行、0 重复、严格递减；其余 70 条 ID↔时间 0 逆序）。②"ID 与总数不符"来自**软删除保号**（回收站 9 条仍占号）+ 历史缺号 11–13 → 128 行 / 最大 131 / 在用 119；**"ID 与试卷绑定"不成立**（关联键是 `paper_code`，`exam_paper` 无 `material_id` 列，引用面只有 progress 24 / share 1 / file 6）。**三方案**：**A 展示序号（推荐，0.65d，零主键手术）**：默认排序改 `material_id desc` + 补回 58 条时间 + 响应加 `seq`（倒序名次，首行=总数）+ 恢复置顶用新增 `list_time` 列；B 真重排 PK（1.5–2d，需级联 3 表 31 行、**518 条审计 `material:` 文本错位**、旧链接失效、写放大，不推荐）；C 物理删+重排（与软删除裁定冲突，否决）。含**逐条需求对照表**、12 条测试点、回滚三层、D1–D5 决策 |
| `plans/试卷上传到学生开考_现状链路_v1.md` | v1 | ✅ 现状实测说明（2026-11-08，只读探针，未改代码） | 回答「现在上传试卷后，学生端考试的机制是什么样的」。**结论：上传 ≠ 可考** —— 上传只落 `study_material(status=0)` + `material_file(primary)` + `paper_code`（C2a 解析），`materials.py` 全文对 `ExamPaper` **只有只读桥**，**零建卷能力**。学生端入场券 = `exam_paper.paper_type='PUBLISHED'`。**7 步全景**：上传 → 上架（只改 status）→ 另建卷（6 条链路/8 处 `ExamPaper(`）→ 配题（`paper_question_relation`，空则 404「该试卷暂无题目」）→ 学生列表（主路径 `GET /api/papers/list`，`role_level<2` 仅 PUBLISHED）→ 开考（主路径 `POST /api/exams/start` → `ExamService.start_exam:46`）→ 进度/交卷/成绩（历史成绩不按 `paper_type` 过滤，下架不丢分）。**3 个断点**：A 上传→卷无自动通道（#127 实证）、B 上架→可考不联动（P5）、C 卷→资料仅反方向可用（补录）。**新发现 R8**：`GET /api/exams/preview/{id}`（`exams.py:651`→`exam_service.py:464`）**漏判 `paper_type`**，学生 token 请求 `ENDED` 的 #1 实测 **200**（对照 `papers.py:229` 同功能接口有守卫）→ 草稿卷配题后题干/选项可被学生直读（不含答案解析）。**实测证据**：学生 `/api/papers/list` 与 `/api/exams/list` 同返回 2 条（#2/#3），`#127 GZ-2024-GK-T` 不在其中；`/api/exams/1`、`/1/questions`=404、`/start`=400。探针 `_run/p5_exam_probe*.py` |
| `plans/P5批_人工验收清单_v1.md` | v1 | 📋 验收指引（2026-11-08，本轮 3 项交付） | 覆盖 **R8 预览修复 + P5 联动 + P5-0 巡检脚本** 的手工验收剧本。**快速版 8 分钟 Q1–Q6**（管理端 #125 下架 → 统计 105/14→104/15 → 学生端 2 张卡变 1 张 → 日志出现 `下架；可作答卷 GZ-2019-BJ-T PUBLISHED→DRAFT` → 再上架全复原）；**完整版** A 组 4 项（`scripts/verify_p5_acceptance.py` 一键只读探针，期望 `7/7 PASS`：学生看 ENDED 卷 404／PUBLISHED 卷 200 带 100 题／管理员 200）+ B 组 9 项（抽屉徽标「已关联·可考/未发布」、旧链接进不去、删除进回收站后仍不可考、恢复=未上架、批量删除、#127 上架 no-op）+ C 组 2 项（巡检漂移 0、门禁 9/10）。含**基线数字、会动真实数据的声明与逐步复原动作、6 条"看不到变化是正常的"、回执模板、5 条排障**（学生端强刷 / `MATERIAL_PAPER_SYNC=false` 应急 / 从地址栏进 `#/student/papers`） |
| `plans/P5_上下架联动_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，A3 落地） | P5 的实施与验收记录。**改了什么**：新增 `exam/contract.py`（考试域状态机：`DRAFT/PENDING/APPROVED`↔`PUBLISHED`，`ENDED` 永不改写，不 commit）+ `services/material_paper_sync.py`（取键 `paper_code`→回落 `badge`、一码多资料判可见性、拼审计文案）+ `config.MATERIAL_PAPER_SYNC` 开关 + `materials.py` **3 处触发**（`PUT /admin/{id}/status`、`DELETE /admin/{id}`、`DELETE /admin/batch`），全部改为「改状态 → 同步卷 → 写审计 → 一次 commit」。**13 条 pytest 全绿**（含无卷 no-op、ENDED 不复活、PENDING→PUBLISHED、软删联动、批量删除、幂等、**联动抛异常则资料状态不提交**、审计文案、卡片不触碰卷、学生 403、开关关闭）。**线上验收**（真实 #125↔卷#2）：下架 → 学生列表 2→1、详情 404、开考 400；再上架 → 全部复原；审计 #506/#507 带 `PUBLISHED→DRAFT`/`DRAFT→PUBLISHED`；最终 `exam_paper` 与验收前一致；复跑巡检**漂移 0 条**。**门禁 9/10**（唯一 FAIL 是既有红 L1-G；L4 PASS = 边界新增 0 条、API 面 343 未变）。**3 条偏差如实记录**（D-P5-5 无代码路径、批量删除改逐条、PENDING 直接 PUBLISHED）。**遗留**：R1 反向漂移（4 处发布入口，需 P0–P4）、D9 教师预览阈值、2 条既有红（classifier 测试未跟上 B3、exam-records 测试与新版 FastAPI 路由结构不符） |
| `plans/P5_上下架联动_方案对比_v1.md` | v1 | ✅ **已实施 A3**（D1=A3 / D2–D5 按建议 / D7 要开关 / D8 已单独修；见交付记录） | 回答「P5 上下架联动 `exam_paper.paper_type` 怎么做」，给 **6 套方案**对比（含影响面/回滚/测试点）：**A3 契约+服务层接线（推荐）**：考试域新增 `exam/contract.py` 拥有可作答性状态机 + `services/material_paper_sync.py` 薄接线 + `materials.py` 3 处调用（status / 软删 / 入库即上架），同事务强一致、**门禁基线仍 1 条、API 面仍 343、零 DDL**、0.75 人日；A1 服务层直写 0.5d（职责混）；A2 契约+基线登记 1.0d（**基线 1→2 需你批准**，换"跨域在扫描里可见"）；B 事件驱动 2.0d（最终一致 + 双路径，建议留给事件总线阶段）；C 改学生侧判据（**否决**，与 §2.3 冲突且 5 处重复判据）；D 只巡检（不达验收，降为回滚资产）。**实测事实**：学生侧 **7 处** `PUBLISHED` 判据（`exams.py:46/104/141/246` + 主路径 `exam_service.py:48` `/api/exams/start` + `paper_generation.py:551` `/api/papers/list` + `papers.py:120/229` + `smart_exam.py:657`；另有 1 处漏判 `exams.py:651` 预览，见 R8/D8）、能写 PUBLISHED 的 4 扇门、状态真源 `study_material.status`（-1:5 / 0:14 / 1:105）、3 套试卷资料 #125/#126 有卷·#127 `GZ-2024-GK-T` 无卷；门禁只扫 `api/v1` 且 `--check-only` 不自动写基线，`catalog/contract.py` 是先例，`paper_backfill.py:131` 已开"services 写 exam_paper"先例。**语义待定 D-P5-1~6**：PENDING/APPROVED 上架即 PUBLISHED、ENDED 不复活、软删联动、入库即上架联动、无卷 no-op。**回滚三层**：`MATERIAL_PAPER_SYNC` 开关 / `git revert`（无 DDL）/ `sqlite3.backup()` 快照 + 审计 detail + 漂移重算脚本。**风险 R1 反向漂移仍在**（教师端 4 处发布入口），需 P0–P4 根除；**R8 预览漏判**实物证据（ENDED 卷预览 200）与 **D8** 处置选项。**§0.5 通俗版**（打比方 + 六条优势 + 分角色预期效果）+ **4 张界面预期图** `assets/P5联动预期/`（管理端下架前后对照 / 可作答卷三态 / 学生端下架即消失 / A3 责任边界数据流） |
| `plans/C3_试卷筛选_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，C 批第 4 段） | 「类型=试卷」时出现**年份/地区/卷别**三个下拉 + 深链。**检查点**：①后端 `paper_year`(1900–2100)/`region`(代码或中文)/`book_kind`(T,A,J)；②订正优先于解析；③带试卷筛选排除非试卷；④组合筛选与 status 共存；⑤筛选后分页正确；⑥不带筛选时行为不变；⑦行回传 paper_year/region/book_kind。**实测** 2019→125、2017→126、BJ→125、江苏→126、2019+BJ→1、2020→0。pytest 11 新增/74 回归、vitest 619、gate 9/10 |
| `plans/C1_讲义大纲与删原件_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，C 批第 3 段） | 讲义能看规模与目录，原件能单独删。**检查点**：①docx 大纲抽取（Heading 优先 / 编号兜底 / 无标题只给字数 / 坏文件不炸）17 例；②`doc_meta` 列 + 启动期自动补列 + 回填脚本（5 条已回填）；③上传与导入落档后自动抽；④列表 `chapter_count/word_count`、预览 `chapters`+`doc`；⑤抽屉两级目录 + 字数；⑥删原件端点（内容寻址：有他资料引用则保留物理文件）+ 二次确认 UI。**实测** 121=3 章 120 字、删临时 pdf 后磁盘文件消失、剩余原件 0。pytest 17 新增/138 回归、vitest 610、gate 9/10 |
| `plans/C批验收反馈修复记录_v1.md` | v1 | ✅ 已完成（2026-11-08） | 验收反馈的 2 个缺陷：①**C2a 未接到上传路径**（编号只在补录/改信息时生成）→ 上传建资料时按文件名解析并写 `paper_code`/`badge`，127 补成 `GZ-2024-GK-T`；②**错误文案被吞**（`apiClient` rejection 是普通对象，非 Error）→ 新增 `errorMessage()` 并替换 9 处，真机确认显示「year 需在 1990–2100 之间，收到 1800」。含数据现状（125 挂了验收用的模拟卷 PDF、可清理清单）。pytest 121、vitest 605、gate 9/10 |
| `plans/C批_人工验收清单_v1.md` | v1 | 📋 验收指引（2026-11-08） | C 批**已实现部分**（C2a 解析 / C4 关联 / C2b 改信息）的 10 分钟剧本：0 节基线（118 / 试卷 2 / 文章·讲义 3-4 / 原件 3）；1 节 C4 只读三条（`?type=paper` 两条带编号、抽屉试卷信息 8 项、无原件是预期）；2 节 C2a 用 `2024国考·公专题本.docx` 实测自动编号 `GZ-2024-GK-T` + 年份 2024/国考/题本 + total 119；3 节 C2b 七步（回填只回填订正值、订正 90 压过可作答卷、清空回退、编号冲突 400、年份 1800 400、补原件落主文件、改地区不改编号）；4 节列 6 项「未做」（C3/C1/P5/批量改信息/补的原件不可单独删/123-124 测试产物）；5 节回执格式；6 节带 `DEV_BACKEND_ORIGIN` 的启动命令 |
| `plans/C2b_改信息弹窗_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，C 批第 2 段） | 「改信息」可用：标题/分类/编号 + 年份/地区/卷别/卷次/题量/总分/时长。**检查点**：①`paper_meta` JSON 只存人工订正；②白名单 + 范围校验（6 组非法值 400）；③订正压过解析、清空回退；④题量压过可作答卷且 `source` 标明来源；⑤编号自动生成/冲突 400/元数据不足不生成；⑥补原件落 `primary`（新增 2 例断言）。**实测** 126 订正 120/120/150、编号不变、`paper_meta_reset` 回退；抽屉与弹窗真机截图。pytest 16 新增/150 回归、vitest 599、gate 9/10 |
| `plans/C2C4_试卷元数据与编号关联_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-08，C 批第 1 段） | 2 套真实公专真题进资料库。**检查点**：①文件名解析器（34 省 + 国考/联考、答案优先于题本、年份取最后一个、`GZ-2019-BJ-T` 缺项不生成）18 例；②`paper_code` 列 + 索引（启动期自动补列）；③补录服务 dry-run 默认 + 幂等 + 编号冲突保留原值 10 例；④预览 `paper` 区块四态；⑤抽屉「试卷信息」；⑥跨域只读收敛到 `services/paper_registry.py`（不新增边界违规）。**实测** #125/#126、100 题/100 分/120 分钟、`answerable=true`；复跑全 skip。**坑**：Decimal 序列化 500、L4 cross_write 拦截 |
| `plans/管理端画风统一_方案_v1.md` | v1 | 📋 **待你拍板 E1–E5**（未写业务代码） | 回答「建新版界面的同时把管理员端所有界面换新画风」。**实测盘点**：`/admin` 下 12 个真实页面（9 个 `.vtj`：dashboard 455 / questions 942 / materials 728 / profile 451 / help 294 / papers 214 / backup 111 / settings 97 / logs 90 行；3 个手写：users 1214 / material_rules 622 / forum 359）+ 2 条 redirect + **3 个已无路由的死页**（不参与改造）；全仓 **0 个 `<el-` 组件**、**0 个 scss 变量**、`#4054e0` 出现 0 次 → 没有"一键换肤"捷径。**三层架构**：`src/styles/tokens.scss`（12 色 + 形状/字号/间距）+ `src/styles/admin-theme.scss`（仅 `.admin-layout` 作用域覆盖 9 个 `.vtj` 页）+ `src/components/admin/` 6 个组件（StatCard/Toolbar/Table/Tag/PageHeader/FormItem）。**排期**：前置 A0 1.5 天（零风险纯新增）→ A2/A3 → A4 用组件做样板页（+0.5）→ A5 与 AdminLayout 重绘合并（+0.2）→ E1 覆盖层 1.5 天 → E2 三页换组件 2 天 → E3 走查 0.5 天；总 8.2 → **14.2 天**，可见里程碑：A4 后 3.5 天见第一个新画风真页、A5 后外框全站统一。**6 条风险**（特异性战争、`!important` 误伤弹窗、泄漏到学生端、users 1214 行回归、设计器预览看不到、拖慢 B/C 批）+ 六条 DoD；**E1–E5 待拍板**，附 11 张现状真机截图与 2 张设计稿（`assets/管理端画风/`） |
| `plans/A0_画风基座_交付记录_v1.md` | v1 | ✅ 已完成（2026-11-07） | 画风轨第 1 项交付记录。**内容**：`admin-tokens.css`（12 色 + 5 档圆角 + 2 档阴影 + 字号 + 6 档间距 + 4 个工具类）、6 个 admin 组件（`AdminTag` 6 类徽标 / `AdminStatCard` 含 emoji 与 `—` 空值 / `AdminPageHeader` / `AdminToolbar` / `AdminTable` 表格壳 / `AdminFormItem`）、组件库预览页 `#/admin/dev/style`（E1/E2 的唯一视觉基准）、`AdminLayout` 面包屑回落 `meta.title`。**为什么不用 scss**：仓库未直接依赖 `sass`，CSS 变量在 `.vtj` 旧页的覆盖层里同样可读。**门禁变更**：新增 1 条页面路由 → L6/L7 **104→105** 两处同步（历史同类变更有先例，注释写明原因，可回滚）。**验证**：vitest 20 passed（含模板未定义变量、undefined→0 两个真实缺陷的回归用例）、L6/L7 通过、typecheck 0、真机 DOM 证明令牌生效（`#4054e0` / `rgb(179,83,9)`）。**没做**：12 页实际改造（E1/E2）、侧栏冻结（A5）、图表空窗（E4=B 另开单）、时间批量格式化（随 E1） |
| `plans/试卷元数据与题目导入关联_方案_v1.md` | v1 | 📋 待确认（P2 题目线，本轮不动） | 回答「题目导入怎么和试卷元数据关联」。**核心：用 `exam_paper.paper_code` 做唯一关联键**——①上传模板 3（7 列）→ upsert `exam_paper` + `exam_paper_tag`（年份/地区/类型/科目）；②题目导入时把 `paper_id`/`paper_code` 传进 `/confirm`（现只按 `paper_name` 猜）→ 题目进 `question_bank` 并由 `paper_question_relation` 挂卷；③原卷 `study_material(type='paper')` 用 `source` 写同一 `paper_code`，实现「看原卷↔练题目」且**一份卷只存一份文件**。实测现状：`exam_paper` 3 行（含 1 条测试）、`exam_paper_tag` 2 行且 **exam_province 全 NULL**、`paper_question_relation` 200 行、`question_bank` 200 题 **point_id 全 NULL**；`/batch-parsed` 已有「自动创建/复用 ExamPaper + 建 relation」能力，但试卷名靠 `_extract_paper_name` 猜。需新增 6 项小能力（元数据导入端点、paper_code 生成器与地区码表、confirm 支持 code、归属试卷下拉（R3 下建议新建手写页）、题目回填考点、重复导入保护）；待拍板 D24–D27 |
| `plans/资料_素材体检报告_v1.md` | v1 | ✅ 已生成（2026-11-05，T0.3） | 预检器 `scripts/precheck_materials.py` 对 `备考资料\` 全量跑：**52 个正式素材 0 阻断、14 条提示**（W208 混合型 PDF ×10、INFO ×7、W201 无 Heading ×1（`公安基础知识.docx` 149 段）、W205 法条缺条号 ×6、W206 章节不可切分 ×1（`100条中国历史文化常识.pdf`）、W207 页数 576>300 ×1（`申论金词500.pdf`））。首轮曾出 4 个阻断，全在 `_模板`/`_测试文件` → 据此新增 4 条豁免规则（X1 跳过 `_` 前缀目录、X2 单页/总图不要求章节、X3 无 Heading 允许入库走兜底切章、X4 模板不计阻断），已写入规范 v2 §11。CSV 明细同目录 |
| `plans/资料上传_管理员端全员可见_方案_v2.md` | v2 | 🟡 **本轮口径**：管理员上传已交付（W2/O5）；**教师端与下发推迟**（见 `资料上传与下发_管理员教师端_方案_v1.md` 与缺陷 D5） | 按你「先做管理员上传→所有人可见，教师端与班级/个人下发推迟」重写：**不建 `material_target` 表、不加可见性服务、不做教师页**，路由 104→**105**，权限沿用 `_require_admin`，学生端**零改动**（上传即 `status=1`，与现有 107 行同语义）。**第二问的审计结论**：统一格式「有规划待落地」（规范 v2 + 预检 T0）；**传输流畅性 3 个缺口**——nginx `client_max_body_size 200m` < 业务 250MB、单请求 250MB 无进度回调/无断点续传、单队列被大文件堵塞；**存储 4 个缺口**——tmp 无 TTL 清理、无磁盘水位、写盘非原子、批量入库可能长事务锁库。全部补法已排入 **T7 传输与存储治理（1 天）**：300m、XHR 进度+整文件重试、fast/slow 双队列、24h TTL、5GB 水位、`fsync+os.replace`+sha256、每 100 条提交。总估时 **8 天**（T0 1 + 实现 6 + 验收 1）。教师/下发留档于 §7，D11/D13/D15/D16 推迟 |
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
- 2026-11-16：收尾三件（D1 / D2 / D5，均为你拍板项）。**D1** R11 补登记：把本批 2 个新端点写进 `backend/tests/test_api_surface.py::KNOWN_EXTRA_OPERATIONS`（`PATCH /api/materials/admin/batch-meta`、`GET /api/materials/admin/parse-drafts/{draft_id}/page-image`），红转绿 **2 passed**，`api_surface.json` 基线未重算。**D2** R3 例外追认：`.vtj/vue/paper_answer.vue`、`paper_result.vue` 两处 `<template>` 改动（`a7fef28`、`b29667b`）由你确认授权，证据与「模板不在 DSL 里、两页未登记进设计器项目」的残余风险记在 `plans/考试结果口径修复_交付记录_v1.md` §9。**D5** 补列迁移：`scripts/migrate/migrate_add_exam_scoring_fields.py` 原**漏登记主字段 `is_scored`** 且 dry-run 会因 `SELECT … is_scored` 自己崩，本次补上并改成只查存在的列、加 `--backup-dir`；新增 DDL 存档 `migrations/20261116_001_exam_paper_material_scoring_columns.sql`、自测 `tests/test_migration_exam_scoring_fields.py`（3 passed）、运维口径 `ops/备考资料_部署与数据初始化_v1.md` §8；被剥列真实库副本端到端验证 PASS（`exam_paper`/`study_material` 8 列由 main.py 启动自愈，`exam_record` 4 列必须跑脚本，否则 500 `no such column: exam_record.is_scored`）。**D5-b** 你追加批准后补上 `exam_record` 的启动自愈：`app/main.py::_ensure_exam_record_scoring_columns`（补 4 列 + `exam_scoring.backfill_stale_records` 按口径 A 回填历史记录，只扫 `question_total=0` 的行、幂等），自测 `tests/test_startup_selfheal_exam_record.py`（3 passed）；重跑被剥列验证 → **12 列全部自愈、ORM 可用、补列脚本变空操作**（`[RESULT] PASS`）；运维口径见 `ops/备考资料_部署与数据初始化_v1.md` §8。
