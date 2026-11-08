# -*- coding: utf-8 -*-
"""试卷 PDF 拆题冒烟工具（2026-11-08）—— 文本型真题 PDF → 题目/选项/题型/答案/解析。

用途
----
验证"语料库里的真题 PDF 能不能自动拆成结构化题目"，产物是一份**只读**的对照清单，
供人工确认质量后再决定是否入库。**绝不写库**。

已验证语料（`题库/公安题目（打印）/2024年国考《公安专业科目》真题.pdf` +
`题库/答案解析（不用打印）/2024年国考《公安专业科目》真题解析.pdf`）：
  · 100 题（题号 1–100 连续，缺号 0）
  · 四项选项齐全 100/100
  · 情境材料覆盖 30/30（71–100，8 组）
  · 题型 单选 70 / 多选 30（与公专真实卷型一致）
  · 答案解析命中 100/100（其中 81 题解析未写字母，从"故BC 错误，D 正确"推断为 D）

三条踩过的坑（已修，别再踩）
--------------------------
 ① 卷面**没有**"单项选择题/多项选择题"大标题，只有 4 处 `【题型】X` 出现在"下一题之前"；
    必须用**段落状态机**（`【题型】多选题` 之后的题默认多选，遇到 `复合题` 转情境段），
    否则 51–70 这 20 道多选题会被全部误判成单选。
 ② 选项可能**一行连排**（`A.平等权B.帮助权C.监督权D.财产权`）→ 必须按 `[A-D][.．、]` 切分，
    不能只按行首匹配（否则只取到 A）。
 ③ PDF 换行会把标记/词切断（`（多\n选）`、`故D 正\n确`）→ 先拼接再**去空白**匹配；
    同时中文句中断行会留空格，展示前用 `clean_cn()` 清掉。

用法
----
    cd backend
    python scripts/parse_paper_pdf_smoke.py     # 只读，生成对照清单到 docs/plans/assets/…
"""
import io
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"C:\Users\35709\OneDrive\Desktop\题库\li_an-question_bank"
Q_PDF = os.path.join(BASE, "题库", "公安题目（打印）", "2024年国考《公安专业科目》真题.pdf")
A_PDF = os.path.join(BASE, "题库", "答案解析（不用打印）", "2024年国考《公安专业科目》真题解析.pdf")
OUT_DIR = os.path.join(BASE, "docs", "plans", "assets", "2024国考公专解析冒烟")
OUT_MD = os.path.join(OUT_DIR, "对照清单_v1.md")

import pymupdf  # noqa: E402

QN_RE = re.compile(r"^\s*(\d{1,3})\s*[.．、]")
OPT_SPLIT_RE = re.compile(r"([A-DＡ-Ｄ])\s*[.．、]\s*")
SEC_RE = re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.]\s*根据以下情境材料\s*[，,]\s*回\s*[答签]\s*"
                    r"(\d{1,3})\s*[—~\-－]+\s*(\d{1,3})\s*题")
MARK_RE = re.compile(r"^\s*【题型】\s*(单选|多选|复合)题?\s*$")
INLINE_RE = re.compile(r"[（(]\s*(单选|多选)\s*[）)]")
ANS_RE = re.compile(r"^\s*(\d{1,3})\s*[、.．]\s*([A-D]{1,4})?\s*(.*)$")


CJK = "\u4e00-\u9fff"


def clean_cn(s: str) -> str:
    """去掉 PDF 换行造成的"汉字之间多余空格"（`会议指 出` → `会议指出`），英文/数字之间的空格保留。"""
    s = re.sub(rf"(?<=[{CJK}，。；：、（）“”《》！？])\s+(?=[{CJK}，。；：、（）“”《》！？])", "", s)
    s = re.sub(r"(?<=[0-9])\s+(?=[年月日时分秒分题页条款项])", "", s)
    return s


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
    return "".join(stem), options


def parse_questions(text):
    lines = [ln.rstrip() for ln in text.splitlines()]
    starts = [(i, int(m.group(1))) for i, ln in enumerate(lines) for m in [QN_RE.match(ln)] if m]

    # 段落状态：`【题型】X` 切换后续默认题型
    section_default = {}
    current = "单选"
    mark_at = {}
    for i, ln in enumerate(lines):
        m = MARK_RE.match(ln)
        if m:
            kind = m.group(1)
            current = "复合" if kind == "复合" else kind + "选" if kind != "复合" else "复合"
            current = "单选" if kind == "单选" else ("多选" if kind == "多选" else "复合")
            mark_at[i] = current
    # 为每个题号算"它之前最近的标记"
    marks_sorted = sorted(mark_at.items())
    default_for = {}
    for ln_no, no in starts:
        state = "单选"
        for m_line, kind in marks_sorted:
            if m_line < ln_no:
                state = kind
            else:
                break
        default_for[no] = "单选" if state == "复合" else state

    sections = []
    for i, ln in enumerate(lines):
        m = SEC_RE.match(ln)
        if not m:
            continue
        nxt = next((s for s, _ in starts if s > i), len(lines))
        body = " ".join(x.strip() for x in lines[i + 1:nxt]
                        if x.strip() and not x.strip().startswith("【题型】"))
        sections.append((i, int(m.group(1)), int(m.group(2)), body.strip()))

    questions = []
    for idx, (ln_no, no) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = [lines[j] for j in range(ln_no, end)]
        block[0] = QN_RE.sub("", block[0])
        stem, options = split_options(block)

        joined = " ".join(x.strip() for x in block)
        # 关键：PDF 会把「（多选）」折断成「（多\n选）」，拼接后仍带空格 → 去空白再匹配
        joined_norm = re.sub(r"\s+", "", joined)
        m = INLINE_RE.search(joined_norm)
        qtype = m.group(1) if m else default_for.get(no, "单选")

        shared, sec_no = "", 0
        for j, (sec_start, fno, tno, material) in enumerate(sections):
            if fno <= no <= tno and sec_start < ln_no:
                shared, sec_no = clean_cn(material), j + 1
                break
        questions.append({"no": no, "stem": clean_cn(stem), "options": options, "type": qtype,
                          "shared": shared, "section": sec_no})
    return questions


