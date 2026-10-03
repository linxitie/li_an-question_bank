#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""行测语料探针（只读）

用途
----
1. 遍历 ``题库/行测`` 全部 PDF，产出结构清单 ``corpus_manifest.json``
2. 对指定试卷做「题本 vs 答案解析」逐题号差集诊断（110 vs 101 类问题）
3. 复现既有 G2 门禁基线（国考 2023 地市级 130 块），确认探针口径与生产解析器一致

**本脚本严格只读**：不写数据库、不修改任何业务代码、不触发 OCR
（实测 170/170 PDF 均有文本层，OCR 是纯浪费）。

与既有口径一致性
----------------
- 元数据提取口径对齐 ``question_import._auto_detect_tags`` 与 ``_detect_complete_paper``
- 分节锚点容错「标记与内容同行」（前序铁律：锚定 ``$`` 是脆弱假设）
- 分区身份只取词表、**不取序号**（实测同一分区出现过 ``一、``/``二、``/``四、`` 三种序号）

用法
----
    python backend/scripts/probe_xingce_corpus.py --out tmp/xingce_probe
    python backend/scripts/probe_xingce_corpus.py --pair "2023年安徽省" --diff
    python backend/scripts/probe_xingce_corpus.py --baseline-g2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pymupdf  # noqa: F401  (禁止使用已废弃的 fitz 别名)

DEFAULT_ROOT = r"D:\砺安题库\砺安题库\题库\行测"

# ── 正则（全部经 170/170 全量语料实测校准）──────────────────────────────────

# 分节头：`一、 政治理论：` / `四、 常识判断：` / `五、 科学推理`
# 序号不参与分区身份判定 —— 实测同一分区出现过三种序号。
# 行尾故意不锚 $，以容忍「标记与内容同行」这一常态。
SECTION_NAMES = (
    "政治理论", "常识判断", "常识", "言语理解与表达",
    "数量关系", "判断推理", "科学推理", "资料分析",
)
_SEC_ALT = "|".join(SECTION_NAMES)
RE_SECTION = re.compile(
    r"^[ \t]*[一二三四五六七八九十]{1,3}[、.．][ \t]*(" + _SEC_ALT + r")[ \t]*[：:]?",
    re.M,
)
# 分节头独占行且短 → 置信度高；用于统计与区间表
RE_SECTION_LINE = re.compile(
    r"^[ \t]*([一二三四五六七八九十]{1,3})[、.．][ \t]*(" + _SEC_ALT + r")[ \t]*[：:]?[ \t]*$",
    re.M,
)

# 题号：全卷连续 N. / N．/ N、   —— 必须带 re.M（行首锚）
RE_QNUM = re.compile(r"^[ \t]*(\d{1,3})[ \t]*[.．、][ \t]*\S", re.M)
# 选项：允许选项值为空（纯图片选项题，实测国考 2025 Q126 四选项文字全空）
RE_OPTION = re.compile(r"^[ \t]*([A-H])[ \t]*[.．、][ \t]*", re.M)
# 答案锚点：行首 `N. 正确答案：X`（85/85 全覆盖，无首页答案表）
# 必须带 re.M —— 锚点是行首 ^，漏掉会把命中率误报为 0%
RE_ANSWER = re.compile(r"^[ \t]*(\d{1,3})[ \t]*[.．、][ \t]*正确答案[：:]", re.M)
# 考点：行测独有，85/85 全覆盖；分隔符实测半角/全角逗号与顿号并存
RE_KAO = re.compile(r"【考点】[ \t]*\r?\n?([^\n【]{1,160})")
# 资料分析材料锚点：全角括号独占行（与申论的「材料1/给定资料N」完全不同）
RE_MATERIAL = re.compile(r"^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$", re.M)

# 年份 / 卷别（文件名提取；省份一律取文件夹名 —— 实测文件名省份写法极不可靠）
RE_YEAR = re.compile(r"(20\d{2})")
RE_PAPER_VARIANT = re.compile(r"（([^（）]{1,24}?(?:卷|类|网友回忆版))）")

ROLE_QB = "QB"   # 题本
ROLE_AN = "ANS"  # 答案解析


# ── 工具 ────────────────────────────────────────────────────────────────────

def pdf_text(doc: pymupdf.Document) -> str:
    pages = []
    for i in range(len(doc)):
        pages.append(str(doc[i].get_text("text")))
    return "\n".join(pages)


