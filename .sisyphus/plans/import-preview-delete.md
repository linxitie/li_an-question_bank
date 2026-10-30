# 题目导入：移除「查看原始文本」+ 逐题删除 计划

- 计划文件：`.sisyphus/plans/import-preview-delete.md`
- 依据工作流：`CLAUDE.md/Opencode执行命令工作流.md`
- 状态：**待人工审核（工作流第二节）**

---

## 一、任务目标

1. 硬删除「题目导入」页的「查看原始文本」功能（无实际意义且占资源）。
2. 识别匹配后，为**每道题**增加「删除」按钮，供教师剔除解析出错的题。
3. 删除后题目序号自动重排，且**题目 / 答案 / 答案解析保持正确对应**。

---

## 二、上下文调查结论（已核实，非推测）

| 结论 | 依据 |
|---|---|
| 「查看原始文本」共 2 处 | `question_import.vue` L219-222（渲染**全文**）、L309-317（各截 3000 字） |
| 预览列表是子组件 | `question_preview_list.vue`，在导入页 **L208 / L298 / L391 三处复用** |
| 题号显示是**索引驱动** | `question_preview_list.vue` L36 `第 {{ idx + 1 }} 题` → 数组删除即自动重排 |
| 组件**不使用** `question_number` | 全文件检索无引用 |
| 导入载荷**不含** `question_number` | L2513-2524 只传 content/options/answer/analysis/type/subject/score/difficulty |
| 答案与解析**随题目对象携带** | 同上，answer/analysis 是对象字段，删对象不会错位 |
| `question_number` 的真实用途 | 异常面板回溯原文位置（L452/454/2629）与匹配对齐校验（L2125-2135）→ 应保留**原文档编号** |

**结论：删除题目对象 + 依赖索引重排即可同时满足「序号重排」与「答案解析不错位」，无需重写任何映射逻辑。**

---

## 三、修改方案

### 3.1 硬删除「查看原始文本」

删除两处 `<details>` 块。**保留底层 state 字段**，因为它们是解析工作变量而非展示专用：
- `state.rawTextPreview`：L1497 `parseRawTextToQuestions` 的输入、L2280 提取试卷标题的来源
- `state.separateQuestionsRawText` / `separateAnswersRawText`：L2067-2076、L2175-2189 作为匹配 API 的真实入参

> 只删 UI，收益是消除把整篇文档（可达上百 KB）渲染进 DOM 的开销；
> 若连 state 一并删除会直接打断解析与匹配主流程。

### 3.2 逐题「删除」按钮

`question_preview_list.vue`：
- L43-47 按钮区新增「删除」按钮，`@click="$emit('delete-question', idx)"`
- L154 `emits` 增加 `'delete-question'`
- 新增 `.btn-mini-delete` 样式（与既有 mini 按钮一致，红色系以示危险）
- 已导入（`q._imported`）的题禁用删除，避免"已入库再删"的语义歧义

`question_import.vue`：
- **三处** `<QuestionPreviewList>` 均绑定 `@delete-question="handleDeleteQuestion"`
- 新增 `handleDeleteQuestion(idx)`：`ElMessageBox.confirm` 二次确认 → `splice(idx,1)` →
  重排 `question_number` 显示序号 → 提示剩余题数

### 3.3 判断题答案输入的可用性修正

判断题答案现为「正确/错误」（2 个汉字），而输入框仍是
`placeholder="A/B/C/D"` `maxlength="4"` 且提示「请输入选项字母」。
按题型自适应：`判断题` 时 placeholder 改为「正确/错误」、`maxlength="8"`、提示改为
「判断题请填写 正确 或 错误」。

---

## 四、涉及文件

| 文件 | 改动 |
|---|---|
| `.vtj/vue/question_import.vue` | 删 2 处原始文本 UI；3 处绑定删除事件；新增 `handleDeleteQuestion` |
| `.vtj/vue/question_preview_list.vue` | 新增删除按钮 + emit + 样式；答案输入按题型自适应 |
| `.vtj/files/question_import.json` | 改后需同步 DSL |
| `.vtj/files/question_preview_list.json`（若存在） | 改后需同步 DSL |

---

## 五、验收标准

1. 「查看原始文本」在合并导入、分离导入两种模式下**均不再出现**。
2. 上传→识别匹配后，每张题卡右上角有「删除」按钮。
3. 删除中间某题后：其下各题序号连续（1,2,3…），**答案与解析仍跟随各自题目**，无错位。
4. 已导入的题删除按钮禁用。
5. 删除有二次确认；取消确认不改变列表。
6. 题目全部删除后页面不报错。
7. 判断题答案可正常填入「正确/错误」。
8. VTJ DSL 同步后 `vtj_check_consistency` 无不一致。
9. Playwright 实测：真实上传该 docx+pdf，删除中间一题，校验序号与答案对应正确，控制台零报错。

---

## 六、风险点

- **R1（中）删除是"预览态删除"而非"已入库删除"。**
  本计划作用于识别匹配后的预览列表；已入库题目的删除走「题目管理」模块。
  若需要入库后删除，需另加接口。
- **R2（低）`question_number` 保留原文档编号会留空洞（如 1,2,4,5）。**
  这是**有意为之**：异常面板依赖它回溯原文位置。但若教师期望"序号与原文一致"，
  需改为重排——两者不可兼得，本计划选择保留原文编号。
- **R3（低）三处复用组件，漏绑一处会导致该入口删除无效。**
  验收标准 2/9 覆盖三个入口。
- **R4（低）删除后 `separateMatchRate` 等统计值不会重算。**
  匹配率是解析期产物，删除个别题不影响其有效性，无需重算。
