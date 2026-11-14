# 考点复核、跨知识点纠正与 PDF/XLSX 横线_实施报告 v8c

> 承接 `教师端导入与三层分类治理_实施报告_v8.0.md`（v8.0 主体，提交 `9608ae90`）。
> 本报告覆盖用户 m03808 授权的四项：①跨知识点纠正 ②复核队列与设计器方案 ③横线回填 ④PDF/XLSX 横线补做。
> 分支 `feat/v6-fix`｜生成日期 2026-11-14｜实施者 ARCH/FE（QBDM 单角色切换）

---

## 0. 需求对照

| # | 用户原话（m03808 摘录） | 落地结果 |
|---|---|---|
| 1 | 「授权，一定要命中准确、将矛盾化解」 | 跨知识点纠正已落库：**462 题**改知识点，**195 题**补空知识点，{\bf 点↔知识点矛盾归零}，可定位率 **79.9% → 83.8%** |
| 2 | 「人工过一遍，请提供详细的设计器解决方案」 | 复核页 `/teacher/point-review` 上线（教师端导航「考点复核」）；确认/驳回双路径实测通过；第 3 章给出**设计器 A/B 两套完整方案**（含节点树、脚本、样式、校验） |
| 3 | 「回填」 | 横线回填 **19 题 30 处** + **2 组材料**；跳过与缺口逐条列明（第 4 章） |
| 4 | 「补做，且需要全方位、多方面补做」 | PDF 矢量线段 + XLSX 单元格边框/富文本两条新链路（第 5 章），新增 **8 个单测**，docx+XLSX+PDF 合计 13 passed |

---

## 1. 现状基线（本轮改动前，实测）

| 指标 | 值 | 来源 |
|---|---|---|
| 题库总量 | 3528 题 | `question_bank` |
| v8.0 后已定位考点 | 2955（83.8%） | 见 2.4 复测 |
| 待复核（tier=review, pending） | 129 + 6 + 562 + 299 = **996** | `GET /api/point-review/stats` |
| 已应用（applied） | 2175 | 同上 |
| 复核页 | 无 | 本轮新建 |
| PDF/XLSX 横线识别 | 无（只做了 docx） | `pdf_reader.py` / `excel_reader.py` 原状 |

---

## 2. ① 跨知识点纠正（--fix-subcategory）

### 2.1 为什么上一轮「只能到 79.9%」

规则引擎 `classify()` 原设计是**在题目已有知识点（sub_category_id）内选考点**。实测发现 709 道未命中题里，大量是**知识点本身标错**：

- 「图形推理」的题被标成知识点「言语理解与表达」
- 「微生物发酵」被标成「判断推理」
- 「基础警务能力」下混入刑事执法题

在这些题上，候选集被限制在错误知识点内，考点再准也命不中 —— 这是**分类链路的矛盾**，不是规则覆盖不足。

### 2.2 实现

`backend/app/services/taxonomy/classifier.py` 拆成两段，语义与原版一致，避免回归：

- `_texts(question_text, options_text, context_text)` → 组装 body/tail/ctx
- `_rank(...)` → 打分排序与 tier 定档

新增：

| 函数 | 作用 |
|---|---|
| `_point_sc_map()` / `point_sc_index()` | 考点 → 知识点反查表（91 条，按 `knowledge_point.parent_id` 建立） |
| `expected_sub_category(point_id)` | 给定考点返回它**应该**挂的知识点 |
| `classify_cross(question_text, subject_id, current_sub_category_id=None, options_text=None, context_text=None)` | 候选集 = 该科目**全部考点**（不按现有知识点收缩），返回追加 `sc_id` / `old_sc_id` / `sc_changed` |

`backend/scripts/taxonomy/reclassify_points.py` 新增 `--fix-subcategory`：

- plan 元组扩展为 `(qid, old_point, new_point, score, tier, reason, batch, old_sc, new_sc)`
- apply 时同步 `UPDATE question_bank SET sub_category_id`
- revert 只还原 `new_sub_category_id IS NOT NULL` 的题（v8c 之前的历史批次 sc 为空，不能盲还原）
- 跳过「已是该考点且无 sc 变更」的 no-op，避免污染审计

