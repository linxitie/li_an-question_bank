# -*- coding: utf-8 -*-
"""清理三轮验收产生的测试数据：演示卡（学生自建、含配图）+ Excel 导入的下架行。

用法（仓库根）：
    python scripts/verify/cleanup_round3.py --dry
    python scripts/verify/cleanup_round3.py
"""
import argparse
import os
import re
import sqlite3
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(REPO, 'backend', 'data', 'question_bank.db')
IMG_DIR = os.path.join(REPO, 'backend', 'uploads', 'materials', 'images')
STUDENT_ID = 3          # 202516001，验收脚本用的学生账号


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--db', default=DB)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    today = datetime.now().strftime('%Y-%m-%d')

    demos = con.execute(
        "SELECT material_id, title, cover_image, content FROM study_material "
        "WHERE subject='shenlun' AND type='card' AND title LIKE '申论综合分析 三步拆解（演示%'"
    ).fetchall()
    # Excel 批量导入进来的待审行：只清「今天 + 学生本人在验收时提交」的，避免误删历史数据
    offline = con.execute(
        "SELECT material_id, title FROM study_material "
        "WHERE status=0 AND type='card' AND creator_id=? AND date(create_time)=?",
        (STUDENT_ID, today)
    ).fetchall()
    print(f'演示卡 {len(demos)} 张 / 下架待审卡片 {len(offline)} 张')
    for r in demos:
        print('  demo', r['material_id'], r['title'][:28])
    for r in offline:
        print('  offline', r['material_id'], r['title'][:28])

    if args.dry:
        print('dry-run：未删除')
        return

    urls = []
    for r in demos:
        if r['cover_image']:
            urls.append(r['cover_image'])
        urls += re.findall(r'/uploads/materials/images/([\w.\-]+)', r['content'] or '')
    ids = [r['material_id'] for r in demos] + [r['material_id'] for r in offline]
    if ids:
        marks = ','.join('?' * len(ids))
        con.execute(f'DELETE FROM study_material WHERE material_id IN ({marks})', ids)
        try:
            con.execute(f'DELETE FROM user_material_progress WHERE material_id IN ({marks})', ids)
        except sqlite3.Error as e:
            print('  跳过 user_material_progress：', e)
        con.commit()

    removed = 0
    for u in set(urls):
        p = os.path.join(IMG_DIR, os.path.basename(u))
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    print(f'已删除 {len(ids)} 条资料、{removed} 个配图')
    print('已公开资料：', con.execute('SELECT COUNT(*) FROM study_material WHERE status=1').fetchone()[0])
    print('下架资料：', con.execute('SELECT COUNT(*) FROM study_material WHERE status=0').fetchone()[0])
    con.close()


if __name__ == '__main__':
    main()
