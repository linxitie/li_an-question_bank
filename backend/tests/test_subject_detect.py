# -*- coding: utf-8 -*-
"""S2 回归：科目识别器（口径 Q-57 c：标题优先、弱特征严格、不确定返回 None）。"""
from app.core.subject_detect import detect_subject, score_text, title_scores


def test_shenlun_card_from_title():
    assert detect_subject("申论分论点一般写几个？", "两到三个，并列递进") == "shenlun"


def test_xingce_card_from_title():
    assert detect_subject("图形推理先看什么？", "先看数量再看位置") == "xingce"


def test_gongzhuan_card_from_title():
    assert detect_subject("治安管理处罚的种类有哪几类？", "警告罚款拘留吊销") == "gongzhuan"


def test_body_only_needs_two_hits():
    assert detect_subject("速算三招", "资料分析用首数法、特征数字法") == "xingce"


def test_body_single_hit_is_none():
    assert detect_subject("速算三招", "资料分析很简单") is None


def test_unknown_text_returns_none():
    assert detect_subject("今天天气不错", "适合出门散步") is None


def test_empty_returns_none():
    assert detect_subject("", "") is None


def test_title_beats_body_conflict():
    # 标题命中申论 → 直接判申论，正文有公专词也不改判
    assert detect_subject("申论怎么写", "公安机关执法") == "shenlun"


def test_title_tie_returns_none():
    # 标题同时出现申论与行测特征词且并列 → 不猜
    assert detect_subject("申论与行测", "") is None


def test_close_body_scores_return_none():
    # 正文申论与公专各命中 1 次（本就不足 2 分）
    assert detect_subject("随便写写", "申论 治安") is None


def test_score_text_shape():
    s = score_text("申论", "公专")
    assert set(s) == {"shenlun", "xingce", "gongzhuan"}
    assert s["shenlun"] >= 2 and s["gongzhuan"] >= 1


def test_title_scores_only_title():
    ts = title_scores("图形推理")
    assert ts["xingce"] == 1 and ts["shenlun"] == 0 and ts["gongzhuan"] == 0
