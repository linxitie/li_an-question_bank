# 教师端题目导入模块 —— 全面修复与满血优化方案 + 实施计划

> **版本**：v1.0（待审）
> **日期**：2026-10-04　**分支**：`fix/vite-mobile-connection`　**基线提交**：`8eee113`
> **状态**：⏸ **待人工审核批准后方可实施**（本文件不含任何代码改动）
> **配套**：`solve_problems_files/行测题目导入优化方案.md`、`行测导入门禁与运维手册.md`、`README.md`

---

## 📌 归档说明（重要）

你的要求是「方案统一存档在 `D:\砺安题库\砺安题库\solve_problems_files`」。
规划代理（Prometheus）被写入护栏限制**只能写 `.omo/*.md`**，因此本方案落在 `.omo/plans/`。
**归档动作已列为下方「阶段 0」的第一项任务（`0-1`），由执行代理（Atlas）复制到**
`solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md`，并同步更新该目录 `README.md` 的文档索引。

---

## 0. 一句话结论

你反馈的 4 个问题**不是同一个原因**，而是 **10 条独立缺陷**叠加，其中 **3 条是「必现级」**（100% 触发）：

| 编号 | 缺陷 | 触发率 | 对应你的问题 |
|---|---|---|---|
| **RC-1** | 前端轮询超时 10 秒且零重试，超时后弹「文件上传异常：signal is aborted without reason」 | 高频 | 问题 1 |
| **RC-2** | 「确认入库」按钮计数读错状态字段，Word/PDF/分离导入**永远显示 0 题、永远无法入库** | **必现** | 问题 2 |
| **RC-5** | 真实入库端点 `/batch-parsed` 丢弃 `requirements` 与题组字段 | **必现** | 问题 3、4 |
| RC-3 | `/confirm` 读服务端旧快照，前端预览里的手工修改被静默丢弃 | 必现（该路径） | 问题 2 |
| RC-4 | `/confirm` 第 3809 行 `confirmed_items` 未定义 → 关联试卷时必然 500 | 必现（该路径） | 问题 2 |
| RC-6 | 文件类型只看扩展名，不校验文件头 | 条件触发 | 问题 1 |
| RC-7 | MinerU 实际只是「扫描件 PDF 的第三级兜底」，并非主识别库 | 事实偏差 | 全局要求 10 |
| RC-8 | 复合题/申论预览在 4 处各写一套，行为不一致 | 必现 | 问题 3、4 |
| RC-9 | 解析器与导入路由双文件超 4200/5000 行，职责混杂 | 结构性 | 全局要求 6 |
| RC-10 | 文档债与垃圾文件（26MB 乱码日志、429 条僵死预览记录、20+ 散落测试脚本） | 事实 | 全局要求 8、9 |

**你的裁决已并入方案**：MinerU 分层主库 / docx 不走 MinerU / 测试脚本直接删除 /
**同步拆分 + 先补齐三科门禁网**（§3.8 六层门禁 + §3.9 十步拆分）/
**I-6 单独 commit + 单独全套 E2E** / **9 个代表性真实语料做 Playwright 抽样，禁止虚拟空文档**（§3.11）。

---

## 1. 现状取证快照（全部实测，非推测）

### 1.1 数据库快照

`backend/data/question_bank.db`（148.6 MB，WAL 模式，73 张表，只读查询）

```
question_subject      : (1,'行测') (2,'申论') (3,'公专')
question_bank         : 2583 题，subject_id 全部 = 3（公专）
                       status=1 → 2478   status=0 → 105
                       行测 = 0 题      申论 = 0 题      ← 两科尚未导入
question_groups       : 21 组，但仅 20 道题带 group_id
requirements 非空     : 0 行          ← 申论「题目要求」从未落库
need_review=1         : 7 题
answer_analysis 为空  : 4 题
question_image        : 263 行
exam_paper            : 29 张

question_import_record: COMPLETED 1064 / PREVIEW 429 / PARTIAL 6 / PARSING 1 / FAILED 1
  ├─ 最后一次 COMPLETED = 2026-09-29   ← 此后 5 天 0 次成功入库
  └─ PREVIEW 记录按日：10-04=28  10-03=100  10-02=6  10-01=8
```

> **「最后一次成功入库是 5 天前」+「429 条 PREVIEW 堆积」= 入库环节整体失效的直接证据。**
> 这不是识别不准，是**识别完了但存不进去**。

### 1.2 你今天（10-04）的上传记录

| import_id | 文件 | 类型 | 状态 | 题数 |
|---|---|---|---|---|
| 1499 / 1500 | 2020年国家公务员考试《公安专业科目》真题.docx | WORD | PREVIEW | 98 / 98 |
| 1497 / 1498 | 2022年公安院校…试题.pdf / 解析.pdf | PDF | PREVIEW | 100 / 100 |
| 1495 / 1496 | 2022年内蒙古…《行测》题本.pdf | PDF | PREVIEW | 120 / 120 |
| 1493 | 2021年3月28日…参考答案及解析.pdf | PDF | PREVIEW | 95 |
| 1492 | 2021年3月28日…试卷.docx | WORD | PREVIEW | 100 |
| **1494** | **t.pdf** | PDF | **FAILED** | 0 |

> **注意成对重复现象**（1489/1490、1491+1492、1495/1496、1499/1500）：
> 同一文件被连续上传两次 —— 这是「前端报了错、用户重传」的典型指纹，
> 与 RC-1 完全吻合。**Word 解析其实一直是成功的（98/100 题），失败的是轮询与入库。**

### 1.3 运行环境

```
后端      http://localhost:8000   （/api 由 Vite 9527 代理）
前端      http://localhost:9527   strictPort，设计器 http://localhost:9527/__vtj__/
MinerU    GET /api/questions/import/mineru-health
          → {"available":true,"version":"python -m mineru.cli.client, version 3.4.5"}
          ⚠️ 本地 CLI 子进程模式，**没有独立 HTTP 服务**（8080/8888 均未监听）
OCR       Python 3.13.5 主进程内 PaddleOCR 必崩，必须走 ocr_worker.py 子进程
语料      题库/公安题目（打印）37 个 .docx + 10 个 .pdf（106 MB）
          题库/行测 170 PDF（141 MB）　题库/申论 254 PDF（151 MB）
          题库/答案解析（不用打印）46 PDF（99 MB）
```

### 1.4 后端日志实测（`backend/logs/app.log`，只读 grep）

```
2026-10-04 11:54:35,419 - [import-async] import_id=1494 解析失败: No /Root object! - Is this really a PDF?
2026-10-04 16:07:52,065 - [import-async] import_id=1501 解析完成 → PREVIEW（96 题）
POST /api/questions/import/upload  → 202，耗时 0.008s ~ 3.5s（上传本身极快，从不是瓶颈）
POST /api/questions/import/ocr    → 422（紧随 1494 失败之后）
```

---

## 2. 根因诊断（逐条含证据、影响、修复落点）

### RC-1 「文件上传异常：signal is aborted without reason」— 轮询超时，非上传失败

**完整因果链（每一环都已定位到行）：**

```
① .vtj/vue/question_import.vue:666-693  fetchWithRetry()
   var controller = new AbortController();
   var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
                                        ↑ 无 reason 地 abort
   → 浏览器抛出 AbortError，message 恰为 "signal is aborted without reason"

② .vtj/vue/question_import.vue:773-777  _pollImportStatus() 轮询状态接口
   this.fetchWithRetry('/api/questions/import/records/' + importId + '/status',
                       { method:'GET', headers:this.getAuthHeaders() },
                       10000, 0)
                       ↑ 10 秒超时    ↑ 0 次重试（retries=0，重试逻辑形同虚设）

③ 后端 GET /records/{id}/status  —— question_import.py:3349-3423
   async def，但内部用**同步** SQLAlchemy db.query()；
   且 status='PREVIEW' 时会 load_json_lenient(record.preview_data)
   反序列化整块预览 JSON（120 题的 payload 可达数 MB，且是双重编码，需多次 json.loads）

④ 后端解析占用 —— question_import.py:3332
   background_tasks.add_task(_process_import_async, ...)
   同步函数被丢进线程池，但 pdfplumber / python-docx 都是**纯 Python 密集计算**
   → 持 GIL → 事件循环被饿死；同时长事务持有 SQLite 写锁

⑤ 一次「慢轮询」= 立刻抛错，无重试
   → 一路冒泡到 :975-977
       } catch (e) {
         ElMessage.error('文件上传异常：' + (e.message || '网络错误'));
       }
   → 用户看到「文件上传异常：signal is aborted without reason」
```

**加重该问题的两个细节：**

- **:976 绕过了已有的友好提示函数**。`handleFetchError`（:697-707）本来能把 AbortError 渲染成
  「请求超时：服务器响应过慢，请稍后重试」，但 :976 直接拼 `e.message`，把技术黑话漏给了用户。
- **`retries` 参数形同虚设**：所有调用点都传 `0`，:686-689 的重试分支永远不会执行。

**影响**：文件**已经解析成功并躺在数据库里**（PREVIEW 状态），用户却看到失败提示 → 重传 →
产生重复 PREVIEW 记录与重复题目。这就是 429 条 PREVIEW 的来源。

**修复落点**：
| 文件 | 改动 |
|---|---|
| `.vtj/vue/question_import.vue:773-777` | 轮询超时 10s → **30s**；`retries` 0 → **2**（指数退避） |
| `.vtj/vue/question_import.vue:976` | 改用 `this.handleFetchError(e, '文件上传')`，不再直出 `e.message` |
| `.vtj/vue/question_import.vue:672` | `controller.abort(new Error('timeout'))` 带上 reason，超时与真实错误可区分 |
| `.vtj/vue/question_import.vue:804` | 上传超时 `60000` → `180000`，`retries` 0 → 1（6.33 MB .docx 留足余量） |
| `question_import.py:3349-3423` | 状态接口改「只查轻量列」：PREVIEW 时不再每次反序列化全量 JSON，另开 `GET /records/{id}/preview` 取结果 |

---

### RC-2 「确认入库」按钮对 Word / PDF / 分离导入永远为 0 —— **必现**

**证据（`.vtj/vue/question_import.vue`）：**

```
:192   <button class="btn-primary" @click="confirmBatchImport"
          :disabled="state.loading || hasBlockedQuestions">
          {{ ... '确认入库 ' + state.batchPreviewData.length + ' 题' }}
                                    ↑ 计数与禁用都读 batchPreviewData

:1050  if (!this.state.batchPreviewData.length) {
:1051      ElMessage.warning('无可导入的题目数据');  ← 直接 return，永不发请求
       }

:1006  self.state.batchPreviewData = data.questions;   ← 唯一一处赋值（仅 Excel/CSV 分支）
:1015  self.state.batchPreviewData = [];               ← Word/PDF 分支：清空！
:1560/1661  this.state.parsedDocsQuestions = questions; ← Word 智能提取写的是 parsedDocsQuestions
:2377  this.state.parsedDocsQuestions = data.questions; ← 分离导入匹配写的是 parsedDocsQuestions
:2725  fetchWithRetry('/api/questions/import/batch-parsed', …)  ← 真实入库走的是另一个端点
```

**结论**：Word / PDF / 分离导入三条路径的题目全部落在 `state.parsedDocsQuestions`，
而按钮读的是 `state.batchPreviewData`。**两条互不相通的状态通道。**
你在预览里看到的题目确实存在，但「确认入库 N 题」永远是 0，点下去只会提示「无可导入的题目数据」。

