# Progress Log

## Session: 2026-06-20 — 答题卡全面修复

### Completed
- [x] 诊断5个答题卡问题根因（API测试 + DB直接查询 + 原始JSON字节检查）
- [x] `_normalize_options` 递归提取嵌套JSON对象 + 字符串两种格式
- [x] `question_type_detail` ENUM扩展（单选题/多选题/不定项）
- [x] API `/random` 端点类型fallback（`_detect_multi_from_content` + 乱码检测）
- [x] 前端 `ujvdv5fe.vue` 类型映射表 + answer.length启发式
- [x] DOCX `_extract_text_from_docx` 图片提取修复（遍历run→drawing→blip）
- [x] `upload_file_for_import` DOCX分支使用后端 `extract_question_blocks`
- [x] DB修复脚本 FIX4（嵌套value）+ FIX5（类型修正）
- [x] 直接SQL: 430条"选择题"→395单选+35多选
- [x] curl验证: 40/40选项OK, 原始JSON字节正确UTF-8
- [x] 后端重启3次（缓存清理+验证修复生效）

### Files Modified
- `backend/app/api/v1/questions.py` — _normalize_options + _detect_multi_from_content + /random fallback
- `backend/app/models/models.py` — question_type_detail ENUM
- `.vtj/vue/ujvdv5fe.vue` — type mapping
- `backend/app/api/v1/question_import.py` — _extract_text_from_docx + upload_file_for_import DOCX branch
- `backend/scripts/fix_answer_page_data.py` — FIX4 + FIX5

### Next Steps (user action)
- Hard refresh browser (Ctrl+Shift+R)
- Test answer page: options display, multi-select badges, multi-select toggle
- Test DOCX import: upload DOCX, verify question count > 0, verify image extraction
