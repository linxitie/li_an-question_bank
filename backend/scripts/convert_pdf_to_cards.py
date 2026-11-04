# -*- coding: utf-8 -*-
"""PDF → 卡片 Excel 转换器（带质量闸门）v2

背景：v1 用「≤30 字且无句末标点 = 正面」的机械规则，把公式碎片、页码、纯数字
（如 `631`、`1000 ្ម0.192`、`D.29`）当成了卡片正面，产出大量无法阅读的卡。

v2 增加闸门：
  1) 字符集：剔除私有区字形（\\uE000-\\uF8FF）与替换符 \\uFFFD 所在段落；
  2) 正面：4–24 字，中文字符占比 ≥60%，且不得是「纯数字/纯符号/公式片段」；
  3) 背面：≥40 字，中文字符占比 ≥50%；
  4) 去重：同一正面只保留第一条。

用法：
    python scripts/convert_pdf_to_cards.py --src <PDF目录> --out <输出目录> [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

PRIVATE = re.compile(r"[\uE000-\uF8FF\uFFFD]")
CJK = re.compile(r"[\u4e00-\u9fff]")
PURE_NUM = re.compile(r"^[\d\s\.\,%％/:\-+×÷=<>≤≥()（）\[\]【】]+$")
HEAD_END = re.compile(r"[。！？；]$")

# (相对路径, 科目, 分类, 输出名)
TARGETS = [
    (r"行测\逻辑填空选择技巧.pdf", "行测", "言语理解与表达", "行测逻辑填空技巧"),
    (r"行测\资料分析速算技巧.pdf", "行测", "资料分析", "行测速算技巧"),
    (r"行测\语句排序题选择技巧.pdf", "行测", "言语理解与表达", "行测语句排序技巧"),
    (r"行测\定义判断重要技巧梳理.pdf", "行测", "判断推理", "行测定义判断技巧"),
    (r"行测\巧辨言语实词.pdf", "行测", "言语理解与表达", "行测巧辨实词"),
    (r"行测\间隔增长率的创新变形与预测.pdf", "行测", "资料分析", "行测间隔增长率"),
    (r"行测\100条中国历史文化常识.pdf", "行测", "常识判断", "行测历史文化常识100条"),
    (r"公专\公基必背考点（法律）.pdf", "公专", "基础知识", "公专必背考点_法律"),
    (r"公专\公基必背考点（非法律）.pdf", "公专", "基础知识", "公专必背考点_非法律"),
    (r"公专\公安必背考点.pdf", "公专", "基础知识", "公专公安必背考点"),
    (r"申论\2025申论必背素材.pdf", "申论", "综合分析", "申论必背素材"),
    (r"申论\2025时政热点必背范文48篇 .pdf", "申论", "议论文写作", "申论范文48篇"),
]

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
CN_RATIO_MIN_FRONT = 0.6
CN_RATIO_MIN_BACK = 0.5


def clean(s: str) -> str:
    return CTRL.sub("", s or "").strip()


def cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    return len(CJK.findall(s)) / len(s)


def ok_front(s: str) -> tuple[bool, str]:
    if not (4 <= len(s) <= 24):
        return False, "长度"
    if PURE_NUM.match(s):
        return False, "纯数字/符号"
    if cjk_ratio(s) < CN_RATIO_MIN_FRONT:
        return False, "中文占比低"
    return True, ""


def ok_back(s: str) -> tuple[bool, str]:
    if len(s) < 40:
        return False, "背面过短"
    if cjk_ratio(s) < CN_RATIO_MIN_BACK:
        return False, "中文占比低"
    return True, ""


def build_cards(text_lines):
    rows, buf, front = [], [], None
    rejected = {"长度": 0, "纯数字/符号": 0, "中文占比低": 0, "背面过短": 0}
    for raw in text_lines:
        line = clean(re.sub(r"\s+", " ", raw))
        if not line or PRIVATE.search(line):
            continue
        is_head = len(line) <= 30 and not HEAD_END.search(line)
        if is_head:
            if front and buf:
                back = "".join(buf)
                f_ok, f_reason = ok_front(front)
                b_ok, b_reason = ok_back(back)
                if f_ok and b_ok:
                    rows.append([front[:120], back[:600]])
                else:
                    rejected[f_reason if not f_ok else b_reason] += 1
            front, buf = line, []
        elif front:
            buf.append(line)
    if front and buf:
        back = "".join(buf)
        f_ok, f_reason = ok_front(front)
        b_ok, b_reason = ok_back(back)
        if f_ok and b_ok:
            rows.append([front[:120], back[:600]])
        else:
            rejected[f_reason if not f_ok else b_reason] += 1
    # 去重
    seen, uniq = set(), []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        uniq.append(r)
    return uniq, rejected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    import pymupdf
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    HEAD = ["正面", "背面", "分类", "考点", "封面"]
    os.makedirs(a.out, exist_ok=True)
    total_rows = 0
    for rel, subj, cat, title in TARGETS:
        path = os.path.join(a.src, rel)
        if not os.path.exists(path):
            print(f"[跳过] {rel}：文件不存在")
            continue
        doc = pymupdf.open(path)
        lines = []
        for page in doc:
            lines.extend((page.get_text("text") or "").split("\n"))
        doc.close()
        rows, rejected = build_cards(lines)
        total_rows += len(rows[:200])

        if not a.dry_run:
            wb = Workbook()
            ws = wb.active
            ws.title = "卡片"
            ws.append(HEAD)
            for c in range(1, 6):
                cell = ws.cell(row=1, column=c)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F3A68")
                cell.alignment = Alignment(horizontal="center")
            for f, b in rows[:200]:
                ws.append([clean(f), clean(b), cat, "", ""])
            ws.column_dimensions["A"].width = 24
            ws.column_dimensions["B"].width = 80
            ws.column_dimensions["C"].width = 18
            ws.column_dimensions["D"].width = 20
            ws.column_dimensions["E"].width = 16
            ws.freeze_panes = "A2"
            wb.save(os.path.join(a.out, f"{subj}_{title}.xlsx"))
        print(f"[{title}] 通过 {len(rows)} 条（写入 {min(200, len(rows))}）| 剔除 {rejected}")

    print(f"\n合计可录入卡片：{total_rows} 条；输出目录：{a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
