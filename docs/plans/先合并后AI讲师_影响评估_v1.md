# 先合并其他任务、再做 AI 讲师，会不会有不良影响 —— 评估报告 v1

> 状态：**评估报告，不含任何合并动作**（`main` 未动，全部为只读实测）
> 日期：2026-11-02　分支：`feat/Study-Material-Management-r4` @ `267da9f`
> 测量口径：本机实测，命令与输出见 §10；远端分支为本地 `origin/*` 快照（未 `git fetch`）

---

## 0. 一句话结论

**「先合并、再做 AI 讲师」本身不会产生不良影响**——合并是快进（fast-forward），不产生 merge commit、不重放提交、不改任何文件内容，且 AI 讲师分支位已经站在 r4 HEAD 上，合并前后都是同一棵树。**真正会伤到 AI 讲师的是另一件事**：远端还躺着 4 个从未进 main 的分支，其中 2 个正是 AI 讲师的现成零件（LLM 客户端、`/api/llm/*` 五个端点、会话模型、AI 对话页），若不先定它们的处置就开工，必然重复造轮子或做出版本分叉。

| 问题 | 结论 | 证据 |
|---|---|---|
| 合并动作本身会不会破坏 AI 讲师的地基？ | ❌ 不会 | 合并后 main 与 AI 分支 tip 指向同一 commit，三棵树（main / 父分支 / AI 分支）完全一致 |
| 合并顺序对 AI 讲师开发有没有影响？ | ✅ 先合并更有利 | 现在的 main 落后 r4 144 个提交；AI 讲师要用的「成就金币/徽章联动」等依赖只在 r4 里 |
| 有没有别的未合并东西会和 AI 讲师撞车？ | ⚠️ **有，且很关键** | `origin/feature/ai-assistant`、`origin/feature/study-plan` 各带一份 `llm_client.py`（171 行，同一 blob）与 `/api/llm/*` |
| 会不会有文本冲突？ | 5 个已知协调点 | 路由计数双改点、R11 端点白名单、迁移编号、`docs/README.md` 索引、`.vtj` 页 |

---

## 1. 问题拆解

你的原话是「把其他任务合并后再做 AI 讲师，会产生不良影响吗」。这句话实际含三个可分别验证的子问题：

- **Q1（合并动作）**：`r4 → 父分支 → main` 之后，AI 讲师分支还在不在、树还是不是原来那棵？
- **Q2（顺序）**：先合并再开工，与先开工再合并，对 AI 讲师的开发/验收/门禁有什么差别？
- **Q3（外部变量）**：除了 r4，还有什么没合进 main 的东西会在 AI 讲师开工时变成路上的坑？

---

## 2. 实测基线

| 对象 | 实测值 | 说明 |
|---|---|---|
| `main` | `da218d1`（2026-10-26） | 与 `origin/main` 一致，落后远端 0 |
| `feat/Study-Material-Management-r4` | `267da9f`（2026-11-02） | 当前检出分支 |
| 领先 main | **144 提交 / 385 文件 / +31,306 −10,085** | `git rev-list --count main..HEAD` |
| 落后 main | **0** | `main` 是 r4 的祖先 → 可 `--ff-only` |
| `feat/Study-Material-Management`（父） | `ce19649` | 落后 r4 1 个 doc 提交 |
| `feat/…-ai-lecturer` | `267da9f` | **已指向 r4 HEAD**，空位、零代码 |
| 工作树 | clean（`git status --porcelain` = 0 行） | 合并前无需 stash |
| 远端分支 | 29 个（另有 `origin/HEAD` 指针）；25 个已被 main 完整包含，**4 个没有** | 见 §5 |

---

## 3. Q1：合并动作本身不会伤到 AI 讲师

四条机制性理由，都是可复核的结构事实，不是判断：

