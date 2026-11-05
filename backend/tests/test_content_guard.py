"""敏感词自生长知识库：引擎 / 判定 / 提案 / 红队 / Obsidian / API 回归测试。"""
import json
from datetime import datetime

import pytest

from app.api.v1.community import forum
from app.models.content_guard import (
    CgAuditEvent,
    CgCase,
    CgEdge,
    CgJudgment,
    CgProposal,
    CgTask,
    CgTerm,
    CgVariant,
)
from app.services.content_guard import (
    audit,
    engine,
    graph,
    guard_text,
    judgments,
    normalizer,
    obsidian,
    proposals,
    reconcile,
    redteam,
    seed_defaults,
    stats,
)


@pytest.fixture
def seeded(db_session):
    report = seed_defaults(db_session)
    db_session.commit()
    return report


def test_seed_is_idempotent(seeded, db_session):
    assert seeded["policies"] > 0
    assert seeded["terms"] > 0
    first = db_session.query(CgTerm).count()
    again = seed_defaults(db_session)
    db_session.commit()
    assert again["terms"] == 0
    assert db_session.query(CgTerm).count() == first
    assert db_session.query(CgEdge).count() > 0


def test_engine_detects_three_levels(seeded, db_session):
    blocked = guard_text(db_session, "有人在这里赌博", scene="test")
    masked = guard_text(db_session, "你这个傻逼", scene="test")
    reviewed = guard_text(db_session, "求代考包过", scene="test")
    db_session.commit()

    assert blocked["level"] == "blocked"
    assert blocked["decision"] == "block"
    assert masked["level"] == "masked"
    assert masked["decision"] in ("mask", "review")
    assert reviewed["decision"] == "review"
    assert blocked["evidence"][1]["step"] == "dfa_match"


def test_evasion_is_normalized_and_masked(seeded, db_session):
    text = "傻.逼 全角傻逼 零宽傻\u200b逼"
    result = guard_text(db_session, text, scene="test")
    db_session.commit()

    assert result["has_sensitive"] is True
    assert "傻逼" in result["words"]
    assert result["masked_text"].count("*") >= len("傻逼") * 3
    assert "." in result["masked_text"]
    # 脱敏摘要不落原文
    assert "*" in result["snippet"]


def test_judgment_and_task_persisted(seeded, db_session):
    before = db_session.query(CgJudgment).count()
    result = guard_text(
        db_session, "赌博网站", scene="forum_post", source_id=9, user_id=3
    )
    db_session.commit()

    assert result["judgment_id"]
    assert result["task_id"]
    assert db_session.query(CgJudgment).count() == before + 1
    task = db_session.query(CgTask).filter(CgTask.task_id == result["task_id"]).first()
    assert task.state == "auto_blocked"
    judgment = db_session.query(CgJudgment).filter(
        CgJudgment.judgment_id == result["judgment_id"]
    ).first()
    assert judgment.content_hash
    assert "赌博" not in judgment.content_snippet
    assert judgment.evidence[-1]["decision"] == "block"
    term = db_session.query(CgTerm).filter(CgTerm.term == "赌博").first()
    assert term.hit_count >= 1
    assert term.block_count >= 1
    daily = stats.overview(db_session)
    assert daily["today"]["total"] >= 1


def test_graph_neighbors(seeded, db_session):
    term = db_session.query(CgTerm).filter(CgTerm.term == "赌博").first()
    data = graph.neighbors(db_session, "term", str(term.term_id), depth=1)
    types = {node["type"] for node in data["nodes"]}
    assert "term" in types
    assert "policy" in types or "category" in types
    assert data["edges"]


def test_false_positive_learning_creates_proposal(seeded, db_session):
    for _ in range(3):
        result = guard_text(db_session, "傻逼", scene="test", persist=True)
        db_session.commit()
        assert result["judgment_id"]
        judgments.override_judgment(
            db_session,
            result["judgment_id"],
            action="reject",
            reviewer_id=1,
            reason="语境是引用",
        )
        db_session.commit()

    term = db_session.query(CgTerm).filter(CgTerm.term == "傻逼").first()
    assert term.false_positive_count >= 3
    assert term.confidence < 0.8
    pending = (
        db_session.query(CgProposal)
        .filter(CgProposal.status == "pending", CgProposal.proposer == "active_learning")
        .count()
    )
    assert pending >= 1
    assert db_session.query(CgCase).filter(CgCase.verdict == "false_positive").count() >= 1


