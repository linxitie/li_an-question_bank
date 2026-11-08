# -*- coding: utf-8 -*-
"""2024 国考公专真卷 → 题库种子导入（一次性工具，2026-11-08 实际跑过并验收）。

用法（在仓库根、后端 8001 已启动的前提下）：
  python backend/scripts/seed_2024_gk/import_2024_gk_paper.py            # dry-run，只打印"每题挂哪些图"
  python backend/scripts/seed_2024_gk/import_2024_gk_paper.py --apply    # 真导入（POST /api/questions/import/batch-parsed）

图片归属**不靠人眼猜**，由 `attribute_figures.py` 按 PDF 版面坐标锚定（图归到它上方最近的题/情境段），
再逐张看图确认。映射结果：
  单题图：40←61 41←64 42←65 43←68 44←69 45←72 46←73 47←76 48←77 49←80 50←81
          65←98 66←101 67←102 68←105 69←106 70←109 75←120 86←130 87/88/89←131
          94←136 95←140 97~100←143
  丢弃件（文字被 Word 切成图片的碎条 / 同一图的低清重复件）：
          82,83,84,87,88,89,90,91,92,93,110,111,112,113,114,115,116,117,123,139

坑（都踩过）：
  · 大图走 base64 会让 question_content 超过 50000 字上限（R-LONG）→ 补录用 `--static-urls`
    把图落到 `backend/app/static/questions/_seed2024/` 后引用 URL，原图无损、正文几百字。
  · `answer_analysis` 才是导入链路的解析字段名，传 `analysis` 会被静默丢弃。
"""
import argparse
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
Q_PDF = os.path.join(BASE, "题库", "公安题目（打印）", "2024年国考《公安专业科目》真题.pdf")
A_PDF = os.path.join(BASE, "题库", "答案解析（不用打印）", "2024年国考《公安专业科目》真题解析.pdf")
IMG_DIR = os.path.join(BASE, "docs", "plans", "assets", "2024国考公专解析冒烟", "images_all_v2")
API = "http://127.0.0.1:8001"
PAPER_CODE = "GZ-2024-GK-T"
PAPER_NAME = "2024年国家公务员考试《公安专业科目》真题（网友回忆版）"

import pymupdf  # noqa: E402

QN_RE = re.compile(r"^\s*(\d{1,3})\s*[.．、]")
OPT_SPLIT_RE = re.compile(r"([A-DＡ-Ｄ])\s*[.．、]\s*")
SEC_RE = re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.]\s*根据以下情境材料\s*[，,]\s*回\s*[答签]\s*"
                    r"(\d{1,3})\s*[—~\-－]+\s*(\d{1,3})\s*题")
MARK_RE = re.compile(r"^\s*【题型】\s*(单选|多选|复合)题?\s*$")
INLINE_RE = re.compile(r"[（(]\s*(单选|多选)\s*[）)]")
ANS_RE = re.compile(r"^\s*(\d{1,3})\s*[、.．]\s*([A-D]{1,4})?\s*(.*)$")
CJK = "\u4e00-\u9fff"

PER_Q_IMAGES = {40: [61], 41: [64], 42: [65], 43: [68], 44: [69], 45: [72], 46: [73],
                47: [76], 48: [77], 49: [80], 50: [81], 65: [98], 66: [101], 67: [102],
                68: [105], 69: [106], 70: [109], 75: [120], 86: [130], 87: [131],
                88: [131], 89: [131], 94: [136], 95: [140]}
GROUP_IMAGES = {8: [143]}


def clean_cn(s):
    s = re.sub(rf"(?<=[{CJK}，。；：、（）“”《》！？])\s+(?=[{CJK}，。；：、（）“”《》！？])", "", s)
    s = re.sub(r"(?<=[0-9])\s+(?=[年月日时分秒分题页条款项])", "", s)
    return s.strip()


def pdf_text(path):
    doc = pymupdf.open(path)
    t = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    doc.close()
    return t


def split_options(block):
    stem, options, cur = [], {k: "" for k in "ABCD"}, None
    for raw in block:
        ln = raw.strip()
        if not ln or ln.startswith("【题型】"):
            continue
        pos = list(OPT_SPLIT_RE.finditer(ln))
        if pos:
            first = ln[:pos[0].start()]
            if first.strip():
                if cur is None:
                    stem.append(first.strip())
                else:
                    options[cur] = (options[cur] + " " + first.strip()).strip()
            for i, m in enumerate(pos):
                key = m.group(1).translate(str.maketrans("ＡＢＣＤ", "ABCD"))
                end = pos[i + 1].start() if i + 1 < len(pos) else len(ln)
                options[key] = ln[m.end():end].strip()
                cur = key
        elif cur:
            options[cur] = (options[cur] + " " + ln).strip()
        else:
            stem.append(ln)
    return clean_cn("".join(stem)), {k: clean_cn(v) for k, v in options.items()}


