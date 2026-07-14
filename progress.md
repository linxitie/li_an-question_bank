# Progress Log

## Session: 2026-06-20 — 答题卡全面修复(v2)

### Round 1: 诊断+基础修复
- [x] API测试：28/50嵌套dict、50/50乱码、11/50缺失、0图片
- [x] _normalize_options递归提取(嵌套dict对象+字符串)
- [x] question_type_detail ENUM扩展+API fallback
- [x] 前端typeMap+answer.length启发式
- [x] DB修复：676嵌套value+430类型修正

### Round 2: 图片管线
- [x] DOCX图片提取(XPath+para._p+iterdescendants)
- [x] 前端v-html渲染+选项IMAGE替换
- [x] _extract_options死代码移除(100/100干净)
- [x] DOCX导入后端解析化(extract_question_blocks)
- [x] 34题导入(8题含图片) + 12图片HTTP 200验证

### Round 3: 严格4选项+去重+映射
- [x] _extract_options [A-H]→[A-D]
- [x] _normalize_options A-D键过滤+content补全
- [x] /random端点85%去重(48/50正确过滤)
- [x] DB FIX6(补全)+FIX7(嵌入标记清理)
- [x] 最终验证：0!=4选项, 0待补充, 0重复对

### Files Modified
- backend/app/api/v1/questions.py — _normalize_options + dedup + type fallback
- backend/app/models/models.py — ENUM扩展
- backend/app/services/text_parser.py — _extract_options A-D + 死代码移除 + content补全
- backend/app/api/v1/question_import.py — XPath图片提取 + DOCX后端解析
- backend/scripts/fix_answer_page_data.py — FIX4-7
- .vtj/vue/ujvdv5fe.vue — v-html + IMAGE替换 + CSS + typeMap

### Direct DB fixes
- 676嵌套value解码(sqlite3)
- 430类型修正(选择题→395单选+35多选)
- 16嵌入标记清理
