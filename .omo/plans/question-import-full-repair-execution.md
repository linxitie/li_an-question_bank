# 题目导入模块全面修复与满血优化 —— 可执行任务计划

> **生成时间**：2026-10-04　**分支**：`fix/vite-mobile-connection`　**基线**：`8eee113`
> **设计方案**：[`./question-import-full-repair.md`](./question-import-full-repair.md)（1160 行 / 78 KB，**执行前必读**）
> **状态**：⏸ 等待 `/start-work` 启动

---

## TL;DR

> **修复 4 个用户可见问题 + 补齐 6 层回归门禁网 + 10 步有序拆分 + 3 处深度下钻 + 12 条 Playwright 真实语料验收。**
>
> **交付物**：
> - 6 层门禁网（L0 红线 / L1 解析指纹 / L2 匹配配对 / **L3 落库链路** / L4 API 契约 / L5 前端数据契约）+ `gate_all.py` 一键入口
> - 上传轮询稳定性修复（消除「signal is aborted without reason」）
> - 入库链路统一（Word/PDF/分离导入**首次真正能入库**）
> - 申论「材料 + 要求 + 逐小题答案解析」三端统一预览 + 学生端竖向滑动作答
> - MinerU 分层主库（扫描件第一顺位）+ 实际引擎名可见
> - `question_import.py` 4996 → ~900 行 router + `question_ingest/` 包
>
> **关键约束**：
> - **门禁网（Wave 1）必须先于一切代码改动**
> - **拆分（Wave 9）必须最后**，且 I-6 单独 commit + 单独全套 E2E
> - 禁止虚拟/空文档进入导入链路测试；只用 §3.11.2 的 9 个真实语料
> - 公专 2583 题**逐字段不得变化**；G1 五项数字逐项一致

---

## Context

### 原始诉求（用户原话要点）
1. Word/PDF扫描件/PDF文档/Excel 上传后**无法真实识别并合理预览**，且 Word 导入报「文件上传异常：signal is aborted without reason」
2. 行测/申论的题目文档+答案文档（分离/合并）**识别预览后无法入库**，且相比之前**退步了**
3. 申论应「一个整题 + 每小题下方匹配答案与解析」；公专/行测保留原预览
4. 复合题预览三端一致；学生端支持上下滑动作答整个复合题

### 已定位的 10 条根因（详见设计方案 §2）
| 编号 | 缺陷 | 触发率 |
|---|---|---|
| RC-1 | 轮询超时 10s + retries=0 + catch 绕过 `handleFetchError` | 高频 |
| **RC-2** | 「确认入库」读错状态字段，**永远 0 题、永远无法入库**；阻断闸门同时失效 | **必现** |
| RC-3 | `/confirm` 读服务端旧快照，丢弃前端修改 | 必现 |
| RC-4 | `question_import.py:3809` `confirmed_items` 未定义 → 题目已入库但返 500 | 必现 |
| **RC-5** | `/batch-parsed` 丢弃 `requirements` / `group_id` | **必现** |
| RC-6 | 文件类型只看扩展名，不校验文件头 | 条件 |
| RC-7 | MinerU 实为扫描件第三级兜底，非主库 | 事实偏差 |
| RC-8 | 复合题预览 4 处各写一套 | 必现 |
| RC-9 | 双巨型文件 4996 / 4239 行 | 结构性 |
| RC-10 | 26MB 乱码日志、429 条僵死预览、20+ 散落脚本 | 事实 |

### 用户已裁决的 6 项决策（设计方案 §8）
分层主库 / docx 不走 MinerU / 429 条 PREVIEW 不动 / 测试脚本直接删除 / **同步拆分且先补门禁网** / 学生端保持竖向滚动。**I-6 单独 commit + 单独全套 E2E。禁止虚拟空文档。**

### 关键实测基线（不得漂移）
```
question_bank  : 2583（全部公专 subject_id=3），status=1 → 2478
question_groups: 21 组，20 题带 group_id
requirements   : 非空 0 行          ← RC-5 的直接后果
question_subject: (1,行测) (2,申论) (3,公专)
question_import_record: COMPLETED 1064 / PREVIEW 429 / PARTIAL 6 / PARSING 1 / FAILED 1
最后一次 COMPLETED = 2026-09-29     ← 此后 0 次成功入库
公专解析基线: 2899 块 / 污染 0 / 题型 {单选题:2534,多选题:249,判断题:80,简答题:36}
              选项数 {4:2796,1:13,2:14,0:73,3:3}
pytest 基线  : 16 failed / 168 passed / 52 errors（判定=失败集合一致，不要求全绿）
```

---

## Verification Strategy

> **零人工介入** —— 全部由执行代理自动执行并留证。

### 测试决策
- **基础设施**：**部分存在**（G1/G2/G3 + pytest），但**全部只测解析器，零落库链路覆盖**
- **策略**：**先补网再动刀** —— Wave 1 建立 L0–L5 六层门禁，其中 **L3（落库链路）为新增且最关键**
- **门禁自身必须有单测**（门禁不能是黑箱）
- **测试数据**：**仅用**设计方案 §3.11.2 的 9 个真实语料（S1–S9），**禁止虚拟/空/构造文件**

### 证据落盘规范
所有证据写入 `.omo/evidence/`：
```
task-{N}-{scenario-slug}.{txt|png|json}
```
每份 txt **首行固定**：
```
文件: <绝对路径> | 大小: <bytes> | SHA256: <前16位> | import_id: <id>
```

### 硬门禁速查（详见设计方案 §5.1）
```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
cd D:\砺安题库\砺安题库\backend
python scripts/gate_all.py            # 全量 L0-L5
python scripts/gate_all.py --quick    # L0+L1，秒级
python scripts/gate_all.py --layer L3 # 单层
```

---

## Execution Strategy

### 并行波次（10 波 + FINAL）

```
Wave 0  前置归档与取证（无依赖，4 路并行）
├── 1. 归档设计方案到 solve_problems_files + 更新 README 索引    [quick]
├── 2. DB 备份（sqlite3 备份 API）+ 基线快照取证                  [unspecified-high]
├── 3. 跑旧 G1-G4 记录现状基线 + 分类登记 52 errors              [unspecified-high]
└── 4. 复现 RC-1/RC-2 留证 + 校验 9 个真实语料文件非空            [unspecified-high]

Wave 1  ★ 门禁网（必须先于一切代码改动；6 路并行 + 1 汇总）
├── 5. L0 gate_l0_redlines.py（6 个 SHA256 红线）                 [quick]
├── 6. L3 gate_l3_ingest.py（内存临时库 + 8 条落库断言）★最关键   [deep]
├── 7. L1 gate_l1_parser.py（三科结构化指纹，升级 G1）            [deep]
├── 8. L2 gate_l2_matching.py（继承 G2/G3 + 2 条历史守卫）        [deep]
├── 9. L4 gate_l4_api_contract.py（归并 verify_task11_*）         [unspecified-high]
├── 10. L5 gate_l5_frontend_contract.py（RC-2 专属反向守卫）      [unspecified-high]
└── 11. gate_all.py + last_run.json + known_broken.json + CI 接线 [unspecified-high]
    ⚠️ 任务 6 必须先红：复现 RC-3/RC-4/RC-5 失败，修完才转绿

Wave 2  稳定性（4 路并行）
├── 12. A-1..A-4 前端超时/重试/错误文案                          [quick]
├── 13. A-5/A-6/A-7 后端状态接口瘦身 + 预览重挂                  [unspecified-high]
├── 14. A-8 + I-1 文件头嗅探 magic.py                            [unspecified-high]
└── 15. RC-4 confirmed_items 修复（独立低风险）                   [quick]

Wave 3  ★ 入库链路（严格串行，每步跑 L0+L3）
├── 16. B-1 前端 pendingQuestions 单一事实来源                   [deep]
├── 17. B-2/B-3 batch-parsed 接 requirements/group_id            [deep]
├── 18. B-4 batch-parsed blocked 闸门                            [deep]
└── 19. B-5/B-6 /confirm 改造（payload.questions 优先）          [deep]

Wave 4  识别与渲染（5 路并行）
├── 20. C-1/C-6 公专回归用例 + 省份只从文件夹取                  [unspecified-high]
├── 21. C-5 分离/合并统一三方交叉校验                            [deep]
├── 22. E-1 后端 members 补 requirements                          [quick]
├── 23. E-2 共用题组渲染组件                                      [visual-engineering]
└── 24. E-3/E-4 teacher_questions + admin_questions 接入          [visual-engineering]

Wave 5  MinerU + 学生端 + 治理（4 路并行）
├── 25. D-1..D-5 MinerU 分层主库 + 引擎名可见                    [deep]
├── 26. F-1/F-2 answer_page 接入共用组件                          [visual-engineering]
├── 27. F-3 mobile_practice + tablet_practice 接入                [visual-engineering]
└── 28. G-1 日志 UTF-8/轮转 + G-2 README 重写                     [quick]

Wave 6  ★ Playwright 抽样（1 路，用 9 个真实语料）
└── 29. PW-1..PW-12 全量执行 + 证据留档                            [unspecified-high]

Wave 7  三处下钻专项（6 路并行）
├── 30. J-1-1/J-1-2 题组图片落盘通道 + owner 参数                 [deep]
├── 31. J-1-3 材料复用键改 SHA256 + J-1-4 lru_cache              [quick]
├── 32. J-2-1 表格行按 top 原位插入                              [deep]
├── 33. J-2-2/J-2-3 材料页识别 + 归属指向后继题号                [deep]
├── 34. J-3-1..J-3-6 Excel 容错字典 + GBK 嗅探 + 丢行报告化       [deep]
└── 35. L3 断言 9/10 + L1 指纹键 + L2 材料守卫                    [deep]

Wave 8  脚本清理（1 路，分批删除）
└── 36. G-3/G-4 20+ 散落脚本删除（先写 manifest，每批后 L0+L1）   [quick]

Wave 9  ★ 拆分（每步独立 commit，前后各跑 L0+L3；可 3 路并行但同文件互斥）
├── 37. I-2 excel_reader     38. I-3 docx_reader     39. I-4 tags
├── 40. I-5 images           41. ★I-6 pdf_reader（单独全套 E2E）
├── 42. I-7 upsert+links     43. I-8 groups 收敛
└── 44. I-9 行测三函数 → text_parser/xingce.py

Wave 10  ★ Playwright 复验（1 路，证明拆分后行为零变化）
└── 45. 用同一批 S1-S9 全量复跑 PW-1..PW-12

Wave FINAL（4 路并行复核）
├── F1. 计划合规审计（oracle）
├── F2. 代码质量审查（unspecified-high）
├── F3. 真实端到端 QA（unspecified-high，含 Playwright）
└── F4. 范围忠实度核查（deep）
```

### 依赖矩阵（简）
```
1 ─────────────────────────────────▶ 45
2 ──▶ 3,4,5,6,7,8,9,10,11 ──▶ 12..19 ──▶ 20..28 ──▶ 29 ──▶ 30..35 ──▶ 36 ──▶ 37..44 ──▶ 45
5 ──▶ 12,13,14,16,17,18,19,30,31,32,33,34,37..44
6 ──▶ 17,18,19,29,45
11 ─▶ 全局（每步收尾必跑）
16 ─▶ 17 ─▶ 18 ─▶ 19
22 ─▶ 23 ─▶ 24 ─▶ 26 ─▶ 27
30,31 ─▶ 29,45
32,33,34 ─▶ 29,45
35 ─▶ 29,45
```

### Agent 调度汇总
| Wave | 路数 | 分布 |
|---|---|---|
| 0 | 4 | quick ×1 / unspecified-high ×3 |
| 1 | 7 | quick ×1 / deep ×3 / unspecified-high ×3 |
| 2 | 4 | quick ×2 / unspecified-high ×2 |
| 3 | 4 | deep ×4（串行） |
| 4 | 5 | unspecified-high ×2 / deep ×1 / quick ×1 / visual-engineering ×2 |
| 5 | 4 | deep ×1 / visual-engineering ×2 / quick ×1 |
| 6 | 1 | unspecified-high ×1 |
| 7 | 6 | deep ×5 / quick ×1 |
| 8 | 1 | quick ×1 |
| 9 | 8 | quick（拆分统一，逐个串行提交） |
| 10 | 1 | unspecified-high ×1 |
| FINAL | 4 | oracle ×1 / unspecified-high ×2 / deep ×1 |

### 关键路径与并行加速
- **关键路径**：2 → 6 → 16 → 17 → 18 → 19 → 29 → 35 → 45 → FINAL
- **并行上限**：7 路（Wave 1）
- **预计加速**：相比完全串行约 **65%**

---

## TODOs

> **格式铁律**：
> - 任务标签必须用**裸数字**：`1.` `2.` …（**禁止** `T1.` / `Phase 1:` / `Task-1.`）
> - Final Wave 标签必须用 `F1.` `F2.`（**禁止** `T-F1.` / `F-1.` / `Final-1.`）
> - 每个任务**必须**含：推荐 Agent Profile + Parallelization + References + Acceptance Criteria + QA Scenarios
> - **无 QA Scenarios 的任务视为未完成**

- [x] 1. 归档设计方案到 solve_problems_files 并更新 README 索引

  **What to do**:
  - 复制 `.omo/plans/question-import-full-repair.md` → `solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md`
  - 在 `solve_problems_files/README.md` 的「文档索引」小节追加一行：
    `- [题目导入模块全面修复与满血优化方案_v1.md](./题目导入模块全面修复与满血优化方案_v1.md) — **教师端题目导入模块全面修复**：10 条根因诊断、上传轮询稳定性、入库链路统一（RC-2/RC-3/RC-4/RC-5）、申论/复合题三端统一预览、六层回归门禁网、10 步有序拆分、三处下钻专项、9 个真实语料 Playwright 验收`
  - 确认 `solve_problems_files/` 下原有的 `行测题目导入优化方案.md` 与 `行测导入门禁与运维手册.md` 不受影响

  **Must NOT do**:
  - 不得修改设计方案正文内容（只做复制）
  - 不得删除或改动 `solve_problems_files/` 下任何既有 .md

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单文件复制 + 单文件追加，无代码逻辑
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `writing`（不撰写新内容，只搬运既有内容）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0（与任务 2/3/4 并行）
  - **Blocks**: 无
  - **Blocked By**: None

  **References**:
  - `.omo/plans/question-import-full-repair.md` — 源文件，1160 行
  - `solve_problems_files/README.md:20-30` — 「文档索引」小节，追加位置
  - `solve_problems_files/行测题目导入优化方案.md:1-5` — 归档格式范本（版本/日期/分支/配套文档四行头）

  **Acceptance Criteria**:
  - [ ] `Test-Path "solve_problems_files\题目导入模块全面修复与满血优化方案_v1.md"` → `True`
  - [ ] 两文件行数一致：`(Get-Content 源).Count -eq (Get-Content 目标).Count` → `True`
  - [ ] `Select-String -Path solve_problems_files/README.md -Pattern "题目导入模块全面修复与满血优化方案_v1"` → 命中 1 行

  **QA Scenarios**:

  ```
  Scenario: 归档文件内容与源文件逐字节一致
    Tool: Bash (PowerShell)
    Preconditions: 设计方案已定稿于 .omo/plans/question-import-full-repair.md
    Steps:
      1. (Get-FileHash .omo/plans/question-import-full-repair.md -Algorithm SHA256).Hash  记为 $H1
      2. (Get-FileHash solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md -Algorithm SHA256).Hash  记为 $H2
      3. 断言 $H1 -eq $H2
    Expected Result: 两个 SHA256 完全相同
    Failure Indicators: 任一文件缺失，或 H1≠H2（说明复制过程被截断或被改写）
    Evidence: .omo/evidence/task-1-archive.txt

  Scenario: README 索引可被检索到，且未破坏既有条目
    Tool: Bash (PowerShell)
    Preconditions: 归档已完成
    Steps:
      1. Select-String -Path solve_problems_files/README.md -Pattern '题目导入模块全面修复与满血优化方案_v1'  → 必须命中
      2. Select-String -Path solve_problems_files/README.md -Pattern '行测题目导入优化方案'  → 必须仍命中
      3. Select-String -Path solve_problems_files/README.md -Pattern '行测导入门禁与运维手册'  → 必须仍命中
    Expected Result: 新条目命中 1 次，两条既有关键条目各仍命中
    Failure Indicators: 新条目缺失（索引未更新），或既有条目消失（误删）
    Evidence: .omo/evidence/task-1-readme.txt
  ```

  **Commit**: YES
  - Message: `docs(plan): archive import-module repair solution to solve_problems_files`
  - Files: `solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md`, `solve_problems_files/README.md`

---

- [x] 2. DB 备份与基线快照取证

  **What to do**:
  - 用 **sqlite3 备份 API**（禁用 `shutil.copy2`）备份 `backend/data/question_bank.db`
  - 采集基线快照并写入 `backend/data/gates/baseline_snapshot.json`：
    `question_bank` 总数 / 按 subject_id 分布 / status 分布 / `question_groups` 数 /
    带 group_id 的题数 / `requirements` 非空数 / `need_review=1` 数 / `answer_analysis` 空数 /
    `question_import_record` 按 status 分布 / `question_image` 数 / `exam_paper` 数
  - 采集 20 道带 `group_id` 的题的**逐字段快照**（question_id / subject_id / type_id /
    options / answer / answer_analysis）作为 E2E-9 的比对基准
  - 采集 2583 道公专题的 **SHA256 指纹清单**（对 `question_id|subject_id|type_id|options|answer|answer_analysis` 归一化后哈希），写入 `backend/data/gates/gongzhuan_field_fingerprint.json`

  **Must NOT do**:
  - **禁止** `shutil.copy2` 复制 DB（WAL 模式下会损坏一致性）
  - **禁止** 用写模式打开真实库（只允许 `mode=ro` 查询；备份用 `src.backup(dst)`）
  - **禁止** 删除或覆盖任何既有 `backend/data/*.bak*` 备份
  - **禁止** 写入 `.omo/` 以外的 .json（`backend/data/gates/` 需 `.gitignore` 白名单）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 涉及 SQLite WAL 一致性、备份 API 正确性、指纹归一化设计
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `git-master`（本任务不提交 DB 文件，仅提交 .json 基线）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0（与任务 1/3/4 并行）
  - **Blocks**: 3, 4, 17, 18, 19, 29, 45（F3 的 E2E-9 比对依赖此基线）
  - **Blocked By**: None

  **References**:
  - `solve_problems_files/行测导入门禁与运维手册.md:129-142` — **WAL 库必须用 `sqlite3` 备份 API** 的原文与原因（`shutil.copy2` 只拷主库无法保证完整性；恢复时残留 `-wal` 会被回放）
  - `solve_problems_files/行测导入门禁与运维手册.md:155-165` — 现有备份清单（`question_bank.db.bak_pre_wipe_20261004_102517` 148.5 MB 等，一律不得动）
  - `backend/app/models/models.py:166-252` — `QuestionBank` 全部列定义，指纹归一化的字段白名单依据
  - `backend/app/models/models.py:255-277` — `QuestionGroup` 列定义
  - `.omo/plans/question-import-full-repair.md:1.1` — 预期基线数值（2583 / 21 / 20 / 0 / 7 / 4 / 263 / 29）

  **Acceptance Criteria**:
  - [ ] 新备份文件存在且 `sqlite3.connect(bak)` 可打开、`PRAGMA integrity_check` 返回 `ok`
  - [ ] `backend/data/gates/baseline_snapshot.json` 存在且各数值 == 设计方案 §1.1 实测值
  - [ ] `backend/data/gates/gongzhuan_field_fingerprint.json` 存在，含 2583 条（或按 status 分组）指纹
  - [ ] 备份文件名含时间戳，且**未覆盖**任何既有 `.bak*`

  **QA Scenarios**:

  ```
  Scenario: 备份可打开且完整性检查通过
    Tool: Bash (PowerShell + 内联 Python)
    Preconditions: 真实库存在且后端进程运行中
    Steps:
      1. 运行 sqlite3 备份 API 生成 backend/data/question_bank.db.bak_import_<ts>
      2. python -c "import sqlite3;c=sqlite3.connect('<bak>');print(c.execute('PRAGMA integrity_check').fetchone()[0])"
      3. 断言输出恰为 "ok"
      4. python -c "import sqlite3;c=sqlite3.connect('<bak>');print(c.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0])"  → 断言等于 2583
    Expected Result: integrity_check = ok，question_bank 行数 = 2583（与备份时点一致）
    Failure Indicators: integrity_check 非 ok，或行数与真实库不符（备份不完整）
    Evidence: .omo/evidence/task-2-backup.txt
    Note: 内联 Python 必须用 @"..."@ here-string 且先设 $env:PYTHONIOENCODING='utf-8'

  Scenario: 基线快照与实测一致（防快照本身写错）
    Tool: Bash (PowerShell)
    Preconditions: 备份与快照均已生成
    Steps:
      1. 读 backend/data/gates/baseline_snapshot.json
      2. 逐键断言：question_bank.total == 2583、question_groups == 21、questions_with_group_id == 20、
         requirements_nonempty == 0、need_review == 7、answer_analysis_empty == 4、
         question_image == 263、exam_paper == 29
      3. 断言 import_record 分布为 COMPLETED 1064 / PREVIEW 429 / PARTIAL 6 / PARSING 1 / FAILED 1
    Expected Result: 全部逐键匹配，任一不符即视为快照错误，必须先查清再继续
    Failure Indicators: 任一数值不同（说明库状态已变或快照逻辑有 bug）
    Evidence: .omo/evidence/task-2-baseline.txt
  ```

  **Commit**: YES
  - Message: `chore(gate): capture DB backup and gongzhuan field fingerprints`
  - Files: `backend/data/gates/baseline_snapshot.json`, `backend/data/gates/gongzhuan_field_fingerprint.json`, `.gitignore`
  - Pre-commit: 不得 stage `*.db` / `*.bak*`

---

