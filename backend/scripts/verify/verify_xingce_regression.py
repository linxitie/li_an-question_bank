# -*- coding: utf-8 -*-
"""
verify_xingce_regression.py — 行测解析器回归门禁（G2）
=================================================

对 ``题库/行测`` 下 85 套「题本+答案解析」逐套解析，输出可跨版本对比的指标表，
并支持 ``--compare`` 做逐项diff（任一项不一致即退出码非 0）。

用法
----
    # 建立/刷新基线
    python scripts/verify_xingce_regression.py "<行测目录>" --out data/xingce_regression_baseline.txt

    # 对比基线（改动后必跑）
    python scripts/verify_xingce_regression.py "<行测目录>" \
        --compare data/xingce_regression_baseline.txt --out data/xingce_regression.txt

    # 增量：只重跑解析，不重跑 PDF 文本提取（改一行解析代码 1 秒级跑完）
    python scripts/verify_xingce_regression.py "<行测目录>" --reparse --cache-dir data/xingce_cache

设计要点（继承 verify_parser_regression.py 的既有约定）
------------------------------------------------------
1. **必须用生产解析器** ``text_parser.extract_question_blocks``，否则测的不是线上行为
2. **分节探针独立实现**：避免「用被测代码测被测代码」。若 ``text_parser`` 已提供
   ``route_xingce_sections``（任务 7 产出），优先使用生产实现；否则回退本地探针，
   使本门禁在任务 7 之前即可运行。
3. **不写数据库、不触网、不调LLM**，可离线复现
4. **伪题号探针**：行测资料分析解析里「小数+单位」文本落在行首会被误判为题号
   （实测安徽 2023 第 780 块吞掉 101–110 共 10 题）。本门禁显式统计该指标，
   任务 8 修复后应下降。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_DIR)

from app.services.text_parser import extract_question_blocks  # noqa: E402

# ── 分节探针（优先用生产实现，否则本地独立实现）──────────────────────────────
XINGCE_SECTION_ALT = (
    "政治理论|常识判断|常识|言语理解与表达|数量关系|判断推理|科学推理|资料分析"
)
_LOCAL_SECTION_RE = re.compile(
    r"^[ \t]*[一二三四五六七八九十]{1,3}[、.．][ \t]*(" + XINGCE_SECTION_ALT + r")"
    r"[ \t]*[：:]?[ \t]*$",
    re.M,
)
_LOCAL_MATERIAL_RE = re.compile(r"^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$", re.M)
_LOCAL_ANSWER_RE = re.compile(r"^[ \t]*(\d{1,3})[ \t]*[.．、][ \t]*正确答案[：:]", re.M)
_LOCAL_KAO_RE = re.compile(r"【考点】[ \t]*\r?\n?([^\n【]{1,160})")

# 任务 7 产出 route_xingce_sections 后自动切到生产实现；此前用本地独立探针。
# 用 getattr 动态取，避免任务 7 未完成时产生静态导入错误。
try:
    import app.services.text_parser as _tp
    _prod_router = getattr(_tp, "route_xingce_sections", None)
    _HAS_PROD_ROUTER = callable(_prod_router)
except Exception:  # noqa: BLE001
    _prod_router = None
    _HAS_PROD_ROUTER = False


def probe_sections(text: str):
    """返回 [(name, start, end)]。优先生产实现。"""
    if _HAS_PROD_ROUTER and _prod_router is not None:
        try:
            r = _prod_router(text)
            if r:
                return [(s["name"], s["start"], s["end"]) for s in r.get("sections", [])]
            return []
        except Exception:  # noqa: BLE001
            pass
    ms = list(_LOCAL_SECTION_RE.finditer(text))
    out = []
    for i, m in enumerate(ms):
        out.append((m.group(1), m.start(),
                    ms[i + 1].start() if i + 1 < len(ms) else len(text)))
    return out


def pdf_text(path: str) -> str:
    import pymupdf
    with pymupdf.open(path) as d:
        pages = []
        for i in range(len(d)):
            pages.append(str(d[i].get_text("text")))
    return "\n".join(pages)


# ── 语料枚举（容错 5 类文件名异常）──────────────────────────────────────────
ROLE_QB, ROLE_AN = "QB", "ANS"
_NOISE_TAIL = re.compile(r"[（(]([^（）]*)[）)]$")


def role_of(name: str) -> str:
    return ROLE_AN if "答案" in name else ROLE_QB


def pair_key(province: str, name: str) -> str:
    base = os.path.splitext(name)[0]
    base = re.sub(r"(答案解析|答案|解析|题本|题干|试题|题)$", "", base)
    m = _NOISE_TAIL.search(base)
    if m is not None and m.group(1).strip() == "网友回忆版":
        base = base[: m.start()]
    return province + "::" + base


def qnums_of(blocks) -> list:
    out = []
    for b in blocks:
        n = str(b.get("question_number", ""))
        if n.isdigit():
            out.append(int(n))
    return out


# ── 已知不一致白名单（伪题号导致的区间漂移）────────────────────────────────
#
# 背景：资料分析/知觉速度题型里，解析文本存在「小数+单位」落在行首的伪题号
# （`41.8％`、`10.5%`、`352.`），以及图形/小标题编号（`2.` `6.`）。这类套的
# 分节题号区间与题本端必然对不上，但**不是解析器退化**。若不放白名单，
# L2 会常年红灯，红灯本身失去信息量。
#
# 白名单只豁免「签名完全一致」的已知不一致：任何数值漂移都会重新 FAIL，
# 因此它挡得住「退化被藏进白名单」。
DEFAULT_MISMATCH_BASELINE = os.path.join(
    BACKEND_DIR, "data", "gates", "xingce_rng_known_mismatch.json")


def _sig(payload) -> str:
    import hashlib
    import json as _json
    raw = _json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_mismatch_baseline(path: str) -> dict:
    """返回 {key: {'sig':..., 'note':...}}；文件不存在返回 {}。"""
    if not path or not os.path.exists(path):
        return {}
    try:
        with io.open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception:  # noqa: BLE001 — 白名单损坏按「没有白名单」处理，宁可红
        print("[mismatch-baseline] 无法解析 %s，按空白名单处理" % path)
        return {}
    return doc.get("known", {}) if isinstance(doc, dict) else {}


def write_mismatch_baseline(path: str, records: dict) -> None:
    """把当前不一致写成白名单（签名 + 说明），供后续回归对比。"""
    import json as _json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generated_by": "scripts/verify/verify_xingce_regression.py --write-mismatch-baseline",
            "why": "行测资料分析/知觉速度语料的伪题号导致分节区间漂移；签名一致才豁免",
            "count": len(records),
        },
        "known": records,
    }
    with io.open(path, "w", encoding="utf-8") as fh:
        _json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("[mismatch-baseline] 已写入 %d 条已知不一致 → %s" % (len(records), path))


# ── 主流程 ──────────────────────────────────────────────────────────────────

def scan(root: str, out_path: str, cache_dir: str = "", reparse: bool = False,
         mismatch_baseline: str = DEFAULT_MISMATCH_BASELINE,
         write_mismatch: bool = False) -> int:
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)

    pairs = defaultdict(dict)
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for name in sorted(os.listdir(pdir)):
            if not name.lower().endswith(".pdf"):
                continue
            pairs[pair_key(province, name)][role_of(name)] = os.path.join(pdir, name)

    f = io.open(out_path, "w", encoding="utf-8")
    w = f.write

    w("行测解析器回归报告  (目录: %s)\n" % root)
    w("分节探针: %s\n" % ("生产 route_xingce_sections" if _HAS_PROD_ROUTER
                          else "本地独立探针（任务 7 产出后自动切换为生产实现）"))
    w("=" * 132 + "\n")
    w("%-3s %-30s %-4s %5s %5s %-9s %6s %6s %6s %6s %s\n" % (
        "#", "试卷", "角色", "块数", "题号", "题号区间", "分节",
        "答案锚点", "考点", "材料", "区间全等"))
    w("-" * 132 + "\n")

    tot = Counter()
    per_pair = {}
    bad_pairs = []
    known = load_mismatch_baseline(mismatch_baseline)
    mismatch_records = {}
    new_keys = []
    drift_keys = []

    for idx, key in enumerate(sorted(pairs), 1):
        pr = pairs[key]
        qb_path, an_path = pr.get(ROLE_QB), pr.get(ROLE_AN)
        if not qb_path or not an_path:
            bad_pairs.append(key)
            w("%-3d %-30s  INCOMPLETE-PAIR (QB=%s ANS=%s)\n" % (
                idx, key[-30:], bool(qb_path), bool(an_path)))
            continue

        rec = {}
        for role, path in ((ROLE_QB, qb_path), (ROLE_AN, an_path)):
            cache_f = (os.path.join(cache_dir, key.replace("::", "__").replace("/", "_")
                                    + "." + role + ".txt") if cache_dir else "")
            text = None
            if cache_f and os.path.exists(cache_f) and not reparse:
                with io.open(cache_f, encoding="utf-8") as fh:
                    text = fh.read()
            if text is None:
                text = pdf_text(path)
                if cache_f:
                    with io.open(cache_f, "w", encoding="utf-8") as fh:
                        fh.write(text)
            rec[role] = text

        qb_text, an_text = rec[ROLE_QB], rec[ROLE_AN]
        qb_blocks = extract_question_blocks(qb_text)
        an_blocks = extract_question_blocks(an_text)
        if not qb_blocks:
            bad_pairs.append(key)
            w("%-3d %-30s  0-BLOCKS\n" % (idx, key[-30:]))
            continue

        qsec = probe_sections(qb_text)
        asec = probe_sections(an_text)

        qn = qnums_of(qb_blocks)
        an_anchor = {int(x) for x in _LOCAL_ANSWER_RE.findall(an_text)}
        kao = _LOCAL_KAO_RE.findall(an_text)
        mat = _LOCAL_MATERIAL_RE.findall(qb_text)

        # 分节 → 题号区间（安全网的核心断言对象）
        #
        # 判据修正（2026-10-30）：原实现用裸正则 ^\s*(\d{1,3})\s*[.．、] 取题号，
        # 解析文本里 "0.5倍""10.5%""352.…" 落在行首时会被误判为题号，把该节
        # min/max 拉偏（85 套仅 4 套区间全等；脚本自身统计的「伪题号」即此来源）。
        # 现改为：
        #   1) 上界取**题目块题号**的最大值（生产解析器结果），超出即视为伪题号；
        #   2) 排除 0；排除 "10.5" 这类小数（句点后紧跟数字）；
        #   3) 句点与顿号分别匹配，避免把 "106、" 当小数。
        def intervals(text, secs, blocks, anchors=None):
            block_nums = qnums_of(blocks)
            hi = max(block_nums) if block_nums else 0
            out = []
            for name, s, e in secs:
                seg = text[s:e]
                nums = []
                # 1. 顿号/全角点结尾："1、" "1．"
                nums += [int(m.group(1)) for m in
                         re.finditer(r"(?m)^\s*(\d{1,3})\s*[．、]", seg)]
                # 2. ASCII 句点结尾，且后面不接数字（排除 "10.5"）
                nums += [int(m.group(1)) for m in
                         re.finditer(r"(?m)^\s*(\d{1,3})\.(?!\d)", seg)]
                nums = [n for n in nums if n > 0 and (hi == 0 or n <= hi)]
                if anchors is not None:
                    # 解析侧：只认有【答案】锚点的编号，挡掉图形/小标题编号（2. 6. …）
                    nums = [n for n in nums if n in anchors]
                out.append((name, min(nums) if nums else None,
                            max(nums) if nums else None, len(nums)))
            return out

        qi = intervals(qb_text, qsec, qb_blocks)
        ai = intervals(an_text, asec, an_blocks, an_anchor)
        seq_ok = [x[0] for x in qi] == [x[0] for x in ai]
        rng_ok = [(x[0], x[1], x[2]) for x in qi] == [(x[0], x[1], x[2]) for x in ai]

        rng_payload = {'qb': [[x[0], x[1], x[2]] for x in qi],
                       'ans': [[x[0], x[1], x[2]] for x in ai]}
        if not rng_ok:
            mismatch_records[key] = {
                'sig': _sig(rng_payload),
                'note': '分节题号区间题本端与解析端不等（伪题号/图形编号所致）',
                'qb': rng_payload['qb'],
                'ans': rng_payload['ans'],
            }

        # 伪题号：超出 1..max(qn) 的块
        hi = max(qn) if qn else 0
        bogus = [n for n in qnums_of(an_blocks) if n > hi]

        w("%-3d %-30s %-4s %5d %5d %-9s %6d %8d %6d %6d %s\n" % (
            idx, key[-30:], "QB", len(qb_blocks), len(qn),
            "%d..%d" % (min(qn), hi) if qn else "-",
            len(qsec), len(an_anchor), len(kao), len(mat),
            ("seq=" + ("OK" if seq_ok else "DIFF")) + " rng=" + ("OK" if rng_ok else "DIFF")))

        w("%-3s %-30s %-4s %5d %5d %-9s %6s %8s %6s %6s %s\n" % (
            "", "", "ANS", len(an_blocks), len(an_anchor), "-",
            len(asec), "-", "-", "-",
            "bogus_qnum=%s" % (sorted(set(bogus)) if bogus else "-")))

        tot['pairs'] += 1
        tot['qb_blocks'] += len(qb_blocks)
        tot['an_blocks'] += len(an_blocks)
        tot['qb_sec'] += len(qsec)
        tot['an_sec'] += len(asec)
        tot['answer_anchor'] += len(an_anchor)
        tot['kao'] += len(kao)
        tot['material'] += len(mat)
        tot['bogus'] += len(bogus)
        tot['qb_with_options'] += sum(1 for b in qb_blocks if b.get('options'))
        tot['an_with_options'] += sum(1 for b in an_blocks if b.get('options'))
        tot['seq_mismatch'] += 0 if seq_ok else 1
        if not rng_ok:
            tot['rng_raw_mismatch'] += 1
            entry = known.get(key)
            if entry and entry.get('sig') == mismatch_records[key]['sig']:
                tot['rng_known'] += 1
            elif entry:
                tot['rng_new'] += 1
                drift_keys.append(key)
            else:
                tot['rng_new'] += 1
                new_keys.append(key)
        tot['qb_no_sec'] += 0 if qsec else 1
        tot['an_no_anchor'] += 0 if an_anchor else 1
        for b in qb_blocks:
            tot['type:' + str(b.get('question_type'))] += 1
            tot['opt:%d' % len(b.get('options') or [])] += 1
        per_pair[key] = {
            'qb_blocks': len(qb_blocks), 'an_blocks': len(an_blocks),
            'qb_sec': len(qsec), 'an_sec': len(asec),
            'answer_anchor': len(an_anchor), 'kao': len(kao),
            'material': len(mat), 'bogus': sorted(set(bogus)),
            'seq_ok': seq_ok, 'rng_ok': rng_ok,
        }

    w("-" * 132 + "\n")
    w("汇总（成功解析 %d 套）\n" % tot['pairs'])
    w("  题本块总数            : %d\n" % tot['qb_blocks'])
    w("  答案解析块总数        : %d\n" % tot['an_blocks'])
    w("  题本缺分节头文件数    : %d   %s\n" % (
        tot['qb_no_sec'], 'PASS 目标为 0' if tot['qb_no_sec'] == 0 else 'FAIL'))
    w("  解析缺答案锚点文件数  : %d   %s\n" % (
        tot['an_no_anchor'], 'PASS 目标为 0' if tot['an_no_anchor'] == 0 else 'FAIL'))
    w("  分节头序列全等套数    : %d / %d\n" % (
        tot['pairs'] - tot['seq_mismatch'], tot['pairs']))
    w("  分节题号区间全等套数  : %d / %d\n" % (
        tot['pairs'] - tot['rng_raw_mismatch'], tot['pairs']))
    w("  已知伪题号不一致(白名单): %d 套   基线 %s\n" % (
        tot['rng_known'],
        os.path.basename(mismatch_baseline) if known else "（无白名单文件）"))
    w("  **新增不一致**        : %d 套   %s\n" % (
        tot['rng_new'], 'PASS 目标为 0' if tot['rng_new'] == 0 else 'FAIL'))
    if new_keys:
        w("  新增不一致套          : %s\n" % (new_keys[:20]))
    if drift_keys:
        w("  签名漂移套（已知套但数值变了）: %s\n" % (drift_keys[:20]))
    w("  分节头命中(题本/解析) : %d / %d\n" % (tot['qb_sec'], tot['an_sec']))
    w("  答案锚点总数          : %d\n" % tot['answer_anchor'])
    w("  【考点】总数: %d\n" % tot['kao'])
    w("  资料分析材料块总数    : %d\n" % tot['material'])
    w("  题本含选项块数: %d / %d\n" % (tot['qb_with_options'], tot['qb_blocks']))
    w("  **伪题号总数**        : %d   （行测特有：解析中「小数+单位」落在行首）\n" % tot['bogus'])
    w("  题型分布              : %s\n" % {
        k[5:]: v for k, v in tot.items() if k.startswith('type:')})
    w("  选项数分布            : %s\n" % {
        k[4:]: v for k, v in tot.items() if k.startswith('opt:')})
    if bad_pairs:
        w("  异常套                : %s\n" % bad_pairs)

    ok = (tot['qb_no_sec'] == 0 and tot['an_no_anchor'] == 0
          and tot['rng_new'] == 0 and tot['pairs'] > 0)
    w("=" * 132 + "\n")
    w("验收结论: %s    （新增不一致 %d 套；已知白名单 %d 套）\n" % (
        'PASS' if ok else 'FAIL', tot['rng_new'], tot['rng_known']))
    f.close()

    # 逐套摘要（供 --compare 精确 diff）
    with io.open(out_path + ".pairs.json", "w", encoding="utf-8") as fh:
        json.dump(per_pair, fh, ensure_ascii=False, indent=1, sort_keys=True)

    # gate_l2 在失败时只摊开 stdout/stderr 尾部，这里必须把判定依据打到 stdout
    print("分节区间全等 %d/%d | 已知伪题号 %d | 新增不一致 %d"
          % (tot['pairs'] - tot['rng_raw_mismatch'], tot['pairs'],
             tot['rng_known'], tot['rng_new']))
    if new_keys:
        print("新增不一致套: %s" % new_keys[:20])
    if drift_keys:
        print("签名漂移套: %s" % drift_keys[:20])
    print("报告: %s" % out_path)

    if write_mismatch:
        write_mismatch_baseline(mismatch_baseline, mismatch_records)
        print("已刷新白名单（本轮不做判定，退出码 0）")
        return 0
    return 0 if ok else 1


def compare(baseline_path: str, current_path: str) -> int:
    """逐项 diff。任一项不一致 → 退出码 1。"""
    import json
    bp = baseline_path + ".pairs.json"
    cp = current_path + ".pairs.json"
    if not (os.path.exists(bp) and os.path.exists(cp)):
        print("[compare] 缺少 .pairs.json，请先分别运行两次 scan")
        return 2
    with io.open(bp, encoding="utf-8") as fh:
        base = json.load(fh)
    with io.open(cp, encoding="utf-8") as fh:
        cur = json.load(fh)

    fields = ("qb_blocks", "an_blocks", "qb_sec", "an_sec", "answer_anchor",
              "kao", "material", "bogus", "seq_ok", "rng_ok")
    diffs = []
    for key in sorted(set(base) | set(cur)):
        if key not in base:
            diffs.append("  + 新增套 %s" % key)
            continue
        if key not in cur:
            diffs.append("  - 消失套 %s" % key)
            continue
        for f in fields:
            if base[key].get(f) != cur[key].get(f):
                diffs.append("  ~ %s  %s: %r -> %r" % (
                    key, f, base[key].get(f), cur[key].get(f)))
    if diffs:
        print("[compare] 检测到 %d 处差异：" % len(diffs))
        for d in diffs[:80]:
            print(d)
        if len(diffs) > 80:
            print("  ... 其余 %d 处省略" % (len(diffs) - 80))
        return 1
    print("[compare] 无差异，与基线完全一致")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="行测解析器回归门禁 G2")
    ap.add_argument("root", nargs="?", default=None)
    ap.add_argument("--out", default=os.path.join(BACKEND_DIR, "data", "xingce_regression.txt"))
    ap.add_argument("--compare", default=None, help="与该基线逐项 diff")
    ap.add_argument("--reparse", action="store_true", help="强制重跑解析")
    ap.add_argument("--cache-dir", default="", help="PDF 文本提取缓存目录")
    ap.add_argument("--current", default=None, help="配合 --compare：当前报告路径")
    ap.add_argument("--mismatch-baseline", default=DEFAULT_MISMATCH_BASELINE,
                    help="已知伪题号不一致白名单 JSON")
    ap.add_argument("--write-mismatch-baseline", nargs="?", const=DEFAULT_MISMATCH_BASELINE,
                    default=None, help="把当前不一致写入白名单（可省路径）")
    a = ap.parse_args()
    if a.compare:
        cur = a.current or a.out
        raise SystemExit(compare(a.compare, cur))
    if not a.root:
        ap.error("需要行测目录，或使用 --compare")
    raise SystemExit(scan(a.root, a.out, a.cache_dir, a.reparse,
                          mismatch_baseline=a.write_mismatch_baseline or a.mismatch_baseline,
                          write_mismatch=bool(a.write_mismatch_baseline)))