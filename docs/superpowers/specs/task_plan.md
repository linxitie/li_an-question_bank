# 答题卡 + DOCX导入 — 全面修复

## Goal
修复答题卡全部5个问题：选项显示、多选徽章、类型检测、DOCX导入0题、图片提取

## Phases

### Phase 1: 诊断根因
- **Status**: complete
- API测试：28/50嵌套dict、50/50类型乱码、11/50选项缺失、0题有图片
- DB验证：options列value是真正JSON对象 `{"key":"A","value":{"key":"A","value":"..."}}`（非字符串）
- type_detail列：hex为正确UTF-8但SQLAlchemy→JSON序列化路径有编码杂音

### Phase 2: 修改1 — _normalize_options 递归提取
- **Status**: complete
- File: `backend/app/api/v1/questions.py` L170-231
- 增加 `isinstance(val, dict)` 分支处理嵌套JSON对象（关键修复）
- 同时处理字符串化dict格式 `"{'key':'A','value':'...'}"`
- 去重（seen set）+ 补全（<4时用 "D. (待补充)" 填充）

### Phase 3: 修改2 — ENUM扩展 + 类型fallback
- **Status**: complete
- File: `backend/app/models/models.py` L768-770 — 增加"单选题""多选题""不定项"
- File: `backend/app/api/v1/questions.py` — `_detect_multi_from_content()` + `/random`端点乱码检测

### Phase 4: 修改4 — 前端类型映射
- **Status**: complete
- File: `.vtj/vue/ujvdv5fe.vue` L325 — typeMap + answer.length启发式fallback

### Phase 5: 修改5 — DOCX导入后端解析化
- **Status**: complete
- File: `backend/app/api/v1/question_import.py` — `_extract_text_from_docx`遍历run查找drawing
- `upload_file_for_import` DOCX分支使用 `extract_question_blocks` 返回结构化数据

### Phase 6: 修改6 — DB数据修复
- **Status**: complete
- File: `backend/scripts/fix_answer_page_data.py` — FIX4嵌套value解码、FIX5类型修正
- 直接SQL: 430条"选择题"→395单选+35多选

### Phase 7: 验证
- **Status**: complete
- curl测试: 40/40选项OK, 0 BAD
- 原始JSON字节: 正确的UTF-8 "单选题"/"多选题"

## Verification
1. `curl /api/questions/random?count=5` → options为干净 "A. xxx" 格式
2. type_detail 为 "单选题" 或 "多选题"
3. 浏览器硬刷新后多选徽章应显示
4. DOCX上传应返回 `total_questions > 0`

## Errors Encountered
| Error | Resolution |
|-------|------------|
| `_normalize_options`未递归dict对象 | 增加 `isinstance(val, dict)` 分支 |
| DB修复脚本FIX5返回0条 | 直接SQL更新：选择题→单选题/多选题 |
| 管道编码杂音误导诊断 | 保存curl输出为文件检查原始字节 |
| Git Bash taskkill /PID被解析为路径 | 使用PowerShell `Stop-Process` |
