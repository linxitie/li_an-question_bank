# 申论/行测/公专 三科题目导入 去粗取精式优化方案 v2

> **状态**：待审核 —— 需你批准后交由 Atlas (`/start-work`) 执行
> **版本关系**：本方案**取代** v1（`.omo/plans/shenlun-import-accuracy.md`）。v1 因"新建状态机+删除前端解析"的路线偏离了你 G6 的去粗取精要求，且未做三科取证而被否决。
> **取证依据**：`.omo/drafts/three-subject-forensics.md`（直接驱动现有 `text_parser.py` 对仓库真实语料运行所得）
> **归档**：本文件由 Prometheus 写在 `.omo/plans/`；任务 T0 会复制到 `solve_problems_files/`（你的 G2 要求）

---

## 0. 本方案与 v1 的根本差异

| 维度 | v1（被否决） | **v2（本方案）** |
|------|-------------|---------------|
| 技术路线 | 新建 `ShenlunParser` 状态机 + 删除前端解析逻辑 | **在现有 `extract_question_blocks` 前插入"区段路由"，后加"块后处理"；切分器本身不动** |
| 三科关系 | 只做申论，公专/行测仅保不退化 | **三科先取证再定范围**；识别出三科共有的图片架构瓶颈（不需重写解析器） |
| 依据 | 推测为主 | **每项改造均有实测证据**，含一组已验证有效的最小改动实验 |
| 阶段划分 | 11 阶段粗粒度 | **见 §7，粒度细化到 1-3 文件/任务** |

---

## 1. 取证结论（方案地基）

### 1.1 三科健康度实测

| 科目 | 题目侧 | 答案侧 | 判定 |
|------|--------|--------|------|
| 公专 | 100/85/97 块，题号 1..N 连续，options 99–100% | `smart_match` rate **0.99–1.0**，`answer='B'`+解析正确注入 | ✅ **健康** |
| 行测 | 130 块，题号 1..130 连续，options 130/130 | rate **0.9923**，答案+解析正确注入 | ✅ **题目/答案健康** |
| 申论 | **真题召回 0/5** | 全部 None | ❌ **崩溃** |

### 1.2 关键实验：最小改动即可救回申论召回率

对 `2018…《申论》真题卷及答案（副省级）.pdf`（真值 5 题）实测：

| 步骤 | 结果 |
|------|------|
| 现状：全文喂 `extract_question_blocks` | **7 块**，块1–6 = 「一、注意事项」的考试说明，块7 题号=21（材料正文数字）→ **召回 0/5** |
| **仅定位「三、作答要求」区段（@6950）到首个「参考答案：」（@7498），只把这段喂现有切分器** | **5 块**，题号 1..5，与 5 个分值锚点一致 → **召回 5/5** |

区段内 5 块的实际内容（暴露剩余唯一问题）：

| 块 | 题号 | 内容 | 判定 |
|----|------|------|------|
| 1 | 1 | `（1）根据"给定资料1"，…（15分） 要求：（1）准确、全面；` | ✅ |
| 2 | 2 | `（2）恰当提炼，条理清晰；` | ❌ 要求子项 |
| 3 | 3 | `（3）不超过350字；（2）上级部门来W市考察…（20分） 要求：（1）紧扣资料…` | ❌ 要求子项 + 真题2 粘连 |
| 4 | 4 | `（4）…（10分）` | ✅ |
| 5 | 5 | `（5）…写一篇文章。（40分）` | ✅ |

→ **区段路由解决召回；剩余需求子项归并，一个纯后处理步骤即可。**

### 1.3 三科共有的架构瓶颈：图片映射（P4/P5/P6）

行测 `2023…地市级题本.pdf`：29 页 / 35 张图，逐页实测：

