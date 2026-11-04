# 备考资料 · 三轮 PC 建卡入口与全图查看（方案与验收）

> 版本：v1（2026-11-02）
> 分支：`feat/Study-Material-Management-r3`（父分支 `feat/Study-Material-Management-r2@ead5313`，`main` 未触碰）
> 范围：①PC 学生端「创建卡片」入口 ②资料页「返回首页」镜像修复 ③PC 卡片配图全图查看 ④还原学生端 Excel 批量上传（两种方式并存）

---

## 1. 需求对照

| # | 你的原话 | 结论 | 落地位置 |
|---|---|---|---|
| 1 | 电脑端学生没有创建卡片的按钮和功能，补上 | 三个科目资料页顶栏下方新增操作条：`[提示] [Excel 批量导入] [＋ 创建卡片]` | `src/utils/materialsCreateEntry.ts`（DOM 注入）＋ `src/main.ts` |
| 2 | 左上角「返回首页」按钮上的字被翻转了 | **类名冲突**：同页翻卡背面 `.back{transform:rotateY(180deg)}` 与顶栏链接 `<a class="back">` 撞名，链接文字被镜像 | `src/style/index.scss` 定向复位 `.mat-page > .top-bar > .back` |
| 3 | 图片在电脑端展示不全，要有点击看全图 | 配图区可点，打开全屏「全图查看器」：缩放 25% 步进（≤300%）、左右切换、Esc 关闭、滚轮缩放 | `src/components/materials/ImageLightbox.vue`、`src/views/pc/material_detail.vue` |
| 4 | 还原学生端 Excel 上传，两种创建方式并存，处理好接口连接 | 创建页改为双 Tab：`逐张创建`（免审即时公开）／`Excel 批量导入`（真实接口，进待审队列）；手机端弹层底部同一入口 | `src/views/student/material_upload.vue`、`src/components/materials/CardCreateForm.vue`、后端 `_item_brief.image_urls` |

---

## 2. 关键决策与根因

### 2.1 「返回首页」为什么会被镜像

`materials_{xingce,shenlun,gongzhuan}.vue` 页面 `<style scoped>` 里有两处 `.back`：

```css
.back { cursor:pointer; color:#5a6b85; font-size:14px; }          /* 顶栏链接（line 316） */
.back { background:#fff; transform: rotateY(180deg); ... }         /* 翻转卡背面（line 399） */
```

同一个作用域内两个 `.back` 规则叠加，`<a class="back">← 返回首页</a>` 一起吃到了
`rotateY(180deg)` → 文字水平镜像、箭头跑到右边。

**R3 约束**：AI 不得改 `.vtj` 页面 `<template>`，因此不在模板里改名，改用一条全局样式
只对顶栏内的 `.back` 复位（`transform: none !important`），翻卡背面不受影响。
彻底方案是在设计器里把顶栏链接改名为 `.back-link`，改完即可删掉这条覆盖。

### 2.2 PC 建卡入口为什么用 DOM 注入

三个资料页都是 VTJ 低代码页（`.vtj/vue/materials_*.vue`），按 R3 不能改模板；
沿用「我的徽章」入口（`profileBadgeEntry.ts`）同一套路：hashchange + 1.2s 兜底轮询，
在 `.mat-page > .top-bar` 之后插入一行操作条，路由切走自动移除、页面重渲染自动补回。

选择「顶栏下方独立一行」而不是塞进顶栏的原因：顶栏是
`justify-content: space-between` 的三段式布局，插入第 4 个 flex 子项会把标题挤偏；
独立一行右对齐既不破坏原布局，也能放「两种方式」的说明文案。

### 2.3 Excel 与逐张创建的口径（这次特意没有合并）

| 方式 | 入口 | 落库 | 是否需审批 |
|---|---|---|---|
| 逐张创建 | 手机端「＋创建」/ PC 操作条「＋ 创建卡片」 | `POST /api/materials/my/card` | **免审**，`status=1` 立即公开 |
| Excel 批量 | PC 操作条「Excel 批量导入」/ 创建页第二个 Tab / 手机端弹层底部链接 | `POST /api/materials/my/upload` | **进待审队列**，`status=0`，管理员上架后公开 |

批量导入保留待审是「还原」原行为：一次几十张卡片如果直接公开，没人兜底。
页面上两处文案都写明当前口径，避免学生以为上传失败。

### 2.4 「一卡两图」在列表里拿不全 → 后端补 `image_urls`

第 1 张图存 `cover_image`、第 2 张存在 `content` 的 `<img>` 里，而列表接口
`_item_brief` 不返回 `content`（文章正文太大）。于是详情页只拿得到 1 张封面，
「看全图」里永远只有 1 张。

修法：`_item_brief` 增加 `image_urls`（封面 + `content` 内 `<img>`，去重保序），
前端 `collectCardImages()` 优先用它，拿不到再回退解析 `content`。
这样列表页一次请求就能拿到全套配图，不用为每张卡再发详情请求。

---

## 3. 变更清单

### 后端
| 文件 | 变更 |
|---|---|
| `backend/app/api/v1/library/materials.py` | `_item_brief` 新增 `image_urls`（+`_brief_images()` 与 `re` 导入） |
| `backend/tests/test_materials_my_upload.py` | 新增 7 条：xlsx 进待审、csv 支持、缺列 400、无效科目、未登录、brief 两图、无图空数组 |