- [x] 3. 跑旧门禁记录现状基线并分类登记 52 个 pytest error

  **What to do**:
  - 跑 `python scripts/verify_parser_regression.py "D:\砺安题库\砺安题库\题库\公安题目（打印）" --out data/parser_regression.txt`（G1）
  - 跑 `python scripts/verify_xingce_regression.py`（G2 + G3）
  - 跑 `python -m pytest backend/tests -q`（G4），把**失败集合**逐条写入 `backend/data/gates/known_broken.json`，
    每条含：`nodeid`、`类型`（failure/error）、`首行错误摘要`、`归类`（如「引用已删除函数」「依赖外部服务」「环境缺失」）、`是否与本次改动相关`（默认 `false`）
  - 校验公专 5 项基线：2899 块 / 污染 0 / `{'单选题':2534,'多选题':249,'判断题':80,'简答题':36}` / `{'4':2796,'1':13,'2':14,'0':73,'3':3}` / PASS

  **Must NOT do**:
  - **禁止**为了让 G1 变绿而修改 `text_parser.py` 或 `verify_parser_regression.py` 的基线常量
  - **禁止**修复任何 pytest 失败（本轮只登记，不收敛）
  - **禁止**修改 `backend/data/regression_baseline_before.txt`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需解读门禁输出、分类 52 个 error、判断归因
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `diagnose`（本任务不修 bug，只登记）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0（与任务 1/2/4 并行）
  - **Blocks**: 5, 6, 7, 8, 11（门禁基线依赖此记录）
  - **Blocked By**: 2（需先备份，避免门禁意外写库）

  **References**:
  - `solve_problems_files/行测导入门禁与运维手册.md:35-75` — G1/G2/G3/pytest 的**精确命令与通过标准原文**（含编码设置两行，必须照抄）
  - `solve_problems_files/行测题目导入优化方案.md:75-83` — 门禁表 G1/G2/G3 的通过标准
  - `solve_problems_files/行测导入门禁与运维手册.md:69-75` — pytest 铁律 R-4：**判定标准是失败集合与基线完全一致，不要求全绿**
  - `backend/scripts/verify_parser_regression.py` — G1 脚本本体
  - `backend/scripts/verify_xingce_regression.py` — G2/G3 脚本本体
  - `.omo/plans/question-import-full-repair.md:1.1` — 必须逐项匹配的 5 项基线数值

  **Acceptance Criteria**:
  - [ ] G1 退出码 0 且输出 5 项与基线**逐项一致**
  - [ ] G2/G3 无新增失败
  - [ ] `known_broken.json` 条目数 == `16 failed + 52 errors` 之和，且每条有 `归类` 与 `是否与本次改动相关` 字段
  - [ ] `known_broken.json` 落盘且可被 `gate_all.py` 读取

  **QA Scenarios**:

  ```
  Scenario: G1 公专五项基线逐项一致
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8 编码；工作目录 backend
    Steps:
      1. python scripts/verify_parser_regression.py "D:\砺安题库\砺安题库\题库\公安题目（打印）" --out data/parser_regression.txt
      2. 断言 $LASTEXITCODE -eq 0
      3. 读 data/parser_regression.txt，断言「题目块总数」行 == 2899
      4. 断言「被污染题块数」== 0
      5. 断言「题型分布」== {'单选题': 2534, '多选题': 249, '判断题': 80, '简答题': 36}
      6. 断言「选项数分布」== {'4': 2796, '1': 13, '2': 14, '0': 73, '3': 3}
      7. 断言「验收结论」== PASS
    Expected Result: 退出码 0 且 5 项逐项匹配
    Failure Indicators: 任一项数值不同即为回归 → 立即停止，不得进入下一 Wave
    Evidence: .omo/evidence/task-3-g1-gongzhuan.txt

  Scenario: pytest 失败集合与基线完全一致，且已分类登记
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8 编码
    Steps:
      1. python -m pytest backend/tests -q 2>&1 | Tee-Object .omo/evidence/task-3-pytest-raw.txt
      2. 从输出提取失败 nodeid 列表，断言数量 == 16 failed
      3. 从输出提取 error nodeid 列表，断言数量 == 52 errors
      4. 读 backend/data/gates/known_broken.json，断言条目数 == 68，且每条含 nodeid/type/摘要/归类/是否与本次改动相关
      5. 断言所有条目的「是否与本次改动相关」均为 false
    Expected Result: 68 条全部登记且标注为非本次引入
    Failure Indicators: 数量不等于 16/52（基线已漂移，须查清）；或有条目缺字段
    Evidence: .omo/evidence/task-3-known-broken.txt
  ```

  **Commit**: YES
  - Message: `chore(gate): record legacy gate baselines and classify pytest debt`
  - Files: `backend/data/gates/known_broken.json`, `backend/data/parser_regression.txt`

---

- [x] 4. 复现 RC-1 / RC-2 并校验 9 个真实语料非空

  **What to do**:
  - **RC-1 复现**：在 `.vtj/vue/question_import.vue` 的 `fetchWithRetry` 临时把 `_pollImportStatus` 的 `timeoutMs` 改为 `1`（仅本地临时、**不提交**），验证是否复现「文件上传异常：signal is aborted without reason」；随后还原
  - **RC-2 复现**：用真实语料 S1 走完「上传 → 预览」，检查确认按钮文案是否显示「确认入库 0 题」、点击是否提示「无可导入的题目数据」
  - **RC-4 复现**：直接调用 `confirm_batch_import` 的内部逻辑（或构造一次带 `auto_detected_tags` 的 `/confirm`），确认是否抛 `NameError: confirmed_items`
  - **RC-5 证据**：查询 `SELECT COUNT(*) FROM question_bank WHERE requirements IS NOT NULL AND TRIM(requirements)<>''` → 断言为 0
  - **语料校验**：逐个 stat 9 个语料文件（S1–S9），断言 `size > 0`、扩展名/文件头一致、记录 SHA256 前 16 位到 `.omo/evidence/task-4-corpus.txt`

  **Must NOT do**:
  - **禁止**提交任何临时改动（RC-1 复现用的 `timeoutMs=1` 必须还原）
  - **禁止**在此任务中真正入库（复现只看 UI 文案与异常，不点确认）
  - **禁止**构造任何虚拟/空文档

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需精确控制临时改动、还原、Playwright 操作真实页面
  - **Skills**: `playwright`
  - **Skills Evaluated but Omitted**: `diagnose`（本任务只复现不修）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0（与任务 1/2/3 并行）
  - **Blocks**: 12, 16, 29（修复任务需要复现证据作为「修复前」对照）
  - **Blocked By**: 2（需先备份）

  **References**:
  - `.vtj/vue/question_import.vue:773-777` — 轮询 `10000, 0`，复现时的目标行
  - `.vtj/vue/question_import.vue:975-977` — `'文件上传异常：' + (e.message || '网络错误')`，要复现的文案出处
  - `.vtj/vue/question_import.vue:192-193` — 按钮文案读 `state.batchPreviewData.length`，RC-2 的现场
  - `.vtj/vue/question_import.vue:1050-1052` — 「无可导入的题目数据」的守卫
  - `backend/app/api/v1/question_import.py:3809` — `for item in confirmed_items:`，RC-4 的现场
  - `.omo/plans/question-import-full-repair.md:3.11.2` — **9 个语料的完整相对路径与覆盖目标**
  - `.omo/plans/question-import-full-repair.md:2` (RC-1/RC-2/RC-4/RC-5 四节的完整因果链) — 每条根因的代码行级依据

  **Acceptance Criteria**:
  - [ ] RC-1 复现截图/日志中存在字符串 `signal is aborted without reason`
  - [ ] RC-2 现场记录到按钮文案为「确认入库 0 题」且点击提示「无可导入的题目数据」
  - [ ] RC-4 复现到 `NameError: name 'confirmed_items' is not defined`
  - [ ] 9 个语料全部 `size > 0`，SHA256 已记录
  - [ ] `git status` 干净（无临时改动残留）

  **QA Scenarios**:

  ```
  Scenario: RC-1 复现出「signal is aborted without reason」
    Tool: Playwright
    Preconditions: 后端 8000 与 Vite 9527 均在运行；已登录教师账号
    Steps:
      1. 临时把 .vtj/vue/question_import.vue:776 的 10000 改为 1（不提交）
      2. Playwright 打开 http://localhost:9527/question-import，切到分离导入标签
      3. 用 setInputFiles 上传 S1（题库\公安题目（打印）\2020届公安院校公安专业联考考试《公安专业科目》真题.docx）
      4. 等待页面出现 ElMessage 错误提示
      5. 断言提示文本包含 "文件上传异常" 且包含 "signal is aborted without reason"
      6. 截图保存
      7. 还原 :776 为 10000，git status 必须干净
    Expected Result: 第 5 步断言成立 = RC-1 成功复现
    Failure Indicators: 未出现该文案（说明复现路径不对，需重新定位；不得跳过此复现）
    Evidence: .omo/evidence/task-4-rc1-repro.png + .txt（首行含 文件/大小/SHA256/import_id）

  Scenario: RC-2 复现出「确认入库 0 题」且无法入库
    Tool: Playwright
    Preconditions: 后端与 Vite 运行中；已登录；已还原 RC-1 的临时改动
    Steps:
      1. Playwright 上传 S1，等待预览列表渲染完成
      2. 断言预览列表 li/卡片数量 > 0（证明题目确实被识别出来了）
      3. 读取确认按钮文本，断言其匹配 /确认入库 0 题/
      4. 点击该按钮
      5. 断言出现 ElMessage "无可导入的题目数据"
      6. 查询 DB：SELECT COUNT(*) FROM question_bank WHERE import_time > <本任务开始时间>  → 断言为 0（零新增）
    Expected Result: 第 3/5/6 步全部成立 = RC-2 成功复现（识别成功但无法入库）
    Failure Indicators: 按钮显示非 0 题（说明代码已变，需重新取证）
    Evidence: .omo/evidence/task-4-rc2-repro.png + .txt

  Scenario: 9 个真实语料全部非空且文件头合法
    Tool: Bash (PowerShell)
    Preconditions: 无
    Steps:
      1. 对 S1..S9 逐个 Test-Path，断言存在
      2. 逐个断言 (Get-Item).Length -gt 0
      3. 逐个读前 4 字节，断言 .docx 为 50 4B 03 04（PK），.pdf 为 25 50 44 46（%PDF）
      4. 逐个记录 SHA256 前 16 位到 .omo/evidence/task-4-corpus.txt
    Expected Result: 9 个文件全部存在、非空、文件头与扩展名一致
    Failure Indicators: 任一文件缺失/为 0 字节/文件头与扩展名不符（须换语料并告知用户）
    Evidence: .omo/evidence/task-4-corpus.txt
  ```

  **Commit**: NO（本任务只取证，不产出代码改动）

- [x] 5. L0 静态红线门禁 `gate_l0_redlines.py`

  **What to do**:
  - 新建 `backend/scripts/gate_l0_redlines.py`，实现 6 条断言：
    1. `backend/app/services/text_parser.py::extract_question_blocks` **函数体** SHA256 == 基线
    2. `backend/app/api/v1/question_import.py` **共享 dispatch 块**（当前 4005-4011）SHA256 == 基线（基线：456 字符）
    3. `.vtj/files/question_import.json` SHA256 == 基线
    4. `.vtj/vue/question_import.vue` **第 1–493 行**（template 段）SHA256 == 基线
    5. `useProvider({ id:'question_import', version:'1790329880372' })` 字面量存在且 version 未变
    6. `extract_question_blocks` 未被 import 到任何新建模块（防误改道）
  - 基线存 `backend/data/gates/L0_redlines.json`；提供 `--update-baseline`（带二次确认）用于**有据可查**的变更
  - **用 AST/正则提取函数体，不用行号** —— 新增代码会使行号整体位移
  - 为每个断言函数写单测 `backend/tests/test_gate_l0.py`（含「篡改后必须失败」的反向用例）

  **Must NOT do**:
  - **禁止**使用行号比对（这是设计文档明令的哈希原因）
  - **禁止**自动 `--update-baseline`（必须人工显式传参）
  - **禁止**在本任务中修改任何被守护的文件

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单一脚本 + 单一 JSON 基线 + 单一测试文件
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `deep`（逻辑直白，无需深度推理）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 6/7/8/9/10/11 并行）
  - **Blocks**: 12, 13, 14, 16, 17, 18, 19, 30–35, 37–44（所有改动代码的任务收尾必跑）
  - **Blocked By**: None

  **References**:
  - `solve_problems_files/行测题目导入优化方案.md:62-73` — **铁律表 R-2/R-3/R-6** 原文（禁同步 DSL、禁改 template、公专逐字段未变）
  - `solve_problems_files/行测导入门禁与运维手册.md:312-326` — **红线清单 12 条原文**，含「校验方法：位移无关的字节比对，不要用行号」「已验证：dispatch 块 456 字符、separate_match_endpoint 函数体 11376 字符，与 HEAD 逐字节相等」
  - `CLAUDE.md/vtj.md:1305-1341` — 附录 F：raw 页禁止同步 DSL 的判定流程与自检命令
  - `.vtj/vue/question_import.vue:508` — `useProvider({ id: 'question_import', version: '1790329880372' })`
  - `backend/app/api/v1/question_import.py:4005-4011` — 共享 dispatch 块
  - `backend/app/services/text_parser.py` — `extract_question_blocks` 定义处

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l0_redlines.py` 退出码 0，6 条断言全 PASS
  - [ ] 6 条断言各自有一个**反向用例**：手动篡改被守护内容后必须 FAIL（`backend/tests/test_gate_l0.py`）
  - [ ] 耗时 < 3 秒
  - [ ] 基线 JSON 已入库

  **QA Scenarios**:

  ```
  Scenario: 正常状态下 L0 全绿
    Tool: Bash (PowerShell)
    Preconditions: 工作目录 backend；已设 UTF-8
    Steps:
      1. Measure-Command { python scripts/gate_l0_redlines.py }  记录耗时
      2. 断言 $LASTEXITCODE -eq 0 且输出含 6 个 "PASS"
      3. 断言耗时 < 3 秒
    Expected Result: 6/6 PASS，退出码 0，耗时 < 3s
    Failure Indicators: 任一 FAIL（说明已有代码改动越过了红线，须先定位是哪个任务越界）
    Evidence: .omo/evidence/task-5-l0-pass.txt

  Scenario: 篡改 template 段后 L0 必须 FAIL（门禁自身有效性）
    Tool: Bash (PowerShell)
    Preconditions: L0 已全绿
    Steps:
      1. 复制 .vtj/vue/question_import.vue 为临时备份（%TEMP%\opencode\qi.vue.bak）
      2. 在第 100 行 template 段内插入一个空格（改 1 字符）
      3. python scripts/gate_l0_redlines.py  → 必须退出码非 0，且明确报出「template 段」这条断言失败
      4. 从备份还原文件
      5. 再次运行 → 必须恢复退出码 0
      6. git status 必须干净
    Expected Result: 第 3 步 FAIL、第 5 步 PASS、git 干净
    Failure Indicators: 篡改后仍 PASS（门禁失效，必须修门禁本身）
    Evidence: .omo/evidence/task-5-l0-negative.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L0 static redline hash gate`
  - Files: `backend/scripts/gate_l0_redlines.py`, `backend/data/gates/L0_redlines.json`, `backend/tests/test_gate_l0.py`

---

- [x] 6. L3 落库链路门禁 `gate_l3_ingest.py` —— **最关键，必须先红后绿**

  **What to do**:
  - 新建 `backend/scripts/gate_l3_ingest.py`
  - **必须用内存临时库**：`sqlite3.connect(':memory:')` + 由 SQLAlchemy `Base.metadata.create_all` 建表，
    通过 `sessionmaker(bind=engine)` 注入，**绝不触碰 `data/question_bank.db`**
  - 实现 8 条断言（每条对应一条已定位缺陷）：

    | # | 断言 | 拦截 |
    |---|---|---|
    | 1 | 传入 N 题 → 库中恰好 N 题（**不多不少**） | 静默丢题 |
    | 2 | 传入 `requirements` → 该列非空 | **RC-5** |
    | 3 | 传入 `group_id` → 该列非空 + `question_groups` 行存在 | **RC-5** |
    | 4 | 任一题 `blocked=true` → 抛 HTTPException 且**库中零新增** | 阻断闸门失效 |
    | 5 | 改一个字段后入库 → 库中是新值（非 `preview_data` 旧快照） | **RC-3** |
    | 6 | 触发建卷路径时**不抛 NameError** | **RC-4** |
    | 7 | 返回的 `new_question_ids` 数量 == `success_count` | 黑箱返回 |
    | 8 | 同一 payload 重复调用 → 幂等，不产生重复题 | 重传事故 |

  - **先红后绿**：第一步只写断言不改实现，**必须先跑出失败**（复现 RC-3/RC-4/RC-5），
    证据存 `.omo/evidence/task-6-red.txt`；任务 17/18/19 修完后转绿
  - 为每条断言写单测 `backend/tests/test_gate_l3.py`

  **Must NOT do**:
  - **禁止**在脚本任何路径上打开 `data/question_bank.db`（必须断言 `db.bind.url.database == ':memory:'` 或 `':memory:' in str(engine.url)`）
  - **禁止**在此任务中修改 `_upsert_question_core` / `/batch-parsed` / `/confirm`（修复归任务 17/18/19）
  - **禁止**为了让门禁变绿而弱化断言

  **Recommended Agent Profile**:
  - **Category**: `deep` — 需要设计内存库注入、构造覆盖全部 8 条断言的 payload、处理事务与 SQLAlchemy session 生命周期
  - **Skills**: `tdd`
  - **Skills Evaluated but Omitted**: `ultrabrain`（目标明确，深度足够）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 5/7/8/9/10 并行；11 需等本任务）
  - **Blocks**: 17, 18, 19, 29, 45
  - **Blocked By**: 2（需先确认真实库已备份，防止误写）

  **References**:
  - `backend/app/api/v1/question_import.py:2013` — `_upsert_question_core` 签名（`db, current_user, question_data`），断言的调用入口
  - `backend/app/api/v1/question_import.py:2032-2037` — **已有的 blocked 闸门**（`raise HTTPException(400)`），断言 4 的依据
  - `backend/app/api/v1/question_import.py:2190` / `:2214` — `group_id` 与 `requirements` 的写入点，断言 2/3 的依据
  - `backend/app/api/v1/question_import.py:2601` — `/batch-parsed` 端点（当前**未**接 requirements/group_id/blocked）
  - `backend/app/api/v1/question_import.py:3575-3863` — `/confirm` 端点全流程；`:3610` 读 `preview_data.items`（RC-3）、`:3809` `confirmed_items`（RC-4）
  - `backend/app/models/models.py:166-252` — `QuestionBank` 列定义（断言 1/2/3 的字段清单）
  - `backend/app/models/models.py:255-277` — `QuestionGroup` 列定义
  - `solve_problems_files/行测导入门禁与运维手册.md:127-142` — WAL 备份禁忌（本任务用内存库正是为规避此风险）
  - `.omo/plans/question-import-full-repair.md:3.8.2` — L3 层的 8 条断言设计表

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l3_ingest.py` 当前**退出码非 0**（已复现 RC-3/RC-4/RC-5），证据 `.omo/evidence/task-6-red.txt`
  - [ ] 脚本内含 `assert ':memory:' in str(engine.url)` 形式的自我保护
  - [ ] 8 条断言各有单测；「篡改实现后必须 FAIL」的反向用例存在
  - [ ] 任务 17/18/19 完成后退出码 0（证据 `.omo/evidence/task-6-green.txt`）

  **QA Scenarios**:

  ```
  Scenario: 门禁脚本绝不触碰真实库（安全性第一）
    Tool: Bash (PowerShell)
    Preconditions: 真实库已按任务 2 备份
    Steps:
      1. 记录真实库文件大小与 mtime（Get-Item backend/data/question_bank.db）
      2. 运行 python scripts/gate_l3_ingest.py（允许失败）
      3. 再次读取真实库大小与 mtime
      4. 断言两次完全一致（字节数与 mtime 均未变）
      5. grep 脚本源码，断言不含 'question_bank.db' 字符串
    Expected Result: 真实库零变化，脚本源码不含真实库路径
    Failure Indicators: mtime 或大小变化（门禁写库了 —— 严重事故，必须立刻停止并回滚）
    Evidence: .omo/evidence/task-6-no-realdb.txt

  Scenario: 门禁先红 —— 成功复现 RC-5（requirements 丢失）
    Tool: Bash (PowerShell)
    Preconditions: 脚本已实现断言 1/2/3
    Steps:
      1. 运行 python scripts/gate_l3_ingest.py -v
      2. 断言退出码非 0
      3. 断言输出中明确出现断言 2（requirements 非空）FAILED
      4. 断言输出中明确出现断言 3（group_id 非空）FAILED
      5. 断言输出中明确出现断言 5/6（RC-3/RC-4）FAILED
    Expected Result: 至少 4 条断言 FAILED = 成功复现真实缺陷
    Failure Indicators: 全部 PASS（说明断言写得太弱，必须加强，否则门禁无价值）
    Evidence: .omo/evidence/task-6-red.txt

  Scenario: 断言 1 能抓住静默丢题
    Tool: Bash (PowerShell)
    Preconditions: 脚本已实现断言 1
    Steps:
      1. 构造 5 题 payload，其中第 3 题 answer 故意留空（触发旧 _normalize_question 的 return None 分支）
      2. 运行单测 pytest backend/tests/test_gate_l3.py -k "exactly_n_questions" -v
      3. 断言测试 FAIL，且失败信息显示「传入 5 题，库中仅 4 题」
    Expected Result: 断言 1 精确抓出入口数不符
    Failure Indicators: 测试 PASS（说明断言 1 写错，无法感知丢题）
    Evidence: .omo/evidence/task-6-no-silent-drop.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L3 ingest contract gate with in-memory DB`
  - Files: `backend/scripts/gate_l3_ingest.py`, `backend/tests/test_gate_l3.py`

---

