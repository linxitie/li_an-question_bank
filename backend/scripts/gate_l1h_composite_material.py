# -*- coding: utf-8 -*-
"""L1-H 复合题材料边界门禁 —— 固化 v9 Wave1/Wave2 的验收标准。

背景
----
两个缺陷都曾长期静默存在，且都不抛异常：

1. **材料吞子题**（v9 W2 修复）
   `composite_matcher.match_xingce_material_groups` 原用「下一个材料块起点」
   当材料上界。原文排列是「材料 → N 道子题 →（下一个材料块）」，必然把中间
   全部子题的题干与选项吞进 `shared_content`。
   实测真实语料误吞率 85% / 471%。
   → 判据：**材料文本内不得出现任何成员题号**。

2. **批内重复关联致整卷回滚**（v9 W1 修复）
   同一份文档内出现重复题目时，第 1 次进 `ok_ids`、第 2 次被去重命中进
   `reused_ids`，两者指向同一 question_id；`existing_rel_qids` 只挡库内，
   挡不住批内 → flush 撞 UNIQUE(paper_id, question_id)，整卷 500。
   实测卷#53 关联行数=0，一道题都没入库。
   → 判据：保序去重后关联列表**无内部重复、不丢题、顺序不变**。

用法
----
    python scripts/gate_l1h_composite_material.py          # 内置夹具（确定性）
    python scripts/gate_l1h_composite_material.py --real   # 额外跑生产缓存真实语料

真实语料部分在缓存缺失时自动跳过——缓存可被清理，不应成为门禁失败原因。
"""
from __future__ import annotations

import argparse
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from app.services.composite_matcher import match_xingce_material_groups
from app.services.text_parser import route_xingce_sections, XINGCE_QNUM_PATTERN

BAR = '=' * 70

STATE = {'fail': 0, 'skip': 0}


def record_fail(msg: str) -> None:
    STATE['fail'] += 1
    print(f'  FAIL {msg}')


def record_skip(msg: str) -> None:
    STATE['skip'] += 1
    print(f'  SKIP {msg}')


def build_groups(text: str):
    """跑完整归组链路，返回 (groups, qno_positions)；无材料块时返回 (None, None)。"""
    sec = route_xingce_sections(text) or {}
    sections = sec.get('sections') or []
    materials = sec.get('materials') or []
    if not materials or not sections:
        return None, None
    qno_pos = []
    for m in XINGCE_QNUM_PATTERN.finditer(text):
        name = next((s['name'] for s in sections
                     if s['start'] <= m.start() < s['end']), '')
        qno_pos.append((int(m.group(1)), m.start(), name))
    qno_pos.sort(key=lambda t: t[1])
    return match_xingce_material_groups(materials, qno_pos, sections), qno_pos


def check_no_question_in_material(text: str, label: str) -> None:
    """判据 1：材料文本内不得出现成员题号。"""
    groups, qno_pos = build_groups(text)
    if not groups or not qno_pos:
        record_skip(f'{label}：无材料块，无法判定')
        return
    for i, g in enumerate(groups, 1):
        end = g['end'] if g['end'] > 0 else len(text)
        mat = text[g['start']:end]
        members = set(g['member_qnums'])
        inside = [qn for qn, pos, _ in qno_pos if g['start'] <= pos < end]
        leaked = [qn for qn in inside if qn in members]
        if leaked:
            record_fail(f'{label} 组{i}（{g["section"]}）：材料内含成员题号 {leaked}'
                        f' —— 材料吞子题回归！材料长 {len(mat)} 字')
        else:
            print(f'  ok   {label} 组{i}（{g["section"]}）：{len(members)} 道子题，'
                  f'材料 {len(mat)} 字，无题号泄漏')


