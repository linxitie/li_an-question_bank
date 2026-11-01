# 备考资料 · 二轮 UI 修正与学生自建卡（方案与验收）

> 版本：v1（2026-11-01）
> 分支：`feat/Study-Material-Management-r2`（父分支 `feat/Study-Material-Management@ce19649`，`main` 未触碰）
> 范围：手机端徽章「精选」可视化、去掉设计器悬浮钮、学生端「创建卡片」重构（去 Excel、免审批）、管理员端 Excel 批量导入复核

---

## 1. 需求对照（用户 5 条 → 落地项）

| # | 用户原话要点 | 结论 | 落地位置 |
|---|---|---|---|
| 1 | 设为精选后界面无变化、弹层按钮仍显示「设为精选」；要求卡片左上角 + 弹层右侧出现金色五角星，按钮改「取消精选」 | **根因是后端 `/api/badges/my` 从不返回 `pinned`**，前端无处可读 → 已在契约层补齐并加星标 | `backend/app/api/v1/library/badges.py`；`src/components/badge/{PinStar.vue,BadgesGrid.vue,BadgeDetailModal.vue}`；`src/views/student/badges.vue` |
| 2 | 去掉右下角悬浮铅笔按钮 | 该按钮不是业务代码，是 `@vtj/pro` 开发期注入的设计器入口 `#vtjLink`（z-index 9999） | `src/style/index.scss`（全局隐藏，设计器仍可直连 `/__vtj__/`） |
| 3 | 手机端学生没有上传入口；要「创建卡片」按钮 → 选科目 → 弹层填字段 + 传 1~2 张图 → 保存即建卡；学生端不要 Excel；不重叠 | 顶栏右侧新增「＋创建」；两步弹层（选科目 → 表单，字段与 Excel 列一一对应）；新端点免审批直接公开 | `src/views/student/mobile/mobile_materials.vue`；`src/components/materials/{CardCreateForm.vue,cardDraft.ts}`；`backend/.../materials.py` 新增 `POST /api/materials/my/card`、`GET /api/materials/taxonomy` |
| 4 | 检查管理员端有无表格上传接口与按钮，保留 Excel 批量导入 | **已有且可用**：`智能导入` 按钮 + 4 步向导（上传→解析→列映射预览→确认入库） | `.vtj/vue/admin_materials.vue`（未改动模板，仅复核）；后端 `/api/materials/admin/import/*` |
| 5 | 自测两端上传功能并给效果图 | 两套 CDP 自动化脚本，22 项断言全通过，10 张效果图 | `scripts/verify/mobile_create_and_pin.mjs`、`scripts/verify/admin_import_shots.mjs`、`docs/plans/assets/备考资料_二轮验收/` |

---

## 2. 根因分析（先证后改）

### 2.1 「设为精选」点了没反应

实测（真实账号 202516001）：

```
GET /api/badges/top  → {"items":[{"kind":"achievement","id":2},{"kind":"achievement","id":1}]}   # 写入成功
GET /api/badges/my   → 57 条，逐条无 pinned 字段                                                # 读取缺失
```

`badges.py` 里 `/wall` 逐条写了 `pinned`，`/my` 却漏了 → 前端 `it.pinned` 永远是 `undefined`：
网格不显示精选标记、弹层按钮永远走 `'设为精选'` 分支。**写入链路本来就是通的，是读契约缺字段。**

修复：`/my` 先取 `_top_keys()` 得精选集合，再逐条 `"pinned": achievement_id in pinned_ids`；
称号固定 `pinned: false`（`/top` 只收 achievement）。

### 2.2 悬浮铅笔按钮

`document.querySelectorAll('*')` 中唯一的可疑元素：

```json
{"tag":"DIV","id":"vtjLink","rect":[668,392,40,40],"z":"9999",
 "html":"<div id=\"vtjLink\"><svg .../></div>"}
```

来源确认为 `node_modules/@vtj/pro/dist/entry/link.js`（`createDevTools` 的 `link` 选项注入，
`transformIndexHtml` 仅 serve 期生效，生产构建不存在）。用户要的是「看不到」，
因此选择 **全局 CSS 隐藏**而不是关掉 `createDevTools`：设计器服务端 `/__vtj__/`、
热更新能力全部保留，出问题删掉那段 CSS 即可恢复。

