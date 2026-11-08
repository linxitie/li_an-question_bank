# 资料管理：ID 连续与排序 —— 交付记录（v1）

> **状态**：✅ **已完成**（2026-11-08）｜方案：[资料管理_ID连续与排序_修复方案_v1.md](资料管理_ID连续与排序_修复方案_v1.md)
> **拍板**：D1=**A（展示序号）** ｜ D2 序号=当前筛选内 ｜ D3 回收站显示「—」 ｜ D4 按 ID 序合成补记 ｜ D5 抽屉/悬停看真实 ID
> **分支**：`feat/material-multi-format-import`（未合并、未触碰 main）

---

## 1. 两个缺陷的真因（复述，避免以后又查一遍）

| 缺陷 | 真因 | 证据 |
|---|---|---|
| ①列表 ID 从第二页起不像降序 | **58 条历史资料（ID 48–105）`create_time` 为 NULL**，列表 `null_last` 把它们排到最后一页 | `select count(*) from study_material where create_time is null` → 58，区间连续 48–105；翻页实测**严格递减、0 重复**，排序逻辑本身没坏 |
| ②删除后 ID 不减、最大 ID ≠ 总数 | **软删除保号**（回收站 9 条仍占 ID）+ 历史缺号 11–13 | 128 行 / 最大 ID 131 / 在用 119；`exam_paper` 无 `material_id` 列，"ID 与试卷绑定"不成立（关联键是 `paper_code`） |

---

## 2. 改了什么（5 个文件）

| 文件 | 改动 |
|---|---|
| `backend/app/models/models.py` | `StudyMaterial` 新增 `list_time`（默认 `now`，索引）：列表排序键，与 `create_time`（真实上传时间）分离 |
| `backend/app/main.py` | 启动期自动补列 `list_time` + 索引 + 回填（`COALESCE(create_time, update_time, '2026-10-28 21:26:44')`）；实测日志「添加列 list_time + 索引 / 回填 128 行」 |
| `backend/app/api/v1/library/materials.py` | ①`order` 参数支持 `id_desc`（**默认**）/`id_asc`/`created_desc`/`created_asc` ②排序键 `list_time desc, material_id desc`（NULL 仍排最后）③响应每行加 `seq`（当前筛选内倒序名次，首行 = total）④**恢复时** `list_time = now` → 置顶 |
| `backend/scripts/backfill_material_create_time.py` | **新增**：补 58 条缺失的 `create_time`（dry-run 默认，`--apply` 才写；每条 +1s 从 `2026-10-28 21:26:45` 起，文档标明"补记"） |
| `src/modules/library/api.ts` | `order` 类型放宽 + 默认改 `id_desc`；`AdminMaterialListItem` 加 `seq?: number` |
| `src/views/admin/materials.vue` | 「ID」列改「编号」显示 `seq`（回收站显示「—」，悬停 `title` 显示真实 ID）；默认排序 `id_desc`；「上传时间」列只在按时间排序时显示箭头；`toggleOrder` 只在 `created_asc/desc` 间切换 |
| `backend/tests/test_materials_id_seq.py` | **新增** 8 例（见 §4） |
| `src/modules/library/__tests__/api.adminList.spec.ts` | 默认参数期望改 `id_desc`，新增「显式 order 透传」1 例 |

---

## 3. 语义（写清楚，避免以后误解）

- **列表显示的"编号"= 连续序号 `seq`**，不是主键。口径 = **当前筛选结果内**：首行 `seq == total`，往下递减到 1；正序（`id_asc`）时按 1..N。
- **删除中间一条**：它上方（更新的）行整体 -1，下方不变 → 最大序号恒等于当前总数。
- **恢复回收站资料**：`list_time = now` → 排到第一行，`seq == total`（等价"最大号 + 1"），**不复用旧号**；`create_time`（上传时间列）**保持真实不变**。
- **回收站视图**：不参与编号，编号列显示「—」。
- **真实主键**：悬停在编号格显示 `内部 ID: N`（排障用）；接口路径/审计日志仍用真实 ID，**没有任何数据迁移**。

---

## 4. 验证结果