**连带灾难 —— 阻断闸门失效**：`:609-616`

```js
blockedQuestionList() {
  const list = this.state.batchPreviewData || [];   // ← 同样读错字段
  return list.filter(q => q && (q.blocked === true || ...));
}
hasBlockedQuestions() { return this.blockedQuestionList.length > 0; }
```

`blocked` / `block_reasons` 是在 `parsedDocsQuestions` 里的，所以：
**「宁可阻断报错交人工」这条你的硬约束，在真实入库路径上完全没生效。**
前端 :1043 的程序性守卫与后端 `/confirm` :3630 的阻断闸门都被绕过了。

**修复落点**：
| 文件 | 改动 |
|---|---|
| `.vtj/vue/question_import.vue` | 引入单一事实来源 `pendingQuestions` computed（合并 `batchPreviewData` 与 `parsedDocsQuestions`，去重）；按钮计数、disabled、`blockedQuestionList`、`confirmBatchImport` 全部改读它 |
| 同上 | 明确职责：`/confirm` 只服务 Excel/CSV；Word/PDF/分离统一走 `/batch-parsed`，两条路径**共用同一个阻断闸门** |

---

### RC-3 `/confirm` 读服务端旧快照，前端手工修改被静默丢弃

```
前端 :1059-1063  发送 { import_id, paper_name, questions: state.batchPreviewData }
后端 :3610       items = preview_data.get('items', []) or []   ← 忽略前端传来的 questions
```

即：教师在预览弹窗里**改过的题干、答案、解析、题型、删掉的题，全部被丢弃**，
后端按自己入库那一刻的原始快照重放。这是「预览改了但入库不对」的根因。

**修复**：`/confirm` 以 `payload['questions']` 为唯一事实来源；`preview_data` 降级为「仅供复盘的历史快照」，
不再参与入库。保留「前端未传 questions 时回落旧逻辑」的兼容分支，且打 deprecation 日志。

---

### RC-4 `/confirm` 第 3809 行 `confirmed_items` 未定义 → 关联试卷时必然 500

```
question_import.py:3809    for item in confirmed_items:
```
全文件 grep `confirmed_items` **只有这一处，从未被赋值** → 必然 `NameError`。

触发条件：`if record.paper_id:`（:3804）为真。而 :3786-3799 恰好在 :3784 提交之后
创建试卷并写入 `record.paper_id`。所以**只要这次导入创建了试卷，就必然 500**。

更糟的是时序：
```
:3784  db.commit()        ← 题目已入库
:3786-3799  创建试卷 + record.paper_id = ... ; db.commit()
:3809  NameError
:3861  db.rollback()      ← 只回滚了试卷关联，题目回滚不掉
:3863  HTTP 500 "导入失败: name 'confirmed_items' is not defined"
```
→ **题目其实进去了，但接口报 500**。用户看到「导入失败」→ 重传 → **重复题目**。
这解释了为什么 `question_type` 表会被撑脏、为什么历史上有大量「重复题」。

**修复**：`confirmed_items` 改为在循环内 `confirmed_items.append(item)` 累积，
并在 `/confirm` 入口加一条**启动即失败**的显式自检（`NameError` 是代码缺陷，不是运行期环境问题，
必须让它在测试里立刻炸出来，而不是等到用户点按钮）。

---

### RC-5 真实入库端点 `/batch-parsed` 丢弃「题目要求」与题组字段 —— **必现**

这是**问题 3 与问题 4 的决定性根因**。

```
前端 payload（:2733-2744）只发送 8 个字段：
   question_content / options / answer / answer_analysis
   question_type_detail / subject_category / score / difficulty
   ✗ 没有 requirements
   ✗ 没有 group_id / parent_id / question_number / sort_order
   ✗ 没有 blocked / block_reasons
```

而**后端其实是支持的**，只是 `/batch-parsed` 这条路没接：

| 能力 | `_upsert_question_core`（:2013） | `/confirm`（:3575） | `/batch-parsed`（:2601） |
|---|---|---|---|
| `requirements` | ✅ :2214 | ✅ :3722 | ❌ **未接** |
| `group_id` | ✅ :2190 | ✅ :3723 | ❌ **未接** |
| `blocked` 阻断 | ✅ :3630（在 `/confirm`） | ❌ **未接** | ❌ **未接** |

**数据库已经证明了后果**：`requirements` 非空 **0 行**、`申论(subject_id=2)` **0 题**、
2583 题里只有 20 题带 `group_id`。
模型层（`models.py:214-234`）**早就建好了** `group_id / parent_id / question_level /
sort_order / question_number / requirements` —— 只是数据永远进不来。

**修复落点**：
| 文件 | 改动 |
|---|---|
| `.vtj/vue/question_import.vue:2733-2744` | payload 补齐 `requirements`（string 与 array 两种形态都兼容）、`group_id`、`question_number`、`sort_order`、`need_review` |
| `question_import.py:2601-2960`（`/batch-parsed`） | 复用 `_upsert_question_core` 的 `requirements`/`group_id` 写入；新增题组 upsert（复用 :1996 / :2371 / :2427 已有的三处 `QuestionGroup(...)` 写法） |
| 同上 | **补 `blocked` 闸门**：任一题 `blocked=true` → 整批 409 拒绝，返回 `block_reasons` 中文映射（前端 :619-637 已有 `LABEL` 映射可直接复用） |

---

### RC-6 文件类型只看扩展名，不校验文件头

```
question_import.py:3311-3312
  file_type_map = {'.xlsx':'EXCEL', '.xls':'EXCEL', '.csv':'EXCEL', '.docx':'WORD', '.pdf':'PDF'}
  file_type = file_type_map.get(ext, 'EXCEL')
```

实测后果：`t.pdf` 实际是 Word 文件 → 按 PDF 走 pdfplumber → 日志实录：

```
2026-10-04 11:54:35,419 - [import-async] import_id=1494 解析失败: No /Root object! - Is this really a PDF?
  raise PDFSyntaxError("No /Root object! - Is this really a PDF?")   ← pdfminer
  pdfplumber.utils.exceptions.PdfminerException: ...
2026-10-04 11:54:35,467 - POST /api/questions/import/ocr → 422
```
`import_id=1494` 至今停在 `FAILED / EXTRACTING`。

反向风险同样存在：真 PDF 改名成 `.docx` 会被送进 python-docx，静默产出空文本。

**修复**：在 :3307 `buf = await file.read()` 之后加**文件头嗅探**（magic bytes）：
`%PDF-` / `PK\x03\x04`（OOXML，区分 docx/xlsx/pptx）+ `D0 CF 11 E0`（旧 OLE .doc/.xls）。
嗅探结果与扩展名冲突时：**以文件头为准 + logger.warning 记录**，
既不静默错路由，也不无脑拒绝用户改过扩展名的合法文件。

---

### RC-7 MinerU 现在是「第三级兜底」，不是主识别库

```
question_import.py:940   def _extract_text_from_pdf(...)
        :975-1105        ① pdfplumber（文本层主力，含表格提取）
        :1133-1138       ② if mineru_is_enabled(): mineru_text = mineru_extract_text_sync(buf)
        :1138            ③ if mineru_text: return _finish(mineru_text, 'mineru')
        :（之后）         ④ 回退 PaddleOCR 逐页路径（ocr_worker.py 子进程）
```

**事实**：
- MinerU 的**唯一调用点**是 :1133，**只在扫描件 PDF 分支**。
- `.docx` **完全不走 MinerU**（走 `_extract_text_from_docx` :706）。
- 有文本层的 PDF **不走 MinerU**（pdfplumber 先成功就返回）。
- 行测 170 份 PDF 实测 **100% 含文本层、0 扫描件** → **行测永远不会触发 MinerU**。

`mineru_service.py` 内部：
- `extract_text_sync`（:120）= `mkdtemp → 落盘 → subprocess.run(mineru) → 收集 *.md`
- `timeout = int(_cfg('MINERU_TIMEOUT', 300) or 300)`（:132）—— **默认 300s**
- `_sem.acquire(timeout=_SEM_WAIT_SECONDS)`（:137）—— **全局单槽串行排队**
- 前端注释（`question_import.vue:922`）写的是 `MINERU_TIMEOUT=600` → **前后端文档漂移**

> 你要求「MinerU 作为主识别库」。**当前架构下这个目标没有实现，且直接切换会有明确风险**：
> 文本层 PDF 走 MinerU 会丢掉 pdfplumber 的表格提取能力（资料分析题的材料表会被打平），
> 而行测 85 套试点 742 题 100% 匹配的成绩正是建立在 pdfplumber 文本层之上的。
> → 我的建议见 §3.4：**按文件类型分层的「主库」策略**，而不是全局换血。

---

### RC-8 复合题 / 申论预览在 4 处各写一套

| 位置 | 实现方式 | 材料 | 小题列表 | requirements | 折叠 |
|---|---|---|---|---|---|
| `.vtj/vue/question_preview_list.vue`（导入预览，1054 行） | 组件化，收 `groups[]`，用 `material_length / material_titles / material_preview` | ✅ | ✅ | ✅ :87-90 | ✅ |
| `.vtj/vue/teacher_questions.vue:108-110` | 自维护 `groupInfo.shared_content` **单块** | ✅ | ❌ | ❌ | ❌ |
| `.vtj/vue/admin_questions.vue:137-139` | 同上（**另一份拷贝**） | ✅ | ❌ | ❌ | ❌ |
| `.vtj/vue/answer_page.vue:78-95` | `.question-scroll` 竖向滚动 + `state.groupMaterials[group_id]` + `isGroupFirstOccurrence` | ✅ | ✅ 顺序 | ❌ | ✅ |

后端契约**已经存在**：
```
GET /api/questions/group/{group_id}      questions.py:571-636
  → { group: {id, group_type, title, shared_content, subject, source},
      members: [{question_id, question_number, sort_order, question_content,
                 options, answer, answer_analysis, question_type_detail,
                 difficulty, score}],   ← 含答案与解析
      total }
  ⚠️ 唯一缺口：members 里**没有 requirements**
```

> **好消息**：你要求的学生端「上下滑动作答整个复合题」`answer_page.vue` **已经实现了**
> （:78 `question-scroll` + :86-95 材料折叠 + :533 `scrollIntoView`）。
> 缺的是把 `requirements` 补进去，以及让它与另外三处**用同一套渲染**。

**修复落点**：
| 文件 | 改动 |
|---|---|
| `questions.py:609-621` | `members[]` 补 `requirements: q.requirements` 与 `need_review` |
| `question_preview_list.vue` | 升级为**三端共用的题组渲染组件**（对外只吃 `/group/{id}` 同构数据） |
| `teacher_questions.vue:108-110` | 删掉自维护 `groupInfo` 单块，改用共用组件（材料在上，小题逐题列出答案+解析） |
| `admin_questions.vue:137-139` | 同上 |
| `answer_page.vue:86-95` | 材料区补 `requirements` 展示；共用组件的只读模式 |

---

### RC-9 解析器与导入路由双巨型文件

| 文件 | 行数 | 体积 | 问题 |
|---|---|---|---|
| `backend/app/api/v1/question_import.py` | **4996** | — | 路由 + 解析 + 落库 + 去重 + 建卷 + 广播 全塞一个文件 |
| `backend/app/services/text_parser.py` | **4239** | 220.9 KB | 选择题/行测/申论/答案归一化/题型判定 全在一个模块 |

