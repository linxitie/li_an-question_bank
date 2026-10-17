#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""行测题型主数据迁移（幂等）

背景
----
``question_bank.type_id`` 是 NOT NULL 外键。实测 ``question_type`` 表中
**subject_id=1（行测）零行**（现有 7 行属公专、6 行属申论），行测题目无法入库。

本脚本为行测补齐客观题型主数据。

安全约束（红线条目，违反即造成存量数据损坏）
------------------------------------------
1. **只按 (type_name, subject_id) 精确匹配后插入**，绝不 UPDATE 既有行
2. **绝不触碰 subject_id=3（公专）与 subject_id=2（申论）** 的任何行
3. ``type_code`` 必须带 subject_id 前缀（``auto_1_xxx``）—— 该列有 UNIQUE 约束，
   与既有 ``_get_or_create_type`` 的生成规范保持一致
4. 写入前强制备份；``--rollback`` 仅按 subject_id=1 定向删除
5. 可重复执行，结果幂等

用法
----
    python scripts/migrate_xingce_question_types.py --dry-run
    python scripts/migrate_xingce_question_types.py --apply
    python scripts/migrate_xingce_question_types.py --rollback
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BACKEND_DIR, "data", "question_bank.db")

SUBJECT_XINGCE = 1
# 行测语料实测：全部为客观题。判断题按既有 type_detection.md 约定归入单选题
#（答案 对/正确/是/√→A，错/错误/否/×→B，由 canonical_answer 完成）。
# 不创建 论述/写作 —— 行测语料实测 0 例。
TARGETS = [
    # (type_name, type_code, description, is_objective, sort_order)
    ("单选题", "auto_1_单选题", "行测单项选择题", 1, 1),
    ("多选题", "auto_1_多选题", "行测多项选择题", 1, 2),
]


def snapshot(cur) -> dict:
    return {
        r[0]: r[1:]
        for r in cur.execute(
            "select type_id, type_name, type_code, subject_id, description,"
            " is_objective, sort_order from question_type")
    }


def report(cur, tag: str) -> None:
    rows = cur.execute(
        "select subject_id, count(*) from question_type group by 1 order by 1"
    ).fetchall()
    print("  [%s] subject_id 分布: %s" % (tag, dict(rows)))


def main() -> int:
    ap = argparse.ArgumentParser(description="行测题型主数据迁移（幂等）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="仅预览，不写库")
    g.add_argument("--apply", action="store_true", help="写入")
    g.add_argument("--rollback", action="store_true", help="删除 subject_id=1 的行")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print("[error] 数据库不存在: %s" % DB_PATH)
        return 2

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    before = snapshot(cur)
    print("迁移前 question_type 行数: %d" % len(before))
    report(cur, "before")

    # ── rollback ────────────────────────────────────────────────────────
    if args.rollback:
        ids = [r[0] for r in cur.execute(
            "select type_id from question_type where subject_id=?", (SUBJECT_XINGCE,))]
        if not ids:
            print("[rollback] subject_id=1 无行，无需回滚")
            con.close()
            return 0
        cur.execute("delete from question_type where subject_id=?", (SUBJECT_XINGCE,))
        con.commit()
        after = snapshot(cur)
        print("[rollback] 已删除 type_id=%s" % ids)
        print("  行数 %d -> %d" % (len(before), len(after)))
        kept = all(before[k] == after[k] for k in after)
        print("  其余行逐字段未变: %s" % kept)
        report(cur, "after")
        con.close()
        return 0 if kept else 1

    # ── dry-run / apply ─────────────────────────────────────────────────
    todo = []
    for name, code, desc, obj, order in TARGETS:
        exist = cur.execute(
            "select type_id from question_type where type_name=? and subject_id=?",
            (name, SUBJECT_XINGCE)).fetchone()
        if exist:
            print("  已存在，跳过: %s (type_id=%s)" % (name, exist[0]))
            continue
        code_taken = cur.execute(
            "select type_id from question_type where type_code=?", (code,)).fetchone()
        if code_taken:
            print("  [冲突] type_code %s 已被 type_id=%s 占用，跳过"
                  % (code, code_taken[0]))
            continue
        todo.append((name, code, desc, obj, order))

    if not todo:
        print("无需变更（幂等）")
        con.close()
        return 0

    print("待插入 %d 行:" % len(todo))
    for t in todo:
        print("   type_name=%-6s type_code=%-14s is_objective=%d sort_order=%d"
              % (t[0], t[1], t[3], t[4]))

    if args.dry_run:
        print("[dry-run] 未写库")
        con.close()
        return 0

    # 写入前强制备份
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(DB_PATH),
                       "question_bank.db.bak_xingce_types_%s" % ts)
    con.commit()
    con.close()
    shutil.copy2(DB_PATH, bak)
    print("已备份: %s (%d 字节)" % (os.path.basename(bak), os.path.getsize(bak)))

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for name, code, desc, obj, order in todo:
        cur.execute(
            "insert into question_type"
            " (type_name, type_code, subject_id, description, is_objective, sort_order)"
            " values (?,?,?,?,?,?)",
            (name, code, SUBJECT_XINGCE, desc, obj, order))
    con.commit()

    # ── 验证 ────────────────────────────────────────────────────────────
    after = snapshot(cur)
    print("迁移后 question_type 行数: %d" % len(after))
    report(cur, "after")

    ok = True
    n_xc = cur.execute("select count(*) from question_type where subject_id=?",
                       (SUBJECT_XINGCE,)).fetchone()[0]
    n_2 = cur.execute("select count(*) from question_type where subject_id=2").fetchone()[0]
    n_3 = cur.execute("select count(*) from question_type where subject_id=3").fetchone()[0]
    print("  行测行数 = %d (期望 %d)" % (n_xc, len(TARGETS)))
    print("  申论行数 = %d (期望 6，未变)" % n_2)
    print("  公专行数 = %d (期望 7，未变)" % n_3)
    ok = ok and n_xc == len(TARGETS) and n_2 == 6 and n_3 == 7

    touched = [k for k in before if before[k] != after.get(k)]
    print("  既有行被改动: %s" % (touched if touched else "无"))
    ok = ok and not touched

    added = sorted(k for k in after if k not in before)
    print("  新增 type_id: %s" % added)

    # 幂等：重复插入应被跳过
    dup = cur.execute(
        "select count(*) from question_type where subject_id=? and type_name in (?,?)",
        (SUBJECT_XINGCE, "单选题", "多选题")).fetchone()[0]
    print("  幂等校验（单选+多选 行数）= %d (期望 %d)" % (dup, len(TARGETS)))
    ok = ok and dup == len(TARGETS)

    con.close()
    print("RESULT = %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())