### 2.3 学生端没有建卡入口

- 手机端 `mobile_materials.vue` 顶栏右侧是一个 32px 的空 `spacer`，从未接入口；
- 学生侧唯一的建卡页 `/materials/upload` 是 **Excel 批量上传 + 待审队列**，且没有任何页面链到它；
- 后端其实早就有 `POST /api/materials/my`（支持 `publish=true` 直接公开）与
  `POST /api/materials/admin/cards/batch-image`（≤9 张图，仅管理员）。

即：缺的是「手机端入口 + 单卡表单 + 学生可用的配图通道」，不是整条链路。

### 2.4 顺带修掉的 3 个手机端显示缺陷（验收图暴露）

| 现象 | 证据 | 修复 |
|---|---|---|
| 徽章页第 3 列被右侧裁切 | 390px 视口下 `.bg-card` 右边界 403（溢出 13px） | `BadgesGrid` 新增 ≤600px 断点：卡片内边距 6px、列间距 8px、字号下调；`badges.vue` 手机端外留白 28px→12px |
| 「全部品质 / 黑铁」筛选词被压成两行并溢出 30px 胶囊 | 窄屏下 `.bd-chip` 被 flex 压缩 | `.bd-chip{flex:none;white-space:nowrap}` + 筛选组允许换行 |
| 配图缩略图只显示 alt 文字 | `img.naturalWidth=0`，`src=blob:` | `index.html` CSP `img-src 'self' data:` **不含 `blob:`** → 改用 `FileReader.readAsDataURL` 生成 dataURL 预览 |

---

## 3. 方案

### 3.1 学生建卡：一次 multipart 请求，免审批

```
POST /api/materials/my/card      multipart/form-data
  subject      xingce|shenlun|gongzhuan   （必填）
  card_front   ≤120 字                    （必填）
  card_back    ≤600 字                    （背面为空时必须有配图）
  category     子类名，可空                （空 → 两轮自动分类）
  point_id     考点 ID，可空
  images       0~2 张 png/jpg/webp，单张 ≤5MB
→ 201/200 {id,status:1,subject,title,category,point_id,cover_image,images,warnings,note}
```

设计要点：

1. **免审批**：直接 `status=1`（Q6 已确认学生建卡免审批）。与 `/my/upload`（Excel 批量、`status=0` 待审）并存，
   后者从此不再出现在学生端 UI。
2. **图片落位**：第 1 张 → `cover_image`（封面，列表/详情复用既有渲染）；
   第 2 张 → `content` 里的 `<img>`（详情页 `v-html` 直接显示）。**不改表结构**，
   两处都是既有字段，避免为 1 张图引入列迁移与指纹基线变更。
3. **原子性**：任一图片校验失败（扩展名/魔数/大小）→ 整单 400，并回收本单已落盘文件；素材行不落库。
4. **去重**：`front+back` 的 `content_hash` 命中已有资料 → 409，不产生重复卡。
5. **配额**：与学生批量上传共用同一套额度（当日 50 张 / 累计 500 张），429 时给出中文原因。
6. **分类两级**：`strict=False`，非法候选不阻断建卡，回退自动分类并在 `warnings` 里回报
   —— 交互式表单里让用户「当场改」比整单失败更合理（区别于管理员改卡的 strict 路径）。
7. **审计**：`_audit(action="create", detail="学生建卡：…")`，沿用既有的中文动作映射，不新增英文动作名。

### 3.2 分类法只读接口

表单要「分类 → 考点」两级下拉，但 `sub_categories` / `knowledge_point` 属 catalog 域。
按 P4.1 边界约定，新增 `GET /api/materials/taxonomy?subject=`，内部只经
`app/api/v1/catalog/contract.py` 取数（`category_names` + `point_map` + `category_name_by_id`），
**不直接 import 他域模型**。

**路由顺序**：该端点必须声明在 `GET /{material_id}` 之前，否则会被整数路径参数吃掉返回 422；
已加回归用例 `test_route_not_shadowed_by_material_id` 守住。

### 3.3 前端交互（手机端）

