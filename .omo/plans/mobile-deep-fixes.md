# 手机端深度优化（前端验证后七项问题修复）

## TL;DR

> **快速摘要**：用户在前端实际验证后发现 7 项问题，涵盖练习页布局、混合练习层级、题库功能重复、今日目标弹窗过简、智能组卷页布局、答题卡页功能缺失。经代码核查，7 项全部定位到具体根因，其中答题卡页「选项与图片被吞没」已定位为 `answer_page.vue` 中两处**未接渲染真源的裸 `v-html`**，申论科目缺失定位为**数据层问题**而非前端。
>
> **交付物**：
> - `mobile_practice.vue`：混合练习层级重构 + 底栏遮挡修复 + 资源入口去重
> - `mobile_home.vue`：今日目标弹窗升级为电脑端 4 字段设计
> - `answer_page.vue`：答题卡页 5 项改造（渲染/进度条/答题卡入口/记背模式/答案延后显示）
> - `smart_exam.vue`：智能组卷页返回按钮、图标尺寸、预览修复
> - `mobile_question_bank.vue`：移除「快速练习」入口
> - 申论科目数据核查报告
>
> **预计工作量**：大
> **并行执行**：是 — 6 个任务分 1 波（按文件隔离，无冲突）
> **关键路径**：T4（答题卡改造，影响面最广）→ F1-F4

---

## Context

### 用户原始反馈

用户在前端实际验证后提出 7 项问题：

1. 今日目标弹窗过于单一（仅能编辑当日做题数量），需参考电脑端「个人小目标」模块设计
2. 「练习」模块缺失「申论」科目，及其知识点与下钻考点
3. 混合练习层级错误：应在第一层（知识点分类）顶部设**一个**「本科目混合练习」按钮；进入具体知识点后再在顶部设**一个**「混合练习」按钮。**不应**每个知识点/考点各设一个
4. 「练习」页因底层有导航栏，「更多练题资源」被导航栏遮挡，需重新布局
5. 「更多练题资源」与「题库练习」重复（历年试卷/智能组卷/错题本）。删除前者中的这三项，仅保留「题库练习」中的；并删除「题库练习」中的「快速练习」（与三大科目分类冲突）
6. 智能组卷页布局不合理：缺返回按钮、图标变形过大、「智能生成」不能预览试卷
7. 答题卡页：选项内容与图片被吞没；右上角需加答题卡入口；顶层需做题进度条与「记背模式」切换；做题模式下需答完全部题目才显示答案与解析

**全局要求**：全局使用中文说明（代码注释与界面文案）。

### 代码核查结论（本计划的事实依据）

| 需求 | 根因定位 | 证据 |
|---|---|---|
| 1 | 手机端弹窗仅 `dailyGoal` 单字段；电脑端为 4 字段 | `mobile_home.vue` `openGoalEdit` vs `personal_goal.vue:94-113` |
| 2 | **非前端问题**。前端 `subjectMeta[2]=申论` 已存在 | `mobile_practice.vue:208`；科目来自 `GET /api/quick-practice/subjects` → `QuestionSubject WHERE status==1` |
| 3 | 存在 3 个混合练习按钮：科目层（正确）+ 子科目层 + 考点层（均需删） | `mobile_practice.vue:44, 72, 107` |
| 4 | `.scroll-area` 无底部内边距，末段被 60px 固定底栏覆盖 | `mobile_practice.vue:625-631` |
| 5 | `moreResources` 含 5 项，其中 3 项与题库页重复 | `mobile_practice.vue:421-427` |
| 6 | 已有返回按钮，但 L124/L142 「重新生成」误用 `.back-btn` 类；图标无尺寸约束 | `smart_exam.vue:75, 124, 142` |
| 7a | **题干 L111、选项 L135 均为裸 `v-html`，未接 `renderQuestionContent`** | `answer_page.vue:111, 135` |
| 7b | 答题卡按钮在 `toolbar-left`（用户要求右上角）；进度仅文字无进度条 | `answer_page.vue:8, 13-21` |
| 7c | 无记背模式；答案与解析无条件显示 | `answer_page.vue` 全文 |

