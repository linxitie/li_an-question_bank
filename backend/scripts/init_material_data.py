# -*- coding: utf-8 -*-
"""备考资料「一键初始化」：迁移 → 卡片 → 成就 → 分类规则（全部幂等）。

用法（在 backend 目录）：
    python scripts/init_material_data.py            # 只初始化缺失项
    python scripts/init_material_data.py --dry-run  # 只看将要做什么

设计要点
- 幂等：卡片按 (subject, type, title) 判重；成就按 (name, trigger_type)；规则按 rule_name。
- 不编造：卡片正面/分类逐字取自 knowledge_point / sub_categories；背面用方法论文案。
- 迁移自愈：缺列/缺表时按 migrations/*.sql 补齐；已存在则跳过。
- 不动任何用户数据：只做 INSERT IGNORE 式新增与 DDL 补列。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "question_bank.db")

SUBJECTS = {"xingce": 1, "shenlun": 2, "gongzhuan": 3}
TARGET = {"xingce": 12, "shenlun": 10, "gongzhuan": 10}

# 子类 → 备考要点（方法论，无编造事实）
HINT = {
    "言语理解与表达": "先判语境再辨词义；抓主旨句与行文脉络，警惕以偏概全、过度推断、无中生有。",
    "常识判断": "抓关键词对应即可，不纠缠细节；不会就选，避免占用后段时间。",
    "判断推理": "先看元素组成（相同/相似/不同），再定规律：位置、样式、数量、属性。",
    "数量关系": "先列式再计算，能估算不精算；列不出式的题果断放弃。",
    "资料分析": "先读题干定指标，再回材料找数据；增长率、比重、平均数三类优先。",
    "政治理论": "记固定搭配与定位（根本保证/根本宗旨/根本立场），不背长段原文。",
    "知觉速度与准确性": "固定节拍 + 短时高频（每次 3~5 分钟），先稳再快。",
    "科学推理": "先判物理/化学/生物场景，再套基本规律，注意单位与量纲。",
    "归纳概括": "要点齐全优先、语言从简；同类合并，避免交叉重复。",
    "综合分析": "先解释、再分析、后结论，落点回到材料主旨。",
    "提出对策": "每条写清主体、动作与落点，避免“加强重视”式空话。",
    "应用文写作": "格式（称谓/正文/落款/日期）齐备，内容仍须来自材料。",
    "议论文写作": "论点明确、结构完整优先；先写完再润色。",
    "职业素养": "先判价值取向（忠诚/为民/公正/廉洁），再排除违反职业纪律的选项。",
    "基础知识": "抓适用条件与程序顺序（先审批后实施）；不背条文原文，记适用边界。",
    "基本警务能力": "按“接警—处置—善后”顺序复盘，注意程序合规与信息上报。",
}

ACHIEVEMENTS = [
    ("成长", "开卷有益", "📖", "首次读完 1 篇备考资料", 10, "material", "material_read_count", 1, 50),
    ("成长", "勤读不辍", "📚", "累计读完 10 篇备考资料", 40, "material", "material_read_count", 10, 51),
    ("成长", "博览群书", "🏛️", "累计读完 50 篇备考资料", 100, "material", "material_read_count", 50, 52),
]

# 分类规则：科目 + 子类 + 关键词（关键词取自考点名中的主题词，不做语义推断）
RULES = [
    ("行测·言语理解与表达", "keyword", {"subject": "xingce", "category": "言语理解与表达",
        "keywords": ["逻辑填空", "片段阅读", "语句排序", "语句表达", "病句", "中心理解", "词义"]}, 90),
    ("行测·常识判断", "keyword", {"subject": "xingce", "category": "常识判断",
        "keywords": ["常识", "文化", "经济常识", "法律常识", "科技常识", "人文"]}, 88),
    ("行测·判断推理", "keyword", {"subject": "xingce", "category": "判断推理",
        "keywords": ["图形推理", "类比推理", "逻辑判断", "定义判断", "加强", "削弱"]}, 88),
    ("行测·数量关系", "keyword", {"subject": "xingce", "category": "数量关系",
        "keywords": ["数学运算", "数字推理", "工程问题", "行程问题", "排列组合", "概率"]}, 88),
    ("行测·资料分析", "keyword", {"subject": "xingce", "category": "资料分析",
        "keywords": ["资料分析", "增长率", "比重", "平均数", "倍数", "同比"]}, 88),
    ("行测·政治理论", "keyword", {"subject": "xingce", "category": "政治理论",
        "keywords": ["二十大", "习近平", "新时代", "政治理论", "党的"]}, 92),
    ("行测·知觉速度", "keyword", {"subject": "xingce", "category": "知觉速度与准确性",
        "keywords": ["同符查找", "知觉速度", "字符"]}, 86),
    ("行测·科学推理", "keyword", {"subject": "xingce", "category": "科学推理",
        "keywords": ["科学推理", "物理", "化学", "生物", "电路", "受力"]}, 86),
    ("申论·归纳概括", "keyword", {"subject": "shenlun", "category": "归纳概括",
        "keywords": ["归纳", "概括", "要点", "问题概括", "原因概括"]}, 90),
    ("申论·综合分析", "keyword", {"subject": "shenlun", "category": "综合分析",
        "keywords": ["综合分析", "现象分析", "词句理解", "评价", "比较分析"]}, 90),
    ("申论·提出对策", "keyword", {"subject": "shenlun", "category": "提出对策",
        "keywords": ["对策", "建议", "措施", "方案", "做法"]}, 90),
    ("申论·应用文写作", "keyword", {"subject": "shenlun", "category": "应用文写作",
        "keywords": ["应用文", "事务文书", "公文", "倡议书", "建议书", "讲话稿", "汇报"]}, 90),
    ("申论·议论文写作", "keyword", {"subject": "shenlun", "category": "议论文写作",
        "keywords": ["议论文", "话题作文", "论点", "论证", "写作"]}, 90),
    ("公专·职业素养", "keyword", {"subject": "gongzhuan", "category": "职业素养",
        "keywords": ["职业道德", "核心价值观", "职业素养", "纪律", "廉政"]}, 90),
    ("公专·基础知识", "keyword", {"subject": "gongzhuan", "category": "基础知识",
        "keywords": ["宪法", "刑法", "治安", "刑事诉讼法", "公安基础", "法条"]}, 90),
    ("公专·基本警务能力", "keyword", {"subject": "gongzhuan", "category": "基本警务能力",
        "keywords": ["接警", "处置", "现场", "盘查", "组织动员", "警务技能", "群众工作"]}, 90),
]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def ensure_migrations(con: sqlite3.Connection, dry: bool) -> list[str]:
    """按 migrations 目录里的 20261027_002/003 补列补表（幂等）。"""
    done = []
    cols = {r[1] for r in con.execute("PRAGMA table_info(study_material)")}
    if "source_material_id" not in cols:
        if not dry:
            con.execute("ALTER TABLE study_material ADD COLUMN source_material_id INTEGER")
            con.execute("CREATE INDEX IF NOT EXISTS idx_material_owner ON study_material(creator_id, status)")
        done.append("补列 study_material.source_material_id + idx_material_owner")

    # P2.2：分类法第三层（资料 → 考点）
    if "point_id" not in cols:
        if not dry:
            con.execute("ALTER TABLE study_material ADD COLUMN point_id INTEGER")
            con.execute("CREATE INDEX IF NOT EXISTS idx_material_point ON study_material(point_id)")
        done.append("补列 study_material.point_id + idx_material_point")

    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "material_share" not in tables:
        if not dry:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS material_share (
                share_id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL UNIQUE,
                owner_id INTEGER NOT NULL,
                scope TEXT NOT NULL DEFAULT 'public',
                status INTEGER NOT NULL DEFAULT 1,
                adopted_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_share_owner ON material_share(owner_id, status);
            CREATE TABLE IF NOT EXISTS material_adopt_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                share_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_adopt UNIQUE (share_id, user_id)
            );
            """)
        done.append("建表 material_share + material_adopt_log")

    if not dry:
        con.commit()
    return done


