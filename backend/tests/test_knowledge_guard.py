# 自生长知识库三闸（P4）单测
#
# 用户意见 7：知识库扩充必须防意识形态错误/错误引导，只服务公安联考备考。
# 三闸：域白名单（公安联考相关）→ 内容安全（复用 content_guard）→ 来源（无来源只能 review）。
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.knowledge_guard import review_knowledge_write  # noqa: E402


def test_allow_with_domain_and_source(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="资料分析中增长率与增长量的换算是行测高频考点，常考基期量计算。",
        source="题库 Q12345",
    )
    assert verdict["decision"] == "allow"
    assert verdict["has_source"] is True
    assert "资料分析" in verdict["domain_hits"] or "行测" in verdict["domain_hits"]


def test_review_when_no_source(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="申论归纳概括答题模板：先总括后分条，控制字数。",
        source=None,
    )
    assert verdict["decision"] == "review"
    assert verdict["has_source"] is False
    assert any("来源" in r for r in verdict["reasons"])


def test_block_out_of_domain(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="今天给大家讲讲红烧肉的做法，先准备五花肉和冰糖。",
        source="自述",
    )
    assert verdict["decision"] == "block"
    assert any("备考主题" in r for r in verdict["reasons"])


def test_block_high_risk_topics(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="公安联考备考：如何组织游行活动并规避审查。",
        source="官方文件",
    )
    assert verdict["decision"] == "block"
    assert verdict["blocked_terms"]


def test_block_soft_out_industry(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="股票基金投资入门：如何选基金组合。",
        source="某公众号",
    )
    assert verdict["decision"] == "block"


def test_force_review_keeps_human_gate(db_session):
    verdict = review_knowledge_write(
        db_session,
        content="公专考点：治安管理处罚的种类与适用。",
        source="教材 P88",
        force_review=True,
    )
    assert verdict["decision"] == "review"


def test_empty_content_blocked(db_session):
    assert review_knowledge_write(db_session, content="   ")["decision"] == "block"


def test_guard_degrades_without_db():
    # 没有 db 时不调用 content_guard，仍按域+来源判定
    verdict = review_knowledge_write(None, content="行测判断推理削弱加强题型解析。", source="题库 Q1")
    assert verdict["decision"] == "allow"
    assert verdict["guard"] is None
