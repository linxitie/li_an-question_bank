"""AI 标题开关 v4（2026-11-04）：suggest 接口、开关落库、手改不冒充 AI。

LLM 全部 mock，不产生真实调用。
"""
from __future__ import annotations

import pytest

from app.services import forum_title_ai as ai


def _create_post(client, headers, **overrides):
    payload = {
        "title": "",
        "content": "推荐两本行测备考资料，粉笔的题目更新一些",
        "content_format": "TEXT",
        "visibility": "ALL",
    }
    payload.update(overrides)
    return client.post("/api/forum/posts", data=payload, headers=headers)


def test_switch_off_skips_generation(client, auth_headers):
    """关闭开关后即便标题为空，也不应被标记为 AI 生成。"""
    resp = _create_post(client, auth_headers, ai_title_enabled="false")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "(无标题)"
    assert body["aiTitle"] is False
    assert body["aiTitleEnabled"] is False


def test_switch_default_on(client, auth_headers):
    resp = _create_post(client, auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["aiTitleEnabled"] is True


def test_title_from_ai_marks_flag(client, auth_headers):
    """用户接受了模型建议且没手改 → 标题标「AI生成」。"""
    resp = _create_post(
        client,
        auth_headers,
        title="行测资料推荐",
        title_from_ai="true",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["aiTitle"] is True
    assert body["title"] == "行测资料推荐"


def test_manual_title_is_not_marked_ai(client, auth_headers):
    resp = _create_post(client, auth_headers, title="我自己起的标题")
    assert resp.status_code == 200, resp.text
    assert resp.json()["aiTitle"] is False


@pytest.mark.asyncio
async def test_suggest_returns_title(client, auth_headers, monkeypatch):
    async def fake_chat(*args, **kwargs):
        return "行测资料选择"

    monkeypatch.setattr(ai, "chat", fake_chat)
    resp = client.post(
        "/api/forum/ai-title/suggest",
        json={"content": "推荐两本行测备考资料，粉笔更新一些", "content_format": "TEXT"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "行测资料选择"
    assert body["reason"] is None


def test_suggest_rejects_short_content(client, auth_headers):
    resp = client.post(
        "/api/forum/ai-title/suggest",
        json={"content": "。。。", "content_format": "TEXT"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] is None
    assert body["reason"] == "no_content"


def test_suggest_requires_login(client):
    resp = client.post("/api/forum/ai-title/suggest", json={"content": "推荐两本行测备考资料"})
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_suggest_rate_limit(client, auth_headers, monkeypatch):
    """连续请求超过配额后应返回 429（保护 token）。"""
    from app.api.v1.community import forum as forum_module

    async def fake_chat(*args, **kwargs):
        return "限流测试标题"

    monkeypatch.setattr(ai, "chat", fake_chat)
    monkeypatch.setattr(forum_module, "AI_SUGGEST_LIMIT", 3)
    forum_module._AI_SUGGEST_HITS.clear()

    for _ in range(3):
        ok = client.post(
            "/api/forum/ai-title/suggest",
            json={"content": "推荐两本行测备考资料，内容足够长"},
            headers=auth_headers,
        )
        assert ok.status_code == 200, ok.text

    blocked = client.post(
        "/api/forum/ai-title/suggest",
        json={"content": "推荐两本行测备考资料，内容足够长"},
        headers=auth_headers,
    )
    assert blocked.status_code == 429, blocked.text
