#!/usr/bin/env python3
"""公专字段指纹回归门禁（L1-G）。

两级判据
--------
1. **逐字段指纹**：基线内的每个 question_id 的 5 个字段（subject_id/type_id/
   options/answer/answer_analysis）sha256 前 16 位必须一致；被改动或被删除即 FAIL。
2. **容量护栏**：各科目题量不得低于基线登记的 `expected_counts`，全库总数不得
   低于 `expected_total`。这条是 2026-10-27「公专题被清空」事故的直接对策——
   旧实现只校验「基线内的题还在不在」，一旦基线本身被清空，门禁会安静地 PASS。

基线文件两种形态（向后兼容）
---------------------------
  旧：``[{question_id, sha256_16}, ...]``        —— 无护栏，会显式警告
  新：``{"meta": {...}, "entries": [...]}``      —— meta.expected_counts 是护栏来源

用法
----
    python scripts/gates/gate_l1g_field_fingerprint.py                # 校验
    python scripts/gates/gate_l1g_field_fingerprint.py --rebaseline --reason "…"
    python scripts/gates/gate_l1g_field_fingerprint.py --self-test

只读连接数据库，绝不写库；`--rebaseline` 只重写基线 JSON。
"""
import hashlib
import json
import os
import sqlite3
import sys
import time

BASE = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
# QB_DB 仅用于「证明门禁能失败」的演练：指向一份临时副本，绝不指向真实库做写操作
DB = os.environ.get('QB_DB') or os.path.join(BASE, 'question_bank.db')
FP = os.path.join(BASE, 'gates', 'gongzhuan_field_fingerprint.json')

FIELDS = 'question_id, subject_id, type_id, options, answer, answer_analysis'
SUBJECT_NAMES = {1: '行测', 2: '申论', 3: '公专'}

# 事故前基线规模：只用于在 meta 里留痕，不参与判据（详见 meta.legacy）
LEGACY_EXPECTED = 2583


def sha(r) -> str:
    qid, sid, tid, opts, ans, ana = r
    return hashlib.sha256(
        f"{qid}|{sid}|{tid}|{opts}|{ans}|{ana}".encode('utf-8')).hexdigest()[:16]


def _ro():
    return sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)


def load_baseline():
    """返回 (entries: dict[qid -> sha], meta: dict)；旧形态 meta 为空。"""
    with open(FP, encoding='utf-8') as fh:
        raw = json.load(fh)
    if isinstance(raw, list):
        return {e['question_id']: e['sha256_16'] for e in raw}, {}
    entries = {e['question_id']: e['sha256_16'] for e in raw.get('entries', [])}
    return entries, raw.get('meta', {})


def subject_counts(con) -> dict:
    rows = con.execute(
        'SELECT subject_id, COUNT(*) FROM question_bank GROUP BY subject_id').fetchall()
    return {int(sid): int(n) for sid, n in rows}


def rebaseline(reason: str) -> int:
    """以当前库重定基线，并登记各科目题量作为护栏。"""
    if not reason.strip():
        print('FAIL: --rebaseline 必须带 --reason "<为什么重定>"')
        return 2

    old_meta = {}
    if os.path.exists(FP):
        try:
            _, old_meta = load_baseline()
        except Exception:  # noqa: BLE001 — 旧文件损坏不阻断重定
            old_meta = {}

    con = _ro()
    rows = con.execute(f'SELECT {FIELDS} FROM question_bank ORDER BY question_id').fetchall()
    counts = subject_counts(con)
    con.close()

    if not rows:
        print('FAIL: 全库 0 题，拒绝用空库重定基线')
        return 2

    entries = [{'question_id': r[0], 'sha256_16': sha(r)} for r in rows]
    meta = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'generated_by': 'scripts/gates/gate_l1g_field_fingerprint.py --rebaseline',
        'reason': reason,
        'scope': '现行题库全量逐字段指纹（subject_id/type_id/options/answer/answer_analysis）',
        'expected_total': len(entries),
        'expected_counts': {str(k): v for k, v in sorted(counts.items())},
        'legacy': {
            'expected_count': LEGACY_EXPECTED,
            'status': 'lost',
            'note': ('2026-10-27 数据事故后库里只剩 200 道公专题，行测/申论为 0；'
                     '本机 4 份备份均为事故后副本，语料库原始文件仍在 题库/ 下。'
                     '护栏改为「各科目题量不下降」以防再次静默清空。'),
        },
    }
    os.makedirs(os.path.dirname(FP), exist_ok=True)
    with open(FP, 'w', encoding='utf-8') as fh:
        json.dump({'meta': meta, 'entries': entries}, fh, ensure_ascii=False, indent=1)

    print(f'  ✅ 已重定基线：{len(entries)} 题  {meta["expected_counts"]}  →  {os.path.normpath(FP)}')
    if old_meta.get('expected_total'):
        print(f'  ℹ 旧基线登记总数 {old_meta["expected_total"]}，新基线 {len(entries)}')
    return 0


