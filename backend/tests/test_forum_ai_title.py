"""AI 标题（2026-11-03 第 3 轮）：清洗规则、判定条件、无密钥降级、回填接口。

LLM 调用全部被 monkeypatch，测试不产生真实请求、不消耗 token。
"""
from __future__ import annotations

import pytest

from app.services import forum_title_ai as ai
from app.services.llm_client import LLMClientError


# --------------------------- 清洗 ---------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('**标题：** "学习心得分享"。', "学习心得分享"),
        ("「行测资料推荐」", "行测资料推荐"),
        ("标题: 备考时间规划\n（以下是解释）", "备考时间规划"),
        ("  前后空白  ", "前后空白"),
        ("", ""),
    ],
)
def test_clean_title(raw, expected):
    assert ai.clean_title(raw) == expected


def test_clean_title_truncates_long_output():
    out = ai.clean_title("一" * 50)
    assert len(out) <= ai.IDEAL_TITLE_LEN


# --------------------------- 判定 ---------------------------

def test_needs_ai_title_for_empty_title_with_body():
    assert ai.needs_ai_title("(无标题)", "<p>推荐两本行测备考资料</p>") is True
    assert ai.needs_ai_title("", "<p>推荐两本行测备考资料</p>") is True


def test_does_not_touch_existing_title():
    assert ai.needs_ai_title("已有标题", "<p>正文</p>") is False


def test_needs_ai_title_requires_real_body():
    assert ai.needs_ai_title("", "<p><br></p>") is False
    assert ai.needs_ai_title("", "[[sticker:http://x]]") is False


def test_needs_ai_title_ignores_emoji_and_punctuation_only_body():
    """纯表情/纯标点的正文无法概括标题，不应触发模型调用（省钱且避免垃圾标题）。"""
    assert ai.needs_ai_title("(无标题)", "😄😍🤨🤔😐🙂") is False
    assert ai.needs_ai_title("(无标题)", "。。。。。。。") is False
    assert ai.needs_ai_title("(无标题)", "<p>。。</p>") is False


def test_needs_ai_title_accepts_meaningful_body():
    assert ai.needs_ai_title("", "推荐几本公安联考行测的备考资料") is True


def test_strip_html_removes_tags_and_stickers():
    assert ai.strip_html("<p>a [[sticker:http://x]] b</p>") == "a b"


# --------------------------- 生成（mock LLM）---------------------------

@pytest.mark.asyncio
async def test_generate_returns_cleaned_title(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return '"行测资料推荐"'

    monkeypatch.setattr(ai, "chat", fake_chat)
    assert await ai.generate_forum_title("<p>推荐几本行测资料</p>") == "行测资料推荐"


@pytest.mark.asyncio
async def test_generate_returns_none_when_llm_unavailable(monkeypatch):
    async def boom(*args, **kwargs):
        raise LLMClientError("未配置大模型密钥")

    monkeypatch.setattr(ai, "chat", boom)
    assert await ai.generate_forum_title("<p>正文</p>") is None


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_body():
    assert await ai.generate_forum_title("<p><br></p>") is None


# --------------------------- 回填接口 ---------------------------

def test_backfill_dry_run_counts_candidates(client, admin_headers):
    resp = client.post(
        "/api/admin/forum/ai-titles/backfill?limit=5&dry_run=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dryRun"] is True
    assert body["processed"] == 0
    assert body["generated"] == 0


def test_backfill_requires_admin(client, auth_headers):
    resp = client.post("/api/admin/forum/ai-titles/backfill?limit=1", headers=auth_headers)
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_backfill_generates_title_and_sets_flag(client, admin_headers, auth_headers, monkeypatch):
    """种一条无标题帖 → 回填 → 标题被填上且 ai_title=1。"""

    async def fake_chat(*args, **kwargs):
        return "AI回填测试标题"

    monkeypatch.setattr(ai, "chat", fake_chat)

    created = client.post(
        "/api/forum/posts",
        data={"title": "", "content": "这是一段用于回填的正文内容", "content_format": "TEXT", "visibility": "ALL"},
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    post_id = created.json()["id"]

    resp = client.post("/api/admin/forum/ai-titles/backfill?limit=20", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["generated"] >= 1

    detail = client.get(f"/api/forum/posts/{post_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "AI回填测试标题"
    assert body["aiTitle"] is True