def year_of(filename: str):
    m = RE_YEAR.search(filename)
    return m.group(1) if m is not None else None


def variant_of(filename: str):
    hits = RE_PAPER_VARIANT.findall(filename)
    return hits[-1] if hits else None


def role_of(filename: str) -> str:
    return ROLE_AN if "答案" in filename else ROLE_QB


def pair_key(province: str, filename: str) -> str:
    """同套试卷的题本/答案解析配对键。

    容错的文件名异常（实测 5 类）：
      题干.pdf 冒充题本 / 试题 vs 题 / 区考 vs 省考 / 省份名缺「省」/ 括号全半角

    ⚠️ 关键：只剥「纯噪声」括号（内容恰为「网友回忆版」）。
    实测踩坑记录：
      - 广东「（县级卷）（网友回忆版）」/「（乡镇卷）（网友回忆版）」→ 须各自成对
      - 北京「（乡镇卷）（网友回忆版）」/「（区级及以上卷）（网友回忆版）」→ 须各自成对
      - 江苏「（A类）（网友回忆版）」…→「A类」须保留
      - 国考「（副省级网友回忆版）」/「（地市级网友回忆版）」→ 卷别与噪声混在**同一个**括号里，
        按「含卷/类则保留」的粗规则会被误剥，导致 3 个年份各自把副省级与地市级并成一套。
    故判定条件收紧为「括号内容 == 网友回忆版」才剥。
    """
    base = os.path.splitext(filename)[0]
    base = re.sub(r"(答案解析|答案|解析|题本|题干|试题|题)$", "", base)
    m = re.search(r"[（(]([^（）]*)[）)]$", base)
    if m is not None and m.group(1).strip() == "网友回忆版":
        base = base[: m.start()]
    return province + "::" + base


def probe_file(path: str) -> dict:
    with pymupdf.open(path) as doc:
        n_pages = len(doc)
        full = pdf_text(doc)
        img_per_page = [len(doc[i].get_images(full=True)) for i in range(n_pages)]

    sections = [
        {"ordinal": m.group(1), "name": m.group(2), "start": m.start()}
        for m in RE_SECTION_LINE.finditer(full)
    ]
    # 补齐区间终点
    for i, s in enumerate(sections):
        s["end"] = sections[i + 1]["start"] if i + 1 < len(sections) else len(full)

    qnums = [int(m.group(1)) for m in RE_QNUM.finditer(full)]
    options = [m.group(1) for m in RE_OPTION.finditer(full)]
    answers = {int(x) for x in RE_ANSWER.findall(full)}
    kao_raw = RE_KAO.findall(full)
    materials = [m.group(1) for m in RE_MATERIAL.finditer(full)]

    def contiguous(seq: list[int]) -> bool:
        if not seq:
            return True
        s = sorted(set(seq))
        return s == list(range(s[0], s[0] + len(s)))

    return {
        "path": path,
        "pages": n_pages,
        "chars": len(full),
        "images_total": sum(img_per_page),
        "images_per_page": img_per_page,
        "sections": sections,
        "section_names": [s["name"] for s in sections],
        "qnums": qnums,
        "qnums_contiguous": contiguous(qnums),
        "qnum_min": min(qnums) if qnums else None,
        "qnum_max": max(qnums) if qnums else None,
        "options": options,
        "option_count": len(options),
        "answers": sorted(answers),
        "answer_count": len(answers),
        "kao_raw": kao_raw,
        "kao_count": len(kao_raw),
        "materials": materials,
        "material_count": len(materials),
    }


def section_interval_table(rec: dict) -> list[dict]:
    """每个分节的题号区间 —— G2 安全网的核心断言对象。"""
    full = rec["_full"]
    out = []
    for s in rec["sections"]:
        seg = full[s["start"]: s["end"]]
        nums = [int(m.group(1)) for m in RE_QNUM.finditer(seg)]
        out.append({
            "name": s["name"],
            "ordinal": s["ordinal"],
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
            "count": len(nums),
        })
    return out


# ── 命令 ────────────────────────────────────────────────────────────────────

