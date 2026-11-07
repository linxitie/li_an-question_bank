# A4b 管理端删除改为软删除 + 回收站 交付记录 v1

- 日期：2026-11-07
- 分支：`feat/material-multi-format-import`（提交见文末；**未合并 main、未推送远端**）
- 触发：清理两条测试资料（121/122）时实测发现「管理员删除」是**物理删除**，与已批准的
  `试卷管理收敛_单一入口与上架即审批_方案_v1.md` §2.2「（删除）|-1|软删除」不符 → 用户裁定 **B：改成软删除**。
- 归属：A 批（A4 资料管理新页的删除闭环补齐），编号 **A4b**，不占用 B 批顺位（B 批仍按 B3 → B1 → B2 执行）。

---

## 1. 问题实录（修改前）

| 项 | 实测 |
|---|---|
| `DELETE /api/materials/admin/{id}` | `db.delete(m)` **物理删除**，并 `delete()` 掉该资料的 `user_material_progress` |
| `DELETE /api/materials/admin/batch` | 同样物理删除；**且该路由声明在 `/admin/{material_id}` 之后 → 永远命中 422**（`material_id="batch"` 无法转 int），批量删除从来就没调通过 |
| 只有 `DELETE /api/materials/my/{id}` | 才是 `m.status = -1` 软删除 |
| 后果 1 | 121/122 两条测试资料**不可恢复地消失**（实测物理行数 0，`max(material_id)=120`） |
| 后果 2 | `admin_stats.by_status.deleted` 的 5 条（16/20/25/46/47）全部来自学生端软删，管理员删除不会让它增加 → 统计与直觉不符 |
| 后果 3 | A4 页删除确认框原写「软删除，可在 C 批回收站恢复」——**文案与实现相反**，用户会以为能恢复 |

## 2. 改法与理由

| 改动 | 文件 | 为什么 |
|---|---|---|
| 单条删除 → `status=-1` | `backend/app/api/v1/library/materials.py`（`admin_delete`） | 与 §2.2 一致；误删可恢复 |
| **不再删学习进度** | 同上 | 恢复后学生进度还在；彻底清理由后续「回收站·彻底删除」承担（B/C 批可加） |
| 幂等 | 同上 | 对已删除行再删返回 `{"ok":true,"already_deleted":true}`，不报 404，避免前端重复点击报错 |
| 批量删除 → `status=-1` + `.filter(status>=0)` | 同上（`admin_batch_delete`） | 已删除的不重复计数；`UPDATE` 一条 SQL，比逐行 `delete` 更省 |
| **路由顺序前移** | 同上 | `DELETE /admin/batch` 必须声明在 `DELETE /admin/{material_id}` **之前**，否则被动态段吞掉（Starlette 按声明顺序匹配，422 不会回退到下一条路由） |
| 恢复 = `PUT /admin/{id}/status {status:0}` | 同上（`admin_set_status`） | 不新增端点（R11 基线 343 不变）；恢复默认落**未上架**，管理员再点「上架」才对学生可见，避免误恢复到已发布 |
| 恢复审计单列 | `_audit` 映射新增 `restore → 恢复资料` | 审计里能区分「恢复」与普通上/下架 |
| 前端：状态下拉新增「回收站（已删除）」 | `src/views/admin/materials.vue` | 复用已有 `?status=-1`，不新增接口 |
| 前端：删除行只显示「预览 / 恢复」，隐藏上架开关与删除 | 同上 | 已删除的行不能再"上架"，也不能再删一次 |
| 前端：删除确认文案改为「移入回收站…数据保留、学习进度保留，可随时恢复」 | 同上 | 文案必须与实现一致 |
| 前端：恢复确认说明「恢复为未上架，学生仍不可见」 | 同上 | 管理员的常见误解是"恢复=学生立刻能看到" |

## 3. 实测证据

### 3.1 后端（活体 8000，真实数据）

