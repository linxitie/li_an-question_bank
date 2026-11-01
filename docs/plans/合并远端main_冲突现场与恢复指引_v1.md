# 合并远端 main 的冲突现场与恢复指引 — v1

> 状态：**仓库当前停在 MERGING（未完成合并）**，2026-10-29 留下现场。
> 目的：让任何人在任何时间接手，都能准确知道"停在哪、怎么继续、怎么回滚"。

---

## 1. 现场快照

| 项 | 值 |
|---|---|
| 当前分支 | `main` |
| 合并前本地 main | `fe11b3a`（含论坛全部工作，670 个提交） |
| 正在合并的对象 | `origin/main`（比本地多 **152** 个提交） |
| 本地有、远端没有 | **92** 个提交 |
| Git 状态 | **MERGING**（`git merge origin/main` 执行到一半） |
| 冲突 | **8 个文件 / 11 个冲突块** |

---

## 2. 冲突清单（含冲突块数量）

| 文件 | 冲突块 | 风险 | 备注 |
|---|---|---|---|
| `backend/app/api/v1/community/forum.py` | **2** | 🔴 高 | 我们的 P3 功能（收藏/可见范围/搜索） vs 远端改动，需语义合并 |
| `backend/app/main.py` | 1 | 🟡 中 | 自动迁移列表（我们加了 visibility/visible_classes 两列） |
| `docs/README.md` | 4 | 🟢 低 | 两边都加了索引行，合并保留双方 |
| `scripts/qbdm/qbdm.py` | 1 | 🟡 中 | **add/add**：两边都新增了此文件 |
| `src/router/index.ts` | 1 | 🔴 高 | 我们的设备守卫（`device === 'mobile'`） vs 远端改动 |
| `src/views/student/mobile/mobile_forum_detail.vue` | 1 | 🟡 中 | 我们的"6 反应收敛为单爱心" |
| `src/views/student/shared/exercise.vue` | 1 | 🟡 中 | 需查明谁改的 |
| `solve_problems_files/README.md` | 0 | 🟢 低 | 远端**删除**（已迁到 `docs/`），本地修改过 → 应接受删除 |

---

## 3. 还有一件未完成的事：stash

合并前为了不被中止，3 个常驻脏文件被暂存：

```
stash 名：dsh_premerge_20261029
内容：
  .vtj/materials/linxitie.policy-exam-bank.json
  .vtj/projects/linxitie.policy-exam-bank.json
  package-lock.json
```

> 这三个文件按红线**不入 Git**，但改动还躺在 stash 里。
> **合并完成或回滚之后**，需执行 `git stash pop` 恢复。

---

## 4. 远端这次带来了什么（重要背景）

远端 152 个提交包含：

- `fix(composite): 复合题材料完整展示与答题页滚动联动`
- `fix(composite): 补齐图片渲染、做题背题、三端吸顶与组卷重考`
- `merge: D1 导入卡片类型修复（分支 fix/D1-import-card-type）`
- `docs(collab): 多人协作 Git 网络稳定方案与诊断脚本`
- **目录分层重构**：`solve_problems_files/` 迁往 `docs/`，大量 `.omo/*` 文件被删除

⚠️ 这解释了为什么冲突不多但**语义风险高**：不是纯补丁，而是结构迁移。

---

## 5. 三条路（任选其一）

### 路线 C：推分支（风险最低，推荐先用）

```powershell
git merge --abort                        # 回到 fe11b3a
git stash pop                            # 恢复 3 个文件
git push origin main:feat/forum-p3-full  # 把 92 个提交推成新分支
```

**结果**：论坛工作立刻上 GitHub；远端 `main` 不受影响；之后可开 PR 慢慢合。

### 路线 A：继续解冲突（完整合并）

```powershell
# 按顺序解，每解一个就跑验证：
# 1) forum.py（2 块）
cd backend; python -m pytest -k forum -q
# 2) main.py / router/index.ts / mobile_forum_detail.vue / exercise.vue
cd ..; npm run typecheck
npx vitest run
# 3) 文档类：docs/README.md、scripts/qbdm/qbdm.py、solve_problems_files/README.md(接受删除)
git add -A
git commit                                # 完成合并提交
git stash pop
git push origin main
```

### 路线 B：先回滚，明天再说

```powershell
git merge --abort
git stash pop
```

**无损**：明天重新 `git merge origin/main` 会得到**完全一样**的 11 个冲突。

---

## 6. 开工前必读

```powershell
cd D:\AAA项目文件\砺安题库\li_an-question_bank
git status                # 应显示 "You have unmerged paths"
git diff --name-only --diff-filter=U    # 列出 8 个冲突文件
git stash list            # 应看到 dsh_premerge_20261029
```

冲突文件里搜 `<<<<<<<` 即可定位每一块。

---

## 7. 已验证的事实（合并前）

三道闸在 `fe11b3a` 上全绿（**之后未再跑过**）：

```
vitest      28 files / 362 tests passed
typecheck   63 条 / 9 文件（基线）
pytest -k forum  69 passed
```

> 合并完成后**必须重跑**，因为 `forum.py` / `main.py` / `router` 都变了。

---

## 8. 一句话总结

**代码没丢、远端没被改、本地只是停在合并中途。**
最省事的收尾是路线 C（推分支）；最彻底的是路线 A（解 11 个冲突块后推 main）。
