# -*- coding: utf-8 -*-
"""S1 测试：徽章命名词库（badge_name_bank）播种。

覆盖：
- 词表规模与唯一性（7 类 × 12 = 84，且 (name, category) 无重复）
- 名字合法性（非空、长度合理、由 prefix+body+suffix 拼成）
- 库内状态（已播种、无空名、无重复）——无库时 skip
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.init_badge_names import DB, PREFIX_SCORE, build_rows  # noqa: E402


class TestBuildRows:
    def test_total_is_84(self):
        rows = build_rows()
        assert len(rows) == 84, f"应为 7 类 × 12 = 84 条，实际 {len(rows)}"

    def test_每类12条(self):
        rows = build_rows()
        per_cat: dict[str, int] = {}
        for r in rows:
            per_cat[r[1]] = per_cat.get(r[1], 0) + 1
        assert len(per_cat) == 7, f"应有 7 个类别，实际 {list(per_cat)}"
        assert all(v == 12 for v in per_cat.values()), f"每类应 12 条，实际 {per_cat}"

    def test_无重复名(self):
        rows = build_rows()
        keys = [(r[0], r[1]) for r in rows]
        assert len(set(keys)) == len(keys), "存在重复的 (name, category)"

    def test_名字由三段拼成且非空(self):
        for name, cat, pre, body, suf, _score, _src, _used, _seed in build_rows():
            assert name == f"{pre}{body}{suf}", f"{name} 不是 prefix+body+suffix 拼接"
            assert name.strip() and len(name) <= 12, f"名字异常：{name!r}"
            assert cat in ("数量", "坚持", "正确率", "综合", "社交", "错题", "成长")

    def test_score符合前缀排序(self):
        rows = build_rows()
        # 同一类别内，第一种前缀的 score 应高于第二种
        by_cat: dict[str, dict[str, int]] = {}
        for name, cat, pre, _b, _s, score, _src, _u, _seed in rows:
            by_cat.setdefault(cat, {}).setdefault(pre, score)
        for cat, pre_map in by_cat.items():
            top = PREFIX_SCORE[0]
            assert max(pre_map.values()) == top, f"{cat} 最高分应为 {top}"

    def test_style_seed在范围内(self):
        for r in build_rows():
            assert 0 <= r[8] < 1000


@pytest.fixture()
def db_conn():
    if not os.path.exists(DB):
        pytest.skip("数据库不存在，跳过库内断言")
    con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
    try:
        yield con
    finally:
        con.close()


class TestDatabase:
    def test_已播种至少84条(self, db_conn):
        n = db_conn.execute("SELECT COUNT(*) FROM badge_name_bank").fetchone()[0]
        assert n >= 84, f"badge_name_bank 应已播种 ≥84 条，实际 {n}"

    def test_无空名(self, db_conn):
        empty = db_conn.execute(
            "SELECT COUNT(*) FROM badge_name_bank WHERE TRIM(name)=''").fetchone()[0]
        assert empty == 0

    def test_无重复名与类别(self, db_conn):
        dup = db_conn.execute(
            "SELECT COUNT(*) FROM (SELECT name, category, COUNT(*) c "
            "FROM badge_name_bank GROUP BY name, category HAVING c > 1)").fetchone()[0]
        assert dup == 0

    def test_七类都有词(self, db_conn):
        cats = {r[0] for r in db_conn.execute(
            "SELECT DISTINCT category FROM badge_name_bank")}
        assert cats == {"数量", "坚持", "正确率", "综合", "社交", "错题", "成长"}, cats

    def test_used初始为0(self, db_conn):
        used = db_conn.execute(
            "SELECT COUNT(*) FROM badge_name_bank WHERE used != 0").fetchone()[0]
        assert used == 0, f"初始 used 应全为 0，实际非 0 有 {used} 条"