| 页 | 图数 | 尺寸 | 对应题 | 性质 |
|----|------|------|-------|------|
| 11 | 5 | 15×33 ×4 + 178×194 | 61–65 | 小图标 + 1 图 |
| 12 | 4 | 15×33 ×2 + 22×33 ×2 | 66–67 | 小图标 |
| 13 | 3 | **584×275 / 581×271 / 600×283** | 72–73 | 大图表 |
| 14 | 2 | **489×574 / 493×198** | 74–76 | 大图表 |
| 15 | 2 | 363×246 / 570×368 | 77–78 | 大图表 |
| 16 | 2 | 547×427 / 531×415 | 79–80 | 立体图形 |
| 17 | **1** | **557×434** | **81–83** | **1 图服务 3 题** |
| 18 | 1 | 600×225 | 84–86 | 图表 |

三条硬事实：
1. **尺寸两极**：`15×33`（应过滤）vs `584×275`（必须保留）
2. **1 图 → N 题**（第14页 2 图 → 74/75/76；第17页 1 图 → 81/82/83）
3. **N 图 → 1 题**（第15页第77题需第77、78两图）

而 `extract_question_blocks` 返回字段**无任何 image**：
```
['analysis','answer','content','format','options','question_number','question_type','suspicious','type_confidence']
```
图片走独立路径 `question_import._extract_and_save_images`（`question_import.py:1630`），与题目切分**无关联依据** → 按页提图按页分配必然串题（这正是历史方案《题目导入图片重复串题问题优化方案》所指）。

`question_image` 表为 `question_id + image_path` 的 **N:1**，`image_type` 实测**仅 `'题干图'`**（263 行） → **无法表达 1:N / N:1 / 多类型**。

### 1.4 申论两种形态两种病因

| | 合并模式（合订本） | 分离模式（题目PDF+答案PDF） |
|---|------------------|------------------------|
| 病因 | 不识别「一、注意事项」为噪声 | 不区分「题号」与「要求子项」（括号样式相同） |
| 证据 | 注意事项 5 条 → 块1–6 | `（2）分条列出；` 被当独立题 |
| 附加 | 参考答案被写入 **`analysis`** 而非 `answer`；块7 题号=21 | `score=1`（真实15/20/25）；答案文档被判 `单选题` |

### 1.5 其余已确认缺陷

| # | 缺陷 | 证据 |
|---|------|------|
| P7 | `suspicious` 只标记不阻断 | 块7 `suspicious=True` 仍可确认入库 |
| P8 | MinerU 只收 `*.md`，图片全丢 | `mineru_service.py:160` |
| P9 | Tesseract 函数错置在 MinerU 服务 | `mineru_service.py:190-255` 用 `pytesseract` |
| P10 | 多余答案号 | 公专 `extra_answer_numbers=[40]` |
| P11 | `question_subject` 无申论行；`question_type` 8 题型全绑 `subject_id=3` | 实测查询 |
| P12 | models.py 声明 `Enum` vs 实际 `VARCHAR(5)` 漂移 | `models.py:193` vs `PRAGMA table_info` |
| P13 | `preview_data` 双重编码 | 代码自认 `question_import.py:213` |
| P14 | `.vtj/files/question_import.json` state 5 个碎片键 + `nodes=null` | `stats='{ total_questions: 0'` 等 |
| — | 公专/行测回归基线健康，必须保持 | `parser_regression.txt` 30份/2899块 PASS |

---

## 2. 优化范围（按你确认的"聚焦"）

| 类别 | 涉及缺陷 | 涉及科目 | 是否动解析器 |
|------|---------|-----------|------------|
| **① 申论解析器** | P1 区段识别 / P2 要求子项归并 / P3 answer-analysis 字段纠偏 | 申论 | ✅ 是（最小增量） |
| **② 三科共有图片映射架构** | P4 schema 表达力 / P5 图片与题目关联依据 / P6 图片对解析层可见 | **三科** | ❌ 否（独立路径 + schema） |
| **③ 主数据与前端隐患** | P11 申论科目/题型 / P14 VTJ DSL 损坏 | 申论 + 前端 | ❌ 否 |
| **④ G6 冗余清理** | P8 MinerU 图片 / P9 Tesseract 归位 / P13 双编码 | 三科 | ⚠️ 仅 MinerU 返回值 |

