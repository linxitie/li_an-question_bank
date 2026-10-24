"""T-08 回填 ``question_bank.sub_category_id``（归一化子科目）。

用法（默认 dry-run，只读）::

    python scripts/migrate/backfill_question_sub_category.py --db <path>
    python scripts/migrate/backfill_question_sub_category.py --apply --db <path> \
        [--report <path>]

回填优先级（仅处理当前 ``sub_category_id IS NULL`` 的题）:

1. 按科目读取对应文本列，严格 ``(subject_id, name)`` 匹配 ``sub_categories``；
2. ``question_bank.point_id`` → canonical ``knowledge_point.sub_category_id``；
3. 分类器结果 ``sub_category_id`` 非空且 ``confidence >= 0.15``；
4. 都不满足 → 保持 ``NULL``（隐藏的“未分类”桶）。

``--apply`` 必须显式传 ``--db``，且默认拒绝对生产库
``backend/data/question_bank.db`` 写入（除非显式 ``--allow-production``）。
本脚本不使用 ``shutil.copy2``、不创建备份、不修改生产库。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"

TEXT_COLUMN_BY_SUBJECT = {
    1: "xingce_subcategory",
    2: "shenlun_subcategory",
    3: "gongzhuan_subcategory",
}
UNCLASSIFIED_TEXT = "无"
MIN_CLASSIFIER_CONFIDENCE = 0.15


# ============================================================
# 纯函数：规划（可在无 DB 的情况下单测）
# ============================================================

def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _text_column(subject_id: int) -> Optional[str]:
    return TEXT_COLUMN_BY_SUBJECT.get(int(subject_id))


def _question_text(question: dict) -> str:
    subject_id = question.get("subject_id")
    if subject_id is None:
        return ""
    column = _text_column(int(subject_id))
    if not column:
        return ""
    return _normalize_text(question.get(column))


def _empty_subject_bucket() -> dict:
    return {
        "total": 0,
        "before_nonnull": 0,
        "before_null": 0,
        "filled_from_text": 0,
        "filled_from_point": 0,
        "filled_from_classifier": 0,
        "filled_null": 0,
        "already_set": 0,
        "changed": 0,
        "after_nonnull": 0,
        "after_null": 0,
    }


def _result_field(result: Any, name: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def plan_sub_category_backfill(
    questions,
    subcategory_ids: dict,
    point_subcategories: dict,
    classifier: Optional[Callable[[str, int], Any]] = None,
) -> dict:
    """计算 ``sub_category_id`` 回填计划，不写库。

    Args:
        questions: 题目 dict，需含 ``question_id/subject_id/point_id/
            question_content``、三个文本列和当前 ``sub_category_id``。
        subcategory_ids: ``(subject_id, name) -> sub_categories.id``（仅 status=1）。
        point_subcategories: canonical ``point_id -> sub_category_id``。
        classifier: 可调用对象 ``classifier(content, subject_id)``，结果需含
            ``sub_category_id`` 与 ``confidence``。

    Returns:
        dict: 计数、``updates``（仅实际变化项）、``null_question_ids`` 等。
    """
    total = len(questions)
    updates: list[dict] = []
    invalid_text_values: list[dict] = []
    classifier_errors: list[dict] = []
    null_question_ids: list[int] = []
    by_subject: dict[int, dict] = {}
    source_counts: Counter = Counter()
    counts: Counter = Counter()
    before_nonnull = 0
    after_nonnull = 0

    for question in questions:
        question_id = int(question["question_id"])
        subject_id = int(question["subject_id"])
        current_raw = question.get("sub_category_id")
        current = int(current_raw) if current_raw is not None else None

        bucket = by_subject.setdefault(subject_id, _empty_subject_bucket())
        bucket["total"] += 1

        if current is not None:
            before_nonnull += 1
            after_nonnull += 1
            counts["already_set"] += 1
            bucket["already_set"] += 1
            bucket["before_nonnull"] += 1
            bucket["after_nonnull"] += 1
            source_counts["already_set"] += 1
            continue

        bucket["before_null"] += 1
        new_value: Optional[int] = None
        source = "null"

        text = _question_text(question)
        if text not in ("", UNCLASSIFIED_TEXT):
            matched = subcategory_ids.get((subject_id, text))
            if matched is not None:
                new_value = int(matched)
                source = "text"
                counts["filled_from_text"] += 1
                bucket["filled_from_text"] += 1
            else:
                invalid_text_values.append(
                    {"question_id": question_id, "subject_id": subject_id, "value": text}
                )

        if new_value is None:
            point_id = question.get("point_id")
            if point_id is not None:
                point_sub_category = point_subcategories.get(int(point_id))
                if point_sub_category is not None:
                    new_value = int(point_sub_category)
                    source = "point"
                    counts["filled_from_point"] += 1
                    bucket["filled_from_point"] += 1

        if new_value is None and classifier is not None:
            try:
                result = classifier(question.get("question_content") or "", subject_id)
                candidate = _result_field(result, "sub_category_id")
                confidence_raw = _result_field(result, "confidence", 0.0)
                confidence = float(confidence_raw) if confidence_raw is not None else 0.0
                if candidate is not None and confidence >= MIN_CLASSIFIER_CONFIDENCE:
                    new_value = int(candidate)
                    source = "classifier"
                    counts["filled_from_classifier"] += 1
                    bucket["filled_from_classifier"] += 1
            except Exception as exc:  # 分类器异常不能中断迁移
                classifier_errors.append(
                    {
                        "question_id": question_id,
                        "subject_id": subject_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        if new_value is None:
            counts["filled_null"] += 1
            bucket["filled_null"] += 1
            null_question_ids.append(question_id)
            source_counts["null"] += 1
        else:
            after_nonnull += 1
            bucket["after_nonnull"] += 1
            source_counts[source] += 1

        if new_value != current:
            updates.append(
                {
                    "question_id": question_id,
                    "old_sub_category_id": current,
                    "new_sub_category_id": new_value,
                    "source": source,
                }
            )
            bucket["changed"] += 1

    all_sources = ("text", "point", "classifier", "null", "already_set")
    for bucket in by_subject.values():
        bucket["after_null"] = bucket["total"] - bucket["after_nonnull"]

    return {
        "total": total,
        "before_nonnull": before_nonnull,
        "before_null": total - before_nonnull,
        "filled_from_text": counts["filled_from_text"],
        "filled_from_point": counts["filled_from_point"],
        "filled_from_classifier": counts["filled_from_classifier"],
        "filled_null": counts["filled_null"],
        "already_set": counts["already_set"],
        "invalid_text_values": invalid_text_values,
        "classifier_errors": classifier_errors,
        "changed": len(updates),
        "after_nonnull": after_nonnull,
        "after_null": total - after_nonnull,
        "by_subject": {key: by_subject[key] for key in sorted(by_subject)},
        "source_counts": {key: source_counts.get(key, 0) for key in all_sources},
        "null_question_ids": null_question_ids,
        "updates": updates,
    }


# ============================================================
# 读取
# ============================================================

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def load_questions(conn: sqlite3.Connection) -> list[dict]:
    """读取回填所需的题目字段；旧库无 ``sub_category_id`` 时按 NULL 处理。"""
    columns = _table_columns(conn, "question_bank")
    fields = ["question_id", "subject_id", "question_content", "point_id"]
    for name in TEXT_COLUMN_BY_SUBJECT.values():
        fields.append(name if name in columns else f"NULL AS {name}")
    fields.append(
        "sub_category_id" if "sub_category_id" in columns else "NULL AS sub_category_id"
    )
    fields.append("status" if "status" in columns else "NULL AS status")
    fields.append("audit_status" if "audit_status" in columns else "NULL AS audit_status")

    rows = conn.execute(
        f"SELECT {', '.join(fields)} FROM question_bank ORDER BY question_id"
    ).fetchall()
    questions = []
    for row in rows:
        item = dict(row)
        item["question_id"] = int(item["question_id"])
        item["subject_id"] = int(item["subject_id"])
        if item.get("sub_category_id") is not None:
            item["sub_category_id"] = int(item["sub_category_id"])
        questions.append(item)
    return questions


def load_subcategory_ids(conn: sqlite3.Connection) -> dict[tuple[int, str], int]:
    return {
        (int(row["subject_id"]), str(row["name"])): int(row["id"])
        for row in conn.execute(
            "SELECT id, subject_id, name FROM sub_categories WHERE status=1"
        )
    }


def load_point_subcategories(conn: sqlite3.Connection) -> dict[int, int]:
    """canonical 考点（status=1、非别名）→ 子科目 ID。"""
    columns = _table_columns(conn, "knowledge_point")
    where = ["status=1", "sub_category_id IS NOT NULL"]
    if "alias_of" in columns:
        where.append("alias_of IS NULL")
    rows = conn.execute(
        "SELECT point_id, sub_category_id FROM knowledge_point WHERE "
        + " AND ".join(where)
    )
    return {int(row["point_id"]): int(row["sub_category_id"]) for row in rows}


def load_linked_question_ids(conn: sqlite3.Connection) -> set[int]:
    columns = _table_columns(conn, "question_knowledge")
    if not columns:
        return set()
    return {
        int(row[0])
        for row in conn.execute("SELECT DISTINCT question_id FROM question_knowledge")
    }


def _needs_classifier(
    questions, subcategory_ids: dict, point_subcategories: dict
) -> bool:
    """文本与 point 都填不上的题才需要加载分类器。"""
    for question in questions:
        if question.get("sub_category_id") is not None:
            continue
        text = _question_text(question)
        subject_id = int(question["subject_id"])
        if text not in ("", UNCLASSIFIED_TEXT) and (
            subject_id,
            text,
        ) in subcategory_ids:
            continue
        point_id = question.get("point_id")
        if point_id is not None and point_subcategories.get(int(point_id)) is not None:
            continue
        return True
    return False


# ============================================================
# 分类器（懒加载，失败降级为 NULL）
# ============================================================

def _build_classifier(target: Path, readonly: bool = False):
    """为指定 DB 构建分类器；返回 ``(callable, close, setup_error)``。"""
    try:
        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.services.question_classifier import (
            QuestionClassifier,
            clear_id_caches,
        )

        if readonly:
            # dry-run 对生产库也只读，避免创建 -wal/-shm 或任何写事务。
            uri = f"file:{target.as_posix()}?mode=ro"
            engine = create_engine(
                "sqlite://",
                creator=lambda: sqlite3.connect(
                    uri, uri=True, check_same_thread=False
                ),
            )
        else:
            engine = create_engine(
                f"sqlite:///{target.as_posix()}",
                connect_args={"check_same_thread": False},
            )
        session = sessionmaker(bind=engine)()
        clear_id_caches()
        classifier = QuestionClassifier()

        def classify(content: str, subject_id: int):
            return classifier.classify_with_db(content, subject_id, session)

        def close() -> None:
            try:
                session.close()
            finally:
                engine.dispose()

        return classify, close, None
    except Exception as exc:  # 不因分类器初始化失败而中断回填
        return None, None, f"{type(exc).__name__}: {exc}"


# ============================================================
# 写库
# ============================================================

def apply_schema_and_updates(conn: sqlite3.Connection, updates: list[dict]) -> None:
    """单事务内补列/建索引/批量更新；失败回滚。"""
    conn.execute("BEGIN IMMEDIATE")
    try:
        if "sub_category_id" not in _table_columns(conn, "question_bank"):
            conn.execute(
                "ALTER TABLE question_bank ADD COLUMN sub_category_id INTEGER"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_question_sub_category "
            "ON question_bank(sub_category_id)"
        )
        if updates:
            conn.executemany(
                "UPDATE question_bank SET sub_category_id=? WHERE question_id=?",
                [
                    (update["new_sub_category_id"], update["question_id"])
                    for update in updates
                ],
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ============================================================
# 报告
# ============================================================

def _final_map(questions, plan: dict) -> dict[int, Optional[int]]:
    final = {
        int(question["question_id"]): question.get("sub_category_id")
        for question in questions
    }
    for update in plan["updates"]:
        final[int(update["question_id"])] = update["new_sub_category_id"]
    return final


def _unlinked_breakdown(questions, linked_ids: set[int], final: dict) -> dict:
    unlinked = [q for q in questions if int(q["question_id"]) not in linked_ids]
    by_subject: Counter = Counter()
    with_text = 0
    without_text = 0
    with_point = 0
    null_after = 0
    for question in unlinked:
        by_subject[int(question["subject_id"])] += 1
        if _question_text(question) not in ("", UNCLASSIFIED_TEXT):
            with_text += 1
        else:
            without_text += 1
        if question.get("point_id") is not None:
            with_point += 1
        if final.get(int(question["question_id"])) is None:
            null_after += 1
    return {
        "count": len(unlinked),
        "with_text": with_text,
        "without_text": without_text,
        "with_point": with_point,
        "null_after": null_after,
        "filled_after": len(unlinked) - null_after,
        "by_subject": {key: by_subject[key] for key in sorted(by_subject)},
        "question_ids": [int(q["question_id"]) for q in unlinked],
    }


def _counter_rows(counter: Counter) -> list[dict]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    ]


def build_reconciliation(questions, final: dict) -> dict:
    """§5.5：公专文本分布 / 可见分布 / 迁移后 NULL 分布 / 差异清单。"""
    all_counter: Counter = Counter()
    visible_counter: Counter = Counter()
    null_counter: Counter = Counter()
    null_by_subject: Counter = Counter()
    differences: list[dict] = []

    for question in questions:
        text_value = question.get("gongzhuan_subcategory")
        all_counter[text_value] += 1
        is_visible = question.get("status") == 1 and question.get("audit_status") == 1
        if is_visible:
            visible_counter[text_value] += 1

        question_id = int(question["question_id"])
        final_value = final.get(question_id)
        if final_value is None:
            null_counter[text_value] += 1
            null_by_subject[int(question["subject_id"])] += 1

        if int(question["subject_id"]) != 3:
            continue
        text = _normalize_text(text_value)
        text_is_wu = text in ("", UNCLASSIFIED_TEXT)
        if text_is_wu and final_value is not None:
            reason = "text_wu_but_sub_category_set"
        elif not text_is_wu and final_value is None:
            reason = "text_present_but_sub_category_null"
        else:
            continue
        differences.append(
            {
                "question_id": question_id,
                "gongzhuan_subcategory": text_value,
                "sub_category_id": final_value,
                "status": question.get("status"),
                "audit_status": question.get("audit_status"),
                "reason": reason,
            }
        )

    return {
        "gongzhuan_subcategory_distribution": _counter_rows(all_counter),
        "gongzhuan_subcategory_visible_distribution": _counter_rows(visible_counter),
        "gongzhuan_subcategory_null_distribution": _counter_rows(null_counter),
        "sub_category_id_null_distribution": [
            {"subject_id": subject_id, "count": null_by_subject[subject_id]}
            for subject_id in sorted(null_by_subject)
        ],
        "reconciliation_differences": differences,
    }


def build_report(
    mode: str,
    db_path: Path,
    plan: dict,
    questions,
    linked_ids: set[int],
    schema_needs_migration: bool,
    classifier_setup_error: Optional[str],
) -> dict:
    final = _final_map(questions, plan)
    report = {
        "mode": mode,
        "db": str(db_path),
        "schema_needs_migration": schema_needs_migration,
        "column_added": bool(mode == "apply" and schema_needs_migration),
        "index_created": bool(mode == "apply"),
        "classifier_setup_error": classifier_setup_error,
        "total": plan["total"],
        "before_nonnull": plan["before_nonnull"],
        "before_null": plan["before_null"],
        "filled_from_text": plan["filled_from_text"],
        "filled_from_point": plan["filled_from_point"],
        "filled_from_classifier": plan["filled_from_classifier"],
        "filled_null": plan["filled_null"],
        "already_set": plan["already_set"],
        "changed": plan["changed"],
        "updated_rows": plan["changed"],
        "after_nonnull": plan["after_nonnull"],
        "after_null": plan["after_null"],
        "by_subject": plan["by_subject"],
        "source_counts": plan["source_counts"],
        "invalid_text_values": plan["invalid_text_values"],
        "classifier_errors": plan["classifier_errors"],
        "null_question_ids": plan["null_question_ids"],
        "unlinked": _unlinked_breakdown(questions, linked_ids, final),
    }
    report.update(build_reconciliation(questions, final))
    return report


def emit_report(report: dict, report_path: Optional[str]) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


# ============================================================
# 执行入口
# ============================================================

def run_backfill_sub_category(
    apply: bool,
    db_path: Optional[str] = None,
    report_path: Optional[str] = None,
    allow_production: bool = False,
    classifier: Optional[Callable[[str, int], Any]] = None,
) -> int:
    target = Path(db_path).resolve() if db_path else DB_PATH.resolve()

    if apply:
        if not db_path:
            raise SystemExit(
                "backfill-question-sub-category --apply requires an explicit --db <path>"
            )
        if target == DB_PATH.resolve() and not allow_production:
            raise SystemExit(
                "refusing to write the production database; pass a temp --db path"
            )
        if not target.exists():
            raise SystemExit(f"database not found: {target}")
        conn = sqlite3.connect(str(target))
        conn.isolation_level = None
    else:
        if not target.exists():
            raise FileNotFoundError(f"database not found: {target}")
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")

    conn.row_factory = sqlite3.Row
    try:
        schema_needs_migration = "sub_category_id" not in _table_columns(
            conn, "question_bank"
        )
        questions = load_questions(conn)
        subcategory_ids = load_subcategory_ids(conn)
        point_subcategories = load_point_subcategories(conn)
        linked_ids = load_linked_question_ids(conn)

        classifier_setup_error = None
        close_classifier = None
        if classifier is None:
            if _needs_classifier(questions, subcategory_ids, point_subcategories):
                classifier, close_classifier, classifier_setup_error = (
                    _build_classifier(target, readonly=not apply)
                )
        try:
            plan = plan_sub_category_backfill(
                questions,
                subcategory_ids,
                point_subcategories,
                classifier=classifier,
            )
        finally:
            if close_classifier is not None:
                close_classifier()

        if apply:
            apply_schema_and_updates(conn, plan["updates"])
            total, nonnull = conn.execute(
                "SELECT COUNT(*), COUNT(sub_category_id) FROM question_bank"
            ).fetchone()
            plan["after_nonnull"] = int(nonnull)
            plan["after_null"] = int(total) - int(nonnull)

        report = build_report(
            "apply" if apply else "dry-run",
            target,
            plan,
            questions,
            linked_ids,
            schema_needs_migration,
            classifier_setup_error,
        )
        if apply:
            report["after_nonnull"] = plan["after_nonnull"]
            report["after_null"] = plan["after_null"]
        emit_report(report, report_path)
        return 0
    finally:
        conn.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "T-08: 回填 question_bank.sub_category_id（默认 dry-run；"
            "--apply 必须显式 --db，且默认拒绝生产库）。"
        )
    )
    parser.add_argument("--db", default=None, help="SQLite 数据库路径（--apply 时必填）")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="写库（补列/建索引/回填）；默认仅 dry-run",
    )
    parser.add_argument("--report", default=None, help="额外把 JSON 报告写入该路径")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        dest="allow_production",
        help="允许对生产库 --apply（本任务禁用）",
    )
    args = parser.parse_args(argv)
    return run_backfill_sub_category(
        apply=args.apply,
        db_path=args.db,
        report_path=args.report,
        allow_production=args.allow_production,
    )


if __name__ == "__main__":
    raise SystemExit(main())
