# 学习计划 · 智能排课与能力画像（P1）单测
#
# 覆盖用户 2026-11-22 提的两点：
#   1) 智能排课不能"每人都一样/每天都一样"→ 现在按任务+画像+待复习错题生成，带 date/sig，任务变即重算；
#   4) 能力雷达与"我的"画像合一 → /plan/current 返回 capability（六维 + 分科正确率 breakdown）。
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.models import StudyGoal, UserProfile  # noqa: E402

TODAY = datetime.now().strftime("%Y-%m-%d")
TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def _profile(db, user_id, **fields):
    row = UserProfile(user_id=user_id, **fields)
    db.add(row)
    db.commit()
    return row


def _task(db, user_id, *, title, task_date, plan_id=1, sort=0, minutes=30, done=False,
          meta='{"summary":"测试方案","phases":[],"tips":""}'):
    db.add(
        StudyGoal(
            user_id=user_id,
            title=title,
            target_count=0,
            plan_id=plan_id,
            sort_order=sort,
            task_date=task_date,
            expected_minutes=minutes,
            is_completed=1 if done else 0,
            status=1,
            plan_meta=meta,
            deadline=datetime.now() + timedelta(days=60),
        )
    )
    db.commit()


def _current(client, headers):
    resp = client.get("/api/plan/current", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_schedule_built_from_today_tasks(db_session, test_user, client, auth_headers):
    _profile(db_session, test_user.user_id, daily_hours=4, self_level="有基础", target_score=210)
    _task(db_session, test_user.user_id, title="资料分析 20 题（增长率）", task_date=TODAY, sort=0, minutes=40)
    _task(db_session, test_user.user_id, title="判断推理 15 题", task_date=TODAY, sort=1, minutes=30)
    _task(db_session, test_user.user_id, title="申论大作文 1 篇", task_date=TODAY, sort=2, minutes=60)
    _task(db_session, test_user.user_id, title="明天的任务", task_date=TOMORROW, sort=3, minutes=30)

    data = _current(client, auth_headers)

    sched = data["schedule"]
    assert sched["date"] == TODAY
    assert sched["version"] == 1
    assert sched["budget_minutes"] == int(round(4 * 60 * 0.9))
    assert 0 < sched["planned_minutes"] <= sched["budget_minutes"]
    # 今天 3 条任务都进排课，明天的不进
    items = [i for p in sched["slots"] for i in p["items"] if i["kind"] == "task"]
    titles = {i["title"] for i in items}
    assert "资料分析 20 题（增长率）" in titles
    assert "明天的任务" not in titles
    # 科目归类与时段匹配：资料分析→行测→上午；申论→晚上
    by_title = {i["title"]: i for i in items}
    assert by_title["资料分析 20 题（增长率）"]["period"] == "morning"
    assert by_title["资料分析 20 题（增长率）"]["subject"] == "行测"
    assert by_title["申论大作文 1 篇"]["period"] == "evening"


def test_schedule_is_dynamic_per_user(db_session, test_user, test_teacher, client, auth_headers):
    # 同一账号：只有 1 条任务时，排课只应有对应项
    _profile(db_session, test_user.user_id, daily_hours=2)
    _task(db_session, test_user.user_id, title="言语理解 15 题", task_date=TODAY)
    first = _current(client, auth_headers)["schedule"]
    assert len(first["slots"]) >= 1

    # 再加一条任务 → 下次读取应重算（sig 变化）
    _task(db_session, test_user.user_id, title="公专 法律常识 20 题", task_date=TODAY, sort=1)
    second = _current(client, auth_headers)["schedule"]

    assert second["sig"] != first["sig"]
    assert second["planned_minutes"] >= first["planned_minutes"]


def test_toggle_recomputes_schedule(db_session, test_user, client, auth_headers):
    _profile(db_session, test_user.user_id, daily_hours=3)
    _task(db_session, test_user.user_id, title="数量关系 10 题", task_date=TODAY)
    data = _current(client, auth_headers)
    goal_id = data["tasks"][0]["goal_id"]

    resp = client.post(f"/api/plan/task/{goal_id}/toggle", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["schedule_recomputed"] is True

    after = _current(client, auth_headers)["schedule"]
    items = [i for p in after["slots"] for i in p["items"] if i["kind"] == "task"]
    assert items and items[0]["done"] is True


def test_capability_six_dims_and_breakdown(db_session, test_user, client, auth_headers):
    _profile(
        db_session,
        test_user.user_id,
        self_level="有基础",
        daily_hours=5,
        target_score=210,
        exam_date="2027-05-01",
        target_post="公安厅",
        subject_weaknesses='["资料分析","判断推理"]',
        self_intro="在职备考，晚上两小时",
    )
    _task(db_session, test_user.user_id, title="任务A", task_date=TODAY, done=True)
    _task(db_session, test_user.user_id, title="任务B", task_date=TOMORROW, sort=1)

    cap = _current(client, auth_headers)["capability"]

    assert [d["key"] for d in cap["dims"]] == ["level", "hours", "goal", "weak", "intro", "plan"]
    assert len(cap["dims"]) == 6
    assert cap["dims"][0]["value"] == 60                     # 有基础
    assert cap["dims"][1]["value"] == 50                     # 5h/10h
    assert cap["dims"][2]["value"] == 100                    # 分数+日期+岗位 全有
    assert cap["dims"][3]["value"] == 50                     # 2 个薄弱科目
    assert cap["dims"][5]["value"] == 50                     # 1/2 完成
    assert 0 <= cap["avg"] <= 100
    assert isinstance(cap["breakdown"], list)
    assert all("accuracy" in row for row in cap["breakdown"])


def test_no_profile_still_works_with_defaults(db_session, test_user, client, auth_headers):
    _task(db_session, test_user.user_id, title="常识判断 20 题", task_date=TODAY)

    data = _current(client, auth_headers)

    assert data["schedule"]["daily_hours"] == 3.0          # 无画像默认 3 小时
    assert data["schedule"]["budget_minutes"] == 162
    dims = {d["key"]: d for d in data["capability"]["dims"]}
    assert dims["hours"]["available"] is False
    assert dims["plan"]["available"] is True


def test_no_plan_unchanged(db_session, test_user, client, auth_headers):
    assert _current(client, auth_headers) == {"has_plan": False}


def test_today_endpoint_includes_schedule(db_session, test_user, client, auth_headers):
    _profile(db_session, test_user.user_id, daily_hours=3)
    _task(db_session, test_user.user_id, title="资料分析 10 题", task_date=TODAY)

    resp = client.get("/api/plan/today", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["schedule"] is not None
    assert body["schedule"]["date"] == TODAY
    assert body["total"] == 1


def test_health_reports_llm_configured(db_session, client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "llm_configured" in body and isinstance(body["llm_configured"], bool)
    assert "env_source" in body and isinstance(body["env_source"], str)
    assert "LLM_API_KEY" not in json.dumps(body)          # 不回显密钥名/值