def parse_answers(text):
    lines = [ln.rstrip() for ln in text.splitlines()]
    hits = []
    for i, ln in enumerate(lines):
        m = ANS_RE.match(ln)
        if m and (m.group(2) or "本题考查" in ln):
            hits.append((i, int(m.group(1)), m.group(2) or "", m.group(3) or ""))
    out = {}
    for k, (i, no, letters, head) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        analysis = (head + " " + " ".join(x.strip() for x in lines[i + 1:end] if x.strip())).strip()
        inferred = False
        if not letters:
            # 兜底：从"X 正确"里推（仅当明确出现，且数量 ≤4）
            flat = re.sub(r"\s+", "", analysis)
            cand = set(re.findall(r"([A-D])正确", flat))
            wrong = set(re.findall(r"([A-D]{1,4})错误", flat))
            cand = {c for c in cand if c not in wrong}
            if 0 < len(cand) <= 4:
                letters = "".join(sorted(cand))
                inferred = True
        out[no] = {"answer": letters, "analysis": clean_cn(analysis), "inferred": inferred}
    return out


def main():
    questions = parse_questions(pdf_text(Q_PDF))
    answers = parse_answers(pdf_text(A_PDF))

    no_set = {q["no"] for q in questions}
    bad_opts = [q["no"] for q in questions if not all(q["options"][k] for k in "ABCD")]
    shared_cnt = sum(1 for q in questions if q["shared"])
    type_cnt = Counter(q["type"] for q in questions)
    missing = [q["no"] for q in questions if not answers.get(q["no"], {}).get("answer")]
    inferred = [q["no"] for q in questions if answers.get(q["no"], {}).get("inferred")]
    conflict = [q["no"] for q in questions
                if answers.get(q["no"], {}).get("answer")
                and ((q["type"] == "单选" and len(answers[q["no"]]["answer"]) != 1)
                     or (q["type"] == "多选" and len(answers[q["no"]]["answer"]) < 2))]

    print("=" * 78)
    print(f"题量 {len(questions)}（{min(no_set)}–{max(no_set)}，缺号 {sorted(set(range(1,101))-no_set) or '无'}）")
    print(f"选项不全：{bad_opts or '无'}｜情境材料覆盖：{shared_cnt}/30｜题型：{dict(type_cnt)}")
    print(f"答案命中 {len(questions)-len(missing)}/{len(questions)}；其中推断 {inferred or '无'}；缺 {missing or '无'}")
    img_dep = [q["no"] for q in questions if re.search(r"图|表|下图|如下图", q["stem"] + q["shared"])]
    print(f"题型×答案字母数冲突：{conflict or '无'}")
    print(f"依赖图/表的题（需抽图，否则不能作答）：{len(img_dep)} 题 → {img_dep[:20]}")

    picks = [q for q in questions if q["no"] in (1, 2, 3, 4, 5, 100)]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# 2024 国考公专真题 · 解析冒烟对照清单（v1）\n\n")
        f.write("> 题源：`题库/公安题目（打印）/2024年国考《公安专业科目》真题.pdf`（29 页，文本型，无需 OCR）\n")
        f.write("> 答案源：`题库/答案解析（不用打印）/2024年国考《公安专业科目》真题解析.pdf`（23 页）\n")
        f.write("> **本清单只读 PDF、不写任何库**，用于确认自动解析质量。\n\n")
        f.write("| 指标 | 结果 |\n|---|---|\n")
        f.write(f"| 题量 | **{len(questions)} 题**（题号 {min(no_set)}–{max(no_set)}，缺号 {sorted(set(range(1,101))-no_set) or '无'}） |\n")
        f.write(f"| 四项选项齐全 | **{len(questions)-len(bad_opts)}/{len(questions)}**{('（不全：' + str(bad_opts) + '）') if bad_opts else ''} |\n")
        f.write(f"| 情境材料覆盖 | **{shared_cnt}/30**（71–100，8 组材料） |\n")
        f.write(f"| 题型分布 | {dict(type_cnt)} |\n")
        f.write(f"| 答案解析命中 | **{len(questions)-len(missing)}/{len(questions)}**"
                f"{('（推断：' + str(inferred) + '）') if inferred else ''}"
                f"{('（缺：' + str(missing) + '）') if missing else ''} |\n")
        f.write(f"| 题型与答案字母数冲突 | {conflict or '无'} |\n\n---\n\n")
        for q in picks:
            a = answers.get(q["no"], {})
            f.write(f"## 第 {q['no']} 题（{q['type']}）"
                    f"{'· 情境组 ' + str(q['section']) if q['section'] else ''}\n\n")
            if q["shared"]:
                f.write("**情境材料（随题共享）**\n\n> " + q["shared"][:600] + "\n\n")
            f.write("**题干**\n\n" + q["stem"] + "\n\n**选项**\n\n")
            for k in "ABCD":
                f.write(f"- {k}. {q['options'][k] or '（缺）'}\n")
            ans = a.get("answer") or "（未匹配）"
            tag = "（从解析推断）" if a.get("inferred") else ""
            f.write(f"\n**答案**：`{ans}`{tag}\n\n**解析（前 320 字）**\n\n> "
                    + (a.get("analysis") or "（未匹配）")[:320] + "\n\n---\n\n")
    print(f"\n对照清单：{os.path.relpath(OUT_MD, BASE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
