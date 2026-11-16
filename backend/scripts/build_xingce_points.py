# 构建行测知识点树（模块7 图谱挂题的前置；只增不改）
#
# 现状：知识库 613 个点以公专/政治为主，行测五大类考点缺失，导致题目挂点覆盖率仅 4%。
# 本脚本按行测通用考点表创建「行测 → 五大类 → 叶子考点」，不改动任何既有知识点。
#
# 用法：
#   python backend/scripts/build_xingce_points.py            # 预演
#   python backend/scripts/build_xingce_points.py --commit   # 建点（先备份）
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"
SUBJECT_ID = 1

# 五大类 → 叶子考点（行测通用考纲）
TREE: dict[str, list[str]] = {
    "判断推理": [
        "图形推理", "定义判断", "类比推理", "逻辑判断", "真假推理",
        "加强削弱", "翻译推理", "可能性推理", "分析推理",
    ],
    "言语理解与表达": [
        "逻辑填空", "成语辨析", "实词辨析", "片段阅读", "主旨概括",
        "意图判断", "细节判断", "语句排序", "语句衔接", "病句辨析",
    ],
    "数量关系": [
        "工程问题", "行程问题", "利润问题", "浓度问题", "排列组合",
        "概率问题", "容斥原理", "等差数列", "几何问题", "年���问题",
    ],
    "资料分析": [
        "增长率", "增长量", "基期量", "现期量", "比重", "平均数",
        "倍数与翻番", "综合分析", "文字资料分析", "图形资料分析", "表格资料分析",
    ],
    "常识判断": [
        "政治常识", "法律常识", "经济常识", "历史常识", "科技常识",
        "地理常识", "公文写作", "时事政治",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    existing = {n for (n,) in cur.execute("SELECT point_name FROM knowledge_point WHERE subject_id=?", (SUBJECT_ID,))}
    to_add: list[tuple[str, int]] = []      # (name, parent_id)
    for cat, leaves in TREE.items():
        if cat not in existing:
            to_add.append((cat, 0))
        for leaf in leaves:
            if leaf not in existing:
                to_add.append((leaf, 0))    # parent 在建点时回填

    print(f"[PLAN] 拟新增知识点 {len(to_add)} 个（现有行测点 {len(existing)} 个）")
    print("   大类:", "、".join(TREE))

    if not args.commit:
        print("[DRY-RUN] 未写库。确认后加 --commit")
        conn.close()
        return 0

    backup = DB.with_suffix(f".db.bak_points_{datetime.now():%Y%m%d_%H%M%S}")
    dst = sqlite3.connect(str(backup))
    with dst:
        conn.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    made = 0
    for cat, leaves in TREE.items():
        row = cur.execute("SELECT point_id FROM knowledge_point WHERE point_name=? AND subject_id=?", (cat, SUBJECT_ID)).fetchone()
        if row:
            cat_id = row[0]
        else:
            cur.execute(
                "INSERT INTO knowledge_point (point_name, subject_id, parent_id, level, sort_order, status) VALUES (?,?,?,?,?,1)",
                (cat, SUBJECT_ID, 0, 1, 1),
            )
            cat_id = cur.lastrowid
            made += 1
        order = 1
        for leaf in leaves:
            row = cur.execute("SELECT point_id FROM knowledge_point WHERE point_name=? AND subject_id=?", (leaf, SUBJECT_ID)).fetchone()
            if row:
                continue
            cur.execute(
                "INSERT INTO knowledge_point (point_name, subject_id, parent_id, level, sort_order, status) VALUES (?,?,?,?,?,1)",
                (leaf, SUBJECT_ID, cat_id, 2, order),
            )
            made += 1
            order += 1
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM knowledge_point WHERE subject_id=?", (SUBJECT_ID,)).fetchone()[0]
    print(f"[DONE] 新增 {made} 个，行测知识点共 {total} 个")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