def test_proposal_approve_adds_variant_to_engine(seeded, db_session):
    term = db_session.query(CgTerm).filter(CgTerm.term == "赌博").first()
    variant_text = "赌\u200b博"
    bypass = "这里可以" + variant_text
    assert guard_text(db_session, bypass, scene="test")["has_sensitive"] is True
    # 人为构造一个原词库不认识的同音变体
    proposal = proposals.create_proposal(
        db_session,
        kind="add_variant",
        title="新增同音变体",
        payload={"term_id": term.term_id, "variant": "堵博", "kind": "homophone"},
        proposer="human",
        dedupe_key=f"test:add_variant:{term.term_id}",
    )
    db_session.commit()
    assert guard_text(db_session, "堵博", scene="test")["has_sensitive"] is False
    proposals.approve_proposal(db_session, proposal.proposal_id, reviewer_id=1, note="ok")
    db_session.commit()
    engine.reset_engine()
    result = guard_text(db_session, "堵博", scene="test")
    assert result["has_sensitive"] is True
    assert result["level"] == "blocked"
    assert audit.verify_chain(db_session)["ok"] is True


def test_redteam_generates_samples_and_proposals(seeded, db_session):
    report = redteam.run(db_session, limit=20)
    db_session.commit()
    assert report["generated"] > 0
    assert report["detected"] + report["undetected"] == report["generated"]
    assert report["samples"]
    if report["undetected"]:
        assert report["proposals"]
        payload = (
            db_session.query(CgProposal)
            .filter(CgProposal.proposal_id == report["proposals"][0])
            .first()
            .payload
        )
        assert payload["term_id"]


def test_obsidian_export_and_review_import(seeded, db_session, tmp_path):
    vault = tmp_path / "vault"
    result = guard_text(db_session, "求代考", scene="test")
    db_session.commit()
    assert result["task_id"]

    first = obsidian.export_all(db_session, vault)
    assert first["ok"] is True
    assert (vault / "README.md").is_file()
    assert (vault / "04-图谱" / "全景.md").is_file()
    assert list((vault / "01-词条").glob("*.md"))
    assert list((vault / "00-待审队列" / "判定").glob("*.md"))

    second = obsidian.export_all(db_session, vault)
    # 概览页含生成时间，跨秒重导可能重写 1 个文件；其余投影必须全部命中清单
    assert second["written"] <= 1
    assert second["skipped"] >= first["written"] - 1

    task_file = next((vault / "00-待审队列" / "判定").glob("*.md"))
    content = task_file.read_text(encoding="utf-8")
    task_file.write_text(content.replace("- [ ] 确认违规", "- [x] 确认违规"), encoding="utf-8")
    report = obsidian.import_reviews(db_session, vault, reviewer_id=1)
    assert report["ok"] is True
    assert report["processed"] == 1
    judgment = db_session.query(CgJudgment).filter(
        CgJudgment.judgment_id == result["judgment_id"]
    ).first()
    assert judgment.human_override == "confirm"
    assert not task_file.exists()


def test_obsidian_proposal_import(seeded, db_session, tmp_path):
    vault = tmp_path / "vault"
    term = db_session.query(CgTerm).filter(CgTerm.term == "赌博").first()
    proposal = proposals.create_proposal(
        db_session,
        kind="update_level",
        title="降级为研判",
        payload={"term_id": term.term_id, "level": "reviewed"},
        proposer="human",
        dedupe_key="obsidian:update_level:1",
    )
    db_session.commit()
    obsidian.export_all(db_session, vault)
    file = vault / "00-待审队列" / "提案" / f"proposal-{proposal.proposal_id}.md"
    assert file.is_file()
    file.write_text(
        file.read_text(encoding="utf-8").replace("- [ ] 通过", "- [x] 通过"),
        encoding="utf-8",
    )
    report = obsidian.import_reviews(db_session, vault, reviewer_id=1)
    assert report["processed"] == 1
    db_session.expire_all()
    assert db_session.query(CgTerm).filter(CgTerm.term_id == term.term_id).first().level == "reviewed"
    assert audit.verify_chain(db_session)["ok"] is True


