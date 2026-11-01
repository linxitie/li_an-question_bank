#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理联调/截图产生的备考资料测试数据（学生自建卡 + 落盘配图）。

背景：`scripts/verify/mobile_create_and_pin.mjs` 会真实建 1 张申论卡（内容固定，
便于比对效果图）；重复执行会命中后端去重返回 409，因此跑之前/之后都要清一次。

用法（在仓库根执行）：
    python scripts/verify/cleanup_test_materials.py --dry    # 只列出，不删
    python scripts/verify/cleanup_test_materials.py          # 删除

删除范围：`creator_id` 指定（默认 3 = 学生 202516001）且 `create_time` 是今天、
`type='card'` 的资料行，以及这些行引用到的 `uploads/materials/images/*` 文件。
不会碰管理员/教师建的正式资料，也不会碰 status=-1 的历史软删行。
"""
import argparse
import os
import re
import sqlite3
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(REPO, 'backend', 'data', 'question_bank.db')
IMG_DIR = os.path.join(REPO, 'backend', 'uploads', 'materials', 'images')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只列出不删除')
    ap.add_argument('--creator', type=int, default=3, help='学生 user_id，默认 3')
    ap.add_argument('--db', default=DB)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    today = datetime.now().strftime('%Y-%m-%d')
    rows = con.execute(
        "SELECT material_id, title, cover_image, content FROM study_material "
        "WHERE creator_id = ? AND type = 'card' AND date(create_time) = ?",
        (args.creator, today)).fetchall()
    print(f'今天由 user_id={args.creator} 自建的卡片：{len(rows)} 张')
    urls = []
    for r in rows:
        print(f"  id={r['material_id']}  {r['title'][:30]}  cover={r['cover_image']}")
        if r['cover_image']:
            urls.append(r['cover_image'])
        urls += re.findall(r'/uploads/materials/images/([\w.\-]+)', r['content'] or '')

    if args.dry:
        print('dry-run：未删除')
        return

    ids = [r['material_id'] for r in rows]
    if ids:
        marks = ','.join('?' * len(ids))
        con.execute(f'DELETE FROM study_material WHERE material_id IN ({marks})', ids)
        try:
            con.execute(f'DELETE FROM user_material_progress WHERE material_id IN ({marks})', ids)
        except sqlite3.Error as e:
            print(f'  跳过 user_material_progress：{e}')
        con.commit()

    removed = 0
    for u in set(urls):
        p = os.path.join(IMG_DIR, os.path.basename(u))
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    print(f'已删除卡片 {len(ids)} 张、配图 {removed} 个')
    print('当前已公开资料：', con.execute('SELECT COUNT(*) FROM study_material WHERE status = 1').fetchone()[0])
    con.close()


if __name__ == '__main__':
    main()
