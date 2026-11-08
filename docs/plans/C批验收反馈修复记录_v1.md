# C 批验收反馈修复记录 v1（两个缺陷）

- 日期：2026-11-08
- 触发：你在 C 批人工验收中报的两个问题
- 结论：**都是缺陷，已修并回归**；数据侧也已修好已有的那条（material 127）

---

## 缺陷 1：C2a 上传后试卷没有编号

### 现象（你的验收截图）

`2024国考·公专题本.docx` 走「批量导入」→ 生成 material **127**，列表副标题是 `—`，
抽屉「试卷信息」里 **编号 `—`**，但年份 2024 / 地区 国考 / 卷别 题本都正常。

### 根因

`paper_code` 只在**两个地方**生成过：C4 反向补录（`paper_backfill`）与 C2b 改信息（`PATCH meta`）。
**B2 的上传端点 `POST /admin/files/upload` 漏了这一步**——文件名解析器写好了，却没有在"建资料"时调用它，
于是 `paper_code` / `badge` 都是空。预览里的年份/地区能出来，是因为 `paper_block` 会**兜底解析标题**，编号不参与兜底。

### 修法

`backend/app/api/v1/library/materials.py` 的 `admin_upload_file`：建资料时若 `type == 'paper'`，
先 `parse_paper_file_name(stem)`，把解析出的编号同时写进 `paper_code` 与 `badge`（列表副标题取 badge）。
解析不出 → 两个字段都留空（不编造）。

### 验证

```
pytest 新增 3 例：
  · 上传 2024国考·公专题本.docx → m.paper_code == 'GZ-2024-GK-T'，预览编号/年份/地区/卷别齐全，题量 None
  · 上传 扫描件_001.pdf          → paper_code / badge 均为 None（不编造）
  · 上传 讲义类文件              → 不写 paper_code
线上：material 127 已用 PATCH 补编号 → 列表显示 `GZ-2024-GK-T`
```

> 数据侧说明：127 是**本次修复前**创建的，所以用「改信息 → 编号留空 → 保存」补上（等价于自动生成）；
> 以后再上传试卷不用手工补。

---

## 缺陷 2：红字只显示「保存失败」，看不到具体原因

### 现象

改信息里填年份 1800 → 只提示「保存失败」，看不到后端 400 的真实文案。

### 根因

`apiClient` 的 rejection 经过拦截器归一化后是**普通对象**
（`{ type, message, status, code, details }`，见 `src/services/api/types.ts`），**不是 `Error` 实例**。
而业务代码写的是：

```ts
saveError.value = e instanceof Error ? e.message : '保存失败';
```

`instanceof Error` 永远为 false → 永远落到兜底文案。**这是个系统性坑**，
不止改信息：列表加载、删除、恢复、预览、批量导入的失败原因都受影响。

### 修法

新增 `src/utils/apiError.ts` 的 `errorMessage(error, fallback)`，兼容四种形态：
`Error` 实例 / 归一化对象 `{message}` / 后端原始体 `{error:{message}}` / `details.detail` / 字符串。
把 5 个文件里的 `instanceof Error ? … : …` 全部替换：

| 文件 | 位置 |
|---|---|
| `src/components/admin/MaterialMetaDialog.vue` | 加载失败、保存失败、上传失败 |
| `src/components/admin/MaterialBatchUpload.vue` | 队列行失败原因 |
| `src/components/admin/MaterialPreviewDrawer.vue` | 下载失败 |
| `src/views/admin/materials.vue` | 列表加载、上下架、删除、恢复、预览加载 |

### 验证

```
vitest `src/utils/__tests__/apiError.spec.ts` 6 例（归一化对象 / Error / 后端原始体 / details / 字符串 / 兜底）
真机（126 改信息填年份 1800 → 保存）红字：
  「year 需在 1990–2100 之间，收到 1800」
```

截图：`docs/plans/assets/资料管理v3/C2b_02_错误原因显示具体文案.png`

---

## 回归

| 项 | 结果 |
|---|---|
| `pytest`（B2 + C2b + C2/C4 + 解析器 + API 基线 + B1 + B3 + 软删，9 套） | **121 passed** |
| `vitest`（全量） | **54 文件 / 605 用例** |
| `npm run typecheck` | exit 0 |
| `gate_all.py` | **9/10**（唯一 FAIL 仍是既有 L1-G） |

---

## 顺带发现的数据情况（你验收过程中产生的，供你决定）

| 资料 | 现状 | 说明 |
|---|---|---|
| #125 2019 北京 | `category=历年真题`；`paper_meta={"total_score":100.0,"duration":120}`；**挂了 1 个原件 `单独一份试卷·模拟卷.pdf`** | 分类/订正是你按 C2b-2 做的；那个 PDF 是你验 C2b-6 时上传的测试文件，**语义上不该挂在 2019 北京真题上** |
| #126 2017 江苏 | 无订正、无原件 | — |
| #127 2024 国考 | 编号已补 `GZ-2024-GK-T`，有 1 个原件（上传的 docx） | 本次新建 |
| 在用资料 | **119**（paper 3、lecture 4、card 109、article 3） | — |

**要清理的话告诉我**（没有"删原件"入口）：可以删掉 #125 上那个 `模拟卷.pdf`（行 + 物理文件），
或把 #125 的 `paper_meta` 订正一并清空、#123/#124「同名资料」两条测试资料软删。
