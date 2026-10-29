# -*- coding: utf-8 -*-
"""S2.5 测试：6 档等级称号播种（badge_title）。

用户批复：见习/入门/熟练/精通/大师/宗师，解锁等级 1/5/10/20/30/50。
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.init_badge_titles import DB, TITLES  # noqa: E402

EXPECTED = [("见习", 1), ("入门", 5), ("熟练", 10), ("精通", 20), ("大师", 30), ("宗师", 50)]


class TestTitleRows:
    def test_六档且等级正确(self):
        got = [(name, level) for _code, name, _d, level, _s in TITLES]
        assert got == EXPECTED, f"应为 {EXPECTED}，实际 {got}"

    def test_code唯一(self):
        codes = [c for c, *_ in TITLES]
        assert len(set(codes)) == 6, f"code 重复：{codes}"

    def test_code前缀规范(self):
        for code, *_ in TITLES:
            assert code.startswith("title_level_"), code

    def test_sort_order递增(self):
        sorts = [s for *_, s in TITLES]
        assert sorts == sorted(sorts) and len(set(sorts)) == 6


@pytest.fixture()
def db_conn():
    if not os.path.exists(DB):
        pytest.skip("数据库不存在")
    con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
    try:
        yield con
    finally:
        con.close()


class TestDatabase:
    def test_库内六档齐全且等级正确(self, db_conn):
        rows = db_conn.execute(
            "SELECT name, unlock_level FROM badge_title WHERE title_code LIKE 'title_level%' "
            "ORDER BY unlock_level").fetchall()
        assert rows == EXPECTED, f"库内等级称号应为 {EXPECTED}，实际 {rows}"

    def test_code无重复(self, db_conn):
        dup = db_conn.execute(
            "SELECT COUNT(*) FROM (SELECT title_code, COUNT(*) c FROM badge_title "
            "GROUP BY title_code HAVING c > 1)").fetchone()[0]
        assert dup == 0

    def test_商城称号未被破坏(self, db_conn):
        names = {r[0] for r in db_conn.execute(
            "SELECT name FROM badge_title WHERE title_code NOT LIKE 'title_level%'")}
        assert {"砺安之星", "公考达人", "学习之王"} <= names, names

    def test_称号总数至少9(self, db_conn):
        n = db_conn.execute("SELECT COUNT(*) FROM badge_title").fetchone()[0]
        assert n >= 9, f"6 等级 + 3 商城 应 ≥9，实际 {n}"