- [x] 7. L1 解析器结构化指纹门禁 `gate_l1_parser.py`

  **What to do**:
  - 新建 `backend/scripts/gate_l1_parser.py`，统一入口
    `python scripts/gate_l1_parser.py --subject gongzhuan|xingce|shenlun`
  - 复用**现有** `verify_parser_regression.py` / `verify_xingce_regression.py` 的语料装载逻辑，不重写
  - 每科输出 JSON 指纹并与 `backend/data/gates/L1_{subject}_baseline.json` **逐键比对**：
    ```
    块数 / 题型分布 / 选项数分布 / 答案覆盖率 / 解析覆盖率
    blocked 率 / need_review 率 / 题号单调性违例数 / 平均块长度 / 最短块长度
    污染计数（UTB 标记 / 测试模板 / 促销文本）
    材料块数 / 题组候选数
    ```
  - 新增键必须显式 `--accept-new-key` 并在 commit message 说明理由
  - 公专基线必须精确等于：2899 块 / 污染 0 / `{'单选题':2534,'多选题':249,'判断题':80,'简答题':36}` / `{'4':2796,'1':13,'2':14,'0':73,'3':3}`
  - 支持 `--subject` 局部跑；退出码非 0 表示漂移

  **Must NOT do**:
  - **禁止**新建题号解析器或改动 `text_parser.py` 任何逻辑（本任务只做指纹采集与比对）
  - **禁止**自动更新基线（必须 `--accept-new-key` 显式传参）
  - **禁止**把 G1 的 5 项数字换成新的自定义指标（必须包含原有 5 项）

  **Recommended Agent Profile**:
  - **Category**: `deep` — 需要设计可归一化的结构化指纹、逐键 diff 报告、三科语料装载复用
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（需跨三科语料的统计聚合，逻辑不简单）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 5/6/8/9/10 并行）
  - **Blocks**: 11, 32, 33, 34（新增指纹键的下钻任务需先有框架）
  - **Blocked By**: 3（需任务 3 确认现状基线）

  **References**:
  - `backend/scripts/verify_parser_regression.py` — G1 脚本，语料装载与 5 项指标的**唯一来源**，必须复用而非重写
  - `backend/scripts/verify_xingce_regression.py` — G2/G3 脚本，行测/申论不变量来源
  - `solve_problems_files/行测导入门禁与运维手册.md:35-64` — G1/G2 的精确通过标准
  - `solve_problems_files/行测题目导入优化方案.md:15-26` — 语料实测 S1–S7（170 份全含文本层、材料块 364 等），公专/行测指纹的期望区间依据
  - `backend/app/services/text_parser.py:3132-3149` — `_IMAGE_MARKER_RE` 与占位符协议（污染/图片计数的依据）
  - `.omo/plans/question-import-full-repair.md:3.8.2` — L1 层的指纹键清单

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l1_parser.py --subject gongzhuan` 退出码 0，指纹含原 G1 的 5 项且数值一致
  - [ ] `--subject xingce` / `--subject shenlun` 均退出码 0
  - [ ] 手动改基线一个数值后重跑 → 必须退出码非 0 且指出具体漂移键
  - [ ] 耗时：gongzhuan < 120s，xingce < 300s

  **QA Scenarios**:

  ```
  Scenario: 三科指纹全部生成且公专含原 5 项
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8；工作目录 backend
    Steps:
      1. python scripts/gate_l1_parser.py --subject gongzhuan -o .omo/evidence/task-7-gongzhuan.json
      2. 断言退出码 0
      3. 断言 JSON 含键 块数 且值 == 2899
      4. 断言 JSON 含键 污染计数 且值 == 0
      5. 断言 JSON 含键 题型分布 且值 == {"单选题":2534,"多选题":249,"判断题":80,"简答题":36}
      6. 断言 JSON 含键 选项数分布 且值 == {"4":2796,"1":13,"2":14,"0":73,"3":3}
      7. python scripts/gate_l1_parser.py --subject xingce  → 断言退出码 0
      8. python scripts/gate_l1_parser.py --subject shenlun  → 断言退出码 0
    Expected Result: 三科退出码均为 0，公专 4 项断言逐项匹配
    Failure Indicators: 公专任一项数值不同 = 解析器已被污染 → 立即停止
    Evidence: .omo/evidence/task-7-l1-gongzhuan.json

  Scenario: 指纹漂移能被精确检出（门禁有效性）
    Tool: Bash (PowerShell)
    Preconditions: L1 已全绿
    Steps:
      1. 备份 backend/data/gates/L1_gongzhuan_baseline.json
      2. 把基线里的 块数 从 2899 改成 2898（仅改基线，不改代码）
      3. python scripts/gate_l1_parser.py --subject gongzhuan  → 必须退出码非 0
      4. 断言输出明确指出「块数: 基线 2898 vs 实际 2899」
      5. 还原基线，重跑 → 退出码 0
    Expected Result: 漂移被检出并精确定位到键
    Failure Indicators: 退出码 0（门禁失效，等于没有门禁）
    Evidence: .omo/evidence/task-7-l1-drift.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L1 structured parser fingerprint for three subjects`
  - Files: `backend/scripts/gate_l1_parser.py`, `backend/data/gates/L1_gongzhuan_baseline.json`, `backend/data/gates/L1_xingce_baseline.json`, `backend/data/gates/L1_shenlun_baseline.json`

- [x] 8. L2 匹配配对门禁 `gate_l2_matching.py`

  **What to do**:
  - 新建 `backend/scripts/gate_l2_matching.py`，归并 `verify_xingce_regression.py` 的行测/申论不变量
  - 行测断言：分节序列全等 / 分节区间一致 / 答案锚点覆盖 100% / `blocked=0` /
    ★ **新增守卫 1：图形推理指令句不得被判为同题**（历史上「131 题中 79 题被判重复静默丢弃」的 60% 事故）
  - 申论断言：`answer_block_count_mismatch` 必须为 0，**除非在白名单**；
    ★ **新增守卫 2：合订本 2019 两份进白名单**（它们当前是**正确阻断**，一旦修复就移出白名单）
  - 白名单存 `backend/data/gates/L2_blocklist.json`，每条含文件名 + 原因 + 登记日期

  **Must NOT do**:
  - **禁止**放宽或删除 `answer_block_count_mismatch` 的阻断（那是用户硬约束）
  - **禁止**在本任务中修改 `text_parser.py` 的申论/行测逻辑
  - **禁止**把 2019 两份从白名单移除（尚未修复，白名单是正确状态）

  **Recommended Agent Profile**:
  - **Category**: `deep` — 需理解行测分节路由与答案锚点机制，设计图形推理指令句的识别判据
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（图形推理去重判据需语料实证）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 5/6/7/9/10 并行）
  - **Blocks**: 11, 33, 35
  - **Blocked By**: 3

  **References**:
  - `backend/scripts/verify_xingce_regression.py` — G2/G3 脚本本体，断言复用来源
  - `solve_problems_files/行测题目导入优化方案.md:29-59` — 差因诊断（T1）与安全网结构校验的局限（安徽 2023 vs 2024 分节区间完全一致，`blocked_count=0`）
  - `solve_problems_files/行测题目导入优化方案.md:137-165` — §7.1 T16 阻塞根因：图形推理题区分信息在图片里不在文本层，`_detect_duplicate` 按文本相似度会误判
  - `.omo/evidence/task-16-dedup-rootcause.txt` — 四个去重口径选项的原始证据
  - `.omo/handoff-shenlun-v4.md:145-202` — 2019 两份的逐行版式证据与 `answer_block_count_mismatch` 正确性论证
  - `solve_problems_files/行测题目导入优化方案.md:62-73` — 铁律 R-6：**宁可阻断报错交人工，不允许静默丢题**

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l2_matching.py` 退出码 0
  - [ ] 新增守卫 1 有**实证反例**：临时把去重改回文本相似度 → 必须 FAIL
  - [ ] 白名单含且仅含 2019 地市级 + 2019 省级两条
  - [ ] 耗时 < 300s

  **QA Scenarios**:

  ```
  Scenario: L2 全绿且白名单正确
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8；工作目录 backend
    Steps:
      1. python scripts/gate_l2_matching.py -v  → 断言退出码 0
      2. 读 backend/data/gates/L2_blocklist.json，断言长度 == 2
      3. 断言两条文件名均含 "2019" 且均含 "申论"
      4. 断言「答案段数与题目数不匹配」类断言的实际违规数 == 白名单条数（2）
    Expected Result: 退出码 0，白名单恰含 2 条且与实际阻断一一对应
    Failure Indicators: 白名单为空（说明 2019 被错误放行 → 盲配风险）；或白名单 > 2 条（有新的静默盲配）
    Evidence: .omo/evidence/task-8-l2.txt

  Scenario: 守卫 1 能抓住图形推理题被误判同题（历史 60% 事故）
    Tool: Bash (PowerShell)
    Preconditions: L2 已全绿
    Steps:
      1. 用题库\行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）题本.pdf 跑 L2，记录「图形推理指令句被判同题数」
      2. 断言该数 == 0
      3. 临时把去重口径改回「按 content 文本相似度」（备份后改，跑，断言守卫 1 FAIL 且报出被误判的题号
      4. 还原，断言守卫 1 恢复 PASS
    Expected Result: 现状 0 条；改坏后必然 FAIL 且能列出被误判题号
    Failure Indicators: 改坏后仍 PASS（守卫 1 形同虚设）
    Evidence: .omo/evidence/task-8-l2-figure-guard.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L2 matching invariants with figure-reasoning guard`
  - Files: `backend/scripts/gate_l2_matching.py`, `backend/data/gates/L2_blocklist.json`

---

- [x] 9. L4 API 契约门禁 `gate_l4_api_contract.py`

  **What to do**:
  - 新建 `backend/scripts/gate_l4_api_contract.py`，**归并并取代**零散的
    `verify_task11_endpoint.py` / `verify_task11_auth.py` / `verify_task11_vite.py`
  - 断言 4 类：
    1. `openapi.json` 快照比对：导入相关端点的**路径 / 方法 / 必填字段**不得漂移
    2. 走真实 ASGI 栈（`httpx.ASGITransport`）覆盖 401 / 403 / 404 / 409 / 422 各分支
    3. **经 Vite 9527 代理实请求**验证非 502（防「改完不重启后端 → 误判前端有问题」）
    4. 新增端点注册校验：`/records/{id}/preview` 必须在 OpenAPI 中存在
  - 旧的三个脚本**移入** `backend/scripts/_archive/`（不删除，留可追溯）

  **Must NOT do**:
  - **禁止**在本任务中新增/修改任何端点实现
  - **禁止**删除旧脚本（只移入 `_archive/`）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需真实 ASGI 栈 + 代理链路 + 鉴权分支覆盖
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（需覆盖 5 类错误分支 + 代理链路验证）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 5/6/7/8/10 并行）
  - **Blocks**: 11, 13（新增 `/preview` 端点后需复验）
  - **Blocked By**: None

  **References**:
  - `backend/scripts/verify_task11_endpoint.py` — 20 项断言的来源，迁移对象
  - `backend/scripts/verify_task11_auth.py` — 鉴权与入参校验（走真实 ASGI 栈），迁移对象
  - `backend/scripts/verify_task11_vite.py` — 经 9527 实请求，迁移对象
  - `solve_problems_files/行测导入门禁与运维手册.md:107-125` — §4 Vite/后端探测：OpenAPI 必须同时出现 `/separate-match` 与 `/separate-match-xingce`；**502 的根因是 8000 未 `--reload`**
  - `backend/app/api/v1/question_import.py:3279` — `/upload` 端点；`:3349` — `/records/{id}/status`（L4 契约基线）
  - `.omo/evidence/task-11-endpoint-vite.txt` / `task-11-g8-vite.txt` — 已有的真实请求证据

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l4_api_contract.py` 退出码 0
  - [ ] 5 类错误分支各至少 1 个用例且被实际覆盖
  - [ ] 旧三脚本已移入 `backend/scripts/_archive/`，`git status` 可见明确的 rename
  - [ ] 耗时 < 30s

  **QA Scenarios**:

  ```
  Scenario: API 契约快照一致 + 五类错误分支被覆盖
    Tool: Bash (PowerShell)
    Preconditions: 后端 8000 运行中；已设 UTF-8
    Steps:
      1. python scripts/gate_l4_api_contract.py -v  → 断言退出码 0
      2. 断言输出含 "401 PASS"、"403 PASS"、"404 PASS"、"409 PASS"、"422 PASS" 各一行
      3. 断言 openapi 快照 diff 为空
    Expected Result: 退出码 0，五类分支全 PASS，契约零漂移
    Failure Indicators: 契约漂移（说明有人改了端点签名未同步本门禁）
    Evidence: .omo/evidence/task-9-l4.txt

  Scenario: 经 9527 代理实请求不返回 502
    Tool: Bash (PowerShell)
    Preconditions: 后端 8000 与 Vite 9527 均运行中；后端已 --reload
    Steps:
      1. 先确认后端已加载新路由：读 http://localhost:8000/openapi.json，断言 paths 含 *separate-match*
      2. Invoke-WebRequest http://localhost:9527/api/questions/import/mineru-health  → 断言 StatusCode == 200
      3. 断言响应体含 "available"
    Expected Result: 200 且响应体正确
    Failure Indicators: 502（后端未 --reload，须先重启后端，不得误判为前端缺陷）
    Evidence: .omo/evidence/task-9-l4-vite.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L4 API contract gate, archive task11 scripts`
  - Files: `backend/scripts/gate_l4_api_contract.py`, `backend/scripts/_archive/verify_task11_*.py`

---

- [x] 10. L5 前端数据契约门禁 `gate_l5_frontend_contract.py`

  **What to do**:
  - 新建 `backend/scripts/gate_l5_frontend_contract.py`，两段：
    - **静态段**：`.vtj/vue/question_import.vue` 必须包含标识符清单
      （`pendingQuestions`、`hasBlockedQuestions`、`handleFetchError`、`blocked`、`block_reasons`、
      `requirements`、`group_id`、`_uploadAndPoll`、`_pollImportStatus`）
    - **★ 反向守卫（RC-2 专属）**：禁止再出现 `state.batchPreviewData.length` 这类**读错状态字段**的写法。
      具体规则：凡「按钮计数 / disabled / 阻断判定 / 空守卫」四处，**必须**读 `pendingQuestions`，直接读
      `batchPreviewData` 即 FAIL
  - **运行时段**（可选，Playwright）：导入预览页能实际渲染出「材料块 + 小题列表 + 各题答案解析」
  - 同样覆盖 `question_preview_list.vue` / `teacher_questions.vue` / `admin_questions.vue` / `answer_page.vue`
    的关键标识符存在性

  **Must NOT do**:
  - **禁止**在本任务中改任何 `.vue`（本任务只建门禁，缺失标识符由任务 16/23/24/26 补）
  - **禁止**放宽反向守卫的匹配范围

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需设计「正向必需 + 反向禁止」双向 grep 规则，误报控制是关键
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（正则规则需精细调误报）

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 5/6/7/8/9 并行）
  - **Blocks**: 11, 16
  - **Blocked By**: None

  **References**:
  - `.vtj/vue/question_import.vue:192-193` — 按钮计数与 disabled 的**违规现场**（读 `state.batchPreviewData.length`）
  - `.vtj/vue/question_import.vue:609-616` — `blockedQuestionList` / `hasBlockedQuestions` 的**违规现场**
  - `.vtj/vue/question_import.vue:1050-1052` — 空守卫的**违规现场**
  - `.vtj/vue/question_import.vue:697-707` — `handleFetchError`（必须被调用而非绕过）
  - `.vtj/vue/question_preview_list.vue:40-90` — 材料块 + `requirements` 的渲染标识符
  - `CLAUDE.md/vtj.md:313-326` — §3.1 职责分离：Claude Code 只改 `<script>`，不碰 template
  - `solve_problems_files/行测题目导入优化方案.md:279-295` — §10 前端改动须知表（只改 script / 禁同步 DSL / version 不得变更 / 必须透传 blocked 与 block_reasons）

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l5_frontend_contract.py` 在**任务 16 完成前**必须 FAIL（因 `pendingQuestions` 尚不存在）
  - [ ] 任务 16 完成后退出码 0
  - [ ] 反向守卫有**实证反例**：把 `:192` 改回 `state.batchPreviewData.length` → 必须 FAIL

  **QA Scenarios**:

  ```
  Scenario: 修复前 L5 必须 FAIL（证明门禁抓得住）
    Tool: Bash (PowerShell)
    Preconditions: 任务 16 尚未完成
    Steps:
      1. python scripts/gate_l5_frontend_contract.py -v  → 断言退出码非 0
      2. 断言输出明确指出「缺少必需标识符 pendingQuestions」
      3. 断言输出明确指出「违规：按钮计数直接读 state.batchPreviewData.length」
    Expected Result: 两条违规都被检出 = 门禁有效
    Failure Indicators: 退出码 0（门禁写得太弱，RC-2 会重新溜进来）
    Evidence: .omo/evidence/task-10-l5-red.txt

  Scenario: 反向守卫能精准定位四处违规点
    Tool: Bash (PowerShell)
    Preconditions: L5 已实现
    Steps:
      1. 运行 gate_l5_frontend_contract.py --only reverse-guard -v
      2. 断言输出恰好列出 4 处违规，行号分别落在 :192（按钮计数）、:193（按钮文案）、
         :610（blockedQuestionList）、:1050（空守卫）附近
    Expected Result: 4 处违规全部列出且行号正确
    Failure Indicators: 少于 4 处（漏检）；或多出无关行（误报，需收紧正则）
    Evidence: .omo/evidence/task-10-l5-reverse.txt
  ```

  **Commit**: YES
  - Message: `test(gate): L5 frontend data contract with RC-2 reverse guard`
  - Files: `backend/scripts/gate_l5_frontend_contract.py`

---

- [x] 11. `gate_all.py` 一键入口、结果机读与 CI 接线

  **What to do**:
  - 新建 `backend/scripts/gate_all.py`，顺序执行 L0→L5，**聚合退出码**，输出统一报告
  - 支持 `--quick`（只跑 L0+L1）、`--layer L<N>`、`--subject <科>`、`--json <outfile>`
  - 每次执行写 `backend/data/gates/last_run.json`（各层耗时、退出码、失败断言摘要、git commit hash）
  - 新建 `backend/data/gates/known_broken.json` 的消费逻辑（从任务 3 的产物读取）
  - 接线：`.pre-commit-config.yaml` 加 **L0**（本地秒级）；`.github/workflows/` 加 **L0+L1+L3**

  **Must NOT do**:
  - **禁止**在 pre-commit 里放 L1 以上的层（耗时会让开发无法提交）
  - **禁止**让 `gate_all.py` 修改任何基线文件
  - **禁止**在 `gate_all.py` 中打开真实库写入

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需子进程编排、超时控制、退出码聚合、CI 配置
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（涉及 6 个子脚本的编排与超时）

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 收尾（必须等 5/6/7/8/9/10 全部完成）
  - **Blocks**: 12–45（**全局**：每个任务的收尾验证都跑它）
  - **Blocked By**: 5, 6, 7, 8, 9, 10

  **References**:
  - `backend/scripts/gate_l0_redlines.py` … `gate_l5_frontend_contract.py` — Wave 1 前 6 个任务的产物
  - `backend/data/gates/known_broken.json` — 任务 3 的产物（68 条债务登记）
  - `.pre-commit-config.yaml` — 现有 hook 配置，接入点
  - `.github/workflows/` — 现有 CI 配置，接入点
  - `solve_problems_files/行测导入门禁与运维手册.md:26-34` — 编码设置两行（`gate_all.py` 调用各门禁时也必须带）

  **Acceptance Criteria**:
  - [ ] `python scripts/gate_all.py` 一次执行输出 6 层报告，退出码 = 各层聚合
  - [ ] `--quick` 耗时 < 10s 且只跑 L0+L1
  - [ ] `last_run.json` 含 git commit hash、每层耗时与失败摘要
  - [ ] 故意让 L3 失败 → `gate_all.py` 退出码非 0 且报告明确指出 L3

  **QA Scenarios**:

  ```
  Scenario: 全量执行与 quick 执行
    Tool: Bash (PowerShell)
    Preconditions: Wave 1 前 6 个任务完成
    Steps:
      1. python scripts/gate_all.py  → 记录耗时与退出码
      2. 断言报告含 L0..L5 六行（L3 此时预期 FAIL，因任务 17/18/19 未做）
      3. python scripts/gate_all.py --quick  → 断言耗时 < 10s，报告只含 L0 与 L1
      4. 读 backend/data/gates/last_run.json，断言含 git_commit 字段且非空
    Expected Result: 第 2/3/4 步成立；全量退出码此时非 0（L3 红是有意的）
    Failure Indicators: quick 超过 10s（会拖慢每次提交）；last_run.json 缺 git_commit
    Evidence: .omo/evidence/task-11-gate-all.txt

  Scenario: 退出码正确聚合（不能被部分成功掩盖）
    Tool: Bash (PowerShell)
    Preconditions: 同上
    Steps:
      1. 临时把 gate_l2_matching.py 的一个断言改坏（备份后改）
      2. python scripts/gate_all.py  → 断言退出码非 0
      3. 断言报告明确指出 "L2 FAILED" 且给出失败断言名
      4. 还原，重跑 → 断言报告恢复为"L2 PASS"（其余层状态不变）
    Expected Result: 任一层失败必然导致整体非 0，且失败层被精确定位
    Failure Indicators: L2 失败但整体退出码 0（聚合逻辑有漏）
    Evidence: .omo/evidence/task-11-gate-aggregate.txt
  ```

  **Commit**: YES
  - Message: `test(gate): unified gate_all entrypoint with CI and pre-commit wiring`
  - Files: `backend/scripts/gate_all.py`, `.pre-commit-config.yaml`, `.github/workflows/*.yml`

