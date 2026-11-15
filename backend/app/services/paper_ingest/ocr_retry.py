# -*- coding: utf-8 -*-
"""扫描件「整行漏检」回收（T5，2026-11-14）。

真机缺陷（5 页探针 draft #6 的第 9 题）：C 行被斜向水印压住 → rapidocr **连框都不出**，
`splitter` 只看到 B→D 之间 120px 的空白，C 永远是空的。补标签（T3）修不了"行不存在"。

三步（只读原 PDF、不落盘、不新增端点/表）：

  **S1 检测**：本题缺选项字母 **且** 相邻两行间距 ≥ 1.6× 该页中位行距 → 判为"缺行"；
  **S2 重跑**：只把那段空白（上下行框外侧 ±6px）按 **300dpi 原样**重跑一次
             （`ocr_sidecar.read_region_text`；实测二值化/400dpi 反而掉字）；
  **S3 回填**：pt→px 换回版面坐标插回行序，坐标 + 文本两道去重，水印仍走几何过滤。

**T6（2026-11-15）补第二类洞**：块内出现**第二组 `A.`** → 中间那行（含题号）被漏，
此时补回来的行**必须以题号开头**才收（否则丢弃），避免把半截正文塞进去。

开关：`PAPER_OCR_RETRY=0` 关闭（默认开）。**没有洞时零额外耗时**（纯内存判断）。
"""
from __future__ import annotations

import os
import re
import time
from difflib import SequenceMatcher
from statistics import median
from typing import Dict, List, Optional, Tuple

from . import splitter

#: 关掉补行的开关（默认开）
ENV_SWITCH = "PAPER_OCR_RETRY"

#: 缺行判定：间距 ≥ 1.6× 中位行距，且比中位数至少多 20px（防稀疏页比例失真）
GAP_RATIO = 1.6
MIN_EXTRA = 20.0
#: 条带上下各往邻行方向多切 6px（正文行高 30–35px，6px 只碰到笔画出头）
PAD_PX = 6.0
#: 上限：一题一处、一页 8 处、一篇 40 处（配合预算，最坏多花 ≈60s）
MAX_PER_QUESTION = 1
MAX_PER_PAGE = 8
MAX_TOTAL = 40
#: P1-4（2026-11-15）：按"题号缺号"补回收的条带上限。41 页实测 5 组缺号 → 6 条带，
#: 每组最坏跨 3 页；上限 12 条 ≈ 最坏 +35s（实测单条带 1–3s）。
MAX_QNO_GAPS = 12
#: 重跑 dpi 与单条带超时（实测单条带 1–2s）
RETRY_DPI = 300
RETRY_TIMEOUT = 30.0
#: 整轮预算：超过就不再补，只记失败数（不让导入变慢到不可接受）
RETRY_BUDGET = 120.0
#: 去重：|Δy| < 0.5×行高 → 同一行；文本相似 ≥0.8 且 |Δy| < 1.2×行高 → 同一行
DEDUPE_Y_RATIO = 0.5
DEDUPE_Y_TEXT_RATIO = 1.2
DEDUPE_TEXT_RATIO = 0.8


def enabled() -> bool:
    """补行是否启用（`PAPER_OCR_RETRY=0/off/false/no` 关闭）。"""
    raw = (os.environ.get(ENV_SWITCH) or "1").strip().lower()
    return raw not in ("0", "off", "false", "no")


def _blocks(rows: List[dict]) -> List[Tuple[int, int, int]]:
    """按题号分块 → `(题号, 起始下标, 结束下标)`；页首无题号的续块跳过（无法归属）。"""
    starts = [i for i, r in enumerate(rows) if splitter.qno_of(r.get("text") or "")]
    out: List[Tuple[int, int, int]] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(rows)
        no = splitter.qno_of(rows[start].get("text") or "")
        if no is not None:
            out.append((int(no), start, end))
    return out


def _missing_letters(block: List[dict]) -> List[str]:
    """这一题缺哪些选项字母（用与拆题完全相同的规则算，保证口径一致）。"""
    if len(block) < 2:
        return []
    texts = [r.get("text") or "" for r in block]
    texts[0] = splitter._strip_qno(texts[0])     # 题号行上可能也带选项（`1.A.甲 B.乙`）
    _stem, options = splitter.split_options(texts)
    return [k for k in "ABCD" if not options[k]]


