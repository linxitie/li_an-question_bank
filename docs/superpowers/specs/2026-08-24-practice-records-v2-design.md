# 「练习记录」功能模块优化设计方案 v2.0

| 项 | 内容 |
|---|---|
| 文档版本 | v2.0（替代 `solve_problems_files/快速练习优化.md` v1.0 草案） |
| 编写日期 | 2026-08-24 |
| 状态 | 设计已经用户逐节批准；本文档为正式规格 |
| 关联分支 | `feat/practice-records-v2` |
| 适用对象 | 前后端开发人员、运维 |

---

## 一、背景与目标

### 1.1 现有功能与问题

学生端「练习记录」位于题库页（`.vtj/vue/question_bank.vue`）右侧栏卡片，提供：今日/本周/累计做题数、做题用时、正确率、按"科目·子科目"的题目类型进度徽章、本周做题趋势图（纯 CSS/SVG 柱状/折线切换）、手动「刷新数据」按钮。

核心痛点：
- **P1 进度颗粒度不足**：进度只到子科目，无法定位薄弱知识点。
- **P2 多来源数据缺失**：统计口径实际只覆盖写入 `practice_record` 的来源。
- **P3 记录不可跳转**：只能看统计，不能一键继续练习/查看解析。
- **P4 手动刷新体验差**：数据更新依赖手动点击。

### 1.2 P2 真实根因（经代码核实）

全库仅 3 处写入 `practice_record`：`practice.py` record/batch-record（默认'随机练习'）、`quick_practice.py /submit`（'快速练习'）、`smart_exam.py` L948-958（'智能组卷'）。**历年试卷与小模考交卷流程从不写该表**（仅写 `exam_record` + `exam_answer_detail`）。因此 `/api/practice/stats-card`、`/type-summary` 天然看不到这两类来源——根因是"缺写入"，而非 v1.0 所称"接口过滤了来源"。

### 1.3 v1.0 草案的缺陷及本版修正

| # | v1.0 缺陷 | 本版修正 |
|---|---|---|
| 1 | 新建 `exercise_records` 统一表：与现有 4 套表（practice_record / smart_exam_record / exam_record+exam_answer_detail / year_paper）大量重复，双写不一致风险高、需迁移历史数据 | **读时聚合**：零新表、零写入路径改动，新建只读聚合接口 UNION 现有表 |
| 2 | 跳转路由全部虚构（`/practice/continue`、`/past-paper/review` 等均不存在） | 全部映射到**真实存在的路由**（见第五节跳转映射表） |
| 3 | source_type 用英文 code（quick_practice/past_paper/mock_exam/ai_paper），与库内中文标签（'快速练习'等）冲突 | 来源标识统一沿用**现有中文标签值** |
| 4 | 快速练习"继续/回顾 recordId"无从谈起（快速练习无会话实体） | 快速练习记录按 `日期+科目` 聚合展示，跳转降级为"再练一组"；不做会话实体 |
| 5 | 新建 `knowledge_progress_cache` 缓存表非必需（`/api/quick-practice/sub-categories` 已返回考点级 total/done） | 第一期不建缓存表，用批量查询优化直接出数 |
| 6 | 示例代码 `<script setup>` + composable + onActivated 与目标页面 VTJ Options API 技术栈不符（且项目无 keep-alive） | 全部采用 Options API 风格，复用 `score_analysis.vue` 已验证的聚焦刷新模式 |
| 7 | overview 返回 `"42h 18m"` 格式化字符串 | 后端一律返回**秒数**，格式化由前端负责 |

### 1.4 目标

学生可以在练习记录中：①看到四种来源统一的统计数据；②查看知识点粒度进度并一键再练；③查看最近做题记录并按状态跳转续答/看解析；④数据自动刷新无需手动操作。

---

## 二、范围与明确不做清单

**做**：知识点进度细化展示、四来源统计/记录整合、点击跳转、自动刷新。

**明确不做**（范围护栏，实施中不得扩大）：

