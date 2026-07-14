# Findings — 答题卡修复

## 根因1: 嵌套JSON对象
DB options value是真正的JSON对象 `{"key":"A","value":{"key":"A","value":"..."}}`，非字符串。`isinstance(val, dict)` 分支解决。

## 根因2: question_type_detail 编码
SQLite hex正确(E5 8D 95 = "单")，但JSON序列化管道产生杂音。直接SQL修复430条+"单选题/多选题"ENUM扩展+API fallback检测。

## 根因3: DOCX导入全链路
- 图片提取：需遍历run查找drawing。最终方案：`para._p.iterdescendants('{DML}blip')` + `r:embed` → `doc.part.rels`
- "0题"：后端对DOCX返回total_questions:0。修复：upload_file_for_import使用extract_question_blocks

## 根因4: _extract_options 死代码
L620-626内层循环无条件重扫描全部行 → 选项大量重复。移除后100/100干净。

## 根因5: /random 无去重
50题中出现2对相似>85%的重复。增加SequentialMatcher过滤，48/50正确过滤。

## 根因6: python-docx xpath
BaseOxmlElement.xpath()不支持namespaces参数。使用python-docx内置nsmap + iterdescendants替代。

## 数据修复统计
- 676题嵌套value解码
- 430题类型修正(395单选+35多选)
- 16题嵌入选项标记清理
- 12+2题>4选项去重
