# -*- coding: utf-8 -*-
"""D5-b（2026-11-16）：`exam_record` 4 个评分字段的启动自愈 + 口径 A 回填。

为什么要这组用例：`exam_record` 是本批唯一没有启动自愈分支的核心表，
`create_all` 只建表不补列 → 老库一查考试就 `no such column: exam_record.is_scored`（实测）。
补列还不够：4 列默认值都是 0，不回填的话老库"已交卷"的记录会被读成"未评分"
（`agent_router` 用 `ExamRecord.is_scored == 1` 做统计会漏）。

用例直接造一个**本批之前**的库（无这 4 列、明细表叫 `exam_answer_detail`），
跑真正的 `app.main._ensure_exam_record_scoring_columns`，断言：

1. 4 列都补上，且 `DEFAULT 0`；
2. 回填结果符合口径 A（已交卷且无 `is_correct IS NULL` → 1；有待评 → 0；未交卷 → 0）；
3. 派生字段按明细算（已答=student_answer 非空、分母=明细条数）；
4. 第二次调用返回空列表、数值不变（幂等）。
"""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.main import _ensure_exam_record_scoring_columns

FOUR = ("is_scored", "manual_pending_count", "answered_count", "question_total")


def _old_db(path) -> None:
    """本批之前的 schema：exam_record 无 4 列，exam_answer_detail 只有回填需要的列。"""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text(
            """CREATE TABLE exam_record (
                   record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   paper_id INTEGER,
                   is_completed INTEGER DEFAULT 0,
                   total_score NUMERIC(10, 2) DEFAULT 0
               )"""
        ))
        conn.execute(text(
            """CREATE TABLE exam_answer_detail (
                   detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   record_id INTEGER NOT NULL,
                   student_answer TEXT,
                   is_correct INTEGER
               )"""
        ))
        # 记录1：已交卷，2 题都评过、答案都填了 → is_scored=1, answered=2, total=2
        conn.execute(text("INSERT INTO exam_record(record_id, is_completed) VALUES (1, 1)"))
        conn.execute(text("INSERT INTO exam_answer_detail(record_id, student_answer, is_correct) "
                          "VALUES (1, 'A', 1), (1, 'B', 0)"))
        # 记录2：已交卷，1 题待人工评分（is_correct NULL）+ 1 题没作答 → is_scored=0, pending=1, answered=1, total=2
        conn.execute(text("INSERT INTO exam_record(record_id, is_completed) VALUES (2, 1)"))
        conn.execute(text("INSERT INTO exam_answer_detail(record_id, student_answer, is_correct) "
                          "VALUES (2, '对答如流', NULL), (2, '', 1)"))
        # 记录3：未交卷，1 题答对 → is_scored=0, pending=0, answered=1, total=1
        conn.execute(text("INSERT INTO exam_record(record_id, is_completed) VALUES (3, 0)"))
        conn.execute(text("INSERT INTO exam_answer_detail(record_id, student_answer, is_correct) "
                          "VALUES (3, 'C', 1)"))
    engine.dispose()


def _read(path) -> dict[int, tuple]:
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT record_id, is_scored, manual_pending_count, answered_count, question_total "
                "FROM exam_record ORDER BY record_id"
            )).all()
        return {r[0]: tuple(r[1:]) for r in rows}
    finally:
        engine.dispose()


def test_selfheal_adds_columns_with_default_zero(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    engine = create_engine(f"sqlite:///{db}")
    try:
        added = _ensure_exam_record_scoring_columns(engine, inspect(engine))
        assert set(added) == set(FOUR), f"应补 4 列，实际 {added}"
        cols = {c["name"]: c for c in inspect(engine).get_columns("exam_record")}
        missing = [c for c in FOUR if c not in cols]
        assert not missing, f"仍缺列: {missing}"
        for col in FOUR:
            assert str(cols[col].get("default") or "").strip("'") == "0", \
                f"{col} 默认值应为 0，实际 {cols[col].get('default')!r}"
    finally:
        engine.dispose()


def test_backfill_follows_scoring_rule_a(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    engine = create_engine(f"sqlite:///{db}")
    try:
        _ensure_exam_record_scoring_columns(engine, inspect(engine))
    finally:
        engine.dispose()

    got = _read(db)
    # 已交卷 + 无待评 → is_scored=1；已答按 student_answer 非空；分母=明细条数
    assert got[1] == (1, 0, 2, 2), got
    # 有待人工评分 → is_scored=0，pending=1，空答案不计已答
    assert got[2] == (0, 1, 1, 2), got
    # 未交卷 → is_scored=0，但派生字段照样算
    assert got[3] == (0, 0, 1, 1), got


def test_second_call_is_idempotent(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    engine = create_engine(f"sqlite:///{db}")
    try:
        assert len(_ensure_exam_record_scoring_columns(engine, inspect(engine))) == 4
        before = _read(db)
        assert _ensure_exam_record_scoring_columns(engine, inspect(engine)) == []
        assert _read(db) == before
    finally:
        engine.dispose()