| # | 不做项 | 理由 |
|---|---|---|
| 1 | 不新建任何数据库表（含 exercise_records / knowledge_progress_cache） | 读时聚合路线 |
| 2 | 不改 `exams.py` / `smart_exam.py` / `quick_practice.py` 的任何写入路径 | 避免影响现有功能模块正常启动与运行 |
| 3 | 不做快速练习会话实体/断点续答 | 独立迭代评估 |
| 4 | 不做学习建议（v1.0 §7.2）、不做 Excel/PDF 导出（v1.0 §7.3） | 用户批准砍掉，后置独立迭代 |
| 5 | 不改跳转目标页（exercise.vue / paper_answer.vue / paper_result.vue / smart_answer.vue / student_papers.vue） | 复用现成协议 |
| 6 | 不下线旧接口 stats-card / type-summary | 本期只加不改删，其他调用方不受影响 |
| 7 | `backend/app/main.py` 零改动 | 新端点全部追加进 practice.py（同 router 已注册） |

---

## 三、后端设计（`backend/app/api/v1/practice.py` 追加）

### 3.1 新增端点总览（均为 GET、只读）

| 端点 | 职责 | SQL 预算 |
|---|---|---|
| `GET /api/practice/unified-stats` | 四来源统一统计卡数据 | ≤5 条 |
| `GET /api/practice/knowledge-progress` | 科目→考点两级进度 | ≤4 条 |
| `GET /api/practice/recent-records` | 四来源最近做题记录（UNION 分页） | 每来源 1 条 + 合并 |

### 3.2 `GET /unified-stats`

响应结构：

```json
{
  "today":    { "count": 23,  "correct": 17,  "accuracy": 73.9, "time_spent_seconds": 1380 },
  "week":     { "count": 156, "correct": 112, "accuracy": 71.8, "time_spent_seconds": 9400 },
  "total":    { "count": 3562,"correct": 2578,"accuracy": 72.4, "time_spent_seconds": 152280 },
  "daily_trend": [ { "date": "2026-08-18", "weekday": "二", "count": 30, "correct": 22 }, "... 共7天" ]
}
```

计算口径（四来源合并）：
- 快速练习/随机练习等刷题流：`practice_record` 按 `practice_date` 聚合（COUNT/SUM/GROUP BY 一次完成，修复旧 stats-card 的 7 天 N+1 循环）。
- 智能组卷：`smart_exam_record` 的 `completed_count`、`time_spent`；对错判定复用其提交时已写入 `practice_record(source_type='智能组卷')` 的行，避免重复计数——即 smart 来源在题数上以 `practice_record` 为准，会话维度仅在 recent-records 使用 `smart_exam_record`。
- 历年试卷/小模考：题数取 `exam_answer_detail`（JOIN `exam_record` ON user_id + 当日提交时间），用时取 `exam_record.duration_used`，对错用 `exam_answer_detail.is_correct`。

> 实现注记：为避免 smart 组卷在 `practice_record` 与 `exam_answer_detail` 双计，`exam_answer_detail` 聚合需排除关联 `smart_exam_record.exam_record_id` 非空的记录。此细节由实现者在编写时以真实数据验证（测试账号核对见验收标准 a）。

### 3.3 `GET /knowledge-progress`

响应结构：

```json
{
  "subjects": [
    {
      "subject_id": 1, "subject_name": "行测", "subject_code": "xc",
      "kps": [
        { "point_id": 12, "point_name": "逻辑填空", "total": 40,
          "done": 31, "done_pct": 77.5, "accuracy": 74.2 }
      ]
    }
  ]
}
```

- 批量查询（≤4 条 SQL）：①全部启用考点及其所属科目；②考点→题目ID 映射（question_knowledge）；③用户对这些题目的去重做题数（GROUP BY knowledge_point_id 一次完成）；④正确数同批计算。
- 排序：科目按 subject_id，考点按 done_pct 升序（薄弱优先）。
- 只返回 total>0 的考点。

### 3.4 `GET /recent-records?source=&status=&limit=&offset=`

- 分页参数沿用库内 limit/offset 风格（`limit` 默认 10，ge=1 le=50；`offset` ge=0），与 practice.py 现有端点一致。
- `source` 可选值 = 中文标签：`快速练习` / `历年试卷` / `小模考` / `智能组卷`；`status` ∈ `completed` / `in_progress`。
- 各来源行构造：