**需求 7a 的关键澄清**：`answer_page.vue:481-485` 的 `loadQuestions` 分支**已**对 stem 和 options 调用 `renderQuestionContent`。因此选项空白只可能出现在**其它加载分支**（quick-practice / smart-exam 传参路径），实施时必须逐条核查所有出题入口，不能只改模板。

### 重要前置事实

- 单一渲染真源：`src/utils/questionRender.js`，导出 `renderQuestionContent` / `renderQuestionSummary` / `sanitizeHtml`
- 回归测试：`node C:\Users\21499\AppData\Local\Temp\opencode\test-question-render.mjs`，当前 **10 passed, 0 failed**
- `SysUser` **无** `address` 列（`address` 属 `School` 模型），与本计划无关但仍待用户决策
- `npm run typecheck:guarded` 因 `.vtj/vue/teacher_papers.vue`（他人未提交改动）行号漂移失败，**禁止**用 `--update` 掩盖
- `npx cross-env ENV_TYPE=live npx vite build` 当前 **构建通过**（17.16s）

---

## Work Objectives

### 核心目标
修复用户实测发现的 7 项前端问题，使练习、答题、智能组卷三大流程的布局、层级与功能完整性达到预期。

### 具体交付物
- `.vtj/vue/mobile_practice.vue` — 混合练习层级重构、底栏遮挡修复、资源去重
- `.vtj/vue/mobile_home.vue` — 今日目标弹窗 4 字段
- `.vtj/vue/answer_page.vue` — 答题卡页 5 项改造
- `.vtj/vue/smart_exam.vue` — 智能组卷页修复
- `.vtj/vue/mobile_question_bank.vue` — 移除快速练习
- 申论数据核查报告

### 完成定义
- [ ] 7 项需求全部落地
- [ ] 渲染回归测试仍 10/10
- [ ] `vite build` 退出码 0
- [ ] 所有改动文件 `lsp_diagnostics` 0 error
- [ ] VTJ `.vue` 与 `.json` 的 `__VERSION__` 一致、新增方法已声明
- [ ] 全部注释与界面文案为中文

### 必须具备
- 所有题目内容渲染走 `renderQuestionContent` 单一真源
- 练习页滚动内容不被底栏遮挡
- 功能入口不重复、不丢失

### 必须禁止（护栏）
- 不得复制题目渲染逻辑到第二个实现
- 不得修改 `src/utils/questionRender.js` 的清洗语义
- 不得改动 `.vtj/vue/teacher_papers.vue`（他人未提交改动）
- 不得执行 `verify-typecheck-baseline.mjs --update`
- 不得删除「历年试卷/智能组卷/错题本」的**唯一**可达入口
- 不得新增第三方依赖
- 不得擅自新增 DB 迁移

---

## Verification Strategy

> **零人工介入** — 全部验证由 agent 执行。

### 测试决策
- **基础设施存在**：是（`test-question-render.mjs`，10 用例）
- **自动化测试**：已有回归测试，改造后必须重跑
- **框架**：Node 原生断言

### QA 策略
每个任务必须包含 agent 可执行的 QA 场景，证据存于 `.omo/evidence/`。
- **UI 页面**：Playwright 打开页面、断言 DOM、截图
- **渲染安全**：回归测试 + grep 裸 `v-html`
- **构建**：`vite build` 退出码

---

## Execution Strategy

### 并行执行波次

