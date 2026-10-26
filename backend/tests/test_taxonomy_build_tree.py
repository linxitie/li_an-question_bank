from __future__ import annotations

from collections import Counter

from scripts.admin.seed import KNOWLEDGE_TREE_V2
from scripts.migrate.build_taxonomy_v2 import (
    OTHER_LEAF,
    build_indexes,
    classify_seed_rows,
    flatten_canonical,
    node_key,
    plan_legacy_others,
    validate_canonical,
)

SUBJECT_IDS = {"行测": 1, "申论": 2, "公专": 3}


def _subcat_ids(tree: dict) -> dict:
    ids: dict[str, int] = {}
    for groups in tree.values():
        for group in groups:
            ids.setdefault(group, len(ids) + 1)
    return ids


def _canonical_nodes() -> list[dict]:
    return flatten_canonical(KNOWLEDGE_TREE_V2, SUBJECT_IDS, _subcat_ids(KNOWLEDGE_TREE_V2))


def test_canonical_flatten_counts_and_other_rule():
    nodes = _canonical_nodes()
    counts = validate_canonical(nodes)
    assert (counts["l2"], counts["l3"], counts["total"]) == (91, 427, 518)
    assert counts["by_subject"] == {
        "行测": {2: 31, 3: 146},
        "申论": {2: 25, 3: 109},
        "公专": {2: 35, 3: 172},
    }

    l2s = [n for n in nodes if n["level"] == 2]
    others = Counter(
        (n["subject_id"], n["sub_category_id"], n["parent_name"])
        for n in nodes
        if n["level"] == 3 and n["name"] == OTHER_LEAF
    )
    for l2 in l2s:
        key = (l2["subject_id"], l2["sub_category_id"], l2["name"])
        assert others[key] == 1, key

    siblings = Counter(node_key(n) for n in nodes)
    assert [k for k, c in siblings.items() if c > 1] == []


def _other_fixture():
    rows = []
    all_rows = {}
    subcat_names = {5: "判断推理"}

    def add(point_id, level, parent_id, subject_id=1):
        row = {
            "point_id": point_id,
            "point_name": OTHER_LEAF,
            "subject_id": subject_id,
            "sub_category_id": 5,
            "level": level,
            "parent_id": parent_id,
        }
        rows.append(row)
        all_rows[point_id] = row

    add(401, 2, 0)
    all_rows[270] = {
        "point_id": 270,
        "point_name": "材料",
        "subject_id": 1,
        "sub_category_id": None,
        "level": 2,
        "parent_id": 0,
    }
    add(571, 3, 270)
    all_rows[412] = {
        "point_id": 412,
        "point_name": "确定捆绑",
        "subject_id": 1,
        "sub_category_id": 5,
        "level": 2,
        "parent_id": 0,
    }
    add(592, 3, 412)

    for offset in range(32):
        parent_id = 700 + offset
        all_rows[parent_id] = {
            "point_id": parent_id,
            "point_name": "图形推理",
            "subject_id": 1,
            "sub_category_id": 5,
            "level": 2,
            "parent_id": 0,
        }
        add(500 + offset, 3, parent_id)

    return rows, all_rows, subcat_names


def test_other_resolution_splits_resolved_and_unresolved():
    rows, all_rows, subcat_names = _other_fixture()
    l2_index, _ = build_indexes(KNOWLEDGE_TREE_V2)
    plans = plan_legacy_others(rows, all_rows, subcat_names, l2_index)

    assert len(plans) == 35
    unresolved = sorted(p["point_id"] for p in plans if p["l2"] is None)
    assert unresolved == [401, 571, 592]
    resolved = [p for p in plans if p["l2"] is not None]
    assert len(resolved) == 32
    assert {p["l2"] for p in resolved} == {"图形推理"}


def test_obsolete_seed_alias_never_crosses_subcategory():
    nodes = [
        {
            "subject_id": 1,
            "sub_category_id": 3,
            "level": 2,
            "parent_name": None,
            "name": "片段阅读",
        },
        {
            "subject_id": 1,
            "sub_category_id": 5,
            "level": 2,
            "parent_name": None,
            "name": "中心理解",
        },
        {
            "subject_id": 1,
            "sub_category_id": 6,
            "level": 3,
            "parent_name": "资料类型",
            "name": "文字资料分析",
        },
        {
            "subject_id": 1,
            "sub_category_id": 5,
            "level": 3,
            "parent_name": "图形推理",
            "name": "知觉准确性",
        },
    ]

    def seed(point_id, name, sub_category_id, level=2, parent_id=0):
        return {
            "point_id": point_id,
            "point_name": name,
            "subject_id": 1,
            "sub_category_id": sub_category_id,
            "level": level,
            "parent_id": parent_id,
        }

    seed_rows = [
        seed(14, "片段阅读", 3),
        seed(16, "中心理解", 3),
        seed(25, "文字资料分析", 6),
        seed(34, "知觉准确性", 7),
        seed(95, "公安机关的性质", 14, level=3, parent_id=72),
    ]
    parent_names = {72: "公安机关性质与职能"}

    reused, obsolete = classify_seed_rows(seed_rows, parent_names, nodes)

    assert [row["point_id"] for row, _ in reused] == [14]
    by_id = {o["point_id"]: o for o in obsolete}
    assert sorted(by_id) == [16, 25, 34, 95]
    assert by_id[25]["alias_key"] == node_key(nodes[2])
    assert by_id[16]["alias_key"] is None
    assert by_id[34]["alias_key"] is None
    assert by_id[95]["alias_key"] is None

    node_by_key = {node_key(n): n for n in nodes}
    for item in obsolete:
        if item["alias_key"] is None:
            continue
        target = node_by_key[item["alias_key"]]
        assert target["sub_category_id"] == item["sub_category_id"]
