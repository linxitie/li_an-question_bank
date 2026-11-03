"""robots 检查器的纯函数测试。"""

from scripts.news.check_robots import is_plain_robots


def test_plain_robots_accepts_rules_and_rejects_html():
    assert is_plain_robots("User-agent: *\nAllow: /\n")
    assert not is_plain_robots("\ufeff\n<!DOCTYPE html><html></html>")
    assert not is_plain_robots("")