def cmd_corpus(args) -> int:
    root = args.root
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    records = []
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for fname in sorted(os.listdir(pdir)):
            if not fname.lower().endswith(".pdf"):
                continue
            rec = probe_file(os.path.join(pdir, fname))
            rec.pop("images_per_page", None)
            rec.update({
                "province": province,
                "filename": fname,
                "role": role_of(fname),
                "year": year_of(fname),
                "paper_variant": variant_of(fname),
                "pair_key": pair_key(province, fname),
            })
            records.append(rec)

    # 变式汇总
    qb = [r for r in records if r["role"] == ROLE_QB]
    an = [r for r in records if r["role"] == ROLE_AN]
    sec_vocab = Counter(n for r in qb for n in r["section_names"])

    summary = {
        "total_files": len(records),
        "qb_files": len(qb),
        "ans_files": len(an),
        "unpaired": sorted({r["pair_key"] for r in records})[:0] or [],
        "qb_total_pages": sum(r["pages"] for r in qb),
        "ans_total_pages": sum(r["pages"] for r in an),
        "qb_total_chars": sum(r["chars"] for r in qb),
        "ans_total_chars": sum(r["chars"] for r in an),
        "section_head_hit_rate": round(
            100.0 * sum(1 for r in qb if r["sections"]) / max(len(qb), 1), 2),
        "answer_anchor_hit_rate": round(
            100.0 * sum(1 for r in an if r["answer_count"]) / max(len(an), 1), 2),
        "kao_hit_rate": round(
            100.0 * sum(1 for r in an if r["kao_count"]) / max(len(an), 1), 2),
        "material_hit_rate": round(
            100.0 * sum(1 for r in qb if r["material_count"]) / max(len(qb), 1), 2),
        "total_materials": sum(r["material_count"] for r in qb),
        "qnums_contiguous_rate": round(
            100.0 * sum(1 for r in qb if r["qnums_contiguous"]) / max(len(qb), 1), 2),
        "section_vocab": dict(sec_vocab.most_common()),
        "papers_per_province": dict(Counter(r["province"] for r in qb)),
    }
    # 配对完整性
    pair_roles = defaultdict(set)
    for r in records:
        pair_roles[r["pair_key"]].add(r["role"])
    summary["complete_pairs"] = sum(1 for v in pair_roles.values() if v == {ROLE_QB, ROLE_AN})
    summary["broken_pairs"] = [k for k, v in pair_roles.items() if v != {ROLE_QB, ROLE_AN}]

    with open(os.path.join(out_dir, "corpus_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "corpus_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print(f"[corpus] files={summary['total_files']} "
          f"QB={summary['qb_files']} ANS={summary['ans_files']} "
          f"pairs={summary['complete_pairs']} broken={len(summary['broken_pairs'])}")
    print(f"[corpus] section_head_hit={summary['section_head_hit_rate']}%  "
          f"answer_anchor_hit={summary['answer_anchor_hit_rate']}%  "
          f"kao_hit={summary['kao_hit_rate']}%  material_hit={summary['material_hit_rate']}%")
    print(f"[corpus] qnums_contiguous={summary['qnums_contiguous_rate']}%  "
          f"total_materials={summary['total_materials']}")
    print(f"[corpus] section_vocab={summary['section_vocab']}")
    if summary["broken_pairs"]:
        print(f"[corpus] BROKEN PAIRS: {summary['broken_pairs']}")
    return 0


def cmd_diff(args) -> int:
    """逐题号比对题本与答案解析，输出差集及双侧原文上下文。"""
    root = args.root
    needle = args.pair
    found = defaultdict(dict)
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for fname in sorted(os.listdir(pdir)):
            if not fname.lower().endswith(".pdf") or needle not in fname:
                continue
            rec = probe_file(os.path.join(pdir, fname))
            rec.pop("images_per_page", None)
            rec["_path"] = os.path.join(pdir, fname)
            found[pair_key(province, fname)][role_of(fname)] = rec

    if not found:
        print(f"[diff] 未找到匹配 '{needle}' 的试卷")
        return 2

    for key, pair in found.items():
        qb, an = pair.get(ROLE_QB), pair.get(ROLE_AN)
        print("=" * 78)
        print(f"[diff] {key}")
        if not qb or not an:
            print(f"        配对不完整 QB={bool(qb)} ANS={bool(an)}")
            continue
        print(f"        题本: {os.path.basename(qb['_path'])}  "
              f"题号数={len(qb['qnums'])} 选项数={qb['option_count']} "
              f"范围={qb['qnum_min']}~{qb['qnum_max']}")
        print(f"        解析: {os.path.basename(an['_path'])}  "
              f"题号数={len(an['qnums'])} 答案锚点={an['answer_count']} "
              f"考点={an['kao_count']} 范围={an['qnum_min']}~{an['qnum_max']}")
        print(f"        分节题本={qb['section_names']}")
        print(f"        分节解析={an['section_names']}")

        qn, an_set = set(qb["qnums"]), set(an["answers"])
        only_q = sorted(qn - an_set)
        only_a = sorted(an_set - qn)
        print(f"        题本题号 {len(qn)} / 答案锚点 {len(an_set)} / 差 {len(only_q) + len(only_a)}")
        print(f"        only_in_questions={only_q}")
        print(f"        only_in_answers={only_a}")

        # 分节区间表（G2 安全网断言对象）
        with pymupdf.open(qb["_path"]) as d:
            qb["_full"] = pdf_text(d)
        with pymupdf.open(an["_path"]) as d:
            an["_full"] = pdf_text(d)
        tq, ta = section_interval_table(qb), section_interval_table(an)
        print("        分节区间表（题本 vs 解析）：")
        for i in range(max(len(tq), len(ta))):
            a = tq[i] if i < len(tq) else None
            b = ta[i] if i < len(ta) else None
            flag = "" if (a and b and a["name"] == b["name"]) else "  ← 不一致"
            fmt = lambda x: (f"{x['name']}({x['ordinal']}) {x['min']}~{x['max']}"
                             f"[{x['count']}]") if x else "-"
            print(f"          {fmt(a):<28} | {fmt(b):<28}{flag}")

        # 差集逐题打印双侧上下文（人工可判读成因）
        ctx = args.context
        for label, nums, src, anchor in (
            ("only_in_questions", only_q, qb, RE_QNUM),
            ("only_in_answers", only_a, an, RE_ANSWER),
        ):
            if not nums:
                continue
            print(f"\n        ── {label} 逐题上下文 ──")
            full = src["_full"]
            for n in nums:
                m = next((m for m in anchor.finditer(full)
                          if int(m.group(1)) == n), None)
                if not m:
                    print(f"          #{n}: 定位失败")
                    continue
                seg = full[m.start(): m.start() + ctx].replace("\n", " ⏎ ")
                print(f"          #{n}: {seg}")
    return 0


def cmd_g2(args) -> int:
    """复现既有 G2 基线：国考 2023 地市级 题本+答案。"""
    root = args.root
    target = args.target
    qb = an = None
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for fname in sorted(os.listdir(pdir)):
            if not fname.lower().endswith(".pdf"):
                continue
            if target in fname:
                rec = probe_file(os.path.join(pdir, fname))
                if role_of(fname) == ROLE_QB and qb is None:
                    qb = rec
                elif role_of(fname) == ROLE_AN and an is None:
                    an = rec
    if not qb or not an:
        print(f"[g2] 未找到 '{target}'")
        return 2
    exp = args.expect
    got_q = len(set(qb["qnums"]))
    got_opt = qb["option_count"]
    got_ans = an["answer_count"]
    rate = (len(set(qb["qnums"]) & set(an["answers"])) / max(got_q, 1)) * 100
    print(f"[g2] target={target}")
    print(f"[g2] 题本块数        = {got_q}   (期望 {exp['blocks']})")
    print(f"[g2] 题本 options    = {got_opt}   (期望 {exp['options']})")
    print(f"[g2] 题号连续        = {qb['qnums_contiguous']}   (期望 True)")
    print(f"[g2] 答案锚点数      = {got_ans}")
    print(f"[g2] 配对率(题号join) = {rate:.2f}%   (期望 >= {exp['match_rate']})")
    ok = (got_q == exp["blocks"] and got_opt == exp["options"]
          and qb["qnums_contiguous"] and rate >= exp["match_rate"])
    print(f"[g2] RESULT = {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="行测语料探针（只读）")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out", default="tmp/xingce_probe")
    ap.add_argument("--pair", help="按文件名子串定位一套试卷并输出差集")
    ap.add_argument("--diff", action="store_true", help="启用差集诊断")
    ap.add_argument("--baseline-g2", action="store_true", help="复现 G2 基线")
    ap.add_argument("--target", default="2023年国家公务员录用考试《行测》题（地市级")
    ap.add_argument("--expect", default='{"blocks":130,"options":130,"match_rate":99.0}')
    ap.add_argument("--context", type=int, default=300)
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"[error] 语料根目录不存在: {args.root}")
        return 2

    if args.baseline_g2:
        args.expect = json.loads(args.expect)
        return cmd_g2(args)
    if args.diff:
        return cmd_diff(args)
    return cmd_corpus(args)


if __name__ == "__main__":
    sys.exit(main())