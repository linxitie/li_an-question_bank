# -*- coding: utf-8 -*-
"""
purge_orphan_detail_category.py — 清理 question_detail_category 孤儿行（可重复执行）

背景（真实生产故障）：
    question_detail_category.question_id 上有 UNIQUE 约束(uk_question_category)，
    且其外键为 NO ACTION（无级联），同时本项目 PRAGMA foreign_keys=0
    （FK 约束实际不生效）→ 删除 question_bank 记录不会级联清理明细行。
    孤儿行堆积后，SQLite 复用已释放的 question_id，新题分配到同 id 时
    INSERT 撞唯一约束 → 题目批量导入整批回滚、接口 500。

    孤儿行历史上主要来自硬删除脚本（clean_questions.py 曾漏清本表），
    代码已修复；本脚本用于清理历史残留并作为定期自愈工具。

孤儿行定义：question_id 在 question_bank 中不存在。这些行不可能被任何题目
引用，删除安全。脚本会先导出 JSON 备份，支持 --dry-run 预览。

用法:
    cd backend
    python scripts/purge_orphan_detail_category.py --dry-run    # 预览
    python scripts/purge_orphan_detail_category.py              # 执行
    python scripts/purge_orphan_detail_category.py --backup D:\\path\\backup.json
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine

DEFAULT_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def main():
    dry_run = '--dry-run' in sys.argv
    backup_path = None
    if '--backup' in sys.argv:
        i = sys.argv.index('--backup')
        if i + 1 < len(sys.argv):
            backup_path = sys.argv[i + 1]

    with engine.connect() as conn:
        fk_on = conn.execute(text('PRAGMA foreign_keys')).scalar()
        q_total = conn.execute(text('SELECT COUNT(*) FROM question_bank')).scalar()
        d_total = conn.execute(text('SELECT COUNT(*) FROM question_detail_category')).scalar()
        orphans = conn.execute(text("""
            SELECT d.category_id, d.question_id, d.question_type_detail
            FROM question_detail_category d
            LEFT JOIN question_bank q ON q.question_id = d.question_id
            WHERE q.question_id IS NULL
            ORDER BY d.question_id
        """)).fetchall()

        print(f'PRAGMA foreign_keys = {fk_on}'
              f'{"（FK 未启用，故删除题目不会级联，本脚本必要）" if not fk_on else ""}')
        print(f'question_bank            : {q_total}')
        print(f'question_detail_category : {d_total}')
        print(f'孤儿明细行               : {len(orphans)}')

        if not orphans:
            print('\n无需清理，库已是健康状态。')
            return 0

        if backup_path is None:
            os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)
            backup_path = os.path.join(
                DEFAULT_BACKUP_DIR,
                f'orphan_detail_backup_{time.strftime("%Y%m%d_%H%M%S")}.json'
            )
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump([{'category_id': r[0], 'question_id': r[1], 'question_type_detail': r[2]}
                       for r in orphans], f, ensure_ascii=False, indent=1)
        print(f'\n已备份 {len(orphans)} 条孤儿行 → {backup_path}')

        if dry_run:
            print('\n[dry-run] 未执行删除。去掉 --dry-run 即可实际清理。')
            return 0

    # 独立事务执行删除
    with engine.begin() as conn:
        n = conn.execute(text("""
            DELETE FROM question_detail_category
            WHERE question_id NOT IN (SELECT question_id FROM question_bank)
        """)).rowcount

    with engine.connect() as conn:
        left = conn.execute(text("""
            SELECT COUNT(*) FROM question_detail_category d
            LEFT JOIN question_bank q ON q.question_id = d.question_id
            WHERE q.question_id IS NULL
        """)).scalar()
        q_after = conn.execute(text('SELECT COUNT(*) FROM question_bank')).scalar()

    print(f'\n已删除孤儿行: {n}')
    print(f'清理后: question_bank={q_after}（应保持不变）  剩余孤儿={left}')
    assert q_after == q_total, 'question_bank 行数被改动！异常中止'
    print('完成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