- [x] 12. 模块 A 前端：轮询超时、重试、错误文案（A-1..A-4）

  **What to do**（仅改 `.vtj/vue/question_import.vue` 的 `<script>`，改动全在 494 行之后）:
  - `:773-777` 状态轮询 `fetchWithRetry(..., 10000, 0)` → `30000, 2`
  - `:804` 上传 `60000, 0` → `180000, 1`（6.33 MB docx 留足余量）
  - `:672` `controller.abort()` → `controller.abort(new Error('client timeout: ' + timeoutMs + 'ms'))`，使超时与真实错误可区分
  - `:688` 重试间隔加抖动：`1000 * (attempt + 1)` → `800 * (attempt + 1) + Math.floor(Math.random() * 400)`
  - `:975-977` catch 改为 `ElMessage.error(this.handleFetchError(e, '文件上传'))`；
    AbortError 时给专属文案：「解析仍在后台进行，请点『刷新预览』，**不要重复上传**」

  **Must NOT do**:
  - **禁止**改 `<template>`（1–493 行）；**禁止**改 `useProvider` version；**禁止**同步 `.vtj/files/*.json`
  - **禁止**把超时改回小于 15s；**禁止**移除重试

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单文件 `<script>` 的 5 处定点修改
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `visual-engineering`（无 UI 变更）

  **Parallelization**: Can Run In Parallel: YES | **Parallel Group**: Wave 2（与 13/14/15 并行）| **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `.vtj/vue/question_import.vue:666-693` — `fetchWithRetry` 本体（重试分支当前永不执行，因所有调用点传 `retries=0`）
  - `.vtj/vue/question_import.vue:697-707` — `handleFetchError`（已存在的中文文案函数，被 :976 绕过）
  - `.vtj/vue/question_import.vue:766-791` — `_pollImportStatus`（`10000, 0` 在 :776）
  - `.vtj/vue/question_import.vue:797-823` — `_uploadAndPoll`（`60000, 0` 在 :804）
  - `CLAUDE.md/vtj.md:1305-1341` — 附录 F：raw 页禁止同步 DSL 的自检命令
  - `.omo/plans/question-import-full-repair.md:2` (RC-1) — 完整五环因果链
  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l0_redlines.py` 退出码 0（template 段与 DSL 零改动）
  - [ ] `python scripts/gate_l5_frontend_contract.py` 仍只报 `pendingQuestions` 缺失（未引入新违规）
  - [ ] `git diff --stat -- .vtj/vue/question_import.vue` 的改动行号**全部 > 493**
  - [ ] Invoke-WebRequest http://localhost:9527/ → 200（**必须实际请求 Vite，不能只靠 SFC 编译通过**）
  **QA Scenarios**:
  ```
  Scenario: 6.33 MB 真实 docx 上传全程无 abort
    Tool: Playwright
    Preconditions: 后端 8000 + Vite 9527 运行；已登录教师
    Steps:
      1. 打开 http://localhost:9527/question-import，切分离导入
      2. setInputFiles 上传 题库\公安题目（打印）\2020届公安院校公安专业联考考试《公安专业科目》真题.docx
      3. waitForText 「确认入库」 或预览列表出现，timeout 300000
      4. 断言页面**未出现**含 "signal is aborted" 的 ElMessage
      5. 断言 import_id 只新增 **1 条**：查 question_import_record 中 original_filename 等于该文件名且 import_time 在本次之后 → COUNT == 1
      6. 截图
    Expected Result: 无 abort；预览出现；仅 1 条 import 记录（证明不再因误报而重传）
    Failure Indicators: 出现 abort 文案；或新增 2 条 import 记录
    Evidence: .omo/evidence/task-12-poll-timeout.png + .txt（首行四要素）
  Scenario: 慢轮询不再被误判为失败（重试生效）
    Tool: Playwright
    Preconditions: 同上
    Steps:
      1. 上传同 S1，但在 DevTools 把 /records/*/status 的首个响应延迟 12 秒（Playwright route 拦截）
      2. 断言页面**不出现**任何错误 ElMessage
      3. 断言最终仍进入 PREVIEW，预览题数 > 0
      4. 断言浏览器 console 无 "[fetchWithRetry] Timeout after 10000ms"（旧阈值）
    Expected Result: 12 秒的慢响应被 30s 超时 + 重试吸收，导入正常完成
    Failure Indicators: 出现错误提示（超时阈值或重试未生效）
    Evidence: .omo/evidence/task-12-retry.png
  ```
  **Commit**: YES — `fix(import): raise poll timeout, add retry, route errors through handleFetchError` — Files: `.vtj/vue/question_import.vue`

---

- [x] 13. 模块 A 后端：状态接口瘦身 + 预览重挂 + 去掉同步兜底（A-5/A-6/A-7）

  **What to do**（`backend/app/api/v1/question_import.py`）:
  - `:3349-3423` `get_import_parse_status`：`status=='PREVIEW'` 时**不再** `load_json_lenient(record.preview_data)` 反序列化全量 JSON，改为返回 `has_result: true` + `preview_url`
  - 新增 `GET /records/{import_id}/preview` 返回完整预览数据（供前端单独取）
  - `:3330-3335` 去掉「未注入 BackgroundTasks 就退化为同步解析」的**阻塞兜底**，改为启动期断言 + 明确 `503`
  - 权限校验沿用现有 `admin/teacher 或本人` 逻辑（`:3368-3371`）

  **Must NOT do**:
  - **禁止**改动 `:4005-4011` 共享 dispatch 块（字节级红线）
  - **禁止**改动 `:376-4053` 的 `separate_match_endpoint` 函数体（11376 字符红线）
  - **禁止**改动 `extract_question_blocks`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需新增端点、拆分响应体、保证向后兼容
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（涉及响应契约变更与兼容分支）
  **Parallelization**: Can Run In Parallel: YES | Wave 2（与 12/14/15 并行）| **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:3349-3423` — 状态接口本体（`load_json_lenient` 全量反序列化在 :3405）
  - `backend/app/api/v1/question_import.py:211-248` — `dump_json_once` / `load_json_lenient`（双重编码兼容工具，新增端点须复用）
  - `backend/app/api/v1/question_import.py:3330-3335` — `BackgroundTasks` 注入与同步兜底
  - `solve_problems_files/行测导入门禁与运维手册.md:107-125` — 502 根因（未 --reload），新增端点后必须按此验证
  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l0_redlines.py` 退出码 0
  - [ ] `GET /records/{id}/status` 单次响应耗时 < 100ms（用真实 PREVIEW 记录测）
  - [ ] OpenAPI 含 `/api/questions/import/records/{import_id}/preview`
  - [ ] `gate_l4_api_contract.py` 退出码 0
  **QA Scenarios**:
  ```
  Scenario: 状态接口不再反序列化大 JSON
    Tool: Bash (PowerShell)
    Preconditions: 后端已 --reload 重启；库中存在 PREVIEW 且 total_questions=120 的记录
    Steps:
      1. 取该 import_id，Measure-Command 连续 5 次 GET /records/{id}/status
      2. 断言平均耗时 < 100ms
      3. 断言响应体含 has_result == true 且**不含** questions 数组
      4. GET /records/{id}/preview → 断言含 questions 且长度 == 120
    Expected Result: 状态接口轻量且 < 100ms；预览数据从新端点单独取
    Failure Indicators: 状态响应仍含 questions（未瘦身）；或耗时 > 500ms
    Evidence: .omo/evidence/task-13-status-slim.txt
  Scenario: 无 BackgroundTasks 注入时明确 503 而非阻塞
    Tool: Bash (PowerShell + 内联 Python)
    Preconditions: 无
    Steps:
      1. python -c 直接调用 upload_file_for_import 但 background_tasks=None
      2. 断言抛出 HTTPException 且 status_code == 503
      3. 断言响应 detail 含 "后台任务" 字样
    Expected Result: 明确 503，绝不同步阻塞解析
    Failure Indicators: 仍然同步解析（请求线程被占死）或抛其他异常
    Evidence: .omo/evidence/task-13-no-bgtasks.txt
  ```
  **Commit**: YES — `fix(import): slim status endpoint, add preview endpoint, drop sync fallback` — Files: `backend/app/api/v1/question_import.py`

---

- [x] 14. 文件头嗅探 `magic.py`（A-8 / I-1）

  **What to do**:
  - 新建 `backend/app/services/question_ingest/__init__.py` 与 `magic.py`
  - `sniff(buf: bytes) -> str`：识别 `%PDF-`→`PDF`、`PK\x03\x04`→OOXML（再按内部 `[Content_Types].xml` 或 `word/`、`xl/` 细分为 `WORD`/`EXCEL`）、`D0 CF 11 E0`→旧 OLE（`WORD`/`EXCEL`）
  - `resolve_type(buf, filename) -> (file_type, conflict: bool)`：以文件头为准，冲突时 `logger.warning`
  - 在 `question_import.py:3303-3312` 接入：**`file_type` 改由 sniff 决定**，`ALLOWED_EXTENSIONS` 校验保留但冲突时按 sniff 放行
  - 冲突信息返回给前端（`response['type_conflict']`），便于教师理解

  **Must NOT do**:
  - **禁止**因 sniff 失败而拒绝上传（应回落扩展名判断并 warning）
  - **禁止**改 `ALLOWED_EXTENSIONS` 集合
  - **禁止**在本任务中新建其他 reader 模块（拆分归 Wave 9）
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需 OOXML 内部结构判别与冲突降级策略
  - **Skills**: `tdd`
  - **Skills Evaluated but Omitted**: `quick`（格式嗅探需覆盖多种真实文件）
  **Parallelization**: Can Run In Parallel: YES | Wave 2 | **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:66` — `ALLOWED_EXTENSIONS = {'.xlsx','.xls','.csv','.docx','.pdf'}`
  - `backend/app/api/v1/question_import.py:3303-3312` — 当前仅按 `os.path.splitext` 判类型（RC-6 现场）
  - `backend/app/api/v1/question_import.py:586-730` — docx 处理（`_sanitize_docx_rels` / `_open_docx_resilient` / `_extract_text_from_docx`），OOXML 判别可复用其 zip 结构认知
  - `backend/app/api/v1/question_import.py:1115-1170` — `_extract_text_from_pdf` 的 pdfplumber 入口（PDF 文件头为 `%PDF-`）
  - `backend/logs/app.log`（`No /Root object!` 那条 ERROR 的上下文）— 真实故障证据
  **Acceptance Criteria**:
  - [ ] 9 个真实语料（S1–S9）全部 sniff 正确，且与扩展名一致
  - [ ] 把 S6（真 PDF）改名 `.docx` → sniff 返回 `PDF` + conflict=True + warning 日志 + **仍能正确解析**
  - [ ] `pytest backend/tests/test_magic.py -v` 全绿（含 ≥ 6 个反向用例）
  **QA Scenarios**:
  ```
  Scenario: 真实语料 sniff 全部正确
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8
    Steps:
      1. 对 S1..S9 逐个读取前 4 字节 + 调用 sniff()
      2. 断言 4 个 .docx → WORD、5 个 .pdf → PDF
      3. 断言每个 conflict 均为 False（扩展名与文件头一致）
    Expected Result: 9/9 正确，无冲突
    Failure Indicators: 任一误判（会导致走错解析器）
    Evidence: .omo/evidence/task-14-sniff-real.txt
  Scenario: PDF 改名 .docx 仍能正确解析（RC-6 修复验证）
    Tool: Playwright
    Preconditions: 后端已 --reload；Vite 运行中
    Steps:
      1. 把 S6 复制为 %TEMP%\opencode\题本_改名.docx（**内容不变，仅改名**）
      2. Playwright 上传该文件
      3. 断言后端日志出现含 "扩展名" 与 "文件头" 不一致的 warning
      4. 断言预览正常出现且题数 > 0（按 pdfplumber 路径解析成功）
      5. 断言页面提示 type_conflict 信息
    Expected Result: warning 出现 + 解析成功（不再出现 No /Root object）
    Failure Indicators: 出现 No /Root object（仍按 docx 走）或解析失败
    Evidence: .omo/evidence/task-14-magic-rename.png + .txt
  ```
  **Commit**: YES — `feat(import): magic-byte file type sniffing` — Files: `backend/app/services/question_ingest/__init__.py`, `backend/app/services/question_ingest/magic.py`, `backend/app/api/v1/question_import.py`, `backend/tests/test_magic.py`

---

- [x] 15. RC-4 `confirmed_items` 未定义修复

  **What to do**（`backend/app/api/v1/question_import.py`）:
  - `:3612` 附近初始化 `confirmed_items: List[Dict[str, Any]] = []`
  - 循环内成功入库后 `confirmed_items.append({**item, 'question_id': <new_id>, 'score': ...})`
  - `:3809` 改为遍历 `confirmed_items`
  - 在 `/confirm` 入口加**显式自检**：`'confirmed_items' in dir()` 不可行 → 改为把该变量提到模块级常量校验或直接在模块导入时做一次 `_ = confirmed_items` 断言；更稳妥的做法是**用 `try/except NameError` 包住 :3804-3830 并 logger.error**，让失败可见而非静默 500

  **Must NOT do**:
  - **禁止**删除 `:3804-3830` 的试卷关联逻辑（那是功能，不是缺陷）
  - **禁止**把 `:3809` 改成 `for item in []` 之类的空循环（掩盖问题）
  - **禁止**改 `:3776-3784` 的状态提交顺序（题目已 commit 的事实不能掩盖）
  **Recommended Agent Profile**:
  - **Category**: `quick` — 单点缺陷，4 行改动
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `deep`（根因已完全定位）
  **Parallelization**: Can Run In Parallel: YES | Wave 2（独立最低风险，先做）| **Blocks**: 29, 45 | **Blocked By**: None
  **References**:
  - `backend/app/api/v1/question_import.py:3809` — `for item in confirmed_items:`（**全文件唯一定义缺失点**，grep 只有这 1 处）
  - `backend/app/api/v1/question_import.py:3776-3784` — `record.success_count/import_status='COMPLETED'` + `db.commit()`（题目已入库的时刻）
  - `backend/app/api/v1/question_import.py:3786-3801` — 创建试卷并写 `record.paper_id`（使 :3804 条件为真）
  - `backend/app/api/v1/question_import.py:3860-3863` — `except Exception: db.rollback(); raise HTTPException(500)`（题目回滚不掉的陷阱）
  - `.omo/evidence/task-4-rc4-repro.txt` — 任务 4 的复现证据
  **Acceptance Criteria**:
  - [ ] `grep -n confirmed_items` 现在有 **≥ 3 处**（初始化 / append / 遍历）
  - [ ] `pytest backend/tests/test_confirm_path.py -v` 全绿，含「触发建卷路径不抛 NameError」用例
  - [ ] `gate_l3_ingest.py` 的**断言 6** 从 FAIL 转 PASS
  - [ ] 端到端：走一次真实 `/confirm` 建卷导入，HTTP 200（不是 500），且题目确实入库
  **QA Scenarios**:
  ```
  Scenario: 建卷路径不再 500，且题目确实入库
    Tool: Bash (PowerShell + 内联 Python 调 ASGI)
    Preconditions: 库已备份（任务 2）；使用**真实**解析结果构造 payload
    Steps:
      1. 读取一条真实 PREVIEW 记录（total_questions >= 50）的 preview_data
      2. 构造 /confirm payload（含 questions 与 auto_detected_tags 触发建卷）
      3. 调用 confirm_batch_import
      4. 断言 HTTP 200 且 success_count > 0
      5. 断言 DB 中 question_bank 新增行数 == success_count（题目真的进去了，不是回滚掉了）
      6. 断言 exam_paper 新增 1 张，且 PaperQuestionRelation 新增行数 == success_count
    Expected Result: 200 + 题目与试卷关系全部落库
    Failure Indicators: 500（NameError 未修）；或 200 但题目数为 0（事务边界错乱）
    Evidence: .omo/evidence/task-15-confirm-200.txt
  Scenario: 门禁断言 6 从红转绿
    Tool: Bash (PowerShell)
    Preconditions: 任务 6 已完成
    Steps:
      1. python scripts/gate_l3_ingest.py -v -k confirm_path  → 修复前：FAIL
      2. 应用本任务修复
      3. 重跑 → 断言 PASS
    Expected Result: 红 → 绿
    Failure Indicators: 仍 FAIL（说明 NameError 只是表象，还有其他未定义名）
    Evidence: .omo/evidence/task-15-l3-assert6.txt
  ```
  **Commit**: YES — `fix(import): define confirmed_items in confirm ingest path` — Files: `backend/app/api/v1/question_import.py`, `backend/tests/test_confirm_path.py`

- [x] 16. 模块 B-1：前端 `pendingQuestions` 单一事实来源（RC-2 核心修复）

  **What to do**（`.vtj/vue/question_import.vue`，**只改 `<script>`**）:
  - 新增 computed `pendingQuestions`：合并 `state.batchPreviewData` 与 `state.parsedDocsQuestions`，按 `question_content` 前 80 字去重，返回**统一题目数组**（并保留 `blocked` / `block_reasons` / `requirements` / `group_id` 等字段）
  - `:193` 按钮文案 `'确认入库 ' + state.batchPreviewData.length + ' 题'` → `pendingQuestions.length`
  - `:192` `:disabled` 保持 `state.loading || hasBlockedQuestions`（`hasBlockedQuestions` 本身已改为读 `pendingQuestions`，见下）
  - `:609-614` `blockedQuestionList` 的 `this.state.batchPreviewData` → `this.pendingQuestions`
  - `:1050` 空守卫 `!this.state.batchPreviewData.length` → `!this.pendingQuestions.length`
  - `:1043` `hasBlockedQuestions` 守卫逻辑不变（底层数据源已修）
  - 确认 `.vtj/vue/question_preview_list.vue` 的 props 传入也改读 `pendingQuestions`

  **Must NOT do**:
  - **禁止**改 `<template>`（1–493 行）；**禁止**改 `useProvider` version；**禁止**同步 DSL
  - **禁止**保留任何「按钮计数读 batchPreviewData」的残留写法（L5 反向守卫会 FAIL）
  - **禁止**删除或弱化 `hasBlockedQuestions` 守卫
  **Recommended Agent Profile**:
  - **Category**: `deep` — 需理清两条状态通道的全部读写点，避免遗漏导致新不一致
  - **Skills**: 无
  - **Skills Evaluated but Omitted**: `quick`（看似只改 4 处，但需排查所有引用）
  **Parallelization**: Can Run In Parallel: NO | **Wave 3 第 1 步（严格串行）** | **Blocks**: 17, 18, 19, 29, 45 | **Blocked By**: 11, 12
  **References**:
  - `.vtj/vue/question_import.vue:609-616` — `blockedQuestionList` / `hasBlockedQuestions`（**RC-2 连带缺陷现场**）
  - `.vtj/vue/question_import.vue:192-193` — 按钮文案与 disabled（RC-2 主现场）
  - `.vtj/vue/question_import.vue:1005-1027` — `uploadBatchFile` 的 Excel 分支（`:1006` 唯一赋值点）vs Word/PDF 分支（`:1015` 清空）
  - `.vtj/vue/question_import.vue:1560` / `:1661` / `:2377` / `:1272-1305` / `:1391` — 全部 `parsedDocsQuestions` 赋值点
  - `.vtj/vue/question_import.vue:1039-1088` — `confirmBatchImport`（`:1050` 空守卫、`:1056` 发请求）
  - `.vtj/vue/question_preview_list.vue:196` — `groups` prop 定义
  - `solve_problems_files/行测导入门禁与运维手册.md:279-295` — §10 前端改动须知（**必须透传 `blocked` 与 `block_reasons`**，否则既有 UI 失效）
  **Acceptance Criteria**:
  - [ ] `python scripts/gate_l0_redlines.py` 退出码 0
  - [ ] `python scripts/gate_l5_frontend_contract.py` 退出码 0（`pendingQuestions` 已存在，四处违规全清）
  - [ ] `grep -n "batchPreviewData.length"` 在 `.vtj/vue/` 下**零命中**
  - [ ] PW-2 场景：Word 上传后按钮显示「确认入库 98 题」而非 0 题
  **QA Scenarios**:
  ```
  Scenario: 按钮显示真实题数且阻断闸门生效
    Tool: Playwright
    Preconditions: 后端 + Vite 运行；已登录教师
    Steps:
      1. 上传 S1（2020届公安院校…真题.docx，6.33 MB），等待预览
      2. 断言按钮文本匹配 /确认入库 \d+ 题/ 且数字 > 0（基线：98）
      3. 断言该按钮 **enabled**（无 blocked 题时）
      4. 点击 → 断言**未出现**「无可导入的题目数据」
      5. 断言请求已发出：Network 面板存在 POST /api/questions/import/batch-parsed 且状态 200
    Expected Result: 按钮显示真实题数，点击真正发出入库请求（RC-2 修复的直接证据）
    Failure Indicators: 仍显示 0 题；或仍提示「无可导入的题目数据」
    Evidence: .omo/evidence/task-16-rc2-fixed.png + .txt

  Scenario: 含 blocked 题时按钮被正确禁用并显示中文原因
    Tool: Playwright
    Preconditions: 同上；需一个含 blocked 的批次（可用 S8 申论省级卷）
    Steps:
      1. 上传 S8（2019年国考《申论》真题及答案（省级）（含解析）.pdf）
      2. 断言按钮文本含「存在阻断问题，无法入库」
      3. 断言按钮 **disabled**
      4. 断言页面显示 `blocked-hint` 内容为中文原因「答案段数与题目数不匹配」（映射见 :619-626）
      5. 断言 DB 中 question_bank 行数**未变**
    Expected Result: 阻断闸门在真实入库路径上生效（RC-2 连带缺陷修复的证据）
    Failure Indicators: 按钮可点（阻断闸门仍失效）或提示为英文/技术黑话
    Evidence: .omo/evidence/task-16-blocked-gate.png
  ```
  **Commit**: YES — `fix(import): single pendingQuestions source of truth for preview and blocked gate` — Files: `.vtj/vue/question_import.vue`, `.vtj/vue/question_preview_list.vue`

---

- [x] 17. 模块 B-2/B-3：`/batch-parsed` 接入 `requirements` 与 `group_id`（RC-5 修复）

  **What to do**:
  - `.vtj/vue/question_import.vue:2733-2744` payload 补齐：`requirements`（string 与 array 两种形态都兼容）、`group_id`、`question_number`、`sort_order`、`need_review`
  - `backend/app/api/v1/question_import.py:2601-2960`（`/batch-parsed`）：把上述字段透传到 `_upsert_question_core`（后者 `:2190` 已支持 `group_id`、`:2214` 已支持 `requirements`，**只差接线**）
  - 新增题组 upsert：把散在 `:1996` / `:2371` / `:2427` 的三处 `QuestionGroup(...)` 收敛为**一个** `_upsert_question_group()` 函数（拆分时迁入 `question_ingest/groups.py`，本任务先在原地收敛）
  - 返回体新增逐题映射：`question_index_map: [{index, question_id, status}]`

  **Must NOT do**:
  - **禁止**改动 `_upsert_question_core` 的 `:2190` / `:2214` 赋值语句（只加调用侧传参）
  - **禁止**改动 `:4005-4011` dispatch 块与 `separate_match_endpoint` 函数体
  - **禁止**在 `/batch-parsed` 中**自动创建**题组而不同步传 `shared_content`（材料为空会产生空题组）
  **Recommended Agent Profile**:
  - **Category**: `deep` — 跨前后端字段对齐 + 三处题组逻辑收敛
  - **Skills**: `tdd`
  - **Skills Evaluated but Omitted**: `quick`（涉及事务边界与题组一致性）
  **Parallelization**: Can Run In Parallel: NO | **Wave 3 第 2 步** | **Blocks**: 18, 19, 29, 45 | **Blocked By**: 16
  **References**:
  - `backend/app/api/v1/question_import.py:2733-2744` — **前端 payload 缺字段的现场**（RC-5 根因之一）
  - `backend/app/api/v1/question_import.py:2190` / `:2214` — `_upsert_question_core` 已支持 `group_id` / `requirements` 的赋值点
  - `backend/app/api/v1/question_import.py:1996` / `:2371` / `:2427` — 三处 `QuestionGroup(...)`（本任务收敛为 1 处）
  - `backend/app/models/models.py:214-234` — `group_id` / `parent_id` / `question_level` / `sort_order` / `question_number` / `requirements` 列定义
  - `backend/app/models/models.py:255-277` — `QuestionGroup` 列定义（`shared_content` / `title` / `subject` / `source`）
  - `.omo/plans/question-import-full-repair.md:2` (RC-5) — 「后端已支持，只是这条路没接」的完整对照表
  **Acceptance Criteria**:
  - [ ] `gate_l0_redlines.py` 退出码 0；`gate_l3_ingest.py` 的**断言 2、3** 从 FAIL 转 PASS
  - [ ] 传入 `requirements` 的题，落库后 `question_bank.requirements` 非空
  - [ ] 传入 `group_id` 的题，落库后 `question_groups` 对应行存在且 `shared_content` 非空
  - [ ] 返回体含 `question_index_map`，其长度 == `success_count + failed_items` 数
  **QA Scenarios**:
  ```
  Scenario: requirements 真正落库（RC-5 修复的核心验证）
    Tool: Bash (PowerShell + 内联 Python 调 ASGI + 只读 sqlite 校验)
    Preconditions: 库已备份
    Steps:
      1. 构造 3 题 payload，q2 带 requirements="①全面准确；②不超过300字"
      2. 调用 /batch-parsed
      3. **只读**查询 SELECT question_id, requirements FROM question_bank WHERE question_id IN (返回的 new_question_ids)
      4. 断言 q2 的 requirements 精确等于 "①全面准确；②不超过300字"
      5. 断言 q1/q3 的 requirements 为 NULL 或空（未被伪造填充）
    Expected Result: requirements 精确落库，缺省留空不伪造
    Failure Indicators: q2 的 requirements 为空（RC-5 未修复）；或 q1/q3 被填了默认值（违反「绝不伪造」）
    Evidence: .omo/evidence/task-17-requirements.txt
  Scenario: 题组与小题的关联正确建立
    Tool: Bash (PowerShell)
    Preconditions: 同上
    Steps:
      1. 构造 1 个题组 + 3 小题（group_id 相同，sort_order 1/2/3）
      2. 调用 /batch-parsed
      3. 断言 question_groups 存在 1 行且 shared_content 非空
      4. 断言 question_bank 中 3 行的 group_id 全部等于该 group.id
      5. 断言 sort_order 依次为 1,2,3
    Expected Result: 题组与小题关联完整，顺序正确
    Failure Indicators: 题组行缺失；或 group_id 未回填（前端传了但后端丢弃）
    Evidence: .omo/evidence/task-17-groups.txt
  ```
  **Commit**: YES — `feat(import): persist requirements and question group on batch-parsed` — Files: `backend/app/api/v1/question_import.py`, `.vtj/vue/question_import.vue`

---

- [x] 18. 模块 B-4：`/batch-parsed` 补 `blocked` 闸门

  **What to do**:
  - `/batch-parsed` 入口（`:2635` 之后、循环之前）扫描 `items`，若任一 `q.get('blocked')` 为真 → **整批拒绝**：
    - `raise HTTPException(status_code=409, detail=...)`，detail 含**中文** `block_reasons` 映射
    - 中文映射直接复用前端 `:619-626` 的 `LABEL` 表（后端建同表，保持单一事实来源，两端各一份字面量但**必须一致**，并由 L3 单测校验）
  - 前端 `.vtj/vue/question_import.vue` 处理 409：展示 `blocked-hint` + 原因，**不**清空 `pendingQuestions`
  - 前端 payload 必须**透传** `blocked` 与 `block_reasons`（当前 `:2733-2744` 未传）

  **Must NOT do**:
  - **禁止**「跳过 blocked 题继续导入其余」（用户硬约束：宁可阻断交人工）
  - **禁止**放宽 `blocked` 判定（`text_parser.py` 侧不动）
  **Recommended Agent Profile**:
  - **Category**: `deep` — 闸门必须拦在事务之前，且要保证零写入
  - **Skills**: `tdd`
  - **Skills Evaluated but Omitted**: `quick`（事务边界需严谨）
  **Parallelization**: Can Run In Parallel: NO | **Wave 3 第 3 步** | **Blocks**: 19, 29, 45 | **Blocked By**: 17
  **References**:
  - `backend/app/api/v1/question_import.py:2032-2037` — `_upsert_question_core` 内**已有的** blocked 闸门（`HTTPException(400)`），本任务在 batch 层再加一道
  - `backend/app/api/v1/question_import.py:3626-3638` — `/confirm` 的 blocked 处理（逐题跳过 + 计入 failed），本任务改为**整批拒绝**
  - `.vtj/vue/question_import.vue:619-626` — `blockedReasonText` 的 `LABEL` 映射表（后端须同表）
  - `.vtj/vue/question_import.vue:1043-1049` — 前端程序性守卫
  - `solve_problems_files/行测题目导入优化方案.md:62-73` — 铁律 R-6 原文
  **Acceptance Criteria**:
  - [ ] `gate_l3_ingest.py` 的**断言 4** 从 FAIL 转 PASS
  - [ ] 含 blocked 的批次 → HTTP 409 + 中文原因 + **DB 零新增**（逐字段断言）
  - [ ] 无 blocked 的批次 → HTTP 200 正常入库（不误伤）
  **QA Scenarios**:
  ```
  Scenario: blocked 批次被整批拒绝且零写入
    Tool: Bash (PowerShell + 内联 Python）
    Preconditions: 库已备份；记录调用前 question_bank 总行数 N0
    Steps:
      1. 构造 3 题 payload，其中 q2 带 blocked=true, block_reasons=["answer_block_count_mismatch"]
      2. 记录 N0 = SELECT COUNT(*) FROM question_bank
      3. 调用 /batch-parsed  → 断言抛 HTTPException 且 status_code == 409
      4. 断言 detail 含中文「答案段数与题目数不匹配」
      5. **只读**查询 N1 = SELECT COUNT(*) FROM question_bank  → 断言 N1 == N0（零写入）
      6. 断言 N0/N1 差值为 0 时，本任务的 rejected 计数器为 1（新增计数生效）
    Expected Result: 409 + 中文原因 + 零写入（整批拒绝，绝不部分导入）
    Failure Indicators: 200；或 409 但 DB 新增了 q1/q3（部分导入，违反硬约束）
    Evidence: .omo/evidence/task-18-blocked-gate.txt
  Scenario: 正常批次不被误伤
    Tool: Bash (PowerShell)
    Preconditions: 同上
    Steps:
      1. 构造 3 题 payload，全部 blocked 为 false/absent
      2. 调用 /batch-parsed  → 断言 200 且 success_count == 3
      3. 断言 question_index_map 长度 == 3
    Expected Result: 正常批次照常入库，闸门不误伤
    Failure Indicators: 被误拒（闸门条件写错，如把 blocked=0 当成真）
    Evidence: .omo/evidence/task-18-no-false-positive.txt
  ```
  **Commit**: YES — `fix(import): reject whole batch on blocked questions` — Files: `backend/app/api/v1/question_import.py`, `.vtj/vue/question_import.vue`, `backend/tests/test_gate_l3.py`

---

- [x] 19. 模块 B-5/B-6：`/confirm` 改造（payload.questions 优先）

  **What to do**:
  - `backend/app/api/v1/question_import.py:3610` — `items = preview_data.get('items', []) or []` 改为：
    **优先** `payload.get('questions')`；仅当其缺失/为空时回落旧逻辑，并 `logger.warning('deprecated: /confirm 未传 questions，已回落到 preview_data 快照')`
  - `:3603-3610` 的 `load_json_lenient(record.preview_data)` 移入**回落分支**（不再无条件反序列化）
  - `:3722-3723` 的 `requirements` / `group_id` 写入保持不变（本就已支持）
  - 补：前端 `:1059-1063` 已有 `questions` 字段，确认传的是 `pendingQuestions`（依赖任务 16）
  - 同步修 `:3786-3830` 的试卷关联，使其兼容「payload 传入的题」而非快照题

  **Must NOT do**:
  - **禁止**删除 `preview_data` 字段（它是历史复盘证据）
  - **禁止**移除回落分支（旧前端仍可能不传 questions）
  - **禁止**改 `:4005-4011` dispatch 块
  **Recommended Agent Profile**:
  - **Category**: `deep` — 契约变更 + 向后兼容 + 事务边界
  - **Skills**: `tdd`
  - **Skills Evaluated but Omitted**: `quick`（兼容分支与事务需严谨）
  **Parallelization**: Can Run In Parallel: NO | **Wave 3 第 4 步（收尾）** | **Blocks**: 29, 45 | **Blocked By**: 15, 17, 18
  **References**:
  - `backend/app/api/v1/question_import.py:3603-3610` — **RC-3 现场**：忽略 payload.questions 读 `preview_data.items`
  - `backend/app/api/v1/question_import.py:3607` — `load_json_lenient` 注释说明历史双重编码（P0-6）
  - `backend/app/api/v1/question_import.py:3722-3723` — `/confirm` 已支持 `requirements` / `group_id`（对照 `/batch-parsed` 的缺失）
  - `.vtj/vue/question_import.vue:1059-1063` — 前端已发送 `questions`
  **Acceptance Criteria**:
  - [ ] `gate_l3_ingest.py` 的**断言 5** 从 FAIL 转 PASS
  - [ ] 「上传 → 预览改 1 题答案 → 入库」后，库中该题答案 == 改后值（RC-3 修复的直接证据）
  - [ ] 不传 `questions` 时仍能工作（回落分支），且日志出现 deprecation warning
  - [ ] `gate_l0_redlines.py` + `gate_all.py --quick` 全绿
  **QA Scenarios**:
  ```
  Scenario: 前端预览的修改能真正落库（RC-3 修复验证）
    Tool: Playwright + Bash（只读 SQL 校验）
    Preconditions: 后端 + Vite 运行；已登录教师；库已备份
    Steps:
      1. 上传 S5（2017年公安院校联考《公安专业科目》题.docx，合并导入含解析），等待预览
      2. 在预览中把第 1 题的 answer 从原值改为 "ZZTEST_QA_EDIT"
      3. 点击「确认入库」
      4. 断言成功提示出现且 success_count == 预览题数
      5. **只读**查询 SELECT answer FROM question_bank WHERE question_content LIKE 'ZZTEST_QA_EDIT%' 的关联行 → 断言答案为 "ZZTEST_QA_EDIT"
      6. 断言库中**不存在**该题仍为旧答案的重复行
    Expected Result: 库中答案 == 前端改后的值，且无重复行（RC-3 与重传重复一并修复）
    Failure Indicators: 库中仍是旧答案（/confirm 仍在读快照）
    Evidence: .omo/evidence/task-19-edit-persisted.png + .txt
    Note: 测试后必须删除该 QA 行，标记 qa_tag，勿污染基线
  Scenario: 旧前端回落分支仍可用（向后兼容）
    Tool: Bash（内联 Python 调 ASGI）
    Preconditions: 同上
    Steps:
      1. 构造 /confirm payload，**不含** questions 字段
      2. 调用 → 断言 HTTP 200 且 success_count > 0
      3. 断言日志出现 "deprecated: /confirm 未传 questions"
    Expected Result: 回落生效且有 deprecation 提示
    Failure Indicators: 报错（旧前端会被打断 → 兼容性回归）
    Evidence: .omo/evidence/task-19-fallback.txt
  ```
  **Commit**: YES — `fix(import): confirm honors payload questions over stale preview snapshot` — Files: `backend/app/api/v1/question_import.py`

- [x] 20. 模块 C-1/C-6：公专回归用例 + 省份只从文件夹名取

  **What to do**:
  - 新增 `backend/tests/test_gongzhuan_regression.py`：锁定公专两条已知缺陷的回归用例
    ① `_extract_options` 字母错位（`A.\nB.\nC.\nD.` → 当前公专链路必须产出 4 个选项，**不得**产出 `[{'A':'B.'},{'C':'D.'}]`）
    ② 公专 0 题的 `requirements` 不得被自动填充（守住「缺省留空不伪造」）
  - `_auto_detect_tags`（`:1443-1504`）复核：省份/年份**只能**从文件夹名取；文件名推断路径必须删除或降级为 warning
  - 加一条用例：文件名不含「省」但文件夹名含「省」时，省份必须正确取到

  **Must NOT do**:
  - **禁止**改 `extract_question_blocks` 函数体（字节级红线）
  - **禁止**改公专的 `_extract_options` 实现（修复只允许走行测专用路径）
  **Recommended Agent Profile**: `unspecified-high`（公专零回归是最高约束）| Skills: `tdd`
  **Parallelization**: YES | Wave 4（与 21/22/23/24 并行）| **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `.omo/notepads/xingce-import-optimization/followup-findings.md:14-25` — 字母错位根因与公专同类缺陷 **0/2583 未污染** 的实证
  - `solve_problems_files/行测题目导入优化方案.md:69-73` — 铁律 R-5：**省份只能来自文件夹名**
  - `backend/app/api/v1/question_import.py:1443-1504` — `_auto_detect_tags`（省份/年份/考试类型提取）
  - `backend/app/api/v1/question_import.py:470-534` — `_parse_excel_buffer` / `_normalize_question`
  **Acceptance Criteria**: `gate_l1_parser.py --subject gongzhuan` 退出码 0 且 5 项逐项一致；新增 3 条公专回归用例全绿
  **QA Scenarios**:
  ```
  Scenario: 公专五项基线零漂移
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/gate_l1_parser.py --subject gongzhuan  2) 断言退出码 0
           3) 断言 块数==2899 / 污染==0 / 题型分布 / 选项数分布 四项全等
    Expected Result: 逐项一致
    Failure Indicators: 任一不同 = 公专回归，立即停止
    Evidence: .omo/evidence/task-20-gongzhuan.txt
  Scenario: 省份只从文件夹名取
    Tool: pytest
    Steps: 1) pytest backend/tests/test_gongzhuan_regression.py -k province -v  2) 断言 PASS
    Expected Result: 文件名无「省」时，省份仍从文件夹名正确取到
    Failure Indicators: 省份为空或错（回归 R-5）
    Evidence: .omo/evidence/task-20-province.txt
  ```
  **Commit**: YES — `test(parser): gongzhuan regression cases and folder-only province detection` — Files: `backend/tests/test_gongzhuan_regression.py`, `backend/app/api/v1/question_import.py`

---

- [x] 21. 模块 C-5：分离导入与合并导入统一三方交叉校验

  **What to do**:
  - 把 `_essay_cross_validate`（题号 + 分值 + 题干指纹）的校验逻辑，从「仅申论分离导入」提升为**分离与合并两条路径共用**
  - `/separate-match`（`:4020`）与 `/separate-match-xingce`（`:4329`）以及合并导入路径，在入库前统一走同一校验函数
  - 校验不通过 → 一律 `blocked`，**禁止按序硬配**
  - 公专/行测链路**不受影响**（`_essay_cross_validate` 是申论专用，其他科目走各自判据）

  **Must NOT do**:
  - **禁止**改 `:4005-4011` dispatch 块（字节级红线）
  - **禁止**改 `separate_match_endpoint` 函数体（11376 字符红线）
  - **禁止**放宽任何阻断条件
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 4 | **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:3866-3889` — `_separate_match_essay`（申论三方校验的现有实现）
  - `.omo/handoff-shenlun-v4.md:272-275` — 用户硬约束 2：「题目数=正确答案段数仅是必要条件，必须逐题校验题号/分值/题干指纹/答案/解析，**禁止计数相等但错配**」
  - `solve_problems_files/行测题目导入优化方案.md:49-59` — 安全网按结构而非身份校验的局限（安徽 2023 vs 2024 结构完全相同 → `blocked_count=0`），需题干指纹兜底
  **Acceptance Criteria**: 分离与合并路径共用同一校验；`gate_l2_matching.py` 退出码 0；构造「计数相等但错配」的样本必须被阻断
  **QA Scenarios**:
  ```
  Scenario: 计数相等但内容错配必须被阻断（核心防线）
    Tool: pytest
    Preconditions: 无
    Steps: 1) 构造 3 题题目文档 + 3 段答案文档，但答案顺序被打乱（第1题答案对应第3题）
           2) 调用统一校验函数  3) 断言返回 blocked=True 且 block_reasons 含 stem_fingerprint_mismatch
    Expected Result: 阻断（宁可报错交人工）
    Failure Indicators: 放行（会造成错配入库，数据污染不可逆）
    Evidence: .omo/evidence/task-21-mismatch-blocked.txt
  Scenario: 行测与公专链路零影响
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/gate_l1_parser.py --subject gongzhuan  2) 断言退出码 0 且 5 项一致
           3) python scripts/gate_l2_matching.py  4) 断言退出码 0
    Expected Result: 两科基线均未变
    Failure Indicators: 任一漂移（说明共用校验误伤了其他科目）
    Evidence: .omo/evidence/task-21-no-bleed.txt
  ```
  **Commit**: YES — `feat(import): unify three-way cross validation for separate and merged import` — Files: `backend/app/api/v1/question_import.py`

---

- [x] 22. 模块 E-1：后端 `group/{id}` 的 `members[]` 补 `requirements`

  **What to do**（`backend/app/api/v1/questions.py:609-621`）:
  - `items.append({...})` 补三个字段：`requirements: q.requirements`、`need_review: q.need_review`、`parent_id: q.parent_id`
  - `question_groups.shared_content` 的图片占位符渲染改为带 `owner='group'`（与任务 30 联动；本任务可先只加字段）

  **Must NOT do**:
  - **禁止**改 `/group/{group_id}` 的路由路径或鉴权
  - **禁止**改 `members` 已有字段的命名
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: YES | Wave 4 | **Blocks**: 23, 26 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/questions.py:571-636` — `get_question_group` 本体（`:609-621` 是 `items.append`）
  - `backend/app/models/models.py:230-234` — `need_review` 与 `requirements` 列定义
  - `.vtj/vue/question_preview_list.vue:87-90` — 前端已在渲染 `q.requirements`（string 与 array 两形态都支持）
  **Acceptance Criteria**: `GET /api/questions/group/{id}` 的 `members[]` 每项含 `requirements`/`need_review`/`parent_id`；有 `requirements` 的题能正确返回（string 原样、array 原样）
  **QA Scenarios**:
  ```
  Scenario: members 返回 requirements（真实复合题）
    Tool: Bash (PowerShell)
    Preconditions: 库中存在带 group_id 的 20 道题之一（基线）
    Steps: 1) 取一个 group_id  2) GET /api/questions/group/{id}
           3) 断言 members 长度 > 0  4) 断言 members[0] 含 requirements / need_review / parent_id 三键
    Expected Result: 三键均存在
    Failure Indicators: 缺键（前端无法渲染要求区块）
    Evidence: .omo/evidence/task-22-group-members.txt
  Scenario: 字段类型不被隐式转换
    Tool: pytest
    Steps: 1) pytest -k group_member_fields  2) 断言 string 保持 string、list 保持 list
    Expected Result: 两种形态均原样返回
    Failure Indicators: 被强制转成同一形态（前端会漏渲染）
    Evidence: .omo/evidence/task-22-field-types.txt
  ```
  **Commit**: YES — `feat(api): group members expose requirements and review flag` — Files: `backend/app/api/v1/questions.py`

---

- [x] 23. 模块 E-2：`question_preview_list.vue` 升级为三端共用题组渲染组件

  **What to do**（`.vtj/vue/question_preview_list.vue`，**只改 `<script>`**）:
  - 对外只吃**统一契约**：`{ group: {id,title,shared_content,group_type,subject,source}, members: [...] }`（即 `/api/questions/group/{id}` 同构）
  - 内部渲染顺序固定为：**材料（可折叠，默认展开）→ 题目要求 → 小题列表（每题带答案 + 解析）**
  - 保留现有 `groups[]` 导入预览模式的**向后兼容 props**（`material_length` / `material_titles` / `material_preview`），两条数据入口归一为内部同一渲染函数
  - 导出只读模式开关 `readonly`（学生端用，隐藏编辑控件）

  **Must NOT do**:
  - **禁止**改 `<template>` 的既有结构（在 script 内通过 props/computed 适配）
  - **禁止**破坏行测分区折叠 + 考点标签（f78a0b6 已落地并验证过）
  - **禁止**改 `useProvider` version
  **Recommended Agent Profile**: `visual-engineering` | Skills: 无
  **Parallelization**: YES | Wave 4 | **Blocks**: 24, 26, 27 | **Blocked By**: 22
  **References**:
  - `.vtj/vue/question_preview_list.vue:40-51` — 材料块渲染（`material_length` / `material_titles` / `material_preview` / 折叠按钮）
  - `.vtj/vue/question_preview_list.vue:87-90` — `requirements` 区块（string 与 array 两形态）
  - `.vtj/vue/question_preview_list.vue:196` — `groups` prop
  - `.vtj/vue/question_preview_list.vue:323` — 「后端 groups 已按材料聚合，这里只负责展示，不做数据判断」的设计约定
  - `.vtj/vue/question_preview_list.vue:383-393` — `material_length` / `material_titles` / `material_preview` 的 computed 组装
  - `backend/app/api/v1/questions.py:625-636` — 统一契约的返回结构
  **Acceptance Criteria**: 组件能渲染「材料 + 要求 + 小题列表（各带答案解析）」；行测分区折叠与考点标签**无回归**（`gate_l5` 与 PW-6 通过）
  **QA Scenarios**:
  ```
  Scenario: 三端共用契约渲染正确
    Tool: Playwright
    Preconditions: 任务 22 完成；有带 group 的复合题
    Steps: 1) 打开导入预览页并上传 S9（申论地市级）
           2) 断言材料块可见且可折叠（点「收起材料」后材料隐藏，再点恢复）
           3) 断言「题目要求」区块可见
           4) 断言小题列表出现，每题下方均有「答案」与「解析」两区
    Expected Result: 材料→要求→小题(答案+解析) 的固定顺序渲染
    Failure Indicators: 任一区块缺失；或顺序不一致
    Evidence: .omo/evidence/task-23-shared-renderer.png
  Scenario: 行测预览零回归
    Tool: Playwright
    Preconditions: 同上
    Steps: 1) 上传 S6 + S7 做行测分离导入  2) 断言 5 个分区折叠头全部出现
           3) 断言考点标签正常显示  4) 断言 blocked == 0
    Expected Result: 行测既有表现完全不变（f78a0b6 无回归）
    Failure Indicators: 分区折叠消失或考点标签缺失（组件重构破坏了行测路径）
    Evidence: .omo/evidence/task-23-xingce-noregress.png
  ```
  **Commit**: YES — `feat(ui): shared group renderer for material, requirements and members` — Files: `.vtj/vue/question_preview_list.vue`

---

- [x] 24. 模块 E-3/E-4：教师端与管理员端接入共用组件（script-only 补 requirements；共用组件接入因 template 红线受阻）

  **What to do**（**只改 `<script>`**）:
  - `.vtj/vue/teacher_questions.vue:546-548` — `groupInfo` 改为调用共用组件所需的数据装配（材料 + members 一次取全，不再只取 `shared_content`）
  - 删除 `:108-110` 的自维护 `groupInfo.shared_content` **单块**渲染逻辑（该块在 template 中，若必须改 template 则**停下请用户在设计器操作**）
  - `.vtj/vue/admin_questions.vue:455-456` 同样处理；删除 `:137-139` 的重复拷贝
  - 两页均渲染「材料 → 要求 → 小题列表（答案+解析）」

  **Must NOT do**:
  - **禁止**手工改 `<template>`；若需要新的容器元素，**必须停下**并请用户在 `http://localhost:9527/__vtj__/` 设计器拖拽
  - **禁止**改 `useProvider` version；**禁止**同步 DSL
  - **禁止**破坏既有的审核详情弹窗（`admin_questions.vue` 1100px/80vh 约定）
  **Recommended Agent Profile**: `visual-engineering` | Skills: 无
  **Parallelization**: YES | Wave 4（与 20/21/22 并行）| **Blocks**: 26, 45 | **Blocked By**: 23
  **References**:
  - `.vtj/vue/teacher_questions.vue:67` — `group-badge`（复合题小题标记）
  - `.vtj/vue/teacher_questions.vue:108-110` — **自维护 groupInfo 单块**（E-3 要替换的现场）
  - `.vtj/vue/teacher_questions.vue:546-548` — `auth.apiFetch('/api/questions/group/' + q.group_id)`
  - `.vtj/vue/admin_questions.vue:137-139` — **重复拷贝**（E-4 要消除的重复）
  - `.vtj/vue/admin_questions.vue:455-456` — 同上
  - `CLAUDE.md/vtj.md:313-326` — §3.1 职责分离：**Claude Code 不应修改 template 中复杂结构，应提示用户回设计器**
  - `solve_problems_files/README.md` — 「弹窗宽度/高度需调整为 1100px / 80vh」的既有约定
  **Acceptance Criteria**: 两页与导入预览**形态一致**；`gate_l0` 红线全绿；`gate_l5` 无新增违规
  **QA Scenarios**:
  ```
  Scenario: 教师端题管与导入预览形态一致
    Tool: Playwright
    Preconditions: 后端 + Vite 运行；有带 group 的复合题
    Steps: 1) 教师端 → 题目管理 → 找该复合题小题 → 打开详情
           2) 断言材料块、题目要求、小题列表（含答案+解析）全部可见
           3) 截图 4) 与导入预览截图并排对比
    Expected Result: 两者渲染结构一致（同一组件）
    Failure Indicators: 任一区块缺失；或仍是只有材料的单块
    Evidence: .omo/evidence/task-24-teacher.png
  Scenario: 管理员端审核弹窗未回归
    Tool: Playwright
    Steps: 1) 管理员端 → 题目审核 → 打开详情弹窗
           2) 断言弹窗宽度 == 1100px 且高度 == 80vh
           3) 断言弹窗内含答案与解析
    Expected Result: 1100px / 80vh 约定保持
    Failure Indicators: 尺寸变化或答案解析缺失
    Evidence: .omo/evidence/task-24-admin.png
  ```
  **Commit**: YES — `refactor(ui): teacher and admin question pages use shared group renderer` — Files: `.vtj/vue/teacher_questions.vue`, `.vtj/vue/admin_questions.vue`

---

- [x] 25. 模块 D-1..D-5：MinerU 分层主库 + 实际引擎名可见

  **What to do**:
  - `question_import.py:1133-1140` — 把 MinerU 在**扫描件分支**显式化为第一顺位，PaddleOCR 降为第二顺位，每级 `logger.info` 记录实际采用的引擎
  - `:973-1105` — 解析结果保留 `engine` 字段（`_finish(text,'pdfplumber')` 机制已有），并把 `engine` 一路透传到预览响应
  - `.docx` **不走** MinerU（决策 2），在代码注释中写明理由
  - `mineru_service.py:132` — `MINERU_TIMEOUT` 默认 300 与前端注释 600 的漂移：统一到 `app/config.py` 单一事实来源；前端改从 `/api/questions/import/stats` 读，不再硬编码 `PDF_OCR_TIMEOUT_MS=960000`
  - `mineru_service.py:137` — 全局单槽 `_sem` 改为**按文件类型分池**，避免长文档堵死其他导入
  - MinerU 失败必须回退并留痕，**绝不静默产出空文本**

  **Must NOT do**:
  - **禁止**让文本层 PDF 走 MinerU（会丢 pdfplumber 表格提取能力，资料分析材料表会被打平）
  - **禁止**让 `.docx` 走 MinerU
  - **禁止**在 MinerU 失败时静默返回空文本
  - **禁止**改行测的 pdfplumber 路径（742 题 100% 匹配的成绩依赖它）
  **Recommended Agent Profile**: `deep` | Skills: 无
  **Parallelization**: YES | Wave 5（与 26/27/28 并行）| **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/services/mineru_service.py:120-190` — `extract_text_sync`（mkdtemp → 落盘 → `subprocess.run` → 收集 `*.md`；`:132` timeout 默认 300；`:137` 全局 `_sem`；`:174-175` 超时回退）
  - `backend/app/services/mineru_service.py:55-68` — `is_enabled()` / `health_check()`（实测 health 返回 3.4.5）
  - `backend/app/api/v1/question_import.py:940-1113` — `_extract_text_from_pdf` 主干（`:975` pdfplumber；`:1133-1138` MinerU 唯一调用点）
  - `backend/app/api/v1/question_import.py:1150` — `_extract_text_from_scanned_pdf`（PaddleOCR 二顺位）
  - `.vtj/vue/question_import.vue:919-926` — 前端注释里的超时口径（`MINERU_TIMEOUT=600`，与后端 300 漂移）
  - `.vtj/vue/question_import.vue:512` — `PDF_OCR_TIMEOUT_MS = 960000` 硬编码
  - `.omo/plans/question-import-full-repair.md:2` (RC-7) + §3.4 — 分层主库的完整设计与风险说明
  **Acceptance Criteria**: 扫描件 PDF 首选 MinerU 且日志标注引擎；文本层 PDF 仍走 pdfplumber；`.docx` 不触发 MinerU；`engine` 字段出现在预览响应与页面；行测 G2 零回归
  **QA Scenarios**:
  ```
  Scenario: 引擎选择符合分层策略（真实语料）
    Tool: Bash (PowerShell)
    Preconditions: MinerU health available（实测 3.4.5）
    Steps: 1) 取一份**扫描件** PDF → 调解析  2) 断言日志含 "[mineru] 解析成功" 且 engine == 'mineru'
           3) 取 S6（有文本层的行测题本）→ 调解析  4) 断言 engine == 'pdfplumber' 且日志**不含** mineru 调用
           5) 取 S1（docx）→ 调解析  6) 断言日志**不含** mineru 调用
    Expected Result: 三种文件各自命中正确引擎（分层主库生效）
    Failure Indicators: 文本层 PDF 走了 MinerU（表格能力丢失风险）；或 docx 走了 MinerU
    Evidence: .omo/evidence/task-25-engine-selection.txt
  Scenario: 行测 G2 零回归 + 预览显示引擎名
    Tool: Bash (PowerShell) + Playwright
    Steps: 1) python scripts/gate_l2_matching.py  2) 断言退出码 0
           3) Playwright 打开导入预览  4) 断言页面显示本次使用的引擎名（如「pdfplumber」）
    Expected Result: G2 零回归；引擎名对用户可见
    Failure Indicators: G2 漂移（pdfplumber 路径被破坏）
    Evidence: .omo/evidence/task-25-l2-noregress.txt + .png
  ```
  **Commit**: YES — `feat(mineru): layered primary engine with visible engine name` — Files: `backend/app/services/mineru_service.py`, `backend/app/api/v1/question_import.py`, `backend/app/config.py`, `.vtj/vue/question_import.vue`

---

- [x] 26. 模块 F-1/F-2：学生端 `answer_page.vue` 接入共用组件（script-only 补 requirements）

  **What to do**（**只改 `<script>`**）:
  - `:86-95` 材料区补 `requirements` 展示（当前缺失）
  - 接入任务 23 的共用组件（`readonly` 模式），保证与教师端预览形态一致
  - **保留** 竖向滚动（`:78 question-scroll`）+ 材料折叠（`:88-90`）+ `scrollIntoView`（`:533`）——决策 6 已定，**不做交互重做**
  - 答案保存必须按小题独立（不得互相覆盖），增加回归断言

  **Must NOT do**:
  - **禁止**改成「一屏一题」翻页（决策 6）
  - **禁止**破坏 `:329` / `:436-439` 的题组首次出现判定（材料不重复显示）
  - **禁止**改 `<template>` 结构
  **Recommended Agent Profile**: `visual-engineering` | Skills: `playwright`
  **Parallelization**: YES | Wave 5 | **Blocks**: 27, 45 | **Blocked By**: 23, 24
  **References**:
  - `.vtj/vue/answer_page.vue:78` — `question-scroll` 滚动容器（**已实现，勿重做**）
  - `.vtj/vue/answer_page.vue:86-95` — 材料折叠 + `shared_content` 渲染（要补 requirements）
  - `.vtj/vue/answer_page.vue:221-223` — `state.groupMaterials` / `state.groupCollapsed`
  - `.vtj/vue/answer_page.vue:329` / `:436-439` — `isGroupFirstOccurrence`（材料只在首题显示）
  - `.vtj/vue/answer_page.vue:533` — `scrollIntoView`
  - `src/utils/questionRender.js` — 安全 HTML 渲染，**不转换换行**（渲染要求分点时必须注意）
  **Acceptance Criteria**: 学生端材料区含要求；与教师端形态一致；小题答案独立保存；`gate_l0` 红线全绿
  **QA Scenarios**:
  ```
  Scenario: 复合题竖向滑动 + 答案独立保存
    Tool: Playwright
    Preconditions: 后端 + Vite 运行；有含 group 的复合题（含小题 >= 2）
    Steps: 1) 学生端进入该复合题练习  2) 断言材料块在第一小题上方可见
           3) 断言「题目要求」可见  4) 向下滚动到第 2 小题，断言材料**不重复**显示
           5) 给小题 1 填答案 "QA_AAA"，给小题 2 填 "QA_BBB"
           6) 提交  7) 重新进入该复合题  8) 断言小题1 == "QA_AAA" 且小题2 == "QA_BBB"
    Expected Result: 竖向贯穿全部小题；答案各自独立保存不互相覆盖
    Failure Indicators: 材料重复显示；或两小题答案互相覆盖（答案归属错乱）
    Evidence: .omo/evidence/task-26-answer-page.png + .txt
  Scenario: 与教师端预览形态一致
    Tool: Playwright
    Steps: 1) 教师端预览该复合题 → 截图 A  2) 学生端作答该复合题 → 截图 B
           3) 并排对比，断言材料/要求/小题的区块顺序与视觉层级一致
    Expected Result: 两端形态一致（同一组件）
    Failure Indicators: 结构或顺序不同
    Evidence: .omo/evidence/task-26-parity.png
  ```
  **Commit**: YES — `feat(ui): answer page uses shared renderer with requirements` — Files: `.vtj/vue/answer_page.vue`

---

- [x] 27. 模块 F-3：手机端与平板端接入共用组件（script-only 补 requirements，实际页为 mobile_answer.vue）

  **What to do**: `.vtj/vue/mobile_practice.vue`、`.vtj/vue/tablet_practice.vue` 同步任务 26 的改动（材料区 + `requirements` + 共用组件 `readonly` 模式）

  **Must NOT do**: **禁止**破坏移动端一屏适配与底部 Tab 布局；**禁止**改 `<template>`
  **Recommended Agent Profile**: `visual-engineering` | Skills: `playwright`
  **Parallelization**: YES | Wave 5 | **Blocks**: 45 | **Blocked By**: 26
  **References**:
  - `.vtj/vue/mobile_practice.vue`（842 行）、`.vtj/vue/tablet_practice.vue`（865 行）
  - `solve_problems_files/手机端深度优化完善方案.md` — 一屏适配与图标缩减的既有规范（勿破坏）
  - `.vtj/vue/answer_page.vue:86-95` — 桌面端的参照实现
  **Acceptance Criteria**: 两端复合题渲染与桌面端一致；移动端一屏适配不回归
  **QA Scenarios**:
  ```
  Scenario: 移动端复合题渲染与桌面端一致
    Tool: Playwright（viewport 390x844）
    Steps: 1) 移动端进入复合题  2) 断言材料 + 要求 + 小题(答案+解析) 区块齐全
           3) 断言竖向滑动可贯穿全部小题  4) 断言底部 Tab 栏仍固定可见
    Expected Result: 渲染一致且移动端布局无回归
    Failure Indicators: 区块缺失；或 Tab 栏被遮挡/滚动穿透
    Evidence: .omo/evidence/task-27-mobile.png
  Scenario: 平板端同验证
    Tool: Playwright（viewport 1024x768）
    Steps: 1) 同上步骤，断言渲染一致
    Expected Result: 一致
    Failure Indicators: 不一致
    Evidence: .omo/evidence/task-27-tablet.png
  ```
  **Commit**: YES — `feat(ui): mobile and tablet practice pages use shared renderer` — Files: `.vtj/vue/mobile_practice.vue`, `.vtj/vue/tablet_practice.vue`

---

- [x] 28. 模块 G-1/G-2：日志编码轮转 + README 重写

  **What to do**:
  - 日志配置强制 **UTF-8** 编码 + 按大小轮转（当前 `backend/logs/app.log` **26.1 MB** 且部分中文行乱码，如 `瑙ｆ瀽澶辫触` = 解析失败）
  - `backend/README.md` 重写为真实架构（当前声称 MySQL 8.0 + Redis + `routers/auth.py`，实际是 SQLite WAL + `app/api/v1/` 布局），并在开头标注旧版内容已 DEPRECATED

  **Must NOT do**:
  - **禁止**删除或截断既有 `app.log`（含故障证据；如需归档先备份）
  - **禁止**在 README 中保留任何与实际不符的端点/表名
  **Recommended Agent Profile**: `quick` | Skills: `writing`（README 需准确重写）
  **Parallelization**: YES | Wave 5 | **Blocks**: 45 | **Blocked By**: 11
  **References**:
  - `backend/logs/app.log` — 26.1 MB；乱码样例行 `2026-10-04 11:54:35,419 - app.api.v1.question_import - ERROR - [import-async] import_id=1494 鏄ｆ瀽澶辫触: No /Root object!`
  - `backend/README.md:1-20` — **过时内容**（MySQL 8.0 主从 + Redis 6.0 + `routers/` 目录）
  - `backend/app/api/v1/` — 真实路由目录
  - `backend/.env` — `DB_TYPE=sqlite` / `SQLITE_PATH=./data/question_bank.db`
  **Acceptance Criteria**: 新日志文件中文**不乱码**；轮转阈值生效；README 无过时端点/表名
  **QA Scenarios**:
  ```
  Scenario: 中文日志不再乱码
    Tool: Bash (PowerShell)
    Preconditions: 已备份旧 app.log
    Steps: 1) 重启后端，触发一次解析（用 S1）  2) 读新日志文件（UTF-8 解码）
           3) 断言含「解析完成」而非「瑙ｆ瀽瀹屾垚」  4) 断言文件大小 < 阈值
    Expected Result: 中文正常，乱码消失
    Failure Indicators: 仍出现乱码（编码未生效）
    Evidence: .omo/evidence/task-28-log-encoding.txt
  Scenario: README 与实际架构一致
    Tool: Bash (PowerShell)
    Steps: 1) Select-String README 断言**不含** "MySQL 8.0" 与 "routers/auth.py"
           2) 断言含 "app/api/v1" 与 "SQLite"  3) 抽 3 个端点与 openapi.json 比对，存在
    Expected Result: README 无过时内容，端点真实存在
    Failure Indicators: 仍含 MySQL/routers 描述（未重写干净）
    Evidence: .omo/evidence/task-28-readme.txt
  ```
  **Commit**: YES — `chore(log): utf8 encoding and rotation` + `docs: rewrite backend README to actual architecture` — Files: 日志配置, `backend/README.md`

- [ ] 29. ★ Playwright 抽样验收：PW-1..PW-12（9 个真实语料）

  **What to do**:
  - 按设计方案 §3.11.3 的 PW-1..PW-12 逐条执行，**只用** S1–S9 真实语料
  - 每条证据（`.omo/evidence/pw-{n}-{场景}.png` + `.txt`）首行固定写
    `文件: <绝对路径> | 大小: <bytes> | SHA256: <前16位> | import_id: <id>`
  - 测试数据统一打 `qa_tag` 前缀；每轮后跑 `gate_l1_parser.py --subject gongzhuan` 确认 2583 基线未变
  - 测试产生的 import 记录与题目行**必须清理或标记**，不得污染基线

  **Must NOT do**:
  - **禁止**使用虚拟/空/构造文件（§3.11.1 硬规则 1-4）
  - **禁止**跳过任何一条 PW 用例
  - **禁止**在证据里省略四要素
  **Recommended Agent Profile**: `unspecified-high` | Skills: `playwright`
  **Parallelization**: Can Run In Parallel: NO | **Wave 6（收敛点）** | **Blocks**: 45 | **Blocked By**: 20–28
  **References**: `.omo/plans/question-import-full-repair.md:3.11.2`（**9 个语料完整路径与覆盖目标**）+ `:3.11.3`（**12 条 PW 用例的完整步骤与通过标准**）
  **Acceptance Criteria**: PW-1..PW-12 全 PASS；证据四要素齐全；公专基线未变
  **QA Scenarios**:
  ```
  Scenario: PW-1 分离导入端到端（Word 题目 + PDF 答案）
    Tool: Playwright
    Steps: 1) 上传 S1 → 预览  2) 上传 S2 作为答案 → 匹配
           3) 断言全程无 "signal is aborted"  4) 断言 import_id 只新增 2 条
           5) 断言匹配率 == 100%  6) 断言预览四区（题干/选项/答案/解析）齐全
    Expected Result: 匹配率 100%，四区齐全，无 abort
    Evidence: .omo/evidence/pw-1-separate-import.png + .txt
  Scenario: PW-10 申论省级卷必须被阻断且零写入
    Tool: Playwright + 只读 SQL
    Steps: 1) 记录 N0  2) 上传 S8  3) 断言提示「答案段数与题目数不匹配」
           4) 断言库中 question_bank 行数 == N0（零写入）
    Expected Result: 正确阻断 + 零写入
    Failure Indicators: 导入成功（说明阻断被放宽 → 盲配风险）
    Evidence: .omo/evidence/pw-10-shenlun-blocked.png + .txt
  ```
  **Commit**: YES — `test(e2e): playwright sampling on 9 real specimens` — Files: `.omo/evidence/pw-*`, `backend/scripts/`（如新增 QA 脚本）

---

- [x] 30. 模块 J-1-1/J-1-2：题组图片落盘通道 + `owner` 参数

  **What to do**:
  - `question_ingest/images.py` 新增 `save_images_for_group(text, group_id, ...)`，落盘到 `/static/question-groups/{gid}/`，与 `question_id` 路径**物理隔离**
  - `_get_or_create_shenlun_group`（`:1996-2006`）在落库后立即调用它处理 `shared_content` 中的 `[IMAGE:...]`
  - `questions.py:623-624` 的 `render_image_placeholder` 增加 `owner` 参数，`owner='group'` 时生成 `/static/question-groups/{gid}/...`
  - `app.main` 增加 `/static/question-groups` 静态挂载

  **Must NOT do**:
  - **禁止**复用 `/static/questions/{qid}/` 路径（会与题目图片混淆并可能互相覆盖）
  - **禁止**改动现有题目图片的落盘路径（会影响 224 道含图题）
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 7（与 31-35 并行）| **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:1661` — `_extract_and_save_images(content_text, question_id, ...)`（**只接受 question_id，缺口在此**）
  - `backend/app/api/v1/question_import.py:1834` — `[IMAGE:x_y]` / `[IMAGE:uuid_x_y]` 占位符协议
  - `backend/app/api/v1/question_import.py:1996-2006` — `_get_or_create_shenlun_group`（写入 `shared_content`）
  - `backend/app/api/v1/questions.py:623-624` — `render_image_placeholder(group.shared_content)`
  - `.vtj/vue/answer_page.vue:95` — `renderQuestionContent(state.groupMaterials[group_id].shared_content)`（裂图的消费端）
  - `.omo/plans/question-import-full-repair.md:3.10` (J-1) — 五环证据链
  **Acceptance Criteria**: 申论复合题材料图片**零裂图**；`gate_l3_ingest` 断言 9 从 FAIL 转 PASS
  **QA Scenarios**:
  ```
  Scenario: 申论材料图片零裂图（RC 后续缺陷修复验证）
    Tool: Playwright
    Steps: 1) 上传 S9（申论地市级）并入库  2) 教师端预览：断言材料区所有 <img> 的 naturalWidth > 0
           3) 学生端作答：同断言  4) 检查无 404 请求
    Expected Result: 全部图片正常显示，零裂图
    Failure Indicators: 任一 img naturalWidth == 0（图片未为题组落盘）
    Evidence: .omo/evidence/task-30-group-images.png + .txt
  Scenario: 题目图片路径零回归
    Tool: Bash (PowerShell)
    Steps: 1) 断言 /static/questions/ 下 263 条 question_image 记录对应文件全部存在（与任务 2 基线比对）
    Expected Result: 224 道含图题的图片路径全部未变
    Failure Indicators: 路径被改（会影响历史数据）
    Evidence: .omo/evidence/task-30-question-images-noregress.txt
  ```
  **Commit**: YES — `fix(import): persist images for question groups with isolated path` — Files: `backend/app/services/question_ingest/images.py`, `backend/app/api/v1/question_import.py`, `backend/app/api/v1/questions.py`, `backend/app/main.py`

---

- [x] 31. 模块 J-1-3/J-1-4：材料复用键改 SHA256 + 缓存改 LRU

  **What to do**:
  - `question_import.py:1989-1992` — 跨批复用键从 `shared_content LIKE '%'+text[:60]+'%'` 改为
    `hashlib.sha256(normalize(text).encode()).hexdigest()` 全文指纹；保留一个指纹→group_id 的映射表（可用新列或内存缓存，**若需加列必须走迁移脚本且默认 dry-run**）
  - `question_import.py:2010` — `_SHENLUN_GROUP_CACHE: Dict[str,int]` 改为 `functools.lru_cache(maxsize=256)`，并提供 `clear()`，在每个导入批次结束时清理

  **Must NOT do**:
  - **禁止**保留任何 `LIKE '%...%'` 的材料复用判断
  - **禁止**无上限的模块级可变字典
  - **禁止**在未备份的情况下执行 ALTER TABLE
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: YES | Wave 7 | **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:1988-1992` — **误合并现场**（前 60 字 LIKE + 子串二次校验）
  - `backend/app/api/v1/question_import.py:2010` — `_SHENLUN_GROUP_CACHE`（**无界全局字典**）
  - `backend/app/models/models.py:255-277` — `QuestionGroup`（若需加指纹列）
  - `.omo/handoff-shenlun-v4.md:203-217` — 迁移脚本约定：**幂等 + 可回滚 + 默认 dry-run + `--apply` 才写入 + 迁移前自动备份**
  **Acceptance Criteria**: 前 60 字相同但内容不同的材料**不再误合并**；缓存有上限且可清空
  **QA Scenarios**:
  ```
  Scenario: 雷同开头但不同的材料不再误合并（误合并修复验证）
    Tool: pytest
    Steps: 1) 构造两份材料 A/B，前 60 字完全相同，第 61 字起不同
           2) 依次入库  3) 断言 question_groups 产生 **2 行**
    Expected Result: 2 行（不再误合并）
    Failure Indicators: 只有 1 行（误合并复现 → 材料互相污染）
    Evidence: .omo/evidence/task-31-no-false-merge.txt
  Scenario: 缓存有界且可清空
    Tool: pytest
    Steps: 1) 连续入库 1000 个不同材料  2) 断言缓存条目数 <= 256
           3) 调用 clear()  4) 断言条目数 == 0
    Expected Result: 有界 + 可清空（内存泄漏修复）
    Failure Indicators: 1000 条（无界增长）
    Evidence: .omo/evidence/task-31-lru-bounded.txt
  ```
  **Commit**: YES — `fix(import): sha256 material reuse key and bounded cache` — Files: `backend/app/api/v1/question_import.py`, `backend/tests/test_shenlun_group_cache.py`

---

- [x] 32. 模块 J-2-1：表格行按 `top` 原位插入

  **What to do**（`question_import.py:1082-1093`）: 表格行不再 `parts.append(row_text)`（页尾追加），改为用 `line_tops` 二分定位，把表格行插到 `page_lines` 的**正确行位置**，再统一拼页文本

  **Must NOT do**:
  - **禁止**回退已修的「全文翻倍」缺陷（`page_norm` 子串判重必须保留）
  - **禁止**把表格行转成 Markdown 表格（会破坏题号连续性识别）
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 7 | **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:1068-1071` — `text_raw` / `text` 与 `parts.append(text)`
  - `backend/app/api/v1/question_import.py:1082-1093` — **表格页尾追加现场**（J-2a）
  - `backend/app/api/v1/question_import.py:1073-1080` — 2026-09-29 修复注释：全文翻倍 14436→28873、题号 70→140
  - `backend/app/api/v1/question_import.py:1001-1005` — `line_tops` 的来源（`extract_text_lines()` 的 `top` 坐标）
  - `backend/app/api/v1/question_import.py:839-891` — `_norm_for_dedup`（判重归一化）
  **Acceptance Criteria**: 表格内容出现在其原始行位置；行测 `gate_l2` 退出码 0；全文翻倍缺陷不回归
  **QA Scenarios**:
  ```
  Scenario: 资料分析材料表不再被移到页尾
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8
    Steps: 1) 解析 S6，dump 全文到临时文件  2) 定位「资料分析」分节
           3) 断言材料表的表头行紧随该节首，而非出现在节末
           4) 断言全文长度与基线偏差 < 1%（未引入翻倍）
    Expected Result: 表格原位，字符数不翻倍
    Failure Indicators: 表格出现在节末（未修复）；或字符数翻倍（去重回归）
    Evidence: .omo/evidence/task-32-table-in-place.txt
  Scenario: 行测 G2 零回归
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/gate_l2_matching.py  2) 断言退出码 0
           3) python scripts/gate_l1_parser.py --subject xingce  4) 断言退出码 0
    Expected Result: 两门禁均 0
    Failure Indicators: 任一漂移
    Evidence: .omo/evidence/task-32-l2.txt
  ```
  **Commit**: YES — `fix(parser): insert pdf table rows at their original line position` — Files: `backend/app/api/v1/question_import.py`, `backend/tests/test_pdf_table_position.py`

---

- [x] 33. 模块 J-2-2/J-2-3：材料页识别 + 图片归属指向后继题号

  **What to do**:
  - 新建 `question_ingest/matdetect.py`：判定「材料页」—— 满足「该页连续 N 行均为表格且无题号」或「命中 `（一）（二）` 全角括号独占行锚点」
  - `question_import.py:1038-1039` 的 `if qn <= 0: qn = carry_in_qn or cur_qn` 分两种情形：普通页回落 `carry_in_qn`；**材料页**改为**前瞻扫描 `page_lines` 找后继第一个题号**
  - 复用行测已有材料块锚点（`（一）（二）` 全角括号独占行，实测 364 块），**不新建锚点体系**

  **Must NOT do**:
  - **禁止**改动行测的题号正则 `XINGCE_QNUM_PATTERN` 与答案锚点切分
  - **禁止**让材料页的图片归属到前一题号
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 7 | **Blocks**: 29, 45 | **Blocked By**: 32
  **References**:
  - `backend/app/api/v1/question_import.py:1011-1019` — `carry_in_qn` 与 `qn_at` 构建
  - `backend/app/api/v1/question_import.py:1034-1049` — **图片归属判定的现场**（J-2b）
  - `backend/app/services/text_parser.py:2036-2038` — 分节标记后的 spill 逻辑（材料归属的既有正确做法）
  - `backend/app/services/composite_matcher.py` — `match_xingce_material_groups()`（材料块归组的既有实现，**复用不新建**）
  - `solve_problems_files/行测题目导入优化方案.md:24` — S6 实测：资料分析等材料块 100% 覆盖，共 **364 块**，锚点为全角括号独占行 `（一）（二）`
  **Acceptance Criteria**: 行测材料块数仍为 364 量级；**块内无题号**；块内图片全部归本块；`gate_l2` 退出码 0
  **QA Scenarios**:
  ```
  Scenario: 行测资料分析材料块归属正确（E2E-11）
    Tool: Bash (PowerShell)
    Preconditions: 已设 UTF-8
    Steps: 1) 解析 S6 并 dump 块列表  2) 定位资料分析分节的材料块
           3) 断言**每个材料块内不含题号正则命中**  4) 断言材料块数与基线一致（364 量级）
           5) 断言材料块内的 [IMAGE:...] 其归属题号 == 该材料块对应的题号区间
    Expected Result: 块内无题号、图片归本块、块数不漂移
    Failure Indicators: 块内含题号；或图片归属到前一题（J-2b 未修复）
    Evidence: .omo/evidence/task-33-material-attribution.txt
  Scenario: 非材料页行为不变（无回归）
    Tool: pytest
    Steps: 1) pytest backend/tests/test_pdf_image_attribution.py  2) 断言全部 PASS
    Expected Result: 普通页仍按「上方最近行题号」归属
    Failure Indicators: 普通题图片归属改变（会影响 3125 张图的既有归属）
    Evidence: .omo/evidence/task-33-noregress.txt
  ```
  **Commit**: YES — `fix(parser): attribute material-page images to the following question` — Files: `backend/app/services/question_ingest/matdetect.py`, `backend/app/api/v1/question_import.py`

---

- [x] 34. 模块 J-3-1..J-3-6：Excel 容错字典 + 表头归一 + 表头探测 + GBK 嗅探 + 丢行报告化

  **What to do**（`backend/app/services/question_ingest/excel_reader.py` + `_normalize_question:505-534`）:
  - `COLUMN_ALIASES` **单一事实来源**字典：题干/答案/**解析**/**分值**/**难度**/**来源**/**知识点**/题型/选项A-H，每语义 **≥ 8 个别名**
  - `normalize_header()`：去首尾空白 + 全角空格转半角 + 去换行制表 + 去尾部冒号 + **大小写不敏感** + 去括号备注
  - `detect_header_row()`：前 5 行逐行打分（命中别名词数最多者即表头）
  - `_parse_csv_buffer` 编码嗅探顺序 `utf-8-sig → gbk → gb18030 → latin-1`，**不抛未捕获异常**
  - `_normalize_question` 丢行改为**返回结构化丢弃报告** `{'row','reason','raw'}`，由 `/batch-parsed` 汇总进 `failed_items`
  - `_parse_excel_buffer` 遍历全部 sheet 或提供 `sheet` 参数 + 明确日志

  **Must NOT do**:
  - **禁止**为 Excel 路径新建**真实测试文件**（遵守用户禁令）—— L3 的 Excel 断言改用纯函数单测或从真实 docx 解析结果反向构造的内存 DataFrame
  - **禁止**给缺失的解析/分值等字段填默认值（缺省必须留空）
  - **禁止**保留 `return None` 静默丢行
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 7 | **Blocks**: 29, 45 | **Blocked By**: 11
  **References**:
  - `backend/app/api/v1/question_import.py:505-534` — `_normalize_question` 本体（**J-3a/b/c/d/e 的现场**）
  - `backend/app/api/v1/question_import.py:470-494` — `_parse_excel_buffer`（`:481` 只取 `rows[0]` 作表头 = J-3d；`:479` `wb.active` 只取首 sheet = J-3g）
  - `backend/app/api/v1/question_import.py:497-503` — `_parse_csv_buffer`（`decode('utf-8-sig')` = **J-3f GBK 直接抛错**）
  - `backend/app/api/v1/question_import.py:2677-2698` — `/batch-parsed` 循环与 `failed_items` 结构（丢弃报告的汇总点）
  - `solve_problems_files/README.md` — 「232 道公专空解析」的根因记录（与 J-3a 同源）
  **Acceptance Criteria**: 7 个缺口全部闭合；`gate_l3_ingest` 断言 10 从 FAIL 转 PASS；丢行可见于 `failed_items`
  **QA Scenarios**:
  ```
  Scenario: 列名容错（纯函数单测，不建文件）
    Tool: pytest
    Steps: 1) pytest -k excel_column_aliases -v
           2) 断言 "题 目 内 容"（全角空格）能匹配到题干
           3) 断言 "题目内容："（带冒号）能匹配
           4) 断言 "Question Content"（大小写）能匹配
           5) 断言含「解析」列时 answer_analysis 被正确取出
    Expected Result: 5 类变体全部命中，且解析列不再丢失
    Failure Indicators: 任一变体失配（J-3e 未修复）；或解析仍为空（J-3a 未修复）
    Evidence: .omo/evidence/task-34-column-aliases.txt
  Scenario: GBK CSV 不再抛未捕获异常 + 丢行有报告
    Tool: pytest
    Steps: 1) 构造 **GBK 编码的内存字节**（非文件），内容为含题干与答案的 CSV
           2) 调用解析函数  → 断言正常返回，不抛 UnicodeDecodeError
           3) 构造缺答案行 → 断言它出现在丢弃报告里且 reason == '缺答案'，且有 row 序号
    Expected Result: GBK 可解析；丢行可见可定位
    Failure Indicators: 抛 UnicodeDecodeError；或丢行静默消失
    Evidence: .omo/evidence/task-34-gbk-and-drop-report.txt
  ```
  **Commit**: YES — `feat(excel): tolerant column dictionary, header detection and gbk sniffing` — Files: `backend/app/services/question_ingest/excel_reader.py`, `backend/app/api/v1/question_import.py`, `backend/tests/test_excel_reader.py`

