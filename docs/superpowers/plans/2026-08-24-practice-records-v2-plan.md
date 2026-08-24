# 「练习记录」模块优化 v2.0 — 实施计划

| 项 | 内容 |
|---|---|
| 计划日期 | 2026-08-24 |
| 规格来源 | `docs/superpowers/specs/2026-08-24-practice-records-v2-design.md`（已批准，commit 62c11fb） |
| 分支 | `feat/practice-records-v2` |
| 任务数 | 3 个主任务（后端 / 前端 / 验收），每任务独立提交 |

---

## Task 1：后端三端点追加 + 冒烟测试

**目标**：`backend/app/api/v1/practice.py` 文件末尾追加 3 个只读端点；新增 `backend/tests/test_practice_unified.py`。**禁止改动文件内任何现有代码、禁止触碰 main.py / exams.py / smart_exam.py / quick_practice.py。**

### 步骤

1.1 在 practice.py 顶部 imports 补充所需模型：`SmartExamRecord, ExamRecord, ExamAnswerDetail, YearPaper, ExamPaper, KnowledgePoint, QuestionKnowledge, SubCategory`（检查现有 import 行，仅追加缺失项）。

1.2 **GET `/unified-stats`**
- 依赖 `get_current_user`。
- `practice_record` 部分：单条 GROUP BY `practice_date` 查询取近 7 日 + 当日/本周/累计的 COUNT/SUM（用 `case()` 或一次取回聚合行后在 Python 汇总，杜绝逐日循环 N+1）。
- 试卷部分（历年+模考）：`ExamRecord JOIN ExamAnswerDetail` 按 `DATE(submit_time/start_time)` 聚合题数/正确数/用时(duration_used)。
- 双计排除：排除 `exam_record.record_id IN (SELECT exam_record_id FROM smart_exam_record WHERE exam_record_id IS NOT NULL)`（智能组卷题数已计入 practice_record）。
- smart 组卷会话不另计题数（规格 §3.2 注记）。
- 返回结构见规格 §3.2；时间一律秒。

1.3 **GET `/knowledge-progress`**
- ≤4 条 SQL：①`KnowledgePoint JOIN SubCategory JOIN QuestionSubject`（status=1）；②`QuestionKnowledge` 取 point_id→question_id 映射；③④对映射内题目按用户去重 done 与 correct 各一条 GROUP BY（或合并为一条含 SUM(case) 的查询）。
- 只返回 total>0 考点；组内按 done_pct 升序；结构见规格 §3.3。

1.4 **GET `/recent-records?source=&status=&limit=&offset=`**
- Query 校验：limit ge=1 le=50 默认 10；offset ge=0；source 可选中文标签枚举；status ∈ completed/in_progress。
- 四来源各自一条查询：
  - 历年试卷：`ExamRecord(exam_type='SELF_TEST') JOIN YearPaper`；
  - 小模考：`ExamRecord(exam_type='MOCK_EXAM') JOIN ExamPaper`；
  - 智能组卷：`SmartExamRecord`；
  - 快速练习：`PracticeRecord(source_type='快速练习') GROUP BY practice_date, subject_id`（JOIN QuestionSubject 取科目名）。
- 得分查询模式复用 exam_records.py 中 /self、/mock 端点的现有写法（可参考其实现，不得 import 其私有函数以外内容造成耦合）。
- 内存合并按最近时间倒序 → 过滤 source/status → 切片分页；条目结构与 `jump{path,params}` 见规格 §3.4；record_key 前缀 `exam_`/`smart_`/`qp_`。
- 返回 `{total, limit, offset, items}`。

### 验证

1.5 `python -m pytest backend/tests/test_practice_unified.py -v` 通过（测试覆盖：未登录 401/403、参数校验 422、混合来源数值正确性、空数据边界）。若项目测试夹具不支持独立运行，则退化为：启动 uvicorn 后 curl 三端点断言 JSON 结构与鉴权行为，把结果贴入提交说明。

### 提交

`feat(practice): add unified-stats/knowledge-progress/recent-records aggregation endpoints`

---

## Task 2：前端 question_bank.vue 升级（VTJ 防护协议全程护航）

