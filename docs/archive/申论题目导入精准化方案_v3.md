# 申论题目导入 去粗取精式精准化方案 v3（最终）

> **状态**：待你批准 → 交由 Atlas (`/start-work`) 执行
> **取代** v1（新建状态机+删前端解析，路线错误）与 v2（三科并进，超出必要）
> **取证依据**：直接驱动现有 `backend/app/services/text_parser.py` 对仓库真实语料运行，全部结论可复现
> **归档**：本文件在 `.omo/plans/`；由执行任务 T0 复制到 `D:\砺安题库\砺安题库\solve_problems_files\`（你的 G2 要求，规划者权限只能写 `.omo/`）

---

## 0. 范围（已按你的指令收窄）

**只修申论。不动公专/行测的题目切分与答案匹配逻辑。**

依据（实测）：公专 `smart_match` rate **0.99–1.0**、行测 **0.9923**，题号连续、选项 100%、答案与解析正确注入 → 这两条链路是正确的，改动它们违反 G6「去粗取精」与 G5「不影响其他模块」。

**唯一例外**：图片映射架构缺陷（`question_image` 只能 N:1）在申论上同样构成阻塞，且申论语料 **118/254 份含图**，故图片改造**只按申论需要实施**，不改公专/行测既有行为。

---

## 1. 实证结论

### 1.1 申论两种形态、两种病因（真题召回均为 0/5）

| | 合并模式（题目+答案同文档） | 分离模式（题目PDF + 答案PDF） |
|---|--------------------------|---------------------------|
| 病因 | 不识别「一、注意事项」为噪声 | 不区分「题号」与「要求子项」（括号样式相同） |
| 证据 | 注意事项 5 条 → 块1–6；块7 题号=**21**（材料正文数字） | `（2）分条列出；` 被当独立题 |
| 附加 | 参考答案被写入 **`analysis`** 而非 `answer` | `score=1`（真实15/20/25）；答案文档被判 `单选题` |

### 1.2 已验证有效的最小改动（方案的技术基石）

对 `2018…《申论》真题卷及答案（副省级）.pdf`（真值 5 题）实测：

| 步骤 | 结果 |
|------|------|
| 现状：全文喂 `extract_question_blocks` | 7 块，题号 1–6 = 注意事项，块7 题号=21 → **召回 0/5** |
| **仅把「三、作答要求」区段（@6950）到首个答案锚点（@7498）这段喂现有切分器** | **5 块，题号 1..5，与 5 个分值锚点一致 → 召回 5/5** |

区段内残留问题（唯一剩余项）：块2 = `（2）恰当提炼，条理清晰；`（要求子项）、块3 = `（3）不超过350字；（2）上级部门来W市考察…（20分）`（要求子项 + 真题2 粘连）→ 需一个**块后处理**步骤。

**结论：新增的只是"选哪一段送进去"，切分器本体不动。** 且识别不到申论区段时返回 `None`，行测/公专走原路径零影响。

### 1.3 答案锚点有 3 种形态（全部实测，必须全部支持）

| 形态 | 出现于 | 实测锚点 | 验证结果 |
|------|--------|---------|---------|
| **① 行内带冒号** | 2018/2019/2020/2022 合订本 | `参考答案\s*[:：](?!说明)` | 2018副省级=5、2020地市级=5、2022地市级=5 ✅ |
| **② 题号+卷别** | **2021 合订本（两套答案）** | `一、参考答案（H）` / `一、参考答案(H)` + `参考答案（F）` | 5 题 × 2 套 = 10 个锚点 ✅（半角/全角括号混用） |
| **③ 单独成行** | 各省分离型答案PDF、2022行政执法 | `^\s*参考答案\s*[:：]?\s*$` | 安徽4/4、广东5/5、北京4/4、国考5/5×3 ✅ |

**⚠️ 已单独验证每条规则各自有效；"三规则取最早命中"的并集逻辑尚未跑通验证 → 列为任务 T1 的第一项验收。**

**反例警示**：`参考答案` 字样**计数**不可用。D1 十份实测 `参考答案` 字样数 / 分值锚点数 = 5/5、**7/4**、**10/5**、**14/9**、5/5、5/5、**11/5**、**11/5**、5/5、**6/3**（因"参考答案说明"亦含该字样）。

### 1.4 申论答案是文本，图片是附加物

`国考申论/2024…地市级答案.pdf`：6 页 / 6271 字 / 5 图。第2页文本**完整包含**题干+要求+参考答案+参考答案说明；图片宽**全为 700px**、高度各异（206/426/515/346/256）；第6页 **0 文本 + 1 图**（纯图片页）。

→ 答案抽取走文本，**不依赖 OCR/MinerU**。图片仍需入库（可能是答案渲染图/材料图），但不阻断答案抽取。

### 1.5 其余确认缺陷

| # | 缺陷 | 证据 |
|---|------|------|
| P4 | `question_image` 为 N:1、`image_type` 仅 `'题干图'`（263行） | 无法表达 1图→N题、N图→1题、多类型 |
| P5 | 图片走 `question_import._extract_and_save_images` 独立路径，与题目切分无关联依据 | 按页分配 → 串题 |
| P6 | `extract_question_blocks` 返回字段无 image | `[analysis,answer,content,format,options,question_number,question_type,suspicious,type_confidence]` |
| P7 | `suspicious` 只标记不阻断 | 块7 `suspicious=True` 仍可确认入库 |
| P8 | MinerU 只收 `*.md`，图片全丢 | `mineru_service.py:160` |
| P9 | Tesseract 两函数错置在 MinerU 服务 | `mineru_service.py:190-255` 用 `pytesseract` |
| P11 | `question_subject` 无申论行；`question_type` 8 题型全绑 `subject_id=3` | 实测查询 |
| P12 | models.py 声明 `Enum` vs 实际 `VARCHAR(5)` 漂移 | `models.py:193` vs `PRAGMA table_info` |
| P13 | `preview_data` 双重编码 | 代码自认 `question_import.py:213` |
| P14 | `.vtj/files/question_import.json` state 5 碎片键 + `nodes=null` | `stats='{ total_questions: 0'` 等 |
| — | 公专/行测基线健康，**必须保持** | `parser_regression.txt` 30份/2899块 PASS |

---

## 2. 改造设计（全部为增量，不重写）

### A. 申论解析（`text_parser.py` 内新增，原切分函数体不动）

**A-1 `_route_sections(text) -> Optional[SectionMap]`**

| 区段 | 锚点 | 容错 |
|------|------|------|
| 噪声 | `^[一二三四五六七八九十]+、\s*注意事项` | 亦兼容 `注意事项` 单独成行 |
| 材料 | `^[一二三四五六七八九十]+、\s*给定材料\|给定资料` | 兼容无「一、」直接以 `材料1`/`给定资料1` 开头 |
| 问题 | `^[一二三四五六九十]+、\s*作答要求` | 兼容 `作答要求` 单独成行 |
| 答案 | **§1.3 三规则取最早命中** | 必须排除 `参考答案说明` |

**安全门槛**：仅当**同时命中 ≥2 个申论锚点**时返回非 `None`，否则 `None` → 原路径。这是保证公专/行测零影响的核心。

**A-2 `extract_question_blocks` 入口接入**：`sec is None` → 原逻辑；否则只对 `sec.question` 区段执行原切分。

**A-3 块后处理 `merge_requirement_items`**

| 判据 | 动作 |
|------|------|
| 块内不含 `（N分）` | 要求子项 → `content` 并入上一块 |
| 块内含分值但开头为要求特征词（准确全面/恰当提炼/不超过/紧扣资料/条理清晰/内容具体/语言流畅/逻辑清晰/观点明确/自选角度/字数） | 拆分：前半并入上一块；后半（自 `（N）`+分值起）作为新块 |
| 归并后块数 ≠ 分值锚点数 | `blocked=True` + `block_reasons=['item_count_mismatch']`，**不生成 preview** |

**A-4 字段纠偏**：`answer` = 参考答案正文；`analysis` = `参考答案说明` + 采分点（`段N 中的要点④…`）。**禁止**用答案填 `analysis`。若答案锚点数 == 题数×2（2021 型），按 `(H)`→`answer`、`(F)`→`analysis` 分配。

**A-5 分值与题型**：`score` 从 `（N分）` 提取；申论**禁止**判为 `单选题/多选题`，仅允许 `简答题/论述题/写作题/简述题`。

**A-6 材料承载**：复用已有 `question_groups`（`shared_content`/`group_type='material'`），各题 `group_id` 指向它。**不新建表**。

### B. 图片映射（只按申论需要，不改公专/行测行为）

**B-1 schema（你已选"甲"：多对多）**

```sql
CREATE TABLE IF NOT EXISTS question_image_ref (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id    BIGINT NOT NULL,
  question_id BIGINT NOT NULL,
  role        VARCHAR(10) NOT NULL,   -- 题干图/材料图/答案图/解析图/选项图
  seq         INTEGER NOT NULL DEFAULT 0,
  anchor_text VARCHAR(200),
  create_time DATETIME,
  UNIQUE(image_id, question_id, role, seq)
);
CREATE INDEX IF NOT EXISTS idx_qir_q ON question_image_ref(question_id);
CREATE INDEX IF NOT EXISTS idx_qir_i ON question_image_ref(image_id);
```
- `question_image` 降级为**图片实体表**（路径/hash/尺寸）
- 回填现有 263 行 → `role='题干图'`，向后兼容
- **回滚 = `DROP TABLE question_image_ref;`（不触碰原表）**

**B-2 归属判定（P5 根治）**：记录图片 `page_idx` + `bbox` → 用 `page.get_text("dict")` 取该页文本块 bbox → **垂直就近**归属；区间边界按就近取整；共用时**为每题各写一条 ref**；复用 `image_filters.py` 现有 L1–L4 过滤 `15×33` 类小图标；记录 `anchor_text` 可追溯。

### C. 主数据与前端

**C-1 迁移**（均幂等 + 带 rollback）
| 迁移 | 内容 | 回滚 |
|------|------|------|
| `M-1` | `INSERT question_subject (2,'申论')` | `DELETE WHERE subject_id=2` |
| `M-2` | 申论题型绑 `subject_id=2` | 按 type_id 定向删 |
| `M-3` | `models.py` `Enum` 声明对齐实际 `VARCHAR`（P12） | 还原声明 |

**不做**：不改 `shenlun_subcategory` 枚举（5 值已完整，三级树 25 考点数据齐备）。

**C-2 VTJ（P14）**：修复 5 个碎片键为完整声明；文件头加"本页禁用设计器保存"警示注释；改前备份；保持 `raw:true`；版本号同步。
前端**只做增量**（`question_import.vue` 仅 script）：材料区预览、要求清单、答案配对状态、三级分类建议、阻断原因展示。复用现有 `.batch-preview`/`preview-item`/`abnormalItems`/`highlightIndex`。**不删除任何现有方法。**

### D. 冗余清理（G6）

| # | 动作 |
|---|------|
| D-1 | Tesseract 两函数迁至 `services/ocr.py`；先 grep 全仓调用点，有调用方留薄转发 + `@deprecated` |
| D-2 | `preview_data` 双编码治理：写侧单层 JSON，读侧兼容旧四层，先统计影响面 |
| D-3 | MinerU `extract_text_sync` 返回 `MineruResult{markdown, images[], elapsed}`（保"绝不抛异常"契约、GPU 锁、超时、健康检查） |

---

## 3. 任务分解（19 任务 / 6 波 + 复核波）

> 粒度：每任务 1–3 文件，有独立可执行验收

### Wave 1 — 基线、迁移、锚点验证（无前置）
| # | 任务 | 验收 |
|---|------|------|
| T0 | 归档本方案到 `solve_problems_files/` + 备份 DB(`cp question_bank.db question_bank.db.bak_<ts>`) 与 VTJ 文件 | 备份存在 |
| T1 | **验证三形态答案锚点并集逻辑** + 建自动不变量回归脚本 | 16 份样本全部定位到答案区 |
| T2 | 采集改造前基线快照（含 `parser_regression.txt` 复现） | `regression_baseline_before.txt` |
| T3 | 迁移 `B-1` 图片多对多表 + 回填 263 行 + rollback | 建表 + 回填 + `DROP` 可回滚 |
| T4 | 迁移 `M-1/M-2/M-3` 申论主数据 + rollback | 申论科目/题型存在；公专 2583 条不变 |

### Wave 2 — 申论解析（依赖 T1）
| # | 任务 | 验收 |
|---|------|------|
| T5 | `_route_sections`（三形态答案锚点 + ≥2 锚点门槛） | 申论命中；行测/公专返回 `None` |
| T6 | `extract_question_blocks` 入口接入（不改原切分函数体） | **公专/行测 `parser_regression` 仍 PASS** |
| T7 | `merge_requirement_items` 要求子项归并 | 块数 == 分值锚点数 |
| T8 | 答案抽取 + `answer`/`analysis` 纠偏（含 2021 两套答案分配） | 参考答案不再进 `analysis` |
| T9 | 材料抽取 → `question_groups` 映射（复用现有表） | 每题材料归属可追溯 |
| T10 | 阻断式校验器（`suspicious` → `blocked`+`block_reasons`） | 不一致时 `blocked=True` |
| T11 | 分值提取 + 申论题型白名单（禁判单选/多选） | `score` 正确；无 `单选题` |

### Wave 3 — 图片与 MinerU（依赖 T3）
| # | 任务 | 验收 |
|---|------|------|
| T12 | 图片提取加 `bbox` + 尺寸元数据（复用 `image_filters`） | 国考申论答案卷 5 张图全提取 |
| T13 | 归属判定（垂直就近 + 共用多写 ref） | `question_image_ref` 行数与归属正确 |
| T14 | `MineruResult` 返回图片（保契约）+ Tesseract 迁出 | 失败仍 `return None`；调用点无断链 |

### Wave 4 — 落库与前端（依赖 T7/T10/T13）
| # | 任务 | 验收 |
|---|------|------|
| T15 | 落库接线：申论科目/题型/题组/考点/图片 ref | 库内字段 100% 匹配 |
| T16 | 前端预览增量 + 阻断提示（**仅 script**，同步 DSL） | 设计器误保存不摧毁逻辑 |

### Wave 5 — 回归验收
| # | 任务 | 验收 |
|---|------|------|
| T17 | 申论合并 10 份 + 分离 2 组 不变量全绿 | 见 §4 第1层 |
| T18 | **公专基线仍 PASS** + 行测抽样不退化 | 与 T2 快照逐项一致 |
| T19 | 端到端 Playwright + 人工抽检 | 证据存 `.omo/evidence/` |

### Wave FINAL — 四路并行复核
F1 方案合规审计（oracle）｜F2 代码质量（unspecified-high）｜F3 真实手工 QA（unspecified-high）｜F4 范围保真（deep）

**关键路径**：T0 → T1 → T5 → T6 → T7 → T10 → T17 → T18 → F1–F4
**并行度**：W1 五任务并发；W2 七任务并发（峰值 7）

---

## 4. 验收（三层，零/低人工）

### 第1层：自动不变量（零人工，覆盖全部 254 份）
| # | 不变量 | 范围 |
|---|--------|------|
| I-1 | 题目数 == 分值锚点数 | 申论 |
| I-2 | 题号序列连续无跳号/无重 | 申论 |
| I-3 | 块内不含第二个题号（对应 `suspicious`） | 申论 |
| I-4 | `score` ∈ {10,15,20,25,30,35,40} | 申论 |
| I-5 | 答案覆盖率 == 100%（分离模式） | 申论 |
| I-6 | 每题引用的 `给定资料N` 在材料区存在 | 申论 |
| I-7 | `answer` 非空 ⟺ 该题有答案段 | 申论 |
| I-8 | `analysis` ≠ `answer`（防字段错位复发） | 申论 |
| I-9 | 申论 `options` 恒为空集（不得出现单选/多选） | 申论 |
| I-10 | `shenlun_subcategory` ∈ 5 合法值；`question_knowledge` 有归属 | 申论 |
| I-11 | 图片 ref 双向可达 | 申论 |
| I-12 | **`parser_regression` 与 T2 基线快照逐项一致** | 公专/行测 |

### 第2层：半自动金标准（人工只看差异）
脚本生成草稿 → 人工只审语义正确性 → 每卷抽 **2 题**（首题+末题）对照原文 → 入库做逐字段 diff。

### 第3层：端到端
Playwright 走完 `/question-import`；截图存 `.omo/evidence/`。

### 硬门禁
| 门禁 | 条件 |
|------|------|
| G1 | **`parser_regression.txt`（公专 30份/2899块）必须仍 PASS**，否则整体不通过 |
| G2 | 行测抽样（2023 国考地市级 130 题）题号序列与 options 数**逐项一致** |
| G3 | 申论 I-1…I-11 **全绿**，任一红则不通过 |
| G4 | 申论图片专项：国考 2024 地市级/副省级各 5 张图**逐图人工确认归属** |

---

## 5. 风险与回滚

| 风险 | 影响 | 缓解 |
|------|------|------|
| 区段路由误命中行测/公专 | 🔴 高 | ≥2 锚点门槛；T6 强制跑 `parser_regression`；G1 门禁 |
| 要求子项归并误合并真题 | 🟠 中 | 分值为硬判据；I-1 不通过即阻断 |
| 改 `text_parser.py` 共享文件波及公专/行测 | 🔴 高 | 改动限定为**新增函数 + 入口分支**，不改原切分函数体；T2 基线快照 + G1/G2 |
| 三形态答案锚点并集未验证 | 🟠 中 | **T1 首要验收项**，先验证再进 T5 |
| 图片归属不准 | 🟠 中 | 保留 `anchor_text` 可追溯 + G4 抽检 + 现有 `attach-image` 兜底 |
| VTJ 设计器误保存摧毁前端逻辑 | 🔴 高 | T0 备份 + 文件头警示 + `raw:true` + 版本号同步 |
| schema 迁移不可回滚 | 低 | `DROP TABLE` 不触碰原表；主数据迁移定向可逆 |

**回滚粒度**：每 Wave 独立可回滚；SQL 各带 `.rollback.sql`；代码走 git revert 单 Wave commit。

---

## 6. 诚实披露：未覆盖项

| 项 | 原因 | 何时补 |
|----|------|-------|
| 三形态答案锚点**并集**逻辑尚未实跑验证 | 单独规则已验证，并集待跑 | **T1（首要）** |
| `_route_sections` 在无「一、」卷上的表现 | 未抽样验证 | T5 内补验 |
| 移动/平板端对申论字段的消费适配 | 本轮不动其模板 | 若移动端显示异常另开专项 |
| `llm_match_questions_answers` 的成本与超时治理 | T15 只做兜底接入 | 若答案覆盖率不达 100% 需专项 |
| `solve_problems_files/` 12 份历史方案冲突核对 | 未完成 | 建议 T1 期间快扫，避免重复已被证伪做法 |
| `text_parser.py` 中是否已存在申论分派点 | 待 bg_6bde1ac4 审计结果 | 收到后补入 §2A |