```
备考资料顶栏 [←] 备考资料 [＋创建]
      ↓ 点击
「选择科目」底部弹层：行测 / 申论 / 公专（当前 Tab 高亮）
      ↓ 选一个
「创建卡片」表单：科目分段 → 正面(120) → 背面(600) → 分类 → 考点 → 配图(≤2) → [上一步][保存并公开]
      ↓ 保存成功
toast「卡片已创建并公开展示」→ 自动切到该科目 → 列表刷新（新卡在首位）→ 卡片栈同步
```

- 按钮在 **顶栏内正常流式布局**，不悬浮、不遮挡列表；实测中心点命中判定不落在底部导航上（`overlap=false`）。
- 桌面端 `/materials/upload` 改为同一组件的 `inline` 形态（无遮罩、单页填写），
  **学生端 Excel 上传入口就此消失**；Excel 批量导入只保留在管理员端。

### 3.4 管理员端（复核，未改代码）

`智能导入` → ① 上传（`.docx/.xlsx/.pdf`）→ ② 解析 → ③ 列映射预览（正面列/背面列/分类列 + 前 12 行预览）
→ ④ 选科目/分类 → 「确认入库（下架态）」→ 列表逐条上架。实测 5 行 xlsx 全流程通畅。

---

## 4. 变更清单

### 后端
| 文件 | 变更 |
|---|---|
| `backend/app/api/v1/library/badges.py` | `/my` 增加 `pinned`（成就按精选集合，称号恒 false） |
| `backend/app/api/v1/library/materials.py` | 新增 `GET /taxonomy`（声明在 `/{material_id}` 之前）、`POST /my/card`；`from fastapi import Form` |
| `backend/tests/test_materials_my_card.py` | 新增 15 条：免审公开/1 图封面/2 图入正文/背面可空/四类校验/去重 409/未登录/taxonomy 形状与路由顺序 |
| `backend/tests/test_badge_top.py` | 新增 `test_my_exposes_pinned_flag`（守住本次根因） |

### 前端
| 文件 | 变更 |
|---|---|
| `src/components/badge/PinStar.vue` | 新增：金色渐变五角星（`useId()` 保证同页多实例渐变 id 唯一） |
| `src/components/badge/BadgesGrid.vue` | 卡片左上角星标、精选描边、≤600px 三列装得下的断点；移除原「精选」文字 chip |
| `src/components/badge/BadgeDetailModal.vue` | 弹层右侧星标列（窄屏转绝对定位，底部 46px 避开关闭钮） |
| `src/views/student/badges.vue` | `togglePin` 以服务端为准刷新并重绑 `detailItem`；满 6 枚拦截；chip 不换行；手机端留白 |
| `src/components/materials/CardCreateForm.vue` | 新增：两步弹层表单（科目/正面/背面/分类/考点/配图/校验/提交） |
| `src/components/materials/cardDraft.ts` | 新增：表单规则纯函数（`validateDraft` / `checkImageFile`），供组件与单测共用 |
| `src/views/student/mobile/mobile_materials.vue` | 顶栏「＋创建」按钮、接入弹层、保存后切科目并刷新 |
| `src/views/student/material_upload.vue` | 由 Excel 上传页改写为「创建卡片」内嵌表单页（学生端不再有 Excel） |
| `src/style/index.scss` | 全局隐藏 `#vtjLink` |
| `src/router/index.ts` | `/materials/upload` 标题 → 「创建卡片」 |
| `vitest.config.ts` | 注册 `@vitejs/plugin-vue`（组件挂载单测所需，随 @vtj/cli 已安装，未新增依赖） |
| `src/**/__tests__/{cardDraft, PinStar}.spec.ts` | 新增 12 条单测 |

### 脚本与产物
- `scripts/verify/mobile_create_and_pin.mjs`（12 断言 + 6 图）
- `scripts/verify/admin_import_shots.mjs`（6 断言 + 4 图）
- `docs/plans/assets/备考资料_二轮验收/01~10.png`

---

## 5. 验收证据

### 5.1 自动化断言