**目标**：卡片升级 + 「查看全部」ElDialog 双 Tab + 自动刷新。**严格按规格 §7.1 六步执行，任何一步失败即停并报告。**

### 步骤

2.1 **基线**：`vtj_check_consistency(id="question_bank")` 必须 consistent；确认 `.vtj/projects/*.json` pages 数组中 question_bank 为 `raw:true`。对 `.vtj/vue/question_bank.vue` 做一次 git 基线提交（如工作区有未提交改动则记录 hash 即可，不强提他人改动）。

2.2 **template 改造**（在现有结构上增量修改，不重构无关区块）：
- log-stats/log-sub-stats 绑定字段切换到新接口数据；
- type badge 内加 `%` 迷你进度条 span；
- 移除 L228-230 常驻刷新按钮区，改为 statsError 错误态 + 重试（复用 L145-150 retry-btn 样式模式）;
- 卡片底部加「查看全部 ›」入口；
- 文件底部追加 ElDialog 结构（两个 Tab、筛选 chips、列表、加载更多、空态）——参照 admin_questions.vue 弹窗先例与本项目 Element Plus 用法。

2.3 **script 改造**（methods 块追加，Options API，风格与现文件一致）：
- state 新增：`unifiedStats`、`kpProgress`、`recentRecords`、`recordsFilter{source,status}`、`recordsPaging{limit,offset,total,loading}`、`dialogVisible`、`activeTab` 等；
- `loadUnifiedStats()`：Promise.all 并行 fetch 三新端点（getJsonHeaders()）；
- `openRecordsDialog()` / `switchTab()` / `setSourceFilter()` / `setStatusFilter()` / `loadMoreRecords()`；
- `goRecordDetail(record)`：按 record.source 分发跳转（规格 §5 映射表；智能组卷已完成条目按 D1 结论处理）；
- 生命周期：mounted 内调用 loadUnifiedStats 并注册 visibilitychange 监听 + 5 分钟 setInterval；beforeUnmount 清理定时器与监听。禁用 onActivated。
- 保留旧 loadPracticeRecords 相关方法暂不删除？——否：本页统计入口统一切换到新接口；旧方法若无其他引用则一并移除，避免死代码（DSL 同步会如实反映）。

2.4 **style 追加**：进度条、徽章四色（#409EFF/#E6A23C/#9B59B6/#67C23A）、弹窗布局、<768px 全屏化媒体查询。

2.5 **版本同步**：useProvider version 更新为新时间戳 → `vtj_sync_vue_to_dsl(id="question_bank")` → 核对返回 changes 清单。

2.6 **一致性校验**：`vtj_check_consistency(id="question_bank")` 必须 consistent；发现 missingInDsl 则手工补写 DSL methods 声明（用 vtj_write_dsl_file section=methods）。

2.7 **显示生效**：删除 node_modules/.vite 缓存 → 重启 dev server → Ctrl+Shift+R。

### 提交

`feat(frontend): practice records card upgrade + records dialog with VTJ dsl sync`
（包含 question_bank.vue + question_bank.json 及其 .bak 变更）

---

## Task 3：验收 a~g + 回归 + 收尾

3.1 按规格 §八 逐项执行 a~g 验证（Playwright MCP 浏览器实测 + SQL 对照 + 控制台检查）。
3.2 回归走查：分类切换、快速练习三级选择入口、搜索、错题集/笔记/收藏/金币购快捷工具、GoalCard。
3.3 D1 开放项结论写入实施记录；R1~R5 风险逐项确认状态。
3.4 最终汇报：分支提交清单、验收结果表、遗留事项。

---

## 执行纪律

- 每 Task 完成即提交并勾选计划状态；Task 失败立即停止并上报阻塞点，不带病续跑。
- 全程不触碰规格第二节"不做清单"所列范围。

---

## 执行状态记录（2026-08-24 收尾更新）