```
before      : total=112 published=102 draft=10 deleted=5
DELETE 110  -> 200 {"ok":true}
after delete: total=111 published=101 deleted=6          ← 只减在用、deleted 才 +1
默认列表含 110 : False
回收站含 110   : True   | 回收站条数 6
DELETE 110 再点 -> 200 {"ok":true,"already_deleted":true} ← 幂等
PUT status=0   -> 200     after restore: total=112 published=101 draft=11 deleted=5
PUT status=1   -> 200     final      : total=112 published=102 draft=10 deleted=5
data restored=True                                        ← 实验数据已还原
DELETE /admin/batch {ids:[]} -> 400 "ids 不能为空"          ← 路由已可达（修复前是 422）
```

### 3.2 前端（headless Chrome + CDP，1600×1000）

| 检查 | 实测 |
|---|---|
| 状态下拉切「回收站（已删除）」 | 顶部出现提示 `回收站：只看已删除资料，点「恢复」可还原` |
| 列表 | 共 5 条（47/46/25/20/16），状态列 `已删除`（danger 色 `rgb(194,65,12)`） |
| 操作列 | 只有 `预览`（`rgb(64,84,224)`）/ `恢复`（`rgb(15,122,77)`）；**无上架开关** |
| 点「恢复」 | 弹窗标题「恢复资料」，正文「恢复后为『未上架』状态，学生仍不可见；需要再点『上架（=审批通过）』才可见。确认恢复「细节判断题避坑」？」，按钮 取消 / 恢复；点取消后行数仍 5、数据未变 |
| 点「删除」（默认视图） | 弹窗标题「移入回收站」，正文「移入回收站后学生端立即不可见，数据保留、学习进度保留，可随时恢复。确认删除「继续盘问的适用对象？（第2组）」？」，按钮 取消 / 移入回收站；点取消后行数仍 20 |
| 截图 | `docs/plans/assets/资料管理v3/A4b_回收站视图.png` |

### 3.3 测试与门禁

| 项 | 结果 |
|---|---|
| `pytest tests/test_materials_soft_delete.py` | **13 passed** |
| 资料相关四套 pytest（soft_delete / stats_scope / a2_meta / a3_preview） | **45 passed** |
| `npm run typecheck` | exit 0 |
| `npm run test:unit` | **48 文件 / 545 用例全通过** |
| `gate_all.py` | 见 §5 |

## 4. 新增测试（`backend/tests/test_materials_soft_delete.py`，13 例）

- 删除后**行还在**且 `status=-1`；学习进度**保留**；默认列表消失、`status=-1` 可查；
- 统计 `total -1` / `published -1` / `deleted +1` 三者同步；
- 重复删除幂等（`already_deleted`）；删不存在的行 404；教师删除 403 且行状态不变；
- 恢复 → `status=0`、回到默认列表；恢复写「恢复资料」审计；`PUT status=-1` 仍被 400 拒绝（删除只能走 DELETE）；
- 批量删除软删 2 条；已删除的不重复计数；空 `ids` 400。

## 5. 门禁

`python backend/scripts/gates/gate_all.py` → **9/10 通过**：

```
PASS L0 / L3 / L1 / L1-H / L2 / L4 / L5 / L6 / L7      （L6 105 处 import、L7 5 passed，页面数不变）
FAIL L1-G  ❌ 护栏/公专: 200 题（下限 3085） ❌ 护栏/总数: 200 题（下限 3632）
gate_all: 9/10 通过
```

L1-G 是**本机既有的红**（本机题库只有 200 题，语料总量未达标），与本次改动无关，A0–A5 各批同样如此。

## 6. 遗留与提醒

1. **彻底删除尚无入口**：现在只能软删 + 恢复，没有「彻底删除」。回收站里堆积的历史行（16/20/25/46/47）如需清除，等 B/C 批加 `purge`（仅超管 + 二次确认）。
2. **`admin_stats.by_status.deleted` 语义已变**：从"学生端软删数"变成"所有软删数"，管理页 5 格统计里不展示它，不影响用户看到的数字。
3. **B 批顺序不变**：B3（讲义落 card 修复 + 重复检测）仍是 B 批第一件事。
4. 唯一一处历史损失不可挽回：121/122 两条测试资料（重复导入的讲义样本）已物理消失；它们本来就是同一份 `04_讲义_正常.docx` 的两次重复上传，不影响真实数据。
