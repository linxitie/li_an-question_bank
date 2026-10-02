#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""申论科目主数据迁移（幂等 + 可回滚）。

背景
----
本库 ``question_subject`` 原本只有两行：``subject_id=1 行测``、``subject_id=3 公专``，
``subject_id=2`` 是空位，正好留给申论。``question_type`` 现有 7 个题型全部绑定
``subject_id=3``（公专），申论需要自己的题型。

用户已选定**乙方案**：新增 ``question_bank.requirements TEXT`` 存题目要求，
不使用 JSON 数组，也不新建"题目-要求"关联表。

真实表结构（本脚本运行时用 PRAGMA 自查，不硬编码）
------------------------------------------------
question_subject(subject_id, subject_name, subject_code, description, sort_order, status)
question_type(type_id, type_name, type_code, subject_id, description, is_objective, sort_order)
question_bank(question_id, subject_id, type_id, ..., score, group_id, parent_id,
              question_number, shenlun_subcategory, ...)   # 无 requirements 列

用法
----
    python migrate_shenlun_subject.py                # dry-run，只打印将要做什么
    python migrate_shenlun_subject.py --apply        # 真执行（先自动备份）
    python migrate_shenlun_subject.py --rollback     # 回滚本次迁移
    python migrate_shenlun_subject.py --verify        # 只校验迁移是否已生效
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# 相对本文件定位到 backend/data/question_bank.db，避免依赖调用时的工作目录
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'question_bank.db')
DB_PATH = os.path.normpath(DB_PATH)

SUBJECT_NAME = '申论'
SUBJECT_DESC = '申论主观题（材料阅读+五大题型）'

# 申论五大题型：(类型名, 是否客观题, 说明)
# is_objective=0 表示主观题，与现有公专主观题（论述题/写作题/简答题）保持一致
SHENLUN_TYPES = [
    ('归纳概括', 0, '概括材料中的要点'),
    ('综合分析', 0, '分析材料中的问题/原因/关系'),
    ('提出对策', 0, '针对问题提出解决办法'),
    ('贯彻执行', 0, '公文/应用文写作'),
    ('文章写作', 0, '议论文/文章写作'),
]

REQ_COLUMN = 'requirements'


# --------------------------------------------------------------------------- #
# 基础设施
# --------------------------------------------------------------------------- #
def log(msg=''):
    print(msg, flush=True)


def connect(db_path=DB_PATH):
    if not os.path.exists(db_path):
        sys.exit('[FATAL] 数据库不存在: %s' % db_path)
    return sqlite3.connect(db_path)


def table_exists(cur, name):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def columns(cur, table):
    """返回该表实际存在的列名集合。"""
    return {r[1] for r in cur.execute('PRAGMA table_info(%s)' % table)}


def backup(db_path):
    """迁移前自动备份，返回备份路径。失败则拒绝继续。"""
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = db_path + '.bak_shenlun_' + stamp
    try:
        # 用 sqlite3 自身 backup API，保证在线一致性（WAL 模式下文件拷贝可能拿到半截数据）
        src = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(dst)
        with dst_conn:
            src.backup(dst_conn)
        dst_conn.close()
        src.close()
    except Exception as exc:                                  # noqa: BLE001
        sys.exit('[FATAL] 备份失败，已中止迁移: %s' % exc)
    log('  [备份] %s (%d bytes)' % (dst, os.path.getsize(dst)))
    return dst


# --------------------------------------------------------------------------- #
# 迁移动作（每个动作都返回 (描述, 是否需要变更)）
# --------------------------------------------------------------------------- #
def find_shenlun_subject(cur):
    """返回已存在的申论 subject_id，没有则返回 None。先按名称找，再看 2 号空位。"""
    cur.execute("SELECT subject_id FROM question_subject WHERE subject_name=?", (SUBJECT_NAME,))
    row = cur.fetchone()
    if row:
        return row[0]
    return None


