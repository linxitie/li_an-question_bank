# -*- coding: utf-8 -*-
"""初始化精选徽章表 + 快照估算标记（幂等）。"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
DB = r"C:\Users\35709\OneDrive\Desktop\题库\li_an-question_bank\backend\data\question_bank.db"

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL")

cols = {r[1] for r in con.execute("PRAGMA table_info(user_achievement)")}
if "snapshot_estimated" not in cols:
    con.execute("ALTER TABLE user_achievement ADD COLUMN snapshot_estimated INTEGER DEFAULT 0")
    print("补列 user_achievement.snapshot_estimated")

tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if "user_badge_top" not in tables:
    con.execute("""
        CREATE TABLE user_badge_top (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            badge_kind VARCHAR(16) NOT NULL,
            badge_id INTEGER NOT NULL,
            sort INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uk_user_badge_top UNIQUE (user_id, badge_kind, badge_id)
        )""")
    con.execute("CREATE INDEX idx_user_badge_top ON user_badge_top(user_id, sort)")
    print("建表 user_badge_top")

# 历史 20 条快照是回填的，统一标为估算（已标的不重复动）
n = con.execute(
    "UPDATE user_achievement SET snapshot_estimated=1 "
    "WHERE tier_snapshot IS NOT NULL AND COALESCE(snapshot_estimated,0)=0").rowcount
con.commit()
print("标记为估算的快照条数:", n)

print("校验：",
      "snapshot_estimated=1 共",
      con.execute("SELECT COUNT(*) FROM user_achievement WHERE snapshot_estimated=1").fetchone()[0],
      "条；user_badge_top 行数",
      con.execute("SELECT COUNT(*) FROM user_badge_top").fetchone()[0])
con.close()
