# 题目导入 PDF 图片/重复/串题 三问题修复 + 图片附件 + 真实进度条

## TL;DR

> **Quick Summary**: 修复 PDF 导入链路的三处缺陷（图片从不提取、全文翻倍导致重复题、翻倍导致串题），
> 新增预览态题目贴图能力与真实增量进度条，最后定向删除 10 个 PDF 导入的题目并重导验证。
>
> **Deliverables**:
> - `_extract_text_from_pdf` 表格重复拼接修复（重复题根治）
> - PDF 内嵌图片 → `[IMAGE:...]` 占位符提取，复用 DOCX 已有下游管线
> - 题块内多题号检测 → 标记可疑（主）+ 自动二次切分（辅）
> - `ContentCleaner` 增补水印/页脚/页眉噪声规则
> - 预览卡片「+题干图 / +选项图」上传能力
> - 后端 6 阶段真实进度埋点 + 状态接口扩展 + 前端消费，废除伪造进度条
> - 定向硬删除这 10 个 PDF 导入的题目（决策：甲）
> - 方案同步归档到 `solve_problems_files/`
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: T1 → T3 → T5 → T6 → T7

---

## Context

### Original Request
用户实测题目导入存在三个问题（PDF 来源）：
1. 题目/选项中的图片不显示
2. 同一道题重复出现
3. 一道题吞掉后续多道题

并追加要求：支持更细粒度需求下钻、方案需经其同意后才能实施、统一存档到 `solve_problems_files/`。

### 根因（全部已用硬数据闭合）

| # | 症状 | 根因 | 证据 |
|---|---|---|---|
| 1 | 图片不显示 | `_extract_text_from_pdf()` 只提文本，从不提取 PDF 内嵌图片 | PDF 逐页统计第 6/14/15/16 页共 **19 个图片对象**；`[IMAGE:` 计数 = **0**；10 个 PDF 全为 0 |
| 2 | 重复题 | 同函数内 `extract_text()` 与 `extract_tables()` **内容被重复 append** | 手工逐页 14,436 字 / 70 题号；项目函数 **28,873 字 / 140 题号**，70 个题号各 2 次 |
| 3 | 串题 | #2 的后果：单调性过滤丢弃重复题号，文本却留在块内 | 题块 7/15/23/32/40/**58**/65/68 内含 7~9 个其他题号；题 58 开头即用户报告原文 |

**#2 是最高优先级**：代码级确定性缺陷，单独造成全文翻倍 + 题块污染，修复收益最大、风险最低。

### 现有可复用机制（要求 6「去粗取精」）

下游图片管线**已完备**，PDF 只需产出同样占位符：

| 环节 | 位置 |
|---|---|
| 占位符生成（DOCX） | `_extract_text_from_docx` L745-811 |
| 落盘 | `_compress_and_store` L1495 |
| 占位符回填（**含 options**） | `_extract_and_save_images` L1435-1448 |
| 无关图三级判定 | `image_filters.classify_image` |
| 安全（路径穿越/SSRF/尺寸） | 同上函数 |
| 静态路由 | `main.py` 挂载 `/static/questions` |

异步与状态链路**已存在**：
- `POST /upload` L2682 → 202 + `import_id`，后台任务 `_process_import_async` L2537
- `GET /records/{import_id}/status` L2752 → **无进度字段**

### 用户 5 项决策（已固化）

| # | 决定 | 影响 |
|---|---|---|
| 1 | **甲**：仅删除这 10 个 PDF 导入的题目 | 删除风险从「清空全库」降为「按批次定向」 |
| 2 | **是**：水印/页脚/页眉/选项渲染 4 项全纳入 | 由「待拍板」转「本期必做」 |
| 3 | **需要**：编辑操作中支持添加图片 | 新增 F-6 |
| 4 | **需要**：所有导入都要进度条，**必须真实递增** | 新增 F-7，废除伪造进度条 |
| 5 | **标记可疑为主 + 自动二次切分** | 兜底策略改为人工可见优先 |

### 顺带查实、本期必做（决策 2）

| 问题 | 实测 |
|---|---|
| 水印「小绵羊上岸店」未清除 | 每页 5 次 |
| 页脚「第X页，共Y页」未清除 | 32 处，`ContentCleaner` 清洗后仍 32 处 |
| 页眉「2023年1月7日…（网友回忆版）」未清除 | 每页 1 次 |
| 选项区图片不渲染 | `question_preview_list.vue` L54 纯文本插值（题干 L52 才是 `v-html`） |

---

## Work Objectives

### Core Objective
让 PDF 导入产出的题目**图片可见、无重复、无串题**，并补齐图片附件与真实进度条两项交互能力，
最后定向清理这 10 个 PDF 的存量脏数据供重导。

### Concrete Deliverables
- `backend/app/api/v1/question_import.py`：重复修复、PDF 图片占位符、进度埋点、状态字段、贴图接口
- `backend/app/services/text_parser.py`：噪声规则、串题检测与标记
- `backend/app/models/models.py` + 新增迁移脚本：进度列
- `.vtj/vue/question_preview_list.vue`：选项 `v-html`、可疑高亮、贴图按钮
- `.vtj/vue/question_import.vue`：进度条消费真实进度
- `solve_problems_files/`：归档本方案

### Definition of Done
- [ ] 目标 PDF 提取字数从 28,873 回落至 ≈14,436，题号 70 个且无重复
- [ ] 目标 PDF 题块内含 ≥2 个题号前缀的数量 = 0
- [ ] 目标 PDF 19 张图经 `classify_image` 判定后真题图 URL 返回 200，题干图进 `question_content`、选项图进 `options`
- [ ] 预览页题干图与选项图均可见；控制台零报错
- [ ] 10 个 PDF 回归题块数不减少、污染数 0
- [ ] 30 份 DOCX 回归仍 PASS、题块 2899 不变、污染 0
- [ ] 进度条随阶段真实递增，无跳变
- [ ] VTJ `vtj_check_consistency` 无不一致；SFC 编译 `OK bad=0`
- [ ] 改动文件 `git diff --numstat` 与 `--ignore-cr-at-eol --numstat` 完全一致

### Must Have
- 复用已有图片管线，**不新建**图片机制
- PDF 与 DOCX 走同一进度协议
- 进度写 DB 而非内存（多 worker / `--reload` 安全）
- 贴图走 `_compress_and_store` 复用安全防护
- 删除前先备份，删除范围严格限定这 10 个 PDF

### Must NOT Have（护栏）
- ❌ 不得禁用/删除 `extract_tables()`（会丢表格题）——只能改触发条件
- ❌ 不得放宽 `extract_question_numbers` 的 monotonic 约束（会引入幽灵题）
- ❌ 不得重启已运行的前后端服务（用户明确要求复用现有端口）
- ❌ 不得硬编码图片 URL 或绕过 `sanitizeHtml`
- ❌ 不得清空全库（决策 1 为「甲」）
- ❌ 不得遗留行尾符噪声（EOL 污染）
- ❌ 不得改动教师端 P0-P5 已完成功能

### Spec Framework Integration
未检测到 SDD 框架（非 OpenSpec / 非 Spec Kit）。按 `CLAUDE.md/Opencode执行命令工作流.md` +
`CLAUDE.md/vtj.md` 执行，VTJ 改动须走 `vtj-mcp-server` 并同步 DSL。

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — 全部由 agent 执行验证。

