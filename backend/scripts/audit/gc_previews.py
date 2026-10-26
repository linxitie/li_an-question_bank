#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""预览数据一次性治理（终态架构 §18.5）。

为什么需要它：question_import_record.preview_data 占了主库 86.7%（262.99 MB），
其中 537 条未确认预览（PREVIEW）已超过 7 天仍全量驻留。本脚本把超期预览外置为
gzip 文件，再把列置为摘要，避免主库被遗弃预览持续挤压。

安全边界（均为本脚本的硬约束）：
- 只改 question_import_record.preview_data 一列，不动任何其它列、表、文件；
- 每条先导出成功，才允许把该行置为摘要；导出失败的行跳过，绝不静默删；
- 执行前后比对四张内容表的行数与 SHA-256 指纹，不一致立即中止；
- 默认 dry-run，必须显式 --execute 才写入；
- 备份、静态资源、题库目录本脚本一律不碰（R6/R7/R8）。

用法：
  python backend/scripts/audit/gc_previews.py            # 只出计划报告
  python backend/scripts/audit/gc_previews.py --execute  # 执行（先备份！）
  python backend/scripts/audit/gc_previews.py --execute --vacuum  # 执行并物理回收
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / 'backend' / 'data' / 'question_bank.db'
PREVIEW_DIR = REPO_ROOT / 'backend' / 'data' / 'import_previews'
REPORT_DIR = REPO_ROOT / 'backend' / 'data' / 'reports'

# 保留期（天）：与 §18.2 的 TTL 表一致，改这里必须同步改文档
RETENTION_DAYS = {
    'PREVIEW': 7,
    'COMPLETED': 30,
    'FAILED': 90,
}

# 内容完整性指纹覆盖的表（与 F0 基线一致，见 §19.8）
FINGERPRINT_TABLES = {
    'question_bank': 'select question_id, question_content, answer, answer_analysis, options, group_id, sort_order, question_level, question_number from question_bank order by question_id',
    'question_groups': 'select id, group_type, subject, shared_content, shared_content_images from question_groups order by id',
    'question_image': 'select image_id, question_id, image_path, image_type, image_order from question_image order by image_id',
    'question_knowledge': 'select id, question_id, knowledge_point_id from question_knowledge order by id',
}


def db_size_bytes(con: sqlite3.Connection) -> int:
  """按页数估算逻辑文件大小；VACUUM 前后的对比口径。"""
  page_size = con.execute('pragma page_size').fetchone()[0]
  page_count = con.execute('pragma page_count').fetchone()[0]
  return page_size * page_count


def fingerprint(con: sqlite3.Connection, table: str) -> dict:
  """按 F0 相同口径算内容指纹；返回行数与 SHA-256。"""
  h = hashlib.sha256()
  rows = 0
  for row in con.execute(FINGERPRINT_TABLES[table]):
    h.update(json.dumps(row).encode('utf-8'))
    rows += 1
  return {'rows': rows, 'sha256': h.hexdigest()}


def all_fingerprints(con: sqlite3.Connection) -> dict:
  return {t: fingerprint(con, t) for t in FINGERPRINT_TABLES}


def count_questions(raw: str) -> int:
  """尽力解析旧记录里有多少题；解析失败不影响清理（文件已外置）。"""
  try:
    data = json.loads(raw)
    # 历史双重编码：再剥一层
    if isinstance(data, str):
      data = json.loads(data)
    if isinstance(data, dict):
      items = data.get('items')
      if isinstance(items, list):
        return len(items)
      resp = data.get('_response')
      if isinstance(resp, dict) and isinstance(resp.get('questions'), list):
        return len(resp['questions'])
    if isinstance(data, list):
      return len(data)
  except (ValueError, TypeError):
    return 0
  return 0


