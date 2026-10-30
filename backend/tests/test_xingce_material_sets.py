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


# 2026-10-28 实测事故：2025 安徽行测资料三的标记行是
# “（三） [IMAGE:7900c602_115_0] [IMAGE:7900c602_115_1]”，图片与标记同行。
# 旧正则只认独占一行的标记 → 资料三漏检 → 资料二区间被撑到 10 题，
# 触发 [2,6] 保护而整组跳过，结果资料二、资料三都没有材料。
PAPER_WITH_IMAGE_MATERIAL = """第五部分 资料分析

（二）
2023年，全国著作权登记总量同比增长显著，其中作品著作权登记量占比最高；
计算机软件著作权登记量保持两位数增长。

111. 2023年全国著作权登记总量同比增速约为（ ）
A. 5%
B. 10%
C. 15%
D. 20%

112. 2023年作品著作权登记量占比约为（ ）
A. 40%
B. 50%
C. 60%
D. 70%

113. 2023年计算机软件著作权登记量同比增速约为（ ）
A. 5%
B. 10%
C. 15%
D. 20%

114. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

115. 下列说法错误的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

（三） [IMAGE:7900c602_115_0] [IMAGE:7900c602_115_1]

116. 根据资料三，下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

117. 根据资料三，下列说法错误的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

118. 根据资料三，下列数值最大的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

119. 根据资料三，下列数值最小的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁

120. 根据资料三，可以推出的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
"""


def test_image_only_material_marker_does_not_swallow_next_set():
    """图片材料标记必须被识别，且不能把资料二撑成 10 题。"""
    blocks = extract_question_blocks_with_material_sets(PAPER_WITH_IMAGE_MATERIAL)
    groups = _material_groups(blocks)
    assert sorted(len(v) for v in groups.values()) == [5, 5], groups
    image_mats = [m for m in groups if '[IMAGE:' in m]
    assert len(image_mats) == 1
    assert '7900c602_115_0' in image_mats[0]
    assert '7900c602_115_1' in image_mats[0]
    assert all(n and 111 <= n <= 120 for members in groups.values() for n in members)


# 2026-10-29 实测事故：2021 北京乡镇卷资料分析第一/二组的标记行分别是
# “（一） [IMAGE:04108529_110_0]”“（二） [IMAGE:04108529_115_1]”，
# 每组只有一张图（token 长度 < 30）→ 旧规则按“材料过短”跳过整组，
# q111–115 / q116–120 两道复合题组在库中完全没有材料。
PAPER_WITH_SINGLE_IMAGE_MATERIAL = """第五部分 资料分析

（一） [IMAGE:04108529_110_0]

111. 2014年该地区私有云市场规模和公有云市场规模之比最接近以下哪一项？
A. 1：4
B. 4：1
C. 1：3
D. 3：1

112. 根据预测，2021年该地区云计算整体市场规模最接近以下哪个数字？
A. 1300亿元
B. 1700亿元
C. 2300亿元
D. 2900亿元

113. 2014-2022年间该地区公有云市场规模同比增速超过 10% 的年份有几个？
A. 6
B. 5
C. 4
D. 3

114. 根据预测，2022年该地区云计算市场整体规模同比增长：
A. 甲
B. 乙
C. 丙
D. 丁

115. 根据材料中所给数据和预测，能够从上述资料中推出的是：
A. 甲
B. 乙
C. 丙
D. 丁
"""


def test_single_image_only_material_is_not_dropped_by_length_guard():
    """单张图片材料（token < 30 字）也必须挂满整组，而不是整组留空。"""
    blocks = extract_question_blocks_with_material_sets(PAPER_WITH_SINGLE_IMAGE_MATERIAL)
    groups = _material_groups(blocks)
    assert len(groups) == 1, groups
    (material, members), = groups.items()
    assert '[IMAGE:04108529_110_0]' in material
    assert sorted(members) == [111, 112, 113, 114, 115]
