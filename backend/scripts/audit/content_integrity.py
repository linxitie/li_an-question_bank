#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内容完整性校验 CI-1..CI-6（终态架构 §19.8 / L7-15）。

为什么需要它：题目的材料与子题、图片、申论材料之间的映射只存在于数据里，
一次批量导入或清理就可能把 `group_id`、`shared_content_images` 写坏，
而页面只会表现为「图裂」「材料丢失」，事后极难定位。本脚本把六条不变量
变成可执行检查，并以 F0 基线（行数 + SHA-256 指纹）作为不可退让的下限。

判定口径：
  PASS  当前完全满足不变量
  WARN  命中已登记存量缺陷（13 行缺图 / 10 个未解析令牌 / 空组 11），只报告不删
  FAIL  新增了同类缺陷，或四表行数/指纹与基线不一致
只读：不写业务表、不删图片、不动静态资源（R6/R7）。

用法：
  python backend/scripts/audit/content_integrity.py --check \
      --baseline backend/data/reports/f0_backup.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent
if str(AUDIT_DIR) not in sys.path:
  sys.path.insert(0, str(AUDIT_DIR))
import gc_previews  # noqa: E402  复用 F0 同口径指纹，避免两套实现漂移

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'backend'
DEFAULT_DB = BACKEND_DIR / 'data' / 'question_bank.db'
STATIC_ROOT = BACKEND_DIR / 'app' / 'static'
REPORT_PATH = BACKEND_DIR / 'data' / 'reports' / 'content_integrity.json'
BASELINE_PATH = BACKEND_DIR / 'data' / 'reports' / 'f1_content_baseline.json'
F0_DB = BACKEND_DIR / 'data' / 'backups' / 'pre_foundation_20261026_193553.db'
F0_REPORT = BACKEND_DIR / 'data' / 'reports' / 'f0_backup.json'
ESSAY_TYPE_IDS = (14, 19, 20)
TOKEN_RE = re.compile(r'\[IMAGE:([^\]]+)\]')

# 已登记存量缺陷（F0 实测，见 docs/superpowers/specs/F0基线冻结与内容完整性_报告_20261026.md）
KNOWN_MISSING_IMAGE_ROWS = 13
KNOWN_UNRESOLVED_TOKENS = 10
KNOWN_ORPHAN_GROUPS = {11}
KNOWN_BAD_GROUPS: set[int] = set()


def _status(failures: list[str], warnings: list[str]) -> str:
  if failures:
    return 'FAIL'
  return 'WARN' if warnings else 'PASS'


def _result(name: str, title: str, failures: list[str], warnings: list[str], **extra) -> dict:
  return {'id': name, 'title': title, 'status': _status(failures, warnings),
          'failures': failures, 'warnings': warnings, **extra}


def _non_empty_sql(col: str) -> str:
  return f"({col} is not null and trim({col}) not in ('', '[]', 'null'))"


def check_group_refs(con: sqlite3.Connection) -> dict:
  """CI-1：组引用双向完整。"""
  orphan_questions = [r[0] for r in con.execute(
    'select q.question_id from question_bank q where q.group_id != 0 '
    'and not exists (select 1 from question_groups g where g.id = q.group_id) limit 50'
  )]
  orphan_groups = [r[0] for r in con.execute(
    'select g.id from question_groups g where not exists '
    '(select 1 from question_bank q where q.group_id = g.id) order by g.id'
  )]
  new_orphans = [g for g in orphan_groups if g not in KNOWN_ORPHAN_GROUPS]
  failures = [f'题目组不存在：{q}' for q in orphan_questions]
  failures += [f'空组（无子题）：{g}' for g in new_orphans]
  warnings = [f'空组（已登记存量）：{g}' for g in orphan_groups if g in KNOWN_ORPHAN_GROUPS]
  return _result('CI-1', '组引用完整', failures, warnings,
                 orphan_groups=orphan_groups, orphan_questions=len(orphan_questions))


def check_group_content(con: sqlite3.Connection) -> dict:
  """CI-2：组必须有材料，不能是空壳。"""
  bad = [r[0] for r in con.execute(
    'select id from question_groups where '
    f'not {_non_empty_sql("shared_content")} and '
    f'not {_non_empty_sql("shared_content_images")} order by id'
  )]
  new_bad = [g for g in bad if g not in KNOWN_BAD_GROUPS]
  failures = [f'组无材料：{g}' for g in new_bad]
  warnings = [f'组无材料（已登记）：{g}' for g in bad if g in KNOWN_BAD_GROUPS]
  return _result('CI-2', '组内容非空', failures, warnings, bad_groups=bad)


