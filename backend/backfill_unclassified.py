# -*- coding: utf-8 -*-
"""
一次性回填脚本：将 66 道 gongzhuan_subcategory='无' 的历史题重新归类。

用法：
  python backend/backfill_unclassified.py           # dry-run，只打印映射与校验，不写库
  python backend/backfill_unclassified.py --apply   # 实际写入 question_bank 与 question_detail_category

说明：
  这 66 道题均为公安专业（subject_id=3），因批量导入时分类失败被静默落默认值「无」。
  映射由逐题阅读题干后人工判定，仅覆盖 66 道「无」题，不触碰已归类的 727 道。
"""
import sqlite3
import sys
import os

# question_id -> 新 gongzhuan_subcategory
# 职业素养(9) / 基础知识(31) / 基本警务能力(26)
MAPPING = {
    # —— 职业素养（职业道德/纪律/廉洁/警察形象/核心价值观）——
    672: "职业素养", 677: "职业素养", 725: "职业素养", 773: "职业素养",
    808: "职业素养", 898: "职业素养", 903: "职业素养", 907: "职业素养",
    939: "职业素养",
    # —— 基础知识（法律/宪法/刑法/治安/公安体制/法治）——
    671: "基础知识", 679: "基础知识", 681: "基础知识", 684: "基础知识",
    687: "基础知识", 693: "基础知识", 696: "基础知识", 740: "基础知识",
    745: "基础知识", 751: "基础知识", 774: "基础知识", 775: "基础知识",
    786: "基础知识", 815: "基础知识", 825: "基础知识", 827: "基础知识",
    856: "基础知识", 861: "基础知识", 863: "基础知识", 865: "基础知识",
    877: "基础知识", 888: "基础知识", 891: "基础知识", 892: "基础知识",
    897: "基础知识", 914: "基础知识", 936: "基础知识", 937: "基础知识",
    958: "基础知识", 978: "基础知识", 979: "基础知识",
    # —— 基本警务能力（巡逻/盘查/检查/处置/防范/勤务/研判）——
    708: "基本警务能力", 709: "基本警务能力", 712: "基本警务能力",
    713: "基本警务能力", 714: "基本警务能力", 723: "基本警务能力",
    744: "基本警务能力", 747: "基本警务能力", 757: "基本警务能力",
    759: "基本警务能力", 760: "基本警务能力", 761: "基本警务能力",
    765: "基本警务能力", 768: "基本警务能力", 769: "基本警务能力",
    787: "基本警务能力", 819: "基本警务能力", 840: "基本警务能力",
    849: "基本警务能力", 871: "基本警务能力", 881: "基本警务能力",
    884: "基本警务能力", 920: "基本警务能力", 970: "基本警务能力",
    976: "基本警务能力", 981: "基本警务能力",
}

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'question_bank.db')


def main():
    apply = '--apply' in sys.argv
    db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) if not apply else sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    rows = cur.execute(
        "SELECT question_id, question_content FROM question_bank "
        "WHERE status=1 AND gongzhuan_subcategory='无' ORDER BY question_id"
    ).fetchall()

    print(f"待回填题目数: {len(rows)}")
    print(f"映射条目数: {len(MAPPING)}")
    missing = [r['question_id'] for r in rows if r['question_id'] not in MAPPING]
    extra = [qid for qid in MAPPING if qid not in {r['question_id'] for r in rows}]
    print(f"未在映射中的「无」题: {missing or '无'}")
    print(f"映射中但非「无」的题: {extra or '无'}")

    if not apply:
        print("\n=== dry-run（不写库）逐题映射 ===")
        for r in rows:
            qid = r['question_id']
            new = MAPPING.get(qid, '无')
            snippet = (r['question_content'] or '').replace('\n', ' ')[:42]
            print(f"  [{qid}] -> {new}  | {snippet}")
        print("\n提示：确认无误后运行 `python backend/backfill_unclassified.py --apply` 写入。")
        db.close()
        return

    # 实际写入
    n_qb = 0
    n_detail = 0
    for r in rows:
        qid = r['question_id']
        new = MAPPING.get(qid)
        if not new:
            continue
        cur.execute("UPDATE question_bank SET gongzhuan_subcategory=? WHERE question_id=?", (new, qid))
        n_qb += cur.rowcount
        cur.execute("UPDATE question_detail_category SET gongzhuan_subcategory=? WHERE question_id=?", (new, qid))
        n_detail += cur.rowcount
    db.commit()

    # 校验
    left = cur.execute(
        "SELECT COUNT(*) FROM question_bank WHERE status=1 AND gongzhuan_subcategory='无'"
    ).fetchone()[0]
    dist = cur.execute(
        "SELECT gongzhuan_subcategory, COUNT(*) c FROM question_bank WHERE status=1 "
        "GROUP BY gongzhuan_subcategory ORDER BY c DESC"
    ).fetchall()
    print(f"\n✅ 已写 question_bank: {n_qb} 行，question_detail_category: {n_detail} 行")
    print(f"   回填后 status=1 且 gongzhuan_subcategory='无' 剩余: {left} 道")
    print("   gongzhuan_subcategory 分布:")
    for d in dist:
        print(f"     {d['gongzhuan_subcategory']}: {d['c']}")
    db.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