```
Wave 1（立即启动 — 按文件隔离，互不冲突）：
├── 任务 1: mobile_practice.vue    需求 3+4+5  [visual-engineering]
├── 任务 2: mobile_home.vue        需求 1      [visual-engineering]
├── 任务 3: answer_page.vue        需求 7      [deep]
├── 任务 4: smart_exam.vue         需求 6      [visual-engineering]
├── 任务 5: mobile_question_bank   需求 5b     [quick]
└── 任务 6: 申论数据核查            需求 2      [unspecified-high]

Wave FINAL（全部任务完成后 — 4 路并行评审）：
├── F1: 需求符合性审计   [oracle]
├── F2: 代码质量评审     [unspecified-high]
├── F3: 真机 Playwright QA [unspecified-high]
└── F4: 范围忠实度检查   [deep]
→ 汇总结果 → 交用户确认
```

### 依赖矩阵

| 任务 | 依赖 | 阻塞 |
|---|---|---|
| 1 | 无 | F1-F4 |
| 2 | 无 | F1-F4 |
| 3 | 无（需任务 1 完成后回归测试仍通过） | F1-F4 |
| 4 | 无 | F1-F4 |
| 5 | 无 | F1-F4 |
| 6 | 无（需 DB 访问权限） | F1-F4 |

### Agent 派发摘要
- **Wave 1**：6 个任务全部并发
- **FINAL**：4 个评审并发

---

## TODOs

> 格式：任务标签用裸数字 `1.` `2.`，最终波次用 `F1.` `F2.`
> 每个任务必须含：实现内容、禁止事项、Agent 画像、并行信息、参考资料、验收标准、QA 场景。

- [ ] 1. 练习页：混合练习层级重构 + 底栏遮挡修复 + 资源入口去重（需求 3、4、5）

  **实现内容**：
  - **需求 3 — 混合练习层级**：删除子科目层按钮（`.vtj/vue/mobile_practice.vue:72-75`）与考点层按钮（`:107-110`）；保留科目层「本科目混合练习」（`:44-48`）；新增一个「本知识点分类混合练习」按钮，置于**子科目列表顶部**（`viewState === 'subModules'` 分支内、`v-for` 之前），点击后对该子科目下**全部知识点**出题
  - **需求 4 — 底栏遮挡**：为 `.scroll-area`（`:625-631`）增加底部内边距，值 = 底栏高度 60px + `env(safe-area-inset-bottom)`，确保「更多练题资源」完整可见
  - **需求 5 — 资源去重**：`moreResources`（`:421-427`）删除「历年试卷」「智能组卷」「错题本」三项，仅保留「题库总览」与「备考资料」
  - **配套删除**：`mixedPracticeSubCategory` / `mixedPracticeKp` 两个函数若已无调用点则一并删除，避免死代码

  **禁止事项**：
  - 不得改动 `mixedPracticeSubject`（科目层，行为已正确）
  - 不得删除历年试卷/智能组卷/错题本在**题库页**的入口
  - 不得复制题目渲染逻辑

  **Agent 画像**：
  - **类别**：`visual-engineering` — 涉及布局与交互层级重排
  - **技能**：`frontend-ui-ux` — 底栏遮挡与视觉层级需实际排版验证

  **并行信息**：
  - **可并行**：是
  - **并行组**：Wave 1（与任务 2、3、4、5、6 并发）
  - **阻塞**：F1-F4
  - **被阻塞**：无

  **参考资料**：
  - `.vtj/vue/mobile_practice.vue:44-48` — 保留的科目层按钮写法
  - `.vtj/vue/mobile_practice.vue:356-399` — 三个 `mixedPractice*` 函数的出题参数
  - `.vtj/vue/mobile_practice.vue:625-631` — `.scroll-area` 现有样式
  - `.vtj/vue/mobile_practice.vue:421-427` — `moreResources` 定义
  - `src/components/MobileTabBar.vue:83` — 底栏固定定位与高度来源

  **验收标准**：
  - [ ] 子科目卡片内不再有混合练习按钮
  - [ ] 考点列表内不再有混合练习按钮
  - [ ] 子科目列表顶部存在唯一「本知识点分类混合练习」按钮
  - [ ] `moreResources` 仅剩 2 项
  - [ ] 滚动到底部时「更多练题资源」不被底栏遮挡
  - [ ] LSP 0 error

  **QA 场景**：
  ```
  场景：混合练习层级正确（正常路径）
    工具：Playwright
    步骤：
      1. 打开 /#/mobile/practice
      2. 断言科目层存在 1 个 .subject-mixed 按钮
      3. 断言子科目卡片内 .mixed-btn 数量为 0
      4. 断言子科目列表顶部存在 1 个聚合混合练习按钮
      5. 点击某个子科目进入知识点列表，断言 .kp-item 内无混合练习按钮
    预期：层级为「科目层 1 个 + 子科目列表顶部 1 个」，无逐项按钮
    证据：.omo/evidence/task-1-mixed-hierarchy.png

  场景：底栏遮挡已修复（边界路径）
    工具：Playwright
    步骤：
      1. 滚动 .scroll-area 至底部
      2. 取「更多练题资源」最后一项的 getBoundingClientRect().bottom
      3. 取底栏 getBoundingClientRect().top
      4. 断言前者 < 后者（未被覆盖）
    预期：内容底边严格小于底栏顶边
    证据：.omo/evidence/task-1-no-overlap.png
  ```

  **提交**：是 — `fix(practice): 重构混合练习层级并修复底栏遮挡`