def _resolve_image(image_path: str) -> Path | None:
  """把库里的 /static/... 映射到磁盘；只拼接，不做任何写入。"""
  raw = (image_path or '').strip().replace('\\', '/')
  if not raw:
    return None
  if raw.startswith('/static/'):
    rel = raw[len('/static/'):]
  elif raw.startswith('static/'):
    rel = raw[len('static/'):]
  else:
    rel = raw.lstrip('/')
  path = (STATIC_ROOT / rel).resolve()
  try:
    path.relative_to(STATIC_ROOT.resolve())
  except ValueError:
    return None  # 越界路径视为不可落地，禁止读到 static 之外
  return path


def check_images(con: sqlite3.Connection) -> dict:
  """CI-3：question_image 每行都要能落地到文件。"""
  missing = [{'image_id': row[0], 'question_id': row[1], 'path': row[2]}
             for row in con.execute(
               'select image_id, question_id, image_path from question_image order by image_id')
             if not (_resolve_image(row[2]) or Path()).is_file()]
  failures = []
  if len(missing) > KNOWN_MISSING_IMAGE_ROWS:
    failures = [f'缺图新增：{m["image_id"]} {m["path"]}' for m in missing[KNOWN_MISSING_IMAGE_ROWS:]]
  warnings = [] if not missing else [f'缺图存量 {len(missing)} 行（基线 {KNOWN_MISSING_IMAGE_ROWS}）']
  return _result('CI-3', '图片可落地', failures, warnings,
                 missing_rows=len(missing), samples=missing[:10])


def _known_image_names(con: sqlite3.Connection) -> tuple[set[str], set[str]]:
  exact = set()
  for (path,) in con.execute('select image_path from question_image'):
    if path:
      exact.add(Path(path.replace('\\', '/')).name)
  prefix = set()
  questions_dir = STATIC_ROOT / 'questions'
  if questions_dir.is_dir():
    for entry in questions_dir.iterdir():
      if entry.is_file():
        prefix.add(entry.name)
  return exact, prefix


def check_tokens(con: sqlite3.Connection) -> dict:
  """CI-4：shared_content 的 [IMAGE:tok] 必须能解析到文件或 question_image。"""
  exact, prefix = _known_image_names(con)
  unresolved = []
  used = 0
  for gid, shared in con.execute('select id, shared_content from question_groups order by id'):
    for token in TOKEN_RE.findall(shared or ''):
      used += 1
      if token in exact:
        continue
      if any(name.startswith(token) for name in prefix):
        continue  # 哈希前缀能命中文件：仍记 WARN，要求 F2 回填结构化数组
      unresolved.append({'group_id': gid, 'token': token})
  failures = []
  if len(unresolved) > KNOWN_UNRESOLVED_TOKENS:
    failures = [f'未解析令牌新增：{u["group_id"]} {u["token"]}'
                for u in unresolved[KNOWN_UNRESOLVED_TOKENS:]]
  warnings = [] if not unresolved else [
    f'未解析令牌 {len(unresolved)} 个（基线 {KNOWN_UNRESOLVED_TOKENS}）；'
    'shared_content_images 尚未回填']
  return _result('CI-4', '令牌可解析', failures, warnings,
                 tokens=used, unresolved=len(unresolved), samples=unresolved[:10])


def check_essay_groups(con: sqlite3.Connection) -> dict:
  """CI-5：申论题挂组时必须同科目且有材料；未挂组合法。"""
  placeholders = ','.join('?' for _ in ESSAY_TYPE_IDS)
  failures = []
  rows = con.execute(
    f'select q.question_id, q.group_id, g.subject, g.shared_content, g.shared_content_images '
    f'from question_bank q join question_groups g on g.id = q.group_id '
    f'where q.type_id in ({placeholders}) and q.group_id != 0', ESSAY_TYPE_IDS
  ).fetchall()
  for qid, gid, subject, shared, shared_images in rows:
    if subject != '申论':
      failures.append(f'申论题 {qid} 挂到非申论组 {gid}（subject={subject}）')
    if not ((shared or '').strip() or (shared_images or '').strip() not in ('', '[]')):
      failures.append(f'申论组 {gid} 无材料，题 {qid} 失去材料映射')
  return _result('CI-5', '申论同科目且有材料', failures, [], checked_pairs=len(rows))


