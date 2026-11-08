# -*- coding: utf-8 -*-
"""按版面坐标把每张图归属到"它正上方最近的那道题/那段情境材料"，取代人工猜测。

输出 `docs/plans/assets/2024国考公专解析冒烟/图片归属_按坐标.json`，并逐行打印
`页码 / xref / 尺寸 / y 坐标 / 推定归属`。判读方法：锚点 = 题号行（1~100）与
情境材料段首行；图片归属到 (页码, y) 不大于图片顶边的最后一个锚点。

**注意**：坐标只给"候选归属"，Word 排版会把图浮动到别处（实测 xref120 落在
题74 正文里，实际是题75 的"雨东派出所巡逻警组位置示意图"），所以最后仍要
逐张看图确认 —— 本脚本负责把 43 张图缩到二十几张候选，人工只判重复件与浮图。
"""
import json
import os
import re

import pymupdf

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Q_PDF = os.path.join(BASE, "题库", "公安题目（打印）", "2024年国考《公安专业科目》真题.pdf")
OUT = os.path.join(BASE, "docs", "plans", "assets", "2024国考公专解析冒烟", "图片归属_按坐标.json")

QN_RE = re.compile(r"^\s*(\d{1,3})\s*[.．、]")
SEC_RE = re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.]\s*根据以下情境材料")

doc = pymupdf.open(Q_PDF)
anchors = []  # (page_idx, y1, kind, label)
for pno in range(doc.page_count):
    for blk in doc[pno].get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if not txt:
                continue
            m = QN_RE.match(txt)
            if m and 1 <= int(m.group(1)) <= 100:
                anchors.append((pno, line["bbox"][3], "题", int(m.group(1))))
                continue
            if SEC_RE.match(txt):
                anchors.append((pno, line["bbox"][3], "情境", re.sub(r"\s+", "", txt)[:24]))
anchors.sort(key=lambda a: (a[0], a[1]))

images = []
for pno in range(doc.page_count):
    for info in doc[pno].get_image_info(xrefs=True):
        images.append((pno, info["bbox"], info.get("xref") or 0))

print(f"锚点 {len(anchors)} 个（题 {sum(1 for a in anchors if a[2]=='题')} / 情境 {sum(1 for a in anchors if a[2]=='情境')}）")
print(f"图对象 {len(images)} 个\n")

rows = []
for pno, bbox, xref in images:
    cands = [a for a in anchors if (a[0], a[1]) <= (pno, bbox[1])]
    owner = cands[-1] if cands else None
    rows.append({"page": pno + 1, "xref": xref,
                 "bbox": [round(v, 1) for v in bbox],
                 "w": round(bbox[2] - bbox[0], 1), "h": round(bbox[3] - bbox[1], 1),
                 "owner": owner[2] if owner else None,
                 "label": owner[3] if owner else None})

for r in rows:
    print(f"p{r['page']:>2} xref{r['xref']:>4} {r['w']:>6.1f}x{r['h']:>5.1f} @y{r['bbox'][1]:>6.1f} "
          f"-> {r['owner']} {r['label']}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
import json
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print(f"\n已写 {OUT}")