- [ ] 2. 今日目标弹窗升级为电脑端 4 字段设计（需求 1）

  **实现内容**：
  - 参照电脑端 `.vtj/vue/personal_goal.vue:94-113` 的 4 字段设计，改造 `mobile_home.vue` 的今日目标弹窗：今日目标（题）、本周目标（题）、明日计划科目、计划题量
  - 复用既有接口 `POST /api/goals/`（`personal_goal.vue:177-178`），不新增后端接口
  - 保留原有「创建/编辑」双态逻辑（`openGoalEdit` / `saveGoal`）
  - 全部文案使用中文

  **禁止事项**：
  - 不得修改后端 `backend/app/api/v1/goals.py`
  - 不得删除现有单字段编辑能力（改为多字段并存）
  - 不得硬编码目标数值

  **Agent 画像**：
  - **类别**：`visual-engineering`
  - **技能**：`frontend-ui-ux` — 弹窗表单布局需与电脑端视觉一致

  **并行信息**：
  - **可并行**：是
  - **并行组**：Wave 1
  - **阻塞**：F1-F4
  - **被阻塞**：无

  **参考资料**：
  - `.vtj/vue/personal_goal.vue:87-118` — 电脑端弹窗完整结构（**必须逐字段对齐**）
  - `.vtj/vue/personal_goal.vue:177-178` — `POST /api/goals/` 请求写法
  - `.vtj/vue/mobile_home.vue` `openGoalEdit` / `saveGoal` — 现有逻辑与表单状态
  - `backend/app/api/v1/goals.py:108` — `POST /` 接受的字段

  **验收标准**：
  - [ ] 弹窗含 4 个字段且中文标签正确
  - [ ] 输入校验与电脑端一致（含 min/max）
  - [ ] 保存走 `POST /api/goals/`
  - [ ] 创建与编辑两态均可用
  - [ ] 同步 DSL methods，LSP 0 error

  **QA 场景**：
  ```
  场景：4 字段弹窗完整可用（正常路径）
    工具：Playwright
    步骤：
      1. 打开 /#/mobile/home，点击今日目标卡片
      2. 断言存在 4 个输入框，标签依次为「今日目标（题）」「本周目标（题）」「明日计划科目」「计划题量」
      3. 各填入合法值并保存
      4. 断言保存成功提示且卡片数值更新
    预期：4 字段齐全、保存成功
    证据：.omo/evidence/task-2-goal-dialog.png

  场景：非法输入被拦截（异常路径）
    工具：Playwright
    步骤：
      1. 今日目标填 0（低于 min=10）
      2. 点击保存
      3. 断言前端校验拦截，未发出请求
    预期：提示且不保存
    证据：.omo/evidence/task-2-goal-dialog-error.png
  ```

  **提交**：是 — `feat(home): 今日目标弹窗升级为四字段`