**明确不做**：不重写公专/行测的题目切分与答案匹配逻辑（取证证明其正确）；不删除前端任何方法（见 §6 的重新定位）。

---

## 3. 改造块 A：申论解析器（最小增量，不重写）

### A-1 区段路由 `SectionRouter`（新增，落在 `text_parser.py` 内）

```
新增函数 _route_sections(text) -> Optional[SectionMap]
  SectionMap: { noise:[ranges], material:(start,end), question:(start,end), answers:[ranges] }

在 extract_question_blocks 入口调用：
  sec = _route_sections(text)
  if sec is None:  → 走原路径（行测/公专命中这里，行为零变化）
  else:            → 只对 sec.question 区段执行原有切分逻辑
```

**识别锚点**（均已在语料中验证存在）：

| 区段 | 锚点正则 | 容错 |
|------|---------|------|
| 噪声 | `^[一二三四五六七八九十]+、\s*注意事项` | 也兼容 `注意事项` 单独成行 |
| 材料 | `^[一二三四五六七八九十]+、\s*给定材料\|给定资料` | 兼容无「一、」直接以 `材料1`/`给定资料1` 开头的卷 |
| 问题 | `^[一二三四五六七八九十]+、\s*作答要求` | 兼容 `作答要求` 单独成行 |
| 答案 | `参考答案\s*[:：]`（**必须带冒号**） | ⚠️ 不可用 `参考答案` 字样计数 |

> **为何必须带冒号**：实测 254 份，D1 十份中 5 份 `参考答案` 字样数 ≠ 分值锚点数（7/4、10/5、14/9、11/5、6/3），因"参考答案说明"亦含该字样。

**风险控制**：`_route_sections` 只在**同时命中 ≥2 个申论锚点**时才返回非 None，任一不命中即返回 None 走原路径。这保证行测/公专**绝不受影响**。

### A-2 块后处理：要求子项归并 `merge_requirement_items`（新增，原地后处理）

在现有切分**之后**、返回**之前**对块列表做一轮归并，规则（不改切分器）：

| 判据 | 动作 |
|------|------|
| 块内**不含**分值标记（`（N分）`） | 判定为要求子项 → `content` 追加到上一块 |
| 块内含分值但**开头是要求特征词**（准确全面/恰当提炼/不超过/紧扣资料/条理清晰/内容具体/语言流畅/逻辑清晰/观点明确/自选角度/字数） | 拆分：前半（要求子项）并入上一块，后半（自 `（N）`+分值 起）作为新块 |
| 归并后块数 ≠ 分值锚点数 | 置 `blocked=True` + `block_reasons=['item_count_mismatch']`，**不生成 preview** |

### A-3 字段纠偏：参考答案 → `answer`（不是 `analysis`）

现行为：参考答案正文被写入 `analysis`。
目标：
- `answer` = 参考答案正文
- `analysis` = `参考答案说明：` 段 + 采分点标注（`段N 中的要点④…可考虑合并`）
- 若无 `参考答案说明`，则 `analysis` 留空（**不得**用答案填充）

### A-4 分值与题型

- `score`：从块内 `（N分）` 提取，缺省 1 → 触发 A-2 的阻断
- `question_type_detail`：申论**禁止**判为 `单选题/多选题`（现有把长文本答案块判成单选题）；申论仅允许 `简答题/论述题/写作题/简述题`

### A-5 材料承载（复用现有表，不新建）

用已有 `question_groups`（`shared_content` / `group_type='material'` / `subject`='申论'）承载"给定材料"，各题 `group_id` 指向它。`composite_matcher.py` 已存在，无需新建。

---

## 4. 改造块 B：三科共有图片映射架构（不重写解析器）

### B-1 schema：新增多对多关联表（你已选"甲"）

