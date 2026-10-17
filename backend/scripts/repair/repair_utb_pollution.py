#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_utb_pollution.py — 清除 UTB 测试污染数据（问题1-R1）

来源诊断：
  backend/tests/test_batch_parsed_import.py 曾直连真实库运行，断言失败导致
  清理代码未执行，残留 10 道模板垃圾题（"人民警察基本素养测试要点N" +
  "UTB{8位hex}"标记）与 2 张污染试卷（paper_name 含 "UTB...直测"）。

功能：
  1. 动态定位污染集（不硬编码 qid，幂等可重跑）
  2. --dry-run（默认）：仅打印将删除的清单
  3. --apply：备份整库 → JSONL 审计 → 级联删除（relation → import_record
     → question_bank → exam_paper）
  4. --restore <audit.jsonl>：按审计日志逆序回插

运行方式：
  cd backend
  python scripts/repair_utb_pollution.py            # dry-run
  python scripts/repair_utb_pollution.py --apply    # 执行（先自动备份）
  python scripts/repair_utb_pollution.py --restore data/audit/utb_repair_xxx.jsonl
"""
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')
_BACKUP_DIR = os.path.join(_BACKEND_DIR, 'data', 'backups')
_AUDIT_DIR = os.path.join(_BACKEND_DIR, 'data', 'audit')

# 污染特征（与 text_parser.py UTB 正则保持一致 + 测试模板关键词）
UTB_RE = re.compile(r'UTB[a-f0-9]{8,}', re.IGNORECASE)
TEST_KEYWORD = '测试要点'


def _row_to_dict(cur, table, where_sql, params):
    """读取整行快照用于审计"""
    cur.execute(f"SELECT * FROM {table} WHERE {where_sql}", params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def find_pollution(cur):
    """动态定位污染集：返回 (question_rows, paper_rows, relation_rows, record_rows)"""
    # 1. 污染题目
    q_rows = _row_to_dict(
        cur, 'question_bank',
        "question_content LIKE '%UTB%' OR question_content LIKE '%测试要点%'", ())
    # 2. 污染试卷（双轨入库产生）
    p_rows = _row_to_dict(
        cur, 'exam_paper',
        "paper_name LIKE '%UTB%' AND paper_name LIKE '%直测%'", ())
    qids = [r['question_id'] for r in q_rows]
    pids = [r['paper_id'] for r in p_rows]
    # 3. 级联关联
    rel_rows, rec_rows = [], []
    if qids:
        ph = ','.join('?' * len(qids))
        rel_rows = _row_to_dict(cur, 'paper_question_relation',
                                f"question_id IN ({ph})", qids)
    if pids:
        ph = ','.join('?' * len(pids))
        rec_rows = _row_to_dict(cur, 'question_import_record',
                                f"paper_id IN ({ph})", pids)
    return q_rows, p_rows, rel_rows, rec_rows


def do_backup():
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(_BACKUP_DIR, f'backup_pre_utb_{ts}.sqlite')
    # WAL 模式下先 checkpoint 保证备份完整
    con = sqlite3.connect(_DB_PATH)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(_DB_PATH, dst)
    return dst


def do_apply():
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    q_rows, p_rows, rel_rows, rec_rows = find_pollution(cur)
    total = len(q_rows) + len(p_rows) + len(rel_rows) + len(rec_rows)
    if total == 0:
        print('✅ 未发现污染数据（幂等：可能已修复过），0 changes。')
        con.close()
        return

    backup_path = do_backup()
    print(f'📦 已备份整库 → {backup_path}')

    os.makedirs(_AUDIT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    audit_path = os.path.join(_AUDIT_DIR, f'utb_repair_{ts}.jsonl')
    audit_f = open(audit_path, 'w', encoding='utf-8')

    def audit(table, pk_col, row):
        audit_f.write(json.dumps({
            'table': table, 'pk': row[pk_col], 'snapshot': row,
        }, ensure_ascii=False) + '\n')

    try:
        # 删除顺序：先子表/关联，后主表（试卷最后，便于审计逆序恢复）
        for r in rel_rows:
            cur.execute('DELETE FROM paper_question_relation WHERE paper_id=? AND question_id=?',
                        (r['paper_id'], r['question_id']))
            audit('paper_question_relation', 'question_id', dict(r))
        for r in rec_rows:
            cur.execute('DELETE FROM question_import_record WHERE import_id=?',
                        (r['import_id'],))
            audit('question_import_record', 'import_id', dict(r))

        # 清理**全部**引用 question_id 的子表（自动发现）。
        # 历史遗漏：本脚本原先只清 paper_question_relation，其余子表全部残留 ——
        # 其中 question_detail_category.question_id 带 UNIQUE 约束
        # (uk_question_category)，孤儿行会在 SQLite 复用主键时
        # 撞唯一约束，导致题目批量导入整批 500 失败。
        qids = [r['question_id'] for r in q_rows]
        if qids:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            _all = [x[0] for x in cur.fetchall()]
            child_tables = []
            for t in _all:
                if t == 'question_bank' or t.startswith('sqlite_'):
                    continue
                cols = [x[1] for x in cur.execute(f'PRAGMA table_info("{t}")').fetchall()]
                if 'question_id' in cols:
                    child_tables.append(t)
            marks = ','.join('?' * len(qids))
            for t in sorted(child_tables):
                try:
                    n = cur.execute(
                        f'DELETE FROM "{t}" WHERE question_id IN ({marks})', qids).rowcount
                    if n:
                        print(f'  已清理 {t}: {n} 行')
                        audit(t, 'question_id', {'count': n})
                except Exception as te:  # noqa: BLE001 — 单表失败不阻断其余清理
                    print(f'  (跳过 {t}: {te})')

        for r in q_rows:
            cur.execute('DELETE FROM question_bank WHERE question_id=?',
                        (r['question_id'],))
            audit('question_bank', 'question_id', dict(r))
        for r in p_rows:
            cur.execute('DELETE FROM exam_paper WHERE paper_id=?',
                        (r['paper_id'],))
            audit('exam_paper', 'paper_id', dict(r))
        con.commit()
        audit_f.close()
        print(f'✅ 修复完成：删除题目 {len(q_rows)}、试卷 {len(p_rows)}、'
              f'关联 {len(rel_rows)}、导入记录 {len(rec_rows)}')
        print(f'📝 审计日志 → {audit_path}')
        print(f'↩️  回滚命令：python scripts/repair_utb_pollution.py --restore {audit_path}')
    except Exception:
        con.rollback()
        audit_f.close()
        raise
    finally:
        con.close()


def do_restore(audit_path):
    """按审计日志逆序回插"""
    if not os.path.exists(audit_path):
        print(f'❌ 审计文件不存在: {audit_path}')
        sys.exit(1)
    con = sqlite3.connect(_DB_PATH)
    cur = con.cursor()
    with open(audit_path, encoding='utf-8') as f:
        entries = [json.loads(line) for line in f if line.strip()]
    # 逆序：试卷 → 题目 → 记录 → 关联
    restored = 0
    for e in reversed(entries):
        table, row = e['table'], e['snapshot']
        cols = ','.join(row.keys())
        ph = ','.join('?' * len(row))
        try:
            cur.execute(f'INSERT OR IGNORE INTO {table} ({cols}) VALUES ({ph})',
                        list(row.values()))
            restored += 1
        except sqlite3.IntegrityError:
            pass  # 已存在（幂等）
    con.commit()
    con.close()
    print(f'✅ 已回插 {restored}/{len(entries)} 行（来自 {audit_path}）')


def do_dry_run():
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    q_rows, p_rows, rel_rows, rec_rows = find_pollution(cur)
    print('=' * 60)
    print('[DRY RUN] UTB 污染数据清单（未修改任何数据）')
    print('=' * 60)
    print(f'\n◆ 将删除题目 {len(q_rows)} 道：')
    for r in q_rows:
        print(f"  qid={r['question_id']} content={str(r['question_content'])[:60]}")
    print(f'\n◆ 将删除试卷 {len(p_rows)} 张：')
    for r in p_rows:
        print(f"  paper_id={r['paper_id']} name={r['paper_name']}")
    print(f'\n◆ 级联删除：关联 {len(rel_rows)} 条、导入记录 {len(rec_rows)} 条')
    print(f'\n合计 {len(q_rows)+len(p_rows)+len(rel_rows)+len(rec_rows)} 行。')
    print('确认无误后执行：python scripts/repair_utb_pollution.py --apply')
    con.close()


if __name__ == '__main__':
    if '--restore' in sys.argv:
        idx = sys.argv.index('--restore')
        do_restore(sys.argv[idx + 1])
    elif '--apply' in sys.argv:
        do_apply()
    else:
        do_dry_run()
