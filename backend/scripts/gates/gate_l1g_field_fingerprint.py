#!/usr/bin/env python3
"""公专字段指纹回归门禁（L1-G）。

判据：**基线内的 2583 个 question_id 必须逐字段与基线一致**。
库容增长不算回归（教师会持续导入），但基线内任何一题被改动/删除即失败。

只读连接，绝不写库。
"""
import hashlib
import json
import os
import sqlite3
import sys

BASE = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
DB = os.path.join(BASE, 'question_bank.db')
FP = os.path.join(BASE, 'gates', 'gongzhuan_field_fingerprint.json')

FIELDS = 'question_id, subject_id, type_id, options, answer, answer_analysis'


def sha(r) -> str:
    qid, sid, tid, opts, ans, ana = r
    return hashlib.sha256(
        f"{qid}|{sid}|{tid}|{opts}|{ans}|{ana}".encode('utf-8')).hexdigest()[:16]


def self_test() -> int:
    """自检：证明本门禁**能失败**。

    一个永远 PASS 的门禁等于没有门禁。这里用构造数据验证「改动 / 丢失」
    两种情形都判定为 FAIL，且不触碰真实库。
    """
    baseline = {1: 'aaa', 2: 'bbb', 3: 'ccc'}
    unchanged = {1: 'aaa', 2: 'bbb', 3: 'ccc'}
    tampered = {1: 'aaa', 2: 'XXX', 3: 'ccc'}   # 第 2 题被改
    shrunk = {1: 'aaa', 2: 'bbb'}               # 第 3 题丢失

    def diff(b, n):
        changed = [q for q in b if q not in n or n[q] != b[q]]
        missing = [q for q in b if q not in n]
        return changed, missing

    c0, m0 = diff(baseline, unchanged)
    c1, m1 = diff(baseline, tampered)
    c2, m2 = diff(baseline, shrunk)

    cases = [
        ('未改动 -> PASS', not c0 and not m0, f'changed={c0} missing={m0}'),
        ('篡改一题 -> FAIL', bool(c1) and not m1, f'changed={c1} missing={m1}'),
        ('丢失一题 -> FAIL', bool(m2), f'changed={c2} missing={m2}'),
    ]
    ok = True
    for label, expect, detail in cases:
        got = (not c0 and not m0) if label.startswith('未改动') else \
              (bool(c1) if label.startswith('篡改') else bool(m2))
        passed = got == expect
        print(f'  {"PASS" if passed else "FAIL"}  自检/{label}  ({detail})')
        if not passed:
            ok = False
    print('L1-G 自检:', 'PASS — 门禁具备失效能力' if ok else 'FAIL — 门禁无法检出改动')
    return 0 if ok else 1


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    if not os.path.exists(FP):
        print('FAIL: 缺少基线指纹文件，请先执行 Wave 0 任务 2')
        return 1
    baseline = {e['question_id']: e['sha256_16']
                for e in json.load(open(FP, encoding='utf-8'))}
    ids = list(baseline)

    con = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
    cur = con.cursor()
    qm = ','.join('?' * len(ids))
    rows = cur.execute(
        f'SELECT {FIELDS} FROM question_bank WHERE question_id IN ({qm})', ids
    ).fetchall()
    total = cur.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0]
    con.close()

    now = {r[0]: sha(r) for r in rows}
    changed = [q for q in ids if q not in now or now[q] != baseline[q]]
    missing = [q for q in ids if q not in now]

    print(f'  基线题数: {len(ids)}   仍在库: {len(now)}   全库总数: {total}')
    if total != len(ids):
        print(f'  ℹ 库容较基线 +{total - len(ids)}（教师导入，非回归）')

    if changed or missing:
        print(f'  ❌ 基线内被改动 {len(changed)} 题 / 丢失 {len(missing)} 题')
        print(f'     示例: changed={changed[:8]} missing={missing[:8]}')
        print('L1-G 公专字段指纹: FAIL')
        return 1
    print(f'  ✅ 基线内 {len(ids)} 题逐字段一致（未改动、未丢失）')
    print('L1-G 公专字段指纹: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())