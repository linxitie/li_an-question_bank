# -*- coding: utf-8 -*-
"""播种「考点级」分类规则（P2.3，幂等）。

背景：material_classification_rules 原有 16 条 = 16 个子类，粒度只到子类，
94 个考点没有任何规则，自动分类永远出不了 point_id。

本脚本从 knowledge_point 逐点生成规则（每个考点 1 条），rule_config 形如
    {"subject": "xingce", "category": "判断推理", "point": "图形推理",
     "keywords": ["图形推理", "图形", "九宫格"]}
优先级按考点名长度递增（越具体越优先），与现有子类规则共存：
命中考点规则时会同时带出父类 category，因此一条规则即可补全两级。

用法：
    python scripts/seed_material_point_rules.py            # 只看计划
    python scripts/seed_material_point_rules.py --apply    # 落库
    python scripts/seed_material_point_rules.py --apply --refresh   # 覆盖已存在规则
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BACKEND, "data", "question_bank.db")
SUBJECTS = {1: "xingce", 2: "shenlun", 3: "gongzhuan"}

# 少量同义/口语说法，纯为提高召回；不改变考点名本身
ALIASES = {
    "逻辑填空": ["选词填空", "实词辨析", "成语"],
    "片段阅读": ["片段", "主旨概括", "意图判断"],
    "中心理解": ["中心理解题", "主旨题", "找中心"],
    "语句表达": ["病句", "语句衔接", "语句排序"],
    "数字推理": ["数列推理", "数字规律"],
    "数学运算": ["计算问题", "工程问题", "行程问题", "排列组合"],
    "图形推理": ["图形", "九宫格", "折纸盒"],
    "逻辑判断": ["加强削弱", "翻译推理", "真假推理"],
    "类比推理": ["类比", "逻辑关系"],
    "定义判断": ["定义"],
    "资料分析": ["资料"],   # 兜底：子类规则优先级更低，不会抢
    "速算技巧": ["速算", "估算", "截位直除"],
    "统计术语": ["同比", "环比", "增量", "增长率"],
    "同符查找": ["同符", "字符比对"],
    "字符替换": ["字符", "替换"],
    "数字区间定位": ["数字区间", "区间定位"],
    "知觉准确性": ["知觉"],
    "归纳概括": ["归纳", "概括"],
    "综合分析": ["分析", "评析"],
    "提出对策": ["对策", "建议", "方案"],
    "应用文写作": ["公文", "文书", "简报"],
    "议论文写作": ["议论文", "政论文", "策论文", "作文"],
    "职业素养": ["职业道德", "核心价值观", "纪律"],
    "基础知识": ["法律", "宪法", "民法", "人民警察法"],
    "基本警务能力": ["接警", "巡逻", "安全检查", "宣传教育", "沟通协调"],
}


def build_rules(con: sqlite3.Connection) -> list[tuple]:
    cats = {r[0]: (r[1] or "").strip() for r in con.execute("SELECT id, name FROM sub_categories")}
    rows = con.execute(
        "SELECT point_name, subject_id, sub_category_id FROM knowledge_point "
        "WHERE status=1 ORDER BY subject_id, sub_category_id, point_id").fetchall()
    out = []
    for name, sid, scid in rows:
        name = (name or "").strip()
        subj = SUBJECTS.get(sid)
        cat = cats.get(scid, "")
        if not name or not subj:
            continue
        keywords = [name] + ALIASES.get(name, [])
        # 去重保序
        seen, kws = set(), []
        for k in keywords:
            if k and k not in seen:
                seen.add(k)
                kws.append(k)
        cfg = {"subject": subj, "category": cat, "point": name, "keywords": kws}
        out.append((
            f"考点·{subj}·{name}", "keyword",
            json.dumps(cfg, ensure_ascii=False),
            60 + min(len(name), 30), 1,
        ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正落库（默认只打印计划）")
    ap.add_argument("--refresh", action="store_true", help="覆盖已存在的同名规则")
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    rules = build_rules(con)

    existing = {r[0]: r[1] for r in con.execute(
        "SELECT rule_name, rule_id FROM material_classification_rules")}
    new = [r for r in rules if r[0] not in existing]
    upd = [r for r in rules if r[0] in existing] if a.refresh else []

    print(f"考点总数 {len(rules)}；已存在同名规则 {len(rules) - len(new)}；"
          f"将新增 {len(new)}；将刷新 {len(upd)}")
    by_sub: dict[str, int] = {}
    for name, *_ in rules:
        sub = name.split("·")[1]
        by_sub[sub] = by_sub.get(sub, 0) + 1
    print("按科目:", by_sub)

    if not a.apply:
        for r in new[:5]:
            print("  样例:", r[0], "→", r[2])
        print("（未落库，加 --apply 生效）")
        con.close()
        return 0

    with con:
        for name, rtype, cfg, prio, en in new:
            con.execute(
                "INSERT INTO material_classification_rules"
                "(rule_name, rule_type, rule_config, priority, enabled)"
                " VALUES (?,?,?,?,?)", (name, rtype, cfg, prio, en))
        for name, rtype, cfg, prio, en in upd:
            con.execute(
                "UPDATE material_classification_rules SET rule_type=?, rule_config=?,"
                " priority=?, enabled=? WHERE rule_name=?",
                (rtype, cfg, prio, en, name))

    total = con.execute("SELECT COUNT(*) FROM material_classification_rules").fetchone()[0]
    point_rules = con.execute(
        "SELECT COUNT(*) FROM material_classification_rules WHERE rule_config LIKE '%\"point\"%'"
    ).fetchone()[0]
    print(f"✅ 落库完成：规则总数 {total}（其中考点级 {point_rules}）")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