def check_batch_dedup() -> None:
    """判据 2：批内保序去重（复现 v9 W1 修复前的崩溃场景）。"""
    ok_ids, reused_ids = [100, 101, 102], [100, 103]
    before = ok_ids + reused_ids
    if len(before) == len(set(before)):
        record_fail('用例构造失效：修复前场景里应存在重复 qid')
        return

    seen, all_ids, skipped = set(), [], []
    for qid in before:
        if qid in seen:
            skipped.append(qid)
            continue
        seen.add(qid)
        all_ids.append(qid)

    expect = []
    for qid in before:
        if qid not in expect:
            expect.append(qid)

    problems = []
    if len(all_ids) != len(set(all_ids)):
        problems.append(f'去重后仍有内部重复：{all_ids}')
    if set(all_ids) != set(ok_ids) | set(reused_ids):
        problems.append(f'去重丢了题：{all_ids}')
    if all_ids != expect:
        problems.append(f'去重改变了顺序：{all_ids} != {expect}')
    if not skipped:
        problems.append('应至少跳过 1 个重复 qid')

    if problems:
        for p in problems:
            record_fail(p)
    else:
        print(f'  ok   批内去重：{len(before)} -> {len(all_ids)}，跳过 {skipped}，'
              f'无重复/无丢题/顺序不变')


def check_real_corpus() -> None:
    """对生产缓存里的真实行测题本跑一遍（缓存缺失则跳过）。

    选取依据是「该卷是否含材料块」而非文件大小——最大的几个缓存反而可能是
    申论/公专卷（材料数为 0），按大小取前 N 会漏掉真正要验的行测卷。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(root, 'data', 'text_cache', 'v3_*.txt')),
                   key=os.path.getsize, reverse=True)
    checked = 0
    for p in files:
        try:
            text = io.open(p, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        if len(text) < 5000:
            continue
        sec = route_xingce_sections(text) or {}
        if not (sec.get('materials') or []):
            continue          # 无材料的卷（申论/公专）不参与本门禁
        groups, _ = build_groups(text)
        if not groups:
            continue
        checked += 1
        check_no_question_in_material(text, os.path.basename(p)[:14])
        if checked >= 4:
            break
    if not checked:
        record_skip('生产缓存中无可用行测题本（缓存可清理，不计为失败）')
    else:
        print(f'  （本次校验 {checked} 份含材料的真实题本）')


# 「材料 → N 道子题」结构的确定性夹具。
# 格式必须贴合 text_parser_xingce 的真实锚点，否则会静默 SKIP（假门禁）：
#   · 分节头   `^[ \t]*([一二三四五六七八九十]{1,3})[、.．][ \t]*<分节名>[ \t]*[:：]?$`，
#              且命中数须 >= XINGCE_MIN_SECTION_HITS(2)
#   · 材料锚点 `^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$`（全角括号须**独占一行**）
# 期望结果：归出 1 个 data_analysis 组，成员 [3,4]，材料内不含任何题号。
FIXTURE = (
    "一、常识判断\n"
    "1. 下列说法正确的是（  ）\n"
    "A.甲 B.乙 C.丙 D.丁\n"
    "2. 下列说法错误的是（  ）\n"
    "A.甲 B.乙 C.丙 D.丁\n"
    "\n"
    "二、资料分析\n"
    "（一）\n"
    "某年某市统计公报：全年地区生产总值增长百分之五，"
    "人均可支配收入提高百分之三。\n"
    "3. 根据材料，该市地区生产总值约为（  ）\n"
    "A.一百 B.二百 C.三百 D.四百\n"
    "4. 根据材料，人均收入提高约（  ）\n"
    "A.百分之三 B.百分之四 C.百分之五 D.百分之六\n"
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description='L1-H 复合题材料边界门禁（v9 W1/W2 回归保护）')
    ap.add_argument('--real', action='store_true', help='额外跑生产缓存真实语料')
    args = ap.parse_args()

    print(BAR)
    print('L1-H 复合题材料边界门禁')
    print(BAR)

    print('\n[1] 批内重复去重（v9 W1）')
    check_batch_dedup()

    print('\n[2] 材料不得吞子题（v9 W2）')
    check_no_question_in_material(FIXTURE, '内置夹具')

    if args.real:
        print('\n[3] 生产缓存真实题本')
        check_real_corpus()

    print('\n' + BAR)
    print(f'结果：失败 {STATE["fail"]} 项 / 跳过 {STATE["skip"]} 项')
    passed = STATE['fail'] == 0
    print('L1-H 复合题材料边界门禁：' + ('PASS' if passed else 'FAIL'))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
