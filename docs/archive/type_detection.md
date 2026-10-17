# 题型判定机制设计与单一事实来源

## 核心问题：题型三处事实来源分裂

历史代码里，一道题的"题型"存在三处互不一致的来源：

| 来源 | 存储位置 | 读取方 |
|---|---|---|
| `question_bank.type_id` → `question_type.type_name` | type_id 外键 | **教师端** `q.type.type_name` |
| `question_detail_category.question_type_detail` | 去规范化字符串 | **学生端** `/random`、`/exercise` |
| 读路径兜底 `_detect_multi_from_content` | 运行时检测 | `/random` 无 detail 时 |

**数据证据**（793 道题）：type_id 层错位 122 道（97 道选择题指到"论述题"、25 道多选指到"单选"），
detail 层错位 32 道（真实多选被标单选/论述）。教师端因此大面积显示错误题型。

## 修复方案：统一单一事实来源

1. **判定入口统一**：`_detect_question_type(content, options, answer)` 是唯一判定逻辑（见 keyword_engineering.md）。
2. **答案归一化统一**：`canonical_answer` 是唯一答案归一化逻辑（见 answer_normalization.md）。
3. **读路径兜底统一**：`questions.py._detect_multi_from_content` 改用 `canonical_answer`，与主判定一致。
4. **数据修复统一**：`repair_question_types.py` 用同一判定函数回填历史数据，使 type_id 与 detail 一致。
5. **启动迁移去害**：移除 `main.py` 中「选择题→单选题」批量折叠（选择题是歧义值，不可盲目折叠为单选）。

## 关键 bug 修复明细

| 位置 | bug | 修复 |
|---|---|---|
| `question_import.py:2614` | 2 参同名 `_detect_question_type` 遮蔽导入的 3 参函数，丢弃 answer 参数 | 删除遮蔽函数 |
| `question_import.py:2372/2513` | OCR 调用不传 answer/options | 补传 `_extract_options` + answer |
| `question_import.py:2191` | `_fallback_loose_parse` 3 参调用被遮蔽触发 TypeError | 移除遮蔽后自动恢复 |
| `question_import.py:_normalize_question` | Excel 缺题型列默认「选择题」→单选 | 改为关键词工程重检测 |
| `question_import.py:confirm_batch_import` | 默认「选择题」→单选 | 改为重检测 + 答案归一化 |
| `questions.py:_detect_multi_from_content` | `len>1 and isalpha()` 对 `A、B` 失效 | 改用 canonical_answer |
| `main.py` 启动迁移 | 「选择题→单选」批量折叠 | 移除，交由修复脚本重检测 |

## 判断题处理

系统仅保留 4 种标准类型：单选/多选/论述/写作。判断题（选项为"对/错"两项）自然归入**单选题**，
答案 `对/正确/是/√`→A、`错/错误/否/×`→B（由 canonical_answer 完成），前端即可正确高亮。