def _base_by_page(rows: List[dict]) -> Dict[int, float]:
    """每页的正文行高中位数（10–80px 取样，水印框 187–343px 自然被排除）。"""
    out: Dict[int, float] = {}
    for page in {r["page"] for r in rows}:
        hs = [r["h"] for r in rows if r["page"] == page and 10.0 <= r["h"] <= 80.0]
        if hs:
            out[int(page)] = sorted(hs)[len(hs) // 2]
    return out


def _option_letter(row: dict) -> Optional[str]:
    """这一行以哪个选项字母开头（A–D）；不是选项行就 None。"""
    m = splitter.OPT_RE.match((row.get("text") or "").strip())
    if not m:
        return None
    return m.group(1).translate(str.maketrans("ＡＢＣＤ", "ABCD"))


def _first_option_index(block: List[dict]) -> Optional[int]:
    """块内第一个选项行的下标。"""
    for i, r in enumerate(block):
        if _option_letter(r):
            return i
    return None


def _option_restart(block: List[dict]) -> Optional[int]:
    """块内**第二次**出现 `A.` 的下标（T6，2026-11-15）。

    为什么这能当"缺题号行"的判据：一道题的选项只会有一次 A–D；
    同一题号块里又冒出第二组 A.，说明中间那道题的**题号行**被 OCR 整行漏了，
    拆题器认不出新题，才把两道题并成一块（实测第 5 题吃掉第 6 题就是这样）。
    """
    seen_a = False
    for i, r in enumerate(block):
        if _option_letter(r) != "A":
            continue
        if seen_a:
            return i
        seen_a = True
    return None


def find_holes(rows: List[dict], *, gap_ratio: float = GAP_RATIO,
               min_extra: float = MIN_EXTRA) -> List[dict]:
    """找出「缺选项字母 + 行间距异常」的位置 → 待重跑的条带（纯内存，零 IO）。

    返回项：`{page, qno, missing, gap, median, y0, y1, x0, x1}`（像素坐标，原点同 `_layout_lines`）。
    `missing` 必须满足 1 ≤ len ≤ 3：四个全缺说明这题本来就没选项（判断题/整题漏），无法定位。
    """
    if not rows:
        return []
    by_page: Dict[int, List[dict]] = {}
    for r in rows:
        by_page.setdefault(int(r["page"]), []).append(r)
    med_page: Dict[int, float] = {}
    all_gaps: List[float] = []
    for page, group in by_page.items():
        group.sort(key=lambda r: r["y"])
        gaps = [b["y"] - a["y"] for a, b in zip(group, group[1:])]
        all_gaps.extend(gaps)
        if gaps:
            med_page[page] = median(gaps)
    med_all = median(all_gaps) if all_gaps else 0.0

    holes: List[dict] = []
    per_page: Dict[int, int] = {}
    for qno, start, end in _blocks(rows):
        if start + 1 >= end:
            continue
        block = rows[start:end]
        missing = _missing_letters(block)
        restart = _option_restart(block)
        if restart is not None:
            # T6（2026-11-15）：块里出现第二组 A. → 中间那一行（含题号）被 OCR 漏了。
            # 只在这两组 A 之间找缝：前一组 A 之前的行属于上一题，不该动。
            kind = "number"
            first_a = _first_option_index(block)
            scope = block[first_a:restart] if first_a is not None else block[:restart]
        elif 1 <= len(missing) <= 3:
            kind = "option"
            scope = block
        else:
            continue
        best: Optional[dict] = None
        for page in sorted({int(r["page"]) for r in scope}):
            group = sorted((r for r in scope if int(r["page"]) == page),
                           key=lambda r: r["y"])
            med = med_page.get(page) or med_all
            if not med or len(group) < 2:
                continue
            for a, b in zip(group, group[1:]):
                gap = b["y"] - a["y"]
                if gap < gap_ratio * med or (gap - med) < min_extra:
                    continue
                if best is None or gap > best["gap"]:
                    best = {"page": page, "qno": qno, "missing": missing, "kind": kind,
                            "gap": gap, "median": med, "prev": a, "next": b}
        if best is None:
            continue
        page = int(best["page"])
        if per_page.get(page, 0) >= MAX_PER_PAGE or len(holes) >= MAX_TOTAL:
            continue
        a, b = best["prev"], best["next"]
        y0 = float(a["y"]) + float(a["h"]) / 2.0 - PAD_PX
        y1 = float(b["y"]) - float(b["h"]) / 2.0 + PAD_PX
        if y1 - y0 < 6.0:                       # 空白带太窄，重跑也没东西
            continue
        # 条带按「整幅文字宽度」切：只按本题的行宽算，可能把缺行的后半截切掉
        # （实测缺行比同题其它行更长）；高度仍是那条缝，成本可以忽略。
        x0 = 0.0
        x1 = max(float(r["x"]) + float(r["w"]) for r in by_page[page]) + PAD_PX
        per_page[page] = per_page.get(page, 0) + 1
        holes.append({"page": page, "qno": qno, "missing": missing, "kind": kind,
                      "gap": round(float(best["gap"]), 1),
                      "median": round(float(best["median"]), 1),
                      "y0": y0, "y1": y1, "x0": x0, "x1": x1})
    return holes


def _consecutive_groups(nums: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    for n in nums:
        if out and n == out[-1][-1] + 1:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def find_number_holes(rows: List[dict], starts: List[Tuple[int, int]],
                      *, max_total: int = MAX_QNO_GAPS) -> List[dict]:
    """按「题号缺号」找待重跑的条带（P1-4，2026-11-15）。纯内存，零 IO。

    为什么要单开一条：T5/T6 的洞检测盯的是**缺选项字母**，而 41 页整卷里 27/45/47/87
    这些题是**题号行整行没被 OCR 出框**（题还是有的，题干接着上一行往下走）。
    实测：对这些缺口做 300dpi 条带重跑，47、87 能逐字捞回、
    27/45 能捞回「27在…」「45东江市…」这种**无分隔符题号**行。

    条带取「上一题最后一行」到「下一题第一行」之间：同页一条；跨页则页尾 + 中间整页 + 页首。
    """
    if not rows or len(starts) < 2:
        return []
    nos = [no for _, no in starts]
    seen = set(nos)
    idx_by_no = {no: i for i, no in starts}
    missing = [n for n in range(1, max(nos) + 1) if n not in seen]
    if not missing:
        return []
    bottom = max(float(r["y"]) + float(r["h"]) for r in rows)
    width = max(float(r["x"]) + float(r.get("w") or 0.0) for r in rows) + PAD_PX

    holes: List[dict] = []
    for grp in _consecutive_groups(missing):
        prev_no, next_no = grp[0] - 1, grp[-1] + 1
        if prev_no not in idx_by_no or next_no not in idx_by_no:
            continue
        a = rows[idx_by_no[prev_no]]
        b = rows[idx_by_no[next_no]]
        p0, p1 = int(a["page"]), int(b["page"])
        base = {"qno": grp[0], "missing_nos": list(grp), "kind": "qno_missing",
                "median": 0.0, "gap": 0.0, "x0": 0.0, "x1": width}
        y_after_a = float(a["y"]) + float(a["h"]) / 2.0 + PAD_PX
        y_before_b = float(b["y"]) - float(b["h"]) / 2.0 - PAD_PX
        if p0 == p1:
            holes.append({**base, "page": p0, "y0": y_after_a, "y1": y_before_b})
        else:
            holes.append({**base, "page": p0, "y0": y_after_a, "y1": bottom})
            for mid in range(p0 + 1, p1):
                holes.append({**base, "page": mid, "y0": 0.0, "y1": bottom})
            holes.append({**base, "page": p1, "y0": 0.0, "y1": y_before_b})
        if len(holes) >= max_total:
            break
    return holes[:max_total]


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def merge(rows: List[dict], recovered: List[dict], *, base_h: float = 0.0) -> List[dict]:
    """把回收行**原位插入**行序，并挡掉重复（同一条带重跑常会多吐半截邻行，实测见过）。

    两道去重：①`|Δy| < 0.5×行高` 视为同一行；②文本相似 ≥0.8 且 `|Δy| < 1.2×行高` 也视为同一行。
    为什么不整篇重排：OCR 的行序是"按 y 分桶再从左到右"，桶内本来就可能微乱；
    整篇按精确 y 重排会顺带改掉上百行的相对顺序（实测 41 页有 100+ 处顺序变动），
    而补行只需要**往缝里插一行**——所以按 (page, y) 找到插入点插进去，其余行序一律不动。
    """
    out = list(rows)
    added = 0
    for rec in sorted(recovered, key=lambda r: (int(r["page"]), float(r["y"]), float(r["x"]))):
        page = int(rec["page"])
        dup = False
        for r in out:
            if int(r["page"]) != page:
                continue
            dy = abs(float(r["y"]) - float(rec["y"]))
            if base_h and dy < DEDUPE_Y_RATIO * base_h:
                dup = True
                break
            if base_h and dy < DEDUPE_Y_TEXT_RATIO * base_h \
                    and _similar(r.get("text") or "", rec.get("text") or "") >= DEDUPE_TEXT_RATIO:
                dup = True
                break
        if dup:
            continue
        pos = len(out)
        for i, r in enumerate(out):
            if (int(r["page"]), float(r["y"])) > (page, float(rec["y"])):
                pos = i
                break
        out.insert(pos, rec)
        added += 1
    return out


def recover_into(path: str, rows: List[dict], *, layout_dpi: int = 200,
                 progress=None, holes: Optional[List[dict]] = None) -> Tuple[List[dict], dict]:
    """检测缺行 → 逐条带重跑 → 回填。返回 `(新行序, 统计)`；任何异常都只记失败、不抛出。

    :param holes: 指定要重跑的条带（P1-4 的题号缺号走这条路径）；不传就按 T5/T6 的
        「缺选项字母 + 行距异常」自己找。
    """
    stats: dict = {"holes": 0, "recovered": 0, "rows": 0, "failed": 0, "rejected": 0,
                   "qnos": [], "recovered_qnos": [], "seconds": 0.0, "skipped": ""}
    if not rows:
        return rows, stats
    if not enabled():
        stats["skipped"] = f"{ENV_SWITCH}=0"
        return rows, stats
    holes = list(holes) if holes is not None else find_holes(rows)
    stats["holes"] = len(holes)
    stats["qnos"] = [h["qno"] for h in holes]
    if not holes:
        return rows, stats
    if not path or not os.path.isfile(path):
        stats["skipped"] = "原件路径不可用"
        return rows, stats

    from .. import ocr_sidecar                   # 延迟导入：单测可整块替身，也不扩大导入面

    ok, why = ocr_sidecar.available()
    if not ok:
        stats["skipped"] = why
        return rows, stats

    from .readers import is_watermark_row        # 延迟导入：避开 readers ↔ ocr_retry 的环

    k = float(layout_dpi or 200) / 72.0          # pt → px（回收行换回版面坐标用）
    k_pt = 72.0 / float(layout_dpi or 200)       # px → pt（发请求给 worker 用）
    base_by_page = _base_by_page(rows)
    base_all = median(list(base_by_page.values())) if base_by_page else 0.0
    t0 = time.monotonic()
    recovered: List[dict] = []
    for i, hole in enumerate(holes, 1):
        if time.monotonic() - t0 > RETRY_BUDGET:
            stats["failed"] += 1
            stats["skipped"] = "超过补行预算"
            break
        if progress:
            try:
                progress(f"补行 {i}/{len(holes)}（第 {hole['qno']} 题）")
            except Exception:                    # noqa: BLE001 — 进度回调不能影响解析
                pass
        rect = [hole["x0"] * k_pt, hole["y0"] * k_pt,
                hole["x1"] * k_pt, hole["y1"] * k_pt]
        try:
            lines = ocr_sidecar.read_region_text(
                path, page=int(hole["page"]), rect=rect,
                dpi=RETRY_DPI, timeout=RETRY_TIMEOUT)
        except ocr_sidecar.OcrTimeout:
            stats["failed"] += 1
            stats["skipped"] = "条带重跑超时"
            break                                # 常驻进程已回收，继续等只会更慢
        except ocr_sidecar.OcrError as exc:
            stats["failed"] += 1
            stats["error"] = str(exc)[:200]      # 留一句原因，排障不用去翻日志
            continue
        base = base_by_page.get(int(hole["page"])) or base_all
        got = 0
        for ln in lines:
            text = (ln.get("text") or "").strip()
            if not text:
                continue
            # T6：题号行的洞只收「以题号开头」的行 —— 同一条缝里可能夹页眉/图表碎片。
            kind = hole.get("kind")
            if kind == "number" and splitter.qno_of(text) is None:
                stats["rejected"] += 1
                continue
            # P1-4：缺号条带还认「27在…」这种**无分隔符题号**，但必须是本组缺号里的那一个
            if kind == "qno_missing":
                got_no = splitter.qno_of(text)
                if got_no is None:
                    got_no = splitter.qno_of_loose(text)
                if got_no is None or got_no not in (hole.get("missing_nos") or [hole["qno"]]):
                    stats["rejected"] += 1
                    continue
            rec = {"text": text,
                   "x": float(ln.get("x") or 0.0) * k,
                   "y": float(ln.get("y") or 0.0) * k,
                   "w": float(ln.get("w") or 0.0) * k,
                   "h": float(ln.get("h") or 0.0) * k,
                   "score": float(ln.get("score") or 1.0),
                   "page": int(hole["page"])}
            if is_watermark_row(rec, base):
                continue
            recovered.append(rec)
            got += 1
        if got:
            stats["recovered"] += 1
            stats["recovered_qnos"].append(hole["qno"])
    stats["seconds"] = round(time.monotonic() - t0, 1)
    if not recovered:
        return rows, stats
    merged = merge(rows, recovered, base_h=base_all)
    added = len(merged) - len(rows)
    stats["rows"] = added
    if not added:                                # 全部被去重挡掉 = 实际没补回
        stats["recovered"] = 0
        stats["recovered_qnos"] = []
    return merged, stats