| 来源 | 数据源 | name | status 判定 | score |
|---|---|---|---|---|
| 历年试卷 | `exam_record`(SELF_TEST) JOIN `year_paper` | paper_title | is_completed | ScoreAnalysis 或 ExamAnswerDetail 汇总得分（复用 `exam_records.py /self` 现成查询模式） |
| 小模考 | `exam_record`(MOCK_EXAM) JOIN `exam_paper` | paper.paper_name | is_completed | 同上（复用 `/mock` 模式） |
| 智能组卷 | `smart_exam_record` | paper_name | status 字段现成 | earned_score 现成 |
| 快速练习 | `practice_record`(source_type='快速练习') GROUP BY practice_date+subject_id | "{M月D日}·{科目名}·快速练习" | 恒 completed（流水无未完成态） | 无（展示 accuracy） |

条目统一结构：

```json
{
  "record_key": "exam_123 | smart_45 | qp_20260824_1",
  "source": "历年试卷",
  "name": "2025年公安联考行测真题",
  "status": "completed",
  "score": 85.0, "accuracy": 78.2,
  "question_count": 120, "time_spent_seconds": 5520,
  "started_at": "...", "completed_at": "...",
  "jump": { "path": "/paper-result", "params": { "record_id": 123 } }
}
```

- 合并排序：completed_at/started_at 倒序；内存分页。
- `record_key` 为带前缀的复合键，保证跨来源唯一、可安全用于前端 key。

### 3.5 安全与健壮性

- 全部端点 `Depends(get_current_user)`，所有查询强制 `user_id == current_user.user_id` 过滤（沿用全库惯例）。
- Query 参数一律加 ge/le 校验；异常输入返回 422/空集而非 500。
- 纯只读操作，无事务/注入面扩大。
- 性能目标：单端点 ≤5 条 SQL、P95 < 500ms（现有索引 idx_user_id_practicerecord / idx_practice_date / idx_smart_user_id / idx_user_id_examrecord 已覆盖查询路径）。

---

## 四、前端设计（`.vtj/vue/question_bank.vue` 单文件内）

### 4.1 右侧栏卡片升级（保持现有形态）

| 区域 | 改动 |
|---|---|
| log-stats 数字区 | 改绑 `loadUnifiedStats()` 返回字段；数字含义变为四来源合计 |
| type-progress badges | 每个 badge 增加 `%` 迷你进度条（CSS 实现）；点击行为保留现有 startTypePractice |
| 刷新按钮 | **移除常驻「刷新数据」按钮**；请求失败时显示错误态 + 重试入口（复用现有 statsError + retry-btn 样式模式），弥补移除手动刷新后的兜底需求 |
| 卡片底部 | 新增「查看全部 ›」文字入口 → 打开 ElDialog |

### 4.2 「查看全部」弹窗（ElDialog，两个 Tab）

- **Tab1 知识点进度**：按科目分组的考点列表；每行显示考点名（≤8 字符完整显示，超出截断+title 悬停全文）、进度条、`done/total`、正确率徽章；点击行 = 再练一组（跳 `/exercise?subject=X&kpId=&kpName=`）；空态文案"暂无知识点数据，完成练习后查看进度"。
- **Tab2 最近做题记录**：
  - 筛选 chips：来源（全部/快速练习/历年试卷/小模考/智能组卷）+ 状态（全部/已完成/进行中）；
  - 行内容：来源徽章（配色见下）+ 名称 + 状态图标（✅ 已完成 / ⏳ 进行中）+ 分数/正确率 + 用时 + `▶` 跳转按钮；
  - 底部「加载更多」（offset 递增分页）；
  - 空态："暂无练习记录，快去刷题吧！"
- 来源徽章配色（沿用 v1.0 §3.2.2 方案，色值不变）：历年试卷 蓝 `#409EFF` / 小模考 橙 `#E6A23C` / 智能组卷 紫 `#9B59B6` / 快速练习 绿 `#67C23A`。
- 移动端适配：<768px 时弹窗全屏化（width:100%; height:100%），列表单列布局。
- Element Plus 可用性：ElDialog 在本项目已有使用先例（admin_questions.vue 审核弹窗）。

### 4.3 自动刷新生命周期（Options API）

```
mounted()        → loadUnifiedStats()（Promise.all 并行拉 3 个新接口）
document visibilitychange → 页面重新可见时刷新（复用 score_analysis.vue 已验证模式）
setInterval      → 每 5 分钟静默刷新
beforeUnmount()  → 清除定时器 + 移除 visibilitychange 监听（防内存泄漏）
```