def test_reconcile_flags_term_without_policy(seeded, db_session):
    db_session.add(
        CgTerm(
            term="孤立词",
            normalized="孤立词",
            level="reviewed",
            category="other",
            status="active",
        )
    )
    db_session.commit()
    report = reconcile.run(db_session, vault=None)
    db_session.commit()
    codes = {item["code"] for item in report["issues"]}
    assert "term_without_policy" in codes
    assert report["proposals"]


def test_api_permissions_and_terms(client, seeded, admin_headers, auth_headers):
    forbidden = client.get("/api/v1/admin/content-guard/overview", headers=auth_headers)
    assert forbidden.status_code == 403

    overview = client.get(
        "/api/v1/admin/content-guard/overview", headers=admin_headers
    )
    assert overview.status_code == 200
    assert overview.json()["terms"]["total"] > 0

    created = client.post(
        "/api/v1/admin/content-guard/terms",
        headers=admin_headers,
        json={"term": "测试违禁词", "level": "masked", "category": "abuse", "confidence": 0.8},
    )
    assert created.status_code == 200
    term_id = created.json()["term_id"]

    duplicate = client.post(
        "/api/v1/admin/content-guard/terms",
        headers=admin_headers,
        json={"term": "测试违禁词", "level": "masked"},
    )
    assert duplicate.status_code == 409

    detected = client.post(
        "/api/v1/admin/content-guard/detect",
        headers=admin_headers,
        json={"text": "这里有测试违禁词", "persist": False},
    )
    assert detected.status_code == 200
    assert detected.json()["has_sensitive"] is True
    assert detected.json()["judgment_id"] is None

    variants = client.post(
        f"/api/v1/admin/content-guard/terms/{term_id}/variants",
        headers=admin_headers,
        json={"variant": "测试违禁辞", "kind": "homophone"},
    )
    assert variants.status_code == 200


def test_api_judgment_override_and_audit(client, seeded, admin_headers, db_session):
    result = guard_text(db_session, "求代考", scene="test")
    db_session.commit()
    verdict = client.post(
        f"/api/v1/admin/content-guard/judgments/{result['judgment_id']}/override",
        headers=admin_headers,
        json={"action": "confirm", "reason": "人工确认"},
    )
    assert verdict.status_code == 200
    assert verdict.json()["judgment_id"] == result["judgment_id"]

    chain = client.get(
        "/api/v1/admin/content-guard/audit/verify", headers=admin_headers
    )
    assert chain.status_code == 200
    assert chain.json()["ok"] is True


def test_console_page_served(client):
    response = client.get("/api/v1/admin/content-guard/console")
    assert response.status_code == 200
    assert "敏感词治理工作台" in response.text
    assert "/api/v1/admin/content-guard" in response.text


def test_forum_masks_and_binds_source(client, seeded, auth_headers, db_session):
    response = client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={"title": "测试", "content": "你这个傻逼"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "*" in body["content"]
    post_id = body.get("post_id") or body.get("id")
    db_session.expire_all()
    judgment = (
        db_session.query(CgJudgment).order_by(CgJudgment.judgment_id.desc()).first()
    )
    assert judgment.decision in ("mask", "review")
    assert judgment.source_id == post_id


def test_forum_post_is_blocked_and_recorded(client, seeded, auth_headers, db_session):
    before = db_session.query(CgJudgment).count()
    response = client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={"title": "测试", "content": "这里有赌博信息"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SENSITIVE_CONTENT_BLOCKED"
    db_session.expire_all()
    assert db_session.query(CgJudgment).count() == before + 1
    judgment = (
        db_session.query(CgJudgment).order_by(CgJudgment.judgment_id.desc()).first()
    )
    assert judgment.scene == "forum_post"
    assert judgment.decision == "block"