def load_points(con: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    cats = {r[0]: r[1] for r in con.execute("SELECT id, name FROM sub_categories")}
    out: dict[str, list[tuple[str, str]]] = {}
    for key, sid in SUBJECTS.items():
        rows = con.execute(
            "SELECT point_name, sub_category_id FROM knowledge_point "
            "WHERE subject_id=? ORDER BY sub_category_id, point_id", (sid,)).fetchall()
        out[key] = [(p, cats.get(c, "")) for p, c in rows]
    return out


def pick(points: list[tuple[str, str]], n: int) -> list[tuple[str, str]]:
    by_cat: dict[str, list[str]] = {}
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


def seed_cards(con: sqlite3.Connection, dry: bool) -> tuple[int, int]:
    pts = load_points(con)
    created = skipped = 0
    for key, n in TARGET.items():
        for point, cat in pick(pts[key], n):
            hit = con.execute(
                "SELECT material_id FROM study_material WHERE subject=? AND type='card' AND title=?",
                (key, point)).fetchone()
            if hit:
                skipped += 1
                continue
            if not dry:
                con.execute(
                    """INSERT INTO study_material(subject,type,category,title,card_front,card_back,
                       badge,difficulty,status,creator_id,study_count,create_time)
                       VALUES(?,?,?,?,?,?,?,?,1,1,0,CURRENT_TIMESTAMP)""",
                    (key, "card", cat, point, f"{point}（{cat}）",
                     HINT.get(cat, "按考点理解适用场景，先判断题型再作答。"), "要点", 2))
            created += 1
    if not dry:
        con.commit()
    return created, skipped


def seed_achievements(con: sqlite3.Connection, dry: bool) -> tuple[int, int]:
    created = skipped = 0
    for cat, name, icon, desc, coins, trig, code, th, sort in ACHIEVEMENTS:
        hit = con.execute("SELECT achievement_id FROM achievement WHERE name=? AND trigger_type=?",
                          (name, trig)).fetchone()
        if hit:
            skipped += 1
            continue
        if not dry:
            con.execute(
                "INSERT INTO achievement(category,name,icon,condition_desc,reward_coins,"
                "trigger_type,condition_code,threshold,sort_order) VALUES(?,?,?,?,?,?,?,?,?)",
                (cat, name, icon, desc, coins, trig, code, th, sort))
        created += 1
    if not dry:
        con.commit()
    return created, skipped


def seed_rules(con: sqlite3.Connection, dry: bool) -> tuple[int, int]:
    created = skipped = 0
    for name, rtype, cfg, prio in RULES:
        hit = con.execute("SELECT rule_id FROM material_classification_rules WHERE rule_name=?",
                          (name,)).fetchone()
        if hit:
            skipped += 1
            continue
        if not dry:
            con.execute(
                "INSERT INTO material_classification_rules(rule_name,rule_type,rule_config,priority,enabled)"
                " VALUES(?,?,?,?,1)", (name, rtype, json.dumps(cfg, ensure_ascii=False), prio))
        created += 1
    if not dry:
        con.commit()
    return created, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(DB):
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1

    print(f"数据库: {DB}")
    print(f"模式: {'DRY-RUN（不写库）' if args.dry_run else '实际执行'}\n")
    con = connect()
    try:
        mig = ensure_migrations(con, args.dry_run)
        print("① 迁移：" + ("；".join(mig) if mig else "无需处理（已是最新）"))

        c1, s1 = seed_cards(con, args.dry_run)
        print(f"② 卡片：新增 {c1}，已存在跳过 {s1}")

        c2, s2 = seed_achievements(con, args.dry_run)
        print(f"③ 成就：新增 {c2}，已存在跳过 {s2}")

        c3, s3 = seed_rules(con, args.dry_run)
        print(f"④ 分类规则：新增 {c3}，已存在跳过 {s3}")

        if not args.dry_run:
            print("\n当前库内统计：")
            for key, n in (("xingce", "行测"), ("shenlun", "申论"), ("gongzhuan", "公专")):
                cnt = con.execute(
                    "SELECT COUNT(*) FROM study_material WHERE subject=? AND type='card' AND status=1",
                    (key,)).fetchone()[0]
                print(f"  {n}: 卡片 {cnt} 张")
            print("  material 成就:",
                  con.execute("SELECT COUNT(*) FROM achievement WHERE trigger_type='material'").fetchone()[0])
            print("  分类规则:",
                  con.execute("SELECT COUNT(*) FROM material_classification_rules WHERE enabled=1").fetchone()[0])
    finally:
        con.close()
    print("\n完成。可重复执行（幂等）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
