"""行测资料分析「材料–小题」绑定回归。

事故：解析器只在每组材料的第一题挂 material_text，其余小题 material 为空，
入库后 group_id=0，前端每题单看 → 材料与小题断裂。
本组用例锁定 `extract_question_blocks_with_material_sets` 的边界行为：
  - 不新增/丢失题块（幻影题块会让题号错位）
  - 段内 2~6 道小题共享同一份材料
  - 段外题目绝不被挂材料
"""
from app.services.text_parser import (
    extract_question_blocks,
    extract_question_blocks_with_material_sets,
)

PAPER = """第一部分 常识判断

1. 常识题一的正确选项是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

2. 常识题二的正确选项是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

第五部分 资料分析

（一）
2022年，全国城镇居民人均可支配收入49283元，比上年名义增长3.9%，扣除价格因素实际增长2.9%；
农村居民人均可支配收入20133元，增长4.2%。城乡居民收入比继续缩小。

106. 截至2022年末，城镇居民人均可支配收入约为农村居民的多少倍（ ）
A. 2.0
B. 2.4
C. 2.8
D. 3.2

107. 2022年农村居民收入实际增速约为（ ）
A. 2.9%
B. 3.9%
C. 4.2%
D. 4.6%

（二）
2023年，某省粮食总产量达到创纪录的800亿斤，比上年增加10亿斤，增长1.3%；
其中夏粮产量300亿斤，秋粮产量500亿斤。

108. 2023年该省粮食总产量同比增加约（ ）
A. 5亿斤
B. 10亿斤
C. 15亿斤
D. 20亿斤

109. 2023年该省秋粮产量占粮食总产量的比重约为（ ）
A. 37.5%
B. 50.0%
C. 62.5%
D. 75.0%
"""


def _material_groups(blocks):
    groups = {}
    for b in blocks:
        mat = (b.get('material_text') or '').strip()
        if mat:
            groups.setdefault(mat, []).append(b.get('question_number'))
    return groups


def test_blocks_count_unchanged():
    base = extract_question_blocks(PAPER)
    bound = extract_question_blocks_with_material_sets(PAPER)
    assert len(base) == len(bound)
    assert [b.get('question_number') for b in base] == [b.get('question_number') for b in bound]


def test_material_bound_to_whole_set():
    blocks = extract_question_blocks_with_material_sets(PAPER)
    groups = _material_groups(blocks)
    assert len(groups) == 2
    assert sorted(len(v) for v in groups.values()) == [2, 2]


def test_questions_before_material_section_stay_clean():
    blocks = extract_question_blocks_with_material_sets(PAPER)
    for b in blocks:
        if b.get('question_number') in (1, 2):
            assert not (b.get('material_text') or '').strip()


def test_materials_are_distinct_per_set():
    blocks = extract_question_blocks_with_material_sets(PAPER)
    groups = _material_groups(blocks)
    texts = list(groups.keys())
    assert '城镇居民' in texts[0]
    assert '粮食总产量' in texts[1]
