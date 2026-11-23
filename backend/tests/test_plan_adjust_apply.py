# 学习计划 · AI 调整落地（P2）单测
#
# 用户意见 5：AI 调整计划"只是发一句话"，回复后没有实际调整、也没有存档。
# 现在 /plan/adjust 要求 LLM 输出**受限指令**（add/move/modify/remove），服务端校验后事务应用，
# 存 diff 快照；同端点 body undo=true 可撤销最近一次（不新增路由）。/plan/current 返回最近 3 条记录。
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.models import StudyGoal  # noqa: E402
from app.services import llm_client  # noqa: E402

TODAY = datetime.now().strftime("%Y-%m-%d")
IN_3D = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
IN_5D = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")


def _seed_plan(db, user_id, *, count=2):
    rows = []
    for i in range(count):
        rows.append(
            StudyGoal(
                user_id=user_id,
                title=f"任务{i}",
                target_count=0,
                plan_id=1,
                sort_order=i,
                task_date=TODAY,
                expected_minutes=30,
                is_completed=0,
                status=1,
                plan_meta=json.dumps({"summary": "测试方案", "phases": [], "tips": ""}, ensure_ascii=False),
            )
        )
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def _fake_llm(monkeypatch, payload: dict):
    async def _chat_plan(_prompt: str) -> str:
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(llm_client, "chat_plan", _chat_plan)


def _adjust(client, headers, instruction="多留时间给公专", **extra):
    body = {"instruction": instruction, **extra}
    resp = client.post("/api/plan/adjust", json=body, headers=headers)
    return resp


def test_adjust_applies_structured_ops(db_session, test_user, client, auth_headers, monkeypatch):
    tasks = _seed_plan(db_session, test_user.user_id, count=2)
    g1, g2 = tasks[0].goal_id, tasks[1].goal_id
    _fake_llm(
        monkeypatch,
        {
            "summary": "调整为公专优先",
            "ops": [
                {"op": "add", "title": "公专法律常识 20 题", "date": IN_3D, "minutes": 45},
                {"op": "move", "goal_id": g1, "to": IN_5D},
                {"op": "modify", "goal_id": g2, "minutes": 50},
                {"op": "remove", "goal_id": g2},
            ],
        },
    )

    resp = _adjust(client, auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied_count"] == 4
    assert body["rejected"] == []
    assert body["schedule_recomputed"] is True

    db_session.expire_all()
    g1_row = db_session.get(StudyGoal, g1)
    g2_row = db_session.get(StudyGoal, g2)
    assert g1_row.task_date == IN_5D
    assert int(g2_row.expected_minutes) == 50
    assert g2_row.status == 0                       # remove 用软删
    added = (
        db_session.query(StudyGoal)
        .filter(StudyGoal.user_id == test_user.user_id, StudyGoal.title == "公专法律常识 20 题")
        .first()
    )
    assert added is not None and added.task_date == IN_3D


def test_invalid_ops_are_rejected(db_session, test_user, client, auth_headers, monkeypatch):
    tasks = _seed_plan(db_session, test_user.user_id, count=1)
    other = StudyGoal(user_id=99999, title="别人的任务", target_count=0, plan_id=1, status=1)
    db_session.add(other)
    db_session.commit()

    _fake_llm(
        monkeypatch,
        {
            "summary": "x",
            "ops": [
                {"op": "move", "goal_id": other.goal_id, "to": IN_3D},   # 不属于本用户/计划
                {"op": "add", "title": "", "date": "bad-date", "minutes": 30},
                {"op": "explode"},                                        # 未知指令
                {"op": "modify", "goal_id": tasks[0].goal_id, "minutes": 0},
            ],
        },
    )

    body = _adjust(client, auth_headers).json()

    assert body["applied_count"] == 0
    assert len(body["rejected"]) == 4
    assert body["message"].startswith("AI 只给了建议")


def test_undo_reverts_last_adjustment(db_session, test_user, client, auth_headers, monkeypatch):
    tasks = _seed_plan(db_session, test_user.user_id, count=2)
    g1, g2 = tasks[0].goal_id, tasks[1].goal_id
    _fake_llm(
        monkeypatch,
        {
            "summary": "调整",
            "ops": [
                {"op": "add", "title": "新增任务", "date": IN_3D, "minutes": 20},
                {"op": "move", "goal_id": g1, "to": IN_5D},
                {"op": "modify", "goal_id": g2, "minutes": 60},
                {"op": "remove", "goal_id": g2},
            ],
        },
    )
    assert _adjust(client, auth_headers).json()["applied_count"] == 4

    undo = client.post("/api/plan/adjust", json={"instruction": "", "undo": True}, headers=auth_headers)
    assert undo.status_code == 200, undo.text
    body = undo.json()
    assert body["reverted_count"] == 4
    assert body["undoable"] is False

    db_session.expire_all()
    assert db_session.get(StudyGoal, g1).task_date == TODAY
    g2_row = db_session.get(StudyGoal, g2)
    assert int(g2_row.expected_minutes) == 30
    assert g2_row.status == 1
    added = (
        db_session.query(StudyGoal)
        .filter(StudyGoal.user_id == test_user.user_id, StudyGoal.title == "新增任务")
        .first()
    )
    assert added.status == 0


def test_recent_adjustments_visible_after_reload(db_session, test_user, client, auth_headers, monkeypatch):
    _seed_plan(db_session, test_user.user_id, count=1)
    _fake_llm(monkeypatch, {"summary": "调整后", "ops": [{"op": "add", "title": "T", "date": IN_3D, "minutes": 15}]})
    _adjust(client, auth_headers)

    data = client.get("/api/plan/current", headers=auth_headers).json()

    assert isinstance(data["recent_adjustments"], list) and data["recent_adjustments"]
    latest = data["recent_adjustments"][0]
    assert latest["applied"] is True
    assert latest["change_count"] == 1
    assert latest["reason"]


def test_empty_instruction_without_undo_is_400(db_session, test_user, client, auth_headers):
    _seed_plan(db_session, test_user.user_id, count=1)
    resp = client.post("/api/plan/adjust", json={"instruction": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_llm_failure_returns_503(db_session, test_user, client, auth_headers, monkeypatch):
    _seed_plan(db_session, test_user.user_id, count=1)

    async def _boom(_prompt: str) -> str:
        raise llm_client.LLMClientError("no key")

    monkeypatch.setattr(llm_client, "chat_plan", _boom)
    assert _adjust(client, auth_headers).status_code == 503