---

- [x] 35. 模块 J：门禁扩展（L3 断言 9/10 + L1 指纹键 + L2 材料守卫）

  **What to do**:
  - L3 新增**断言 9**：复合题入库后，`shared_content` 中每个 `[IMAGE:xxx]` 都必须有对应落盘文件（缺一即失败）
  - L3 新增**断言 10**：Excel 路径传入 3 行 → 库中恰好 3 题；**含解析列的必须落库**；缺答案行必须出现在 `failed_items` 而非静默消失
  - L1 新增指纹键：`材料块数`、`材料页表格行归属正确率`
  - L2 新增守卫：「材料块内不得含题号」+「材料块的图片不得归属到前一题号」
  - 同步 `gate_all.py` 无需改（自动包含新断言）

  **Must NOT do**: **禁止**降低新断言的严格度；**禁止**把新守卫的基线调到「当前实现的结果」以外的值（若当前实现仍有缺陷，应先修实现再定基线）
  **Recommended Agent Profile**: `deep` | Skills: `tdd`
  **Parallelization**: YES | Wave 7（建议**最后**做，需在 30-34 完成后）| **Blocks**: 29, 45 | **Blocked By**: 30, 31, 32, 33, 34
  **References**:
  - `backend/scripts/gate_l3_ingest.py` / `gate_l1_parser.py` / `gate_l2_matching.py` — 任务 6/7/8 的产物（扩展点）
  - `backend/app/api/v1/question_import.py:1849-1927` — `[IMAGE:...]` 标记的提取与落盘循环（断言 9 的判据来源）
  - `solve_problems_files/行测题目导入优化方案.md:24` — S6：材料块 364 的基线数值（断言 9/10 的期望区间）
  **Acceptance Criteria**: 4 条新断言/守卫全部就位且**能真实检出对应缺陷**（反向用例存在）
  **QA Scenarios**:
  ```
  Scenario: 新断言能检出对应缺陷（反向验证）
    Tool: pytest
    Steps: 1) pytest backend/tests/test_gate_l3.py -k "group_image_persisted" -v
           2) 断言测试 FAIL，且失败信息显示「shared_content 含 N 个 IMAGE 标记但只有 M 个落盘文件」
           3) 应用任务 30 修复后重跑 → 断言 PASS
    Expected Result: 红 → 绿（门禁真的抓得住）
    Failure Indicators: 修改实现后仍 FAIL（说明断言判据写错）
    Evidence: .omo/evidence/task-35-l3-assert9.txt
  Scenario: L1 新指纹键与 L2 材料守卫生效
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/gate_l1_parser.py --subject xingce  2) 断言 JSON 含 材料块数 且值与基线一致
           3) python scripts/gate_l2_matching.py  4) 断言退出码 0 且输出含「材料块内题号数 == 0」
    Expected Result: 新键存在且基线一致；新守卫通过
    Failure Indicators: 新键缺失；或守卫报出材料块含题号（J-2 未真正修复）
    Evidence: .omo/evidence/task-35-l1-l2-new-guards.txt
  ```
  **Commit**: YES — `test(gate): extend L3/L1/L2 for group images, excel drops and material guards` — Files: `backend/scripts/gate_l3_ingest.py`, `backend/scripts/gate_l1_parser.py`, `backend/scripts/gate_l2_matching.py`, `backend/tests/test_gate_l3.py`