def parse_questions():
    lines = [ln.rstrip() for ln in pdf_text(Q_PDF).splitlines()]
    starts = [(i, int(m.group(1))) for i, ln in enumerate(lines) for m in [QN_RE.match(ln)] if m]

    marks, cur_state = {}, "单选"
    for i, ln in enumerate(lines):
        m = MARK_RE.match(ln)
        if m:
            cur_state = "多选" if m.group(1) in ("多选", "复合") else "单选"
            marks[i] = cur_state
    marks_sorted = sorted(marks.items())

    sections = []
    for i, ln in enumerate(lines):
        m = SEC_RE.match(ln)
        if not m:
            continue
        nxt = next((s for s, _ in starts if s > i), len(lines))
        body = " ".join(x.strip() for x in lines[i + 1:nxt]
                        if x.strip() and not x.strip().startswith("【题型】"))
        sections.append((i, int(m.group(1)), int(m.group(2)), clean_cn(body)))

    out = []
    for idx, (ln_no, no) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = [lines[j] for j in range(ln_no, end)]
        block[0] = QN_RE.sub("", block[0])
        stem, options = split_options(block)

        state = "单选"
        for m_line, kind in marks_sorted:
            if m_line < ln_no:
                state = kind
            else:
                break
        default_type = "单选" if state == "复合" else state
        m = INLINE_RE.search(re.sub(r"\s+", "", " ".join(block)))
        qtype = m.group(1) if m else default_type

        shared, gi = "", 0
        for j, (sec_start, a, b, material) in enumerate(sections, 1):
            if a <= no <= b and sec_start < ln_no:
                shared, gi = material, j
                break
        out.append({"no": no, "stem": stem, "options": options, "type": qtype,
                    "shared": shared, "group": gi})
    return out


def parse_answers():
    lines = [ln.rstrip() for ln in pdf_text(A_PDF).splitlines()]
    hits = []
    for i, ln in enumerate(lines):
        m = ANS_RE.match(ln)
        if m and (m.group(2) or "本题考查" in ln):
            hits.append((i, int(m.group(1)), m.group(2) or "", m.group(3) or ""))
    out = {}
    for k, (i, no, letters, head) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        analysis = clean_cn(head + " " + " ".join(x.strip() for x in lines[i + 1:end] if x.strip()))
        explicit = bool(letters)
        if not letters:
            flat = re.sub(r"\s+", "", analysis)
            cand = set(re.findall(r"([A-D])正确", flat))
            wrong = set(re.findall(r"([A-D]{1,4})错误", flat))
            cand = {c for c in cand if c not in wrong}
            if 0 < len(cand) <= 4:
                letters = "".join(sorted(cand))
        out[no] = {"answer": letters, "analysis": analysis, "explicit": explicit}
    return out


SEED_STATIC = os.path.join(BASE, "backend", "app", "static", "questions", "_seed2024")


def image_static_url(xref):
    """把图复制到 static/questions/_seed2024/，正文直接引用 /static URL。

    为什么不走 base64：大图内联会让 question_content 超过 50000 字符上限（R-LONG），
    而压缩到能过限又必然糊掉图表文字。落盘引用则原图无损。
    """
    for f in os.listdir(IMG_DIR):
        if re.search(rf"xref{xref}_", f):
            os.makedirs(SEED_STATIC, exist_ok=True)
            ext = os.path.splitext(f)[1]
            name = f"gk2024_xref{xref}{ext}"
            dst = os.path.join(SEED_STATIC, name)
            if not os.path.exists(dst):
                with open(os.path.join(IMG_DIR, f), "rb") as src, open(dst, "wb") as out:
                    out.write(src.read())
            return f"/static/questions/_seed2024/{name}"
    return None


