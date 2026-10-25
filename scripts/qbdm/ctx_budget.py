#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QBDM 装载预算闸 —— 装载前估算 token，对照 T0-T3 预算给放行/拦截结论。

为什么需要它：
    模型上下文里最贵的错误是"先读进来再说"。本脚本在读取之前把成本算清楚，
    让"超预算"从主观感觉变成可复现的数字（QBDM 五零指标中的 Z4）。

用法：
    python scripts/qbdm/ctx_budget.py --tier T2 AGENTS.md docs/README.md:1-20
    python scripts/qbdm/ctx_budget.py --tier T1 --json backend/app/main.py:600-643
    python scripts/qbdm/ctx_budget.py --tier T2 --log docs/plans/QBDM_装载账本.md api/v1/exam/

约定：
    - 条目写 `路径[:起始行-结束行]`；给目录时只统计规模，不读内容（入上下文成本记 0）。
    - 禁止入上下文的路径（题库/、static/、node_modules、.git）直接拦截。
    - token 估算用字符分类启发式（CJK 0.7 / 非 CJK 4 字符≈1 token），偏保守。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, asdict

# 预算档：tier -> 装载上限（估算 token）
TIER_BUDGET = {'T0': 8_000, 'T1': 25_000, 'T2': 60_000, 'T3': 60_000}

# 这些路径只允许传"路径+统计"，禁止把内容读入上下文
FORBIDDEN_PREFIXES = ('题库/', 'backend/app/static/', 'node_modules/', '.git/', 'dist/')

# 目录统计的字符单位：超过这个值的目录直接判 DANGER
DIR_WARN_BYTES = 50 * 1024 * 1024


@dataclass
class Item:
  raw: str
  path: str
  kind: str          # file | slice | dir | missing | forbidden
  lines: int
  chars: int
  tokens: int
  note: str = ''


def _estimate_tokens(text: str) -> int:
  """按字符类别估算 token：CJK 每字约 0.7 token，其余每 4 字符约 1 token。"""
  cjk = 0
  other = 0
  for ch in text:
    if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
      cjk += 1
    else:
      other += 1
  return int(cjk * 0.7 + other / 4.0) + 1


def _parse_item(raw: str) -> tuple[str, int | None, int | None]:
  """拆 `路径:起-止`。Windows 盘符里的冒号不算分隔符（只在最后一段尝试解析）。"""
  head, sep, tail = raw.rpartition(':')
  if sep and head and '-' in tail:
    start_s, _, end_s = tail.partition('-')
    if start_s.isdigit() and end_s.isdigit():
      return head, int(start_s), int(end_s)
  return raw, None, None


def _read_slice(path: str, start: int | None, end: int | None) -> tuple[str, int]:
  with open(path, 'r', encoding='utf-8', errors='replace') as fh:
    lines = fh.readlines()
  if start is not None and end is not None:
    # 行号按 1 起、闭区间
    chosen = lines[max(start - 1, 0):end]
  else:
    chosen = lines
  return ''.join(chosen), len(chosen)


def _dir_stat(path: str) -> tuple[int, int]:
  """目录只统计字节数与文件数，绝不读内容。"""
  total_bytes = 0
  count = 0
  for root, _dirs, files in os.walk(path):
    for name in files:
      try:
        total_bytes += os.path.getsize(os.path.join(root, name))
        count += 1
      except OSError:
        continue
  return total_bytes, count


def inspect(raw: str, repo_root: str) -> Item:
  norm = raw.replace('\\', '/')
  for prefix in FORBIDDEN_PREFIXES:
    if norm.startswith(prefix) or ('/' + prefix) in norm:
      return Item(raw, norm, 'forbidden', 0, 0, 0, f'命中禁入前缀 {prefix}：只允许传路径与统计')

  path, start, end = _parse_item(raw)
  abs_path = path if os.path.isabs(path) else os.path.join(repo_root, path)
  if not os.path.exists(abs_path):
    return Item(raw, path, 'missing', 0, 0, 0, '路径不存在')

  if os.path.isdir(abs_path):
    total_bytes, count = _dir_stat(abs_path)
    note = f'目录：{count} 文件 / {total_bytes / 1024 / 1024:.1f} MB（内容不入上下文，成本记 0）'
    if total_bytes > DIR_WARN_BYTES:
      note += ' ⚠ 超大目录，禁止遍历内容'
    return Item(raw, path, 'dir', 0, total_bytes, 0, note)

  try:
    text, line_count = _read_slice(abs_path, start, end)
  except OSError as exc:
    return Item(raw, path, 'missing', 0, 0, 0, f'读取失败：{exc}')
  return Item(raw, path, 'slice' if start is not None else 'file', line_count,
              len(text), _estimate_tokens(text))


def main(argv: list[str] | None = None) -> int:
  try:
    sys.stdout.reconfigure(encoding='utf-8')  # Windows GBK 控制台下打印中文/符号不炸
  except AttributeError:
    pass

  parser = argparse.ArgumentParser(description='QBDM 装载预算闸（读取前估算 token）')
  parser.add_argument('items', nargs='+', help='条目：路径 或 路径:起始行-结束行 或 目录')
  parser.add_argument('--tier', default='T2', choices=sorted(TIER_BUDGET), help='预算档，默认 T2')
  parser.add_argument('--json', action='store_true', help='输出 JSON（供脚本消费）')
  parser.add_argument('--log', default=None, help='把本次结论追加到指定 md 账本')
  parser.add_argument('--repo', default=os.getcwd(), help='仓库根，默认当前目录')
  args = parser.parse_args(argv)

  budget = TIER_BUDGET[args.tier]
  items = [inspect(raw, args.repo) for raw in args.items]
  total = sum(item.tokens for item in items)
  blocked = [item for item in items if item.kind in ('forbidden', 'missing')]
  verdict = 'FAIL' if blocked or total > budget else 'PASS'

  if args.json:
    payload = {
      'tier': args.tier,
      'budget': budget,
      'total_tokens': total,
      'verdict': verdict,
      'items': [asdict(item) for item in items],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
  else:
    print(f'QBDM 装载预算闸 | 档位 {args.tier} | 上限 ~{budget} tokens')
    print(f'{"条目":<48} {"类别":<9} {"行":>6} {"字符":>8} {"~tokens":>9}')
    print('-' * 84)
    for item in items:
      label = item.raw if len(item.raw) <= 46 else item.raw[:43] + '...'
      print(f'{label:<48} {item.kind:<9} {item.lines:>6} {item.chars:>8} {item.tokens:>9}')
      if item.note:
        print(f'    └ {item.note}')
    print('-' * 84)
    ratio = (total / budget * 100) if budget else 0
    print(f'合计 ~{total} tokens / 上限 {budget}（{ratio:.0f}%）')
    if blocked:
      print('结论 FAIL：存在禁入路径或缺失路径，改传"路径+统计"再试。')
    elif total > budget:
      print(f'结论 FAIL：超预算 {total - budget} tokens。请拆分成多段装载，或改用脚本统计代替读取。')
    else:
      print('结论 PASS：可装载。')

  if args.log:
    stamp = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    row = f'| {stamp} | {args.tier} | ~{total}/{budget} | {len(items)} | {verdict} |'
    need_header = not os.path.exists(args.log)
    with open(args.log, 'a', encoding='utf-8') as fh:
      if need_header:
        fh.write('# QBDM 装载账本（Z4 证据）\n\n| 时间 | 档位 | tokens/上限 | 条目数 | 结论 |\n|---|---|---|---|---|\n')
      fh.write(row + '\n')

  return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
  raise SystemExit(main())
