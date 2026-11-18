"""知识库落位：文件夹用学号 + 注册即建库（2026-11-18）。

覆盖：
1. 知识库目录名用学号（user_no），而不是昵称；
2. 注册成功后调用导出器（失败不影响注册）；
3. 零节点学生也会生成目录（用真实库副本验证，避开内存库限制）。
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.services import kg_vault_export


def test_vault_dir_named_by_user_no():
    user = {"user_id": 7, "username": "abc", "user_no": "202516001", "nickname": "闲者"}
    assert kg_vault_export.user_dir_name(user) == "202516001"


def test_register_calls_vault_export(monkeypatch, client):
    calls = []

    def fake_export(username, out=None):
        calls.append(username)
        return {"users": 0, "notes": 0}

    monkeypatch.setattr(kg_vault_export, "export_user_by_name", fake_export)

    res = client.post("/api/auth/register", json={
        "username": "vaultprobe01",
        "password": "probe123456",
        "phone": "13900001111",
        "user_no": "202599901",
        "user_type": "student",
    })
    assert res.status_code == 200, res.text
    assert calls == ["vaultprobe01"]


def test_register_survives_vault_export_failure(monkeypatch, client):
    def boom(username, out=None):
        raise RuntimeError("磁盘写满")

    monkeypatch.setattr(kg_vault_export, "export_user_by_name", boom)

    res = client.post("/api/auth/register", json={
        "username": "vaultprobe02",
        "password": "probe123456",
        "phone": "13900002222",
        "user_no": "202599902",
        "user_type": "student",
    })
    assert res.status_code == 200, res.text


def test_export_creates_dir_for_student_without_nodes(tmp_path):
    """零节点学生也要有 用户/<学号>/ 目录（空态看板），用真实库副本验证。"""
    src = kg_vault_export.default_db_path()
    assert src.exists(), "需要真实库文件做副本"
    tmp_db = tmp_path / "copy.sqlite"
    with sqlite3.connect(str(src)) as s, sqlite3.connect(str(tmp_db)) as d:
        s.backup(d)

    with sqlite3.connect(str(tmp_db)) as conn:
        conn.execute(
            "INSERT INTO sys_user (username, password, phone, user_no, user_type, role_level, status, is_deleted) "
            "VALUES (?, ?, ?, ?, 'student', 0, 1, 0)",
            ("emptystudent01", "x", "13900003333", "202599903"),
        )
        conn.commit()

    vault = tmp_path / "vault"
    result = kg_vault_export.export_vault(db_path=tmp_db, out=vault)
    assert result["users"] >= 2

    user_dir = vault / "用户" / "202599903"
    assert user_dir.is_dir(), "没有任何图谱节点的学生也必须有自己的库目录"
    assert (user_dir / ".obsidian" / "app.json").is_file()
    board = (user_dir / "弱项看板.md").read_text(encoding="utf-8")
    assert "还没有学习数据" in board
    readme = (user_dir / "README.md").read_text(encoding="utf-8")
    assert "202599903" in readme