| 套件 | 结果 |
|---|---|
| `mobile_create_and_pin.mjs` | **12/12 PASS**（星标 2 枚、悬浮钮不可见、弹层星标与「取消精选」、取消/恢复双向、创建按钮不重叠、配图 1 张、保存后列表首条为新卡） |
| `admin_import_shots.mjs` | **6/6 PASS**（按钮存在、向导打开、5 行解析、预览 5 张、入库成功、库内 +5 条下架态） |
| `pytest tests/test_materials_my_card.py` | **15 passed** |
| `pytest tests/test_badge_top.py` | **8 passed** |
| `vitest run`（全量） | **31 文件 / 440 tests passed** |
| `vue-tsc --noEmit` | **0 error** |

### 5.2 效果图

| 图 | 说明 |
|---|---|
| `01_徽章页_精选星标.png` | 徽章页 3 列完整不裁切，2 枚精选卡左上角金色五角星 |
| `02_徽章弹层_精选星标.png` | 弹层右侧星标 + 「精选」，左下按钮为「取消精选」 |
| `03_手机端_创建入口.png` | 顶栏右侧「＋创建」，无悬浮钮遮挡 |
| `04_创建卡片_选科目.png` | 第一步选科目 |
| `05_创建卡片_填写完成.png` | 第二步表单（已填正面/背面/分类/考点 + 1 张配图缩略图） |
| `06_创建后_列表首条.png` | toast + 自动切申论 + 新卡在列表首位、卡片栈同步 |
| `07_管理端_资料管理_导入入口.png` | 管理端「智能导入」按钮 |
| `08_管理端_导入向导_上传.png` | 向导第 ① 步 |
| `09_管理端_导入向导_列映射预览.png` | 5 行解析 + 列映射 + 预览卡 |
| `10_管理端_导入向导_入库结果.png` | 入库成功提示 |

### 5.3 数据卫生

联调产生的 1 张学生卡 + 5 条导入资料已全部删除，`uploads/materials/images` 下测试图一并清理：

```
已公开资料 97（= 94 张卡片 + 3 篇文章）  下架态 0
```

复现与清理：

```bash
# 跑验收（会真实建 1 张申论卡）
python scripts/verify/cleanup_test_materials.py --dry     # 先看有没有遗留
node scripts/verify/mobile_create_and_pin.mjs             # 15 项断言 + 6 张图
node scripts/verify/admin_import_shots.mjs                # 6 项断言 + 4 张图（会入库 5 条下架资料）
python scripts/verify/cleanup_test_materials.py           # 清掉今日学生自建卡 + 配图
```

> ⚠️ 管理员导入的 5 条是 `status=0` 下架态，清理需在「资料管理」列表逐条删除，
> 或按 `material_id` 直删；本轮已用后者清理干净。
> 另：pytest 全量跑批时真实库会多注册 1 个测试账号（既有行为），本轮已删除，用户数回到 30。

---

## 6. 已知不足

1. **配图只做「封面 + 正文附图」两处落位**，没有独立图集字段；若后续要「一卡 9 图」图集，
   需新增 `image_urls` 列并同步前端画廊（当前 2 张的形态已满足本轮需求）。
2. **未指定考点时卡片会带「通用技巧」标记**（A 方案既有约定）。表单已用提示语告知用户，
   但没有强制选考点；如需强制，应同步评估存量 12 张通用技巧卡。
3. **精选上限 6 枚**：满额时前端弹 `alert` 拦截，未做「替换哪一枚」的选择器。
4. **手机端卡片栈**后层卡按设计向右错位 11px/层，超出视口部分被裁——这是堆叠视觉的一部分，
   不是布局溢出（`document.scrollWidth === innerWidth`）。
5. `POST /api/materials/my/upload`（Excel 批量、待审）**保留未删**：学生端 UI 已无入口，
   端点留作兼容与后续「教师代传」复用；若确认不再需要，可单独提案下线。
6. 设计器悬浮入口是全局隐藏而非删除：**手机端要给用户看设计器入口时需要临时删掉那条 CSS**。

---

## 7. 回滚

```bash
git checkout feat/Study-Material-Management-r2
git revert <merge-or-commit>          # 或 git reset --hard ce19649
# 无数据库迁移、无表结构变更 → 回滚不需要动数据
# 仅需清理本轮若残留的 uploads/materials/images/ 与测试卡片（正常已清理）
```
