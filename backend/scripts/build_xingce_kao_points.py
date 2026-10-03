#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""行测考点清单构建（任务 5）

从 85 套「答案解析」PDF 抽取 ``【考点】`` 字段，产出可复现的知识点清单。

背景
----
实测行测答案解析 **85/85 覆盖** ``【考点】``，是行测独有的免费增值
（申论/公专答案解析均无此字段）。但它有两个必须先解决的问题：

1. **层级化路径**：语料中大量形如 ``词的辨析-搭配对象`` / ``中心理解题-关联词-转折``，
   是 2~3 级路径，而 ``knowledge_point`` 表需以 ``parent_id``/``level`` 承载
2. **省份私有考点**：``江苏特色-综合资料``（97 次）若直接入库会产生 24 套互不相同的
   省级私有知识点，污染全局树

关键决策
--------
- **层级分隔符** = ``-``（语料实证，非推测）
- **省份前缀剥离** = ``^(省份|国考|多省)特色[-－]?\\s*`` → 剥离后映射到全局节点；
  剥离后全局不存在者，保留原名但打 ``province_scoped`` 标，**不与全局节点混同**
- **长尾全保留**：74 个 token 出现 ≤2 次、34 个仅 1 次。按前序铁律
  「关键词表完备性无法靠推理保证，只能靠语料穷举」，**一律不丢弃**，只打频率档
- **不新建表**：层级用 ``knowledge_point.parent_id`` + ``level`` 承载

用法
----
    python scripts/build_xingce_kao_points.py --out data/xingce_kao_points.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
DEFAULT_ROOT = r"D:\砺安题库\砺安题库\题库\行测"

RE_KAO = re.compile(r"【考点】[ \t]*\r?\n?([^\n【]{1,160})")
RE_SPLIT = re.compile(r"[,，、;；/／]+")
RE_HIER = re.compile(r"[-－—–]+")
RE_SEC = re.compile(
    r"^[ \t]*[一二三四五六七八九十]{1,3}[、.．][ \t]*"
    r"(政治理论|常识判断|常识|言语理解与表达|数量关系|判断推理|科学推理|资料分析)"
    r"[ \t]*[：:]?[ \t]*$", re.M)

PROVINCES = (
    "内蒙古|北京|吉林|国考|多省|宁夏|安徽|山东|山西|广东|广西|江苏|江西|河北|河南|"
    "海南|湖北|湖南|甘肃|福建|贵州|辽宁|陕西|青海|黑龙江|深圳|新疆|兵团"
)
RE_PROV_PREFIX = re.compile(r"^(?:" + PROVINCES + r")\s*特色\s*[-－—–]?\s*")


def freq_tier(n: int) -> str:
    if n >= 50:
        return "high"
    if n >= 10:
        return "medium"
    if n >= 3:
        return "low"
    return "rare"


def load_pdf_text(path: str) -> str:
    import pymupdf
    with pymupdf.open(path) as d:
        pages = []
        for i in range(len(d)):
            pages.append(str(d[i].get_text("text")))
    return "\n".join(pages)