这直接违反你的全局要求 6（去粗取精而非胡乱新建）。**但必须强调**：
`text_parser.py` 同时是 **G1 公专零回归门禁**的守门对象（基线 2899 块 / 污染 0 /
题型分布 `{'单选题':2534,'多选题':249,'判断题':80,'简答题':36}` /
选项数分布 `{'4':2796,'1':13,'2':14,'0':73,'3':3}`），
`extract_question_blocks` 函数体被列为**字节级红线**。

→ **✅ 本轮做拆分**（你的裁决，见 §3.9）。但必须遵守两条硬约束：
1. **门禁网先行**（§3.8）—— L0 红线哈希 + L3 落库语义必须先建立，否则无从证明「移动未改变行为」；
2. **`text_parser.py` 只能减约 12%** —— 申论解析被 `extract_question_blocks` 字节级红线锁在原地，
   `question_import.py` 才是主战场（4996 → ~900 router + 独立包）。

---

### RC-10 文档债与垃圾文件（对应你的全局要求 8、9）

| 项 | 实测 | 处置建议 |
|---|---|---|
| `backend/logs/app.log` | **26.1 MB**，且**部分中文行乱码**（`瑙ｆ瀽澶辫触` = 解析失败） | 修编码（强制 UTF-8）+ 按大小轮转 |
| `question_import_record` PREVIEW | **429 条**僵死预览 | 需你**单独授权**才可清理 |
| `question_import_record` PARSING | 1 条卡死（`t.pdf`） | 同上 |
| 根目录散落 | `_p1.py _p2.py _p3.py check_versions.py check_xicon.py verify_types.py verify_types2.py test_notes_api.py test_random_api.py test_obsidian_read.py backfill_unclassified.py clean_questions.py fix_irrelevant_images.py fix_utb_in_db.py smoke_tmp.js api_test.json docx_text_output.txt docx_v4.txt pipeline_test.txt pipeline_v2.txt .DS_Store debug.log` | 逐个判定「有引用 / 无引用」，无引用者归档到 `solve_problems_files/_archive/` 而非直接删 |
| `backend/data/*.bak*` | 多个全量备份（含 148.5 MB 的 `bak_pre_wipe_20261004_102517`） | **禁止清理**（回滚依赖） |
| `backend/README.md` | **完全过时**：声称 MySQL 8.0 + Redis + `routers/auth.py` 目录结构；实际是 SQLite(WAL) + `app/api/v1/` | 重写或标注 DEPRECATED |
| `text_cache.bak_20261001_200518` | 「全文翻倍」旧文本的证据 | **禁止删除** |

---

## 3. 修复与优化方案

### 3.0 改造总原则（贯穿所有模块）

1. **单一事实来源**：题目集合只有一份（前端 `pendingQuestions` computed）；
   阻断闸门只有一处（前端 computed + 后端 `/batch-parsed` 与 `/confirm` 双端）；
   答案归一化只有 `canonical_answer`；题型判定只有 `_detect_question_type`。
2. **宁可阻断，不许静默丢题 / 盲配 / 伪造**（沿用你的既有硬约束）。
3. **公专零回归**：G1 门禁 5 项数字必须逐项一致，不接受「总数不变」。
4. **不新建已有能力的替代品**：题号解析、答案归一化、题型判定、题组表、OCR/MinerU 服务
   一律复用现有实现，只做接线与加固。
5. **VTJ 纪律**：`question_import` 页 `raw: true` → **禁止同步 `.vtj/files/*.json`**；
   `useProvider({ id:'question_import', version:'1790329880372' })` **version 不得变更**；
   任何 `<template>` 结构变更**必须停下请你在设计器拖拽**，执行代理只改 `<script>`。

### 3.1 模块 A —— 上传与轮询稳定性（对应问题 1）

| # | 落点 | 改动 |
|---|---|---|
| A-1 | `question_import.vue:773-777` | 状态轮询超时 `10000` → `30000`；`retries` `0` → `2` |
| A-2 | `question_import.vue:975-977` | catch 改用 `handleFetchError(e,'文件上传')`；AbortError 映射为「解析仍在后台进行，请点『刷新预览』，**不要重复上传**」 |
| A-3 | `question_import.vue:672` | `controller.abort(new Error('client timeout'))` 带上 reason，使超时可与真实错误区分 |
| A-4 | `question_import.vue:804` | 上传超时 `60000` → `180000`，`retries` `0` → `1`（6.33 MB .docx 留足余量） |
| A-5 | `question_import.py:3349-3423` | 状态接口**瘦身**：PREVIEW 时不再每次反序列化全量 JSON；新增 `GET /records/{id}/preview` 单独取结果 |
| A-6 | `question_import.py:3330-3335` | 去掉「未注入 BackgroundTasks 就退化为同步」的**阻塞兜底**——改为启动期断言 + 明确 503，杜绝请求线程被解析占死 |
| A-7 | 新增 `GET /records/{id}/preview` | 用户刷新页面后能重新挂上已有 import_id 的预览（现在刷新即丢失，等于逼用户重传） |
| A-8 | `question_import.py:3303-3312` | **文件头嗅探**（见 RC-6），扩展名与文件头冲突时以文件头为准并记 warning |

**验收**：上传 6.33 MB 的 `2020届公安院校公安专业联考…真题.docx`，从点击到出现预览，
**全程无「signal is aborted」**；故意把 PDF 改名 `.docx` 上传，日志出现 warning 且**仍能正确解析**。

### 3.2 模块 B —— 入库链路统一（对应问题 2）—— **最高优先级**

| # | 落点 | 改动 |
|---|---|---|
| B-1 | `question_import.vue` | 新增 `pendingQuestions` computed（合并 `batchPreviewData` + `parsedDocsQuestions`）；:192 按钮计数、:615 `hasBlockedQuestions`、:609 `blockedQuestionList`、:1050 空守卫 **全部改读它** |
| B-2 | `question_import.vue:2733-2744` | `/batch-parsed` payload 补齐（见 RC-5 字段清单） |
| B-3 | `question_import.py:2601+`（`/batch-parsed`） | 接入 `requirements` / `group_id` / `question_number` / `sort_order` 落库 |
| B-4 | `question_import.py:2601+` | **补 `blocked` 闸门**：任一题 blocked → `409` + `block_reasons`（中文文案复用前端 `LABEL` 表） |
| B-5 | `question_import.py:3610`（`/confirm`） | 改为以 `payload['questions']` 为准；`preview_data` 降级为历史快照 |
| B-6 | `question_import.py:3809` | 修 `confirmed_items` NameError；并在模块导入处加显式自检 |
| B-7 | `question_import.py:2601+` | 返回**逐题结果映射**（前端题目 index ↔ 新 question_id ↔ 失败原因），消除「导入了多少」的黑箱 |

**验收**：对同一份 Word 文档，走「上传→预览→改 1 道题的答案→确认入库」，
题库中该题答案 = 改后的值（RC-3 修复证据）；含 `blocked` 题的批次返回 409 且**零写入**（B-4）。

### 3.3 模块 C —— 三科识别与匹配加固（对应问题 2 的识别侧）

**不做**：不新建题号解析器、不新建答案归一化、不新建题型判定、不新建表。

| # | 科目 | 改动 | 依据 |
|---|---|---|---|
| C-1 | 公专 | `_extract_options` 字母错位缺陷（244 题 `options=[{'A':'B.'},{'C':'D.'}]`）已在行测专用路径修复；**本方案只补一条回归用例**，确保公专链路不受影响 | G1 门禁 |
| C-2 | 行测 | 复核 `328b0b0`「按题号+来源去重」在**图形推理指令句**上的表现（历史曾 131 题中 79 题被判重复而静默丢弃）；异常一律 `need_review` 而非丢弃 | 行测方案 §7.1 |
| C-3 | 申论 | 打通 **T2 迁移已完成但从未落库**的断点：`requirements` 列已存在（`models.py:234`）但 0 行数据。修复点在 B-3，不在解析器 | handoff §4 T2/T3 |
| C-4 | 申论 | 合订本 2019 两份仍阻断（`answer_block_count_mismatch`）。**保持阻断，不放宽** —— 这是正确行为；仅在你能确认「答案区真有 5 段而题目只有 4 题」后才补题号体例 | handoff §4 T1 |
| C-5 | 分离导入 | 题目文档 / 答案文档**分离**与**合并**两条路径统一到同一个三方交叉校验（题号 + 分值 + 题干指纹），不一致即阻断，**禁止按序硬配** | handoff §5.2 |
| C-6 | 全科 | `_auto_detect_tags` 的省份/年份必须**只从文件夹名取**，禁止用文件名推断（2025 甘肃全年缺「省」、广西写「区考」） | 行测方案 R-5 |

### 3.4 模块 D —— MinerU 定位为「分层主库」（对应全局要求 10）

> 详见 §8 决策点 1/2。按文件类型分层的「主库」策略，**不做全局换血**。

| 文件类型 | 主识别库 | 辅助（依次回退） | 理由 |
|---|---|---|---|
| **.docx / .xlsx / .csv** | 原生解析（python-docx / openpyxl） | — | MinerU 只吃 PDF，走它反而多一次格式转换损耗 |
| **PDF 有文本层** | pdfplumber（含表格） | PyPDF2 | 行测 170/170 有文本层；申论 254 份同源 |
| **PDF 扫描件** | **MinerU 3.4.5（第一顺位）** | PaddleOCR（`ocr_worker.py` 子进程） | MinerU 版式覆盖最广，成功率最高 |
| **图片** | MinerU `extract_text_from_image` | PaddleOCR | 同上 |

| # | 落点 | 改动 |
|---|---|---|
| D-1 | `question_import.py:1133-1140` | MinerU 在扫描件分支**显式化为第一顺位**，PaddleOCR 降为第二顺位，**加日志标注实际采用的引擎** |
| D-2 | `question_import.py:973-1105` | 解析结果保留 `engine` 字段（`_finish(text,'pdfplumber')` 已有此机制），**预览页显示本次实际使用的引擎** |
| D-3 | `mineru_service.py:132` | `MINERU_TIMEOUT` 默认 300 与前端注释 600 漂移 → **统一为单一事实来源**（放 `app/config.py`，前端从 `/api/questions/import/stats` 读取，不再硬编码 `PDF_OCR_TIMEOUT_MS=960000`） |
| D-4 | `mineru_service.py:137` | 全局单槽 `_sem`（60s 排队）改为**按文件类型分池**，避免长文档把其他导入全堵住 |
| D-5 | 新增 | MinerU 失败时**必须回退并留痕**，绝不静默产出空文本 |

### 3.5 模块 E —— 复合题 / 申论统一预览契约（对应问题 3）

**目标预览形态（你要求的）**：申论 = 一个整题（材料 + 要求），其下逐个小题各带自己的答案 + 解析。

```
┌─────────────────────────────────────────────────────────┐
│ 第 3 题  [申论·归纳概括]  15 分                          │
│ ┌── 给定材料（可折叠，默认展开）────────────────────┐    │
│ │  材料正文…（多段，含图片）                          │    │
│ └────────────────────────────────────────────────────┘    │
│ ┌── 题目要求 ─────────────────────────────────────┐    │
│ │  ① 全面、准确；② 逻辑清晰；③ 不超过 300 字         │    │
│ └────────────────────────────────────────────────────┘    │
│  ├─ 小题 (1) 概括主要问题                            │    │
│  │    答案：…（分点）                                  │    │
│  │    解析：…（分点）                                  │    │
│  ├─ 小题 (2) 提出对策建议                            │    │
│  │    答案：…    解析：…                              │    │
└─────────────────────────────────────────────────────────┘
```