---

- [x] 36. 模块 G-3/G-4：删除 20+ 散落测试脚本（分批）

  **What to do**:
  - **前置**：逐个 `grep -r` 全仓确认零引用；把**完整清单 + 引用检查结果**写入 `.omo/evidence/task-delete-manifest.txt`
  - 第一批（零引用且明确是调试产物）：`_p1.py` `_p2.py` `_p3.py` `check_versions.py` `check_xicon.py` `verify_types.py` `verify_types2.py` `smoke_tmp.js` `debug.log` `.DS_Store` `api_test.json` `docx_text_output.txt` `docx_v4.txt` `pipeline_test.txt` `pipeline_v2.txt` `test_notes_api.py` `test_random_api.py` `test_obsidian_read.py`
  - 第二批（需逐个确认后再删）：`backfill_unclassified.py` `clean_questions.py` `fix_irrelevant_images.py` `fix_utb_in_db.py` `reset_password.py` `restart_backend.py` `create_news_tables.py` `check_notes_api.py`
  - 每批删除后跑 `gate_all.py --quick`；任一失败立即停止并从 git 恢复该批

  **Must NOT do**:
  - **禁止**删除 `backend/scripts/` 下**任何**被方案引用的验证脚本（`verify_parser_regression.py` / `verify_xingce_regression.py` / `verify_task11_*`（已移入 `_archive/`）/ `repair_question_types.py` / `migrate_xingce_knowledge_points.py` 等）
  - **禁止**删除 `backend/data/*.bak*` 与 `text_cache.bak_20261001_200518`
  - **禁止**用 `git add -A`（必须显式列出删除的文件）
  - **禁止**在引用检查未通过时删除
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: Can Run In Parallel: NO | Wave 8（**分批串行**，每批后验证）| **Blocks**: 45 | **Blocked By**: 35
  **References**:
  - 仓库根目录实测清单（设计方案 §2 RC-10 表格中的完整列表）
  - `backend/README.md`（已被任务 28 重写，确认其中未引用这些脚本）
  - `solve_problems_files/行测导入门禁与运维手册.md:155-165` — **现有备份清单，禁止清理**
  - `.omo/notepads/xingce-import-optimization/followup-findings.md:52-54` — 红线：DB 备份、312 条 import 记录、`text_cache.bak_*` 不得清理
  **Acceptance Criteria**: manifest 完整；分批删除且每批后 `gate_all.py --quick` 通过；`git status` 无意外文件
  **QA Scenarios**:
  ```
  Scenario: 删除前引用检查全部通过
    Tool: Bash (PowerShell)
    Preconditions: 无
    Steps: 1) 对每个待删文件执行 grep -r "<文件名>" backend/ scripts/ src/ .vtj/ --include=*.py --include=*.vue --include=*.json
           2) 断言每个文件的命中数 == 0（或仅命中自身）
           3) 断言 manifest 文件已写入且行数 == 待删文件数
    Expected Result: 全部零引用 + manifest 完整
    Failure Indicators: 任一文件有引用（删除会破坏功能）
    Evidence: .omo/evidence/task-delete-manifest.txt
  Scenario: 分批删除后门禁仍通过
    Tool: Bash (PowerShell)
    Preconditions: 第一批已删
    Steps: 1) python scripts/gate_all.py --quick  2) 断言退出码 0
           2) 断言 git status 的删除列表与 manifest 第一批完全一致（无多删）
           3) 执行第二批后重复 1-2
    Expected Result: 两批均通过，无多删
    Failure Indicators: 门禁失败（删到了有用的东西）
    Evidence: .omo/evidence/task-36-after-delete.txt
  ```
  **Commit**: YES（每批一个）— `chore: remove stale debug scripts batch N` — Files: 显式列出的删除清单