- [ ] 3. 答题卡页五项改造（需求 7）

  **实现内容**：
  - **7a 渲染修复（最高优先）**：`answer_page.vue:111` 题干与 `:135` 选项改用 `renderQuestionContent`。**关键**：`:481-485` 的 `/api/questions/random` 分支已渲染，需**逐条核查其余出题入口**（quick-practice、smart-exam、错题复习等传参路径）是否存在未渲染分支，这是选项空白的真正根因
  - **7b 布局**：`答题卡` 按钮从 `toolbar-left`（`:8`）移至右上角 `toolbar-right`（`:23-37`）；`progress-info`（`:13-21`）由纯文字改为**可视进度条**
  - **7c 记背模式**：新增 `state.mode`（`practice` / `memorize`）与切换控件；记背模式下隐藏选项选择交互，直接展示答案与解析
  - **7d 答案延后显示**：做题模式下，未答完所有题目前不显示答案与解析（复用现有解析区，加完成判定）

  **禁止事项**：
  - 不得修改 `src/utils/questionRender.js`
  - 不得改 `answer_page.vue` 之外的文件
  - 不得破坏倒计时与自动保存

  **Agent 画像**：
  - **类别**：`deep` — 涉及多条出题路径核查与模式状态机
  - **技能**：`frontend-ui-ux` — 进度条与模式切换需视觉验证

  **并行信息**：
  - **可并行**：是
  - **并行组**：Wave 1
  - **阻塞**：F1-F4
  - **被阻塞**：无

  **参考资料**：
  - `.vtj/vue/answer_page.vue:111,135` — 待修裸 `v-html`
  - `.vtj/vue/answer_page.vue:450-500` — 已正确渲染的分支（作为其它分支的对照样板）
  - `.vtj/vue/answer_page.vue:6-38` — 工具栏结构
  - `.vtj/vue/answer_page.vue:40-70` — 现有答题卡面板（勿重复实现）
  - `src/utils/questionRender.js` — 渲染真源签名

  **验收标准**：
  - [ ] 题干与选项的图片正常显示
  - [ ] 选项文字不丢失
  - [ ] 全仓答题页无裸 `v-html`
  - [ ] 答题卡入口位于右上角
  - [ ] 顶部有可视进度条
  - [ ] 记背模式可切换且行为正确
  - [ ] 做题模式答完前不显示答案解析
  - [ ] 回归测试 10/10，LSP 0 error

  **QA 场景**：
  ```
  场景：选项与图片正常渲染（正常路径）
    工具：Playwright
    步骤：
      1. 进入含图片题目的练习
      2. 断言 .q-stem 内存在 img.q-img
      3. 断言 .option-text 文本非空
      4. 截图
    预期：图片与选项均可见
    证据：.omo/evidence/task-3-render.png

  场景：答案延后显示（边界路径）
    工具：Playwright
    步骤：
      1. 进入做题模式，仅答第 1 题
      2. 断言解析区不显示
      3. 答完最后一题
      4. 断言解析区显示
    预期：答完前不显示答案
    证据：.omo/evidence/task-3-defer-answer.png
  ```

  **提交**：是 — `fix(answer): 修复渲染并新增答题卡页模式与进度条`