`backend/scripts/taxonomy/migrate_v8c.py`：`point_assign_audit` 增列 `old_sub_category_id` / `new_sub_category_id`（备份 `backend/data/backups/question_bank_pre_v8c_20261114_212539.db`）。

### 2.3 执行与结果

```bash
# dry-run
python backend/scripts/taxonomy/reclassify_points.py --subject all --fix-subcategory --batch v8-fix-sc
# 落库
python backend/scripts/taxonomy/reclassify_points.py --subject all --fix-subcategory --batch v8-fix-sc --apply
```

| 档位 | 题数 | 说明 |
|---|---|---|
| auto（自动应用） | 1996 | 其中 **462 题**含知识点纠正 |
| review（待人工） | 1088 → 规范化后 996 | 队列见第 3 章 |
| unmatched（仍未定位） | 444 | 13 题题干仅「（题干缺失）」类，其余无有效关键词 |

**知识点纠正流向（Top 6）**：

| 原知识点 | 新知识点 | 题数 |
|---|---|---|
| 基础知识 | 接警与处警 | 45 |
| 基础知识 | 合理处置 | 32 |
| 基础知识 | 巡逻 | 31 |
| 基本警务能力 | 刑事执法基础知识 | 21 |
| 言语理解与表达 | 图形推理 | 10 |
| 未分类 | 数学运算 | 13 |

**样例**：#54「不属于刑事强制措施的是」由「基本警务能力」纠正为「基础知识 · 刑事执法基础知识」（置信 11，次优 9）；#131「车巡组」纠正为「巡逻」（7 / 3）。

### 2.4 复测（`_tmp_cov.py` 实测后产物已清理）

| 科目 | 总量 | 已定位 | 覆盖率 |
|---|---|---|---|
| 行测 | 613 | 484 | 79.0% |
| 申论 | 39 | 36 | 92.3% |
| 公专 | 2876 | 2435 | 84.7% |
| **合计** | **3528** | **2955** | **83.8%** |

- 补空知识点：`backend/_tmp_fillsc.py`（已删）把「已定位考点但 `sub_category_id IS NULL`」的 **195 题**按 point→sc 补齐
- 一致性校验：`SELECT count(*) WHERE point 所属 sc <> question.sub_category_id` = **0**
- 回滚：`--revert --batch-id v8-fix-sc` 会把 462 题的考点与知识点一并还原

---

## 3. ② 复核队列与设计器方案

### 3.1 接口（已就绪，仅 teacher/admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/point-review/queue?batch_id=&page=&page_size=` | pending 清单，按置信分降序；返回 `audit_id/question_id/old_point_name/new_point_name/score/tier/reason/snippet` |
| POST | `/api/point-review/{audit_id}` | body `{"accept": true/false, "note": "..."}`；驳回时还原 `point_id` **与** `sub_category_id` |
| GET | `/api/point-review/stats` | 各批次 total / by_tier / by_status |

权限：`_require_reviewer` 只放行 `user_type in (teacher, admin)`，学生一律 403。

### 3.2 页面（已实施，方案 A）

- 文件：`src/views/teacher/pc/PointReview.vue`（手写页，约 480 行）
- 路由：`src/router/index.ts` → `/teacher/point-review`（name `TeacherPointReview`，meta roles teacher/admin）
- 入口：`.vtj/vue/TeacherNavHeader.vue` script 的 `navTabs` 增 `{ key: 'review', label: '考点复核', path: '/teacher/point-review' }`
  - 该组件**没有 `.vtj/files` DSL**，不是设计器页面，改 script 不触发 R2/R3
- 三态：骨架屏（loading）/ 空态（本批已复核完毕）/ 错误（红条 + 重试）
- 交互：批次下拉、进度条与四计数、卡片（题号 / 置信分 / 题干摘要 / 旧→新 / 命中关键词）、确认、驳回（先 prompt 原因）、备注、分页
- 响应式：`@media (max-width: 720px)` 单列、按钮全宽、备注框 `flex: 0 0 auto`；导航在 `@media (max-width: 1024px)` 改横向滚动（原来 8 个 tab 在 390/834px 会被裁掉）
- 可访问性：所有可交互元素 `:focus-visible` 2px 描边；`prefers-reduced-motion` 关掉过渡与骨架动画

### 3.3 双路径实测（真实 HTTPS 调用，非 mock）

