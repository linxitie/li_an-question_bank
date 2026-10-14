# -*- coding: utf-8 -*-
"""复合题组存量数据修复（题目导入模块修复方案 v8 · Wave 4）。

背景：v8 诊断发现四类存量数据问题——
  1. 空壳题组：0 成员，界面上「有组」但查不到任何小题
  2. 垃圾占位符材料：shared_content 是「（材料待恢复）」+ 题干前 200 字
     （backfill_shenlun_groups.py:85 的历史产物）。一旦成员从软删恢复，
     前端会把**题干当材料**展示给用户，属会扩散的错误。
  3. 组内题号重复：同一份卷被导入两次，题号 1-4 各存在两条
  4. 全库重复题目：同内容多行，去重机制未拦住

设计约束：
  · 默认 dry-run，只读报告；必须显式 --apply 才写库
  · 写库前用 sqlite3 backup API 备份（WAL 模式，禁止 shutil.copy2）
  · 只删「垃圾占位符组」这一类确定性垃圾；空壳组/重复题仅报告不删，
    业务数据删除由人工判断

用法：
    python scripts/fix_composite_groups_r8.py            # dry-run 报告
    python scripts/fix_composite_groups_r8.py --apply    # 执行修复（含自动备份）
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

# backfill_shenlun_groups.py:85 生成的占位符前缀。命中即判定为垃圾材料。
PLACEHOLDER_PREFIX = '（材料待恢复）'

DB_REL = os.path.join('data', 'question_bank.db')


def backup_db(con: sqlite3.Connection) -> str:
    """WAL 模式下必须走 sqlite3 backup API，复制主库会丢未 checkpoint 的页。"""
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dst_path = os.path.abspath(
        f'data/question_bank.db.bak_r8_{ts}')
    dst = sqlite3.connect(dst_path)
    try:
        con.backup(dst)
    finally:
        dst.close()
    return dst_path


def report(con: sqlite3.Connection) -> dict:
    r = {}

    r['empty_groups'] = con.execute(
        "SELECT g.id, g.subject, g.group_type, LENGTH(COALESCE(g.shared_content,'')) "
        "FROM question_groups g "
        "WHERE NOT EXISTS (SELECT 1 FROM question_bank b "
        "                WHERE b.group_id = g.id) ORDER BY g.id").fetchall()

    r['placeholder_groups'] = con.execute(
        "SELECT g.id, g.subject, g.group_type, LENGTH(COALESCE(g.shared_content,'')) "
        "FROM question_groups g "
        "WHERE g.shared_content LIKE ? ORDER BY g.id",
        (PLACEHOLDER_PREFIX + '%',)).fetchall()

    # 「材料实为题干」：shared_content 与某道成员题的题干（去所有空白后）相同 ——
    # 这类组没有材料，只有被复制进去的题干，成员一旦恢复就会把题干当材料展示。
    # 归一化必须放在 Python 侧做：SQLite 的 REPLACE 只能逐字符删空格/换行，
    # 且源文里混有全角空格与软换行，字符级 REPLACE 会漏判。
    # 特征与 PLACEHOLDER_PREFIX 不同（回填脚本有时连前缀都没带上），故独立检测。
    norm = lambda s: re.sub(r'\s+', '', s or '')
    stem_hits = []
    for gid, subj, gt, mat in con.execute(
            "SELECT g.id, g.subject, g.group_type, g.shared_content "
            "FROM question_groups g WHERE LENGTH(TRIM(COALESCE(g.shared_content,'')))>0"
    ):
        target = norm(mat)
        for qid, content in con.execute(
                "SELECT question_id, question_content FROM question_bank "
                "WHERE group_id = ?", (gid,)):
            if norm(content) == target:
                stem_hits.append((gid, subj, gt, qid, len(mat or '')))
                break
    r['stem_as_material'] = stem_hits

    r['dup_qnum_groups'] = con.execute(
        "SELECT group_id, question_number, COUNT(*) c FROM question_bank "
        "WHERE status = 1 AND group_id > 0 "
        "AND question_number IS NOT NULL AND TRIM(question_number) <> '' "
        "GROUP BY group_id, question_number HAVING COUNT(*) > 1 "
        "ORDER BY group_id, question_number").fetchall()

    r['dup_contents'] = con.execute(
        "SELECT substr(question_content,1,60) c, COUNT(*) n, "
        "       GROUP_CONCAT(DISTINCT subject_id) subs "
        "FROM question_bank WHERE status = 1 "
        "AND LENGTH(TRIM(COALESCE(question_content,''))) > 20 "
        "GROUP BY question_content HAVING COUNT(*) > 1 "
        "ORDER BY n DESC").fetchall()

    r['img_residue'] = con.execute(
        "SELECT question_id, subject_id, substr(question_content,1,60) "
        "FROM question_bank WHERE status = 1 "
        "AND question_content LIKE '%[IMAGE:%' ORDER BY question_id").fetchall()

    return r


def print_report(r: dict) -> None:
    bar = '=' * 66
    print(bar)
    print('一、空壳题组（0 成员）—— 仅报告，需人工确认')
    print(bar)
    if not r['empty_groups']:
        print('  无')
    for gid, subj, gt, ln in r['empty_groups']:
        print(f'  组{gid:<4} 科目={subj} 类型={gt} 材料{ln}字')

    print()
    print(bar)
    print('二、垃圾占位符材料组 —— --apply 时删除（方案 D6 决策）')
    print(bar)
    if not r['placeholder_groups']:
        print('  无')
    for gid, subj, gt, ln in r['placeholder_groups']:
        print(f'  组{gid:<4} 科目={subj} 类型={gt} 材料{ln}字  ← {PLACEHOLDER_PREFIX}…')

    print()
    print(bar)
    print('三、材料与成员题干完全相同（仅报告，需人工判断）')
    print(bar)
    print('  说明：公专情境题的「材料」本就是题干（_detect_and_link_composite_groups:784')
    print('        取 shared_content=头题题干），单成员属正确建模，不在删除范围；')
    print('        申论出现同样形态则是材料退化（材料≠题干），需人工确认。')
    if not r['stem_as_material']:
        print('  无')
    for gid, subj, gt, qid, ln in r['stem_as_material']:
        mark = '←申论材料退化?' if subj == '申论' else ''
        print(f'  组{gid:<4} 科目={subj} 类型={gt} 材料{ln}字 == q{qid} 题干 {mark}')

    print()
    print(bar)
    print('四、组内题号重复 —— 仅报告')
    print(bar)
    if not r['dup_qnum_groups']:
        print('  无')
    for gid, qn, c in r['dup_qnum_groups']:
        print(f'  组{gid:<4} 题号={qn} 出现{c}次')

    print()
    print(bar)
    print('五、全库重复题目 —— 仅报告（v8 W6 待定位去重失效原因）')
    print(bar)
    if not r['dup_contents']:
        print('  无')
    for c, n, subs in r['dup_contents'][:20]:
        print(f'  x{n:<3} subject_ids={subs}  {c}')

    print()
    print(bar)
    print('六、未解析 [IMAGE: 标记 —— 仅报告（需人工核对图片文件）')
    print(bar)
    if not r['img_residue']:
        print('  无')
    for qid, sid, txt in r['img_residue']:
        print(f'  q{qid:<6} subject={sid}  {txt}')


def main() -> int:
    ap = argparse.ArgumentParser(description='复合题组存量数据修复（v8 Wave 4）')
    ap.add_argument('--apply', action='store_true',
                    help='实际写库（默认 dry-run，仅报告）')
    args = ap.parse_args()

    db_path = os.path.abspath(DB_REL)
    if not os.path.exists(db_path):
        print(f'找不到数据库: {db_path}')
        return 2

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        result = report(con)
        print_report(result)

        if not args.apply:
            print()
            print('>>> dry-run 结束，未做任何写入。加 --apply 执行修复。')
            return 0

        # 只删「带占位符前缀」的组：那是 backfill_shenlun_groups.py 取不到真实材料
        # 时拼出来的假数据，无歧义。
        # 不删「材料==成员题干」的组：公专情境题的建模本就如此（见 print_report 第三项），
        # 与垃圾数据同形却性质相反，交人工判断。
        ids = sorted({row[0] for row in result['placeholder_groups']})
        if not ids:
            print()
            print('>>> 无占位符垃圾组，无需写入。')
            return 0

        bak = backup_db(con)
        print()
        print(f'>>> 已备份: {bak}')
        for gid in ids:
            con.execute('DELETE FROM question_groups WHERE id = ?', (gid,))
        con.commit()
        print(f'>>> 已删除占位符垃圾组 {ids}；其余项目仅报告未改动。')
        return 0
    finally:
        con.close()


if __name__ == '__main__':
    raise SystemExit(main())
