"""T-08 tests: ``question_bank.sub_category_id`` backfill.

Planner tests are pure (no DB). Apply/dry-run tests use a tiny sqlite temp file
and an injected fake classifier so behaviour is deterministic.
"""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from app.models.models import QuestionBank
from scripts.migrate.backfill_question_sub_category import (
    DB_PATH,
    plan_sub_category_backfill,
    run_backfill_sub_category,
)

SUBCATEGORY_IDS = {
    (1, "政治理论"): 1,
    (1, "判断推理"): 5,
    (2, "归纳概括"): 8,
    (3, "基础知识"): 14,
    (3, "基本警务能力"): 15,
}
POINT_SUBCATEGORIES = {10: 1, 11: 5, 12: 8, 13: 14}


def _question(
    question_id: int,
    *,
    subject_id: int = 1,
    xingce: str = "无",
    shenlun: str = "无",
    gongzhuan: str = "无",
    point_id: int | None = None,
    current: int | None = None,
    content: str = "题干",
) -> dict:
    return {
        "question_id": question_id,
        "subject_id": subject_id,
        "question_content": content,
        "point_id": point_id,
        "xingce_subcategory": xingce,
        "shenlun_subcategory": shenlun,
        "gongzhuan_subcategory": gongzhuan,
        "sub_category_id": current,
    }


def _plan(questions, classifier=None) -> dict:
    return plan_sub_category_backfill(
        questions, SUBCATEGORY_IDS, POINT_SUBCATEGORIES, classifier=classifier
    )


def _fake(sub_category_id=None, confidence=0.0):
    return lambda content, subject_id: SimpleNamespace(
        sub_category_id=sub_category_id, confidence=confidence
    )


# ============================================================
# Planner
# ============================================================

def test_model_declares_column_and_index():
    table = QuestionBank.__table__
    assert "sub_category_id" in table.columns
    assert table.c.sub_category_id.nullable is True
    assert any(index.name == "idx_question_sub_category" for index in table.indexes)


def test_subject_specific_text_mapping_and_invalid_fallthrough():
    plan = _plan(
        [
            _question(1, subject_id=1, xingce="判断推理"),
            _question(2, subject_id=2, shenlun=" 归纳概括 "),
            _question(3, subject_id=3, gongzhuan="基础知识"),
            _question(4, subject_id=1, xingce="无", point_id=10),
            _question(5, subject_id=1, xingce="不存在的分类", point_id=11),
            _question(6, subject_id=1, xingce="乱写"),
        ]
    )

    assert plan["filled_from_text"] == 3
    assert plan["filled_from_point"] == 2
    assert plan["filled_null"] == 1
    assert plan["invalid_text_values"] == [
        {"question_id": 5, "subject_id": 1, "value": "不存在的分类"},
        {"question_id": 6, "subject_id": 1, "value": "乱写"},
    ]
    values = {u["question_id"]: u for u in plan["updates"]}
    assert values[1]["new_sub_category_id"] == 5
    assert values[1]["source"] == "text"
    assert values[2]["new_sub_category_id"] == 8
    assert values[3]["new_sub_category_id"] == 14
    # "无" 被忽略，回落到 point；无效文本也继续回落到 point
    assert values[4]["new_sub_category_id"] == 1
    assert values[4]["source"] == "point"
    assert values[5]["new_sub_category_id"] == 5
    assert values[5]["source"] == "point"
    assert 6 not in values
    assert plan["null_question_ids"] == [6]


def test_point_fallback_when_text_empty():
    plan = _plan([_question(7, subject_id=3, gongzhuan="  ", point_id=13)])

    assert plan["filled_from_text"] == 0
    assert plan["filled_from_point"] == 1
    assert plan["updates"] == [
        {
            "question_id": 7,
            "old_sub_category_id": None,
            "new_sub_category_id": 14,
            "source": "point",
        }
    ]


def test_classifier_accepts_exactly_threshold():
    plan = _plan([_question(8, subject_id=3)], _fake(15, 0.15))

    assert plan["filled_from_classifier"] == 1
    assert plan["updates"][0]["new_sub_category_id"] == 15
    assert plan["updates"][0]["source"] == "classifier"


