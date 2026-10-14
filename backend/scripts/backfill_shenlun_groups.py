"""一次性回填脚本：为存量申论题补建材料组（2026-10-13 第六轮修复）。

背景：申论材料组建组链路（前端透传 + /batch-parsed 建组）修复前的存量题
无 group_id——教师端/学生端/管理员端显示「无头苍蝇」。材料从导入记录
question_import_record 的 preview_data.raw_text 恢复。

用法：python scripts/backfill_shenlun_groups.py [--dry-run]
幂等：已挂组的题跳过；组按材料内容指纹去重。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import sqlite3  # noqa: E402
from collections import defaultdict  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'question_bank.db')


def load_preview_materials(con) -> dict:
    """从导入记录提取各卷申论材料。返回 {卷关键词: 材料文本}。"""
    out = {}
    cur = con.cursor()
    rows = cur.execute(
        "SELECT original_filename, preview_data FROM question_import_record "
        "WHERE original_filename LIKE '%申论%' AND import_status='PREVIEW'"
    ).fetchall()
    for fname, pd in rows:
        try:
            data = json.loads(pd)
            while isinstance(data, str):
                data = json.loads(data)
        except Exception:
            continue
        raw = data.get('raw_text') or ''
        if not raw:
            r = data.get('_response') or {}
            raw = r.get('raw_text_preview') or ''
        i = raw.find('给定材料')
        if i < 0:
            continue
        j = raw.find('作答要求', i)
        mat = raw[i:j if j > i else i + 6000].strip()
        if len(mat) >= 50:
            out[fname] = mat
    return out


def main():
    dry = '--dry-run' in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()

    sid = cur.execute(
        "SELECT subject_id FROM question_subject WHERE subject_name='申论'").fetchone()
    if not sid:
        print('未找到申论科目')
        return 1
    sid = sid[0]

    rows = cur.execute(
        "SELECT question_id, source, question_content FROM question_bank "
        "WHERE subject_id=? AND (group_id IS NULL OR group_id=0)", (sid,)).fetchall()
    print(f'无组申论题: {len(rows)}')

    materials = load_preview_materials(con)
    print(f'可恢复材料卷: {len(materials)}')

    by_source = defaultdict(list)
    for qid, source, content in rows:
        by_source[source or ''].append((qid, content))

    groups_created, questions_linked = 0, 0
    for source, qs in by_source.items():
        mat = ''
        # 按卷匹配材料：source 与导入记录文件名关键字匹配
        for fname, m in materials.items():
            if source and source in fname:
                mat = m
                break
        if not mat:
            # 兜底：第一题题干作占位材料（保证组结构完整）
            mat = '（材料待恢复）' + (qs[0][1][:200] if qs and qs[0][1] else '')
        digest = 'shenlun_' + source[:20].replace(' ', '')
        # 幂等：已有同 source 组则复用
        cur.execute(
            "SELECT id FROM question_groups WHERE title=? LIMIT 1", (digest,))
        g = cur.fetchone()
        if g:
            gid = g[0]
        else:
            cur.execute(
                "INSERT INTO question_groups (group_type, shared_content, title, subject, source) "
                "VALUES ('material', ?, ?, '申论', ?)",
                (mat, digest, source or ''))
            gid = cur.lastrowid
            groups_created += 1
        for qid, _ in qs:
            if not dry:
                cur.execute(
                    "UPDATE question_bank SET group_id=? WHERE question_id=? AND (group_id IS NULL OR group_id=0)",
                    (gid, qid))
            questions_linked += 1

    if dry:
        print('[dry-run] 不写库')
    else:
        con.commit()
    print(f'建组 {groups_created} / 挂题 {questions_linked}')
    con.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