def build(root: str) -> dict:
    tokens = Counter()          # token -> 出现次数
    token_secs = defaultdict(Counter)   # token -> {section: n}
    token_papers = defaultdict(set)     # token -> {paper_key}
    papers = {}                          # paper_key -> meta
    marker_total = 0

    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for name in sorted(os.listdir(pdir)):
            if not name.lower().endswith(".pdf") or "答案" not in name:
                continue
            key = province + "::" + name
            text = load_pdf_text(os.path.join(pdir, name))

            secs = [m.group(1) for m in RE_SEC.finditer(text)]
            papers[key] = {"province": province, "file": name,
                           "sections": secs, "markers": 0}

            for m in RE_KAO.finditer(text):
                papers[key]["markers"] += 1
                marker_total += 1
                # 归属分区：取该【考点】之前最近的分区头
                sec = "未分区"
                for sm in RE_SEC.finditer(text):
                    if sm.start() < m.start():
                        sec = sm.group(1)
                    else:
                        break
                raw = m.group(1).strip()
                for tok in RE_SPLIT.split(raw):
                    tok = tok.strip()
                    if not tok or len(tok) > 60:
                        continue
                    tokens[tok] += 1
                    token_secs[tok][sec] += 1
                    token_papers[tok].add(key)

    # 组装清单
    roots = set()
    items = []
    for tok, cnt in tokens.most_common():
        stripped = RE_PROV_PREFIX.sub("", tok).strip()
        province_scoped = bool(RE_PROV_PREFIX.match(tok))
        parts = [p.strip() for p in RE_HIER.split(stripped) if p.strip()]
        level = len(parts)
        root_name = parts[0] if parts else stripped
        if level == 1:
            roots.add(root_name)
        items.append({
            "token": tok,
            "count": cnt,
            "freq_tier": freq_tier(cnt),
            "province_scoped": province_scoped,
            "path": parts,
            "level": level,
            "root": root_name,
            "normalized": stripped,
            "sections": dict(token_secs[tok].most_common()),
            "papers": sorted(token_papers[tok]),
        })

    return {
        "meta": {
            "root": root,
            "papers": len(papers),
            "markers_total": marker_total,
            "distinct_tokens": len(items),
            "distinct_roots": len(roots),
            "hier_tokens": sum(1 for i in items if i["level"] > 1),
            "province_scoped": sum(1 for i in items if i["province_scoped"]),
            "freq_tiers": dict(Counter(i["freq_tier"] for i in items)),
        },
        "roots": sorted(roots),
        "items": items,
    }


def reverse_lookup_verify(root: str, items: list, sample: int = 20) -> dict:
    """抽样反查：清单中的 token 必须能在答案解析原文里定位到至少一个题号。"""
    step = max(1, len(items) // sample)
    picked = items[::step][:sample]
    hits, misses = 0, []
    for it in picked:
        found = False
        for province in sorted(os.listdir(root)):
            pdir = os.path.join(root, province)
            if not os.path.isdir(pdir):
                continue
            for name in sorted(os.listdir(pdir)):
                if not (name.lower().endswith(".pdf") and "答案" in name):
                    continue
                if province + "::" + name not in set(it["papers"]):
                    continue
                text = load_pdf_text(os.path.join(pdir, name))
                if it["token"] in text:
                    found = True
                    break
            if found:
                break
        if found:
            hits += 1
        else:
            misses.append(it["token"])
    return {"sampled": len(picked), "hits": hits,
            "misses": misses, "rate": round(hits * 100.0 / max(len(picked), 1), 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="行测考点清单构建")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out", default=os.path.join(BACKEND_DIR, "data", "xingce_kao_points.json"))
    ap.add_argument("--verify", action="store_true", help="抽样反查 token")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print("[error] 语料根目录不存在: %s" % args.root)
        return 2

    data = build(args.root)
    m = data["meta"]
    print("卷数                : %d" % m["papers"])
    print("【考点】标记总数    : %d" % m["markers_total"])
    print("不同 token 数       : %d" % m["distinct_tokens"])
    print("根节点数            : %d" % m["distinct_roots"])
    print("层级化 token(>1级)  : %d" % m["hier_tokens"])
    print("省份私有 token      : %d" % m["province_scoped"])
    print("频率档分布          : %s" % m["freq_tiers"])
    print()
    print("ROOT 节点 (%d): %s" % (len(data["roots"]), "、".join(data["roots"])))

    if args.verify:
        v = reverse_lookup_verify(args.root, data["items"])
        print()
        print("抽样反查: %d/%d 命中 (%.1f%%)  未命中=%s"
              % (v["hits"], v["sampled"], v["rate"], v["misses"]))
        if v["misses"]:
            return 1

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    print()
    print("已写出: %s (%d 字节)" % (os.path.basename(args.out), os.path.getsize(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())