1. **同一 commit**：AI 讲师分支在上一轮已由 `da218d1` 前移到 `267da9f`。合并完成后 `main` 也等于 `267da9f`，两者指向同一个对象——不存在「谁比谁旧」。
2. **纯快进**：`behind=0` 且 `main` 是祖先，`git merge --ff-only` 只移动分支指针，不新建提交、不重放、不三方合并，**文件内容零变化**。
3. **没有并行推进**：本地没有任何分支在 r4 之后继续提交（27 个模块分支全部被 r4 包含，未被包含的 = 0），所以不存在「合并时把别人的新提交带上/漏下」。
4. **不碰 `.vtj`**：这一轮合并的 385 个文件里 `.vtj/vue/*.vue` 有改动（平板页），但 AI 讲师后续要新建的页面走设计器 + `script` 分支，与这轮改动不重叠；R1/R3 均不受影响。

> 反过来说：**如果合并用 `--squash` 或 `--no-ff`，结论就会变差**。`--squash` 会让 main 产生一棵内容相同但**没有共同提交**的树，AI 分支回到 main 时会把 144 个提交重放一遍；`--no-ff` 会多一个 merge commit，AI 分支必须再 `merge main` 一次才能保持线性。**只推荐 `--ff-only`**。

---

## 4. Q2：先合并对 AI 讲师更有利

| 维度 | 先合并（推荐） | 先做 AI 讲师，后合并 |
|---|---|---|
| 起点代码 | main 含 144 个提交（含成就金币/徽章、三端统一、资料模块全量） | 若从 `da218d1` 切出，缺整模块；AI 讲师的「金币/徽章联动」无从对接 |
| 门禁基线 | 合后在 main 上跑一次 `gate_all`（10 层）即为「已知绿」 | 红灯要在 144 个未合并提交的噪声里排查，且每次 rebase 重跑 |
| 冲突面 | 0（无并行分支） | `src/router/index.ts`（路由表尾部 + 计数常量）、`docs/README.md` 必冲突 |
| 返回 main 的成本 | `--ff-only` 一行 | 需 merge/rebase，手工解 3-way 冲突 |
| 需求④ 的排期 | 合并完即开工，无阻塞 | 合并窗口与开发窗口重叠，两边都在改同一批文件 |

结论：**先合并**不仅在风险上是 0，在效率上是净收益。

---

## 5. Q3：关键发现——4 个未合并远端分支，2 个是 AI 讲师的零件

`origin/*` 快照里 29 个远端分支只有 4 个带 main 之外的提交（其余 25 个已被 main 完整包含）：

| 分支 | 领先 | 文件 | 与 AI 讲师的关系 | 处置建议 |
|---|---|---|---|---|
| `origin/feature/ai-assistant` | +2（2026-10-25） | 12 个：`backend/app/services/llm_client.py`(171 行)、`backend/app/api/v1/platform/llm.py`（**5 个 `/api/llm/*` 端点**）、`models.py`（`ChatSession`/`ChatMessage`）、`core/config.py`、`.env.example`、`.vtj/vue/ai_chat.vue`、`src/router/index.ts`、`src/modules/ai-assistant/*`（把占位外壳换成实现，+229/−79） | **直接相关**：这就是「联考小智」（模块⑱）的对话地基 | **取零件，不取历史**（见 §7 方案 A） |
| `origin/feature/study-plan` | +3（2026-10-25/27） | 8 个：同一份 `llm_client.py`（blob 完全相同 `3d9eef9`）、`growth/study_plan.py`、`.vtj/vue/study_plan.vue`、`question_bank.vue`、`models.py`、`config.py`、`main.py`、`router` | 相关（同一个 LLM 客户端） | 先取 `llm_client.py`，学习计划本身另案 |
| `origin/fix/D1-import-card-type` | +1（2026-10-27） | `library/materials.py`（5 行）、`tests/test_material_import_card_type.py`、`docs/README.md`、1 份报告 | **已冗余**：同一段注释与 `type="card"` 修复**已在 r4**（`materials.py:1955-1957`、`:1974`），r4 里同名测试文件内容不同（blob `254fa9d` vs 分支 `432f223`） | **丢弃**，不要合并（会造无意义冲突） |
| `origin/feat/teacher-optimization` | +1（2026-09-01 老分支） | 改 `backend/app/api/v1/teacher.py`（**该路径在 HEAD 已不存在**，现为 `platform/teacher.py`）、`question_import.py`、`text_parser.py` | 无关 | **不要直接合并**：modify/delete 冲突，解错会复活旧教师 API 形成双份路由 |