def test_classifier_rejects_below_threshold():
    plan = _plan([_question(9, subject_id=3)], _fake(15, 0.149))

    assert plan["filled_from_classifier"] == 0
    assert plan["filled_null"] == 1
    assert plan["updates"] == []
    assert plan["null_question_ids"] == [9]


def test_classifier_rejects_missing_sub_category_id():
    plan = _plan([_question(10, subject_id=3)], _fake(None, 0.99))

    assert plan["filled_from_classifier"] == 0
    assert plan["filled_null"] == 1
    assert plan["null_question_ids"] == [10]


def test_classifier_exception_is_recorded_and_leaves_null():
    def boom(content, subject_id):
        raise RuntimeError("classifier down")

    plan = _plan([_question(11, subject_id=3)], boom)

    assert plan["filled_null"] == 1
    assert plan["classifier_errors"] == [
        {
            "question_id": 11,
            "subject_id": 3,
            "error": "RuntimeError: classifier down",
        }
    ]
    assert plan["null_question_ids"] == [11]


def test_nothing_matches_stays_null():
    plan = _plan([_question(12, subject_id=3)], _fake(None, 0.0))

    assert plan["filled_null"] == 1
    assert plan["after_nonnull"] == 0
    assert plan["after_null"] == 1
    assert plan["changed"] == 0
    assert plan["null_question_ids"] == [12]


def test_existing_non_null_is_preserved_as_already_set():
    plan = _plan([_question(13, subject_id=1, xingce="判断推理", current=1)])

    assert plan["already_set"] == 1
    assert plan["before_nonnull"] == 1
    assert plan["after_nonnull"] == 1
    assert plan["updates"] == []
    assert plan["source_counts"]["already_set"] == 1


# ============================================================
# sqlite temp DB fixtures
# ============================================================