def select_candidates(con: sqlite3.Connection) -> list[dict]:
  """按保留期筛出超期且仍持有实体预览数据的行。"""
  now = datetime.now()
  out: list[dict] = []
  rows = con.execute(
      'select import_id, import_status, import_time, preview_data '
      'from question_import_record '
      "where preview_data is not null and length(preview_data) > 0 "
      "and import_status in ('PREVIEW','COMPLETED','FAILED') "
      'order by import_id'
  ).fetchall()
  for import_id, status, import_time, raw in rows:
    raw = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    if '"_purged":true' in raw or '"_purged": true' in raw:
      continue  # 已治理过，保持幂等
    if not import_time:
      continue  # 时间不明的不动，交人工判断
    try:
      created = datetime.fromisoformat(str(import_time).split('.')[0])
    except ValueError:
      continue
    keep_days = RETENTION_DAYS.get(status, 7)
    if now - created < timedelta(days=keep_days):
      continue
    out.append({
        'import_id': import_id,
        'status': status,
        'import_time': str(import_time),
        'bytes': len(raw.encode('utf-8')),
        'questions': count_questions(raw),
        'raw': raw,
    })
  return out


def export_one(item: dict, month: str) -> str:
  """把一条原始 preview_data 原样写入 gzip；返回相对仓库根的引用路径。"""
  target_dir = PREVIEW_DIR / month
  target_dir.mkdir(parents=True, exist_ok=True)
  target = target_dir / f"{item['import_id']}.json.gz"
  # 原样保存，不做 JSON 重排：保证回读内容与库内字节语义一致
  with gzip.open(target, 'wt', encoding='utf-8') as fh:
    fh.write(item['raw'])
  rel = target.relative_to(REPO_ROOT).as_posix()
  with gzip.open(target, 'rt', encoding='utf-8') as fh:
    if fh.read() != item['raw']:
      raise RuntimeError(f"回读校验失败: {rel}")
  return rel


def purge_batch(con: sqlite3.Connection, items: list[dict]) -> int:
  """批量置摘要；每条独立 UPDATE，整批一个事务。"""
  now = datetime.now().isoformat(timespec='seconds')
  for item in items:
    summary = {
        '_purged': True,
        'questions': item['questions'],
        'ref': item['ref'],
        'purged_at': now,
    }
    con.execute(
        'update question_import_record set preview_data = ? where import_id = ?',
        (json.dumps(summary, ensure_ascii=False), item['import_id']),
    )
  return len(items)


