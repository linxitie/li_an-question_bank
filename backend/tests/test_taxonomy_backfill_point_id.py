"""T-06 tests for backfilling question_bank.point_id from canonical relations.

Pure dict planner tests plus a small sqlite temp-file apply test.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.migrate.build_taxonomy_v2 import (
    DB_PATH,
    canonical_relation_targets,
    plan_point_id_backfill,
    run_backfill_point_id,
)


def _point(point_id: int, *, status: int = 1, alias_of: int | None = None) -> dict:
    return {
        "point_id": point_id,
        "point_name": f"point-{point_id}",
        "subject_id": 1,
        "sub_category_id": 1,
        "parent_id": 0,
        "level": 3,
        "status": status,
        "alias_of": alias_of,
    }


def _question(question_id: int, point_id: int | None = None) -> dict:
    return {"question_id": question_id, "point_id": point_id}


def _rel(question_id: int, point_id: int) -> dict:
    return {"question_id": question_id, "knowledge_point_id": point_id}


def _plan(questions, points, relations) -> dict:
    return plan_point_id_backfill(
        questions, points, canonical_relation_targets(points, relations)
    )


def _points() -> list[dict]:
    return [
        _point(1),
        _point(2),
        _point(10, status=0, alias_of=2),
        _point(11, status=0),
    ]


def test_single_canonical_relation_fills_point_id():
    plan = _plan([_question(100)], _points(), [_rel(100, 1)])

    assert plan["filled_from_relation"] == 1
    assert plan["updates"] == [
        {"question_id": 100, "old_point_id": None, "new_point_id": 1}
    ]
    assert plan["after_nonnull"] == 1
    assert plan["after_null"] == 0


def test_multiple_canonical_relations_choose_lowest_and_report_ambiguous():
    points = _points() + [_point(68), _point(71)]
    plan = _plan([_question(162)], points, [_rel(162, 71), _rel(162, 68)])

    assert plan["filled_ambiguous"] == 1
    assert plan["filled_from_relation"] == 0
    assert plan["updates"][0]["new_point_id"] == 68
    assert plan["ambiguous_questions"] == [
        {
            "question_id": 162,
            "chosen_point_id": 68,
            "candidate_point_ids": [68, 71],
        }
    ]


def test_hidden_null_relation_is_ignored():
    # Add the legacy ambiguous ids 68/71 to the canonical points for this case.
    points = _points() + [_point(68), _point(71)]
    plan = _plan([_question(200)], points, [_rel(200, 11)])

    assert plan["no_canonical_relation"] == 1
    assert plan["filled_from_relation"] == 0
    assert plan["updates"] == []
    assert plan["after_nonnull"] == 0


def test_current_alias_maps_to_alias_of():
    plan = _plan([_question(300, point_id=10)], _points(), [])

    assert plan["mapped_from_alias"] == 1
    assert plan["updates"] == [
        {"question_id": 300, "old_point_id": 10, "new_point_id": 2}
    ]
    assert plan["after_nonnull"] == 1


def test_current_hidden_null_is_cleared():
    plan = _plan([_question(400, point_id=11)], _points(), [])

    assert plan["cleared_hidden"] == 1
    assert plan["updates"] == [
        {"question_id": 400, "old_point_id": 11, "new_point_id": None}
    ]
    assert plan["after_nonnull"] == 0
    assert plan["after_null"] == 1


def test_current_canonical_is_unchanged():
    plan = _plan([_question(500, point_id=1)], _points(), [])

    assert plan["already_canonical"] == 1
    assert plan["updates"] == []
    assert plan["point_id_nonnull_before"] == 1
    assert plan["after_nonnull"] == 1


def test_unknown_current_point_is_cleared_and_reported():
    plan = _plan([_question(600, point_id=999)], _points(), [])

    assert plan["cleared_invalid"] == 1
    assert plan["invalid_current_points"] == [{"question_id": 600, "point_id": 999}]
    assert plan["updates"] == [
        {"question_id": 600, "old_point_id": 999, "new_point_id": None}
    ]


def _create_db(path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE question_bank (
                question_id INTEGER PRIMARY KEY,
                point_id INTEGER
            );
            CREATE TABLE knowledge_point (
                point_id INTEGER PRIMARY KEY,
                point_name TEXT,
                subject_id INTEGER,
                sub_category_id INTEGER,
                parent_id INTEGER,
                level INTEGER,
                status INTEGER,
                alias_of INTEGER
            );
            CREATE TABLE question_knowledge (
                question_id INTEGER,
                knowledge_point_id INTEGER
            );
            """
        )
        conn.executemany(
            "INSERT INTO knowledge_point VALUES (?, ?, 1, 1, 0, 3, ?, ?)",
            [
                (1, "point-1", 1, None),
                (2, "point-2", 1, None),
                (10, "old-alias", 0, 2),
                (11, "hidden-null", 0, None),
            ],
        )
        conn.executemany(
            "INSERT INTO question_bank VALUES (?, ?)",
            [
                (1, None),
                (2, 10),  # alias -> 2
                (3, 11),  # hidden-null -> NULL
                (4, 99),  # unknown -> NULL
                (5, None),  # no relation -> NULL
                (6, 1),  # canonical -> unchanged
                (7, None),  # two targets -> lowest (1)
            ],
        )
        conn.executemany(
            "INSERT INTO question_knowledge VALUES (?, ?)",
            [(1, 1), (7, 2), (7, 1), (3, 11), (6, 1)],
        )
        conn.commit()
    finally:
        conn.close()


def _point_ids(path) -> dict[int, int | None]:
    conn = sqlite3.connect(str(path))
    try:
        return {
            int(row[0]): row[1]
            for row in conn.execute(
                "SELECT question_id, point_id FROM question_bank ORDER BY question_id"
            )
        }
    finally:
        conn.close()


def test_apply_twice_is_idempotent(tmp_path):
    db = tmp_path / "taxonomy_t06_test.db"
    _create_db(db)
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"

    assert run_backfill_point_id(True, str(db), str(first_report)) == 0
    first = json.loads(first_report.read_text(encoding="utf-8"))
    after_first = _point_ids(db)

    assert first["filled_from_relation"] == 1
    assert first["filled_ambiguous"] == 1
    assert first["mapped_from_alias"] == 1
    assert first["cleared_hidden"] == 1
    assert first["cleared_invalid"] == 1
    assert first["already_canonical"] == 1
    assert first["no_canonical_relation"] == 1
    assert first["updated_rows"] == 5
    assert after_first == {1: 1, 2: 2, 3: None, 4: None, 5: None, 6: 1, 7: 1}

    assert run_backfill_point_id(True, str(db), str(second_report)) == 0
    second = json.loads(second_report.read_text(encoding="utf-8"))

    assert second["updated_rows"] == 0
    assert _point_ids(db) == after_first
    assert second["after_nonnull"] == first["after_nonnull"] == 4
    assert second["after_null"] == first["after_null"] == 3


def test_dry_run_does_not_write(tmp_path):
    db = tmp_path / "taxonomy_t06_dry.db"
    _create_db(db)
    report_path = tmp_path / "dry.json"

    assert run_backfill_point_id(False, str(db), str(report_path)) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["mode"] == "dry-run"
    assert report["after_nonnull"] == 4
    assert _point_ids(db) == {1: None, 2: 10, 3: 11, 4: 99, 5: None, 6: 1, 7: None}


def test_production_path_is_refused_without_allow_production():
    with pytest.raises(SystemExit, match="production"):
        run_backfill_point_id(True, str(DB_PATH))