```
# 确认（accept）：只改审计状态，不改题
POST /api/point-review/4039 {"accept":true}  → {"review_status":"accepted","reverted":false}

# 驳回（reject）：题从 1039/92 还原到 920/14
POST /api/point-review/4040 {"accept":false} → {"review_status":"rejected","reverted":true}
question_bank#1826  point_id/sub_category_id: (1039, 92) → (920, 14)   ✅ 双字段同时还原
```

### 3.4 设计器解决方案（用户要求的详细版）

**先说结论**：这个页面**不需要进设计器**，已按方案 A 落地。若你希望它出现在 VTJ 设计器的页面列表里（可拖拽改布局），按方案 B 做，两者可共存。

#### 方案 A（当前，推荐）：手写页 + 导航入口

| 项 | 值 |
|---|---|
| 文件 | `src/views/teacher/pc/PointReview.vue` |
| 路由 | hash 路由 `#/teacher/point-review` |
| 设计器可见 | 否（不在 `.vtj/` 下，不会被 `vtj_sync_vue_to_dsl` 触碰，**没有 raw 覆盖风险**） |
| 改动方式 | 直接改 `.vue`，改完 `npx vue-tsc --noEmit` + 截图 |
| 适合 | 已能自测通过、需要稳定可用的场景 |

#### 方案 B（可选）：在设计器里做同名功能页

**B-1 新建页面**（用 MCP，不要手写 DSL）

```json
// mcp__vtj__vtj_create_page_scaffold
{ "id": "teacher_point_review", "name": "TeacherPointReviewDsl",
  "title": "考点复核", "icon": "Checked", "addRoute": true,
  "routePath": "/teacher/point-review-dsl" }
```

> 路径特意加 `-dsl` 后缀，避免与方案 A 抢同一个路由。

**B-2 节点树**（深度 6，控制在设计器可拖拽范围内）

```
div.pr-page
├─ TeacherNavHeader            activeNav="review"
└─ main.pr-main
   ├─ header.pr-head          （h1 考点复核 + p.pr-sub 说明）
   │  └─ div.pr-batch         （span 批次 + el-select 绑定 state.batch + el-button 刷新）
   ├─ section.pr-progress     （div.pr-bar > span.pr-bar-done :style width + ul.pr-stats 四个 li）
   ├─ p.pr-alert              v-if="state.error"（文案 + 重试按钮）
   ├─ section.pr-list         v-for="it in state.items" :key="it.audit_id"
   │  └─ article.pr-card
   │     ├─ div.pr-card-top   （span.pr-qid / span.pr-score）
   │     ├─ p.pr-snippet
   │     ├─ div.pr-flow       （span.pr-point.old / span.pr-arrow / span.pr-point.new）
   │     ├─ p.pr-reason       {{ it.reasonText }}
   │     └─ div.pr-actions    （button.pr-ok / button.pr-no / input.pr-note）
   └─ div.pr-pager            （上一页 / 第 x / y 页 / 下一页）
```

**B-3 状态（designer state 面板，逐个新增）**

| 字段 | 类型 | 默认值 |
|---|---|---|
| `batches` | array | `[]` |
| `batch` | string | `''` |
| `items` | array | `[]` |
| `page` | number | `1` |
| `pageSize` | number | `20` |
| `total` | number | `0` |
| `pending` | number | `0` |
| `acting` | number | `0` |
| `notes` | object | `{}` |
| `loading` | boolean | `true` |
| `error` | string | `''` |

**B-4 脚本方法（粘贴到设计器「方法」面板，可直接用）**