| # | 落点 | 改动 |
|---|---|---|
| E-1 | `questions.py:609-621` | `members[]` 补 `requirements` / `need_review` / `parent_id` |
| E-2 | `question_preview_list.vue` | 重构为**三端共用渲染组件**，内部按「材料 → 要求 → 小题列表（各带答案解析）」渲染；对外只吃统一契约 |
| E-3 | `teacher_questions.vue:108-110` | 删除自维护 `groupInfo` 单块，接共用组件 |
| E-4 | `admin_questions.vue:137-139` | 同上（消除重复拷贝） |
| E-5 | 公专 / 行测 | **保留现有预览设定不变**（行测的分区折叠 + 考点标签已由 `f78a0b6` 落地且验证过，不得回归） |
| E-6 | 模板结构 | ⚠️ 若共用组件需要的容器在 `<template>` 中不存在，**必须停下请你在 `http://localhost:9527/__vtj__/` 设计器拖拽**，不手工改 template |

### 3.6 模块 F —— 学生端竖向滑动作答（对应问题 4）

**好消息**：`answer_page.vue:78-95` 的竖向滚动 + 题组材料折叠 + `scrollIntoView` **已实现**。

| # | 落点 | 改动 |
|---|---|---|
| F-1 | `answer_page.vue:86-95` | 材料区补 `requirements` 展示（当前缺失） |
| F-2 | 同上 | 接入 E-2 的共用组件（只读模式），保证与教师端预览**形态一致** |
| F-3 | `mobile_practice.vue` / `tablet_practice.vue` | 同步 F-1/F-2 |
| F-4 | 回归验证 | 复合题从第一小题一路滑到最后一小题，答案各自独立保存，**不得互相覆盖** |

### 3.7 模块 G —— 运维、清理与文档债（对应全局要求 8、9）

| # | 落点 | 改动 | 授权 |
|---|---|---|---|
| G-1 | `app/logs` 配置 | 强制 UTF-8 编码 + 按大小轮转（现在 26 MB 且乱码） | ✅ 可做 |
| G-2 | `backend/README.md` | 重写为实际架构（SQLite WAL + `app/api/v1/` 布局 + 真实端点表） | ✅ 可做 |
| G-3 | 20+ 散落测试脚本 | **直接删除**（你的裁决）。前置硬约束：① 逐个 `grep -r` 全仓确认零引用；② 删除前把完整清单 + 引用检查结果写入 `.omo/evidence/task-delete-manifest.txt`；③ 分批删除，每批后跑 `gate_all.py --quick` | ✅ 已授权 |
| G-4 | `.DS_Store` / `debug.log` / `smoke_tmp.js` | 删除（无任何引用） | ✅ 可做 |
| G-5 | 429 条 PREVIEW + 1 条 PARSING | **不动**。清理属破坏性操作，需**单独授权** | ⛔ 需单独授权 |
| G-6 | `backend/data/*.bak*`、`text_cache.bak_20261001_200518` | **禁止清理**（回滚与证据依赖） | ⛔ 永不动 |
| G-7 | `question_import.py` / `text_parser.py` 拆分 | ✅ **本轮做**（你的裁决）→ 见 §3.9 全 10 步。前置：**必须先完成阶段 1 门禁网** | ✅ 已授权 |
| G-9 | `.pre-commit-config.yaml` / `.github/workflows` | 接入 L0（本地秒级）与 L0+L1+L3（CI） | ✅ 可做 |
| G-10 | pytest 债务 | 本轮**不收敛**，但必须把 `16 failed / 52 errors` 逐个分类登记进 `backend/data/gates/known_broken.json`，并写明每项的失败原因 | ✅ 可做 |
| G-8 | 全局 | 严格禁用 `git add -A`；`backend/tmp/`、`*.db*`、`题库/` 下 PDF 一律不入库 | ✅ 纪律 |

---

### 3.8 模块 H —— 三科回归门禁网（长期基建，你追加的最高优先项）

> **为什么这是最高优先项**：现有 G1–G4 **全部只测解析器**，一条都不测**落库链路**。
> 这正是 RC-2 / RC-3 / RC-4 / RC-5 四条**必现**缺陷能一路溜过所有门禁、直接打到你面前的原因。
> **先有网，再动刀** —— 模块 I 的拆分必须建在模块 H 之上。

#### 3.8.1 现有门禁的能力缺口

| 现有 | 覆盖 | 缺口 |
|---|---|---|
| G1 `verify_parser_regression.py` | 公专解析器 5 项数字 | 只测**公专**；数字快照式，分布巧合相等时抓不到语义回归 |
| G2/G3 `verify_xingce_regression.py` | 行测分节/区间/答案覆盖 + 申论不变量 | 无**结构化指纹**，无法回答「哪一题变了」 |
| G4 `pytest` | 单元测试 | 基线是 **`16 failed / 168 passed / 52 errors`** —— 这是**债务**被当成标准；52 个 error 未分类 |

#### 3.8.2 分层门禁网设计（每层只抓一类缺陷，互不重叠）

```
gate_all.py  ← 一键入口，退出码聚合，报告写 backend/data/gates/last_run.json
  │
  ├── L0 静态红线门禁   gate_l0_redlines.py        ~1s    ★ 新建
  ├── L1 解析器指纹门禁 gate_l1_parser.py          ~60s   ★ 升级 G1
  ├── L2 匹配配对门禁   gate_l2_matching.py        ~180s  ★ 升级 G2/G3
  ├── L3 落库链路门禁   gate_l3_ingest.py          ~20s   ★ 新建（最关键）
  ├── L4 API 契约门禁   gate_l4_api_contract.py    ~15s   ★ 新建（归并现有零散脚本）
  └── L5 前端数据契约   gate_l5_frontend_contract.py ~10s  ★ 新建
```

**L0 静态红线门禁**（秒级，无语料，进 pre-commit）
| 断言 | 基线 |
|---|---|
| `text_parser.py::extract_question_blocks` **函数体** SHA256 | 位移无关比对，锁死 |
| `question_import.py` 共享 dispatch 块（4005-4011）SHA256 | 456 字符，锁死 |
| `.vtj/files/question_import.json` SHA256 | `raw:true` 页禁改 DSL |
| `.vtj/vue/question_import.vue` **第 1-493 行**（template 段）SHA256 | 零改动 |
| `useProvider({ id:'question_import', version:'1790329880372' })` | version 不得变更 |
| 公专 2583 题的 `extract_question_blocks` 路径未被 import 到新模块 | 防误改 |

> **这是唯一能 100% 可靠守住字节级红线的手段** —— 人工按行号比对会在上方新增代码后整体位移，
> 必须改成哈希。

**L1 解析器指纹门禁**（把「数字快照」升级为「结构化指纹」）
- 统一入口：`python scripts/gate_l1_parser.py --subject gongzhuan|xingce|shenlun`
- 每科输出 JSON 指纹，**逐键比对** `backend/data/gates/L1_{subject}_baseline.json`：
  ```
  块数 / 题型分布 / 选项数分布 / 答案覆盖率 / 解析覆盖率
  blocked 率 / need_review 率 / 题号单调性 / 平均块长度
  污染计数（UTB 标记、测试模板、促销文本）
  材料块数 / 题组数（复合题）
  ```
- 新增键必须显式 `--accept-new-key` 并在 commit 说明理由 → **基线变更必须有据可查**
- 公专基线必须精确等于现有 2899 那 5 项，一项都不能差

**L2 匹配配对门禁**（继承 G2/G3 并加两条历史回归守卫）
- 行测：分节序列全等 / 分节区间一致 / 答案锚点覆盖 100% / blocked=0
- **新增守卫 1**：图形推理指令句**不得**被判为同题（针对历史上「131 题中 79 题被判重复静默丢弃」的 60% 事故）
- **新增守卫 2**：申论 `answer_block_count_mismatch` 必须为 0，**除非在白名单**
  （合订本 2019 两份进白名单 —— 它们当前是**正确阻断**；一旦修复就移出白名单）

**L3 落库链路门禁**（★ 当前完全缺失，也是本轮最重要的新增）
- **用临时内存库**（`sqlite3.connect(':memory:')` + 由 SQLAlchemy metadata 建表），**绝不触碰真实库**
- 断言清单（每条都对应一条已定位的真实缺陷）：
  | # | 断言 | 拦截的缺陷 |
  |---|---|---|
  | 1 | 传入 N 题 → 库中恰好 N 题（**不多不少**） | 静默丢题（行测 60% 事故） |
  | 2 | 传入 `requirements` → 库中该列非空 | **RC-5** |
  | 3 | 传入 `group_id` → 库中该列非空 + 题组行存在 | **RC-5** |
  | 4 | 任一题 `blocked=true` → 409 且**库中零新增** | 阻断闸门失效 |
  | 5 | 改一个字段后入库 → 库中是新值（非 `preview_data` 旧快照） | **RC-3** |
  | 6 | 触发建卷路径时**不抛 NameError** | **RC-4** |
  | 7 | `new_question_ids` 数量 == `success_count` | 黑箱返回 |
  | 8 | 重复调用同一 `import_id` → 幂等，不产生重复题 | 重传事故 |

**L4 API 契约门禁**（归并现有 `verify_task11_endpoint.py` / `verify_task11_auth.py` / `verify_task11_vite.py`）
- `openapi.json` 快照比对：导入相关端点的路径 / 方法 / 必填字段不得漂移
- 覆盖 401 / 403 / 404 / 409 / 422 / 500 各分支入参校验
- 含「经 Vite 9527 代理实请求」验证（避免改完不重启后端拿到 502 却误判前端有问题）

**L5 前端数据契约门禁**（静态 grep + 运行时 Playwright 双段）
- 静态：`.vtj/vue/question_import.vue` 必须包含标识符清单
  （`pendingQuestions`、`hasBlockedQuestions`、`handleFetchError`、`blocked`、`block_reasons`、`requirements`、`group_id`…）
- **反向守卫（关键）**：禁止再出现 `state.batchPreviewData.length` 这类**读错状态字段**的写法 → **RC-2 的专属回归守卫**
- 运行时：导入预览页能实际渲染出「材料块 + 小题列表 + 各题答案解析」

#### 3.8.3 门禁网的长期维护约定（可长久稳定运行的关键）

| 约定 | 内容 |
|---|---|
| **基线入库** | `backend/data/gates/*.json` 全部入库，任何变更走 `--accept` 且 commit message 写明理由 |
| **基线单调性** | 基线只能「有据可查地」变更。例：新增行测分区枚举值 → 必须同时更新 L1 行测基线并说明 |
| **门禁自身有单测** | `gate_*.py` 每个断言函数都要有对应单测，门禁本身不能是黑箱 |
| **分层执行** | `--quick` 只跑 L0+L1（秒级，进 pre-commit）；全量跑 L0–L5（CI / 发布前） |
| **局部可跑** | `--subject xingce` / `--layer L3` 支持局部执行，避免每次全量 |
| **结果可机读** | 每次写 `last_run.json`，供 CI 判定与后续看板消费 |
| **债务登记** | pytest 的 `16 failed / 52 errors` **本轮不收敛**，但必须逐个分类登记为 `known_broken.json`，并承诺后续专项收敛 |

#### 3.8.4 门禁网与拆分的关系（不可颠倒）

