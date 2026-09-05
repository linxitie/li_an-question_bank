"""
修复试卷状态：ENDED->DRAFT + 同步question_count

功能：
1. 将有题目关联的ENDED试卷恢复为DRAFT状态
2. 从paper_question_relation表反算question_count并同步
3. 幂等可重复执行

用法：
  python fix_paper_status.py --dry-run    # 预览修复内容
  python fix_paper_status.py              # 执行修复
"""
import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'question_bank.db')


def fix(dry_run=True):
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("=" * 60)
    print(f"[INFO] 试卷状态修复脚本 -- {'预览模式' if dry_run else '执行模式'}")
    print(f"[INFO] 数据库: {DB_PATH}")
    print(f"[INFO] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 统计每个paper的实际关联题目数
    c.execute('''
        SELECT paper_id, COUNT(*) as cnt
        FROM paper_question_relation
        GROUP BY paper_id
    ''')
    rel_map = dict(c.fetchall())  # {paper_id: actual_count}
    print(f"\n[INFO] paper_question_relation 中有 {len(rel_map)} 套试卷有关联题目")

    # 2. 查看所有试卷状态
    c.execute('''
        SELECT paper_id, paper_name, paper_type, question_count, composition_method, create_time
        FROM exam_paper
        ORDER BY paper_id
    ''')
    all_papers = c.fetchall()

    print(f"\n[INFO] 数据库中共 {len(all_papers)} 套试卷:")
    print(f"  {'ID':>4} | {'状态':<10} | {'DB题数':>6} | {'实际关联':>6} | 试卷名")
    print("  " + "-" * 70)

    for pid, name, ptype, qcount, comp, ctime in all_papers:
        actual = rel_map.get(pid, 0)
        flag = ""
        if ptype == "ENDED" and actual > 0:
            flag = " [NEED FIX]"
        elif ptype == "ENDED" and actual == 0:
            flag = " (empty)"
        print(f"  {pid:>4} | {ptype:<10} | {qcount:>6} | {actual:>6} | {name[:35]}{flag}")

    # 3. 找出需要修复的试卷
    c.execute("SELECT paper_id, paper_name, question_count FROM exam_paper WHERE paper_type='ENDED'")
    ended_papers = c.fetchall()

    fixed = 0
    skipped = 0
    print(f"\n[FIX] 修复分析:")
    for pid, name, db_qcount in ended_papers:
        actual = rel_map.get(pid, 0)
        if actual > 0:
            # 有实际关联题目 -> 恢复为DRAFT并同步题数
            if not dry_run:
                c.execute(
                    "UPDATE exam_paper SET paper_type='DRAFT', question_count=?, update_time=? WHERE paper_id=?",
                    (actual, datetime.now().isoformat(), pid)
                )
            print(f"  [FIX] ID={pid} '{name}' ENDED->DRAFT, question_count {db_qcount}->{actual}")
            fixed += 1
        else:
            # 无关联题目 -> 保持ENDED
            print(f"  [SKIP] ID={pid} '{name}' 无关联题目，保持ENDED")
            skipped += 1

    # 4. 额外修复：同步question_count与实际不一致的非ENDED试卷
    c.execute("SELECT paper_id, paper_name, question_count FROM exam_paper WHERE paper_type != 'ENDED'")
    active_papers = c.fetchall()
    count_fixed = 0
    for pid, name, db_qcount in active_papers:
        actual = rel_map.get(pid, 0)
        if actual != db_qcount:
            if not dry_run:
                c.execute(
                    "UPDATE exam_paper SET question_count=?, update_time=? WHERE paper_id=?",
                    (actual, datetime.now().isoformat(), pid)
                )
            print(f"  [SYNC] ID={pid} '{name}' question_count {db_qcount}->{actual}")
            count_fixed += 1

    # 5. 提交
    if not dry_run:
        conn.commit()
        print(f"\n[DONE] 修复完成:")
        print(f"  恢复试卷: {fixed} 套 (ENDED->DRAFT)")
        print(f"  题数同步: {count_fixed} 套")
        print(f"  跳过(空试卷): {skipped} 套")
    else:
        print(f"\n[DRY-RUN] 将修复:")
        print(f"  恢复试卷: {fixed} 套 (ENDED->DRAFT)")
        print(f"  题数同步: {count_fixed} 套")
        print(f"  跳过(空试卷): {skipped} 套")
        print(f"\n  去掉 --dry-run 参数执行写入")

    # 6. 验证
    if not dry_run:
        print(f"\n[VERIFY] 修复后状态:")
        c.execute('''
            SELECT paper_type, COUNT(*) FROM exam_paper GROUP BY paper_type
        ''')
        for ptype, cnt in c.fetchall():
            print(f"  {ptype}: {cnt} 套")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    fix(dry_run=dry)