```sql
-- 迁移 B-1（新建表，幂等）
CREATE TABLE IF NOT EXISTS question_image_ref (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id      BIGINT  NOT NULL,           -- → question_image.image_id
  question_id   BIGINT  NOT NULL,           -- → question_bank.question_id
  role          VARCHAR(10) NOT NULL,       -- 题干图/选项图/答案图/解析图/材料图
  seq           INTEGER NOT NULL DEFAULT 0, -- 该题内图片顺序
  anchor_text   VARCHAR(200),               -- 归属判据（可追溯）
  create_time   DATETIME,
  UNIQUE(image_id, question_id, role, seq)
);
CREATE INDEX IF NOT EXISTS idx_qir_q ON question_image_ref(question_id);
CREATE INDEX IF NOT EXISTS idx_qir_i ON question_image_ref(image_id);
```

- `question_image` 保留为**图片实体表**（路径/hash/尺寸），一图一行，可去重
- `question_image_ref` 承担**多对多归属**
- 回填：现有 263 行 `question_image` → 生成对应 ref（`role='题干图'`），保证向后兼容
- 回滚：`DROP TABLE question_image_ref;`（不触碰原表，回滚安全）

### B-2 图片与题目的关联依据（P5 根治）

现状问题：按页提图 → 按页分配 → 串题。
新增**归属判定**（在 `_extract_and_save_images` 侧，`question_import.py:1630`）：

| 步骤 | 做法 |
|------|------|
| 1 | 按页提取图片，同时记录 `page_idx` + `bbox` |
| 2 | 用 PyMuPDF `page.get_text("dict")` 取得该页所有文本块的 `bbox` |
| 3 | **就近归属**：图片 bbox 与某题号文本块在**同一垂直区间** → 归属该题 |
| 4 | **区间继承**：若图片位于两题号之间且更靠近下一题号 → 归下一题；跨页图片按 `seq` 延续上一题 |
| 5 | **共用判定**：若同一图片同时满足多题且垂直距离差 < 阈值 → 为**每题各写一条 ref**（这正是第17页 1 图 → 81/82/83 的情形） |
| 6 | **尺寸过滤**：复用 `image_filters.py` 现有 L1–L4（含 L4 尺寸启发式）过滤 `15×33` 类小图标 |
| 7 | 记录 `anchor_text` = 判据文本片段，便于人工复核与后续纠错 |

### B-3 图片对解析层可见（P6）

- 不改 `extract_question_blocks` 的返回签名（**避免破坏公专/行测**）
- 由 B-2 侧独立产出 `image_refs`，在落库阶段与 `question_id` 绑定
- 预览态复用现有 `/records/{id}/attach-image` 端点补充/纠正归属

### B-4 MinerU 返回图片（P8）

`mineru_service.extract_text_sync` 由 `-> str | None` 改为 `-> MineruResult | None`：

```python
@dataclass
class MineruResult:
    markdown: str
    images: list[dict]   # [{'abs_path','rel_path','page','idx'}]
    elapsed: float
```

**必须保持的契约（不可破坏）**：任何失败仍 `return None`；GPU 串行锁 / 超时 / 健康检查 TTL 全部沿用；调用方回退链路不变。

---

## 5. 改造块 C：主数据与前端（低风险，高必要）

### C-1 主数据补齐（P11）

| 迁移 | 内容 | 幂等 | 回滚 |
|------|------|------|------|
| `M-1` | `INSERT question_subject (2,'申论')` | `WHERE NOT EXISTS` | `DELETE FROM question_subject WHERE subject_id=2` |
| `M-2` | 申论题型（`写作题/论述题/简答题/简述题` 绑 `subject_id=2`） | 同上 | 按 type_id 定向删 |
| `M-3` | `models.py` 的 `Enum(...)` 声明对齐实际 `VARCHAR`（P12） | 纯声明 | 还原声明 |

**不做**：不改 `shenlun_subcategory` 枚举值（5 值已完整，D4 三级树数据齐备）。

### C-2 VTJ DSL 修复（P14）

