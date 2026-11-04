"""MinerU OCR 文本归一化回归（P4）。

事故：扫描件 OCR 输出 ASCII (一)/(二)，且题号会粘在上一行末尾
（...高1.79个百分点108.2023年... / ...下降55.46%。111.2021年...），
导致资料分析组边界与 108/111 两道题一起丢失。
本用例锁定 normalize_ocr_markdown 的最小行为，并验证归一化后 10 题 / 2 组 × 5 题。
"""
from app.services.text_parser import (
    extract_question_blocks_with_material_sets,
    normalize_ocr_markdown,
)

OCR_TEXT = """所给出的图、表、文字或综合性资料均有若干个问题要你回答。

(一)

2023年，我国制浆造纸及纸制品全行业完成纸浆、纸及纸板和纸制品产量合计29139万吨，同比增长2.63%。
2023年，全国纸及纸板消费量13165万吨，同比增长6.14%；人均年消费量93.37千克，同比增长6.30%。

106.2021年全国纸及纸板产量约为：
A.11715万吨
B.12105万吨
C.12762万吨
D.13227万吨
107.2022年全国纸及纸板消费量同比增速与产量同比增速相比约：
A.低4.58个百分点
B.低0.5个百分点
C.高5.37个百分点
D.高1.79个百分点108.2023年，造纸及纸板生产企业部分经济指标同比增速按从高到低排列，正确的是（）。A.成品存货、利润总额、资产、负债总额
B.成品存货、利润总额、负债总额、资产
C.利润总额、负债总额、资产、成品存货
D.利润总额、资产、负债总额、成品存货
109.2023年我国东部地区纸及纸板产量与中部地区相比约多：
A.4倍以上
B.3-4倍
C.2-3倍
D.1-2倍
110.能够从上述资料中推出的是：
A.2023年全国纸浆的产量超过10000万吨
B.2022年全国纸及纸板人均年消费量超过90千克
C.2023年纸及纸板产量超过100万吨的18个省（区、市）都不属于西部地区
D.2023年全国2567家造纸及纸板生产企业的营业收入不超过利润总额的30倍

(二)

2023年全国著作权（包括作品著作权、计算机软件著作权、著作权质权）登记总量达8923901件，同比增长40.46%。
2023年全国共完成作品著作权登记6428277件，同比增长42.30%，该比例比上年同期增加4.86个百分点。

2023年作品著作权质权登记涉及担保金额78384.32万元，同比下降55.46%。111.2021年全国著作权登记总量约为：
A.626万件
B.656万件
C.685万件
D.728万件
112.2022年美术作品、摄影作品、文字作品的著作权登记量共约：
A.369万件
B.389万件
C.409万件
D.429万件
113.以下折线图中，最能准确反映2023年登记量前五位的同比增长率情况的是：
A.
[IMAGE:1e56212e30044d97b043f566747699f1c2783fed43269b78190e753afa37a1a5_0_0]
B.
[IMAGE:160d9899edde8809941b1a8268ec1c178802f92a063c7acaf327932e9d8e44ae_0_0]
C.
[IMAGE:80217b9c63c89acb8ecc4c52bba84110862d32f405b0b0fd84654fd4557effdb_0_0]
D.
[IMAGE:ff2abdc69013976b8ea85a5912a86936aa447a456d7b37782d2a049b4b6b122a_0_0]
114.2023年平均每件计算机软件著作权质权登记涉及主债务金额比作品著作权质权登记高约：
A.1135万元
B.1056万元
C.967万元
D.825万元
115.不能从上述资料中推出的是：
A.2023年全国共完成计算机软件著作权登记2495213件
B.2023年全国作品著作权登记总量同比增量超过200万件
C.2023年计算机软件著作权质权登记在著作权质权登记中比重同比上升
D.2023年平均每件作品著作权质权登记涉及主债务金额同比下降
"""


def test_normalize_ascii_markers_and_glued_question_numbers():
    text = normalize_ocr_markdown(OCR_TEXT)
    assert '(一)' not in text and '(二)' not in text
    assert '（一）' in text and '（二）' in text
    assert '高1.79个百分点\n108. 2023年' in text
    assert '下降55.46%。\n111. 2021年' in text
    # 小数与百分数不能被当题号切开
    assert '人均年消费量93.37千克' in text
    assert '低4.58个百分点' in text


def test_normalized_ocr_keeps_ten_questions_and_two_five_question_groups():
    blocks = extract_question_blocks_with_material_sets(normalize_ocr_markdown(OCR_TEXT))
    numbers = [int(b['question_number']) for b in blocks if b.get('question_number')]
    assert numbers == list(range(106, 116)), numbers
    first = [b.get('material_text') or '' for b in blocks if 106 <= int(b['question_number']) <= 110]
    second = [b.get('material_text') or '' for b in blocks if 111 <= int(b['question_number']) <= 115]
    assert all(m and '纸及纸板' in m for m in first)
    assert all(m and '著作权' in m for m in second)
    assert len({m for m in first}) == 1
    assert len({m for m in second}) == 1


def test_normalize_is_idempotent():
    once = normalize_ocr_markdown(OCR_TEXT)
    assert normalize_ocr_markdown(once) == once