```
❌ 先拆分再补门禁  → 无法验证「移动是否改变行为」→ 拆分必然变成不可控重构
✅ 先建 L0 + L3    → 再纯平移 → 每步用 L0（哈希）+ L3（落库语义）证明行为未变
```

---

### 3.9 模块 I —— 巨型文件有序拆分（你的裁决：同步拆分）

#### 3.9.1 必须先讲清的一个硬约束（诚实披露）

`text_parser.py::extract_question_blocks` 被你定为**字节级红线**，而：
- 申论的 `_parse_essay_document` 是**被 `extract_question_blocks` 入口直接调用**的（handoff §2.1）
- ⇒ **申论部分不能移出**，否则函数体必须改成委派，红线即破

**结论**：
| 文件 | 当前 | 可拆空间 | 拆后 | 说明 |
|---|---|---|---|---|
| `text_parser.py` | 4239 行 | **仅行测部分**（`route_xingce_sections` / `split_xingce_answer_blocks` / `xingce_cross_validate`） | ~3700 行 | 申论/公专/答案归一化/题型判定**全部留在原地**。降幅约 12%，但风险极低 |
| `question_import.py` | 4996 行 | **绝大部分** | ~900 行 router + 独立包 | 无字节级红线（dispatch 块除外），**这才是拆分的主战场** |

> 我不会为了「看起来拆了」而伪造降幅。可拆空间受红线约束，这是事实。

#### 3.9.2 `question_ingest` 包结构（主战场）

```
backend/app/services/question_ingest/
    __init__.py       re-export，保持 from ...question_import import X 全兼容（零调用方改动）
    magic.py          ★ 新增：文件头嗅探（RC-6）
    docx_reader.py    _sanitize_docx_rels / _open_docx_resilient / _extract_text_from_docx_raw_xml / _extract_text_from_docx
    pdf_reader.py     _extract_text_from_pdf / _extract_text_from_scanned_pdf / _decode_pdf_image / _extract_images_from_pdf_page / _pdf_has_images_only
    excel_reader.py   _parse_excel_buffer / _parse_csv_buffer / _normalize_question
    tags.py           _auto_detect_tags / _detect_complete_paper / _extract_paper_name / _get_or_create_import_paper
    images.py         _extract_and_save_images / _compress_and_store / [IMAGE:x_y] 占位符协议 / _check_size
    upsert.py         _upsert_question_core / _upsert_xingce_question / _detect_duplicate / _get_duplicate_info
    groups.py         ★ 新增：把散在 3 处的 QuestionGroup(...) 收敛为一处（配合模块 B）
    links.py          ★ 新增：_link_knowledge_points / _get_or_create_subject / _get_or_create_type

backend/app/api/v1/question_import.py   ← 只留 router 定义 + 端点函数 + 共享 dispatch 块（字节不变）
```

#### 3.9.3 拆分执行顺序（**每步一个独立 commit，可单独回滚**）

| 步 | 内容 | 验证 |
|---|---|---|
| **I-0** | **先建 L0 红线门禁 + L3 落库门禁**（模块 H） | 这是拆分的前置条件，不可跳过 |
| I-1 | 建 `question_ingest/` 包骨架 + `magic.py`（RC-6 文件头嗅探，逻辑新增但独立可测） | `gate_l0` + `gate_l3_ingest` |
| I-2 | 平移 `excel_reader.py`（130 行，风险最低，先热手） | 每步：`gate_all.py --quick` + `gate_l3_ingest.py` |
| I-3 | 平移 `docx_reader.py`（200 行） | 同上 + E2E-1 |
| I-4 | 平移 `tags.py`（300 行） | 同上 + E2E-5 |
| I-5 | 平移 `images.py`（400 行） | 同上 + E2E-1（图片占位符协议） |
| I-6 | 平移 `pdf_reader.py`（700 行，**风险最高**，单独 commit） | 同上 + E2E-2 + E2E-5 |
| I-7 | 平移 `upsert.py` + `links.py`（约 700 行） | `gate_l3_ingest` 全绿 + E2E-3/4/9 |
| I-8 | 新建 `groups.py`，收敛 3 处 `QuestionGroup(...)` 为 1 处 | `gate_l3_ingest` + E2E-6/7 |
| I-9 | 平移行测三函数到 `text_parser/xingce.py`（约 400 行，**唯一动 text_parser 的步骤**） | `gate_l0` 红线必须仍绿 + `gate_l2_matching` |

**每一步的铁律**：
- **纯移动（move）不改逻辑** —— `git diff` 必须显示为「纯删除 + 纯新增」，零逻辑变更
- 每步独立 commit，message 标注 `refactor(import): move X to question_ingest，纯移动零逻辑变更`
- 每步前后各跑一次 `gate_l0_redlines.py` + `gate_l3_ingest.py`
- **禁止 `git add -A`**，每次显式 `git add` 具体文件

---

### 3.10 模块 J —— 三处下钻专项（你追加的深入需求）

> 以下每条都有**代码行级证据 + 真实语料实测**，不是推测。

#### J-1 申论「给定材料」的图片如何定位到具体小题

**现状机制（实测）**
```
① PDF/docx 提取时，图片被替换成文本占位符 [IMAGE:{session}_{qn}_{seq}]
   question_import.py:1062   page_lines[anchor] += f' [IMAGE:{key}]'
   → 占位符挂在「图片上方最近一行」（按 top 坐标，:1034-1037）

② 申论材料抽取是「纯文本行拼接」
   text_parser.py:2632-2650  _essay_collect_materials()
     body = '\n'.join(lines[anchor:q_start])
   → [IMAGE:...] 标记**能存活**到 material_text 里

③ 但 material_text「仅第一块携带，避免重复占用内存」
   text_parser.py:2685       material_text 共享材料全文（仅第一块携带）

④ 图片落盘只按 question_id
   question_import.py:1661   _extract_and_save_images(content_text, question_id, ...)
   → **没有 group 变体**

⑤ 而前端确实会去渲染 group 的材料
   answer_page.vue:95        v-html="renderQuestionContent(state.groupMaterials[q.group_id].shared_content)"
   questions.py:623-624      render_image_placeholder(group.shared_content)
```

**⭐ 结论（这是一个此前未被记录的真缺陷）**：
`question_groups.shared_content` 里**存着 `[IMAGE:...]` 标记，但这些图片从未为「题组」落盘**。
`_extract_and_save_images` 只接受 `question_id`，而题组没有 `question_id`。
⇒ **复合题/申论的材料图片在学生端与教师端全部裂图**，且因为占位符文本被 `render_image_placeholder`
转成了 `<img src="/static/questions/{qid}/...">`，浏览器拿到的是一个**永远不存在的路径**。

**同时发现两个伴生缺陷：**

| # | 位置 | 缺陷 | 风险 |
|---|---|---|---|
| J-1a | `question_import.py:1989-1992` | 跨批复用键 = `shared_content LIKE '%'+text[:60]+'%'` + 子串包含二次校验 | 不同卷材料开头 60 字雷同（如「根据给定材料，归纳概括…」）会**误合并成一个题组**，材料互相污染 |
| J-1b | `question_import.py:2010` | `_SHENLUN_GROUP_CACHE: Dict[str,int]` 是**模块级全局字典**，无 TTL、无上限、无失效 | 长期运行**无界增长**（内存泄漏）；key 若不含 user 维度则有串号风险 |

**修复方案**
| # | 落点 | 改动 |
|---|---|---|
| J-1-1 | 新建 `question_ingest/images.py` 的 `save_images_for_group()` | 以 `group_id` 为命名空间落盘（`/static/question-groups/{group_id}/`），与 `question_id` 路径**物理隔离** |
| J-1-2 | `questions.py:623-624` | `render_image_placeholder` 增加 `owner='group'` 参数，生成 `/static/question-groups/{gid}/...` |
| J-1-3 | `question_import.py:1989-1992` | 复用键从「前 60 字 LIKE」改为**内容 SHA256 全文指纹**（`hashlib.sha256(normalized_text)`），彻底消除误合并 |
| J-1-4 | `question_import.py:2010` | `_SHENLUN_GROUP_CACHE` 改为 `functools.lru_cache(maxsize=256)` + 提供 `clear()`，并在导入批次结束时清理 |
| J-1-5 | L3 门禁新增断言 9 | 复合题入库后，`shared_content` 中的每个 `[IMAGE:xxx]` 都必须有对应的落盘文件（**缺一即失败**） |
| J-1-6 | E2E-10（新增） | 申论卷导入后，教师端预览 + 学生端作答，材料区图片**全部正常显示，零裂图** |

#### J-2 行测资料分析的材料表跨页归属

**现状机制（实测）**
```
① 图片→题号 的归属规则：取「图片上方最近一行的所属题号」
   question_import.py:1034-1039
     for i, lt in enumerate(line_tops):
         if lt <= top: anchor = i; qn = qn_at.get(i, 0)
     if qn <= 0: qn = carry_in_qn or cur_qn

② 跨页延续：carry_in_qn = cur_qn（:1011），注释 :1008-1010 已说明
   「实测漏修此点会丢掉第 6 页的两张图（其题号 40 在第 5 页）」

③ 但表格文本走的是另一条路 —— 页尾追加
   :1068-1071   text_raw = page.extract_text();  parts.append(text)      ← 页文本先入 parts
   :1082-1093   for table in page.extract_tables():
                    row_text = ' | '.join(...)
                    parts.append(row_text)                                ← 表格行后入 parts
```

**⭐ 结论（两个错位机制）**：

| # | 缺陷 | 后果 |
|---|---|---|
| **J-2a** | **表格文本是 `parts.append`（页尾追加），不是按行坐标原位插入** | 资料分析的材料表内容被移到**该页末尾**，脱离了它原本所属的材料块。若该页还有题号行，表内容会被划给**错误的题块** |
| **J-2b** | **材料表通常没有题号行** → `qn_at[i]` 全部继承 `carry_in_qn`（上一页题号） | 材料表的图片被归属到**上一页的最后一题**，而不是材料块。资料分析「材料在前、题目在后」的典型版式必然错位 |
| J-2c | `_norm_for_dedup(row_text) in page_norm` 是**子串包含**判重（:1090） | pdfplumber 单元格文本与 `extract_text()` 的空白/换行差异极易导致**漏判重复** → 全文翻倍（历史实测 14,436 → 28,873 字符、题号 70 → 140） |

**修复方案**
| # | 落点 | 改动 |
|---|---|---|
| J-2-1 | `question_import.py:1082-1093` | 表格行改为**按 `top` 坐标插入到 `page_lines` 的正确位置**（用 `line_tops` 二分定位），不再页尾追加 |
| J-2-2 | 新建 `question_ingest/matdetect.py` | 材料块起始判定：`（一）（二）` 全角括号独占行（已有锚点，见行测方案 S6）**或** 该页连续 N 行均为表格且无题号 → 标记为「材料页」，其图片归属到**后继第一个题号**而非前题 |
| J-2-3 | `question_import.py:1038-1039` | `qn <= 0` 与「材料页」两种情形分别处理：前者回落 `carry_in_qn`，后者指向**后继题号**（需前瞻扫描 `page_lines`） |
| J-2-4 | L1 门禁新增指纹键 | `材料块数` 与 `材料页表格行归属正确率`（行测基线：364 块，越界 0） |
| J-2-5 | L2 门禁新增守卫 | 断言「材料块内不得含题号」+「材料块的图片不得归属到前一题号」 |
| J-2-6 | E2E-11（新增） | 用 `题库\行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）题本.pdf` 实测：资料分析 5 个材料块，块内表格完整、块内无题号、块内图片全部归到本块 |