- 现状：`question_import` 页 `raw: true` ✅，但 JSON `state` 有 5 个碎片键、`nodes: null`
- **不做**：删除前端任何方法（v1 方案此项被否决）
- **做**：修复 5 个碎片键为完整声明；文件头加"本页禁用设计器保存"警示注释；改前备份
- 前端**只做增量**：`question_import.vue` 增加申论预览呈现（材料区、要求清单、答案配对状态、分类建议、阻断原因），复用现有 `.batch-preview` / `preview-item` / `abnormalItems` / `highlightIndex` 结构

---

## 6. 改造块 D：冗余清理（G6 去粗取精）

| # | 动作 | 说明 |
|---|------|------|
| D-1 | Tesseract 两函数迁出 `mineru_service.py` | `extract_text_from_image` / `_bytes` → `services/ocr.py`；**先 grep 全仓调用点**，有调用方则留薄转发并标 `@deprecated` |
| D-2 | `preview_data` 双编码治理（P13） | 写侧统一单层 JSON；读侧兼容旧的四层；先统计旧记录影响面 |
| D-3 | 前端重复解析**降级而非删除** | `parseRawTextToQuestions` 等 6 个方法改为"优先用后端 preview，缺失时才本地兜底"，并在 UI 明示来源；**保留代码**避免大改 |
| D-4 | `extra_answer_numbers` 归零（P10） | 公专多出的答案号 `[40]`：按题号区间剔除越界项 |

---

## 7. 实施阶段（粒度细化：每任务 1–3 文件）

> **与 v1 的差异**：任务从 11 个粗阶段拆为 **24 个可独立验证的任务**，分 7 波，峰值 6 并发。每任务有独立验收命令。

### Wave 1 — 备份、取证基线、迁移脚本（无前置）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| T0 | 归档方案到 `solve_problems_files/` + 备份 DB 与 VTJ 文件 | `.omo/plans/*.md` | `cp question_bank.db question_bank.db.bak_<ts>` 存在 |
| T1 | 建**自动不变量**回归脚本（不依赖人工金标准） | `backend/scripts/shenlun_invariants.py` | 对 254 份语料输出不变量报告 |
| T2 | 建**半自动金标准**生成器（脚本提取 + 差异人工审核） | `backend/scripts/build_groundtruth.py` | 产出 `申论金标准.json` 草稿 |
| T3 | 迁移脚本 `B-1`（图片多对多表）+ 回填 + 回滚 | `backend/migrations/*_image_ref.sql` | 建表成功 + 263 行回填 + `DROP` 可回滚 |
| T4 | 迁移脚本 `M-1/M-2/M-3`（申论主数据）+ 回滚 | `backend/migrations/*_shenlun_subject.sql` | 申论科目行/题型存在；公专 2583 条不变 |
| T5 | 采集**改造前**基线快照（公专/行测/申论三科） | `backend/data/regression_baseline_before.txt` | 含 `parser_regression.txt` 复现结果 |

### Wave 2 — MinerU 与图片提取（依赖 T0）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| T6 | `MineruResult` 数据类 + `extract_text_sync` 返回图片（保契约） | `services/mineru_service.py` | 失败仍 `return None`；`/mineru-health` 正常 |
| T7 | Tesseract 两函数迁至 `ocr.py` + 薄转发 | `services/mineru_service.py`, `services/ocr.py` | 全仓调用点无断链 |
| T8 | 图片提取加 `bbox` + 尺寸元数据（复用 `image_filters`） | `api/v1/question_import.py:_extract_and_save_images` | 行测 2023 卷提取到 35 张图且小图标被过滤 |

