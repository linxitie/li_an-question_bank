# 历史数据统一修复

## 真实数据结论（SQLite ./data/question_bank.db，status=1，793 道）

| 指标 | 数值 |
|---|---|
| answer_analysis 为空 | 234（其中 232 道为公专 subject_id=3、来源为空、题干无内嵌解析） |
| question_type 表行数 | 仅 5 行（单选×3、多选×1、论述×1），写作题无行 |
| question_bank.type_id 错位 | 122 道（97 道选择题指到论述、25 道多选指到单选） |
| 真实多选（答案含≥2个A-D字母） | 127 道，其中 31 道标单选、1 道标论述 |
| 答案="待补充" | 99 道（人工补全，无法自动恢复） |

## 修复脚本

`backend/scripts/repair_question_types.py`（幂等，可重复运行）：

```
python scripts/repair_question_types.py --dry-run   # 预览（默认）
python scripts/repair_question_types.py --apply     # 实际写入
```

对每题执行：`_detect_question_type` 重检测 + `canonical_answer` 归一化，并同时修正：
1. `question_bank.type_id`（经 `_get_or_create_type` 解析到正确题型行）
2. `question_detail_category.question_type_detail`
3. 选择题答案归一化入库（"待补充"占位符保留）

## dry-run 结果（验证通过）

```
题目总数         : 791
type_id 修正      : 159
detail 修正       : 38
答案归一化        : 0     ← 答案已由历史脚本归一化，无需再改
待补充答案(人工)  : 99

题型分布（修复前 → 修复后）:
  单选题         :  619 →  622
  多选题         :   73 →  163   ← 核心修复：90 道多选被重新识别
  论述题         :   99 →    6   ← 97 道误判论述被纠正
```

## 注意事项

- **232 道公专空解析**：入库时源数据即无解析，库内不可恢复；需用修复后的导入管线从公专原始素材（含解析列）重新导入补解析，靠去重逻辑更新既有题目。
- **99 道"待补充"答案**：需人工补全。
- **已废弃脚本**：`scripts/fix_question_types.py`、`scripts/migrate_question_types.py`、`scripts/normalize_question_types.py` 各自内嵌了旧版检测逻辑，已由本脚本 + text_parser 统一函数取代；后续不再维护旧脚本的检测逻辑。
- 修复后建议用 sqlite3 只读查询复核 cross-tab（bank_type vs detail_type）一致、"真实多选被标单选"归零。
