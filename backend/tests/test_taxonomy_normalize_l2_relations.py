"""T-08b tests for normalizing direct canonical-L2 references to ``其他`` L3.

Pure dict planner tests plus a small sqlite temp-file apply test.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.migrate.build_taxonomy_v2 import (
    DB_PATH,
    plan_l2_relation_normalization,
    run_normalize_l2_relations,
)

OTHER_ID = 110


def _point(
    point_id: int,
    name: str,
    *,
    level: int,
    parent_id: int | None = None,
    status: int = 1,
    alias_of: int | None = None,
) -> dict:
    return {
        "point_id": point_id,
        "point_name": name,
        "parent_id": parent_id,
        "level": level,
        "status": status,
        "alias_of": alias_of,
    }


def _points() -> list[dict]:
    return [
        _point(10, "数量关系", level=2),
        _point(20, "资料分析", level=2),
        _point(101, "具体A", level=3, parent_id=10),
        _point(105, "具体B", level=3, parent_id=10),
        _point(OTHER_ID, "其他", level=3, parent_id=10),
        _point(201, "具体C", level=3, parent_id=20),
        _point(40, "旧L3", level=3, parent_id=10, status=0),
    ]


def _question(question_id: int, point_id: int | None = None) -> dict:
    return {"question_id": question_id, "point_id": point_id}


def _rel(rel_id: int, question_id: int, point_id: int) -> dict:
    return {
        "id": rel_id,
        "question_id": question_id,
        "knowledge_point_id": point_id,
    }


def _plan(relations, questions) -> dict:
    return plan_l2_relation_normalization(_points(), relations, questions)


def test_single_l2_relation_moves_to_other_l3():
    plan = _plan([_rel(1, 1, 10)], [_question(1, 10)])

    assert plan["l2_relations_before"] == 1
    assert plan["moved"] == 1
    assert plan["deduped"] == 0
    assert plan["relation_updates"] == [
        {
            "id": 1,
            "question_id": 1,
            "old_knowledge_point_id": 10,
            "new_knowledge_point_id": OTHER_ID,
        }
    ]
    assert plan["question_updates"] == [
        {"question_id": 1, "old_point_id": 10, "new_point_id": OTHER_ID}
    ]
    assert plan["relations_after"] == 1
    assert plan["question_points_l2_after"] == 0


def test_duplicate_target_deletes_l2_source_instead_of_duplicating():
    plan = _plan(
        [_rel(1, 2, 10), _rel(2, 2, OTHER_ID)], [_question(2, 10)]
    )

    assert plan["moved"] == 0
    assert plan["deduped"] == 1
    assert plan["relation_updates"] == []
    assert plan["relation_deletes"] == [
        {"id": 1, "question_id": 2, "knowledge_point_id": 10}
    ]
    assert plan["relations_after"] == 1
    assert plan["question_updates"] == [
        {"question_id": 2, "old_point_id": 10, "new_point_id": OTHER_ID}
    ]


def test_l2_without_other_is_reported_and_left_unchanged():
    plan = _plan([_rel(1, 7, 20)], [_question(7, 20)])

    assert plan["l2_relations_before"] == 1
    assert plan["moved"] == 0
    assert plan["deduped"] == 0
    assert plan["unmigrated"] == 1
    assert plan["relation_updates"] == []
    assert plan["relation_deletes"] == []
    assert plan["missing_other"] == [
        {
            "scope": "relation",
            "point_id": 20,
            "point_name": "资料分析",
            "count": 1,
        },
        {
            "scope": "question",
            "point_id": 20,
            "point_name": "资料分析",
            "count": 1,
        },
    ]
    # The question point cannot stay on L2 and has no L3 target either.
    assert plan["question_points_cleared"] == 1
    assert plan["question_updates"] == [
        {"question_id": 7, "old_point_id": 20, "new_point_id": None}
    ]


def test_question_on_l2_without_relation_falls_back_to_other():
    plan = _plan([], [_question(8, 10)])

    assert plan["question_points_l2_before"] == 1
    assert plan["question_points_updated"] == 1
    assert plan["question_updates"] == [
        {"question_id": 8, "old_point_id": 10, "new_point_id": OTHER_ID}
    ]


def test_question_with_l2_and_specific_l3_chooses_smallest_l3():
    plan = _plan(
        [_rel(1, 4, 10), _rel(2, 4, 101)], [_question(4, 10)]
    )

    # 101 < 110, so the specific L3 wins over 其他.
    assert plan["question_updates"] == [
        {"question_id": 4, "old_point_id": 10, "new_point_id": 101}
    ]


def test_non_l2_relations_and_question_points_are_unchanged():
    plan = _plan([_rel(1, 5, 101)], [_question(5, 101)])

    assert plan["l2_relations_before"] == 0
    assert plan["question_points_l2_before"] == 0
    assert plan["relation_updates"] == []
    assert plan["relation_deletes"] == []
    assert plan["question_updates"] == []
    assert plan["changed"] == 0


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
                parent_id INTEGER,
                level INTEGER,
                status INTEGER,
                alias_of INTEGER
            );
            CREATE TABLE question_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                knowledge_point_id INTEGER
            );
            """
        )
        conn.executemany(
            "INSERT INTO knowledge_point VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, "数量关系", None, 2, 1, None),
                (20, "资料分析", None, 2, 1, None),
                (101, "具体A", 10, 3, 1, None),
                (105, "具体B", 10, 3, 1, None),
                (OTHER_ID, "其他", 10, 3, 1, None),
                (201, "具体C", 20, 3, 1, None),
                (40, "旧L3", 10, 3, 0, None),
            ],
        )
        conn.executemany(
            "INSERT INTO question_bank VALUES (?, ?)",
            [
                (1, 10),
                (2, 10),
                (3, 20),
                (4, 10),
                (5, 101),
                (6, 10),
                (7, 20),
                (8, 10),
            ],
        )
        conn.executemany(
            "INSERT INTO question_knowledge (id, question_id, knowledge_point_id) "
            "VALUES (?, ?, ?)",
            [
                (1, 1, 10),
                (2, 2, 10),
                (3, 2, OTHER_ID),
                (4, 4, 10),
                (5, 4, 101),
                (6, 5, 101),
                (7, 6, 101),
                (8, 7, 20),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _snapshot(path) -> dict:
    conn = sqlite3.connect(str(path))
    try:
        return {
            "relations": [
                tuple(row)
                for row in conn.execute(
                    "SELECT id, question_id, knowledge_point_id "
                    "FROM question_knowledge ORDER BY id"
                )
            ],
            "points": {
                int(row[0]): row[1]
                for row in conn.execute(
                    "SELECT question_id, point_id FROM question_bank "
                    "ORDER BY question_id"
                )
            },
        }
    finally:
        conn.close()


def test_dry_run_does_not_write(tmp_path):
    db = tmp_path / "taxonomy_t08b_dry.db"
    _create_db(db)
    before = _snapshot(db)
    report_path = tmp_path / "dry.json"

    assert run_normalize_l2_relations(False, str(db), str(report_path)) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mode"] == "dry-run"
    assert report["l2_relations_before"] == 4
    assert report["moved"] == 2
    assert report["deduped"] == 1
    assert report["unmigrated"] == 1
    assert report["changed"] == 10
    assert report["missing_other"] == [
        {
            "scope": "relation",
            "point_id": 20,
            "point_name": "资料分析",
            "count": 1,
        },
        {
            "scope": "question",
            "point_id": 20,
            "point_name": "资料分析",
            "count": 2,
        },
    ]
    assert _snapshot(db) == before


def test_apply_updates_refs_and_second_apply_is_idempotent(tmp_path):
    db = tmp_path / "taxonomy_t08b_apply.db"
    _create_db(db)
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"

    assert run_normalize_l2_relations(True, str(db), str(first_report)) == 0
    first = json.loads(first_report.read_text(encoding="utf-8"))
    after_first = _snapshot(db)

    assert first["changed"] == 10
    assert first["moved"] == 2
    assert first["deduped"] == 1
    assert first["unmigrated"] == 1
    assert first["question_points_updated"] == 7
    assert first["question_points_cleared"] == 2
    assert first["relations_after"] == 7
    assert first["question_points_l2_after"] == 0
    assert after_first["points"] == {
        1: OTHER_ID,
        2: OTHER_ID,
        3: None,
        4: 101,
        5: 101,
        6: 101,
        7: None,
        8: OTHER_ID,
    }
    assert (2, OTHER_ID) in {
        (row[1], row[2]) for row in after_first["relations"]
    }
    assert (1, 10) not in {
        (row[1], row[2]) for row in after_first["relations"]
    }

    assert run_normalize_l2_relations(True, str(db), str(second_report)) == 0
    second = json.loads(second_report.read_text(encoding="utf-8"))

    assert second["changed"] == 0
    assert second["moved"] == 0
    assert second["deduped"] == 0
    assert second["question_points_updated"] == 0
    assert second["unmigrated"] == 1
    assert _snapshot(db) == after_first


def test_production_path_is_refused_without_allow_production():
    with pytest.raises(SystemExit, match="production"):
        run_normalize_l2_relations(True, str(DB_PATH))