### Wave 3 — 申论解析器（依赖 T6）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| T9 | `_route_sections` 区段路由（锚点 + 冒号约束） | `services/text_parser.py` | 申论命中；行测/公专返回 `None` |
| T10 | `extract_question_blocks` 入口接入路由（**不改原切分逻辑**） | `services/text_parser.py` | **公专/行测 `parser_regression` 仍 PASS** |
| T11 | `merge_requirement_items` 要求子项归并 | `services/text_parser.py` | 块数 == 分值锚点数 |
| T12 | 答案区抽取 + `answer`/`analysis` 字段纠偏 | `services/text_parser.py` | 参考答案不再进 `analysis` |
| T13 | 材料抽取 → `question_groups` 映射 | `services/text_parser.py`, `services/composite_matcher.py` | 每题材料归属可追溯 |
| T14 | 阻断式校验器（`suspicious` → `blocked`+`block_reasons`） | `services/text_parser.py` | 不一致时 `blocked=True` |

### Wave 4 — 落库与图片关联（依赖 T3/T11/T13）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| T15 | 落库接线：申论科目/题型/题组/考点/图片 ref | `api/v1/question_import.py` | 库内字段 100% 匹配 |
| T16 | 图片归属判定（bbox 就近 + 区间继承 + 共用多写） | `api/v1/question_import.py` | 第17页 1 图 → 81/82/83 各 1 条 ref |
| T17 | 分离模式答案装配（复用 `smart_match` + `llm_match` 兜底） | `services/text_parser.py` | 答案覆盖率 100% |

### Wave 5 — 前端增量（依赖 T14）

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| T18 | 修复 DSL 5 个碎片键 + 加警示注释 + 备份 | `.vtj/files/question_import.json`, `.vtj/vue/question_import.vue` | JSON 可解析；版本号一致 |
| T19 | 预览增量：材料区/要求清单/答案配对状态/分类建议 | `.vtj/vue/question_import.vue`（**仅 script**） | 设计器误保存不摧毁逻辑 |
| T20 | 阻断提示：确认按钮禁用 + `block_reasons` 展示 | `.vtj/vue/question_import.vue`（仅 script） | blocked 时按钮不可点 |
| T21 | 前端解析降级为兜底 + 来源标识 | `.vtj/vue/question_import.vue`（仅 script） | 优先走后端 preview |

### Wave 6 — 回归与验收（依赖全部）

| # | 任务 | 验收 |
|---|------|------|
| T22 | 申论合并模式 10 份 + 分离模式 2 组 不变量全通过 | 题目数/题号/答案覆盖/材料覆盖 全绿 |
| T23 | **公专 `parser_regression.txt` 基线仍 PASS** + 行测抽样不退化 | 与 T5 快照逐项一致 |
| T24 | 端到端 Playwright：上传→预览→阻断→确认→题库页可见 | 含材料/答案/解析/分类/图片 |

### Wave FINAL — 四路并行复核

| # | 任务 | 角色 |
|---|------|------|
| F1 | 方案合规审计（Must Have / Must NOT Have 逐条核验） | `oracle` |
| F2 | 代码质量（`tsc`/lint/pytest/AI-slop 扫描） | `unspecified-high` |
| F3 | 真实手工 QA（从干净状态跑全部场景，存证据） | `unspecified-high` |
| F4 | 范围保真（1:1 比对"改了什么/没改什么"，检测越界） | `deep` |

**关键路径**：T0 → T3/T4 → T8 → T10 → T11 → T14 → T22 → T23 → F1–F4
**并行度**：W1 六任务并发；W3 五任务并发（峰值 6）

---

## 8. 验收方案（改进版：自动不变量优先，降低人工成本）

> **与 v1 的差异**：v1 要求"纯人工逐字段金标准"，成本过高。本版改为**三层验证金字塔**，人工只投入在差异审核。

### 第 1 层：自动不变量（零人工，覆盖 100% 语料）