### 前端
| 文件 | 变更 |
|---|---|
| `src/utils/materialsCreateEntry.ts` | 新增：三科资料页「创建卡片 / Excel 批量导入」操作条（DOM 注入，含样式与销毁） |
| `src/main.ts` | 挂载 `installMaterialsCreateEntry()` |
| `src/utils/materialImages.ts` | 新增：`collectCardImages()`（优先 `image_urls`，回退解析封面+content） |
| `src/components/materials/ImageLightbox.vue` | 新增：全图查看器（缩放/切换/Esc/滚轮/遮罩点击关闭、锁定 body 滚动） |
| `src/views/pc/material_detail.vue` | 配图区可点 + 常显「点击看全图（N 张）」角标 + `ImageLightbox`；`Card` 类型补 `image_urls`/`content` |
| `src/views/student/material_upload.vue` | 改写为双 Tab：逐张创建（内嵌表单）/ Excel 批量导入（真实接口、结果明细、`?tab=excel` 深链） |
| `src/components/materials/CardCreateForm.vue` | 手机端弹层底部加「一次多张？改用 Excel 批量导入」入口 |
| `src/modules/library/api.ts` | `LibraryMaterial` 补 `image_urls` |
| `src/style/index.scss` | 顶栏 `.back` 复位（修镜像） |
| `src/utils/__tests__/{materialImages,materialsCreateEntry}.spec.ts` | 新增 17 条单测 |

### 脚本与产物
- `scripts/verify/pc_create_and_image_shots.mjs`（13 断言 + 7 图）
- `scripts/verify/mobile_excel_entry_shots.mjs`（4 断言 + 2 图）
- `scripts/verify/cleanup_round3.py`（演示卡与本次待审行清理，`--dry` 可预演）
- `scripts/verify/gen_demo_images.py` + `docs/plans/assets/备考资料_三轮验收/_素材/`（演示配图）
- `docs/plans/assets/备考资料_三轮验收/01~09.png`

---

## 4. 验收证据

### 4.1 自动化断言

| 套件 | 结果 |
|---|---|
| `pc_create_and_image_shots.mjs` | **13/13 PASS**：返回首页 `transform=none`、入口两按钮、双 Tab、`?tab=excel` 深链、真实导入「已提交 5 张」、详情配图、全图 1/2→2/2、125% 缩放、Esc 关闭 |
| `mobile_excel_entry_shots.mjs` | **4/4 PASS**：手机弹层有 Excel 入口、可进 Excel 面板、`docW=390=innerWidth` 无溢出 |
| `pytest tests/ -k material` | **157 passed**（另有 3 条 `test_material_parser.py` 因沙箱禁止写 pytest 临时目录报 `PermissionError`，与本轮改动无关） |
| 新增两个测试文件 | 7 + 17 条全绿 |
| `vitest run`（全量） | **33 文件 / 454 passed** |
| `vue-tsc --noEmit` | **0 error** |
| `gate_all.py` | **10/10 通过** |

### 4.2 效果图

| 图 | 说明 |
|---|---|
| `01_PC资料页_返回首页正常且含建卡入口.png` | 顶栏「← 返回首页」恢复正常，下方新增操作条 |
| `02_创建页_逐张创建.png` | 双 Tab 的第一个：原逐张表单 |
| `03_创建页_Excel批量导入.png` | 第二个 Tab：限额说明 + 科目 + 拖拽上传 |
| `04_创建页_Excel导入结果.png` | 真实接口返回「已提交 5 张 · 待审核」 |
| `05_PC详情页_配图可点.png` | 卡片配图 + 常显「点击看全图（2 张）」 |
| `06_全图查看器_第1张.png` | 全屏弹层：1/2、缩放控件、左右切换 |
| `07_全图查看器_第2张放大.png` | 第 2 张 + 125% 放大 |
| `08_手机端_创建弹层_Excel入口.png` | 手机端弹层底部的 Excel 入口 |
| `09_手机端_Excel导入.png` | 手机端 Excel 面板（390px 无溢出） |

### 4.3 数据卫生

```
验收前：已公开 99（96 卡片 + 3 文章）、下架 0
验收产生：演示卡 1 张（2 图）+ Excel 待审 5 条
验收后：已公开 99、下架 0（cleanup_round3.py 已清理，配图一并删除）
```

---

## 5. 已知不足

1. **`.back` 镜像靠 CSS 覆盖修**：模板里类名仍冲突，建议在设计器把顶栏链接改成 `.back-link`（R3 限制 AI 改模板）。
2. **PC 建卡入口是 DOM 注入**：VTJ 页面若改结构（`.mat-page > .top-bar` 变化）会失效；1.2s 轮询在极端情况下可能有一次闪烁。
3. **Excel 通道仍是待审**：如需与逐张创建一样免审，后端把 `/my/upload` 的 `status=0` 改 `1` 即可（一行），但届时批量内容无兜底。
4. **全图查看器只做了缩放/切换**，没做拖拽平移与双指缩放（触屏端建议后续补）。
5. 手机端卡片详情仍未接全图查看器（本轮需求只点名电脑端）。
6. 沙箱限制：`pytest` 需要写 `%TEMP%` 的三条解析器测试在受限沙箱下报 `PermissionError`，属环境问题。

---

## 6. 回滚

```bash
git checkout feat/Study-Material-Management-r3
git revert <commit>        # 或 git reset --hard ead5313
# 无表结构变更；后端改动仅为响应多一个字段 image_urls
# 若残留验收数据：python scripts/verify/cleanup_round3.py
```