def self_test() -> int:
    """自检：证明本门禁**能失败**（含护栏）。"""
    baseline = {1: 'aaa', 2: 'bbb', 3: 'ccc'}
    guard = {3: 200}

    def diff(b, n):
        changed = [q for q in b if q not in n or n[q] != b[q]]
        missing = [q for q in b if q not in n]
        return changed, missing

    def guard_fail(counts, expected):
        return {s: (n, expected.get(s, 0)) for s, n in counts.items() if n < expected.get(s, 0)}

    c0, m0 = diff(baseline, dict(baseline))
    c1, m1 = diff(baseline, {1: 'aaa', 2: 'XXX', 3: 'ccc'})
    c2, m2 = diff(baseline, {1: 'aaa', 2: 'bbb'})
    g_ok = guard_fail({3: 200}, guard)
    g_bad = guard_fail({3: 199}, guard)

    cases = [
        ('未改动 -> 指纹 PASS', not c0 and not m0),
        ('篡改一题 -> 指纹 FAIL', bool(c1) and not m1),
        ('丢失一题 -> 指纹 FAIL', bool(m2)),
        ('题量未降 -> 护栏 PASS', not g_ok),
        ('题量骤降 -> 护栏 FAIL', bool(g_bad)),
    ]
    ok = True
    for label, passed in cases:
        print(f'  {"PASS" if passed else "FAIL"}  自检/{label}')
        if not passed:
            ok = False
    print('L1-G 自检:', 'PASS — 门禁具备失效能力（含容量护栏）' if ok else 'FAIL — 门禁无法检出改动')
    return 0 if ok else 1


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    if '--rebaseline' in sys.argv:
        reason = ''
        if '--reason' in sys.argv:
            i = sys.argv.index('--reason')
            reason = sys.argv[i + 1] if i + 1 < len(sys.argv) else ''
        return rebaseline(reason)

    if not os.path.exists(FP):
        print('FAIL: 缺少基线指纹文件，请先执行 --rebaseline --reason "…"')
        return 1
    baseline, meta = load_baseline()
    ids = list(baseline)

    con = _ro()
    qm = ','.join('?' * len(ids))
    rows = con.execute(
        f'SELECT {FIELDS} FROM question_bank WHERE question_id IN ({qm})', ids).fetchall()
    counts = subject_counts(con)
    total = sum(counts.values())
    con.close()

    now = {r[0]: sha(r) for r in rows}
    changed = [q for q in ids if q not in now or now[q] != baseline[q]]
    missing = [q for q in ids if q not in now]

    print(f'  基线题数: {len(ids)}   仍在库: {len(now)}   全库总数: {total}')
    if meta.get('expected_total'):
        print(f'  基线登记总数: {meta["expected_total"]}'
              f'   基线时间: {meta.get("generated_at", "-")}')
        print(f'  重定理由: {meta.get("reason", "-")}')
    else:
        print('  ⚠ 旧版基线（无容量护栏）：无法发现「基线本身被清空」，建议 --rebaseline')

    # —— 判据 1：逐字段指纹 ——
    fp_ok = not (changed or missing)
    if fp_ok:
        print(f'  ✅ 基线内 {len(ids)} 题逐字段一致（未改动、未丢失）')
    else:
        print(f'  ❌ 基线内被改动 {len(changed)} 题 / 丢失 {len(missing)} 题')
        print(f'     示例: changed={changed[:8]} missing={missing[:8]}')

    # —— 判据 2：容量护栏 ——
    expected_counts = {int(k): int(v) for k, v in (meta.get('expected_counts') or {}).items()}
    expected_total = int(meta.get('expected_total') or 0)
    guard_ok = True
    if expected_counts or expected_total:
        for sid, exp in sorted(expected_counts.items()):
            got = counts.get(sid, 0)
            flag = '✅' if got >= exp else '❌'
            name = SUBJECT_NAMES.get(sid, f'subject#{sid}')
            print(f'  {flag} 护栏/{name}: {got} 题（下限 {exp}）')
            if got < exp:
                guard_ok = False
        if expected_total:
            flag = '✅' if total >= expected_total else '❌'
            print(f'  {flag} 护栏/总数: {total} 题（下限 {expected_total}）')
            if total < expected_total:
                guard_ok = False
        ghost = {sid: n for sid, n in counts.items() if sid not in expected_counts}
        if ghost:
            names = {SUBJECT_NAMES.get(s, str(s)): n for s, n in ghost.items()}
            print(f'  ℹ 新增科目题量（未登记，不判 FAIL）: {names}')

    ok = fp_ok and guard_ok
    print('L1-G 公专字段指纹:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
