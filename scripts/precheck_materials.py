# -*- coding: utf-8 -*-
"""备考资料上传前预检器（T0.3）

用途：
    在管理员上传**之前**，把一批本地文件按《资料内容格式与分类规范 v2》跑一遍，
    输出「阻断（block）/ 提示（warn）」清单，避免"传完才发现格式不对"。

规则来源：docs/plans/资料内容格式与分类规范_v2.md §2/§3/§4/§6
    E001 缺必需列 / E002 必填空 / E003 超长 / E004 行数超上限 / E005 文件内重复行
    E006 分类不在词表 / E007 考点不在词表 / E008 危险标签 / E009 扩展名不支持 / E010 超体积
    W101 跳过非卡片 sheet / W102 已自动分批 / W201 无 Heading / W202 段落超长
    W203 表格超列 / W204 图片超限 / W205 法条引用格式 / W206 章节不可切分 / W207 页数超限
    W208 混合型 PDF（部分页无文字层）

用法：
    python scripts/precheck_materials.py "C:\\...\\备考资料" \
        --md docs/plans/资料_素材体检报告_v1.md \
        --csv docs/plans/资料_素材体检报告_v1.csv

退出码：0 = 全部无阻断；1 = 存在阻断项（可用于 CI/门禁）。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sqlite3
import sys
from collections import Counter, OrderedDict

sys.stdout.reconfigure(encoding="utf-8")

CARD_HEADER_ALIAS = OrderedDict([
    ("front", ("正面", "front", "问题", "题目", "问")),
    ("back", ("背面", "back", "答案", "解析", "答")),
    ("category", ("分类", "子类", "category")),
    ("point", ("考点", "知识点", "point")),
    ("cover", ("封面", "配图", "cover")),
])
FRONT_MAX, BACK_MAX = 120, 600
ROW_WARN, ROW_BLOCK = 500, 2000
PAGE_WARN, PAGE_BLOCK = 300, 1024
TEXT_PAGE_MIN = 50          # 单页文字少于此值视为"无文字层"
MAX_IMG, IMG_MB = 20, 2.0
TABLE_COLS_MAX = 8
DANGEROUS = re.compile(r"<\s*(script|iframe|object|embed)\b|on\w+\s*=", re.I)
LAW_WITH_ARTICLE = re.compile(r"《[^》]{2,40}》\s*第[一二三四五六七八九十百零〇\d]+条")
LAW_ANY = re.compile(r"《[^》]{2,40}》")
CHAPTER = re.compile(r"^\s*(第[一二三四五六七八九十百零〇\d]+[章节讲部分]|[一二三四五六七八九十]+、|\d+[.、]\s*\S)")

SUBJECTS = ("行测", "申论", "公专")


def load_vocab(db_path: str):
    """从库里取子类/考点词表（只读）。失败返回空集合，不阻断预检。"""
    subs, points = set(), set()
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        subs = {r[0] for r in con.execute("select name from sub_categories") if r[0]}
        points = {r[0] for r in con.execute("select point_name from knowledge_point") if r[0]}
        con.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 词表加载失败（{exc}），E006/E007 将跳过", file=sys.stderr)
    return subs, points


def issue(code: str, level: str, msg: str) -> dict:
    return {"code": code, "level": level, "msg": msg}


def resolve_header(headers):
    idx = {}
    lowered = [str(h or "").strip() for h in headers]
    for key, aliases in CARD_HEADER_ALIAS.items():
        for i, h in enumerate(lowered):
            if h in aliases:
                idx[key] = i
                break
    return idx


def check_xlsx(path: str, subs, points):
    from openpyxl import load_workbook

    out = []
    size_mb = os.path.getsize(path) / 1e6
    if size_mb > 10:
        out.append(issue("E010", "block", f"文件 {size_mb:.1f} MB 超过卡片 10 MB 上限"))

    wb = load_workbook(path, read_only=True, data_only=True)
    card_sheets, other_sheets = [], []
    total_rows = 0
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            other_sheets.append(ws.title)
            continue
        header = [("" if v is None else str(v).strip()) for v in rows[0]]
        idx = resolve_header(header)
        if "front" in idx and "back" in idx:
            card_sheets.append((ws.title, header, idx, rows[1:]))
        else:
            other_sheets.append(ws.title)
    wb.close()

    if other_sheets:
        out.append(issue("W101", "warn", "已跳过非卡片 sheet：" + "、".join(other_sheets[:5])))
    if not card_sheets:
        out.append(issue("E001", "block", "没有任何 sheet 同时含「正面」与「背面」列"))
        return out, 0

    missing_alias = []
    for sheet, header, idx, rows in card_sheets:
        if "category" not in idx:
            missing_alias.append(f"{sheet}:分类列")
        if "point" not in idx:
            missing_alias.append(f"{sheet}:考点列")
        data = [r for r in rows if r and any((v is not None and str(v).strip()) for v in r)]
        total_rows += len(data)
        if len(data) > ROW_WARN:
            out.append(issue("W102", "warn", f"{sheet} 共 {len(data)} 行 > {ROW_WARN}，将自动分批"))
        # 逐行校验（只统计前 5 个样例，避免报告爆炸）
        e2 = e3 = e6 = e7 = e8 = 0
        seen = set()
        e5 = 0
        for r in data:
            def cell(k):
                i = idx.get(k)
                return "" if i is None or i >= len(r) or r[i] is None else str(r[i]).strip()

            front, back = cell("front"), cell("back")
            cat, pt = cell("category"), cell("point")
            if not front or not back:
                e2 += 1
            if len(front) > FRONT_MAX or len(back) > BACK_MAX:
                e3 += 1
            if cat and subs and cat not in subs:
                e6 += 1
            if pt and points and pt not in points:
                e7 += 1
            if DANGEROUS.search(front + back):
                e8 += 1
            key = (front, back)
            if key in seen:
                e5 += 1
            seen.add(key)
        for code, n, label, level in (("E002", e2, "必填单元格为空", "block"),
                                      ("E003", e3, "正面>120 或 背面>600 字", "warn"),
                                      ("E005", e5, "文件内重复行", "warn"),
                                      ("E006", e6, "分类不在子类词表", "warn"),
                                      ("E007", e7, "考点不在考点表", "warn"),
                                      ("E008", e8, "含危险标签", "block")):
            if n:
                out.append(issue(code, level, f"{sheet}: {label} × {n}"))
    if total_rows > ROW_BLOCK:
        out.append(issue("E004", "block", f"总行数 {total_rows} 超过 {ROW_BLOCK}，请拆分文件"))
    if missing_alias:
        out.append(issue("W103", "warn", "缺少可选列（不影响导入）：" + "、".join(missing_alias[:5])))
    return out, total_rows


def check_docx(path: str):
    import docx
    from docx.table import Table

    out = []
    size_mb = os.path.getsize(path) / 1e6
    if size_mb > 50:
        out.append(issue("E010", "block", f"文件 {size_mb:.1f} MB 超过讲义 50 MB 上限"))
    doc = docx.Document(path)
    headings, long_paras = 0, 0
    law_bad = 0
    for p in doc.paragraphs:
        style = (p.style.name or "") if p.style is not None else ""
        if style.lower().startswith(("heading", "标题")):
            headings += 1
        text = (p.text or "").strip()
        if len(text) > 500:
            long_paras += 1
        if LAW_ANY.search(text) and not LAW_WITH_ARTICLE.search(text):
            law_bad += 1
    if headings == 0:
        n_para = len([x for x in doc.paragraphs if (x.text or "").strip()])
        level = "warn" if n_para <= 50 else "warn"
        out.append(issue("W201", level,
                         f"未检测到 Heading 1/2/3 标题样式（正文段落 {n_para} 段），章节将按兜底规则切分"))
    if long_paras:
        out.append(issue("W202", "warn", f"超长段落（>500 字）× {long_paras}"))
    wide = [t for t in doc.tables if t.columns and len(t.columns) > TABLE_COLS_MAX]
    if wide:
        out.append(issue("W203", "warn", f"表格列数 >{TABLE_COLS_MAX} 的共 {len(wide)} 个"))
    imgs = [r for r in doc.part.rels.values() if "image" in r.reltype]
    big = sum(1 for r in imgs if len(r.target_part.blob) > IMG_MB * 1024 * 1024)
    if len(imgs) > MAX_IMG:
        out.append(issue("W204", "warn", f"内嵌图片 {len(imgs)} 张 > {MAX_IMG}"))
    if big:
        out.append(issue("W204", "warn", f"单张图片 >{IMG_MB:.0f} MB 的共 {big} 张"))
    if law_bad:
        out.append(issue("W205", "warn", f"法条引用缺条号 × {law_bad}（应写《法》第X条）"))
    return out, headings


def check_pdf(path: str):
    import pymupdf as fitz

    out = []
    size_mb = os.path.getsize(path) / 1e6
    limit = 250 if size_mb > 50 else 250
    if size_mb > limit:
        out.append(issue("E010", "block", f"文件 {size_mb:.1f} MB 超过 {limit} MB 上限"))
    doc = fitz.open(path)
    pages = doc.page_count
    empty_pages = text_pages = chapters = 0
    head_samples = []
    for i in range(min(pages, 60)):     # 采样前 60 页判定与切章
        t = doc[i].get_text().strip()
        if len(t) < TEXT_PAGE_MIN:
            empty_pages += 1
        else:
            text_pages += 1
            for line in t.splitlines()[:6]:
                if CHAPTER.match(line):
                    chapters += 1
                    if len(head_samples) < 3:
                        head_samples.append(line.strip()[:24])
                    break
    doc.close()
    sampled = min(pages, 60)
    scanned = sampled and empty_pages == sampled
    if scanned:
        out.append(issue("INFO", "info", f"全文无文字层（扫描件），将走 OCR 通道；共 {pages} 页"))
    elif empty_pages and text_pages:
        out.append(issue("W208", "warn", f"混合型：采样 {sampled} 页中 {empty_pages} 页无文字层"))
    brief = any(k in os.path.basename(path) for k in ("总图", "清单", "速查", "口诀"))
    if chapters == 0 and not scanned:
        if pages <= 3 or brief:
            out.append(issue("INFO", "info", f"{pages} 页的单页/速查类，不要求章节结构"))
        else:
            out.append(issue("W206", "warn", f"采样 {sampled} 页未识别到章节标题（第X章/一、/1.）"))
    if pages > PAGE_WARN:
        out.append(issue("W207", "warn", f"共 {pages} 页 > {PAGE_WARN}，建议拆分"))
    if pages > PAGE_BLOCK:
        out.append(issue("E011", "block", f"共 {pages} 页 > {PAGE_BLOCK}，必须拆分"))
    return out, {"pages": pages, "chapters": chapters, "scanned": scanned, "head": head_samples}


def subject_of(name: str):
    for s in SUBJECTS:
        if s in name:
            return s
    return "未标注"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--md", default="")
    ap.add_argument("--csv", default="")
    ap.add_argument("--db", default=os.path.join("backend", "data", "question_bank.db"))
    ap.add_argument("--include-nonprod", action="store_true",
                    help="连同 _模板/_测试文件 一起检（默认跳过：它们不是待导入素材）")
    args = ap.parse_args()

    subs, points = load_vocab(args.db) if os.path.exists(args.db) else (set(), set())
    if not subs:
        print("[warn] 未加载到子类词表，E006 跳过", file=sys.stderr)

    files = []
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if not args.include_nonprod:
            dirnames[:] = [d for d in dirnames if d not in ("_模板", "_测试文件")]
        for f in filenames:
            if f.lower().endswith((".xlsx", ".docx", ".pdf")):
                files.append(os.path.join(dirpath, f))
    files.sort()

    rows, blocked = [], 0
    for p in files:
        rel = os.path.relpath(p, args.root)
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == ".xlsx":
                issues, extra = check_xlsx(p, subs, points)
                detail = f"行数 {extra}"
            elif ext == ".docx":
                issues, extra = check_docx(p)
                detail = f"Heading {extra}"
            else:
                issues, extra = check_pdf(p)
                detail = f"{extra['pages']} 页 / 章 {extra['chapters']}" + ("（扫描）" if extra["scanned"] else "")
        except Exception as exc:  # noqa: BLE001
            issues = [issue("E000", "block", f"预检异常：{type(exc).__name__}: {exc}")]
            detail = "-"
        b = sum(1 for i in issues if i["level"] == "block")
        w = sum(1 for i in issues if i["level"] == "warn")
        blocked += 1 if b else 0
        rows.append({"file": rel, "subject": subject_of(rel), "ext": ext, "size_mb": round(os.path.getsize(p) / 1e6, 2),
                     "detail": detail, "block": b, "warn": w, "issues": issues})

    # 输出
    total = len(rows)
    sum_block = sum(r["block"] for r in rows)
    sum_warn = sum(r["warn"] for r in rows)
    by_ext = Counter(r["ext"] for r in rows)
    lines = ["# 素材体检报告（预检器输出）\n",
             f"> 生成命令：`python scripts/precheck_materials.py \"{args.root}\"`",
             f"> 规则：`docs/plans/资料内容格式与分类规范_v2.md`\n",
             "## 汇总\n",
             "| 指标 | 值 |", "|---|---|",
             f"| 文件总数 | {total} |",
             "| 按类型 | " + "、".join(f"{k} {v}" for k, v in by_ext.items()) + " |",
             f"| 含阻断项文件 | **{blocked}** |",
             f"| 阻断项合计 | {sum_block} |",
             f"| 提示项合计 | {sum_warn} |",
             "\n## 明细\n",
             "| 文件 | 科目 | 类型 | 大小 MB | 概况 | 阻断 | 提示 | 问题 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        msg = "；".join(f'{i["code"]} {i["msg"]}' for i in r["issues"])[:180] or "—"
        lines.append(f'| {r["file"]} | {r["subject"]} | {r["ext"][1:]} | {r["size_mb"]} | {r["detail"]} | {r["block"]} | {r["warn"]} | {msg} |')

    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
        with open(args.md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[ok] 报告已写入 {args.md}")
    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "subject", "ext", "size_mb", "detail", "block", "warn", "issues"])
            for r in rows:
                w.writerow([r["file"], r["subject"], r["ext"], r["size_mb"], r["detail"], r["block"], r["warn"],
                            " | ".join(f'{i["code"]}:{i["msg"]}' for i in r["issues"])])
        print(f"[ok] CSV 已写入 {args.csv}")

    print(f"\n合计 {total} 个文件：阻断 {sum_block} 项（{blocked} 个文件）、提示 {sum_warn} 项")
    top = Counter(i["code"] for r in rows for i in r["issues"])
    for code, n in top.most_common(10):
        print(f"  {code}: {n}")
    return 1 if sum_block else 0


if __name__ == "__main__":
    raise SystemExit(main())
