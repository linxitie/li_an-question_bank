# -*- coding: utf-8 -*-
"""
question_cascade.py — 题目级联清理（单一事实来源）

背景（真实生产故障）：
    生产库实测有 **14 张表**含 question_id 列并引用 question_bank，但
    clean_questions.py 原本只列了 6 张子表，cleanup_incomplete.py 一张都没列。
    手维护清单必然漏表 → 漏表的那些表在主表被硬删除后残留孤儿行。
    其中 question_detail_category.question_id 带 UNIQUE 约束
    (uk_question_category)，孤儿行会在 SQLite 复用主键时
    撞唯一约束 → 题目批量导入**整批回滚、接口 500**。

设计要点：
    1. **运行时自动发现**引用 question_id 的子表，而不是硬编码清单 ——
       新增表自动被覆盖，从根上杜绝"又漏了一张"这类复发。
    2. 提供 purge_children() 供硬删除脚本调用；sweep_orphans() 兜底清理残留。
    3. 全部操作只删"父行已不存在"的子表行，对 question_bank 本身零改动。
    4. SQLite 与 MySQL 双兼容（本项目当前为 SQLite，MySQL 走 information_schema）。
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# 非 SQLite 环境的兜底清单（已知引用 question_bank 的子表）
FALLBACK_CHILD_TABLES: List[str] = [
    'exam_answer_detail',
    'favorite_question',
    'paper_question_relation',
    'practice_record',
    'question_detail_category',
    'question_edit_log',
    'question_image',
    'question_knowledge',
    'question_marker',
    'question_note',
    'video_resource',
    'video_watch_record',
    'wrong_question_class',
    'wrong_question_personal',
]

# 绝不能被当作子表清理的目标表
NEVER_PURGE = {'question_bank'}


def _is_sqlite(bind: Any) -> bool:
    try:
        return bind.dialect.name == 'sqlite'
    except Exception:  # noqa: BLE001
        return False


def discover_child_tables(bind: Any) -> List[str]:
    """发现所有含 question_id 列、且不是 question_bank 本身的表。"""
    try:
        if _is_sqlite(bind):
            from sqlalchemy import text
            with bind.connect() as conn:
                names = [r[0] for r in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
            found = []
            for t in names:
                if t in NEVER_PURGE or t.startswith('sqlite_'):
                    continue
                with bind.connect() as conn:
                    cols = [r[1] for r in conn.execute(
                        text(f'PRAGMA table_info("{t}")')).fetchall()]
                if 'question_id' in cols:
                    found.append(t)
            return sorted(found)
        # MySQL 等：用 information_schema
        from sqlalchemy import text
        with bind.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT TABLE_NAME FROM information_schema.COLUMNS
                WHERE COLUMN_NAME = 'question_id'
                  AND TABLE_SCHEMA = DATABASE()
            """)).fetchall()
        return sorted(r[0] for r in rows if r[0] not in NEVER_PURGE)
    except Exception as e:  # noqa: BLE001 — 发现失败时退回静态清单，绝不阻断清理
        logger.warning(f"[cascade] 自动发现子表失败({e})，退回静态清单")
        return list(FALLBACK_CHILD_TABLES)


def purge_children(db, question_ids: Sequence[int]) -> int:
    """在删除 question_bank 记录**之前**调用，清理其所有子表行。

    返回删除的子表行总数。任何单表失败都不阻断其余表（尽量清干净）。
    """
    if not question_ids:
        return 0
    tables = discover_child_tables(db.get_bind())
    total = 0
    for t in tables:
        try:
            n = db.query(_table_class(t)).filter(
                _table_class(t).question_id.in_(list(question_ids))
            ).delete(synchronize_session=False)
            total += n or 0
        except Exception as e:  # noqa: BLE001 — 表可能不存在/结构不同，跳过继续
            logger.debug(f"[cascade] 清理 {t} 跳过: {e}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
    if total:
        logger.info(f"[cascade] 清理子表共 {total} 行（{len(question_ids)} 个题目）")
    return total


def sweep_orphans(db) -> dict:
    """兜底：删除所有"父行已不存在"的子表行（即历史遗留孤儿）。

    返回 {'表名': 删除行数, ...}，供调用方记录审计日志。
    """
    report = {}
    for t in discover_child_tables(db.get_bind()):
        try:
            n = db.query(_table_class(t)).filter(
                ~_table_class(t).question_id.in_(
                    db.query(_table_class('question_bank').question_id)
                )
            ).delete(synchronize_session=False)
            if n:
                report[t] = n
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[cascade] sweep {t} 跳过: {e}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
    if report:
        logger.warning(f"[cascade] 清理历史孤儿行: {report}")
    return report


def _table_class(name: str):
    """按表名取 SQLAlchemy 映射类（自动导入 models 以确保全部注册）。

    兼容 SQLAlchemy 1.x 的 ``Base._class_registry`` 与 2.x 的 ``Base.registry.mappers``。
    """
    import importlib
    importlib.import_module('app.models.models')
    from app.models.models import Base

    # 2.x：registry.mappers（按实际表名匹配，最可靠）
    registry = getattr(Base, 'registry', None)
    if registry is not None:
        for mapper in registry.mappers:
            table = getattr(mapper, 'local_table', None)
            if table is not None and table.name == name:
                return mapper.class_

    # 1.x 兼容
    reg = getattr(Base, '_class_registry', None) or getattr(Base, '_sa_registry', None)
    if reg is not None:
        found = reg.get(name)
        if found is not None:
            return found
        guess = ''.join(w.capitalize() for w in name.split('_'))
        found = reg.get(guess)
        if found is not None:
            return found

    raise KeyError(f'未找到表 {name} 的 ORM 映射')