### 4.1 pytest（8 例，全绿）

| 用例 | 断言 |
|---|---|
| 默认排序 + 连续序号 | `ids` 严格递减；`seq == [total, total-1, …]` |
| 翻页不重不漏（25 条 / 每页 10） | 25 行 0 重复，`seq == 25..1` |
| 删除中间一条 | `total 5→4`，`seq == [4,3,2,1]`，`max(seq) == total` |
| 恢复置顶 | 首行即该资料，`seq == total`；`create_time` 不变、`list_time` 变新 |
| 序号口径随筛选 | 只筛行测时 `total=2`、`seq=[2,1]` |
| 按上传时间排序仍可用 | `created_asc/desc` 仍按真实时间 |
| 正序模式 | `id_asc` → `seq == [1,2,3]` |
| 新建资料置顶 | 新建后首行 = 新资料，`seq == total` |

### 4.2 线上实测（真实库）

| 步骤 | 结果 |
|---|---|
| 默认列表 | `total=119`，p1 `seq=119..110`、p2 `109..100`、p3 `99..90`；翻 12 页 **119 行 0 重复**，ID 严格递减，`seq` 连续到 1 |
| 补 58 条时间 | `create_time IS NULL` → **0**；48 号 = `2026-10-28 21:26:45`、105 号 = `21:27:42`（每条 +1s） |
| 恢复 #46（回收站） | 列表首行变成 #46，`seq=120=total(119→120)`；`create_time` 仍 `2026-10-29 08:27:22`、`list_time` 刷成 `2026-11-08 15:53:11` |
| 再删回回收站 | `total` 回到 119，#46 不在列表；数据与验收前一致（仅 `list_time` 变化，回收站视图不显示） |

### 4.3 前端

- `vue-tsc --noEmit`：**0 错误**
- `vitest run`：**56 文件 / 620 测试全通过**（原 619 + 本次 1）

### 4.4 门禁

`OPENAPI_URL=http://127.0.0.1:8001/openapi.json python scripts/gates/gate_all.py` → **9/10 通过**：
L0 / L1 / L1-H / L2 / L3 / **L4** / L5 / L6 / L7 全 PASS；唯一 FAIL 是**既有红 L1-G**（本机题库 200 题 < 下限 3085/3632，与本批无关）。
L4 PASS 同时说明 **API 面仍 343**（只加了 query 参数与响应字段，没有新端点）与**模块边界新增 0 条**。

---

## 5. 没做什么（明确边界）

- **没有重排主键**（方案 B 被否）：`material_id` 一行未改，3 张引用表（progress 24 / share 1 / file 6）与 519 条审计日志保持原义。
- **没有修复那 3 个缺号（11–13）**：它们是历史硬删留下的空洞，软删除方案下无法"补回"，序号方案也不需要它们连续。
- **没有动"上传时间"的真实性**：58 条是**补记**（合成值），文档与脚本都标注清楚；如需真实值，只能从当年的导入日志回溯（不可得）。

---

## 6. 回滚

| 层 | 操作 |
|---|---|
| 1 排序 | 前端 `?order=created_desc` 即回到"按上传时间"旧表现；后端代码 revert 后默认恢复 `created_desc` |
| 2 代码 | `git revert <本批提交>`；`list_time` 是新增列，保留不影响旧代码（旧代码不读它） |
| 3 数据 | 快照 `backend/data/question_bank.db.bak_before_p5_20261108_155035`（补时间前，128 行，integrity ok）；补时间脚本只碰 `create_time IS NULL` 的 58 行，可用快照整库还原 |

---

## 7. 复核命令

```powershell
cd li_an-question_bank\backend
$env:PYTHONIOENCODING="utf-8"

# 8 条专项
python -m pytest tests/test_materials_id_seq.py -q

# 跨页与序号（只读，线上库）
python ..\..\_run\verify_id_sort.py

# 补时间清单（dry-run，不写库）
python scripts/backfill_material_create_time.py

# 门禁
$env:OPENAPI_URL="http://127.0.0.1:8001/openapi.json"
python scripts/gates/gate_all.py
```