def pick_free_subject_id(cur):
    """挑一个未被占用的 subject_id：优先 2（历史空位），否则 max+1。不硬编码。"""
    cur.execute("SELECT COALESCE(MAX(subject_id),0) FROM question_subject")
    max_id = cur.fetchone()[0] or 0
    cur.execute("SELECT subject_id FROM question_subject")
    used = {r[0] for r in cur.fetchall()}
    if 2 not in used:
        return 2
    cand = max_id + 1
    while cand in used:
        cand += 1
    return cand


def apply(cur, log_changes):
    """执行全部迁移。log_changes=True 时才真正写库。"""
    actions = []

    # --- 1. question_subject 补申论行 ---
    sid = find_shenlun_subject(cur)
    if sid is None:
        sid = pick_free_subject_id(cur)
        actions.append('question_subject 插入申论行 subject_id=%s' % sid)
        if log_changes:
            cur.execute(
                'INSERT INTO question_subject'
                ' (subject_id, subject_name, subject_code, description, sort_order, status)'
                ' VALUES (?,?,?,?,?,?)',
                (sid, SUBJECT_NAME, 'auto_' + SUBJECT_NAME, SUBJECT_DESC, 1, 1))
    else:
        actions.append('question_subject 申论行已存在 subject_id=%s（跳过）' % sid)

    # --- 2. question_bank 增 requirements 列 ---
    cols = columns(cur, 'question_bank')
    if REQ_COLUMN in cols:
        actions.append('question_bank.%s 列已存在（跳过）' % REQ_COLUMN)
    else:
        actions.append('question_bank ADD COLUMN %s TEXT' % REQ_COLUMN)
        if log_changes:
            cur.execute('ALTER TABLE question_bank ADD COLUMN %s TEXT' % REQ_COLUMN)

    # --- 3. question_type 申论题型绑 subject_id ---
    cur.execute('SELECT type_id, type_name FROM question_type WHERE subject_id=?', (sid,))
    existing = {r[1] for r in cur.fetchall()}
    cur.execute('SELECT COALESCE(MAX(type_id),0) FROM question_type')
    next_tid = (cur.fetchone()[0] or 0) + 1
    added = 0
    for order, (name, is_obj, desc) in enumerate(SHENLUN_TYPES, start=1):
        if name in existing:
            actions.append('question_type「%s」已存在（跳过）' % name)
            continue
        actions.append('question_type 插入「%s」-> subject_id=%s' % (name, sid))
        if log_changes:
            cur.execute(
                'INSERT INTO question_type'
                ' (type_id, type_name, type_code, subject_id, description, is_objective, sort_order)'
                ' VALUES (?,?,?,?,?,?,?)',
                (next_tid, name, 'auto_申论_' + name, sid, desc, is_obj, order))
            next_tid += 1
        added += 1
    if not added:
        actions.append('question_type 申论题型已齐全（跳过）')

    return actions, sid


