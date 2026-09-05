# 题目导入功能模块 — 满血完善方案实施记录

## 实施日期
2026-08-05

## 问题回顾

### 问题1: 分离导入 0% 匹配率
- **根因**: 答案文档无题号时，前后端解析逻辑均无法匹配 → match_rate = 0%
- **修复**: 
  1. 新增 `ContentCleaner` 噪声过滤器
  2. 新增 `_match_pure_sequence_enhanced()` 纯序列位置匹配（支持空格/逗号/换行/中文答案/混合格式）
  3. 新增 `POST /api/questions/import/parse` 统一解析端点
  4. 前端 `matchSeparateQuestionsAnswers()` 改为后端 Pipeline 优先

### 问题2: 合并导入图片丢失
- **根因**: 前端 `extractQuestionFromBlock()` 不保留 `[IMAGE:xxx]` 占位符
- **修复**: 后端 `_extract_image_refs_from_content()` 提取并定位图片引用

### 问题3: 图片导入OCR能力不足
- **根因**: PaddleOCR仅基础文字识别，无公式/表格/手写支持
- **修复**:
  1. `enhance_preprocessing()`: 超分辨率 + CLAHE + 透视校正
  2. `detect_formula_regions()`: 公式区域检测 + LaTeX转换
  3. `detect_table_structure()`: 表格结构检测 + HTML输出
  4. `recognize_image_enhanced()`: 统一增强OCR入口

## 架构变更

### 之前（前后端双重解析）
```
前端: parseRawTextToQuestions → extractQuestionFromBlock → 6种本地匹配策略 (1100+行)
后端: text_parser.py → smart_match_questions_answers → 7种策略
问题: 策略不一致、不可测试、难以扩展
```

### 之后（统一后端Pipeline）
```
前端 (Thin UI): callBackendParse → 渲染 ParseResult → 用户修正 → 确认提交
后端: /parse → ContentCleaner → QuestionSplitter → QuestionParser → AnswerMatcher → Validator
优势: 策略统一、可测试、易扩展
```

## 文件变更清单

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `backend/app/schemas/schemas.py` | +60行 | 新增 ParseRequest, ParseResult, ParsedQuestion, ImageRef, OCREnhancedResult |
| 2 | `backend/app/services/text_parser.py` | +200行 | ContentCleaner类, _match_pure_sequence_enhanced, 策略链增强 |
| 3 | `backend/app/services/ocr.py` | +250行 | enhance_preprocessing, detect_formula_regions, detect_table_structure, recognize_image_enhanced |
| 4 | `backend/app/api/v1/question_import.py` | +200行 | 新增 /parse 端点, 增强 /ocr 端点, _fallback_loose_parse |
| 5 | `.vtj/vue/question_import.vue` | +80/-200行 | callBackendParse, 简化matchSeparateQuestionsAnswers/parseOcrTextToQuestions, 修复_readDocViaBackend |

### 不影响的功能模块
- 路由 (src/router/index.ts)
- 认证 (src/auth.ts)
- 数据库模型 (models.py)
- 单题录入 (submitSingle)
- 导入记录 (loadRecords)
- 其他VTJ页面

## 新增API端点

### POST /api/questions/import/parse
统一文档解析入口，替代前端所有本地解析逻辑。

**请求体 (ParseRequest):**
```json
{
  "questions_text": "1. 题目内容...",
  "answers_text": "A B C D...",
  "mode": "separate",
  "paper_name": "2024国考行测",
  "subject_category": "行测"
}
```

**响应体 (ParseResult):**
```json
{
  "status": "success",
  "questions": [{
    "question_number": 1,
    "question_content": "...",
    "options": [{"key": "A", "value": "..."}],
    "answer": "C",
    "analysis": "...",
    "images": [{"path": "[IMAGE:xxx]", "position": "stem"}],
    "question_type": "单选题",
    "subject_category": "行测"
  }],
  "match_rate": 100.0,
  "matched_count": 30,
  "total_questions": 30,
  "strategy_used": "增强纯序列匹配(30题)"
}
```

## 验证结果

### ContentCleaner 测试
- ✅ 页码过滤: `第1页（共12页）` 正确过滤
- ✅ 社交媒体: `扫一扫关注公众号` 正确过滤
- ✅ 题目内容保持完整

### 增强纯序列匹配测试
- ✅ 空格分隔: `A B C D A B C D` → 12个字母全部提取
- ✅ 中文答案: `对 错 对 错 对` → A B A B A
- ✅ 混合格式: `1A 2B 3C 4D 5A` → 5题全部匹配

### 代码编译验证
- ✅ schemas.py — 编译通过
- ✅ text_parser.py — 编译通过
- ✅ ocr.py — 编译通过
- ✅ question_import.py — 编译通过

## VTJ同步提醒
修改 `.vtj/vue/question_import.vue` 的 `<script>` 后，需要执行:
```bash
node vtj-mcp-server/vtj-mcp-server.js --sync question_import
```
或在VTJ MCP工具中使用 `vtj_sync_vue_to_dsl`。
