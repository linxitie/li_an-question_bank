# -*- coding: utf-8 -*-
"""diagnose_problems.py — 只读诊断脚本：量化5个问题的规模（不修改任何数据）"""
import sqlite3
import re
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
_DB_REL = os.path.join(os.getcwd(), 'data', 'question_bank.db')
DB = _DB_REL if os.path.exists(_DB_REL) else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'question_bank.db')
STATIC_Q = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'questions')

con = sqlite3.connect(DB)  # 中文路径下 URI 只读模式不可用；本脚本仅执行 SELECT
con.execute("PRAGMA query_only = 1")
cur = con.cursor()

print("=" * 70)
print("[1] UTB 乱码题目统计")
print("=" * 70)
rows = cur.execute("SELECT question_id, question_content, options, answer, answer_analysis FROM question_bank").fetchall()
utb_rows = [r for r in rows if r[1] and re.search(r'UTB[a-f0-9]{6,}', str(r[1]) + str(r[2]) + str(r[3]))]
yaodian_rows = [r for r in utb_rows if '测试要点' in str(r[1])]
print(f"总题数: {len(rows)}")
print(f"含UTB乱码题数: {len(utb_rows)}")
print(f"其中'测试要点'模板题: {len(yaodian_rows)}")
if yaodian_rows[:2]:
    print("\n--- 样例1 ---")
    r = yaodian_rows[0]
    print(f"question_id={r[0]}")
    print(f"question_content={str(r[1])[:300]}")
    print(f"options={str(r[2])[:400]}")
    print(f"answer={r[3]}")
    print(f"answer_analysis={str(r[4])[:200]}")

print()
print("=" * 70)
print("[2] 图片文件与引用统计")
print("=" * 70)
total_files = 0
dir_count = 0
for d in os.listdir(STATIC_Q) if os.path.exists(STATIC_Q) else []:
    dp = os.path.join(STATIC_Q, d)
    if os.path.isdir(dp):
        dir_count += 1
        total_files += len([f for f in os.listdir(dp) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
print(f"static/questions/ 下题目目录数: {dir_count}, 图片文件总数: {total_files}")

# 统计内容中引用的图片
img_ref_qids = cur.execute("SELECT COUNT(*) FROM question_bank WHERE question_content LIKE '%<img%'").fetchone()[0]
print(f"question_content 含<img>标签的题数: {img_ref_qids}")
opt_img = cur.execute("SELECT COUNT(*) FROM question_bank WHERE options LIKE '%<img%' OR options LIKE '%img\\_docx%' ESCAPE '\\'").fetchone()[0]
print(f"options 含图片引用的题数: {opt_img}")

# 抽样看一个用户提到的目录 1111
d1111 = os.path.join(STATIC_Q, '1111')
if os.path.exists(d1111):
    fs = os.listdir(d1111)
    print(f"\n目录 1111 内容 ({len(fs)} 个文件): {fs[:10]}")
    # 找到引用这些图片的题目
    ref_rows = cur.execute("SELECT question_id, question_id FROM question_bank WHERE question_id=1111").fetchall()
    for qid in [1111]:
        row = cur.execute("SELECT question_id, substr(question_content,1,500) FROM question_bank WHERE question_id=?", (qid,)).fetchone()
        if row:
            print(f"题 {qid} 内容片段: {row[1][:300]}")

print()
print("=" * 70)
print("[3] 答案解析缺失统计")
print("=" * 70)
total = len(rows)
empty_analysis = [r for r in rows if not r[4] or not str(r[4]).strip() or str(r[4]).strip() in ('', '无', '[OCR导入，待补充答案解析]', '待补充')]
empty_answer = [r for r in rows if not r[3] or not str(r[3]).strip() or str(r[3]).strip() in ('', '待补充')]
print(f"解析为空/占位的题数: {len(empty_analysis)} ({len(empty_analysis)*100//max(total,1)}%)")
print(f"答案为空/'待补充'的题数: {len(empty_answer)}")

# 按科目分布
subj_dist = Counter()
for r in empty_analysis:
    sr = cur.execute("SELECT subject_id FROM question_bank WHERE question_id=?", (r[0],)).fetchone()
    subj_dist[sr[0] if sr else '?'] += 1
print(f"空解析按subject_id分布: {dict(subj_dist)}")
for sid in list(subj_dist.keys())[:5]:
    if isinstance(sid, int):
        nm = cur.execute("SELECT subject_name FROM question_subject WHERE subject_id=?", (sid,)).fetchone()
        if nm:
            print(f"  subject_id={sid}: {nm[0]} -> {subj_dist[sid]} 题")

print()
print("=" * 70)
print("[4] 题型双源一致性检查（单选误判论述）")
print("=" * 70)
try:
    type_rows = cur.execute("""
        SELECT qb.question_id, qb.type_id, qt.type_name, qdc.question_type_detail,
               LENGTH(COALESCE(qb.options,'')), COALESCE(qb.answer,'')
        FROM question_bank qb
        LEFT JOIN question_type qt ON qb.type_id = qt.type_id
        LEFT JOIN question_detail_category qdc ON qdc.question_id = qb.question_id
    """).fetchall()
    print(f"参与比对的题数: {len(type_rows)}")
    # 有选项但被判为论述的
    has_opts_essay = [r for r in type_rows if r[4] and r[4] > 10 and r[2] and ('论述' in str(r[2]) or '写作' in str(r[2])
                      or (r[3] and '论述' in str(r[3])))]
    print(f"[疑似误判] options非空但 type_name/detail 为论述|写作: {len(has_opts_essay)}")
    for r in has_opts_essay[:8]:
        print(f"  qid={r[0]} type_id={r[1]} type_name={r[2]} detail={r[3]} opt_len={r[4]}")
    # type_name 与 detail 冲突
    conflict = [r for r in type_rows if r[2] and r[3] and str(r[2]).rstrip('题') != str(r[3]).rstrip('题')
                and not (str(r[2]).startswith('单选') and str(r[3]) == '选择题')]
    print(f"type_name 与 question_type_detail 冲突: {len(conflict)}")
    from collections import Counter as C2
    pairs = C2((str(r[2]), str(r[3])) for r in conflict)
    for (tn, dt), c in pairs.most_common(12):
        print(f"  type_name={tn!r} vs detail={dt!r}: {c} 条")
except Exception as e:
    print(f"查询失败: {e}")

print()
print("=" * 70)
print("[5] 题型表内容")
print("=" * 70)
for r in cur.execute("SELECT type_id, type_name, type_code FROM question_type ORDER BY type_id"):
    print(f"  type_id={r[0]} name={r[1]} code={r[2]}")

con.close()
print("\n[完成] 只读诊断结束，未修改任何数据。")