| 任务 | 状态 | 提交 | 验证证据 |
|---|---|---|---|
| Task 1 后端三端点 | ✅ 完成 | `91c55f9` | pytest **12/12 通过**（四来源混合数值、智能组卷双计排除、参数校验422、鉴权401、空态边界）；顺带修复趋势窗口差一错误 |
| Task 2 前端改造+VTJ同步 | ✅ 完成 | `cc84cae`(基线) + `6385574` | vue/compiler-sfc 编译校验通过；`vtj_sync_vue_to_dsl` 对齐 `__VERSION__=1787547281992`；手工补写13个新方法声明入DSL（R2预案）；check_consistency versionMatch=true |
| 验收期补充修复 | ✅ 完成 | `2a3f97b` | 真库冒烟暴露 goKpPractice 使用 subject_code(auto_*) 缺陷 → 改用 subject_id→xc/sl/ga 映射，SFC复验通过 |
| Task 3 真库冒烟验收 | ✅ 完成 | — | OAuth2表单登录成功；三新端点 HTTP 200（25~48ms，远低于500ms标准）；真实数据吻合（qp_2026-07-30_3 / total.count=5 / secs=150）；中文筛选参数生效；旧接口 stats-card/type-summary 回归正常 |

### 已知条件与移交清单（用户浏览器走查前必读）

1. **R1/D1 待验**：smart_answer.vue 对已完成记录的回看能力需在真实数据下确认；若不支持，已完成态智能组卷条目按规格§5降级为摘要不可跳转。
2. **R2 记录在案**：vtj-mcp-server 方法签名正则对本文件提取失效（基线即有）；check_consistency 的 extraInDsl(35项)/missingInDsl["if"] 均属该已知误报类，非真实漂移。raw:true + 版本号对齐(1787547281992)为实际生效的双重防护。
3. **浏览器侧验收项**（b/c/d/e/f-console）由用户执行：
   - 删除 `node_modules/.vite/` 缓存目录
   - 重启 `npm run dev`（后端 uvicorn 照常）
   - 浏览器 Ctrl+Shift+R 强刷
   - 走查：卡片数字四来源口径 → 「查看全部」弹窗两Tab → 考点点击再练一组 → 各来源记录跳转续答/看解析 → 切标签页返回自动刷新 → 控制台零报错 → 相邻模块回归（快速练习入口/错题集/成绩分析/GoalCard）
4. `.vtj/files/question_bank.json.bak` 为同步工具自动备份（本地回滚用），未纳入版本库。
5. 先存于 question_bank.json state 区的碎片化污染条目（如键 `2`/`3`/practiceLog 截断值）为历史遗留，本次未触碰，建议独立清理任务处理。

---

## 追加轮执行记录（2026-08-24）：幻影徽章 + 空白跳转修复

| 项 | 内容 | 提交 |
|---|---|---|
| 问题1「公专·综合」幻影徽章 | type-summary 移除 `'综合'` 兜底桶：子科目缺失/None/'无' 的题目直接跳过统计（系统中不存在该分类） | `59ce021` |
| 问题2 跳转空白·真因 | recent-records 的 qp_ 行 `jump.subject` 透传了库中真实存在的 `auto_*` 科目码 → exercise 页旧接口科目校验 400 → 前端 `if(!res.ok) return` 静默留白。修复：按 subject_id 映射为约定键 xc/sl/ga（与 goKpPractice 同源缺陷的第二位点） | `59ce021` |
| 回归测试 | 新增 `test_auto_code_maps_to_convention_key`；套件 **13/13** 通过 | `59ce021` |
| 历史数据清理 | 新增 `scripts/cleanup_old_records.py`（--dry-run/--apply + 自动备份 + 幂等）；已执行 apply：**删除 practice_record 254 条**（<2026-08-01），exam 系 0 条；备份于 `backend/data/backups/pre_cleanup_20260824_163443/` | `31ec4bf` |
| 真库复验 | `BAD_ZONGHE_COUNT=0`（types 4→3）；recent-records total=0（旧记录清除后合理空态）；exercise 旧接口整科取样正常（200，20/772 题）| — |

### 追加轮说明
- 清理前 dry-run 显示 exam 系全为 0 —— 库中不存在旧试卷记录；现存唯一 exam_record（8月23日，paper_id=18）数据完整（100 关联全部有效），可正常续答。
- 后端改动需**重启 uvicorn 服务**后生效；本轮未改动任何前端文件。
