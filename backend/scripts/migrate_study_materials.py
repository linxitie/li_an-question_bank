"""备考资料三表幂等迁移。用法：
    python backend/scripts/migrate_study_materials.py --dry-run   # 仅打印动作
    python backend/scripts/migrate_study_materials.py             # 执行（可安全重复运行）

前置约束：study_material 若已有数据将拒绝执行（本迁移按"空表重建"设计，
见 solve_problems_files/备考资料模块优化设计方案_v2.2.md 第三章）。
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "question_bank.db"

STUDY_MATERIAL_DDL = """
CREATE TABLE study_material (
    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject VARCHAR(20) NOT NULL,
    type VARCHAR(20) NOT NULL,
    category VARCHAR(50),
    title VARCHAR(200) NOT NULL,
    summary VARCHAR(500),
    content TEXT,
    card_front VARCHAR(200),
    card_back TEXT,
    cover_image VARCHAR(500),
    video_id INTEGER,
    duration INTEGER DEFAULT 0,
    read_time INTEGER DEFAULT 0,
    difficulty TINYINT DEFAULT 1,
    badge VARCHAR(20),
    sort_order INTEGER DEFAULT 0,
    status TINYINT DEFAULT 1,
    view_count INTEGER DEFAULT 0,
    study_count INTEGER DEFAULT 0,
    creator_id BIGINT REFERENCES sys_user(user_id),
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
)"""

PROGRESS_DDL = """CREATE TABLE IF NOT EXISTS user_material_progress (
    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL REFERENCES sys_user(user_id),
    material_id INTEGER NOT NULL REFERENCES study_material(material_id),
    status SMALLINT DEFAULT 0,
    progress_percent FLOAT DEFAULT 0,
    is_favorite BOOLEAN DEFAULT 0,
    completed_at DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, material_id)
)"""

IMPORT_DDL = """CREATE TABLE IF NOT EXISTS material_import_record (
    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(10),
    file_size BIGINT,
    parse_mode VARCHAR(20),
    parse_status VARCHAR(20) DEFAULT 'pending',
    parse_result TEXT,
    error_message VARCHAR(1000),
    uploader_id BIGINT REFERENCES sys_user(user_id),
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
)"""

IDX_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_subject_type ON study_material(subject, type)",
    "CREATE INDEX IF NOT EXISTS idx_status_sort ON study_material(status, sort_order)",
    "CREATE INDEX IF NOT EXISTS idx_progress_user ON user_material_progress(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_status ON material_import_record(parse_status)",
]


def table_exists(cur, name):
    return cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="仅打印将要执行的动作")
    args = ap.parse_args()
    if not DB.exists():
        sys.exit(f"[ABORT] db not found: {DB}")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    actions = [("PRAGMA journal_mode=WAL",)]
    if table_exists(cur, "study_material"):
        n = cur.execute("SELECT COUNT(*) FROM study_material").fetchone()[0]
        if n > 0:
            sys.exit(f"[ABORT] study_material 已有 {n} 行！空表假设不成立，人工评估后再改脚本。")
        actions.append(("DROP TABLE study_material",))
    actions.append((STUDY_MATERIAL_DDL,))
    if not table_exists(cur, "user_material_progress"):
        actions.append((PROGRESS_DDL,))
    if not table_exists(cur, "material_import_record"):
        actions.append((IMPORT_DDL,))
    actions += [(d,) for d in IDX_DDL]

    print(f"[PLAN] {len(actions)} 个动作 @ {DB}")
    for a in actions:
        print("  -", a[0][:90].replace("\n", " "))
    if args.dry_run:
        print("[DRY-RUN] 未执行")
        return
    for (sql,) in actions:
        con.execute(sql)
    con.commit()
    for t in ("study_material", "user_material_progress", "material_import_record"):
        assert table_exists(cur, t), f"missing {t}"
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    print(f"[DONE] 三表就绪, journal_mode={mode}")


if __name__ == "__main__":
    main()