def _create_db(path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE sub_categories (
                id INTEGER PRIMARY KEY,
                subject_id INTEGER,
                name TEXT,
                status INTEGER
            );
            CREATE TABLE knowledge_point (
                point_id INTEGER PRIMARY KEY,
                point_name TEXT,
                subject_id INTEGER,
                sub_category_id INTEGER,
                status INTEGER,
                alias_of INTEGER
            );
            CREATE TABLE question_knowledge (
                question_id INTEGER,
                knowledge_point_id INTEGER
            );
            CREATE TABLE question_bank (
                question_id INTEGER PRIMARY KEY,
                subject_id INTEGER,
                question_content TEXT,
                point_id INTEGER,
                xingce_subcategory TEXT,
                shenlun_subcategory TEXT,
                gongzhuan_subcategory TEXT,
                status INTEGER,
                audit_status INTEGER
            );
            """
        )
        conn.executemany(
            "INSERT INTO sub_categories (id, subject_id, name, status) VALUES (?, ?, ?, ?)",
            [
                (1, 1, "政治理论", 1),
                (5, 1, "判断推理", 1),
                (8, 2, "归纳概括", 1),
                (14, 3, "基础知识", 1),
                (15, 3, "基本警务能力", 1),
                (99, 1, "隐藏子科目", 0),
            ],
        )
        conn.executemany(
            "INSERT INTO knowledge_point "
            "(point_id, point_name, subject_id, sub_category_id, status, alias_of) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, "canonical-a", 1, 1, 1, None),
                (11, "hidden-point", 1, 5, 0, None),
                (12, "alias-point", 1, 8, 1, 11),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _insert_questions(path, rows) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executemany(
            "INSERT INTO question_bank "
            "(question_id, subject_id, question_content, point_id, "
            " xingce_subcategory, shenlun_subcategory, gongzhuan_subcategory, "
            " status, audit_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _apply_fixture(path) -> None:
    _create_db(path)
    _insert_questions(
        path,
        [
            (1, 1, "题干", None, "判断推理", "无", "无", 1, 1),
            (2, 1, "题干", 10, "无", "无", "无", 1, 1),
            (3, 1, "classify", None, "无", "无", "无", 1, 1),
            (4, 1, "题干", 11, "无", "无", "无", 1, 0),
            (5, 1, "题干", 12, "无", "无", "无", 0, 1),
        ],
    )
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("INSERT INTO question_knowledge VALUES (1, 10)")
        conn.commit()
    finally:
        conn.close()


def _columns(path) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(question_bank)")}
    finally:
        conn.close()


def _values(path) -> dict[int, int | None]:
    conn = sqlite3.connect(str(path))
    try:
        return {
            int(row[0]): row[1]
            for row in conn.execute(
                "SELECT question_id, sub_category_id "
                "FROM question_bank ORDER BY question_id"
            )
        }
    finally:
        conn.close()


def _fake_for_apply(content, subject_id):
    if content == "classify":
        return SimpleNamespace(sub_category_id=5, confidence=0.15)
    return SimpleNamespace(sub_category_id=None, confidence=0.0)


# ============================================================
# dry-run / apply
# ============================================================

def test_dry_run_does_not_mutate_schema_or_rows(tmp_path):
    db = tmp_path / "t08_dry.db"
    _apply_fixture(db)
    report_path = tmp_path / "dry.json"

    assert "sub_category_id" not in _columns(db)

    assert (
        run_backfill_sub_category(
            False, str(db), str(report_path), classifier=_fake_for_apply
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["mode"] == "dry-run"
    assert report["schema_needs_migration"] is True
    assert report["column_added"] is False
    assert report["index_created"] is False
    assert report["filled_from_text"] == 1
    assert report["filled_from_point"] == 1
    assert report["filled_from_classifier"] == 1
    assert report["filled_null"] == 2
    assert report["changed"] == 3
    assert report["null_question_ids"] == [4, 5]

    # 只读：列和行均未变化
    assert "sub_category_id" not in _columns(db)
    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='index' AND name='idx_question_sub_category'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT xingce_subcategory FROM question_bank WHERE question_id=1"
        ).fetchone()[0] == "判断推理"
    finally:
        conn.close()


def test_apply_creates_column_index_and_is_idempotent(tmp_path):
    db = tmp_path / "t08_apply.db"
    _apply_fixture(db)
    first_report = tmp_path / "first.json"
    second_report = tmp_path / "second.json"

    assert (
        run_backfill_sub_category(
            True, str(db), str(first_report), classifier=_fake_for_apply
        )
        == 0
    )
    first = json.loads(first_report.read_text(encoding="utf-8"))

    assert first["mode"] == "apply"
    assert first["schema_needs_migration"] is True
    assert first["column_added"] is True
    assert first["index_created"] is True
    assert first["changed"] == 3
    assert first["updated_rows"] == 3
    assert first["after_nonnull"] == 3
    assert first["after_null"] == 2
    assert _values(db) == {1: 5, 2: 1, 3: 5, 4: None, 5: None}

    conn = sqlite3.connect(str(db))
    try:
        assert "sub_category_id" in _columns(db)
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='index' AND name='idx_question_sub_category'"
        ).fetchone()[0] == 1
    finally:
        conn.close()

    assert (
        run_backfill_sub_category(
            True, str(db), str(second_report), classifier=_fake_for_apply
        )
        == 0
    )
    second = json.loads(second_report.read_text(encoding="utf-8"))

    assert second["schema_needs_migration"] is False
    assert second["column_added"] is False
    assert second["changed"] == 0
    assert second["updated_rows"] == 0
    assert second["already_set"] == 3
    assert second["filled_null"] == 2
    assert _values(db) == {1: 5, 2: 1, 3: 5, 4: None, 5: None}


def test_report_has_unlinked_breakdown_and_reconciliation(tmp_path):
    db = tmp_path / "t08_report.db"
    _apply_fixture(db)
    report_path = tmp_path / "report.json"

    assert (
        run_backfill_sub_category(
            False, str(db), str(report_path), classifier=_fake_for_apply
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["unlinked"]["count"] == 4
    assert report["unlinked"]["question_ids"] == [2, 3, 4, 5]
    assert report["unlinked"]["null_after"] == 2
    assert report["unlinked"]["filled_after"] == 2
    assert report["null_question_ids"] == [4, 5]
    assert "gongzhuan_subcategory_distribution" in report
    assert "gongzhuan_subcategory_visible_distribution" in report
    assert "gongzhuan_subcategory_null_distribution" in report
    assert "reconciliation_differences" in report


def test_production_guard_rejects_production_path_and_missing_db():
    with pytest.raises(SystemExit, match="production"):
        run_backfill_sub_category(True, str(DB_PATH))

    with pytest.raises(SystemExit, match="explicit --db"):
        run_backfill_sub_category(True)
