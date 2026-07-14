# Findings — 答题卡修复

## 根因1: 嵌套JSON对象（非字符串）
**发现**: DB中options列的value字段是真正的JSON对象 `{"key":"A","value":{"key":"A","value":"...文本..."}}`，不是字符串 `"{'key':'A',...}"`。
**影响**: `_normalize_options` 只检测 `isinstance(val, str)` 的dict字符串格式，漏掉了 `isinstance(val, dict)` 的直接对象格式。
**修复**: 在 `_extract()` 增加 `if isinstance(val, dict): return _extract(val, depth+1)` 分支。

## 根因2: question_type_detail 编码杂音
**发现**: SQLite直接查询hex正确（`E5 8D 95 E9 80 89 E9 A2 98` = "单选题"），但FastAPI JSON序列化后通过管道读取出现乱码。原始JSON字节实际正确。
**影响**: 前端 `typeMap` 的key匹配可能失败。
**修复**: (a) ENUM扩展 (b) API fallback检测 (c) 前端answer.length启发式 (d) 直接修复DB全部430条

## 根因3: DOCX导入全链路问题
**发现**: (a) 图片提取：`_extract_text_from_docx` 从paragraph直接`findall` drawings，但图片在run内部（`<w:r><w:drawing>`）(b) "0题"：后端对DOCX返回 `total_questions: 0`，前端自行解析不稳定
**修复**: (a) 遍历 `child.findall('.//{WML}r')` 再查找drawing (b) 使用 `extract_question_blocks` 后端解析

## 根因4: question_detail_category ENUM不含"单选题"/"多选题"
**发现**: models.py ENUM只有"选择题"等7项，无"单选题""多选题"。导入代码默认 '选择题'。
**修复**: ENUM增加"单选题""多选题""不定项"。

## 数据修复统计
- 676题嵌套value解码
- 430题类型修正（395单选 + 35多选）
- 2题 >4选项去重
