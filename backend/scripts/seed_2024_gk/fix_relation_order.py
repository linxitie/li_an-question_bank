# -*- coding: utf-8 -*-
"""把某张卷的题序按题目真实题号重排（`question_order = question_number`）。

为什么需要它：`/api/questions/import/batch-parsed` 的 `question_order` 是
"追加序号"（`order_base = next_question_order(...)`）。只要一张卷**分批补录**
（比如首轮有题因超长/缺字段被拒，稍后只补那几题），补录的题就会排到卷尾，
学生端预览顺序与真实题号错位 —— 2024 国考卷 #4 实测 100 条里 60 条错位。

用法：
  python backend/scripts/seed_2024_gk/fix_relation_order.py --paper 4          # 只报告
  python backend/scripts/seed_2024_gk/fix_relation_order.py --paper 4 --apply   # 真改

安全边界：
  · 只改 `paper_question_relation.question_order`，**不碰题干/答案/选项/图片**；
  · 仅在"该卷所有关联题都有纯数字题号、且互不重复"时才动手，否则一条不改；
  · 改完立刻复算并打印 `order ↔ 题号` 不一致条数（期望 0）。
"""
import argparse
import os
import re
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                  "data", "question_bank.db")


def snapshot(db, paper_id):
    return db.execute(
        "select r.question_order, b.question_number, b.question_id "
        "from paper_question_relation r join question_bank b on b.question_id=r.question_id "
        "where r.paper_id=? order by r.question_order", (paper_id,)).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    rows = snapshot(db, args.paper)
    print(f"卷 #{args.paper} 关联 {len(rows)} 条")
    if not rows:
        print("没有关联题，什么都不用做")
        return 0

    nums = [n for _o, n, _q in rows]
    bad_nums = [n for n in nums if not re.fullmatch(r"\d+", str(n or ""))]
    dup = len(nums) != len(set(nums))
    print(f"非纯数字题号 {len(bad_nums)} 条，重复题号 {'有' if dup else '无'}")
    if bad_nums or dup:
        print("→ 不满足重排前提（要么有题号缺失/非数字，要么题号重复）。为保证不误伤，本次一条不改。")
        return 2

    mism = [(o, n) for o, n, _q in rows if str(o) != str(n)]
    print(f"当前 order↔题号 不一致 {len(mism)} 条，示例 {mism[:5]}")
    if not mism:
        print("已经对齐，无需改")
        return 0
    if not args.apply:
        print("（dry-run）加 --apply 才会写库")
        return 0

    with db:
        db.execute(
            "update paper_question_relation set question_order = ("
            " select cast(b.question_number as integer) from question_bank b "
            " where b.question_id = paper_question_relation.question_id) "
            "where paper_id=?", (args.paper,))
    after = snapshot(db, args.paper)
    mism_after = [(o, n) for o, n, _q in after if str(o) != str(n)]
    orders = [o for o, _n, _q in after]
    print(f"改完：order 数 {len(orders)}，去重 {len(set(orders))}，"
          f"min {min(orders)} / max {max(orders)}，不一致 {len(mism_after)} 条")
    return 0 if not mism_after else 1


if __name__ == "__main__":
    sys.exit(main())
