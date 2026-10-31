# 合并远端 main 的合并与验收报告 — v1

> 报告类型：排查 / 验收报告
> 日期：2026-10-29
> 分支：`main`
> 合并提交：`60ca515`　修复提交：`28c2b66`
> 结论：**合并完成、验证通过、已推送 GitHub**

---

## 1. 背景

论坛模块（P3 全套 + 教师端 T1–T5 + 手机端改造）已在本地 `main` 完成并验证，准备推送到 GitHub 时被拒：

```
! [rejected]  main -> main (fetch first)
```

`git fetch` 后发现**双方分叉**：

| 方向 | 提交数 |
|---|---|
| 远端独有（`origin/main`） | **152** |
| 本地独有（`main`） | **92** |

远端多出的提交包括：复合题修复（`6a2a3c5`、`7505e13`）、D1 导入卡片类型修复（`4396c2b`）、多人协作 Git 方案（`c42b714`），以及**目录分层重构**（`solve_problems_files/` 迁往 `docs/`、删除大量 `.omo/*`）。

---

## 2. 冲突处置（8 个文件 / 11 个冲突块）

| # | 文件 | 冲突块 | 处置 | 依据 |
|---|---|---|---|---|
| 1 | `src/views/student/mobile/mobile_forum_detail.vue` | 1（310–315） | 取远端 | 远端修了 `formatTime(iso?: string \| null)` 类型问题，与我们的爱心收敛无关 |
| 2 | `docs/README.md` | 4 | 取远端 + **移出索引** + 写入 `.gitignore` | 用户决定：该文件不上传 GitHub |
| 3 | `solve_problems_files/README.md` | 0（modify/delete） | 接受远端删除 + **目录进 `.gitignore`** | 用户决定：不随仓库分发 |
| 4 | `src/views/student/shared/exercise.vue` | 1（305–310） | **保留双方** | 我们的 `sanitizeHtml` + `FeedbackDrawer` 与远端的 `renderQuestionContent` 需并存 |
| 5 | `src/router/index.ts` | 1（417–423） | 取远端 | 远端按 R12 让平板复用 `mobile_forum_detail.vue`；我们的爱心收敛正好在该页，**平板自动获得同一交互** |
| 6 | `backend/app/main.py` | 1（794–798） | 取远端 `media_assets_api.router` | 实测 `backend/app/api/v1/media/image_media.py` 已不存在，旧路由无实体 |
| 7 | `scripts/qbdm/qbdm.py` | 1（add/add，整文件） | 取远端 398 行版 | AGENTS.md §8 记录的命令面是 `role/gate/modules/module/design/status`，与远端版一致；本地版仅 `module/gate` |
| 8 | `backend/app/api/v1/community/forum.py` | 2（27–35、1415–1454） | **远端对象存储为主 + 我们的校验留在回滚分支**；import 取并集 | 远端引入 `settings.MEDIA_STORE_ENABLED` 对象存储分支并保留 `# 回滚分支` 旧路径，我们的 `ARCHIVE_MAGIC` 文件头校验属于旧路径，故置于其后 |

### 8.1 forum.py 的 import 并集

```python
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Request, HTTPException
from sqlalchemy.orm import Session, aliased          # aliased 供收藏统计
from sqlalchemy import func, or_, and_, String       # and_/String 供可见范围过滤
```

> 只取远端会丢掉 `aliased`/`and_`/`String`，导致 P3 的收藏统计与可见范围过滤器报错；只取本地会缺 `HTTPException`（对象存储不可用时返回 503）。

---

## 3. 合并中发现并修复的真问题

### 3.1 对象存储白名单缺附件格式（阻断级）

合并后论坛上传改走对象存储（`MEDIA_STORE_ENABLED` 默认 `True`），而 `backend/app/services/media_service.py` 的 `_FORUM_TYPES` 只允许 `doc/docx/pdf/xls/xlsx`：

```
FAILED tests/test_forum_upload.py::test_upload_rar_with_magic  - assert 422 == 200
FAILED tests/test_forum_upload.py::test_upload_7z_with_magic   - assert 422 == 200
```

**修复**：补齐 `ppt/pptx/txt/csv/zip/rar/7z` + `png/jpg/jpeg/gif/webp`（提交 `28c2b66`）。
**结果**：`pytest -k forum` 从 2 failed 变为 **78 passed**。

> 注意：该修复第一次提交时**漏了暂存**，推送后核对 `git status` 才发现，随即补提交并二次推送。教训：`git commit` 后必须 `git status` 复核。

---

## 4. 验收结果（合并后实测）

| 检查 | 命令 | 结果 |
|---|---|---|
| 应用可导入 | `python -c "import app.main"` | **OK** |
| 后端论坛测试 | `python -m pytest tests -q -k forum` | **78 passed**，871 deselected |
| 前端类型 | `npm run typecheck` | **0 错误 / 0 文件**（合并前为 63 条 / 9 文件，远端已修） |
| 前端单测 | `npx vitest run` | **33 files / 397 passed**（合并前 28 / 362） |

---

## 5. 推送记录

| 方向 | 提交范围 | 内容 |
|---|---|---|
| 第一次 | `c42b714..60ca515` | 合并提交（152 远端 + 92 本地） |
| 第二次 | `60ca515..28c2b66` | 对象存储白名单修复 |

推送后一致性：

```
git rev-list --left-right --count origin/main...main
→ 0    0        （本地与 GitHub 完全一致）
```

---

## 6. 遗留事项

| 项 | 说明 | 建议 |
|---|---|---|
| `docs/README.md` 索引 | 已从版本控制移除（用户决定），其中**未包含** v1.4/v1.5/v1.6 的索引行 | 若日后恢复跟踪，再补索引 |
| `solve_problems_files/` 46 个文件 | 目录已进 `.gitignore`，本地仍有实体，GitHub 不再分发 | 保留本地或迁入 `docs/` |
| 3 个 `.bak_20261026*` 备份 | 未跟踪（按规则不入库） | 可自行删除 |
| 教师端附件上传的端到端验证 | 合并前就未做真机上传 | 合并后走对象存储了，需**重新验证一次真实上传** |
| 平板详情页 | 路由改为复用 `mobile_forum_detail.vue`，`tablet_forum_detail.vue` 仍在磁盘但不再被路由引用 | 确认是否保留文件 |

---

## 7. 复现与回滚

```powershell
# 复现本次合并（若需重做）
git checkout main
git merge origin/main
# 按 §2 表格逐文件处置
# 跑 §4 四项验证
git commit
git push origin main
```

回滚到合并前（会丢远端 152 个提交，勿在共享环境随意执行）：

```powershell
git reset --hard fe11b3a
git push --force-with-lease origin main
```

> 当前 `main` 已与远端同步，**再次合并无需重做**。