- **禁用 onActivated/onUnmounted 组合**（项目无 keep-alive；本文件为 Options API）。
- 从答题页返回题库页时 hash 路由重新 mounted，天然触发刷新，无需额外代码。
- 所有新增方法命名与现有风格一致（camelCase、挂 methods 块）；请求走现有 getJsonHeaders()/fetch 封装模式。

### 4.4 加载与错误状态

| 场景 | 表现 |
|---|---|
| 首次加载 | 卡片数字区显示占位 0，不阻塞页面其余部分（沿用现状异步加载模式） |
| 弹窗首次打开 | Tab 内容区骨架屏/加载文案 |
| 接口失败 | 卡片显示错误态 + 重试按钮；弹窗内显示"加载失败，点击重试" |
| 空数据 | 各区域独立空态文案（见 4.2） |

---

## 五、跳转映射表（全部指向真实存在的前端路由）

| 来源 | 未完成/进行中 → | 已完成 → |
|---|---|---|
| 历年试卷 | `/paper-answer?record_id={exam_record.record_id}&paper_id={paper_id}` （自带断点续答） | `/paper-result?record_id={exam_record.record_id}` |
| 小模考 | 同历年试卷协议 | 同历年试卷协议 |
| 智能组卷 | `/smart-answer?paper_id={paper_id}&record_id={smart_exam_record.id}&paper_name={快照名}` | 同左（页面自恢复作答状态）* |
| 快速练习 | `/exercise?subject={xc\|sl\|ga}`（再练一组） | 同左 |

> \* 开放问题 D1（实施首日验证）：实测 `smart_answer.vue` 对已完成记录的回看能力。若不支持解析回看，则 Tab2 中已完成态智能组卷条目**降级为仅展示成绩摘要、不显示跳转按钮**，并在实施记录中如实标注。此为唯一允许的现场决策点，其余跳转不得偏离本表。

---

## 六、数据口径定义

| 口径 | 定义 | 备注 |
|---|---|---|
| done（已做） | 去重做过题数，不论对错 | 与现有 type-summary、sub-categories 口径一致 |
| accuracy（正确率） | 答对次数 / 总答题次数 ×100%，保留 1 位小数 | 分母为 0 时返回 0 |
| time_spent | 一律秒（整数），前端负责格式化为"xh ym/x分钟" | 修正 v1.0 格式化字符串反模式 |
| 来源标签 | 中文：`快速练习` / `历年试卷` / `小模考` / `智能组卷` | 与 practice_record.source_type 现有值域一致；禁止引入英文 code |
| status | `completed` / `in_progress`（接口对外英文枚举，前端渲染为中文图标文案） | 仅记录列表使用 |

---

## 七、实施约束

### 7.1 VTJ 防护协议（强制，逐步执行）

> 依据：`vtj-mcp-server/vtj-mcp-server.js` 源码（sync L991-1095 / consistency L1097-1163）与 `CLAUDE.md/vtj.md` §7.1。目的：保证 VTJ 版本一致，杜绝"修改后前端不显示"。

1. **改前基线**：运行 `vtj_check_consistency(id="question_bank")`，基线必须 consistent；并在 `.vtj/projects/*.json` 的 pages 数组确认 question_bank 为 `raw:true`（raw 页面不受设计器保存覆盖）。
2. **修改载体**：只编辑 `.vtj/vue/question_bank.vue`（template/script/style 三段都在此文件内完成）；`useProvider({ id: 'question_bank', ... })` 的 **id 永不改动**。
3. **版本同步**：修改完成后，将 .vue 内 `useProvider` 的 `version` 升级为新时间戳（如 Date.now() 值），随即执行 `vtj_sync_vue_to_dsl(id="question_bank")`——MCP 会把 DSL 的 `__VERSION__` 更新为 .vue 值（以 .vue 为准），并将新增 methods/state/lifeCycles 以**只增合并**方式写入 DSL JSON；写前自动生成 `.bak` 备份。
4. **同步校验**：复跑 `vtj_check_consistency(id="question_bank")` 必须返回 `consistent`（注意核对 missingInDsl/extraInDsl 差异清单——MCP 的方法签名提取正则可能漏深层嵌套方法，发现漏提时手工补写 DSL methods 声明）。
5. **显示生效保障**：删除 `node_modules/.vite/` 缓存目录 → 重启 `npm run dev` → 浏览器 Ctrl+Shift+R 强制刷新后验证。
6. **回滚兜底**：所有 MCP 写操作自动留 `.bak`；实施前额外建议对 question_bank.vue 做一次 git 提交基线。