def image_b64(xref, max_b64=28000):
    """读图并转 data URI；过大时等比缩小/重压缩，避免 question_content 触发 R-LONG 50000 上限。"""
    for f in os.listdir(IMG_DIR):
        m = re.search(rf"xref{xref}_", f)
        if m:
            path = os.path.join(IMG_DIR, f)
            with open(path, "rb") as fh:
                data = fh.read()
            ext = "jpeg" if f.endswith((".jpeg", ".jpg")) else "png"
            if len(base64.b64encode(data)) > max_b64:
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    w, h = im.size
                    side = 900
                    if max(w, h) > side:
                        im = im.resize((int(w * side / max(w, h)), int(h * side / max(w, h))),
                                       Image.LANCZOS)
                    for q in (82, 70, 60, 50):
                        buf = io.BytesIO()
                        im.save(buf, format="JPEG", quality=q, optimize=True)
                        cand = buf.getvalue()
                        if len(base64.b64encode(cand)) <= max_b64:
                            data, ext = cand, "jpeg"
                            break
                    else:
                        data, ext = cand, "jpeg"
                except Exception as e:  # noqa: BLE001
                    print(f"  ! xref{xref} 压缩失败，仍按原图内联: {e}")
            return f"data:image/{ext};base64," + base64.b64encode(data).decode()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="", help="只导入这些题号，逗号分隔（补录用）")
    ap.add_argument("--static-urls", action="store_true",
                    help="图片落盘到 /static 并在正文引用 URL（大图补录时用，绕开 50000 字上限）")
    args = ap.parse_args()
    only = {int(x) for x in re.findall(r"\d+", args.only)} if args.only else set()
    pick = image_static_url if args.static_urls else image_b64

    questions = parse_questions()
    answers = parse_answers()
    print(f"题目 {len(questions)}｜答案 {len(answers)}")

    payload_items, plan = [], []
    for q in questions:
        if only and q["no"] not in only:
            continue
        a = answers.get(q["no"], {})
        imgs = list(PER_Q_IMAGES.get(q["no"], []))
        if q["group"] and q["group"] in GROUP_IMAGES:
            imgs += GROUP_IMAGES[q["group"]]
        imgs = sorted(set(imgs))
        plan.append((q["no"], q["type"], imgs))

        html = ""
        if q["shared"]:
            html += f"<p>{q['shared']}</p>"
        html += f"<p>{q['stem']}</p>"
        for x in imgs:
            uri = pick(x)
            if uri:
                html += f'<p><img src="{uri}" /></p>'
        payload_items.append({
            "question_number": str(q["no"]),
            "question_content": html,
            "options": [{"key": k, "value": q["options"][k]} for k in "ABCD" if q["options"][k]],
            "answer": a.get("answer", ""),
            "answer_analysis": a.get("analysis", ""),
            "question_type_detail": "多选题" if q["type"] == "多选" else "单选题",
            "subject_category": "公专",
            "difficulty": 3,
            "score": 1,
            "source": "2024国考公专（网友回忆版）",
        })

    with_img = [p for p in plan if p[2]]
    print(f"带图题 {len(with_img)} 道；无图 {len(plan)-len(with_img)} 道")
    for no, t, imgs in with_img:
        print(f"  题{no:>3}（{t}）← xref {imgs}")
    longest = max(payload_items, key=lambda it: len(it["question_content"]))
    print(f"最长题干长度 {len(longest['question_content'])}（题{longest['question_number']}，上限 50000）")

    # 反向校验：文字里提到"图/表"却没挂图的题（漏图风险）
    by_no = {q["no"]: q for q in questions}
    miss = [no for no, t, imgs in plan
            if not imgs and re.search(r"下图|上图|表中|图1|表1|见表|如图", by_no[no]["stem"])]
    print("提到图却没图（漏图风险）：", miss if miss else "无")

    if not args.apply:
        print("\n（dry-run）加 --apply 才会真的 POST 导入")
        return 0

    token = None
    data = urllib.parse.urlencode({"username": "cbrycc", "password": "cbrycc"}).encode()
    req = urllib.request.Request(API + "/api/auth/login", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        token = json.loads(r.read().decode()).get("access_token")

    body = json.dumps({"paper_name": PAPER_NAME, "paper_code": PAPER_CODE,
                       "subject_category": "公专", "import_mode": "combined",
                       "match_rate": 100.0, "questions": payload_items}).encode()
    req = urllib.request.Request(API + "/api/questions/import/batch-parsed", data=body,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        return 1
    print("\n导入结果:", {k: resp.get(k) for k in
                        ("paper_id", "success_count", "duplicate_count", "need_confirm_count", "message")})
    print("失败条目:", (resp.get("failed_items") or [])[:5])
    return 0


if __name__ == "__main__":
    sys.exit(main())