> **拆分阶段通用铁律（任务 37–44 每一步都适用）**：
> 1. **纯移动（move）不改逻辑** —— `git diff` 必须显示为「纯删除 + 纯新增」，零逻辑变更
> 2. 每步一个独立 commit，message 含 `refactor(import): move <mod> to question_ingest, pure move`
> 3. 每步**前后各跑一次** `gate_l0_redlines.py` + `gate_l3_ingest.py`
> 4. **禁止** `git add -A`；每次显式 `git add` 具体文件
> 5. 保持 `from ...question_import import X` **全兼容**（`__init__.py` re-export）
> 6. 改动前后各跑 `gate_all.py --quick`

- [x] 37. I-2 平移 `excel_reader.py`（约 130 行，热手）

  **What to do**: 新建 `question_ingest/excel_reader.py`，把 `_parse_excel_buffer` / `_parse_csv_buffer` / `_normalize_question` 原样移入；`question_import.py` 改为从该模块导入；`__init__.py` re-export 保持调用方零改动
  **Must NOT do**: 禁止改动函数体；禁止顺手「优化」代码
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: YES | Wave 9（**同文件互斥**：与 38-44 中任一 `question_import.py` 改动任务不可并发）| **Blocks**: 41, 42, 43, 45 | **Blocked By**: 36
  **References**: `backend/app/api/v1/question_import.py:470-534`（待平移的三函数）；`backend/app/api/v1/question_import.py:2714`（`from ...services.text_parser import _detect_question_type` 的相对导入风格参照）
  **Acceptance Criteria**: `gate_l0` 红线 0；`gate_l3` 全绿；`git diff --stat` 显示纯删除+纯新增且行数守恒
  **QA Scenarios**:
  ```
  Scenario: 纯移动后行为不变
    Tool: Bash (PowerShell)
    Steps: 1) git diff --stat  2) 断言新增行数 == 删除行数（守恒）
           3) git diff -U0  4) 断言无任何非空白字符的增删（纯移动）
           5) gate_l0 + gate_l3 → 均 0
    Expected Result: 纯移动、无逻辑变更、门禁全绿
    Failure Indicators: 行数不守恒或有逻辑改动（不再是纯移动）
    Evidence: .omo/evidence/task-37-pure-move.txt
  Scenario: Excel 路径仍可工作（纯函数级）
    Tool: pytest
    Steps: 1) pytest -k excel -v  2) 断言全部 PASS
    Expected Result: 行为不变
    Failure Indicators: FAIL（移动破坏了导入路径）
    Evidence: .omo/evidence/task-37-excel.txt
  ```
  **Commit**: YES — `refactor(import): move excel_reader to question_ingest, pure move` — Files: `backend/app/services/question_ingest/excel_reader.py`, `backend/app/services/question_ingest/__init__.py`, `backend/app/api/v1/question_import.py`

---

- [x] 38. I-3 平移 `docx_reader.py`（约 200 行）

  **What to do**: 把 `_sanitize_docx_rels` / `_open_docx_resilient` / `_extract_text_from_docx_raw_xml` / `_extract_text_from_docx` / `_rels_base_dir` 平移至 `question_ingest/docx_reader.py`
  **Must NOT do**: 禁止改动 docx 容错逻辑（`_sanitize_docx_rels` 是畸形 docx 的兜底）
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: Wave 9（同文件互斥）| **Blocks**: 41-45 | **Blocked By**: 37
  **References**: `backend/app/api/v1/question_import.py:578-730`（docx 全套函数，含畸形 docx 的两级兜底与 XML 兜底）
  **Acceptance Criteria**: 纯移动；`gate_l0`/`gate_l3` 全绿；S3（畸形 docx）仍能解析
  **QA Scenarios**:
  ```
  Scenario: 畸形 docx 仍能解析（容错逻辑零回归）
    Tool: Bash (PowerShell)
    Preconditions: S3 已备好
    Steps: 1) 移动前后各调一次 _extract_text_from_docx(S3 字节)
           2) 断言两次输出**逐字节相同**  3) 断言长度 > 0
    Expected Result: 输出完全一致（证明纯移动）
    Failure Indicators: 输出不同（移动时漏了容错分支）
    Evidence: .omo/evidence/task-38-docx-parity.txt
  Scenario: 纯移动校验
    Tool: Bash (PowerShell)
    Steps: 1) git diff -U0  2) 断言无非空白增删  3) gate_l0 + gate_l3 → 0
    Expected Result: 纯移动 + 门禁全绿
    Evidence: .omo/evidence/task-38-pure-move.txt
  ```
  **Commit**: YES — `refactor(import): move docx_reader to question_ingest, pure move`

---

- [x] 39. I-4 平移 `tags.py`（约 300 行）

  **What to do**: 把 `_auto_detect_tags` / `_detect_complete_paper` / `_extract_paper_name` / `_get_or_create_import_paper` 平移至 `question_ingest/tags.py`
  **Must NOT do**: 禁止改动省份/年份提取规则（铁律 R-5：省份只从文件夹名）
  **Recommended Agent Profile**: `quick` | Skills: 无
  **Parallelization**: Wave 9 | **Blocks**: 41-45 | **Blocked By**: 38
  **References**: `backend/app/api/v1/question_import.py:1443-1659`（四个标签/建卷函数）；铁律 R-5 见 `solve_problems_files/行测题目导入优化方案.md:69`
  **Acceptance Criteria**: 纯移动；85 套省份/年份仍 100% 正确
  **QA Scenarios**:
  ```
  Scenario: 建卷元数据零回归
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/verify_task12_metadata.py  2) 断言 85 套省份/年份 100% 正确
           3) python scripts/verify_task12_idempotent.py  4) 断言幂等
    Expected Result: 元数据与幂等性均不变
    Failure Indicators: 任一项失败（标签逻辑被破坏）
    Evidence: .omo/evidence/task-39-tags.txt
  Scenario: 纯移动校验
    Tool: Bash (PowerShell)
    Steps: 1) git diff -U0 → 无非空白增删  2) gate_l0 + gate_l3 → 0
    Expected Result: 纯移动 + 门禁全绿
    Evidence: .omo/evidence/task-39-pure-move.txt
  ```
  **Commit**: YES — `refactor(import): move tags to question_ingest, pure move`

