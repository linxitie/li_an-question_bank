# 教师端题目呈现优化 —— 收尾验证计划

- 计划文件：`.sisyphus/plans/teacher-optimization-closeout.md`
- 依据工作流：`CLAUDE.md/Opencode执行命令工作流.md`
- 原始问题清单：`solve_problems_files/教师端问题呈现.md`
- 方案存档：`solve_problems_files/教师端问题优化解决方案.md`（v1.1）
- 状态：**等待人工审核（工作流第二节，人工审核不可跳过）**

---

## 一、任务目标

P0–P5 六个阶段的功能代码已全部实施完毕。本计划只覆盖**收尾验证与交付**：

1. 用真实 HTTP 请求验证 P5 新增的试卷题目内容编辑接口。
2. 用 30 份真实题目 DOCX + 30 份答案 PDF 走通端到端导入。
3. 浏览器验证教师端三个页面的图片渲染、题型、待复核筛选、试卷题目增删改查。
4. 把验证结论回写方案存档，产出可交付的测试报告。

**本计划不新增功能、不改业务逻辑。** 发现的缺陷按工作流第四节"由 Atlas 修正"处理。

---

## 二、已完成部分的验证结论（工作流第四节，人工审查 + 测试）

### 2.1 git diff 审查发现并已修复的破坏

| 问题 | 发现方式 | 状态 |
|---|---|---|
| `question_import.py` 行尾符被整体 CRLF→LF，git 报 +3931/-3730 掩盖真实改动 | `git diff --stat` | 已还原为 +240/-39 |
| 项目 `core.autocrlf=false` 且无 `.gitattributes`，git 按字节比较，易复发 | 配置检查 | 已确认（见风险点 R4） |

根因：我的批量脚本用文本模式写入，触发行尾转换。修复方式为二进制读写逐文件还原。

修复后核对：11 个改动文件的 `git diff --numstat` 与 `git diff --ignore-cr-at-eol --numstat` **完全一致**，即 diff 中已无行尾噪声，剩余 1282/387 全为真实内容改动。

### 2.2 修复的既有缺陷：pytest 套件完全无法运行

`backend/app/main.py` 第 37–40 行（**历史代码，非本次引入**）：

