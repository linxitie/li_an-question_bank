# 答案归一化 canonical_answer

## 问题

答案正则捕获组 `[A-Da-d对错正确错误是否]+` 只匹配**连续字母**，导致多选答案被截断：
- `答案：A、B、C` → 捕获 `A`
- `答案：A B` → 捕获 `A`
- `答案：A，B` → 捕获 `A`

多选信号（答案多字母）因此丢失，间接导致题型被误判为单选。

## 方案

新增 `canonical_answer(answer) -> str`（text_parser.py），作为唯一答案归一化入口：

```
1. 全角 → 半角（全角字母/数字/符号）
2. 中文判断词 → 字母：对/正确/是/√ → A，错/错误/否/× → B（按长度降序替换，避免子串误命中）
3. 去分隔符/空白/标点，统一大写，仅保留 [A-Z0-9]
```

### 示例

| 输入 | 输出 |
|---|---|
| `A、B、C` | `ABC` |
| `A B` | `AB` |
| `A，B` | `AB` |
| `对` | `A` |
| `正确` | `A` |
| `错` / `错误` | `B` |
| `√` | `A` |
| `×` | `B` |
| `a,b` | `AB` |

## 使用范围（单一事实来源）

- `text_parser.extract_answer_from_lines`（标准分支 + 嵌入式分支）：提取后归一化。
- `text_parser._detect_question_type`：答案多字母判定。
- `questions._detect_multi_from_content`：读路径兜底。
- `question_import._normalize_question` / `confirm_batch_import`：入库前归一化。
- `repair_question_types.py`：历史数据归一化。

## 边界与安全

- **仅用于客观题**（单选/多选/判断）的字母答案归一化；论述/写作题的自由文本答案**不经过**此函数（否则会丢失正文）。
- 归一化后为空（如答案="待补充"占位符）时，调用方**保留原文**，不丢失占位标记。
- `ANSWER_PATTERNS` 捕获组已拓宽为含分隔符 `[A-Da-d对错正确错误是否、，,;；\s·]+`，
  但 `range`/`per_item` 模式（多题连续答案序列）仍保持连续字母，交由 `parse_answer_sequence` 逐题处理，避免误捕获。