| # | 不变量 | 适用范围 | 判定 |
|---|--------|---------|------|
| I-1 | 题目数 == 分值锚点数 | 申论 | 申论合并模式**精确** |
| I-2 | 题号序列连续无跳号/无重 | 三科 | 精确 |
| I-3 | 块内不含第二个题号 | 三科 | 精确（对应 `suspicious`） |
| I-4 | 每题 `score` ∈ {10,15,20,25,30,35,40} | 申论 | 精确 |
| I-5 | 答案覆盖率 == 100% | 分离模式 | 精确 |
| I-6 | 每题引用的 `给定资料N` 在材料区存在 | 申论 | 精确 |
| I-7 | `answer` 非空 ⟺ 该题有对应答案段 | 申论 | 精确 |
| I-8 | `analysis` 不等于 `answer` | 申论 | 精确（防字段错位复发） |
| I-9 | 选项数 ∈ {2,3,4}（申论恒为空集） | 三科 | 精确 |
| I-10 | 图片 ref 双向可达（image↔question） | 三科 | 精确 |
| I-11 | 公专/行测 `parser_regression` 与基线快照一致 | 公专/行测 | 精确 |
| I-12 | `shenlun_subcategory` ∈ 5 合法值 | 申论 | 精确 |

### 第 2 层：半自动金标准（人工只看差异）

- T2 脚本自动提取 → 生成金标准**草稿**
- 人工**只审核 I-1…I-12 未覆盖的语义正确性**（如"这道题问的是概括还是分析"）
- 审核后的金标准入库，后续改动做**逐字段 diff**
- 每卷抽 **2 题**（首题+末题）人工对照原文，成本可控

### 第 3 层：端到端与视觉验证

- Playwright 走完 `/question-import` 全流程
- 截图证据存 `.omo/evidence/`

### 硬门禁

| 门禁 | 条件 |
|------|------|
| G1 | `parser_regression.txt`（公专 30 份/2899 块）**必须仍 PASS**，否则整体不通过 |
| G2 | 行测抽样（2023 国考地市级 130 题）题号序列与 options 数**逐项一致** |
| G3 | 申论 I-1…I-12 **全绿**，任一红则不通过 |
| G4 | 图片专项：行测第13–18页图表归属**逐图人工确认**（共 11 张大图） |

---

## 9. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 区段路由误命中行测/公专 | 低 | 🔴 高 | 双锚点门槛（≥2 个申论锚点）；T10 强制跑 `parser_regression` |
| 要求子项归并误合并真题 | 中 | 🟠 中 | 分值标记为硬判据；I-1 不通过即阻断 |
| 破坏公专/行测（改 `text_parser.py` 共享文件） | 中 | 🔴 高 | 改动限定在**新增函数 + 入口分支**，不改原切分函数体；T5 基线快照 + G1 门禁 |
| 图片归属判定不准 | 中 | 🟠 中 | 保留 `anchor_text` 可追溯 + 人工抽检 11 张大图 + 现有 `attach-image` 兜底 |
| VTJ 设计器误保存摧毁前端逻辑 | 低 | 🔴 高 | T0 备份 + 文件头警示 + `raw:true` 保持 + 版本号同步 |
| schema 迁移不可回滚 | 低 | 🔴 高 | `DROP TABLE question_image_ref` 不触碰原表；主数据迁移定向可逆 |
| `MineruResult` 破坏"绝不抛异常"契约 | 低 | 🟠 中 | `try/except` 全覆盖 + 失败必 `None` + `/mineru-health` 回归 |

**回滚粒度**：每个 Wave 独立可回滚；T3/T4 的 SQL 各带 `.rollback.sql`；代码走 git revert 单 Wave commit。

---

## 10. 本方案未覆盖（诚实披露）

| 项 | 原因 | 何时补 |
|----|------|-------|
| 移动/平板端对申论字段的消费适配 | 本轮不动其模板 | 若申论入库后移动端显示异常，另开专项 |
| `llm_match_questions_answers` 的 LLM 调用成本与超时治理 | T17 只做兜底接入，未做成本控制 | 若分离模式答案覆盖率不达 100% 则需专项 |
| 254 份全语料的行测/公专逐份取证 | 本轮只抽样行测 1 份、公专 3 份 | 若 G2 门禁发现其他卷退化则扩大 |
| `solve_problems_files/` 12 份历史方案与本方案的冲突核对 | 未完成 | 建议在 T1 期间快速扫一遍，避免重复已被证伪的做法 |