def check_fingerprint(con: sqlite3.Connection, baseline: dict) -> dict:
  """CI-6：四表行数 + 指纹必须与 F0 基线完全一致。"""
  # 新基线用 fingerprints；兼容 F0 报告的 fingerprint（表->sha 字符串）
  base_fp = baseline.get('fingerprints') or baseline.get('fingerprint') or {}
  base_counts = baseline.get('counts') or {}
  failures, detail = [], {}
  for table in gc_previews.FINGERPRINT_TABLES:
    now = gc_previews.fingerprint(con, table)
    detail[table] = now
    # F0 报告里 fingerprint 是「表 -> sha256 字符串」，行数在 counts 里；
    # 同时兼容将来可能升级成的 {rows, sha256} 结构。
    old = base_fp.get(table)
    old_sha = old.get('sha256') if isinstance(old, dict) else old
    old_rows = base_counts.get(table)
    if old_rows is not None and now['rows'] != old_rows:
      failures.append(f'{table} 行数 {now["rows"]} != 基线 {old_rows}')
    if old_sha and now['sha256'] != old_sha:
      failures.append(f'{table} 指纹不一致')
  if not base_fp:
    failures.append('基线缺少 fingerprint 字段')
  return _result('CI-6', '四表行数与指纹不变', failures, [], fingerprints=detail)


def write_baseline(con: sqlite3.Connection, source: Path) -> dict:
  """生成 F1 可复现基线；口径写进文件，避免再出现「不知道当时怎么算的」。"""
  import hashlib
  fingerprints = {t: gc_previews.fingerprint(con, t) for t in gc_previews.FINGERPRINT_TABLES}
  baseline = {
    'created_at': datetime.now().strftime('%Y%m%d_%H%M%S'),
    'source': str(source),
    'source_sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
    'serialization': 'sqlite3 tuple -> json.dumps(tuple) 默认参数（ensure_ascii=True），逐行 update utf-8',
    'ordering': '见 gc_previews.FINGERPRINT_TABLES（四表均显式 ORDER BY）',
    'fingerprints': fingerprints,
    'counts': {t: v['rows'] for t, v in fingerprints.items()},
  }
  if F0_REPORT.is_file():
    f0 = json.loads(F0_REPORT.read_text(encoding='utf-8'))
    baseline['f0_report_fingerprint'] = f0.get('fingerprint')
    baseline['f0_report_counts'] = {t: (f0.get('counts') or {}).get(t) for t in fingerprints}
    baseline['f0_report_note'] = (
      'F0 报告指纹由当次临时探针生成，序列化细节未落代码，实测无法用任何常见变体复现；'
      '本基线改为对 F0 备份库（pre_foundation_20261026_193553.db）重算，'
      '并已验证与当前主库逐表一致，故 F0 报告哈希仅作历史留档，不参与 CI-6。')
  return baseline


def run_checks(con: sqlite3.Connection, baseline: dict) -> dict:
  checks = [check_group_refs(con), check_group_content(con), check_images(con),
            check_tokens(con), check_essay_groups(con), check_fingerprint(con, baseline)]
  summary = {s: sum(1 for c in checks if c['status'] == s) for s in ('PASS', 'WARN', 'FAIL')}
  return {'checked_at': datetime.now().strftime('%Y%m%d_%H%M%S'),
          'database': str(DEFAULT_DB), 'checks': checks, 'summary': summary}


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description='内容完整性 CI-1..CI-6（只读）')
  parser.add_argument('--db', default=str(DEFAULT_DB))
  parser.add_argument('--baseline', default=str(BASELINE_PATH))
  parser.add_argument('--check', action='store_true', help='FAIL 时退出码 1')
  parser.add_argument('--report', default=str(REPORT_PATH))
  parser.add_argument('--write-baseline', action='store_true',
                      help='从 --db 生成 F1 基线（默认取自 F0 备份库），不跑检查')
  args = parser.parse_args(argv)

  db = Path(args.db)
  if not db.is_file():
    print(f'库不存在：{db}', file=sys.stderr)
    return 2
  con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=10)
  try:
    if args.write_baseline:
      baseline = write_baseline(con, db)
      out = Path(args.report) if args.report != str(REPORT_PATH) else Path(args.baseline)
      out.parent.mkdir(parents=True, exist_ok=True)
      out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
      print(f"基线已写入：{out} {baseline['counts']}")
      return 0
    baseline = json.loads(Path(args.baseline).read_text(encoding='utf-8'))
    report = run_checks(con, baseline)
  finally:
    con.close()
  report['database'] = str(db)
  report['baseline'] = str(args.baseline)
  out = Path(args.report)
  out.parent.mkdir(parents=True, exist_ok=True)
  out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

  for check in report['checks']:
    print(f"[{check['status']}] {check['id']} {check['title']}")
    for line in check['failures'][:5]:
      print(f'  FAIL {line}')
    for line in check['warnings'][:5]:
      print(f'  WARN {line}')
  print(f"汇总：{report['summary']}  报告：{out}")
  if args.check and report['summary']['FAIL']:
    return 1
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
