# VTJ 版本一致性检查修复报告 v1

> 状态：**已修复并验收**（2026-11-02，分支 `fix/vtj-version-consistency`）
> 触发：推 `origin/main` 前按你的要求先修「VTJ 版本一致性」

---

## 1. 修复前实测（`python scripts/vtj_version_sync.py`）

```
✅ 版本一致: ×69（about、admin_*、home_page、tablet_* …）
⚠️  JSON 文件不存在: .vtj/files/smart_recommend.json
⚠️  JSON 文件不存在: .vtj/files/TeacherNavHeader.json
⚠️  无法从 Vue 提取版本: .vtj/vue/teacher_analytics.vue
⚠️  无法从 Vue 提取版本: .vtj/vue/teacher_classes.vue
⚠️  无法从 Vue 提取版本: .vtj/vue/teacher_messages.vue
⚠️  无法从 Vue 提取版本: .vtj/vue/teacher_profile.vue
❌ 部分文件版本同步失败        → exit 1
```

**CI 后果**：`.github/workflows/vtj-version-check.yml` 直接跑这个脚本且 `continue-on-error: false`，所以每次 push 到 `.vtj/**` 都会红。上一轮合并涉及的 147 个提交里刚好有 **6 个 `.vtj/**` 文件**变更，一推必红。

---

## 2. 根因：把「非设计器页面」当成了「版本漂移」

`.vtj/vue/` 下其实有两类文件，脚本原先对它们一视同仁：

| 类别 | 特征 | 例子 | 应有行为 |
|---|---|---|---|
| **设计器页面** | `<script>` 里有 `useProvider({ id, version })`，且 `.vtj/files/<同名>.json` 有 `__VERSION__` | `home_page.vue:199` → `useProvider({ id: 'home_page', version: '1785750000100' })` + `home_page.json` 的 `__VERSION__` | 两边必须相等，不等就同步/报错 |
| **非设计器页面** | 手写 `<template>`、无 `useProvider`；或只有一边（有 vue 无 json / 有 json 无 vue） | 4 个 `teacher_*` 手写页（`useProvider` 命中数 **0**）、`TeacherNavHeader.vue`（无 JSON）、`smart_recommend.vue`（有 provider 但无 JSON） | **没有「设计器版本」可对齐，跳过并计数** |

实测证据：

```text
Select-String .vtj/vue/home_page.vue       -Pattern useProvider → 命中（设计器页）
Select-String .vtj/vue/teacher_analytics.vue -Pattern useProvider → 0 命中（手写页）
```

4 个 `teacher_*` 页的 `.vtj/files/*.json`（`__VTJ_BLOCK__: true`）是历史残留，它们从来不是设计器产物 → 拿它们去对齐版本本身就是伪命题。

**另一个更隐蔽的问题**：CI 调的是**同步**模式。也就是说，即使真有漂移，CI 会在自己的 checkout 里把 JSON 改掉再判通过——**这个检查从来没真正拦住过任何东西**。

---

## 3. 修复内容

### 3.1 `scripts/vtj_version_sync.py`（重写主流程）

| 改动 | 说明 |
|---|---|
| 新增分类函数 `classify()` | 返回 `ok` / `skip-no-json` / `skip-no-provider`，把「非设计器页面」与「真的漂移」分开 |
| 默认（同步）模式 | 只同步真正漂移的设计器页面；非设计器页面打印 `⏭ 跳过` 并计数，**不判失败** |
| 新增 `--check` | 只读比对、不写文件；不一致 `exit 1` 并打印 `页名: Vue=x, JSON=y`（CI 用） |
| 新增 `--strict` | 非设计器页面也算失败，供人工排查（保留旧语义的严格版） |
| 汇总输出 | `📊 设计器页面 69 个一致、0 个已同步、0 个失败；非设计器页面跳过 6 个`，`--check/--strict` 附带跳过明细 |
| 单文件模式 | `python scripts/vtj_version_sync.py home_page.vue` 行为保留 |

### 3.2 `.github/workflows/vtj-version-check.yml`

```diff
-          python scripts/vtj_version_sync.py
+          python scripts/vtj_version_sync.py --check
```

CI 从「自动改 + 判通过」变成**真正的守门**：有漂移就红，必须本地跑同步后重新提交。

### 3.3 文档

`docs/ops/备考资料_本地开发与门禁手册_v1.md` 新增 **§2.1 VTJ 版本一致性**：三种用法、分类口径表（哪 6 个跳过、为什么）、当前基线（69 + 6）。

---

## 4. 验收（全部实测）

| 场景 | 命令 | 结果 |
|---|---|---|
| 当前基线 | `python scripts/vtj_version_sync.py` | `📊 69 一致、0 同步、0 失败；跳过 6`；**exit 0** |
| 检查模式 | `python scripts/vtj_version_sync.py --check` | 同上 + 跳过明细；**exit 0** |
| 严格模式 | `python scripts/vtj_version_sync.py --strict` | `❌ --strict：存在非设计器页面，需人工确认`；**exit 1**（旧语义仍可用） |
| **真的漂移能被抓住** | 把 `home_page.json` 的 `__VERSION__` 改成 `1` 后 `--check` | `❌ 版本不一致: home_page（Vue=1785750000100 JSON=1）`；**exit 1** |
| 同步模式能修 | 同上场景跑默认模式 | `🔄 版本不一致: home_page` → `✅ 已同步` → 再 `--check` exit 0 |
| 还原 | `git checkout -- .vtj/files/home_page.json` | 回到原格式，`--check` exit 0；工作区只剩脚本本身变更 |

> 漂移实验是「改 → 验证 → git 还原」，**没有把实验改动提交**；`.vtj/vue` 一个字节没动（守 R1/R3）。

---

## 5. 边界与已知不足

1. **不是把检查改松**：设计器页面之间一旦真不一致，`--check` 仍 exit 1（已实测）；放宽的只有「根本不是设计器页面」的 6 个文件。
2. **`smart_recommend` 值得以后处理**：它有 `useProvider` 却没有 JSON，说明可能是个没导完的设计器页面；补 JSON 需要设计器导出，**本次未动**。
3. **4 个 `teacher_*` 的残留 JSON** 仍留在 `.vtj/files/`：按 R1 不擅自删 `.vtj/`，留着不影响任何检查（脚本已跳过）。要不要清理由你定。
4. CI 其余 4 个作业（black/isort/flake8、prettier/eslint、pytest tests/unit、alembic migration）**未验证**，推送后可能仍有红项——属既有状态，与本次修复无关。