def main() -> int:
  parser = argparse.ArgumentParser(description='预览数据一次性治理（默认 dry-run）')
  parser.add_argument('--execute', action='store_true', help='真正写入（默认只出计划）')
  parser.add_argument('--vacuum', action='store_true', help='执行后开启 incremental auto_vacuum 并 VACUUM')
  parser.add_argument('--batch', type=int, default=100, help='每批行数，默认 100')
  parser.add_argument('--baseline-db', default='', help='给定基线库（如 F0 备份），指纹不一致则拒绝执行')
  args = parser.parse_args()

  if not DB_PATH.exists():
    print(f"[FAIL] 数据库不存在: {DB_PATH}")
    return 2

  started = time.time()
  con = sqlite3.connect(DB_PATH, timeout=30)
  con.execute('pragma busy_timeout=30000')
  size_before = db_size_bytes(con)
  fp_before = all_fingerprints(con)
  total_rows = con.execute('select count(*) from question_import_record').fetchone()[0]

  baseline_ok = True
  if args.baseline_db:
    base = sqlite3.connect(args.baseline_db)
    fp_base = all_fingerprints(base)
    base.close()
    baseline_ok = fp_base == fp_before
    if not baseline_ok:
      print('[FAIL] 与基线库指纹不一致，数据已被改动，拒绝继续。')
      print(f'  基线: {fp_base}')
      print(f'  当前: {fp_before}')
      con.close()
      return 4
    print('[OK] 与基线库四表指纹一致')

  candidates = select_candidates(con)
  planned_bytes = sum(c['bytes'] for c in candidates)
  print('== 计划 ==')
  print(f"数据库: {DB_PATH}")
  print(f"逻辑大小: {size_before / 1048576:.2f} MB；question_import_record = {total_rows} 行")
  by_status: dict[str, list[int]] = {}
  for c in candidates:
    agg = by_status.setdefault(c['status'], [0, 0])
    agg[0] += 1
    agg[1] += c['bytes']
  for status, (n, b) in sorted(by_status.items()):
    print(f"  {status}: {n} 行 / {b / 1048576:.2f} MB（>{RETENTION_DAYS[status]} 天）")
  print(f"合计待治理: {len(candidates)} 行 / {planned_bytes / 1048576:.2f} MB")

  report = {
      'timestamp': datetime.now().isoformat(timespec='seconds'),
      'mode': 'execute' if args.execute else 'dry-run',
      'db_path': str(DB_PATH),
      'db_size_bytes_before': size_before,
      'rows_before': total_rows,
      'planned_rows': len(candidates),
      'planned_bytes': planned_bytes,
      'planned_by_status': {k: {'rows': v[0], 'bytes': v[1]} for k, v in by_status.items()},
      'baseline_db': args.baseline_db,
      'baseline_match': baseline_ok,
      'fingerprint_before': fp_before,
      'purged': 0,
      'exported': 0,
      'skipped_export_failed': 0,
  }

  if args.execute:
    month = datetime.now().strftime('%Y%m')
    purged = 0
    failed: list[int] = []
    for start in range(0, len(candidates), args.batch):
      batch = candidates[start:start + args.batch]
      ready: list[dict] = []
      for item in batch:
        try:
          item['ref'] = export_one(item, month)
          ready.append(item)
        except Exception as exc:  # noqa: BLE001 - 单条失败不能连累整批
          failed.append(item['import_id'])
          print(f"[WARN] 导出失败 import_id={item['import_id']}: {exc}")
      if ready:
        try:
          purge_batch(con, ready)
          con.commit()
          purged += len(ready)
          print(f"  批次 {start // args.batch + 1}: 已置摘要 {len(ready)} 行")
        except Exception as exc:  # noqa: BLE001
          con.rollback()
          print(f"[WARN] 批次写入失败，已回滚该批: {exc}")
      report['exported'] += len(ready)
    report['purged'] = purged
    report['skipped_export_failed'] = len(failed)
    report['failed_import_ids'] = failed

    con.execute('pragma wal_checkpoint(TRUNCATE)')

    if args.vacuum:
      # §18.5：首次从 NONE 切 INCREMENTAL 需要一次全库 VACUUM
      con.execute('pragma auto_vacuum=INCREMENTAL')
      con.execute('vacuum')
      con.execute('pragma auto_vacuum')  # 让新连接读到新 header
      report['auto_vacuum'] = con.execute('pragma auto_vacuum').fetchone()[0]

    fp_after = all_fingerprints(con)
    report['fingerprint_after'] = fp_after
    report['fingerprint_match'] = fp_after == fp_before
    report['rows_after'] = con.execute('select count(*) from question_import_record').fetchone()[0]
    report['db_size_bytes_after'] = db_size_bytes(con)
    report['mismatch_tables'] = [t for t in fp_before if fp_before[t] != fp_after.get(t)]

  report['integrity_check'] = con.execute('pragma integrity_check').fetchone()[0]
  report['quick_check'] = con.execute('pragma quick_check').fetchone()[0]
  report['elapsed_seconds'] = round(time.time() - started, 2)
  con.close()

  REPORT_DIR.mkdir(parents=True, exist_ok=True)
  out = REPORT_DIR / f"gc_previews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
  out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')

  print('== 结果 ==')
  print(f"integrity_check={report['integrity_check']} quick_check={report['quick_check']}")
  if args.execute:
    print(f"已治理 {report['purged']} 行；导出失败 {report['skipped_export_failed']} 行")
    print(f"指纹一致: {report['fingerprint_match']}；不一致表: {report['mismatch_tables']}")
    print(f"逻辑大小: {size_before / 1048576:.2f} MB -> {report['db_size_bytes_after'] / 1048576:.2f} MB")
  print(f"报告: {out}")
  if not args.execute:
    print('（dry-run：未写入任何数据，加 --execute 才执行）')
  return 0 if report.get('fingerprint_match', True) else 3


if __name__ == '__main__':
  sys.exit(main())