#### J-3 Excel 表格按列名映射的容错字典

**现状（`question_import.py:505-534` `_normalize_question`）**
```python
content  = row.get('题目内容') or row.get('题干') or row.get('question') or row.get('题目') or ''
answer   = row.get('答案')   or row.get('正确答案') or row.get('answer') or row.get('标准答案') or ''
subject  = row.get('科目')   or row.get('科目大类') or row.get('subject') or '行测'
raw_type = (row.get('题型') or row.get('题目类型') or row.get('type') or '').strip()
options  = 选项A..H / 裸 A..H / 选项|options(JSON串)
if not content or not answer: return None      ← ★ 静默丢行，无日志无计数
```

**⭐ 结论（6 个缺口，全部会导致「导入成功但数据错误/缺失」）**

| # | 缺口 | 后果 |
|---|---|---|
| **J-3a** | **不读「解析/答案解析/analysis/explanation」列** | Excel 导入的题**解析必然为空**（与你 README 里「232 道公专空解析」同源） |
| **J-3b** | **不读 分值/score、难度/difficulty、来源/source、知识点/考点 列** | 这四类元数据全部丢失，只能靠 `_auto_detect_tags` 猜 |
| **J-3c** | `if not content or not answer: return None` | **静默丢行**，无 logger、无计数、无返回报告 → 违反「不许静默丢题」硬约束，且无法排查 |
| **J-3d** | 表头**只取 `rows[0]`**，无表头行探测 | 真实题库 Excel 常在第 1 行放标题说明 → 整表解析失败或全表 `None` |
| **J-3e** | 列名**只做首尾 `strip()`** | `题 目 内 容`（全角空格）、`题目内容\n`、`Question Content`（大小写）、`题目内容：`（带冒号）全部匹配失败 |
| **J-3f** | `_parse_csv_buffer` 用 `buf.decode('utf-8-sig')` | **Windows 导出的 GBK CSV 直接抛 UnicodeDecodeError**（无 try/except，无编码嗅探） |
| J-3g | `wb.active` 只取第一个 sheet | 多 sheet 题库文件只导第一个 |

**修复方案：建立「单一容错字典」**
| # | 落点 | 改动 |
|---|---|---|
| J-3-1 | 新建 `question_ingest/excel_reader.py` 的 `COLUMN_ALIASES` | **唯一事实来源**的列名容错字典，覆盖 题干/答案/解析/题型/分值/难度/来源/知识点/选项 A-H，**每个语义 ≥ 8 个别名** |
| J-3-2 | 同上 `normalize_header()` | 表头归一：去首尾空白 + 全角空格转半角 + 去换行/制表 + 去尾部冒号 + **大小写不敏感** + 去括号备注 |
| J-3-3 | 同上 `detect_header_row()` | 前 5 行逐行打分（命中别名词数最多者即为表头行），解决 J-3d |
| J-3-4 | `_parse_csv_buffer` | 编码嗅探顺序 `utf-8-sig → gbk → gb18030 → latin-1`，全部失败才报错；**不得抛未捕获异常** |
| J-3-5 | `_normalize_question` 的丢行分支 | 改为**返回结构化丢弃报告** `{'row': idx, 'reason': '缺题干'|'缺答案', 'raw': {...}}`，由 `/batch-parsed` 汇总进 `failed_items`，前端可见 |
| J-3-6 | `_parse_excel_buffer` | 遍历全部 sheet（`wb.worksheets`），或至少提供 `sheet=0` 参数 + 明确日志 |
| J-3-7 | L3 门禁新增断言 10 | Excel 路径：传入 3 行 → 库中恰好 3 题；**含解析列的必须落库**；缺答案行必须出现在 `failed_items` 而非静默消失 |
| J-3-8 | **本轮不新建真实 Excel 测试文件**（遵守你的禁令）→ L3 的 Excel 断言改用**从真实 docx 解析结果反向构造的内存 DataFrame**（非文件），或直接对 `_normalize_question` 做纯函数单测 | 见 §3.11 硬规则 4 |

---

### 3.11 Playwright 实地测试 —— 代表性真实语料清单

> **你的硬要求（不可协商）**：
> 1. **不准导入虚拟或空的文档**做导入测试；
> 2. **不需要全部测试**，挑选代表性的进行 Playwright 实地测试；
> 3. 测试数据**必须**来自 `题库\行测`、`题库\申论`、`题库\公安题目（打印）`、`题库\答案解析（不用打印）`。

#### 3.11.1 硬规则（写进门禁，违反即判测试无效）

| # | 规则 |
|---|---|
| 1 | 每个测试用例必须声明其使用的**真实文件绝对路径**，执行前校验 `os.path.getsize > 0` 且文件头合法 |
| 2 | **禁止**任何 `b"fake content"`、`'x'*100`、`新建空 .docx/.pdf` 之类的构造文件进入**导入链路**测试 |
| 3 | 单元测试层面允许构造内存数据，但**仅限纯函数**（如 `_normalize_question`），**不得**用于验证上传/解析/入库链路 |
| 4 | 每条 E2E 证据必须包含：**文件名 + 字节大小 + SHA256 前 16 位 + 后端 `import_id`** 四要素，否则视为无效证据 |
| 5 | 测试产生的 `question_import_record` 与 `question_bank` 行**必须清理或标记**（用 `qa_tag` 前缀区分），**不得污染 2583 题公专基线** |
| 6 | 测试前 DB 备份；测试后跑 `gate_l1_parser.py --subject gongzhuan` 确认公专 2899 基线未变 |

#### 3.11.2 八个代表性真实语料（全部已核实存在于磁盘）

| # | 科目 | 路径（相对 `题库\`） | 大小 | 覆盖目标 |
|---|---|---|---|---|
| **S1** | 公专 | `公安题目（打印）\2020届公安院校公安专业联考考试《公安专业科目》真题.docx` | **6.33 MB** | ★ **RC-1 慢轮询复现**（语料最大 Word）、分离导入题目文档、图片占位符协议、J-1 材料图片 |
| **S2** | 公专 | `答案解析（不用打印）\2020届公安院校公安专业联考考试《公安专业科目》真题参考答案及解析.pdf` | — | 与 S1 配对做**分离导入**（题目 docx + 答案 pdf 跨格式） |
| **S3** | 公专 | `公安题目（打印）\2016江西招警考试《人民警察基础知识》真题（部分）.docx` | 0.09 MB | ★ **畸形 docx**（`_sanitize_docx_rels` 注释点名）+ **「（部分）」命名异常** |
| **S4** | 公专 | `答案解析（不用打印）\2016江西招警考试《人民警察基础知识》真题答案及解析（部分）.pdf` | 0.40 MB | 与 S3 配对，验证**命名异常下的分离匹配** |
| **S5** | 公专 | `公安题目（打印）\2017年公安院校联考《公安专业科目》题.docx` | 3.86 MB | ★ **合并导入**（单文档含题+答案+解析） |
| **S6** | 行测 | `行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）题本.pdf` | 0.85 MB | ★ **副省级**（历史 60% 静默丢弃 + 三变体重复率异常的重灾卷）、J-2 资料分析跨页材料表、分区折叠 + 考点标签 |
| **S7** | 行测 | `行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）答案解析.pdf` | 0.98 MB | 与 S6 配对做**行测分离导入**（答案锚点切分 + 配对安全网） |
| **S8** | 申论 | `申论\2019年国家公务员考试《申论》真题及答案（省级）（含解析）.pdf` | 0.25 MB | ★ **正确阻断样本**（历史记录 5 块 / 答案 4 / 阻断 5）—— 用来**验证阻断仍生效**，**不是**用来修它 |
| **S9** | 申论 | `申论\2020年国家公务员考试《申论》真题及答案（地市级）.pdf` | 0.21 MB | ★ **申论正常样本**：一个整题（材料+要求）→ 逐小题各带答案+解析；J-1 材料图片 |

> **合计 9 个真实文件、4 个科目场景、8 类缺陷形态**（大文件 / 畸形 docx / 命名异常 / 合并 / 分离 / 跨格式 / 正确阻断 / 正常复合题）。
> **不跑全量 170+254 份** —— 全量验证由 L1/L2 门禁脚本承担，Playwright 只做**端到端抽样**。

#### 3.11.3 Playwright 用例映射

| 用例 | 语料 | 操作序列 | 通过标准 |
|---|---|---|---|
| PW-1 | S1 → S2 | 分离导入：先传 S1（docx）→ 预览 → 再传 S2（pdf 答案）→ 匹配 | **全程无「signal is aborted」**；`import_id` 只有 2 条（不重复）；匹配率 100%；预览显示题干/选项/答案/解析四区 |
| PW-2 | S1 | 观察后端日志 | `current_phase` 依次 `READING→EXTRACTING→IMAGES→SPLITTING→MATCHING→BUILDING→DONE`；进度百分比单调上升无回退 |
| PW-3 | S1 | 预览中改第 1 题答案 → 确认入库 | 库中该题 `answer` = 改后值（RC-3 证据）；`success_count` = 预览题数 |
| PW-4 | S5 | 合并导入（单文档含解析） | 一键完成；`answer_analysis` 非空率 > 90%；解析分点正确换行显示 |
| PW-5 | S3 + S4 | 畸形 docx + 命名异常配对 | S3 能被清洗后打开（有 warning 日志）；S3↔S4 题数一致或明确阻断，**绝不按序硬配** |
| PW-6 | S6 → S7 | 行测分离导入 | 5 个分区折叠正确、考点标签显示、资料分析 5 个材料块块内无题号、blocked=0 |
| PW-7 | S6 | 教师端题目管理查看该卷 | 与导入预览**形态一致**（同一组件渲染） |
| PW-8 | S9 | 申论导入 → 教师端预览 | 一个整题：材料块（可折叠）+ 题目要求 + 逐小题的答案/解析；`requirements` 非空 |
| PW-9 | S9 | 学生端作答该复合题 | 材料在上，竖向滑动贯穿全部小题，答案各自独立保存不互相覆盖；**材料图片零裂图**（J-1） |
| PW-10 | S8 | 申论省级卷导入 | **必须被阻断**，显示「答案段数与题目数不匹配」中文原因；**库中零新增** |
| PW-11 | 任一 | 把 S6 复制并改名 `.docx` 后上传 | 日志出现扩展名/文件头不一致 warning，**仍能正确解析**（RC-6 证据） |
| PW-12 | — | 导入 S1 后**刷新浏览器** | 能重新挂上已有 `import_id` 的预览，**不必重传**（A-7 证据） |

**证据落盘**：`.omo/evidence/pw-{用例号}-{场景}.png` + `.txt`，每份 txt 首行固定写
`文件: <绝对路径> | 大小: <bytes> | SHA256: <前16位> | import_id: <id>`

---

## 4. 必须做 / 禁止做