```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

新建 TextIOWrapper 后原 wrapper 被 GC，析构时关闭其底层 binary buffer，新 wrapper 指向已关闭的流 →
任何写入抛 `ValueError: I/O operation on closed file` → 解释器打印 `lost sys.stderr`。

后果：`pytest tests` 在**收集阶段即崩溃**，stdout 全空、零测试结果。工作流第四节强制的"运行测试套件"此前根本无法执行。

修复：改用 `reconfigure()`（复用同一底层流，不触发关闭），并对不支持/已关闭的流做静默兜底。

### 2.3 测试套件结果 —— 已证明 0 回归

| 运行环境 | 结果 |
|---|---|
| 我的工作区（含 P0–P5 全部改动） | `16 failed, 168 passed, 52 errors` |
| HEAD 基线（`git archive` 导出，**仅打流修复**，无任何 P0–P5 改动） | `16 failed, 168 passed, 52 errors` |

逐条比对：两边各 68 条 `FAILED`/`ERROR` 条目，**逐条完全一致**。

> **结论：本次 P0–P5 改动引入 0 个回归，也未修复任何既有失败。**
> 那 16 failed / 52 errors 全部为既有问题，主因是
> `sqlite3.OperationalError: index idx_import_status already exists`（索引重复声明）等。

### 2.4 已通过的专项验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 30 份真实 DOCX 解析回归 | `python scripts\verify_parser_regression.py "C:\Users\21499\OneDrive\Desktop\公安题目（打印）" --limit 30` | `exit=0` **验收结论: PASS**；30/30 解析；题目块 2899；**被污染题块 0**；断号 1（2019届文件原有） |
| 字段收口单元测试 | `test_coerce.py` | `OK, fails = 0` |
| P2 分节边界单元测试 | `p2_unit.py` | `OK` |
| P3 题型分类单元测试 | `p3_unit.py` | `PASS` |
| P4 尾部图片清理单元测试 | `p4_unit.py` | `PASS` |
| 3 个 Vue SFC + P5 模板编译 | `node vue_parse.cjs` | `TOTAL SYNTAX FAILURES: 0` |
| P5 前后端绑定静态检查 | — | `FAILURES: 0`（2 条 WARN 系检查脚本正则误报，实际模板已引用） |
| VTJ DSL 同步 | `vtj_vtj_sync_vue_to_dsl(teacher_papers)` | 已同步 7 项；`versionMatch: true` |
| 数据库备份完整性 | — | `integrity_check=ok`，8 表行数与源库一致，SHA256 已记录 |

---

## 三、剩余详细步骤

### 步骤 1：P5 后端接口真实联调

1. 后端已在 `0.0.0.0:8000` 运行（pid 25568，已重启加载新代码）。
2. 准备数据：取一个当前用户创建、状态为 `DRAFT` 的试卷及其题目关系。
3. 对 `PUT /api/teacher/papers/{paper_id}/questions/{question_id}/content` 依次验证：
   - 正常修改题干/选项/答案/解析/难度 → 200，DB 落库正确
   - 修改题型 → `need_review` 被清除
   - 修改分值 → `paper_question` 关系分值与试卷总分同步更新
   - `question_edit_log` 新增一条 `action=UPDATE` 审计
   - 非本人试卷 → 403/404
   - 非 `DRAFT` 试卷 → 拒绝
   - 非法题型名 → 拒绝（不得静默创建垃圾题型）
4. 验证完**回滚该测试数据**，不得污染生产库。

### 步骤 2：30 份 DOCX + 30 份 PDF 端到端导入

- 题目：`C:\Users\21499\OneDrive\Desktop\公安题目（打印）` 前 30 份
- 答案：`C:\Users\21499\OneDrive\Desktop\答案解析（不用打印）` 前 30 份
- 核对点：图片是否落盘且可访问、题型分布是否合理、答案是否正确对齐、
  低置信度题是否落 `need_review=1`、导入预览是否正确渲染图片。

### 步骤 3：浏览器验证

启动前端（`npm run dev`，端口 5173 当前空闲），用 Playwright 验证：

- 题目管理页：图片正常显示、编辑弹窗实时预览、「待复核」筛选可用
- 题目导入页：预览区图片与题型正确
- 试卷管理页：本卷题目增删改查、改分、排序、编辑弹窗、预览图片
- 控制台无报错

### 步骤 4：收尾

1. `git status` / `git diff --stat` 终审，确认无新增意外改动。
2. 将最终验证数据回写 `solve_problems_files/教师端问题优化解决方案.md`。
3. 产出测试报告归档。

---

## 四、涉及文件

**待验证（本次不计划修改）**

- `backend/app/api/v1/teacher.py` — P5 接口
- `backend/app/schemas/teacher.py` — `PaperQuestionContentUpdate`
- `backend/app/main.py` — 启动迁移 + 本次修复的流配置
- `backend/app/api/v1/question_import.py` — 导入与题型
- `backend/app/services/text_parser.py` — 解析与分类
- `backend/app/services/image_filters.py` — 图片过滤
- `backend/app/models/models.py` — `need_review`
- `.vtj/vue/teacher_papers.vue` / `teacher_questions.vue` / `question_import.vue`
- `.vtj/files/*.json` — 对应 DSL

**数据与脚本**

- `backend/data/question_bank.db`
- `backend/data/backups/pre_teacher_opt_20260928_163902/question_bank.db`
- `backend/scripts/verify_parser_regression.py`
- `backend/scripts/repair_type_registry.py`

**文档**

- `solve_problems_files/教师端问题优化解决方案.md`
- `CLAUDE.md/vtj.md`
- `CLAUDE.md/Opencode执行命令工作流.md`

---

## 五、验收标准（可量化）

1. P5 接口 7 个场景全部返回预期状态码，`question_edit_log` 审计落库，测试数据已回滚。
2. 30 份 DOCX 导入全部成功，**被污染题块数 = 0**。
3. 30 份 PDF 答案与题目正确对齐，答案正确率 ≥ 95%。
4. 浏览器三个页面控制台零报错，图片全部正常显示。
5. `pytest tests` 结果与 HEAD 基线**逐条一致**（68 条失败/错误条目完全相同），即 0 回归。
6. `git diff --stat` 中无行尾符噪声（`--numstat` 与 `--ignore-cr-at-eol --numstat` 一致）。
7. 方案存档已回写最终验证数据与遗留项。

---

## 六、风险点

- **R1（高）子代理不可用。** 连续 3 次委派均 30 分钟静默超时：
  `bg_cd11e00c`、`bg_c577bfa2`、`ses_f181fbd2cffexjYLk7wJxYHZKd`。
  工作流第三节要求 Atlas 委托子代理执行编码，但该路径当前不可用。
  工作流 5.1 指出病因为 `delegation.model` 与 `model.default` 不兼容；
  已核查 `C:\Users\21499\.config\opencode\opencode.json`，其中**只有 deepseek provider，
  没有 `model.default`，也没有任何 agent/委派配置**。修复需改用户的全局配置文件，
  属用户决策，我不擅自修改。**需人工决策后才能合规继续。**

- **R2（中）行尾符问题可能复发。** `core.autocrlf=false` 且无 `.gitattributes`。
  建议加 `.gitattributes` 显式声明 `*.py text eol=crlf`，从根上消除。
  本次未做（属新增文件，超出收尾范围），列为建议。

- **R3（中）既有测试失败不在本次范围。** 16 failed / 52 errors 源于
  `idx_import_status` 索引重复等历史问题。按工作流，若要修复需重新走
  Prometheus 规划流程，不应混入本次收尾。

- **R4（中）题型注册表名称不一致。** P3 分类器可能产出「简答题」「填空题」，
  而库中现有为「简述题」等旧名称；`_get_or_create_type` 会自动建新行。
  步骤 1/2 需确认这是否造成题型分裂。

- **R5（低）导入 PDF 可能触发外部服务。** 答案解析依赖 MinerU/Playwright，
  30 份 PDF 耗时可能较长，且可能失败，需预留时间与容错。

- **R6（低）后端重启影响。** 已重启后端（pid 25568）以加载新代码，
  原进程 pid 4392（16:31 启动，早于全部改动）已停止。