```js
// 说明：设计器里 request 必须走 auth.apiFetch（裸 fetch 无 token 会 401）
async loadStats() {
  const auth = window.__VTJ_AUTH__;
  const res = await auth.apiFetch('/api/point-review/stats');
  const data = await res.json();
  this.batches = data.batches || [];
  if (!this.batch && this.batches.length) this.batch = this.batches[0].batch_id;
  const cur = this.batches.find((b) => b.batch_id === this.batch);
  this.pending = (cur && cur.by_status && cur.by_status.pending) || 0;
},
async loadQueue() {
  this.loading = true; this.error = '';
  try {
    const auth = window.__VTJ_AUTH__;
    const qs = '?batch_id=' + encodeURIComponent(this.batch) +
               '&page=' + this.page + '&page_size=' + this.pageSize;
    const res = await auth.apiFetch('/api/point-review/queue' + qs);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    this.items = (data.items || []).map((it) => ({
      ...it,
      // 设计器模板不放复杂表达式，reason 在这里先翻译好
      reasonText: this.formatReason(it.reason)
    }));
    this.total = data.total || 0;
  } catch (e) {
    this.error = '接口返回异常，请稍后重试';
  } finally { this.loading = false; }
},
formatReason(raw) {
  if (!raw) return '';
  try {
    const p = JSON.parse(raw);
    const parts = [];
    if (Array.isArray(p.hits)) {
      const words = p.hits.filter((h) => typeof h === 'string' && !/[()[\]{}|\\.*+?^$]/.test(h));
      if (words.length) parts.push('命中关键词：' + words.slice(0, 6).join('、'));
    }
    if (typeof p.margin === 'number') parts.push('与次优考点相差 ' + p.margin + ' 分');
    return parts.length ? parts.join(' · ') : raw;
  } catch (e) { return raw; }
},
async decide(it, accept) {
  let note = this.notes[it.audit_id] || '';
  if (!accept) {
    const input = window.prompt('驳回原因（会写入审计，便于回溯）：', '');
    if (input === null) return;
    note = input.slice(0, 120);
  }
  this.acting = it.audit_id;
  try {
    const auth = window.__VTJ_AUTH__;
    const res = await auth.apiFetch('/api/point-review/' + it.audit_id, {
      method: 'POST',
      body: JSON.stringify({ accept: accept, note: note })
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    await this.loadStats(); await this.loadQueue();
  } catch (e) {
    window.alert('提交失败，请重试');
  } finally { this.acting = 0; }
}
```

**B-5 事件绑定**

| 节点 | 事件 | 动作 |
|---|---|---|
| 批次 `el-select` | `change` | `page=1; loadQueue()` |
| 刷新按钮 | `click` | `loadStats(); loadQueue()` |
| 确认按钮 | `click` | `decide(it, true)` |
| 驳回按钮 | `click` | `decide(it, false)` |
| 上一页/下一页 | `click` | `page±1; loadQueue()` |
| 页面 `mounted` / 生命周期 `onMounted` | — | `loadStats().then(() => loadQueue())` |

**B-6 样式**

设计器「样式」面板直接粘贴方案 A 的 `<style scoped>` 内容（`.pr-*` 前缀，约 120 行）。关键三条：

```css
.pr-note { flex: 1 1 220px; min-width: 160px; height: 34px; }
@media (max-width: 720px) { .pr-note { flex: 0 0 auto; width: 100%; min-width: 0; } }
.pr-ok:focus-visible, .pr-no:focus-visible { outline: 2px solid #1a3c6d; outline-offset: 2px; }
```

**B-7 保存与校验（顺序不能反）**

1. `mcp__vtj__vtj_write_dsl_file` 只写 `nodes` / `state` / `methods`，**不要**写整个 `full`
2. `mcp__vtj__vtj_check_consistency` 看版本号/方法签名是否一致
3. `npx vue-tsc --noEmit` → 必须 exit 0
4. 打开 `http://localhost:9527/__vtj__/` 拖一次布局并保存，再刷新 `#/teacher/point-review-dsl` 截图
5. **禁止**对该页执行 `vtj_sync_vue_to_dsl`（新页不是 raw，但一旦手改过 template 就会丢方法）

**B-8 方案选择建议**

| 场景 | 选 |
|---|---|
| 只求「老师能复核」 | A（已完成，零风险） |
| 后续要让非开发同事改文案/布局 | B（先按上面的脚手架建，再拖拽） |
| 想两边都有 | A + B 同时存在（路由不同，互不影响） |

---

## 4. ③ 横线回填

### 4.1 方法

docx 每 ~40 字换行，解析后同样留半角空格，**正则无法区分换行空格与横线空格**（3669 有 5 个空格，只有 3 个是横线）。因此改为逐题「上下文片段 → 期望替换」：先断言片段在题干中唯一出现，再替换，避免误伤。

脚本：`backend/scripts/taxonomy/backfill_blanks_apply.py`

### 4.2 结果