---

- [x] 40. I-5 平移 `images.py`（约 400 行）

  **What to do**: 把 `_extract_and_save_images` / `_compress_and_store` / `_check_size` / 占位符协议相关函数平移至 `question_ingest/images.py`（含任务 30 新增的 `save_images_for_group`）
  **Must NOT do**: 禁止改动 `[IMAGE:x_y]` 占位符格式；禁止改动 `/static/questions/` 路径（263 条历史记录依赖）
  **Recommended Agent Profile**: `unspecified-high` | Skills: 无
  **Parallelization**: Wave 9 | **Blocks**: 41-45 | **Blocked By**: 39
  **References**: `backend/app/api/v1/question_import.py:1661-1927`（图片提取/落盘全套，含 1834 的占位符协议）；任务 30 的 `save_images_for_group`
  **Acceptance Criteria**: 纯移动；263 条 `question_image` 路径全部未变；组图片通道仍工作
  **QA Scenarios**:
  ```
  Scenario: 题目图片路径零回归
    Tool: Bash (PowerShell)
    Steps: 1) 记录移动前 /static/questions/ 下文件清单与哈希
           2) 移动 + 解析 S1（含图片的 docx）  3) 断言新文件路径前缀与移动前一致
           4) 断言历史 263 条对应文件全部仍存在
    Expected Result: 路径与文件零变化
    Failure Indicators: 路径前缀变化（历史图片全失效）
    Evidence: .omo/evidence/task-40-images.txt
  Scenario: 纯移动校验
    Tool: Bash (PowerShell)
    Steps: 1) git diff -U0 → 无非空白增删  2) gate_l0 + gate_l3（含断言 9）→ 0
    Expected Result: 纯移动 + 门禁全绿
    Evidence: .omo/evidence/task-40-pure-move.txt
  ```
  **Commit**: YES — `refactor(import): move images to question_ingest, pure move`

---

- [x] 41. ★ I-6 平移 `pdf_reader.py`（约 700 行，**风险最高：单独 commit + 单独全套 E2E**）

  **What to do**: 把 `_extract_text_from_pdf` / `_extract_text_from_scanned_pdf` / `_decode_pdf_image` / `_extract_images_from_pdf_page` / `_pdf_image_to_png` / `_pdf_has_images_only` / `_pdf_image_to_png` 平移至 `question_ingest/pdf_reader.py`
  **本任务必须额外做（你的裁决：保质保量，不越改越退）**:
  - **单独 commit**，不与任何其他平移混在同一 commit
  - **单独跑全套 E2E**（E2E-1/2/5/6/10/11 + PW-1/6/7/11）
  - **单独跑行测 170 份全量**：`python scripts/import_xingce_all.py --batches "国考行测" --dry-run`，断言分节序列全等、答案覆盖 100%、blocked=0
  - 移动后逐一比对「移动前后同一 PDF 的提取文本 **SHA256 完全相同**」——这是纯移动的最强证据

  **Must NOT do**:
  - 禁止改动 pdfplumber 路径的任何逻辑（742 题 100% 匹配依赖它）
  - 禁止改动 2026-09-29 的「全文翻倍」修复
  - 禁止改动任务 32/33 的表格定位与材料页归属
  - 禁止与其他平移合并成一个 commit
  **Recommended Agent Profile**: `unspecified-high` | Skills: `playwright`
  **Parallelization**: Wave 9（**必须独占**，不得与其他平移并发）| **Blocks**: 42-45 | **Blocked By**: 40
  **References**:
  - `backend/app/api/v1/question_import.py:892-1275`（pdf_reader 全套，含 `:973-1105` pdfplumber 主干、`:1073-1080` 翻倍修复、`:1133-1140` MinerU 分支、`:1150` 扫描件）
  - `solve_problems_files/行测题目导入优化方案.md:15-26` — 语料实测 S1–S7（170 份全含文本层、行测不需要 OCR）
  - `solve_problems_files/行测题目导入优化方案.md:196-198` — **六套试点基线：742 题 / 100% 匹配 / 阻断 0**
  - `solve_problems_files/行测导入门禁与运维手册.md:196-225` — 批量重导入指引与顺序铁律
  **Acceptance Criteria**: 纯移动；**同一 PDF 提取文本 SHA256 移动前后完全相同**；全套 E2E + 行测 170 份 dry-run 全绿
  **QA Scenarios**:
  ```
  Scenario: 提取文本逐字节相同（纯移动最强证据）
    Tool: Bash (PowerShell)
    Preconditions: 移动前先跑一次并记录哈希
    Steps: 1) 移动前：对 S6、S9、S2 各调一次 _extract_text_from_pdf，记录输出 SHA256
           2) 执行平移  3) 移动后重复步骤 1
           4) 断言 3 组哈希**逐一相同**
    Expected Result: 哈希完全相同（逻辑零变化）
    Failure Indicators: 任一哈希不同（移动中漏改或改错了逻辑）
    Evidence: .omo/evidence/task-41-text-hash-parity.txt
  Scenario: 行测 170 份全量零回归 + 全套 E2E
    Tool: Bash (PowerShell) + Playwright
    Steps: 1) python scripts/import_xingce_all.py --batches "国考行测" --dry-run
           2) 断言分节序列全等、答案覆盖 100%、blocked == 0
           3) gate_all.py 全量 → 断言各层状态与移动前一致
           4) 执行 E2E-1/2/5/6/10/11 + PW-1/6/7/11 → 全 PASS
    Expected Result: 全绿，行为零变化
    Failure Indicators: 任何一项漂移（必须 git 回退本 commit）
    Evidence: .omo/evidence/task-41-full-e2e.txt
  ```
  **Commit**: YES（**独占**）— `refactor(import): move pdf_reader to question_ingest, pure move` + 门禁证据写入 commit body

---

- [x] 42. I-7 平移 `upsert.py` + `links.py`（约 700 行）

  **What to do**: 把 `_upsert_question_core` / `_upsert_xingce_question` / `_detect_duplicate` / `_get_duplicate_info` 平移至 `question_ingest/upsert.py`；`_link_knowledge_points` / `_get_or_create_subject` / `_get_or_create_type` 平移至 `links.py`
  **Must NOT do**: 禁止改动去重口径（`328b0b0` 按题号+来源）；禁止改动 `_detect_question_type` 的调用约定
  **Recommended Agent Profile**: `unspecified-high` | Skills: `tdd`
  **Parallelization**: Wave 9 | **Blocks**: 43-45 | **Blocked By**: 41
  **References**: `backend/app/api/v1/question_import.py:277-454`（links 三函数 + `_detect_duplicate`）、`:2013-2235`（`_upsert_question_core`）、`:4610-4732`（`_upsert_xingce_question`）
  **Acceptance Criteria**: 纯移动；`gate_l3` 全部 10 条断言全绿；公专 2583 题逐字段未变
  **QA Scenarios**:
  ```
  Scenario: 落库语义零变化（L3 全断言）
    Tool: Bash (PowerShell)
    Steps: 1) gate_l3_ingest.py → 断言断言 1..10 全 PASS
           2) gate_l1_parser.py --subject gongzhuan → 断言 5 项一致
           3) 与任务 2 的 gongzhuan_field_fingerprint.json 逐题比对 → 断言 2583 题全部一致
    Expected Result: 落库语义与历史数据完全不变
    Failure Indicators: 任一断言 FAIL 或字段指纹不一致
    Evidence: .omo/evidence/task-42-upsert-parity.txt
  Scenario: 纯移动校验
    Tool: Bash (PowerShell)
    Steps: 1) git diff -U0 → 无非空白增删  2) gate_l0 → 0
    Expected Result: 纯移动
    Evidence: .omo/evidence/task-42-pure-move.txt
  ```
  **Commit**: YES — `refactor(import): move upsert and links to question_ingest, pure move`

---

- [x] 43. I-8 新建 `groups.py`，三处 `QuestionGroup` 收敛为一处

  **What to do**: 把 `:1996` / `:2371` / `:2427` 三处 `QuestionGroup(...)` 收敛为 `_upsert_question_group()` 单一函数，参数化 `group_type`（`shenlun_material` / `material` / `scenario` / `data_analysis`）
  **Must NOT do**: 禁止改变任一调用的现有语义（三种 group_type 的默认值必须保持）
  **Recommended Agent Profile**: `unspecified-high` | Skills: `tdd`
  **Parallelization**: Wave 9 | **Blocks**: 44, 45 | **Blocked By**: 42
  **References**: `backend/app/api/v1/question_import.py:1996-2006` / `:2371` / `:2427`（三处现场）；`backend/app/models/models.py:265-266`（`group_type` 枚举：material/scenario/passage/data_analysis）
  **Acceptance Criteria**: 三处收敛为一处且行为等价；`gate_l3` 断言 3/9 全绿
  **QA Scenarios**:
  ```
  Scenario: 收敛后行为等价
    Tool: pytest
    Steps: 1) pytest -k question_group_upsert -v  2) 断言三种 group_type 各 1 个用例全 PASS
           3) gate_l3_ingest.py → 断言断言 3 与 9 全 PASS
    Expected Result: 收敛后行为等价
    Failure Indicators: 任一 group_type 默认值被改动
    Evidence: .omo/evidence/task-43-groups.txt
  ```
  **Commit**: YES — `refactor(import): converge three QuestionGroup upserts into one` — Files: `backend/app/services/question_ingest/groups.py`, `backend/app/api/v1/question_import.py`

---

- [x] 44. I-9 行测三函数 → `text_parser/xingce.py`（**唯一动 `text_parser.py` 的步骤**）

  **What to do**: 把 `route_xingce_sections` / `split_xingce_answer_blocks` / `xingce_cross_validate` 移入新建的 `backend/app/services/text_parser/xingce.py`；`text_parser.py` 保持为薄壳（`__init__.py` re-export 保证所有 `from ...text_parser import X` 零改动）
  **★ 硬约束**：`extract_question_blocks` **函数体字节级不变** → **申论部分（`_parse_essay_document` 及其 15 个符号）必须留在 `text_parser.py`**，因为它被 `extract_question_blocks` 入口直接调用
  **Must NOT do**:
  - 禁止改动 `extract_question_blocks` 函数体（**L0 红线会 FAIL**）
  - 禁止移动申论解析符号
  - 禁止把 `text_parser.py` 改成 `text_parser/` 目录（会破坏 `from ...text_parser import` 的解析，除非同时保留同名 `.py`，此时须先确认 import 机制）
  **Recommended Agent Profile**: `unspecified-high` | Skills: `tdd`
  **Parallelization**: Wave 9（最后一步）| **Blocks**: 45 | **Blocked By**: 43
  **References**:
  - `backend/app/services/text_parser.py` — `route_xingce_sections` / `split_xingce_answer_blocks` / `xingce_cross_validate`（+296 行，T7/T8）+ `extract_question_blocks`（**红线**）
  - `.omo/plans/question-import-full-repair.md:3.9.1` — **可拆空间的诚实披露**（text_parser 只能减约 12%，申论被红线锁住）
  - `solve_problems_files/行测题目导入优化方案.md:85-98` — 实现落点表（这三函数的行数与来源）
  - `solve_problems_files/行测题目导入优化方案.md:312-326` — 红线清单（`extract_question_blocks` 字节级未改）
  **Acceptance Criteria**: `gate_l0` 的 `extract_question_blocks` 哈希**必须仍绿**；`gate_l2` 退出码 0；`text_parser.py` 行数下降（但申论部分仍在原地）
  **QA Scenarios**:
  ```
  Scenario: 红线函数体字节级未变（最关键）
    Tool: Bash (PowerShell)
    Steps: 1) gate_l0_redlines.py  2) 断言断言 1（extract_question_blocks 函数体 SHA256）PASS
           3) git diff -U0 -- backend/app/services/text_parser.py
           4) 断言 diff 中**只含删除**（无新增逻辑行），或新增仅为 import 语句
    Expected Result: 红线函数体哈希不变（= 字节级未改）
    Failure Indicators: 哈希变化（红线被破，必须 git 回退）
    Evidence: .omo/evidence/task-44-redline-hash.txt
  Scenario: 行测解析零回归
    Tool: Bash (PowerShell)
    Steps: 1) gate_l2_matching.py → 断言退出码 0（分节序列全等、区间一致、答案覆盖 100%、blocked=0）
           2) gate_l1_parser.py --subject xingce → 断言退出码 0
           3) python scripts/verify_xingce_regression.py → 断言全通过
    Expected Result: 行测全链路零回归
    Failure Indicators: 任一漂移
    Evidence: .omo/evidence/task-44-xingce.txt
  ```
  **Commit**: YES — `refactor(parser): move xingce section routing into text_parser/xingce, pure move`

---

- [ ] 45. ★ Playwright 复验：用同一批 S1–S9 全量复跑 PW-1..PW-12

  **What to do**: 在 Wave 9 全部拆分完成后，**用与任务 29 完全相同的 9 个真实语料**再跑一遍 PW-1..PW-12，逐条与任务 29 的证据**并排比对**，证明「10 步拆分后行为零变化」
  **Must NOT do**:
  - **禁止**换语料（换了就失去对比意义）
  - **禁止**跳过任何一条 PW
  - **禁止**在复验中「顺手修 bug」（发现问题记入 `known_broken.json` 并回到对应任务）
  **Recommended Agent Profile**: `unspecified-high` | Skills: `playwright`
  **Parallelization**: Can Run In Parallel: NO | **Wave 10（最终收敛点）** | **Blocks**: F1-F4 | **Blocked By**: 36, 44
  **References**:
  - `.omo/evidence/pw-*` — 任务 29 的原始证据（比对基准）
  - `.omo/plans/question-import-full-repair.md:3.11.3` — PW-1..PW-12 的完整步骤
  **Acceptance Criteria**: PW-1..PW-12 全 PASS；与任务 29 证据**结构一致**；公专 2583 基线未变；`gate_all.py` 全绿
  **QA Scenarios**:
  ```
  Scenario: 拆分后行为零变化（逐条对比证据）
    Tool: Playwright + 文件比对
    Steps: 1) 逐条重跑 PW-1..PW-12  2) 与 .omo/evidence/pw-*.png 并排比对
           3) 断言每条的「匹配率 / 题数 / 阻断数 / 引擎名」与任务 29 完全相同
           4) gate_all.py 全量 → 断言各层状态与拆分前一致
           5) gate_l1_parser.py --subject gongzhuan → 断言 5 项一致
    Expected Result: 全部指标逐项相同（证明纯移动零副作用）
    Failure Indicators: 任一指标漂移（拆分引入了行为变化，必须定位并回退对应 commit）
    Evidence: .omo/evidence/task-45-pw-reverify/  （逐条含 before/after 对照）
  Scenario: 门禁与公专基线最终确认
    Tool: Bash (PowerShell)
    Steps: 1) python scripts/gate_all.py  2) 断言退出码 0
           2) 与任务 2 的 gongzhuan_field_fingerprint.json 逐题比对 2583 题 → 断言全部一致
           3) git status 断言干净（无残留）
    Expected Result: 全绿 + 公专数据零变化
    Failure Indicators: 任一失败
    Evidence: .omo/evidence/task-45-final-gates.txt
  ```
  **Commit**: YES — `test(e2e): playwright re-verification after ten-step split, zero behaviour change` — Files: `.omo/evidence/task-45-pw-reverify/*`

---

## Final Verification Wave

> 4 个复核代理**并行**执行，全部 APPROVE 后呈现结果给用户，**取得明确同意**才算完成。
> **禁止**自动推进；**禁止**在取得用户同意前勾选 F1–F4。

- [ ] F1. **计划合规审计** — `oracle`
  逐条读 `.omo/plans/question-import-full-repair.md` 的 §4 Must Have / Must NOT Have。
  对每条 Must Have 验证实现存在（读文件 / curl 端点 / 跑命令）；
  对每条 Must NOT Have 全仓搜索违禁模式并给出 `file:line`；
  检查 `.omo/evidence/` 下所有证据文件是否存在且四要素齐全；
  比对交付物清单与设计方案 §3。
  输出：`Must Have [N/N] | Must NOT Have [N/N] | 证据 [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **代码质量审查** — `unspecified-high`
  跑 `python -m pytest backend/tests -q`（失败集合须与 `16 failed / 168 passed / 52 errors` 一致）
  + `python scripts/gate_all.py` 全绿 + `Invoke-WebRequest http://localhost:9527/` 返回 200。
  审查所有改动文件：`as any`/`@ts-ignore`、空 catch、生产环境 `console.log`、注释掉的代码、未用 import、
  AI slop（过度注释、过度抽象、泛化命名）。
  输出：`Gate [PASS/FAIL] | Pytest [N pass/N fail 与基线一致] | Vite [200/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **真实端到端 QA** — `unspecified-high`（+ `playwright` skill）
  从干净状态执行**全部** E2E-1..E2E-12 与 **PW-1..PW-12**，
  且**只使用** §3.11.2 的 S1–S9 真实语料。
  重点复验：RC-1 无 abort、RC-2 能真正入库、RC-3 前端改动能落库、
  RC-4 无 500、RC-5 `requirements` 非空、RC-6 改名仍可解析、J-1 零裂图、J-2 材料块块内无题号。
  证据存 `.omo/evidence/final-qa/`。
  输出：`Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **范围忠实度核查** — `deep`
  逐任务读「What to do」与实际 `git diff`/`git log` 比对 1:1：
  规格内该建的都建了（无遗漏）、规格外没建（无越界）。
  检查「Must NOT do」遵守情况；检测跨任务污染（任务 N 动了任务 M 的文件）；
  标记未记账的改动。
  输出：`Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

### 全局纪律（违反即回滚）
- **禁止 `git add -A`** —— 每次显式 `git add` 具体文件
- 禁止 `git checkout` / `reset` / `clean`
- `backend/tmp/`、`*.db*`、`题库/` 下 PDF、`node_modules/` 一律不入库
- 每个任务一个原子 commit；Wave 9 拆分任务**每步一个独立 commit**（可单独回滚）

### Commit 映射
| Wave | Commit 粒度 | Message 模板 |
|---|---|---|
| 0 | 每任务 1 个 | `chore(gate): baseline snapshot and evidence` / `docs(plan): archive solution to solve_problems_files` |
| 1 | 每任务 1 个 | `test(gate): L0 redline hash gate` / `test(gate): L3 ingest contract gate` / `test(gate): L1 parser fingerprint` … |
| 2 | 每任务 1 个 | `fix(import): raise poll timeout and retry` / `fix(import): slim status endpoint` / `feat(import): magic-byte sniffing` / `fix(import): define confirmed_items` |
| 3 | 每任务 1 个（串行） | `fix(import): single pendingQuestions source` / `feat(import): persist requirements and group_id` / `fix(import): enforce blocked gate on batch-parsed` / `fix(import): confirm honors payload questions` |
| 4 | 每任务 1 个 | `test(parser): gongzhuan regression case` / `feat(import): three-way cross validation` / `feat(api): group members include requirements` / `feat(ui): shared group renderer` / `refactor(ui): teacher+admin use shared renderer` |
| 5 | 每任务 1 个 | `feat(mineru): layered primary engine` / `feat(ui): answer page shared renderer` / `feat(ui): mobile+tablet shared renderer` / `chore(log): utf8 and rotation` / `docs: rewrite backend README` |
| 6 | 1 个 | `test(e2e): playwright sampling on 9 real specimens` |
| 7 | 每任务 1 个 | `fix(import): group image persistence` / `fix(import): sha256 material reuse key` / `fix(parser): table rows inserted in place` / `fix(parser): material page attribution` / `feat(excel): tolerant column dictionary` / `test(gate): L3 assertions 9-10` |
| 8 | 每批 1 个 | `chore: remove stale debug scripts batch N` |
| 9 | **每步 1 个** | `refactor(import): move <mod> to question_ingest, pure move` |
| 10 | 1 个 | `test(e2e): playwright re-verification after split` |

### 拆分任务的 commit message 附加要求
```
refactor(import): move pdf_reader to question_ingest, pure move

纯移动，零逻辑变更。git diff 显示为纯删除 + 纯新增。
门禁：L0 红线 PASS / L3 落库全绿 / PW-1..12 全绿。
Co-Authored-By: Sisyphus <noreply@opencode.ai>
```

---

## Success Criteria

### 验证命令
```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
cd D:\砺安题库\砺安题库\backend

python scripts/gate_all.py                 # 期望：全层 PASS，退出码 0
python -m pytest backend/tests -q          # 期望：16 failed / 168 passed / 52 errors（集合一致）
Invoke-WebRequest http://localhost:9527/ -UseBasicParsing | Select StatusCode   # 期望：200
$o = (Invoke-WebRequest http://localhost:8000/openapi.json -UseBasicParsing).Content | ConvertFrom-Json
$o.paths.PSObject.Properties.Name | Where-Object { $_ -like "*import*" }        # 期望：端点齐全
(Invoke-WebRequest http://localhost:8000/api/questions/import/mineru-health -UseBasicParsing).Content  # 期望：available=true
```

### 最终检查清单
- [ ] 「确认入库」对 Word/PDF/分离导入**显示真实题数且能成功入库**（RC-2 修复）
- [ ] 上传 6.33 MB docx **全程无「signal is aborted」**（RC-1 修复）
- [ ] 预览中的手工修改**能落库**（RC-3 修复）
- [ ] 建卷路径**不再 500**（RC-4 修复）
- [ ] 申论入库后 `question_bank.requirements` **非空行数 > 0**（RC-5 修复）
- [ ] PDF 改名 `.docx` **仍能解析**（RC-6 修复）
- [ ] 预览页显示**本次实际使用的识别引擎**（RC-7 修复）
- [ ] 申论/复合题在导入预览、教师端、管理员端、学生端**四处形态一致**（RC-8 修复）
- [ ] `question_import.py` 降至 ~900 行 router（RC-9 修复）
- [ ] 复合题材料图片**零裂图**（J-1 修复）
- [ ] 行测资料分析材料块**块内无题号、图片归本块**（J-2 修复）
- [ ] Excel 导入**解析列不丢、丢行有报告**（J-3 修复）
- [ ] 公专 2583 题**逐字段未变**（G1 + E2E-9）
- [ ] `text_parser.py` 的 `extract_question_blocks` **函数体 SHA256 未变**（L0 红线）
- [ ] `.vtj/files/question_import.json` **零改动**
- [ ] `.vtj/vue/question_import.vue` 的 **template 段（1-493 行）零改动**
- [ ] 全部证据含 **文件名 + 大小 + SHA256 + import_id** 四要素
- [ ] F1–F4 全部 APPROVE，且**用户明确同意**

---