### 7.2 工程约束

- 后端每完成一个端点（含冒烟测试通过）独立 commit；前端整体一个 commit；VTJ DSL 同步随前端 commit 一并提交（含 question_bank.json 变更）。
- 提交信息格式沿用仓库惯例：`feat(scope): ...` / `fix(scope): ...`。
- 严格禁止触碰第二节"不做清单"所列文件与行为。

---

## 八、验收标准

| # | 标准 | 验证方式 |
|---|---|---|
| a | 统计卡数字 = 四来源合计（准备一个含四种来源做题数据的测试账号逐一核对） | 人工 + SQL 对照 |
| b | 弹窗 Tab1 展示科目→考点两级进度，点击考点能进入对应练习且题目范围正确 | Playwright 浏览器操作验证 |
| c | Tab2 四种来源记录均可见、徽章颜色正确；未完成试卷点击进入 `/paper-answer` 能断点续答，已完成进入 `/paper-result` 能看到成绩与解析 | Playwright + 真实路由断言 |
| d | 切换浏览器标签页再切回，≤1 秒内数据自动更新（Network 面板可见自动请求） | Playwright visibilitychange 模拟 |
| e | 断网/接口 500 时出现重试入口而非白屏或报错弹窗堆积 | DevTools 拦截模拟 |
| f | `vtj_check_consistency(id="question_bank")` 返回 consistent；浏览器控制台零报错；相邻模块（快速练习三级选择、错题集入口、成绩分析入口、GoalCard）回归正常 | MCP 工具 + 控制台检查 + 回归走查 |
| g | 三个新接口 P95 < 500ms（当前数据量级，793 题/单用户万级记录） | curl 计时或 pytest 计时断言 |

---

## 九、测试策略

- **后端**：`backend/tests/test_practice_unified.py` 新增冒烟测试，沿用现有 tests 目录模式（TestClient + 测试库夹具）：覆盖三端点的鉴权（未登录 401/403）、参数校验（422）、四来源数据混合下的数值正确性、空数据边界。
- **前端**：Playwright MCP 浏览器实测——渲染快照、弹窗交互、筛选、跳转落点 URL 断言、控制台错误收集。
- **VTJ**：check_consistency 前后对照；Vite 缓存清理后启动无编译错误。
- **回归**：题库页原有交互（分类切换、快速练习入口、搜索、错题集/笔记/收藏/金币购快捷工具、GoalCard）逐一走查。

---

## 十、风险与开放问题

| # | 风险/开放项 | 影响 | 缓解 |
|---|---|---|---|
| R1 | smart_answer.vue 已完成回看能力未知（开放问题 D1） | 智能组卷已完成条目可能不可跳转解析页 | 实施首日验证；不支持则按第五节预案降级 |
| R2 | vtj-mcp-server 的 extractMethodsFromScript 正则为惰性匹配，深层嵌套方法可能漏提取进 DSL | 设计器未来保存时理论上可能丢方法声明（raw:true 下风险低） | 每次 sync 后核对 check_consistency 差异清单，漏提手工补 |
| R3 | 大历史量用户（万级 practice_record）聚合查询变慢 | unified-stats 响应超时 | 已有索引覆盖；必要时后续迭代引入汇总缓存表（本期禁做） |
| R4 | exam_answer_detail 与 practice_record('智能组卷') 双计 | 统计偏大 | 见 3.2 实现注记：排除 smart 关联的 exam_answer_detail；验收标准 a 兜底核对 |
| R5 | ElDialog 样式与既有移动端布局冲突 | 小屏错位 | <768px 全屏化 + Playwright 移动视口截图验证 |

---

## 附：涉及文件清单（预期变更面）

| 文件 | 变更类型 |
|---|---|
| `backend/app/api/v1/practice.py` | 追加 3 个只读端点（main.py 不动） |
| `.vtj/vue/question_bank.vue` | template/script/style 升级（VTJ 防护协议全程护航） |
| `.vtj/files/question_bank.json` | 由 vtj_sync_vue_to_dsl 自动同步（__VERSION__ + methods/state/lifeCycles） |
| `backend/tests/test_practice_unified.py` | 新增冒烟测试 |
| `docs/superpowers/specs/2026-08-24-practice-records-v2-design.md` | 本文档 |