### 5.1 为什么「先合并」反而让这 4 个分支更好处理

- 合并后 main 的「最新日期 / 最新路由表 / 最新模型清单」就定下来了，取零件时不会取到两套版本。
- 这 4 个分支现在落后 main **127** 个提交；合并完成后会落后 **271**。**但取零件（`git checkout <branch> -- <file>`）与落后多少无关**——取的是文件内容，不是历史。反之若试图「整支合并」，落后越多冲突越重。

### 5.2 现状缺口（HEAD 实测）

| 检查项 | 结果 |
|---|---|
| `backend/app/services/llm_client.py` | ❌ 不存在（main 与 r4 都没有） |
| `backend/app/api/v1/platform/llm.py` | ❌ 不存在 |
| `models.py` 中 `ChatSession` / `ChatMessage` | ❌ 不存在 |
| `.vtj/vue/ai_chat.vue` | ❌ 不存在 |
| `src/router/index.ts` 里 `ai_chat` / `llm` 路由 | ❌ 无 |
| `src/modules/ai-assistant/*` | ⚠️ 只有**占位外壳**（`36b402b` 生成，`api.ts` 注释明写「占位，P2 阶段按真实端点收窄」） |

即：**AI 讲师现在等于「零后端 LLM 能力 + 占位前端模块」**，而远端两个分支里已经有一份可用的 LLM 客户端与 5 个会话端点。

---

## 6. 无论什么顺序都必须改的 5 个协调点

| # | 位置 | 现状值 | AI 讲师要做的事 | 风险 |
|---|---|---|---|---|
| 1 | `scripts/verify-modularization-constraints.mjs` 的 `EXPECTED_DYNAMIC_IMPORTS` + `backend/tests/test_route_roles.py` 的 `== 98` | **两处都是 98** | 每新增 1 个 VTJ 页面，两处同步 +N | 只改一处 → L6 或 L7 红，且数字错在合并时最易发生 |
| 2 | `backend/tests/test_api_surface.py` 的 `KNOWN_EXTRA_OPERATIONS` | 白名单 **36 条**；基线 `api_surface.json` **343 端点 / 37 模块**冻结 | 新端点逐条登记（R11） | 不登记 → A8 门禁红；改基线 → 违反 R11 |
| 3 | `backend/migrations/YYYYMMDD_NNN_*.sql` | L7 检查：同日期组序号**连续**、foundation DDL sha256 不变 | 新表迁移取**当天新日期** | 复用 `20261027` 组或跳号 → L7 红 |
| 4 | `docs/README.md` 索引 + 变更日志 | 641 行，索引表 + 按日期日志 | 新报告追加一行 | 唯一的高频文本冲突文件 |
| 5 | `.vtj/vue/*.vue` 新建页 | CI `vtj-version-check.yml` 仅在 `.vtj/**` 变更时触发（push/PR） | 新页由设计器产出 | AI 若提交 `.vtj` 变更会触发一次版本一致性检查 |

---

## 7. 推荐执行顺序（待你批准）

```text
0) 备份：git branch backup/main-pre-r4 main ；git tag pre-r4-merge main
1) git switch feat/Study-Material-Management && git merge --ff-only r4
2) git switch main && git merge --ff-only feat/Study-Material-Management
3) main 上跑基线：gate_all（10 层）+ vitest + vue-tsc + 3 个 CDP 验收
4) git switch feat/…-ai-lecturer && git merge --ff-only main   # tip 对齐 main
5) 取零件（方案 A）：git checkout origin/feature/ai-assistant -- \
     backend/app/services/llm_client.py backend/app/api/v1/platform/llm.py
   （模型/配置/env.example 按差异手工摘，不整文件覆盖）
6) 再开 AI 讲师：先出方案（讲什么、怎么讲、视频从哪里来），你批了再写码
7) 每次 main 前进 → git merge main 回 AI 分支；推送 main 前需你二次确认
```

**三种处置选项对比**（针对 `feature/ai-assistant`）：