### 必须做（Must Have）
- [ ] **模块 H 全 6 层门禁网**（L0/L1/L2/L3/L4/L5）+ `gate_all.py` 一键入口 + `known_broken.json` 债务登记
- [ ] 模块 A 全部 8 项（上传轮询稳定性 + 文件头嗅探）
- [ ] 模块 B 全部 7 项（入库链路统一 + `confirmed_items` 修复 + blocked 闸门）
- [ ] 模块 C 的 C-1、C-3、C-5、C-6
- [ ] 模块 D 的 D-1、D-2、D-3、D-4、D-5
- [ ] 模块 E 的 E-1、E-2、E-3、E-4
- [ ] 模块 F 的 F-1、F-2、F-3
- [ ] 模块 G 的 G-1、G-2、G-3、G-4、G-9、G-10
- [ ] **模块 I 全部 10 步**（I-0 门禁 → I-9 行测平移），每步独立 commit
- [ ] **模块 J 全部三处下钻**：J-1（申论材料图片归属 + 误合并 + 缓存泄漏）、J-2（行测跨页材料表错位）、J-3（Excel 列名容错字典 + 静默丢行）
- [ ] **§3.11 的 9 个代表性真实语料 Playwright 全量执行**（PW-1..PW-12）

### 禁止做（Must NOT Have · 违反即回滚）
- [ ] 不改 `text_parser.py::extract_question_blocks` **函数体**（字节级红线，位移无关比对）
- [ ] 不改 `question_import.py:4005-4011` 共享 dispatch 块（字节级未改）
- [ ] 不新建题号解析器 / 答案归一化 / 题型判定 / 题组表 / OCR 服务
- [ ] 公专 2583 题**逐字段不变**（G1 门禁 5 项数字逐项一致）
- [ ] 不改 `.vtj/vue/question_import.vue` 的 `<template>`（1–493 行）
- [ ] 不改 `.vtj/files/question_import.json`（`raw: true` 页禁止同步 DSL，同步工具有损）
- [ ] 不改 `useProvider({ id:'question_import', version:'1790329880372' })` 的 version
- [ ] 不调 `vtj_sync_vue_to_dsl` / `vtj_vtj_write_*`
- [ ] 不动 DB 备份、`text_cache.bak_20261001_200518`、429 条 PREVIEW（无单独授权）
- [ ] 不写库前不备份；WAL 库必须用 `sqlite3` 备份 API，禁止 `shutil.copy2`
- [ ] SQL 里不写中文（PowerShell 传递会静默损坏 where 条件）；一律 Python 侧 `\uXXXX` 取 id 再按数字 IN
- [ ] 不允许静默丢题 / 盲配 / 伪造答案解析；缺答案缺解析**留空**
- [ ] 不用 `git add -A`；不 `git checkout` / `reset` / `clean`
- [ ] **禁止用虚拟文件 / 空文件 / 构造的假内容做导入链路测试**（见 §3.11 硬规则 1-4）——
      单元测试层面构造内存数据仅限纯函数，且不得用于验证上传/解析/入库链路
- [ ] **禁止用未标注 `qa_tag` 的测试数据污染 2583 题公专基线**；每轮 E2E 后必须跑
      `gate_l1_parser.py --subject gongzhuan` 确认基线未变
- [ ] **I-6（平移 pdf_reader.py）必须单独 commit + 单独跑全套 E2E**（你的裁决：保质保量，不越改越退）

---

## 5. 验收门禁

工作目录统一 `D:\砺安题库\砺安题库\backend`，先设编码：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING='utf-8'
```

### 5.1 硬门禁（模块 H 建好后，以此为准；旧的 G1–G4 全部并入新门禁网）

**一键执行**：
```powershell
cd D:\砺安题库\砺安题库\backend
python scripts/gate_all.py                 # 全量 L0-L5
python scripts/gate_all.py --quick         # L0+L1，秒级，进 pre-commit
python scripts/gate_all.py --layer L3      # 只跑落库链路
python scripts/gate_all.py --subject xingce  # 只跑某科
```

| 层 | 脚本 | 耗时 | 通过标准 |
|---|---|---|---|
| **L0** 红线 | `gate_l0_redlines.py` | ~1s | 6 个 SHA256/字面量断言**全部**匹配（`extract_question_blocks` 函数体、dispatch 块、`question_import.json`、`question_import.vue` 第 1-493 行、`useProvider` version、公专路径未被改道） |
| **L1** 指纹 | `gate_l1_parser.py` | ~60s | 三科 JSON 指纹**逐键**与基线一致；公专必须精确 = 2899 块 / 污染 0 / `{'单选题':2534,'多选题':249,'判断题':80,'简答题':36}` / `{'4':2796,'1':13,'2':14,'0':73,'3':3}` / PASS |
| **L2** 匹配 | `gate_l2_matching.py` | ~180s | 行测分节序列全等 / 区间一致 / 答案覆盖 100% / blocked=0 / **图形推理指令句未被判同题**；申论 `answer_block_count_mismatch` = 0（白名单除外） |
| **L3** 落库 | `gate_l3_ingest.py` | ~20s | **8 条断言全绿**（见 §3.8.2 L3 表）。用内存临时库，不触碰真实 DB |
| **L4** API | `gate_l4_api_contract.py` | ~15s | openapi 快照一致；401/403/404/409/422/500 各分支校验通过；经 9527 代理实请求非 502 |
| **L5** 前端 | `gate_l5_frontend_contract.py` | ~10s | 必需标识符全部存在；**禁止** `state.batchPreviewData.length` 等读错字段写法；Playwright 运行时渲染出材料+小题+答案解析 |
| **L6** pytest | 现有 `pytest` | — | 失败集合与基线 `16 failed / 168 passed / 52 errors` 完全一致（本轮不收敛，52 errors 须登记进 `known_broken.json`） |

> **判定标准**：任一层非 0 → **立即停止，不进下一阶段**。
> **新增失败项即为回归**，不得只看总数。

### 5.2 端到端验收（逐条留证 `.omo/evidence/`）

| 编号 | 场景 | 通过标准 |
|---|---|---|
| E2E-1 | 上传 6.33 MB `.docx`（2020届公安院校…真题） | 全程无「signal is aborted」；`app.log` 出现 `current_phase=DONE`；**只产生 1 条** import 记录 |
| E2E-2 | 上传 PDF 改名 `.docx` | 日志出现扩展名/文件头不一致 warning，**仍能正确解析** |
| E2E-3 | 预览改 1 道题的答案后确认入库 | 库中该题答案 = 改后值；响应 `success_count` = 预览题数 |
| E2E-4 | 构造含 `blocked` 题的批次 | 返回 409，`block_reasons` 为中文可读；**库中零新增** |
| E2E-5 | 行测题本 + 答案解析分离导入 | 分区折叠正确、考点标签显示、匹配率 100%、blocked=0 |
| E2E-6 | 申论合并导入 | 一个整题（材料+要求）→ 逐小题各带答案+解析；`requirements` 非空行数 > 0 |
| E2E-7 | 复合题学生端作答 | 材料在上，竖向滑动贯穿全部小题，答案各自独立保存不互相覆盖 |
| E2E-8 | 教师端/管理员端题目管理 | 与导入预览**形态一致**（同一组件渲染） |
| E2E-9 | 公专 2583 题 | `subject_id` / `type_id` / `options` / `answer` / `answer_analysis` 逐字段与备份一致 |
| **E2E-10** | 申论复合题**材料图片**（S9） | 教师端预览 + 学生端作答，材料区图片**全部正常显示，零裂图**；`shared_content` 中每个 `[IMAGE:xxx]` 都有落盘文件（J-1） |
| **E2E-11** | 行测**资料分析跨页材料表**（S6） | 5 个材料块，块内**无题号**、块内表格完整、块内图片全部归到本块（不落前题）（J-2） |
| **E2E-12** | **畸形 docx + 命名异常**（S3↔S4） | S3 被清洗后打开（有 warning）；S3↔S4 题数一致或明确阻断，**绝不按序硬配** |

### 5.3 VTJ 改动自检（每次改 `.vue` 后）

```powershell
git diff --stat -- .vtj/files/question_import.json          # 必须为空
Select-String -Path .vtj/vue/question_import.vue -Pattern 'useProvider\(\{'  # version 不得变更
git diff --stat -- .vtj/vue/question_import.vue              # template 段(1-493行) 必须无改动
```
改完 `.vue` 后**必须实际请求 Vite**（`http://localhost:9527/` 返回 200），不能只靠 SFC 编译通过。

---

## 6. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 | 回滚 |
|---|---|---|---|---|
| 模块 B 改动波及公专落库 | 中 | 高（2583 题基线受损） | G1 门禁 + E2E-9 逐字段比对 | 恢复 DB 备份（sqlite3 备份 API） |
| 状态接口瘦身导致前端拿不到结果 | 中 | 中 | 前端先兼容：新字段缺失时回落旧 `result` | 还原 `question_import.py` 单个函数 |
| 统一入库组件改动 `teacher/admin` 题管页 | 中 | 中 | 只替换渲染块，不动 API 调用 | `git checkout` 单文件（**需确认无他人未提交改动**） |
| MinerU 提为扫描件第一顺位后耗时上升 | 低 | 中 | 保留 PaddleOCR 二顺位 + 引擎名日志 | D-1 单点回滚 |
| 清理测试脚本误删仍被引用的文件 | 低 | 高 | 逐个 grep 引用 + 移入 `_archive/` 而非删 | 从 `_archive/` 移回 |
| 清理 429 条 PREVIEW 误删有价值数据 | — | 高 | **本方案不动**，需单独授权 | — |

**DB 备份（写库前必做，WAL 库禁用 copy2）**：
```python
import sqlite3, datetime
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
src = sqlite3.connect('data/question_bank.db'); dst = sqlite3.connect('data/question_bank.db.bak_import_%s' % ts)
with dst: src.backup(dst)      # ★ 不要用 shutil.copy2
dst.close(); src.close()
```
回滚时覆盖主库并**同时删除 `-wal` 与 `-shm`**。

---

## 7. 分阶段实施顺序（依赖驱动，可并行）