def rollback(cur, log_changes):
    """回滚本次迁移。只删本次新建的东西，不动任何历史公专/行测数据。"""
    actions = []

    sid = find_shenlun_subject(cur)
    if sid is None:
        actions.append('未找到申论科目行，无需回滚')
        return actions, None

    # 先删绑到申论的题型，再删申论题型名占用的 code
    cur.execute('SELECT COUNT(*) FROM question_type WHERE subject_id=?', (sid,))
    n = cur.fetchone()[0]
    actions.append('删除 question_type 中 subject_id=%s 的 %d 个题型' % (sid, n))
    if log_changes:
        cur.execute('DELETE FROM question_type WHERE subject_id=?', (sid,))

    actions.append('删除 question_subject 申论行 subject_id=%s' % sid)
    if log_changes:
        cur.execute('DELETE FROM question_subject WHERE subject_id=?', (sid,))

    if REQ_COLUMN in columns(cur, 'question_bank'):
        actions.append('question_bank 删除 %s 列（SQLite 3.35+ 支持 DROP COLUMN）' % REQ_COLUMN)
        if log_changes:
            try:
                cur.execute('ALTER TABLE question_bank DROP COLUMN %s' % REQ_COLUMN)
            except Exception as exc:                           # noqa: BLE001
                actions.append('  [跳过] 老版本 SQLite 不支持 DROP COLUMN: %s' % exc)
    return actions, sid


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def verify(cur):
    """返回 (是否全部通过, 明细行列表)"""
    rows = []
    ok = True

    sid = find_shenlun_subject(cur)
    if sid is None:
        rows.append('[FAIL] question_subject 缺申论行')
        ok = False
    else:
        rows.append('[ OK ] question_subject 申论行 subject_id=%s' % sid)

    if REQ_COLUMN in columns(cur, 'question_bank'):
        rows.append('[ OK ] question_bank.%s 列存在' % REQ_COLUMN)
    else:
        rows.append('[FAIL] question_bank 缺 %s 列' % REQ_COLUMN)
        ok = False

    if sid is not None:
        cur.execute('SELECT type_name FROM question_type WHERE subject_id=? ORDER BY sort_order', (sid,))
        names = [r[0] for r in cur.fetchall()]
        missing = [n for n, _, _ in SHENLUN_TYPES if n not in names]
        if missing:
            rows.append('[FAIL] 申论题型缺失: %s' % '、'.join(missing))
            ok = False
        else:
            rows.append('[ OK ] 申论题型齐全: %s' % '、'.join(names))

    cur.execute('SELECT COUNT(*) FROM question_bank WHERE subject_id=3')
    rows.append('[INFO] 公专题目数 subject_id=3: %d（迁移不应改变此数）'
                % cur.fetchone()[0])
    return ok, rows


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description='申论科目主数据迁移（幂等 + 可回滚）')
    ap.add_argument('--apply', action='store_true', help='真正写入数据库（默认 dry-run）')
    ap.add_argument('--rollback', action='store_true', help='回滚本次迁移')
    ap.add_argument('--verify', action='store_true', help='只校验迁移是否生效')
    ap.add_argument('--db', default=DB_PATH, help='数据库路径（默认 backend/data/question_bank.db）')
    args = ap.parse_args()

    log('=' * 72)
    log('申论主数据迁移  db=%s' % args.db)
    log('=' * 72)

    con = connect(args.db)
    cur = con.cursor()
    mode = 'APPLY' if (args.apply or args.rollback) else 'DRY-RUN'
    log('模式: %s' % mode)
    log('')

    if args.verify:
        ok, rows = verify(cur)
        for r in rows:
            log('  ' + r)
        log('')
        log('校验结果: %s' % ('PASS' if ok else 'FAIL'))
        con.close()
        sys.exit(0 if ok else 1)

    if not args.apply and not args.rollback:
        log('[提示] dry-run 模式，未改动任何数据。确认无误后加 --apply 执行。')
        log('')

    if args.apply or args.rollback:
        log('[安全] 先备份数据库...')
        backup(args.db)
        log('')

    try:
        if args.rollback:
            actions, _ = rollback(cur, True)
        else:
            actions, _ = apply(cur, args.apply)
        for a in actions:
            log('  %s %s' % ('[写入]' if args.apply else '[计划]', a))
        if args.apply or args.rollback:
            con.commit()
            log('')
            log('已提交。')
        con.close()
    except Exception as exc:                                   # noqa: BLE001
        con.rollback()
        log('')
        log('[FATAL] 迁移失败并已回滚事务: %s' % exc)
        sys.exit(1)

    # 迁移后自检
    con = connect(args.db)
    ok, rows = verify(con.cursor())
    con.close()
    log('')
    log('-' * 72)
    for r in rows:
        log('  ' + r)
    log('校验结果: %s' % ('PASS' if ok else 'FAIL'))
    if not args.apply and not args.rollback:
        log('')
        log('提醒：以上为 dry-run，实际数据未改动。')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()