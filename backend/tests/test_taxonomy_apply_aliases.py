"""T-04 tests for mapping legacy alias rows to canonical targets.

Pure fixtures only: no production database is read or written.
"""
from __future__ import annotations

import pytest

from scripts.migrate.build_taxonomy_v2 import (
    OTHER_LEAF,
    AliasMappingError,
    build_canonical_index,
    build_indexes,
    find_exact_target,
    find_other_target,
    plan_alias_updates,
)

SUBJECT_ID = 1
SUBCAT_ID = 5
TREE = {
    "行测": {
        "判断推理": {
            "图形推理": ["属性规律", OTHER_LEAF],
            "逻辑判断": [],
            "类比推理": [],
            "定义判断": [],
        }
    }
}
L2_ID = 632
OTHER_ID = 633
ATTR_ID = 634


def _row(
    point_id: int,
    name: str,
    level: int,
    parent_id: int,
    *,
    sub_category_id: int | None = SUBCAT_ID,
    status: int = 1,
    alias_of: int | None = None,
) -> dict:
    return {
        "point_id": point_id,
        "point_name": name,
        "subject_id": SUBJECT_ID,
        "sub_category_id": sub_category_id,
        "parent_id": parent_id,
        "level": level,
        "status": status,
        "alias_of": alias_of,
    }


def _canonical_rows() -> list[dict]:
    return [
        _row(L2_ID, "图形推理", 2, 0),
        _row(OTHER_ID, OTHER_LEAF, 3, L2_ID),
        _row(ATTR_ID, "属性规律", 3, L2_ID),
        # Hidden canonical rows must never be offered as targets.
        _row(700, "隐藏L2", 2, 0, status=0),
        _row(701, "属性规律", 3, 700, status=0, alias_of=ATTR_ID),
    ]


def _legacy_rows() -> list[dict]:
    return [
        _row(127, "属性规律", 2, 0),
        _row(128, "对称性", 2, 0),
        _row(129, "图形推理", 2, 0),
        _row(130, OTHER_LEAF, 3, 131, sub_category_id=None),
        _row(131, "图形推理", 2, 0),
        _row(132, "噪声词", 2, 0, sub_category_id=None),
    ]


def _csv(rows: list[tuple[int, str, str]]) -> list[dict]:
    return [
        {
            "old_id": str(old_id),
            "old_name": "",
            "subject": "行测",
            "sub_category": "",
            "new_id": "",
            "new_name": new_name,
            "match_type": match_type,
            "confidence": "0.9",
            "note": "",
        }
        for old_id, new_name, match_type in rows
    ]


def _plan(csv_rows: list[dict]):
    legacy = {row["point_id"]: row for row in _legacy_rows()}
    all_rows = dict(legacy)
    l2_index, _ = build_indexes(TREE)
    index = build_canonical_index(_canonical_rows())
    return plan_alias_updates(
        csv_rows, legacy, all_rows, {SUBCAT_ID: "判断推理"}, l2_index, index
    )


def test_exact_and_alias_resolve_to_canonical_l3():
    index = build_canonical_index(_canonical_rows())

    exact = find_exact_target(index, 127, SUBJECT_ID, SUBCAT_ID, "属性规律")
    alias = find_exact_target(index, 128, SUBJECT_ID, SUBCAT_ID, "属性规律")
    assert exact["point_id"] == ATTR_ID
    assert alias["point_id"] == ATTR_ID

    updates, counts, unresolved = _plan(
        _csv(
            [
                (127, "属性规律", "exact"),
                (128, "属性规律", "alias"),
            ]
        )
    )
    by_id = {u["old_id"]: u for u in updates}
    assert by_id[127]["alias_of"] == ATTR_ID
    assert by_id[128]["alias_of"] == ATTR_ID
    assert by_id[127]["sub_category_id"] == SUBCAT_ID
    assert counts["exact"] == 1 and counts["alias"] == 1
    assert unresolved == []


def test_subcategory_other_resolves_l2_other_leaf():
    index = build_canonical_index(_canonical_rows())
    target = find_other_target(index, 129, SUBJECT_ID, "图形推理")
    assert target["point_id"] == OTHER_ID

    updates, _counts, _unresolved = _plan(
        _csv([(129, OTHER_LEAF, "subcategory_other")])
    )
    assert updates[0]["alias_of"] == OTHER_ID
    assert updates[0]["sub_category_id"] == SUBCAT_ID


def test_subcategory_other_falls_back_to_parent_for_legacy_other():
    # 130 itself has no sub-category (resolver returns None); its parent 131
    # resolves to L2 图形推理, so it must still land on that L2's 其他 leaf.
    updates, _counts, _unresolved = _plan(
        _csv([(130, OTHER_LEAF, "subcategory_other")])
    )
    assert updates[0]["old_id"] == 130
    assert updates[0]["alias_of"] == OTHER_ID


def test_hidden_rows_get_null_alias_and_status_zero():
    updates, counts, _unresolved = _plan(_csv([(132, "", "hidden")]))
    assert updates[0]["alias_of"] is None
    assert updates[0]["status"] == 0
    assert counts["hidden"] == 1


def test_ambiguous_exact_target_raises():
    rows = _canonical_rows() + [
        _row(702, "图形推理二号", 2, 0),
        _row(703, "属性规律", 3, 702),
    ]
    index = build_canonical_index(rows)
    with pytest.raises(AliasMappingError, match="old_id 127"):
        find_exact_target(index, 127, SUBJECT_ID, SUBCAT_ID, "属性规律")


def test_missing_target_raises():
    index = build_canonical_index(_canonical_rows())
    with pytest.raises(AliasMappingError, match="old_id 127"):
        find_exact_target(index, 127, SUBJECT_ID, SUBCAT_ID, "不存在的考点")
    with pytest.raises(AliasMappingError, match="old_id 129"):
        find_other_target(index, 129, SUBJECT_ID, "不存在的L2")