- **19 题、30 处**：2661 / 2689 / 3666 / 3667 / 3668 / 3669 / 3670 / 3671 / 3672 / 3673 / 3674 / 3675 / 3676 / 3798 / 3799 / 3808 / 3809 / 3921 / 3922
- **2 组材料**：group 51 →「想它。”____。人们」；group 54 →「软硬件工具，____。」
- 报告：`docs/design/横线回填结果_v1.json`
- 备份：`question_bank_pre_blanks_20261114_212804.db` / `..._212823.db` / `..._212839.db`

### 4.3 跳过与缺口（如实记录）

| 题 | 原因 |
|---|---|
| 3800 | 原文「研究 地均居于」语义不通，疑 docx 吞了「地位」，不猜 |
| 4214 | 划线对象是整句，没有可插入空位 |
| 3937 / 3938 / 3942 / 3947 / 4065 / 4077 / 4080 | `group_id=0`，复合题材料本身缺失 —— 属**源文件缺失**，不是空位丢失 |

---

## 5. ④ PDF / XLSX 横线（全方位补做）

### 5.1 PDF（矢量线段）

新模块 `backend/app/services/question_ingest/pdf_underline.py`：

| 常量 | 值 | 含义 |
|---|---|---|
| `BLANK` | `____` | 统一占位 |
| `SEG_MIN_W` | 18.0 | 短于 18pt 的线视为标点装饰 |
| `SEG_MAX_RATIO` | 0.6 | 宽于页宽 60% 视为页框/表格线 |
| `GAP_MAX` / `GAP_MIN` | 6.0 / -3.0 | 线段顶边与字符基线的容差 |
| `RECT_MAX_H` | 2.5 | 细矩形（下划线常被画成 rect）高度上限 |

流程：

1. `collect_h_segments(page, page_width, table_bboxes)` —— 从 `page.lines` / `rects` / `edges` 收水平线
   - **按 `(round(x0,1), round(top,1), round(x1,1))` 去重**：pdfplumber 同一根线会同时出现在 lines 与 edges，不去重会插两个 `____`
   - 落在 `page.find_tables()` 的 bbox 内直接跳过（表格框线不是填空）
2. `_char_text_positions(text, chars)` —— 把字符对象顺序对齐到 `extract_text()` 的下标
   - `extract_text()` 会合成空格（实测 27 个 char 对 30 个字符）；按比例估算会把 `____` 插到行尾，这里改为按字符序列对齐
3. `apply_line_blanks(text, chars, segs)` —— 按字符中心 x 定位插入；落点前是空格就用 `____` 顶替；已含 `____` 的行不重复插

接线：`pdf_reader.py` 在 `for page_no, page in enumerate(pdf.pages, 1)` 内先 `tables = page.find_tables()`（复用给表格原位插入），再 `mark_page_blanks(page, tlines, page_width, table_bboxes=[t.bbox for t in tables])`。

端到端实测（合成 PDF）：`_extract_text_from_pdf` 输出

```
编译人员在岗位上____的写照。填入划横线部分最恰当的一项是：
```

### 5.2 XLSX（单元格边框 + 富文本）

新模块 `backend/app/services/question_ingest/xlsx_underline.py`：

- `cell_has_bottom_only_border(cell)` —— 只有 bottom 有边、left/right/top 全无，才算「填空下划线」；四边网格是表格，不算
- `rich_text_with_underline(cell)` —— openpyxl 3.1 `CellRichText`：下划线空白 → `____`，下划线文字 → `<u>…</u>`
- `cell_display_text(cell)` —— 统一取文本

接线：`excel_reader.py` 的 `parse_excel_buffer` 额外用 `read_only=False` 加载一份 `wb_styled`（阈值 `_STYLE_LOAD_MAX_BYTES = 8MB`，超过就跳过样式判定，避免大文件 OOM），行号映射 `row_excel = header_idx + 2 + r_off`。

### 5.3 测试

`backend/tests/test_underline_pdf_xlsx.py`（8 个）+ `test_docx_underline.py`（5 个）：

