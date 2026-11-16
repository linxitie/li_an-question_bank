# 构建知识图谱骨架（模块7 · P6）
# 数据源: backend/data/xingce_kao_points.json（85 份行测真题、479 个考点标记、370 个词根）
# 产出: question_subject 行测科目 + knowledge_point 三级树（科目 -> 模块 -> 考点/二级考点）
# 幂等: 以 (subject_id, parent_id, point_name) 去重，可重复执行
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # backend/
DB = ROOT / "data" / "question_bank.db"
SRC = ROOT / "data" / "xingce_kao_points.json"

SUBJECT_NAME = "行测"
SUBJECT_CODE = "XC"

# 真题标记里出现的大类 -> 标准模块名
MODULE_ALIASES = {
    "言语理解与表达": "言语理解与表达",
    "言语理解": "言语理解与表达",
    "判断推理": "判断推理",
    "数量关系": "数量关系",
    "数量": "数量关系",
    "资料分析": "资料分析",
    "资料": "资料分析",
    "常识判断": "常识判断",
    "常识": "常识判断",
}


def ensure_subject(cur) -> int:
    row = cur.execute(
        "SELECT subject_id FROM question_subject WHERE subject_code = ?", (SUBJECT_CODE,)
    ).fetchone()
    if row:
        return int(row[0])
    cur.execute(
        "INSERT INTO question_subject (subject_name, subject_code, description, sort_order, status) VALUES (?,?,?,?,1)",
        (SUBJECT_NAME, SUBJECT_CODE, "行政职业能力测验", 90),
    )
    return int(cur.lastrowid)


def upsert_point(cur, subject_id: int, parent_id: int, level: int, name: str, desc: str, order: int) -> int:
    row = cur.execute(
        "SELECT point_id FROM knowledge_point WHERE subject_id=? AND IFNULL(parent_id,0)=? AND point_name=?",
        (subject_id, parent_id, name),
    ).fetchone()
    if row:
        cur.execute("UPDATE knowledge_point SET level=?, description=? WHERE point_id=?", (level, desc[:500], row[0]))
        return int(row[0])
    cur.execute(
        "INSERT INTO knowledge_point (point_name, subject_id, parent_id, level, description, sort_order, status) VALUES (?,?,?,?,?,?,1)",
        (name, subject_id, parent_id, level, desc[:500], order),
    )
    return int(cur.lastrowid)


def main() -> int:
    if not SRC.exists():
        print(f"[SKIP] 考点数据不存在: {SRC}")
        return 1
    data = json.loads(SRC.read_text(encoding="utf-8"))
    items = data.get("items") or []
    meta = data.get("meta") or {}
    print(f"[SRC] 考点 {len(items)} 个，来源真题 {meta.get('papers')} 份，标记 {meta.get('markers_total')} 处")

    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    subject_id = ensure_subject(cur)
    print(f"[SUBJECT] {SUBJECT_NAME} subject_id={subject_id}")

    # 1) 先建模块层
    modules = {}
    module_order = 0
    for name in MODULE_ALIASES.values():
        if name in modules:
            continue
        module_order += 1
        modules[name] = upsert_point(cur, subject_id, 0, 1, name, f"{SUBJECT_NAME}模块：{name}", module_order)
    default_module = upsert_point(cur, subject_id, 0, 1, "综合考点", "未归类的行测考点", 99)

    # 2) 再挂考点
    created = 0
    linked = 0
    for idx, it in enumerate(items, start=1):
        token = (it.get("token") or "").strip()
        if not token:
            continue
        sections = it.get("sections") or {}
        target = default_module
        for sec in sections.keys():
            mapped = MODULE_ALIASES.get(sec)
            if mapped:
                target = modules[mapped]
                break
        tier = it.get("freq_tier") or "rare"
        count = int(it.get("count") or 0)
        paths = "/".join(it.get("path") or [])
        desc = f"频次 {count}（{tier}）；路径 {paths}；涉及试卷 {len(it.get('papers') or [])} 份"
        upsert_point(cur, subject_id, target, 2, token, desc, idx)
        created += 1
        if target != default_module:
            linked += 1

    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM knowledge_point WHERE subject_id=?", (subject_id,)).fetchone()[0]
    mod_cnt = cur.execute("SELECT COUNT(*) FROM knowledge_point WHERE subject_id=? AND level=1", (subject_id,)).fetchone()[0]
    pnt_cnt = cur.execute("SELECT COUNT(*) FROM knowledge_point WHERE subject_id=? AND level=2", (subject_id,)).fetchone()[0]
    print(f"[DONE] 行测知识点合计 {total}（模块 {mod_cnt} / 考点 {pnt_cnt}），其中 {linked} 个挂到标准模块")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