- [ ] 4. 智能组卷页布局与预览修复（需求 6）

  **实现内容**：
  - `smart_exam.vue:124` 与 `:142` 的「重新生成」按钮误用 `.back-btn` 类导致样式错乱，改用正确按钮类
  - 图标尺寸统一（当前偏大、变形），加统一尺寸约束
  - 排查 `doGenerate`（`:276`）为何未产出试卷预览，修复后必须能看到预览

  **禁止事项**：
  - 不得修改后端 `/api/smart-exam/*` 接口
  - 不得删除已有返回入口

  **Agent 画像**：
  - **类别**：`visual-engineering`
  - **技能**：`frontend-ui-ux`

  **并行信息**：
  - **可并行**：是
  - **并行组**：Wave 1
  - **阻塞**：F1-F4
  - **被阻塞**：无

  **参考资料**：
  - `.vtj/vue/smart_exam.vue:75, 124, 142` — 按钮类误用处
  - `.vtj/vue/smart_exam.vue:276, 362` — `doGenerate` / `regenerate`
  - `.vtj/vue/smart_exam.vue:410` — `preview-hero` 预览区样式

  **验收标准**：
  - [ ] 返回按钮样式正确
  - [ ] 「重新生成」样式与返回按钮区分
  - [ ] 图标尺寸协调不变形
  - [ ] 智能生成后可见试卷预览
  - [ ] LSP 0 error

  **QA 场景**：
  ```
  场景：生成后可见预览（正常路径）
    工具：Playwright
    步骤：
      1. 打开 /#/smart-exam
      2. 点击「智能生成」
      3. 断言预览区出现试卷题目摘要
      4. 截图
    预期：预览可见
    证据：.omo/evidence/task-4-preview.png
  ```

  **提交**：是 — `fix(smart-exam): 修复按钮样式与试卷预览`

- [ ] 5. 题库页移除「快速练习」入口（需求 5b）

  **实现内容**：
  - `mobile_question_bank.vue:173-180` 的 `topActions` 移除 `quick`（快速练习）项，及其 `selectTopAction`（`:289-305`）中的 `quick` 分支
  - 保留历年试卷、智能组卷、错题本入口（由任务 1 从「更多练题资源」移除后，此处为唯一入口）
  - 同步 DSL methods

  **禁止事项**：
  - 不得删除其余三项入口
  - 不得改动 `/mobile/practice` 路由本身

  **Agent 画像**：
  - **类别**：`quick`

  **并行信息**：
  - **可并行**：是
  - **并行组**：Wave 1
  - **阻塞**：F1-F4
  - **被阻塞**：无

  **参考资料**：
  - `.vtj/vue/mobile_question_bank.vue:173-180` — `topActions` 定义
  - `.vtj/vue/mobile_question_bank.vue:289-305` — `selectTopAction` 分支

  **验收标准**：
  - [ ] 顶栏不再显示「快速练习」
  - [ ] 其余三项入口仍可用
  - [ ] 死代码已清理
  - [ ] DSL 已同步，LSP 0 error

  **QA 场景**：
  ```
  场景：题库顶栏入口正确（正常路径）
    工具：Playwright
    步骤：
      1. 打开 /#/mobile/question-bank
      2. 断言顶栏为 5 项且不含「快速练习」
      3. 断言「历年试卷」仍可点击并跳转
    预期：无快速练习，其余可用
    证据：.omo/evidence/task-5-topactions.png
  ```

  **提交**：是 — `refactor(question-bank): 移除快速练习入口`

- [ ] 6. 申论科目数据核查（需求 2）

  **实现内容**：
  - 核查 `question_subject` 表中申论记录：是否存在、`status` 是否为 1、`sort_order` 是否合理
  - 核查申论是否有子科目与知识点数据（否则前端下钻为空）
  - 若数据缺失，**输出诊断报告与补数建议**；是否执行数据订正需用户确认（涉及生产数据，不得擅自改库）

  **禁止事项**：
  - 不得擅自 INSERT/UPDATE 生产数据
  - 不得修改后端代码（前端 `subjectMeta[2]=申论` 已存在，非前端缺陷）

  **Agent 画像**：
  - **类别**：`unspecified-high`

  **并行信息**：
  - **可并行**：是（只读核查，不改代码）
  - **并行组**：Wave 1
  - **阻塞**：F1-F4
  - **被阻塞**：需数据库访问权限

  **参考资料**：
  - `.vtj/vue/mobile_practice.vue:206-210` — `subjectMeta` 已含申论
  - `backend/app/api/v1/quick_practice.py:66-86` — 科目来源 `status==1`
  - `backend/app/api/v1/quick_practice.py:95` — `subjectId` 限制 `ge=1, le=3`

  **验收标准**：
  - [ ] 输出申论数据现状结论
  - [ ] 明确指出是数据缺失还是前端问题
  - [ ] 给出可执行补数建议

  **QA 场景**：
  ```
  场景：申论科目可见（正常路径）
    工具：Bash（curl）
    步骤：
      1. curl /api/quick-practice/subjects（带认证）
      2. 断言返回项含 subject_name 为「申论」
    预期：申论出现在科目列表
    证据：.omo/evidence/task-6-shenlun-subjects.json
  ```

  **提交**：否（只读诊断）