### Test Decision
- **基础设施存在**: YES（pytest + Playwright 已在前序轮次验证可用）
- **自动化测试**: Tests-after（改动集中在既有解析链路，回归优先于新增单测）
- **框架**: pytest（后端）+ Playwright（前端）+ curl（API）
- **基线纪律**: 改动前必须先跑 30 DOCX 回归与 HEAD 基线对比并记录数值，改动后逐项比对

### QA Policy
每个任务必须含 ≥1 happy path + ≥1 failure/edge 场景，证据落 `.omo/evidence/task-{N}-*.{ext}`。
- **后端解析**: Bash（python 脚本调真实函数，断言字符数/题号/落盘文件）
- **API**: Bash（curl 打真实端口 8000，断言状态码与字段）
- **前端 UI**: Playwright（复用已在运行的 9527，断言 DOM + 截图）
- **数据库**: Bash（sqlite3 查询断言行数与字段）

---

## Execution Strategy

### Parallel Execution Waves

> 按**文件冲突**划分并行流：同一文件的任务必须串行，不同文件的任务并行。
> `question_import.py` 与 `text_parser.py` 各为单流，天然串行；跨文件任务并行。

```
Wave 1 (并行 3):
├── T1: text_parser.py 噪声规则（水印/页脚/页眉）      [unspecified-high]
├── T2: question_import.py 提取层（重复修复 + PDF 图片占位符） [unspecified-high]
└── T3: models.py 进度列 + 幂等迁移脚本                [quick]

Wave 2 (并行 2):
├── T4: question_import.py 接口层（进度埋点 + 状态字段 + 贴图接口）  [deep]
└── T5: text_parser.py 串题检测 + 标记可疑 + 二次切分  [unspecified-high]

Wave 3 (并行 2):
├── T6: question_preview_list.vue（选项 v-html + 可疑高亮 + 贴图按钮） [visual-engineering]
└── T7: question_import.vue（进度条消费真实进度）        [visual-engineering]

Wave 4 (串行 2):
├── T8: 集成回归（10 PDF + 30 DOCX + 基线比对）
└── T9: 定向硬删除 10 PDF 题目 + 重导验证

Wave FINAL (并行 4):
├── F1: 方案合规审计 (oracle)
├── F2: 代码质量审查 (unspecified-high)
├── F3: 真实手工 QA (unspecified-high)
└── F4: 范围保真核查 (deep)
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|---|---|---|
| T1 | — | T5, T8 |
| T2 | — | T4, T8 |
| T3 | — | T4 |
| T4 | T2, T3 | T7, T8 |
| T5 | T1 | T6, T8 |
| T6 | T5 | T8 |
| T7 | T4 | T8 |
| T8 | T1,T2,T4,T5,T6,T7 | T9 |
| T9 | T8 | — |

### Agent Dispatch Summary

- **Wave 1**: T1 → `unspecified-high` | T2 → `unspecified-high` | T3 → `quick`
- **Wave 2**: T4 → `deep` | T5 → `unspecified-high`
- **Wave 3**: T6 → `visual-engineering` | T7 → `visual-engineering`
- **Wave 4**: T8 → `unspecified-high` | T9 → `unspecified-high`
- **FINAL**: F1 → `oracle` | F2 → `unspecified-high` | F3 → `unspecified-high` | F4 → `deep`

---

## TODOs

> 任务标签使用裸数字格式（`1.`、`2.`），Final Wave 使用 `F1.` 格式。

- [x] 1. ContentCleaner 增补水印/页脚/页眉噪声规则

  **What to do**:
  - 在 `backend/app/services/text_parser.py` 的 `ContentCleaner` 中新增三类噪声过滤：
    - **页脚**：正则 `第\s*\d+\s*页[，,]\s*共\s*\d+\s*页`，整行匹配即删
    - **水印**：整行为同一词重复（如「小绵羊上岸店 小绵羊上岸店」）且不含题号前缀/选项标记（`A.`–`D.`）即删
    - **页眉**：短行（≤ `HEADER_FOOTER_MAX_LENGTH`）且与文档标题高度相似（重复出现 ≥3 次），首次出现保留、后续删除
  - 必须挂在 **Phase1 噪声过滤** 的最前，确保页脚在题号行首判定之前被剔除
  - 不得放宽 `HEADER_FOOTER_THRESHOLD` / `HEADER_FOOTER_MAX_LENGTH` 现有语义

  **Must NOT do**:
  - 不得删除含题号或选项标记的行（会误删真题）
  - 不得改动 `extract_question_numbers` 的 monotonic 逻辑

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需精读 `ContentCleaner` 多阶段结构并插入不破坏既有判定顺序的规则
  - **Skills**: `[]` — 纯 Python 字符串处理，无领域技能重叠

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T2、T3 并行）
  - **Blocks**: T5, T8
  - **Blocked By**: None

  **References**:
  - `backend/app/services/text_parser.py` — `ContentCleaner.clean()` / Phase1 / Phase2 三阶段顺序；新规则必须插在 Phase1 最前，否则页脚会先污染题号行首判定
  - `HEADER_FOOTER_THRESHOLD` / `HEADER_FOOTER_MAX_LENGTH` — 现有页眉页脚判定阈值，不要重定义，只复用其长度语义
  - `backend/app/api/v1/question_import.py` L836-900 `_extract_text_from_pdf` — 页脚/水印/页眉的**产生源**，用于确认噪声形态

  **WHY Each Reference Matters**:
  - `ContentCleaner` 阶段顺序决定了规则插入位置；插错阶段会导致「已清洗但仍残留 32 处页脚」这类既有失败
  - 阈值常量决定页眉判定是否会误伤正常题干行，必须先理解再复用

  **Acceptance Criteria**:
  - [ ] 目标 PDF 经 `ContentCleaner.clean_text()` 后：
    - [ ] `第X页，共Y页` 匹配数 = **0**（当前 32）
    - [ ] `小绵羊上岸店` 匹配数 = **0**（当前每页 5 次）
    - [ ] `（网友回忆版）` 页眉匹配数 ≤ 1（首次保留）
  - [ ] 30 份 DOCX 回归：题块总数仍为 **2899**，污染数 **0**
  - [ ] pytest 无新增失败

  **QA Scenarios**:
  ```
  Scenario: 噪声被清除且题目不丢
    Tool: Bash (python)
    Preconditions: 目标 PDF 在题目目录；30 DOCX 语料就位
    Steps:
      1. 调 _extract_text_from_pdf() 得 raw；对 raw 调 ContentCleaner.clean_text() 得 clean
      2. 断言 re.search(r'第\s*\d+\s*页[，,]\s*共\s*\d+\s*页', clean) is None
      3. 断言 '小绵羊上岸店' not in clean
      4. 断言 '（网友回忆版）' 在 clean 中出现次数 <= 1
      5. 跑 30 DOCX 回归脚本，断言题块数 == 2899 且污染数 == 0
    Expected Result: 全部断言通过
    Failure Indicators: 页脚/水印仍残留，或 DOCX 题块数变化（说明误删了正文）
    Evidence: .omo/evidence/task-1-noise-clean.txt

  Scenario: 边缘输入不被误删（负向）
    Tool: Bash (python)
    Preconditions: 构造含「参见第3页，第4页」等正文表述的样本字符串
    Steps:
      1. 构造 sample = '1. 参见第3页的内容与第4页对照，本题选A。'
      2. 调 ContentCleaner().clean_text(sample)
      3. 断言 '参见第3页的内容与第4页对照' 仍完整保留（未被页脚正则误伤）
      4. 断言结果中不含 'A.' 被误删
    Expected Result: 正文完整保留
    Failure Indicators: 正文被截断或选项行被删除
    Evidence: .omo/evidence/task-1-noise-clean-error.txt
  ```

  **Commit**: YES
  - Message: `fix(parser): 增补水印页脚页眉噪声规则`
  - Files: `backend/app/services/text_parser.py`

- [x] 2. 修复 PDF 表格重复拼接 + 新增 PDF 图片占位符提取

  **What to do**:
  - **步骤 A｜根治重复（最高优先级）**：修改 `question_import.py` L863-879 的 pdfplumber 分支。
    当前 `extract_text()` 与 `extract_tables()` 的结果都被 append 进 `parts`，导致全文翻倍。
    改为：**仅当 `extract_text()` 为空时才启用表格提取**；两者都有内容时，
    对表格行做「是否已存在于本页文本」的归一化比对，已存在则跳过。
  - **步骤 B｜安全网**：`_finish()` 前增加相邻重复块折叠——若 `parts` 中存在归一化后相同、
    且仅隔 1 个短行的相邻块，丢弃后者。
  - **步骤 C｜PDF 图片占位符**：新增内部函数 `_extract_pdf_images_markers(buf)`，
    遍历 `page.images`，按图片 `top` 坐标把 `[IMAGE:pdf_{session}_{page}_{seq}]`
    插入到最接近的文本行之后，使占位符随该行进入 `question_content` 或 `options`。
    复用现有 `_session_id` 机制与 `img_pdf_` 文件名前缀族。

  **Must NOT do**:
  - ❌ 不得删除或注释掉 `extract_tables()` 调用（会丢表格题），只能改触发条件
  - ❌ 不得新建图片 URL 机制，必须产出与 DOCX 同构的 `[IMAGE:...]` 占位符
  - ❌ 不得绕过 `image_filters.classify_image` 与 `_compress_and_store`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需在保留表格题能力的前提下消除翻倍，并新增坐标锚定逻辑
  - **Skills**: `[]` — pdfplumber 坐标 API 无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T1、T3 并行）
  - **Blocks**: T4, T8
  - **Blocked By**: None

  **References**:
  - `backend/app/api/v1/question_import.py` L863-879 — **缺陷精确位置**：`extract_text()` 与 `extract_tables()` 双 append
  - `backend/app/api/v1/question_import.py` L745-811 `_extract_text_from_docx` — 占位符格式 `[IMAGE:{session}_{qn}_{seq}]` 的**权威参考**，PDF 必须产出同构格式
  - `backend/app/api/v1/question_import.py` L1435-1448 `_extract_and_save_images` — 下游回填入口，docstring 明确「支持 options 中的 [IMAGE:xxx] 占位符替换为真实 `<img>`」
  - `backend/app/api/v1/question_import.py` L1495 `_compress_and_store` — 落盘函数，含路径穿越防护与 SSRF 检测
  - `backend/app/services/image_filters.py` `classify_image` — 三级 block/suspect/keep 判定，PDF 图片同样受此过滤
  - `backend/app/api/v1/question_import.py` L1476 — DOCX 图片暂存目录注释，说明暂存目录约定

  **WHY Each Reference Matters**:
  - L745-811 是**唯一权威的占位符格式来源**；格式不一致会导致 `_extract_and_save_images` 的
    `marker_pattern`（L1609 正则 `[a-f0-9]+_\d+_\d+|\d+_\d+`）匹配不上，图片静默丢失
  - L1609 的正则决定了 `pdf_{session}_{page}_{seq}` 中的 session 必须是十六进制可匹配形态，需核对
  - L1435-1448 已覆盖 options，这是 PDF 选项图能落地的前提，无需改动

  **Acceptance Criteria**:
  - [ ] 目标 PDF `_extract_text_from_pdf()` 输出从 **28,873** 字符回落至 **≈14,436**
  - [ ] 该 PDF 行首题号从 **140** 降至 **70**，且 70 个题号**各出现 1 次**
  - [ ] 该 PDF `[IMAGE:` 占位符数 **> 0**（当前 0）
  - [ ] 10 个 PDF 全部回归：**题块数不减少**（表格题未丢失）
  - [ ] PDF 提取后**必须清空文本缓存**再验证，否则命中旧缓存导致结果失真

  **QA Scenarios**:
  ```
  Scenario: 重复消除且图片占位符生成（happy path）
    Tool: Bash (python)
    Preconditions: 已清空 PDF 文本缓存；目标 PDF 就位
    Steps:
      1. raw = _extract_text_from_pdf(open(pdf,'rb').read())
      2. 断言 len(raw) 在 [14000, 15000] 区间（当前 28873）
      3. nums = extract_question_numbers(raw, monotonic=False)
      断言 len(nums) == 70 且 len(set(nums)) == 70（当前 140/70）
      4. 断言 raw.count('[IMAGE:') > 0（当前 0）
      5. 断言 raw 中 '第X页，共Y页' 已无残留
    Expected Result: 字数回落约一半、题号无重复、图片占位符存在
    Failure Indicators: 字数仍为 28873 说明步骤 A 未生效；占位符为 0 说明步骤 C 未生效
    Evidence: .omo/evidence/task-2-dedup-image.txt

  Scenario: 表格题不丢失（负向回归）
    Tool: Bash (python)
    Preconditions: 10 个 PDF 语料就位
    Steps:
      1. 改动前先记录 10 个 PDF 的题块数基线（若基线不存在，先 git stash 取改动前数值）
      2. 改动后重跑 10 个 PDF，逐个断言题块数 >= 基线值
      3. 特别检查含表格版面的 PDF，其表格单元格文本未丢失
    Expected Result: 无任何 PDF 题块数减少
    Failure Indicators: 任一 PDF 题块数下降 → 表格提取被误禁用
    Evidence: .omo/evidence/task-2-dedup-image-error.txt
  ```

  **Commit**: YES
  - Message: `fix(import): 修复 PDF 表格重复拼接并新增图片占位符提取`
  - Files: `backend/app/api/v1/question_import.py`

---

- [x] 3. QuestionImportRecord 增加进度列与幂等迁移脚本

  **What to do**:
  - 在 `backend/app/models/models.py` 的 `QuestionImportRecord` 增加两列：
    ```python
    progress_percent = Column(Integer, default=0, comment="解析进度 0-100")
    current_phase     = Column(String(50), comment="当前阶段标识")
    ```
  - 新增幂等迁移脚本 `backend/migrations/add_import_progress.py`：
    先 `PRAGMA table_info(question_import_record)` 判存在性，再决定是否 `ALTER TABLE ADD COLUMN`
  - 同步更新建表定义（`scripts/init_db.py` 或等价文件），保证新库直接带这两列
  - **执行迁移前后各做一次数据库备份**

  **Must NOT do**:
  - 不得用 DROP/CREATE 方式重建表
  - 不得跳过备份直接迁移

  **Recommended Agent Profile**:
  - **Category**: `quick` — 两列 + 一个幂等 ALTER 脚本，机械且有明确验证方式
  - **Skills**: `[]` — SQLite DDL 无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1（与 T1、T2 并行）
  - **Blocks**: T4
  - **Blocked By**: None

  **References**:
  - `backend/app/models/models.py` `class QuestionImportRecord` — 现有列清单，确认**无** progress 类字段，勿重复添加
  - `backend/app/api/v1/question_import.py` L2752 `get_import_parse_status` — 消费方，后续 T4 在此读新列
  - `backend/app/api/v1/question_import.py` L2537 `_process_import_async` — 消费方，后续 T4 在此写新列
  - `backend/data/question_bank.db` — 迁移目标库

  **WHY Each Reference Matters**:
  - 需先确认列确实不存在，避免与历史迁移重复
  - 两个消费方决定了列的类型与取值范围（`progress_percent` 必须能存 0-100 整数）

  **Acceptance Criteria**:
  - [ ] `PRAGMA table_info(question_import_record)` 包含 `progress_percent` 与 `current_phase`
  - [ ] 迁移脚本**重复执行两次不报错**（幂等）
  - [ ] `PRAGMA integrity_check` = `ok`
  - [ ] 迁移前后 `question_bank` 表行数一致（数据未丢）
  - [ ] 迁移前已生成数据库备份并记录 SHA256

  **QA Scenarios**:
  ```
  Scenario: 迁移成功且幂等（happy path）
    Tool: Bash (sqlite3 / python sqlite3)
    Preconditions: 已完成数据库备份
    Steps:
      1. 记录迁移前 question_bank 行数 N0
      2. 执行迁移脚本第 1 次，断言退出码 0
      3. 执行迁移脚本第 2 次，断言退出码 0（幂等验证）
      4. PRAGMA table_info 断言两列均存在
      5. 断言迁移后 question_bank 行数 == N0
      6. PRAGMA integrity_check 断言 == 'ok'
    Expected Result: 两次执行均成功，列存在，数据行数不变
    Failure Indicators: 第二次执行报 "duplicate column" → 脚本非幂等
    Evidence: .omo/evidence/task-3-migration.txt

  Scenario: 迁移不丢数据（负向）
    Tool: Bash (python sqlite3)
    Preconditions: 库中存在题目数据
    Steps:
      1. 迁移前抽取 5 条 question_id 与题干摘要作为指纹
      2. 执行迁移
      3. 迁移后按同样 question_id 复查，断言题干摘要逐条一致
    Expected Result: 5 条指纹全部一致
    Failure Indicators: 任一条不匹配 → 迁移破坏了数据
    Evidence: .omo/evidence/task-3-migration-error.txt
  ```

  **Commit**: YES
  - Message: `feat(import): 导入记录增加进度字段与幂等迁移脚本`
  - Files: `backend/app/models/models.py`, `backend/migrations/add_import_progress.py`, 建表脚本

- [x] 4. 后台解析 6 阶段真实进度埋点 + 状态接口扩展 + 预览态贴图接口

  **What to do**:
  - **步骤 A｜进度埋点**：在 `_process_import_async` (L2537) 内按真实阶段上报，
    **每阶段结束即写库**，循环内逐项推进：

    | 阶段 | `current_phase` | 进度 | 真实依据 |
    |---|---|---|---|
    | ① 文件读取 | `READING` | 5 | 文件流读取完成 |
    | ② 文本提取 | `EXTRACTING` | 10→45 | **PDF 逐页循环内每页 +4%** |
    | ③ 图片提取落盘 | `IMAGES` | 45→60 | **每张图 +1.5%** |
    | ④ 题目切分 | `SPLITTING` | 60→75 | `extract_question_blocks` 返回后 |
    | ⑤ 答案匹配 | `MATCHING` | 75→90 | `smart_match_questions_answers` 返回后 |
    | ⑥ 预览构建 | `BUILDING` | 90→100 | `preview_data` 写库后置 100 |

    > ②③ 是**循环内逐项推进**，这是「随时变动」的关键：260s 扫描件也能看到进度平滑爬升。
  - **步骤 B｜状态接口**：`GET /records/{import_id}/status` (L2752) 响应新增
    `progress_percent` 与 `current_phase` 两个字段。
  - **步骤 C｜贴图接口**：新增 `POST /import-records/{import_id}/attach-image`，
    入参 `file` / `target`(`content`|`option`) / `option_key` / `question_index`。
    走 `_compress_and_store(data, 'img_attach_', idx, ext)` 落盘，
    把 `<img src="/static/questions/...">` 插入 `question_content` 末尾或对应 option 的 `value` 末尾，
    回写 `preview_data` 并 commit，返回 `{path, url, question_index, target, option_key}`。

  **Must NOT do**:
  - ❌ 不得把进度存在模块内存字典（多 worker / uvicorn `--reload` 会丢）
  - ❌ 不得用定时器或固定百分比伪造进度
  - ❌ 不得绕过 `_compress_and_store`（会丢路径穿越防护与 SSRF 检测）
  - ❌ 不得改动 `import_status` 枚举现有取值

  **Recommended Agent Profile**:
  - **Category**: `deep` — 需在既有异步任务中插入 6 阶段埋点并新增接口，涉及 DB 写入时机与事务边界
  - **Skills**: `[]` — FastAPI BackgroundTasks 与 SQLAlchemy 无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 T5 并行；同文件但 T5 改 text_parser.py 无冲突）
  - **Blocks**: T7, T8
  - **Blocked By**: T2, T3

  **References**:
  - `backend/app/api/v1/question_import.py` L2537 `_process_import_async` — **埋点位置**，六阶段对应函数调用点
  - `backend/app/api/v1/question_import.py` L2682 `upload_file_for_import` — 202 返回体与 `import_id` 来源，T7 依赖此契约
  - `backend/app/api/v1/question_import.py` L2752 `get_import_parse_status` — 响应体扩展点；注意 L2800-2802 注释记录了历史双重编码坑，扩展时不要破坏 `load_json_lenient` 兼容逻辑
  - `backend/app/api/v1/question_import.py` L1495 `_compress_and_store` — 贴图接口落盘复用
  - `backend/app/api/v1/question_import.py` L1435-1448 `_extract_and_save_images` — 确认 URL 形态为 `/static/questions/{qid}/{filename}`
  - `backend/app/models/models.py` `QuestionImportRecord` — T3 新增的两列
  - `.vtj/vue/question_import.vue` L761 — 前端伪造进度条位置，T7 需删除

  **WHY Each Reference Matters**:
  - `_process_import_async` 是**唯一**能拿到真实阶段边界的地方，在外层埋点拿不到细粒度
  - L2800-2802 的 `load_json_lenient` 是踩过坑的兼容代码，改响应结构时容易连带破坏历史记录读取
  - L761 的伪造进度条是用户明确点名的问题（「突然就完成」），T7 必须删除该行

  **Acceptance Criteria**:
  - [ ] 上传 PDF 后轮询状态接口，`progress_percent` 呈**多段递增**（至少出现 5 个不同数值），非 0→100 跳变
  - [ ] `current_phase` 依次经过 `READING`→`EXTRACTING`→`IMAGES`→`SPLITTING`→`MATCHING`→`BUILDING`
  - [ ] 状态接口返回体含 `progress_percent` 与 `current_phase`
  - [ ] `POST /import-records/{import_id}/attach-image` 传 `target=content` 成功，题干末尾出现 `<img>`
  - [ ] 同一接口传 `target=option` + `option_key=B` 成功，对应选项 `value` 末尾出现 `<img>`
  - [ ] 贴图后 `GET /records/{import_id}/status` 的 `result.questions[index]` 已含该 `<img>`
  - [ ] 旧记录（无进度列值的 `NULL`）查询状态接口不报错，返回 0

  **QA Scenarios**:
  ```
  Scenario: 进度真实递增（happy path）
    Tool: Bash (curl)
    Preconditions: 后端已在 8000 运行；已登录取 token
    Steps:
      1. curl -X POST /api/question-import/upload 传目标 PDF，断言 202 且返回 import_id
      2. 循环 curl GET /records/{import_id}/status，每 600ms 采样一次 progress_percent
      3. 收集全部采样值，断言去重后不同数值个数 >= 5
      4. 断言采样值单调不减，且最终到达 100
      5. 断言采样到的 current_phase 集合包含 EXTRACTING 与 SPLITTING
    Expected Result: 进度多段平滑递增，非 0→100 跳变
    Failure Indicators: 去重后数值 <= 2 → 埋点缺失，仍是跳变
    Evidence: .omo/evidence/task-4-progress.txt

  Scenario: 贴图接口与非法入参（负向）
    Tool: Bash (curl)
    Preconditions: 已有 PREVIEW 状态的 import_id
    Steps:
      1. 传合法 png + target=content，断言 200 且返回 url 以 /static/questions/ 开头
      2. 断言该 url curl 返回 200 且 Content-Type 为图片
      3. 传 target=option 但省略 option_key，断言返回 4xx 且 detail 含明确错误信息
      4. 传 .txt 文件，断言 4xx（类型白名单生效）
      5. 传不存在的 question_index=99999，断言 4xx 且不产生脏数据
    Expected Result: 合法请求成功，非法请求 4xx 且错误信息明确
    Failure Indicators: 非法请求返回 200，或错误被静默吞掉
    Evidence: .omo/evidence/task-4-attach-image-error.txt
  ```

  **Commit**: YES
  - Message: `feat(import): 后台解析六阶段真实进度埋点与预览态贴图接口`
  - Files: `backend/app/api/v1/question_import.py`

---

- [x] 5. 串题检测：标记可疑为主 + 自动二次切分为辅

  **What to do**:
  - 在 `text_parser.py` 的 `extract_question_blocks` 切分完成后，对**每个题块**做「块内题号前缀检测」：
    统计块内出现 ≥2 个独立题号前缀（`^\s*\d+[．.、]` 形态）的情况
  - **主策略（标记可疑）**：命中时给题块打 `suspicious=True` 与 `suspicious_reason='内含多个题号前缀'`
  - **辅策略（自动二次切分）**：仅当二次切分能产出**语义完整**的子块时执行，
    否则保持原块 + 标记可疑（宁可标记也不错误切分）
  - 标记字段需能通过预览接口透传到前端（确认 `preview_data` 的 questions 项结构是否需增字段）

  **Must NOT do**:
  - ❌ 不得放宽 `extract_question_numbers` 的 monotonic 约束（会引入幽灵题，
    此前已因 monotonic 修过一次「2017国考第100题」问题）
  - ❌ 不得因二次切分丢失题干内容
  - ❌ 不得把可疑标记当作错误静默丢弃题目

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需精读既有切分逻辑与判断题修复，在不破坏 monotonic 的前提下加检测层
  - **Skills**: `[]` — 纯文本切分逻辑

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2（与 T4 并行，不同文件）
  - **Blocks**: T6, T8
  - **Blocked By**: T1

  **References**:
  - `backend/app/services/text_parser.py` `extract_question_blocks` — 主切分函数，检测层挂在此处之后
  - `backend/app/services/text_parser.py` `extract_question_numbers(monotonic=...)` — **禁止放宽**；其注释记录了 monotonic 修复历史
  - `backend/app/api/v1/question_import.py` L3136 `/parse` 与 L2097 `/batch-parsed` — 预览数据出口，确认 questions 项字段结构
  - 目标 PDF 实测基线 — 题块 7/15/23/32/40/58/65/68 内含 7~9 个其他题号；修复后应为 0

  **WHY Each Reference Matters**:
  - `extract_question_numbers` 的 monotonic 注释是**血泪教训**，放宽会重引入幽灵题
  - 两个预览出口决定 `suspicious` 字段能否透传到前端，T6 依赖此契约

  **Acceptance Criteria**:
  - [ ] 目标 PDF 切分后，**含 ≥2 个题号前缀的题块数 = 0**
  - [ ] 30 份 DOCX 回归：题块总数仍 **2899**，污染数 **0**（检测层不得误伤正常题）
  - [ ] 正常题块**不出现** `suspicious=True`（误报率控制）
  - [ ] `suspicious` 字段出现在预览接口返回的 questions 项中

  **QA Scenarios**:
  ```
  Scenario: 串题被检出并标记（happy path）
    Tool: Bash (python)
    Preconditions: 目标 PDF；T2 的重复修复已生效
    Steps:
      1. raw = _extract_text_from_pdf(pdf_bytes)
      2. blocks = extract_question_blocks(raw)
      3. 对每块统计 r'^\s*\d+[．.、]' 匹配数，断言全部 == 1
      4. 断言无块同时含 '二. 多项选择题' 与 ≥2 个题号前缀
      5. 断言 len(blocks) 与题号最大值一致（70 题 → 70 块，题号连续）
    Expected Result: 无吞题，题块与题号一一对应
    Failure Indicators: 仍有块含多个题号 → 重复修复未生效
    Evidence: .omo/evidence/task-5-suspicious.txt

  Scenario: 正常题不被误标（负向）
    Tool: Bash (python)
    Preconditions: 30 DOCX 语料
    Steps:
      1. 跑 30 DOCX 回归，断言题块总数 == 2899
      2. 统计 suspicious=True 的块数，断言 == 0（或 < 总块数 1%）
      3. 抽查 10 个被判正常的块，断言题干首尾连贯未被截断
    Expected Result: 零误伤
    Failure Indicators: suspicious 数量异常高 → 块内题号正则过宽
    Evidence: .omo/evidence/task-5-suspicious-error.txt
  ```

  **Commit**: YES
  - Message: `fix(parser): 新增串题检测与可疑标记`
  - Files: `backend/app/services/text_parser.py`

- [x] 6. 预览卡片改造：选项 v-html + 可疑高亮 + 贴图按钮

  **What to do**:
  - **选项区渲染**：`.vtj/vue/question_preview_list.vue` L53-54 由纯文本插值
    `{{ opt.key }}. {{ opt.value }}` 改为 `v-html="renderQuestionContent(opt.value)"`，
    保持 `opt.key` 仍由模板单独输出。`renderQuestionContent` 自带 `sanitizeHtml`，安全性与题干同级。
  - **可疑高亮**：题目卡片读取 `q.suspicious`，为真时加高亮边框 + 「疑似串题」角标 + 原因提示
  - **贴图按钮**：每张卡片与上一轮「删除」按钮并列新增
    - 「+ 题干图」→ 选图 → 上传 → 题干末尾立即出现图片
    - 每个选项行右侧「+ 图」小按钮 → 上传 → 该选项末尾出现图片
    - 上传中按钮 loading 并禁用；失败用 `ElMessage.error` 提示，不静默失败
  - 上传成功后**用返回的 `question_index` 就地更新本地数组**，不重新拉整个预览（避免丢失用户已做编辑）
  - 改完执行 `vtj_sync_vue_to_dsl` 并跑 `vtj_check_consistency`

  **Must NOT do**:
  - ❌ 不得改 `<template>` 以外的既有业务逻辑（除贴图相关新增）
  - ❌ 不得重新拉取预览覆盖用户编辑
  - ❌ 不得新增未经 `sanitizeHtml` 的渲染入口
  - ❌ 不得破坏上一轮已实现的逐题删除功能

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — 三处 UI 改造（v-html 渲染、高亮态、异步按钮态）需保证视觉与交互一致
  - **Skills**: `[]` — VTJ 组件改动按 `vtj.md` 规范执行，无需额外技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3（与 T7 并行，不同文件）
  - **Blocks**: T8
  - **Blocked By**: T5

  **References**:
  - `.vtj/vue/question_preview_list.vue` L52 — 题干区 `v-html="renderQuestionContent(q.question_content)"`，**选项区改造须与之对齐**
  - `.vtj/vue/question_preview_list.vue` L53-54 — 待改造的选项区，当前 `{{ opt.key }}. {{ opt.value }}`
  - `src/utils/questionRender.js` `renderQuestionContent` — 复用此函数完成占位符→`<img>` 转换，**不要另写渲染逻辑**
  - `.vtj/vue/question_preview_list.vue` 上一轮新增的删除按钮 — 贴图按钮须与其并列，保持同一交互风格
  - `CLAUDE.md/vtj.md` + `vtj-mcp-server` — raw VTJ 页面改动规范与 DSL 同步流程
  - `backend/app/api/v1/question_import.py` 贴图接口（T4 新增）— 前端调用契约：`{path, url, question_index, target, option_key}`

  **WHY Each Reference Matters**:
  - L52 是同一文件内已验证可渲染图片的写法，选项区照抄即可保证一致
  - `renderQuestionContent` 已封装 sanitize，绕过它等于引入 XSS
  - 删除按钮是上一轮成果，贴图按钮需与其视觉对齐，否则卡片控件风格割裂

  **Acceptance Criteria**:
  - [ ] 含图片的选项在预览卡片中**可见**，且不显示 `<img` 源码文本
  - [ ] `suspicious=True` 的卡片显示「疑似串题」角标与高亮边框
  - [ ] 点击「+ 题干图」上传后图片立即出现，无需刷新页面
  - [ ] 点击选项「+ 图」上传后图片挂在**正确选项**上（验证 A 图不会挂到 B）
  - [ ] 上传失败时弹出错误提示，不静默
  - [ ] 逐题删除功能仍正常
  - [ ] `vtj_check_consistency` 无不一致；SFC 编译 `OK bad=0`
  - [ ] 控制台零报错

  **QA Scenarios**:
  ```
  Scenario: 选项图与题干图均可见（happy path）
    Tool: Playwright
    Preconditions: 复用已在运行的 9527 前端与 8000 后端（**不重启**）
    Steps:
      1. 导航到题目导入页，上传目标 PDF
      2. 等待进度条到达 100% 并进入预览
      3. 定位含图片的题卡，断言 .docs-q-content 内存在可见 <img> 且 naturalWidth > 0
      4. 断言 .docs-q-options 内存在可见 <img> 且 naturalWidth > 0
      5. 断言页面文本中不含字面量 '<img src=' （未被当作文本显示）
      6. 断言控制台无 error
      7. 截图保存
    Expected Result: 题干图与选项图都真实渲染
    Failure Indicators: 出现 '<img src=' 字面量 → 选项区未改 v-html
    Evidence: .omo/evidence/task-6-preview-render.png

  Scenario: 贴图与误标高亮（负向）
    Tool: Playwright
    Preconditions: 预览页已加载
    Steps:
      1. 对第 1 题点击「+ 题干图」，选择一张 > 5MB 的非法大图
      2. 断言出现 ElMessage 错误提示，且该题题干未出现新图片
      3. 断言卡片内容未被清空（编辑未丢失）
      4. 断言可疑题卡显示角标文字「疑似串题」
      5. 断言正常题卡不显示该角标
    Expected Result: 失败有明确提示，数据未损坏
    Evidence: .omo/evidence/task-6-preview-render-error.png
  ```

  **Commit**: YES
  - Message: `feat(import): 预览卡片支持选项图渲染与题干贴图`
  - Files: `.vtj/vue/question_preview_list.vue`, `.vtj/files/question_preview_list.json`

---

- [x] 7. 前端进度条消费真实进度并废除伪造进度

  **What to do**:
  - **删除伪造进度**：移除 `question_import.vue` L761 的
    `self.setProgress(0, Math.min(45, 10 + Math.round(waited / 4000)))` 定时器
  - **改为真实轮询**：上传成功后按 `import_id` 轮询 `GET /records/{import_id}/status`（间隔 600ms），
    把 `progress_percent` 直接赋给已有的 `state.progressPercent`
  - **步骤映射**：把 `current_phase` 映射到 `state.progressSteps` 的 6 个标签：
    读取文件 / 提取文本 / 提取图片 / 切分题目 / 匹配答案 / 构建预览
  - `status` 变为 `PREVIEW` 时停止轮询并置 100
  - **保留** `state.importProgress` 旧字段做兼容，避免其他页面回归
  - **组件卸载时必须 `clearInterval`**，防止轮询泄漏
  - **PDF 与 DOCX 走同一协议**（用户要求「所有题目进行导入都要设置进度条」）
  - OCR 阶段（>60s 无进展）在 ①~③ 完成前显示「扫描件识别中，请稍候」文案，避免用户以为卡死

  **Must NOT do**:
  - ❌ 不得保留任何定时器伪造的百分比
  - ❌ 不得在组件卸载后继续轮询
  - ❌ 不得删除 `state.importProgress`（其他页面可能依赖）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — 轮询生命周期管理 + 六步骤状态映射 + 长耗时文案
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3（与 T6 并行，不同文件）
  - **Blocks**: T8
  - **Blocked By**: T4

  **References**:
  - `.vtj/vue/question_import.vue` L761 — **必须删除的伪造进度行**（`Math.min(45, waited/4000)`）
  - `.vtj/vue/question_import.vue` L18-32 — 步骤条 UI（`state.progressSteps` / `progressPercent` 渲染）
  - `.vtj/vue/question_import.vue` L555-557 — `progressPhase` / `progressPercent` / `progressSteps` state 定义
  - `.vtj/vue/question_import.vue` L340, L344-345, L529 — 旧 `state.importProgress` 进度条，需保留兼容
  - `backend/app/api/v1/question_import.py` L2752 `get_import_parse_status` — 轮询契约，T4 新增两字段
  - `backend/app/api/v1/question_import.py` L2682 `upload_file_for_import` — 202 响应返回 `import_id` 的位置

  **WHY Each Reference Matters**:
  - L761 是用户明确点名的问题（「突然就完成进度」），不删则需求 4 未达成
  - L555-557 已有 `progressSteps` 结构，无需新建 state，只需喂真实值
  - L2682 的响应体决定轮询从哪拿 `import_id`

  **Acceptance Criteria**:
  - [ ] L761 伪造进度代码已删除
  - [ ] 上传任一 PDF，进度条**至少出现 5 个不同数值**且单调不减
  - [ ] 6 个步骤标签随 `current_phase` 依次点亮
  - [ ] 离开导入页后轮询停止（Network 面板无持续 status 请求）
  - [ ] DOCX 导入同样走进度条（非仅 PDF）
  - [ ] 旧 `state.importProgress` 字段仍存在，其他页面无回归
  - [ ] 进度到达 100 后轮询停止

  **QA Scenarios**:
  ```
  Scenario: 进度条真实递增（happy path）
    Tool: Playwright
    Preconditions: 复用已在运行的 9527/8000（**不重启**）
    Steps:
      1. 导航到题目导入页，选择目标 PDF
      2. 点击开始导入
      3. 每 300ms 采样一次进度条宽度与步骤条高亮状态
      4. 断言采样到的不同百分比数值个数 >= 5
      5. 断言百分比单调不减，终值为 100
      6. 断言至少 4 个步骤标签先后进入 done/active 态
      7. 断言源码中不存在 Math.min(45, ...) 伪造逻辑
      8. 截图
    Expected Result: 进度平滑递增，步骤依次点亮
    Failure Indicators: 不同数值 <= 2 → 仍在用伪造进度
    Evidence: .omo/evidence/task-7-progress.png

  Scenario: 轮询泄漏与 DOCX 覆盖（负向）
    Tool: Playwright
    Preconditions: 预览页已加载
    Steps:
      1. 记录 Network 中 status 请求计数
      2. 导航到其他页面
      3. 等待 5 秒，断言 status 请求计数不再增长（clearInterval 生效）
      4. 返回导入页，改传一个 DOCX 文件
      5. 断言 DOCX 导入同样出现多段递增进度
    Expected Result: 无轮询泄漏；DOCX 也有真实进度
    Failure Indicators: 离开页面后请求仍持续 → 未 clearInterval
    Evidence: .omo/evidence/task-7-progress-error.png
  ```

  **Commit**: YES
  - Message: `feat(import): 进度条消费后端真实进度并废除伪造进度`
  - Files: `.vtj/vue/question_import.vue`, `.vtj/files/question_import.json`

- [x] 8. 集成回归：10 PDF + 114 DOCX + HEAD 基线逐行比对

  **What to do**:
  - 跑完整回归并与**改动前基线**逐行比对，任何数值变化都要解释
  - 确认 VTJ DSL 一致性与 SFC 编译
  - 确认无行尾符噪声
  - 用已在运行的 9527/8000 做端到端手工验证（不重启服务）

  **Must NOT do**:
  - ❌ 不得为跑测试重启服务（用户明确要求复用现有端口）
  - ❌ 不得跳过基线比对直接宣称通过

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需组织多套回归并逐项比对基线
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 串行
  - **Blocks**: T9
  - **Blocked By**: T1, T2, T4, T5, T6, T7

  **References**:
  - `C:\Users\21499\AppData\Local\Temp\opencode\repro3.py` — 现有复现脚本，需扩展以覆盖图片与进度
  - `C:\Users\21499\AppData\Local\Temp\opencode\raw_inspect.py` — 题号/页脚/水印统计脚本
  - HEAD 基线数值（已记录）：pytest 16 failed / 168 passed / 52 errors；30 DOCX 题块 2899、污染 0
  - `CLAUDE.md/Opencode执行命令工作流.md` — 验证阶段要求

  **WHY Each Reference Matters**:
  - HEAD 基线数值是判断「是否引入回归」的唯一依据，必须逐条对齐而非只看总数
  - 52 errors 是历史遗留（如 `sys.stdout` 捕获问题），已修复过一次；不应新增

  **Acceptance Criteria**:
  - [ ] pytest 失败/通过/错误数与 HEAD 基线**逐条一致**（16/168/52）
  - [ ] 30 DOCX：题块 2899、污染 0
  - [ ] 10 PDF：题块数不减少、污染 0、无重复题号
  - [ ] `vtj_check_consistency` 无不一致；SFC 编译 `OK bad=0`
  - [ ] 所有改动文件 `git diff --numstat` 与 `--ignore-cr-at-eol --numstat` **完全一致**
  - [ ] 端到端：上传→预览→编辑→贴图→确认导入全流程通

  **QA Scenarios**:
  ```
  Scenario: 端到端全流程（happy path）
    Tool: Playwright
    Preconditions: 复用运行中的 9527/8000；10 PDF 语料就位
    Steps:
      1. 打开导入页，上传目标 PDF
      2. 断言进度条多段递增至 100%
      3. 断言预览页题块数 == 70，题号 1..70 连续无重复
      4. 断言题干图与选项图均可见
      5. 断言可疑角标按预期出现
      6. 贴一张图到第 1 题，断言立即可见
      7. 点确认导入，断言入库成功
      8. 断言控制台无 error
    Expected Result: 全流程无报错，数据正确入库
    Failure Indicators: 任一环节报错或数据错乱
    Evidence: .omo/evidence/task-8-e2e.png

  Scenario: 回归零容忍（负向）
    Tool: Bash
    Preconditions: 已记录 HEAD 基线
    Steps:
      1. pytest 全量，断言 failed/passed/errors 与基线逐条一致
      2. 30 DOCX 回归，断言题块 == 2899
      3. git diff --numstat 对比 --ignore-cr-at-eol --numstat，断言完全一致
    Expected Result: 零新增失败、零行尾噪声
    Failure Indicators: 出现基线中不存在的失败 → 引入回归
    Evidence: .omo/evidence/task-8-e2e-error.txt
  ```

  **Commit**: NO（仅验证，不改代码）

---

- [x] 9. 定向硬删除这 10 个 PDF 导入的题目并重导验证（含 dry-run 闸门）

  **What to do**:
  - **步骤 A｜备份**：`backend/data/question_bank.db` 备份到
    `backend/data/backups/pre_import_repair_<时间戳>/question_bank.db`，记录 SHA256，
    立即验证 `PRAGMA integrity_check` = `ok`
  - **步骤 B｜识别（dry-run，不删）**：确定「这 10 个 PDF 导入的题目」的**可复现识别口径**。
    优先使用 `QuestionImportRecord.original_filename` 匹配这 10 个文件名 + `import_status='COMPLETED'`
    的记录；若 `question_bank` 与导入记录之间**无直接外键**，则改用内容指纹口径：
    以 T8 解析出的 70 个题块题干做归一化哈希，与 `question_bank.question_content` 比对。
    **产出待删清单并报给用户：总数 + 抽样 5 条 + 识别口径说明。**
  - **步骤 C｜闸门确认**：等待用户确认清单无误后方可执行删除。**此步不可跳过。**
  - **步骤 D｜删除**：在单个事务中硬删除，同时按外键依赖清理
    `paper_question_relation`、`question_edit_log`、`question_image` 中的关联行。
    **不软删、不进回收站**（用户明确要求「硬删除」）
  - **步骤 E｜重导**：用修复后的链路重新导入这 10 个 PDF
  - **步骤 F｜验证**：核对重导后题量、题号连续性、图片可见性、无重复无串题
  - **步骤 G｜方案归档（必做，缺此项 F4 必然失败）**：将本计划
    `.omo/plans/import-pdf-image-dedup-repair.md` 复制到
    `solve_problems_files/题目导入图片重复串题问题优化方案.md`，
    并在 `solve_problems_files/` 内追加一节「实施结果记录」，
    写入：根因结论、实际改动清单、10 项验收标准的**实测数值**、遗留风险。
    **不得**用空文件或仅含标题的占位文件充数。

  **Must NOT do**:
  - ❌ **不得在用户确认 dry-run 清单前执行任何 DELETE**
  - ❌ 不得删除这 10 个 PDF 之外的题目（决策 1 为「甲」）
  - ❌ 不得跳过备份
  - ❌ 不得留空事务或部分提交（必须全成功或全回滚）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 不可逆数据操作，需严谨的识别口径与事务边界控制
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 串行
  - **Blocks**: —
  - **Blocked By**: T8

  **References**:
  - `backend/app/models/models.py` `QuestionImportRecord` — `original_filename` / `import_status` / `preview_data` 是识别口径的依据
  - `backend/app/models/models.py` `QuestionBank` — 确认是否存在指向导入记录的外键；**无则必须用内容指纹口径**
  - `paper_question_relation` / `question_edit_log` / `question_image` — 需连带清理的关联表
  - `backend/data/question_bank.db` — 删除目标
  - `backend/data/backups/pre_teacher_opt_20260928_163902/question_bank.db` — 已有可用备份（SHA256 `ebbb3da…`），可作为回滚兜底

  **WHY Each Reference Matters**:
  - **识别口径是本任务最大风险点**：若 `question_bank` 与 `QuestionImportRecord` 无外键，
    用 `original_filename` 删会**删不到**，用模糊内容匹配删会**误删手工录入题**。
    必须先查清 schema 再定口径，这正是 dry-run 存在的意义
  - 三张关联表若有残留会导致前端查题报错或统计失真

  **Acceptance Criteria**:
  - [ ] 备份存在且 SHA256 已记录，`integrity_check` = `ok`
  - [ ] dry-run 清单已产出并经用户确认（总数 + 抽样 5 条）
  - [ ] 删除后这 10 个 PDF 的题目**在库中为 0**
  - [ ] 删除**未波及**其他题目（删除前后总题数差 == dry-run 清单数）
  - [ ] 三张关联表无孤儿行
  - [ ] 重导后 10 个 PDF 题目数与 T8 解析基线一致
  - [ ] 重导后题号连续、无重复、无串题、图片全部可见

  **QA Scenarios**:
  ```
  Scenario: dry-run 识别准确（happy path）
    Tool: Bash (python sqlite3)
    Preconditions: T8 回归通过；已完成备份
    Steps:
      1. 查出 import_status='COMPLETED' 且 original_filename 匹配这 10 个 PDF 的记录数 N_rec
      2. 查明 question_bank 是否存在指向 import 的外键
      3. 按确认的口径枚举待删题目，输出总数 N_del 与 5 条抽样（question_id + 题干前 40 字）
      4. 断言 N_del > 0
      5. 断言抽样题目内容确实来自这 10 个 PDF（与解析基线题干匹配）
      6. **在此停止，等待用户确认**
    Expected Result: 清单可复现、抽样内容正确
    Failure Indicators: N_del == 0 → 识别口径错误；抽样含无关题目 → 口径过宽
    Evidence: .omo/evidence/task-9-dryrun.txt

  Scenario: 删除边界与回滚（负向）
    Tool: Bash (python sqlite3)
    Preconditions: 用户已确认清单；备份可用
    Steps:
      1. 记录删除前 question_bank 总行数 N0 及 3 条不在清单内的题目指纹
      2. 在事务中执行删除
      3. 断言总行数 == N0 - N_del（差值精确等于清单数）
      4. 断言 3 条保留题目指纹逐条未变（未误删）
      5. 断言三张关联表无孤儿行
      6. 若任一断言失败 → rollback 并从备份恢复
    Expected Result: 精确删除，无误伤
    Failure Indicators: 删除数 != N_del → 口径不一致；保留题被删 → 误伤
    Evidence: .omo/evidence/task-9-dryrun-error.txt
  ```

  **Commit**: NO（数据操作，不纳入代码提交）

---

## Final Verification Wave

> 4 个审查 agent 并行执行，全部通过后汇总报用户，**等待用户明确批准**才视为完成。

- [ ] F1. **方案合规审计** — `oracle`
  逐条核对「Must Have / Must NOT Have」：对每条 Must Have 读文件或打接口验证存在；
  对每条 Must NOT Have 搜索代码库确认禁项未出现（尤其：未禁用 `extract_tables()`、
  未放宽 monotonic、未残留 `Math.min(45, ...)` 伪造进度、未清空全库）。
  检查 `.omo/evidence/` 下证据文件是否齐全。
  输出：`Must Have [N/N] | Must NOT Have [N/N] | 证据 [N 存在/N 缺失] | VERDICT: APPROVE/REJECT`

- [ ] F2. **代码质量审查** — `unspecified-high`
  跑 `lsp_diagnostics` 于全部改动文件（要求 0 新增错误）、pytest、VTJ 一致性检查。
  审查反模式：`as any` / `@ts-ignore` / 空 catch / 生产环境 console.log / 注释掉的死代码 /
  过度注释 / 泛化命名（data/result/item/temp）。
  注意 `text_parser.py` 有 4 个**既存**类型告警（2098 / 2911 / 3190），需确认**非本次引入**。
  输出：`Diagnostics [N 新增] | Tests [N pass/N fail] | VTJ [一致/不一致] | VERDICT`

- [ ] F3. **真实手工 QA** — `unspecified-high`
  复用运行中的 9527/8000（**不重启**），从干净状态走完整用户旅程：
  上传 PDF → 观察进度条 → 预览 → 检查题干图与选项图 → 检查可疑角标 →
  贴图 → 逐题删除 → 确认导入 → 到题库页查图片是否持久化。
  覆盖边界：空题库、大文件（10 PDF 批量）、上传中途取消、贴图失败。
  证据落 `.omo/evidence/final-qa/`。
  输出：`场景 [N/N 通过] | 集成 [N/N] | 边界 [N 已测] | VERDICT`

- [ ] F4. **范围保真核查** — `deep`
  逐任务读「What to do」与实际 diff 比对，确认 1:1 —— 该建的都建了（无遗漏）、
  没建多余的（无越界）。重点核查：T6/T7 是否只改了列明的三处/四处，
  有无夹带对教师端 P0-P5 的改动；有无跨任务污染（某任务动了他人文件）。
  同时确认方案已归档到 `solve_problems_files/`。
  输出：`任务 [N/N 合规] | 污染 [CLEAN/N 问题] | 越界 [CLEAN/N 处] | 归档 [是/否] | VERDICT`

---

## Commit Strategy

按 Wave 分支提交，每个 commit 自带验证：

- `fix(import): 修复 PDF 表格重复拼接导致全文翻倍` — `question_import.py`
- `feat(import): PDF 图片占位符提取复用 DOCX 下游管线` — `question_import.py`
- `fix(parser): 增补水印页脚页眉噪声规则与串题标记` — `text_parser.py`
- `feat(import): 后台解析 6 阶段真实进度埋点与状态字段` — `question_import.py`, `models.py`, 迁移脚本
- `feat(import): 预览态题目贴图接口与卡片按钮` — `question_import.py`, `question_preview_list.vue`
- `feat(import): 前端进度条消费真实进度废除伪造进度` — `question_import.vue`
- `chore(import): 归档优化方案到 solve_problems_files` — `solve_problems_files/`

---

## Success Criteria

### Verification Commands
```powershell
# 后端回归
cd D:\砺安题库\iry安题库\backend   # 实际路径 D:\砺安题库\砺安题库\backend
python -m pytest tests/ -q              # 预期：无新增失败（HEAD 基线 16 failed/168 passed/52 errors 逐条一致）
python C:\Users\21499\AppData\Local\Temp\opencode\repro3.py   # 预期：图片标记 >0、题号无重复、无吞题

# 前端
# 复用已在运行的 9527/8000，不重启
# Playwright 实测预览页题干图 + 选项图可见、进度条递增

# 数据库
sqlite3 backend\data\question_bank.db "PRAGMA integrity_check;"   # 预期：ok
```

### Final Checklist
- [ ] 目标 PDF 无重复题、无串题
- [ ] 目标 PDF 图片 100% 可显示（题干 + 选项）
- [ ] 进度条真实递增，无跳变
- [ ] 噪声（水印/页脚/页眉）清除
- [ ] 30 DOCX 回归无回归
- [ ] VTJ DSL 一致、SFC 编译通过
- [ ] 无行尾符噪声
- [ ] 方案已归档 `solve_problems_files/`
- [ ] 10 个 PDF 题目已定向删除并重导验证