| 方案 | 做法 | 代价 | 风险 |
|---|---|---|---|
| **A（推荐）** | 合并后从该分支 `checkout` 两个文件（`llm_client.py`、`platform/llm.py`），模型/配置按需摘 | 约 1 小时阅读+适配 | 需补 `ChatSession/ChatMessage` 模型与 `config`，否则端点起不来 |
| B | 从零自己写 LLM 客户端 | 少说 1 天，且要重新踩超时/流式/重试 | 与两分支形成第三份实现 |
| C | 整支合并进 main | 需先 `merge main`，冲突集中在 `router/index.ts`、`models.py`、`config.py`；且会把未验收的「联考小智」直接塞进 main | 需求④是「AI 讲师/AI 视频」，与对话助手不是同一形态，合进来会打乱验收口径 |

> 注意：方案 A 取进来的 `/api/llm/chat` 是**纯对话**接口。若需求④要做的是「讲师讲解」（按科目/章节生成讲稿、配音、视频），`llm_client.py` 可直接复用，**`llm.py` 的会话端点是否沿用要等你定功能形态**——这属于设计决策，不在此报告内。

---

## 8. 风险与回退

| 风险 | 触发条件 | 处理 |
|---|---|---|
| 合并后门禁红 | main 上跑出 FAIL（当前 r4 是 10/10，理论上不会） | `git reset --hard pre-r4-merge` 回退，再定位 |
| 误用 `--squash` / `--no-ff` | 手工执行时加错参数 | 立即 `reset --hard`，改回 `--ff-only` |
| 取零件把整支副作用带进来 | 用了 `git merge` 而非 `git checkout -- <file>` | 只允许按文件取；取完 `git diff --stat` 复核 |
| 误合 D1 / teacher-optimization | 批量合并历史分支 | 这两支**禁止合并**（§5） |
| 推送后 CI 报 VTJ 版本不一致 | 提交了 `.vtj/**` 但版本未同步 | 本地先 `npm run` 对应检查；或先不推 main |

---

## 9. 已知不足

1. **远端快照可能过期**：没做 `git fetch`，4 个分支的领先数以本地 `origin/*` 为准；若远端有新提交，数字会变。
2. **无法判定 4 个分支是否已被用户放弃**：日期（2026-09-01 / 10-25 / 10-27）与内容看像是历史尝试，但需要你确认后才好删。
3. **AI 讲师的功能形态未定**：页面数、端点数未知，§6 表里「+N」无法预估；`/api/llm/*` 是否能直接支撑「讲师」形态需方案定稿后判断。
4. **视频生成路径未评估**：若引入外部服务/异步任务，会新增 env 与后台任务，与本次合并无关但影响部署，另行评估。
5. **未验证 r4 的 144 个提交里是否有与 LLM 相关的半成品**：只验证了 `llm_client.py`/`llm.py`/`ai_chat.vue`/`ChatSession` 四项不存在；`grep -ri "deepseek\|llm"` 的广谱扫描未做。

---

## 10. 测量命令（可复核）

```powershell
cd li_an-question_bank
git log --oneline -1 main                                   # da218d1
git rev-list --count main..HEAD                             # 144
git rev-list --count HEAD..main                             # 0
git merge-base --is-ancestor main HEAD                      # exit 0 → 可 FF
git diff --shortstat main HEAD                              # 385 files, +31306 -10085
git branch -r | % { $_.Trim() } | ? { $_ -notmatch 'HEAD' } |
  % { "$_ ahead=" + (git rev-list --count "main..$_") }
git log --oneline main..origin/feature/ai-assistant          # 2 commits
git rev-parse origin/feature/ai-assistant:backend/app/services/llm_client.py
git rev-parse origin/feature/study-plan:backend/app/services/llm_client.py   # 同一 blob
git diff main...origin/fix/D1-import-card-type -- backend/app/api/v1/library/materials.py
Select-String backend/app/api/v1/library/materials.py -Pattern 'type="card"|业务事实'   # 1955-1957 / 1974
Select-String backend/app/models/models.py -Pattern 'class Chat(Session|Message)'       # 无
git ls-tree -r --name-only HEAD -- src/modules/ai-assistant                              # 占位 4 文件
python -c "import json;from pathlib import Path;b=json.loads(Path('backend/data/refactor_baseline/api_surface.json').read_text(encoding='utf-8'));print(len(b),sum(len(v['endpoints']) for v in b.values()))"   # 37 343
```