```
阶段 0（前置 · 无依赖 · 全部只读或纯增量）
  ├─ 0-1 ★ 归档本方案到 solve_problems_files/ + 更新该目录 README 索引
  ├─ 0-2 DB 备份（sqlite3 备份 API）+ 记录基线快照（题目 2583 / groups 21 / requirements 0 / PREVIEW 429）
  ├─ 0-3 跑旧 G1/G2/G3/G4 记录真实现状基线
  ├─ 0-4 复现 RC-1（构造慢轮询）与 RC-2（点确认入库）各留一份证据
  └─ 0-5 G-3 删除清单：逐个 grep 全仓引用 + 写入 .omo/evidence/task-delete-manifest.txt

★ 阶段 1（门禁网 · 必须先于一切改动）
  ├─ 1-1 L0 gate_l0_redlines.py（6 个哈希/字面量断言，秒级）
  ├─ 1-2 L3 gate_l3_ingest.py（内存临时库 + 8 条落库断言）★ 最关键
  ├─ 1-3 L1 gate_l1_parser.py（三科结构化指纹，升级 G1）
  ├─ 1-4 L2 gate_l2_matching.py（继承 G2/G3 + 2 条历史回归守卫）
  ├─ 1-5 L4 gate_l4_api_contract.py（归并 verify_task11_* 三个零散脚本）
  ├─ 1-6 L5 gate_l5_frontend_contract.py（含 RC-2 专属反向守卫）
  ├─ 1-7 gate_all.py 一键入口 + last_run.json + known_broken.json 债务登记
  └─ 1-8 接 pre-commit（L0）与 CI（L0+L1+L3）
     ⚠️ 1-2 必须先红：它要先复现出 RC-3/RC-4/RC-5 的失败，修完才转绿

阶段 2（并行 · 稳定性与必现缺陷）
  ├─ 2-1 A-1/A-2/A-3/A-4 前端超时/重试/错误文案（含 RC-1 复验）
  ├─ 2-2 A-5/A-6/A-7 后端状态接口瘦身 + 去掉同步兜底 + 预览重挂
  ├─ 2-3 A-8 + I-1 文件头嗅探 magic.py（RC-6）
  └─ 2-4 RC-4 confirmed_items 修复（独立、低风险、单独 commit）

阶段 3（核心 · 严格串行 · 每步跑 L0+L3）
  ├─ 3-1 B-1 前端 pendingQuestions 单一事实来源（RC-2）
  ├─ 3-2 B-2/B-3 batch-parsed 接 requirements/group_id（RC-5）
  ├─ 3-3 B-4 batch-parsed 补 blocked 闸门
  ├─ 3-4 B-5/B-6 confirm 改造（RC-3）
  └─ 3-5 → 立刻跑 E2E-3 / E2E-4 / E2E-9 + L0+L3 全绿

阶段 4（并行 · 识别与渲染）
  ├─ 4-1 C-1/C-5/C-6（公专回归用例 / 分离合并统一三方校验 / 省份只从文件夹取）
  ├─ 4-2 E-1 后端 members 补 requirements
  ├─ 4-3 E-2 共用渲染组件
  ├─ 4-4 E-3/E-4 teacher/admin 接入
  └─ 4-5 D-1..D-5 MinerU 分层主库 + 引擎名可见

阶段 5（并行 · 学生端 + 治理）
  ├─ 5-1 F-1/F-2/F-3 answer_page + mobile/tablet 接入共用组件
  ├─ 5-2 G-1 日志 UTF-8 与轮转 + G-2 README 重写 + G-3/G-4 脚本删除（分批，每批后 L0+L1）
  └─ 5-3 ★ Playwright 实地测试 PW-1..PW-12（9 个真实语料，S1..S9）

阶段 6（并行 · 三处下钻专项 · 必须在 E2E 抽样前完成）
  ├─ 6-1 J-1-1/J-1-2 group 图片落盘通道 + render_image_placeholder owner 参数
  ├─ 6-2 J-1-3 材料复用键改 SHA256 + J-1-4 缓存改 lru_cache   ★ 修误合并与内存泄漏
  ├─ 6-3 J-2-1 表格行按 top 原位插入（不再页尾追加）
  ├─ 6-4 J-2-2/J-2-3 材料页识别 + 归属指向后继题号
  ├─ 6-5 J-3-1..J-3-6 Excel 容错字典 + 表头归一 + 表头探测 + GBK 嗅探 + 丢弃报告化
  └─ 6-6 L3 新增断言 9/10 + L1 新增指纹键 + L2 新增材料守卫

阶段 7（拆分 · 每步独立 commit，前后各跑 L0+L3）
  ├─ 7-1  I-2 excel_reader   7-2  I-3 docx_reader   7-3  I-4 tags
  ├─ 7-4  I-5 images        7-5  ★ I-6 pdf_reader（单独 commit + 单独全套 E2E）
  ├─ 7-6  I-7 upsert+links  7-7  I-8 groups 收敛
  └─ 7-8  I-9 行测三函数 → text_parser/xingce.py（唯一动 text_parser 的步骤）

阶段 8（最终 · Playwright 复验）
  └─ 8-1 ★ 用同一批 9 个真实语料**全量复跑** PW-1..PW-12，证明拆分后行为零变化

阶段 FINAL
  ├─ F1 计划合规审计（oracle）
  ├─ F2 代码质量审查
  ├─ F3 真实端到端 QA（逐条跑 E2E-1..12 + PW-1..12）
  └─ F4 范围忠实度核查

关键路径：0-2 → 1-1 → 1-2 → 3-1 → 3-2 → 3-3 → 3-4 → 3-5 → 6-1..6-6 → 5-3(PW 抽样) → 7-1..7-8 → 8-1(PW 复验) → FINAL
并行度：阶段 2（4 路）、阶段 4（5 路）、阶段 5（3 路）、阶段 6（6 路）、阶段 7（8 路）
```

---

## 8. 决策点裁决结果（已确认，2026-10-04）

| # | 决策点 | **你的裁决** | 落地方式 |
|---|---|---|---|
| **1** | MinerU 定位 | ✅ **分层主库**（不做全局换血） | §3.4：扫描件 PDF → MinerU 第一顺位；文本层 PDF → pdfplumber 为主（含表格）；预览页显示本次实际引擎 |
| **2** | `.docx` 是否走 MinerU | ✅ **不走，保持原生** | §3.4：`.docx` 走现有 python-docx 弹性解析（0.1~0.35s，含悬空关系清洗 + XML 兜底） |
| **3** | 429 条 PREVIEW + 1 条 PARSING | ⏸ **本轮不动** | 仅在 §4 记录为「需单独授权」；本轮零操作 |
| **4** | 20+ 散落测试脚本 | ✅ **直接删除** | §3.7 G-3：逐个 grep 零引用 + 先写 `.omo/evidence/task-delete-manifest.txt` + 分批删除，每批后跑 L0+L1 |
| **5** | 巨型文件拆分 | ✅ **同步拆分**，且**必须先补齐三科门禁网** | §3.9 全 10 步 + §3.8 六层门禁网；门禁网（阶段 1）**严格先于**拆分（阶段 6） |
| **6** | 学生端复合题交互 | ✅ **保持竖向滚动 + 材料可折叠** | §3.6：仅补 `requirements` + 接入共用渲染组件，不做交互重做 |

> **由决策 5 派生的强制顺序**（不可颠倒）：
> **阶段 1 门禁网 → 阶段 3 修复 → 阶段 6 下钻 → 阶段 7 拆分**。
> 门禁网没建起来就拆分 = 不可控重构，这正是历史上「越改越退步」的成因。

### 8.1 三处下钻的实测结论摘要（§3.10）

| 下钻点 | 结论 | 严重度 |
|---|---|---|
| **申论材料图片 → 小题定位** | `question_groups.shared_content` 存着 `[IMAGE:...]` 标记，但图片**从未为题组落盘**（`_extract_and_save_images` 只接受 `question_id`）⇒ **复合题材料图片在教师端与学生端全部裂图**。伴生：材料复用键是「前 60 字 LIKE」会**误合并不同卷的雷同材料**；`_SHENLUN_GROUP_CACHE` 是**无界全局字典**（内存泄漏） | 🔴 高 |
| **行测资料分析跨页材料表** | 表格文本走 `parts.append` **页尾追加**，不按行坐标原位插入 ⇒ 表内容脱离所属材料块；同时材料表**无题号行**导致 `qn_at` 全部继承上一页题号 ⇒ **材料图片归属到前一题** | 🔴 高 |
| **Excel 列名容错** | 不读解析/分值/难度/来源/知识点列；`return None` **静默丢行无日志**；表头只取 `rows[0]` 无探测；列名只做首尾 strip（全角空格/大小写/尾部冒号全失配）；**GBK CSV 直接抛 UnicodeDecodeError** | 🟠 中高 |

### 8.2 Playwright 代表性真实语料（§3.11，已核实存在于磁盘）

| # | 科目 | 文件 | 大小 | 覆盖目标 |
|---|---|---|---|---|
| S1 | 公专 | `公安题目（打印）\2020届公安院校公安专业联考考试《公安专业科目》真题.docx` | **6.33 MB** | ★ RC-1 慢轮询复现 / 分离导入题目 / 图片占位符 |
| S2 | 公专 | `答案解析（不用打印）\2020届公安院校公安专业联考考试《公安专业科目》真题参考答案及解析.pdf` | — | 与 S1 跨格式分离配对 |
| S3 | 公专 | `公安题目（打印）\2016江西招警考试《人民警察基础知识》真题（部分）.docx` | 0.09 MB | ★ 畸形 docx + 「（部分）」命名异常 |
| S4 | 公专 | `答案解析（不用打印）\2016江西招警考试《人民警察基础知识》真题答案及解析（部分）.pdf` | 0.40 MB | 与 S3 配对 |
| S5 | 公专 | `公安题目（打印）\2017年公安院校联考《公安专业科目》题.docx` | 3.86 MB | ★ 合并导入（单文档含解析） |
| S6 | 行测 | `行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）题本.pdf` | 0.85 MB | ★ 历史 60% 静默丢弃重灾卷 / J-2 跨页材料表 / 分区折叠 |
| S7 | 行测 | `行测\国考行测\2023年国家公务员录用考试《行测》题（副省级网友回忆版）答案解析.pdf` | 0.98 MB | 与 S6 行测分离导入 |
| S8 | 申论 | `申论\2019年国家公务员考试《申论》真题及答案（省级）（含解析）.pdf` | 0.25 MB | ★ **正确阻断样本**（验证阻断仍生效，不是修它） |
| S9 | 申论 | `申论\2020年国家公务员考试《申论》真题及答案（地市级）.pdf` | 0.21 MB | ★ 申论正常样本：材料+要求+逐小题答案解析 / J-1 材料图片 |

> ⛔ **硬规则**：禁止用虚拟/空/构造文件做导入链路测试；每份证据必须含
> **文件名 + 字节大小 + SHA256 前 16 位 + import_id** 四要素；测试数据须打 `qa_tag` 标记，
> 每轮后跑 `gate_l1_parser.py --subject gongzhuan` 确认 2583 题基线未变。

---

## 9. 本方案**未**覆盖（诚实披露）

1. **不收敛 pytest 的 52 个 error** —— 只做分类登记（`known_broken.json`）。收敛是独立专项。
2. **不解决** 申论合订本 2019 两份的阻断 —— 当前阻断是**正确行为**，需你先确认那份 PDF
   到底是「答案多一段」还是「题目漏切一题」。
3. **不迁移** MinerU 到独立 HTTP 服务 —— 当前 CLI 子进程模式实测可用（health 3.4.5），
   仅修超时口径与串行池。
4. **不处理** 232 道公专空解析的历史数据 —— 那是源数据缺失，需用修复后的管线从原始素材重导，
   库内不可恢复。
5. **不触碰** 行测 85 套全量导入的去重口径决策 —— 该项已在 `328b0b0` 落地，本方案只做回归验证。
6. **不做** 复合题「一屏一题」的交互重做（决策 6 已定为保持竖向滚动）。
7. **不用** 真实题库全量 170+254 份做 Playwright —— 全量覆盖由 L1/L2 门禁脚本承担，
   Playwright 只做 §3.11 的 9 个代表性真实语料抽样（阶段 8 会用同一批语料**复验**一次，
   证明拆分后行为零变化）。
8. **不收敛** pytest 的 52 个 error —— 只做分类登记（`known_broken.json`）。

---

> **下一步**：本方案已按你的全部裁决与下钻要求定稿（0.0 节 → 3.11 节，共 11 个章节）。
> 1. 若还有需要下钻的部分，请直接指出；
> 2. 若认可，回一句「批准」即可 —— 我随后把 §7 的 8 个阶段展开为 `.omo/plans/` 下的
>    可执行任务清单（含每项的推荐 Agent、并行波次、Agent-Executed QA Scenarios、
>    证据路径、Commit 策略），交由 `/start-work` 由 Atlas 执行；
> 3. 执行阶段 0 的第一件事会是把本方案归档到
>    `solve_problems_files/题目导入模块全面修复与满血优化方案_v1.md`
>    并更新该目录 `README.md` 的文档索引。