---

## Final Verification Wave

> 全部实现任务完成后执行。4 个评审并行，全部通过方可交用户确认。
> **禁止在获得用户明确认可前勾选 F1-F4。**

- [ ] F1. **需求符合性审计** — `oracle`
  逐条核对本计划 7 项需求是否落地。逐条读取改动文件确认；检查 `.omo/evidence/` 证据文件是否齐备。
  输出：`需求 [N/7] | 证据 [N/M] | 结论：通过/驳回`

- [ ] F2. **代码质量评审** — `unspecified-high`
  运行 `vite build` 与渲染回归测试；审查 `as any`/`@ts-ignore`/空 catch/console.log 残留/注释掉的代码；确认 VTJ `.vue` 与 `.json` 的 `__VERSION__` 一致且新增方法已声明。
  输出：`构建 [通过/失败] | 测试 [N/N] | 文件 [N 干净/N 问题] | 结论`

- [ ] F3. **真机 Playwright QA** — `unspecified-high`
  从干净状态执行**所有**任务的 QA 场景；重点验证 7 项需求的真实交互；检查控制台无报错。
  输出：`场景 [N/N] | 需求覆盖 [7/7] | 控制台 [干净/有错] | 结论`

- [ ] F4. **范围忠实度检查** — `deep`
  核对每个任务「实现内容」与实际改动一致；确认未越界改动（如 `teacher_papers.vue`、后端文件）；确认未复制题目渲染逻辑。
  输出：`任务 [N/N 合规] | 越界 [无/N 处] | 结论`

---

## Commit Strategy

- `fix(practice): 重构混合练习层级并修复底栏遮挡` — `.vtj/vue/mobile_practice.vue` + 对应 `.json`
- `feat(home): 今日目标弹窗升级为四字段` — `.vtj/vue/mobile_home.vue` + 对应 `.json`
- `fix(answer): 修复渲染并新增答题卡页模式与进度条` — `.vtj/vue/answer_page.vue` + 对应 `.json`
- `fix(smart-exam): 修复按钮样式与试卷预览` — `.vtj/vue/smart_exam.vue` + 对应 `.json`
- `refactor(question-bank): 移除快速练习入口` — `.vtj/vue/mobile_question_bank.vue` + 对应 `.json`

**禁止**：提交 `.vtj/vue/teacher_papers.vue`、`backend/app/api/v1/question_import.py` 等他人未提交改动。

---

## Success Criteria

### 验证命令
```bash
node C:\Users\21499\AppData\Local\Temp\opencode\test-question-render.mjs   # 期望 10 passed, 0 failed
npx cross-env ENV_TYPE=live npx vite build                                  # 期望退出码 0
npm run typecheck:guarded                                                   # 期望仅 teacher_papers.vue 既有基线失败
```

### 最终清单
- [ ] 需求 1-7 全部落地
- [ ] 全仓答题内容无裸 `v-html`
- [ ] 渲染回归测试 10/10
- [ ] `vite build` 通过
- [ ] VTJ DSL 全部同步
- [ ] 全部注释与文案为中文
- [ ] 未越界改动他人文件


