#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_question_groups.py — 复合题（题组）数据层迁移（B1）

内容：
  1. 新表 question_groups：由 SQLAlchemy Base.metadata.create_all 自动创建
  2. 旧表 question_bank 加 5 列：group_id/parent_id/question_level/sort_order/question_number
     + 索引 idx_group_id（SQLite ALTER TABLE 仅支持加列，幂等：列已存在则跳过）

五件套：--dry-run 默认 / --apply 显式 / 自动备份 / JSONL 审计 / 幂等可重跑

用法:
  cd backend
  python scripts/migrate_question_groups.py            # dry-run
  python scripts/migrate_question_groups.py --apply    # 执行
"""
import sys
import os
import json
import shutil
import sqlite3
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')

# (列名, DDL 片段)——与 models.QuestionBank 定义一致
NEW_COLUMNS = [
    ('group_id', "INTEGER DEFAULT 0"),
    ('parent_id', "INTEGER DEFAULT 0"),
    ('question_level', "INTEGER DEFAULT 1"),
    ('sort_order', "INTEGER DEFAULT 0"),
    ('question_number', "VARCHAR(10)"),
]


def _backup():
    backup_dir = os.path.join(_BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'backup_pre_qgroup_{ts}.sqlite')
    con = sqlite3.connect(_DB_PATH)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(_DB_PATH, dst)
    return dst


def _existing_columns(con):
    return {r[1] for r in con.execute('PRAGMA table_info(question_bank)')}


def do_dry_run():
    from app.core.database import Base
    from app.models.models import QuestionGroup  # noqa: F401 注册模型
    tables = [t for t in Base.metadata.tables]
    con = sqlite3.connect(_DB_PATH)
    cols = _existing_columns(con)
    con.close()
    print('=' * 60)
    print('[DRY RUN] 复合题数据层迁移计划（未修改）')
    print('=' * 60)
    print(f"新表 question_groups: {'已存在' if 'question_groups' in tables else '将由 create_all 创建'}")
    print('question_bank 待加列:')
    for name, ddl in NEW_COLUMNS:
        status = '已存在（跳过）' if name in cols else f'ALTER TABLE ADD COLUMN {name} {ddl}'
        print(f'  {name}: {status}')
    print('索引: idx_group_id（随建表/加列创建）')


def do_apply():
    from sqlalchemy import text
    from app.core.database import Base, engine
    from app.models.models import QuestionGroup  # noqa: F401 注册模型

    backup = _backup()
    logger.info(f"已备份整库 → {backup}")

    # 1) 新表（幂等：checkfirst=True）
    Base.metadata.create_all(engine, checkfirst=True)
    logger.info("question_groups 表就绪")

    # 2) 旧表加列（幂等）
    audit_path = os.path.join(_BACKEND_DIR, 'data', 'audit',
                              f'qgroup_migrate_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl')
    os.makedirs(os.path.dirname(audit_path), exist_ok=True)
    con = engine.raw_connection()
    try:
        cols = _existing_columns(con)
        applied = []
        for name, ddl in NEW_COLUMNS:
            if name in cols:
                logger.info(f"列 {name} 已存在，跳过（幂等）")
                continue
            # raw_connection 是 DBAPI 原生连接，execute 接受纯字符串 SQL
            con.execute(f'ALTER TABLE question_bank ADD COLUMN {name} {ddl}')
            applied.append(name)
            logger.info(f"已加列: {name}")
        # 3) 索引（幂等：查重后创建）
        idx = con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_group_id'"
        ).fetchone()
        if not idx:
            con.execute('CREATE INDEX idx_group_id ON question_bank(group_id)')
            applied.append('idx_group_id')
            logger.info("已建索引: idx_group_id")
        con.commit()
        with open(audit_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'applied': applied, 'backup': backup},
                               ensure_ascii=False) + '\n')
        logger.info(f"迁移完成: {applied or '无变更（幂等）'}")
        logger.info(f"审计 → {audit_path}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='复合题数据层迁移')
    p.add_argument('--apply', action='store_true', help='实际执行（默认dry-run）')
    args = p.parse_args()
    if args.apply:
        do_apply()
    else:
        do_dry_run()
