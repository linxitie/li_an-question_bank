# -*- coding: utf-8 -*-
"""从 knowledge_point / sub_categories 生成三科卡片并上线（数据来自库内权威表，不编造事实）。

- front = 考点名（逐字取自 knowledge_point）
- back  = 按子类给出的备考方法（方法论，不含法条编号/年份等未核实事实）
- 通过 /api/materials/my + publish=true 建卡（creator=管理员），直接上线
"""
import sqlite3

import requests

DB = r"C:\Users\35709\OneDrive\Desktop\题库\li_an-question_bank\backend\data\question_bank.db"
B = "http://127.0.0.1:8000"

# 子类 → 备考要点（方法论）
HINT = {
    # 行测
    "言语理解与表达": "先判语境再辨词义；抓主旨句与行文脉络，警惕以偏概全、过度推断、无中生有。",
    "常识判断": "抓关键词对应即可，不纠缠细节；不会就选，避免占用后段时间。",
    "判断推理": "先看元素组成（相同/相似/不同），再定规律：位置、样式、数量、属性。",
    "数量关系": "先列式再计算，能估算不精算；列不出式的题果断放弃。",
    "资料分析": "先读题干定指标，再回材料找数据；增长率、比重、平均数三类优先。",
    "政治理论": "记固定搭配与定位（根本保证/根本宗旨/根本立场），不背长段原文。",
    "知觉速度与准确性": "固定节拍 + 短时高频（每次 3~5 分钟），先稳再快。",
    "科学推理": "先判物理/化学/生物场景，再套基本规律，注意单位与量纲。",
    # 申论
    "归纳概括": "要点齐全优先、语言从简；同类合并，避免交叉重复。",
    "综合分析": "先解释、再分析、后结论，落点回到材料主旨。",
    "提出对策": "每条写清主体、动作与落点，避免“加强重视”式空话。",
    "应用文写作": "格式（称谓/正文/落款/日期）齐备，内容仍须来自材料。",
    "议论文写作": "论点明确、结构完整优先；先写完再润色。",
    # 公专
    "职业素养": "先判价值取向（忠诚/为民/公正/廉洁），再排除违反职业纪律的选项。",
    "基础知识": "抓适用条件与程序顺序（先审批后实施）；不背条文原文，记适用边界。",
    "基本警务能力": "按“接警—处置—善后”顺序复盘，注意程序合规与信息上报。",
}

# 每科取多少张（按子类轮转，保证覆盖）
TARGET = {"xingce": 12, "shenlun": 10, "gongzhuan": 10}


def load_points():
    con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
    cats = {r[0]: r[1] for r in con.execute("SELECT id, name FROM sub_categories")}
    out = {}
    for sid, key in ((1, "xingce"), (2, "shenlun"), (3, "gongzhuan")):
        rows = con.execute(
            "SELECT point_name, sub_category_id FROM knowledge_point "
            "WHERE subject_id=? ORDER BY sub_category_id, point_id", (sid,)).fetchall()
        out[key] = [(p, cats.get(c, "")) for p, c in rows]
    con.close()
    return out


def pick(points, n):
    """按子类轮转挑选，保证每个子类都有代表卡。"""
    by_cat = {}
    for p, c in points:
        by_cat.setdefault(c, []).append(p)
    picked, i = [], 0
    cats = list(by_cat.keys())
    while len(picked) < n and any(by_cat[c] for c in cats):
        c = cats[i % len(cats)]
        if by_cat[c]:
            picked.append((by_cat[c].pop(0), c))
        i += 1
    return picked


def main():
    tok = requests.post(B + "/api/auth/login",
                        data={"username": "cbrycc", "password": "cbrycc"}, timeout=20).json()["access_token"]
    H = {"Authorization": "Bearer " + tok}
    pts = load_points()
    created = []
    for key, n in TARGET.items():
        for point, cat in pick(pts[key], n):
            hint = HINT.get(cat, "按考点理解适用场景，先判断题型再作答。")
            body = {"subject": key, "type": "card", "category": cat,
                    "title": point, "card_front": f"{point}（{cat}）",
                    "card_back": hint, "badge": "要点", "difficulty": 2,
                    "publish": True}
            r = requests.post(B + "/api/materials/my", json=body, headers=H, timeout=20)
            if r.status_code == 200:
                created.append((key, r.json()["id"], point, cat))
            else:
                print("  ✗ 建卡失败:", key, point, r.status_code, r.text[:80])
    print(f"新建卡片 {len(created)} 张")
    from collections import Counter
    print("  按科目:", dict(Counter(c[0] for c in created)))
    print("  按子类:", dict(Counter(c[3] for c in created)))

    print("\n== 上线后各科 card 计数 ==")
    for key in ("xingce", "shenlun", "gongzhuan"):
        r = requests.get(B + "/api/materials", params={"subject": key, "type": "card"},
                         timeout=15).json()
        print(f"  {key:10} card = {r.get('total')} 条")
    print("\n== 示例 ==")
    for key, mid, point, cat in created[:6]:
        print(f"  #{mid} [{key}/{cat}] {point}")


if __name__ == "__main__":
    main()
