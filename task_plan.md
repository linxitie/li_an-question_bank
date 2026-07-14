# 砺安题库 — 答题卡+导入全面修复

## Goal
修复答题卡5大问题：选项显示、多选徽章、类型检测、DOCX导入0题、图片提取。后续追加：严格4选项A-D、API查重、选项映射清理。

## Phases

### Phase 1: 诊断根因 → complete
- API测试：28/50嵌套dict、50/50类型乱码、11/50选项缺失、0题图片
- DB验证：options value是真正JSON对象（非字符串）；type_detail hex正确但序列化路径杂音

### Phase 2: _normalize_options 递归提取 → complete
- 增加 `isinstance(val, dict)` 分支（关键修复）+ 字符串化dict处理
- 去重(seen set) + 补全(<4时从content提取)

### Phase 3: ENUM扩展+类型fallback → complete
- models.py: 增加"单选题""多选题""不定项"
- questions.py: `_detect_multi_from_content()` + /random端点乱码检测

### Phase 4: 前端类型映射 → complete
- ujvdv5fe.vue: typeMap + answer.length启发式fallback

### Phase 5: DOCX导入后端解析化 → complete
- _extract_text_from_docx: XPath+para._p精准图片定位，支持 stem/option/混合 三种位置
- upload_file_for_import: DOCX分支使用extract_question_blocks

### Phase 6: 图片前端渲染 → complete
- ujvdv5fe.vue: v-html渲染stem+option；选项IMAGE替换；CSS

### Phase 7: DB数据修复 → complete
- FIX4: 嵌套value解码(676题)
- FIX5: question_type_detail乱码修复(430题→395单选+35多选)
- FIX6: <4选项补全
- FIX7: 嵌入选项标记清理(16题)

### Phase 8: 严格4选项A-D防线 → complete
- text_parser.py: _extract_options [A-H]→[A-D] + 死代码移除 + content回退补全
- questions.py: _normalize_options A-D键过滤 + content补全
- fix_answer_page_data.py: FIX6补全 + FIX7映射清理

### Phase 9: /random 端点去重 → complete
- 85%相似度过滤(SequentialMatcher)，48/50正确过滤2对重复

### Phase 10: 验证 → complete
- curl 50题: 0!=4选项, 0待补充, 0重复对, 12图片HTTP 200

## Verification
1. `curl /api/questions/random?count=50` → options全部4项A-D，0 placeholder
2. type_detail为正确UTF-8 "单选题"/"多选题"
3. 48/50返回(2对重复过滤)，post-API检查0残留重复
4. /static/questions/*.png → HTTP 200
5. 浏览器Ctrl+Shift+R → 多选徽章+图片渲染

## Errors Encountered
| Error | Resolution |
|-------|------------|
| _normalize_options未递归dict对象 | 增加isinstance(val, dict)分支 |
| DB修复FIX5返回0条 | 直接SQL更新选择题→单选题/多选题 |
| 管道编码杂音误导诊断 | 保存文件检查原始hex |
| _extract_options死代码导致选项重复 | 移除L620-626内层重扫描循环 |
| python-docx xpath不支持namespaces参数 | 移除参数，使用内置nsmap |
| 后端未重启导致dedup不生效 | 强杀所有Python进程后重启 |
