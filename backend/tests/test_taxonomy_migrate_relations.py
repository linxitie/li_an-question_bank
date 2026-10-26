"""T-05 tests for migrating question_knowledge relations to canonical points.

Pure fixtures only: no production database is read or written.
"""
from __future__ import annotations

import pytest

from scripts.migrate.build_taxonomy_v2 import (
    RelationMappingError,
    build_canonical_index,
    plan_relation_migration,
)

SUBJECT_ID = 1
VERBAL_SUBCAT = 3
DATA_SUBCAT = 6


def _point(
    point_id: int,
    name: str,
    level: int,
    parent_id: int,
    *,
    subject_id: int = SUBJECT_ID,
    sub_category_id: int | None = VERBAL_SUBCAT,
    status: int = 1,
    alias_of: int | None = None,
) -> dict:
    return {
        "point_id": point_id,
        "point_name": name,
        "subject_id": subject_id,
        "sub_category_id": sub_category_id,
        "parent_id": parent_id,
        "level": level,
        "status": status,
        "alias_of": alias_of,
    }


def _canonical_points() -> list[dict]:
    return [
        _point(689, "意图判断", 3, 14),
        _point(692, "词句理解", 3, 14),
        _point(700, "文字资料", 3, 735, sub_category_id=DATA_SUBCAT),
        _point(701, "图形资料", 3, 735, sub_category_id=DATA_SUBCAT),
    ]


def _hidden_points() -> list[dict]:
    return [
        _point(17, "词语理解", 2, 0, status=0),
        _point(18, "态度意图", 2, 0, status=0),
        _point(25, "文字资料分析", 2, 0, sub_category_id=DATA_SUBCAT, status=0),
        _point(26, "图形资料分析", 2, 0, sub_category_id=DATA_SUBCAT, status=0),
        _point(124, "待归类-职业素养", 2, 0, subject_id=3, sub_category_id=13, status=0),
        _point(125, "待归类-基础知识", 2, 0, subject_id=3, sub_category_id=14, status=0),
        _point(126, "待归类-基本警务能力", 2, 0, subject_id=3, sub_category_id=15, status=0),
        _point(200, "旧别名", 2, 0, status=0, alias_of=692),
    ]


def _rel(rel_id: int, question_id: int, point_id: int) -> dict:
    return {
        "id": rel_id,
        "question_id": question_id,
        "knowledge_point_id": point_id,
    }


def _plan(relations: list[dict]) -> dict:
    points = _canonical_points() + _hidden_points()
    return plan_relation_migration(
        points, relations, build_canonical_index(points)
    )


def test_alias_of_non_null_relation_moves_to_target():
    plan = _plan([_rel(1, 100, 200)])

    assert plan["migrated"] == 1
    assert plan["deduped"] == 0
    assert plan["unmigrated"] == 0
    assert plan["actions"] == [
        {
            "id": 1,
            "question_id": 100,
            "old_point_id": 200,
            "target_id": 692,
            "kind": "update",
        }
    ]
    assert plan["relations_to_alias_nonnull"] == 0


def test_manual_points_resolve_named_canonical_l3():
    plan = _plan(
        [
            _rel(1, 101, 17),
            _rel(2, 102, 18),
            _rel(3, 103, 25),
            _rel(4, 104, 26),
        ]
    )

    targets = {a["old_point_id"]: a["target_id"] for a in plan["actions"]}
    assert targets == {17: 692, 18: 689, 25: 700, 26: 701}
    assert plan["migrated"] == 4
    assert plan["unmigrated"] == 0
    assert plan["manual_targets"] == {
        "17": {"id": 692, "name": "词句理解"},
        "18": {"id": 689, "name": "意图判断"},
        "25": {"id": 700, "name": "文字资料"},
        "26": {"id": 701, "name": "图形资料"},
    }


def test_unmapped_hidden_relations_are_preserved():
    plan = _plan(
        [
            _rel(1, 201, 124),
            _rel(2, 202, 125),
            _rel(3, 203, 125),
            _rel(4, 204, 126),
        ]
    )

    assert plan["migrated"] == 0
    assert plan["deduped"] == 0
    assert plan["unmigrated"] == 4
    assert plan["actions"] == []
    assert plan["relations_after"] == 4
    assert plan["distinct_pairs_after"] == 4
    assert plan["relations_to_hidden_null"] == 4
    assert plan["unmigrated_by_point"] == [
        {"point_id": 125, "point_name": "待归类-基础知识", "count": 2},
        {"point_id": 124, "point_name": "待归类-职业素养", "count": 1},
        {"point_id": 126, "point_name": "待归类-基本警务能力", "count": 1},
    ]


def test_duplicate_target_pair_is_deduped():
    plan = _plan(
        [
            _rel(1, 300, 17),
            _rel(2, 300, 692),
            _rel(3, 301, 17),
        ]
    )

    assert plan["deduped"] == 1
    assert plan["migrated"] == 1
    assert plan["relations_before"] == 3
    assert plan["relations_after"] == 2
    assert plan["distinct_pairs_after"] == 2
    assert plan["duplicate_pairs_after"] == 0
    delete = [a for a in plan["actions"] if a["kind"] == "delete"]
    assert delete == [
        {
            "id": 1,
            "question_id": 300,
            "old_point_id": 17,
            "target_id": 692,
            "kind": "delete",
        }
    ]


def test_second_plan_is_idempotent():
    relations = [
        _rel(1, 400, 17),
        _rel(2, 400, 18),
        _rel(3, 401, 124),
        _rel(4, 402, 200),
    ]
    first = _plan(relations)
    assert first["migrated"] == 3
    assert first["deduped"] == 0
    assert first["unmigrated"] == 1

    updated = [dict(rel) for rel in relations]
    by_id = {rel["id"]: rel for rel in updated}
    for action in first["actions"]:
        if action["kind"] == "update":
            by_id[action["id"]]["knowledge_point_id"] = action["target_id"]
        else:
            del by_id[action["id"]]
    updated = list(by_id.values())

    second = _plan(updated)
    assert second["migrated"] == 0
    assert second["deduped"] == 0
    assert second["unmigrated"] == 1
    assert second["relations_before"] == first["relations_after"]
    assert second["distinct_pairs_after"] == first["distinct_pairs_after"]


def test_ambiguous_manual_target_raises():
    points = _hidden_points() + [
        _point(900, "词句理解", 3, 14),
        _point(901, "词句理解", 3, 14),
    ]
    with pytest.raises(RelationMappingError, match="old point 17"):
        plan_relation_migration(
            points, [_rel(1, 100, 17)], build_canonical_index(points)
        )
