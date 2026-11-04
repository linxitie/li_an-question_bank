# -*- coding: utf-8 -*-
"""去重必须比较选项：行测资料分析多题共用同一句设问。"""
from app.services.text_parser import _options_conflict, _options_fingerprint


def test_options_conflict_detects_different_choices():
    left = [
        {'key': 'A', 'value': '2022 年下半年首次募资总额低于上半年'},
        {'key': 'B', 'value': '2022 年下半年平均每家首次募资约 10.7 亿元'},
    ]
    right = [
        {'key': 'A', 'value': '2023 年全国纸及纸板产量超过 10000 万吨'},
        {'key': 'B', 'value': '2022 年全国纸及纸板人均消费量超过 90 千克'},
    ]
    assert _options_conflict(left, right) is True


def test_options_conflict_allows_same_choices():
    options = [
        {'key': 'A', 'value': '甲'},
        {'key': 'B', 'value': '乙'},
    ]
    assert _options_conflict(options, list(options)) is False


def test_options_fingerprint_ignores_labels_and_json_wrapper():
    raw = '[{"key": "A", "value": "甲"}, {"key": "B", "value": "乙"}]'
    assert _options_fingerprint(raw) == {'甲', '乙'}
