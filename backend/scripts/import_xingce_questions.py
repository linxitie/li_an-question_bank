# 行测题本 → question_bank 导入器（默认 dry-run，不写库）
#
# 前置：先跑 backend/scripts/extract_xingce_dryrun.py 生成 backend/data/tmp/*.json
#
# 用法：
#   python backend/scripts/import_xingce_questions.py            # 预演，只打印计划
#   python backend/scripts/import_xingce_questions.py --commit   # 真正写库（会先备份）
#
# 红线遵守：
#   - R10：写库前用 sqlite3.backup() 备份，不用 shutil.copy2
#   - 幂等：按题干哈希去重，重复执行不会产生副本
#   - 只增不改：不动既有 0 行以外的数据，不删任何行
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"
SRC = ROOT / "backend" / "data" / "tmp"

SUBJECT_ID = 1          # question_subject: 1=行测
CREATOR_ID = 2          # 现有 admin 账号
TYPES = [
    # (type_name, type_code, is_objective, sort_order)
    ("单选题", "single_choice", 1, 1),
    ("多选题", "multi_choice", 1, 2),
    ("判断题", "judge", 1, 3),
]
YEAR_RE = re.compile(r"(20\d{2})")


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def qhash(stem: str, options: dict) -> str:
    raw = norm(stem) + "|" + "|".join(sorted(norm(v) for v in options.values()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_items() -> list[dict]:
    files = sorted(SRC.glob("*.json"))
    out: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        year = int(YEAR_RE.search(f.stem).group(1)) if YEAR_RE.search(f.stem) else None
        for d in data:
            if len(d.get("options", {})) != 4:
                continue
            # 跨页污染：选项过长整题丢弃
            if any(len(v) > 120 for v in d["options"].values()):
                continue
            out.append({"qno": d["qno"], "stem": d["stem"], "options": d["options"],
                        "year": year, "source": f.stem[:180]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="真正写库（默认只预演）")
    args = ap.parse_args()

    if not DB.exists():
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1
    items = load_items()
    if not items:
        print("[FAIL] backend/data/tmp 下没有可用 JSON，请先跑 extract_xingce_dryrun.py")
        return 1

    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute("SELECT substr(question_content,1,120) FROM question_bank")}
    seen: set[str] = set()
    plan = []
    for it in items:
        h = qhash(it["stem"], it["options"])
        key = norm(it["stem"])[:120]
        if key in existing or h in seen:
            continue
        seen.add(h)
        plan.append(it)

    print(f"[PLAN] 候选 {len(items)} 题，去重后待写入 {len(plan)} 题（现有 {len(existing)} 题）")
    for it in plan[:3]:
        print(f"   · 第{it['qno']}题 {it['stem'][:40]}… 选项 {len(it['options'])} 个 年份 {it['year']}")

    if not args.commit:
        print("[DRY-RUN] 未写库。确认无误后加 --commit")
        conn.close()
        return 0

    backup = DB.with_suffix(f".db.bak_import_{datetime.now():%Y%m%d_%H%M%S}")
    dst = sqlite3.connect(str(backup))
    with dst:
        conn.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    # 题型补齐（question_type 当前为空）
    type_ids: dict[str, int] = {}
    for name, code, obj, order in TYPES:
        row = cur.execute("SELECT type_id FROM question_type WHERE type_code=?", (code,)).fetchone()
        if row:
            type_ids[code] = row[0]
        else:
            cur.execute(
                "INSERT INTO question_type (type_name, type_code, subject_id, is_objective, sort_order) VALUES (?,?,?,?,?)",
                (name, code, SUBJECT_ID, obj, order),
            )
            type_ids[code] = cur.lastrowid
    print(f"[TYPE] 题型映射 {type_ids}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for it in plan:
        cur.execute(
            """INSERT INTO question_bank
               (subject_id, type_id, question_content, options, answer, answer_analysis,
                difficulty, year, source, creator_id, audit_status, status, create_time, update_time,
                xingce_subcategory, question_number)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                SUBJECT_ID, type_ids["single_choice"], it["stem"],
                json.dumps(it["options"], ensure_ascii=False), "", "",
                3, it["year"], it["source"], CREATOR_ID, 1, 1, now, now,
                "无", str(it["qno"]),
            ),
        )
        inserted += 1
    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM question_bank").fetchone()[0]
    print(f"[DONE] 写入 {inserted} 题，题库现有 {total} 题")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