| 用例 | 断言 |
|---|---|
| PDF 单线段 | 插入恰好 1 个 `____` |
| 整页宽线 | 忽略（页框） |
| 表格内线段 | 忽略 |
| 已含 `____` | 不重复插 |
| xlsx 单下边框 | 写 `____` |
| xlsx 四边网格 | 不算 |
| xlsx 富文本 run | 下划线文字 → `<u>` |
| 端到端 `parse_excel_buffer` | 行文本含 `____` |

```
13 passed（pdf/xlsx 8 + docx 5）
```

---

## 6. 验证总表

| 项 | 命令 | 结果 |
|---|---|---|
| 门禁 | `python backend/scripts/gates/gate_all.py --quick` | **4/4 PASS**（L0 3.9s / L1-G 0.2s / L1 5.8s / L1-H 0.2s） |
| 类型 | `npx vue-tsc --noEmit` | **exit 0** |
| 下划线单测 | `pytest tests/test_underline_pdf_xlsx.py tests/test_docx_underline.py -q` | **13 passed** |
| 复核接口 | accept / reject 实测 | 双路径通过，reject 同时还原 point_id + sub_category_id |
| 三端截图 | chrome-headless-shell 1440 / 834 / 390 | `scrollWidth - innerWidth = 0`，console 错误 0 |
| 版本号 | `/health` + 角标 | 均 `v2.0.0`，无 `c4639296 · f88b771` 双串 |

截图产物：`C:/Users/21499/AppData/Local/Temp/shots_v8b/{pc,tab,m}_point_review.png`

---

## 7. 数据变更与回滚

| 变更 | 备份 | 回滚 |
|---|---|---|
| `point_assign_audit` 增 2 列 | `question_bank_pre_v8c_20261114_212539.db` | 直接用备份覆盖（先停服务、同步删 `-wal/-shm`） |
| 462 题考点+知识点 | 同上 | `reclassify_points.py --revert --batch-id v8-fix-sc` |
| 195 题补空知识点 | 已并入 v8c 备份 | 同上（按 `source_batch` 筛） |
| 19 题 + 2 组材料横线 | `..._pre_blanks_20261114_212839.db` | 用备份还原 |

---

## 8. 遗留清单

| 项 | 数量 | 处理建议 |
|---|---|---|
| 待人工复核 | 996 | 教师端「考点复核」逐条过；确认=保留，驳回=还原 |
| 仍未定位考点 | 444 | 多为图片题/纯材料题，需题干补全 |
| 材料缺失复合题 | 8（3937/3938/3942/3947/4065/4077/4080 等） | 需原始 docx/PDF 重新导入 |
| 配图缺失 | 80 张（13 条引用文件已不在磁盘） | 需原图库；当前显示「配图缺失」占位 |
| 缺横线未回填 | 2（3800/4214） | 3800 需原文，4214 划线为整句 |
| 探测账号 | `qa_v8_teacher`（user_id 28） | 仅供复核页自测，可随时 DELETE |

---

## 9. 涉及文件

**后端**

- `backend/app/services/taxonomy/classifier.py`（拆分 + `classify_cross` / `expected_sub_category`）
- `backend/scripts/taxonomy/reclassify_points.py`（`--fix-subcategory`）
- `backend/scripts/taxonomy/migrate_v8c.py`
- `backend/scripts/taxonomy/backfill_blanks_apply.py`（`MATERIAL_REPLACEMENTS`）
- `backend/app/api/v1/exam/point_review.py`（sc 快照 + 驳回同步还原）
- `backend/app/services/question_ingest/pdf_underline.py`（新）
- `backend/app/services/question_ingest/xlsx_underline.py`（新）
- `backend/app/services/question_ingest/pdf_reader.py`（接线）
- `backend/app/services/question_ingest/excel_reader.py`（接线）
- `backend/tests/test_underline_pdf_xlsx.py`（新，8 用例）

**前端**

- `src/views/teacher/pc/PointReview.vue`（新，约 480 行）
- `src/router/index.ts`（`/teacher/point-review`）
- `.vtj/vue/TeacherNavHeader.vue`（导航项 + 窄屏横向滚动样式）

---

## 10. 审批栏

| 项 | 结论 |
|---|---|
| 四项授权范围（m03808） | 全部实施完毕 |
| 设计器方案 | 见 3.4，A 已落地、B 待你确认是否要建 |
| 是否需要我把方案 B 也建出来 | 待你拍板（不建不影响使用） |

