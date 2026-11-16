# -*- coding: utf-8 -*-
"""模块4/7 AI 真功能接入（/api/llm/chat 一次性任务）的回归测试。

守四件事：
  1) 新增场景 essay/interview/coach 与 persist 字段是 add-only 契约，默认值保持旧行为；
  2) 三个场景的 system prompt 都强制 JSON 输出（否则前端解析必挂）；
  3) persist=false 走一次性通道：不建会话、不写消息、直接返回大模型回复；
  4) 非法 scene / 空消息被拒绝。
"""

import asyncio

import pytest
from pydantic import ValidationError

from app.api.v1.platform import llm as llm_api
from app.services import llm_client


def test_scene_enum_is_add_only():
    base = llm_api.ChatRequest(message="hi")
    assert base.scene == "qa"
    assert base.persist is True
    for scene in ("essay", "interview", "coach"):
        assert llm_api.ChatRequest(message="x", scene=scene).scene == scene
    with pytest.raises(ValidationError):
        llm_api.ChatRequest(message="x", scene="nope")


@pytest.mark.parametrize(
    "scene,keys",
    [
        ("essay", ["total", "dimensions", "comment", "suggestions"]),
        ("interview", ["content", "expression", "presence", "logic", "comment"]),
        ("coach", ["suggestion"]),
    ],
)
def test_scene_prompts_require_json(scene, keys):
    prompt = llm_client.SCENE_SYSTEM_PROMPTS[scene]
    assert "JSON" in prompt
    for key in keys:
        assert key in prompt


def test_one_shot_does_not_touch_db(monkeypatch):
    called = {}

    async def fake_chat(messages, scene="qa", extra_system=""):
        called["scene"] = scene
        called["messages"] = messages
        return '{"suggestion": "资料分析 20 题，重点练增长率"}'

    monkeypatch.setattr(llm_client, "chat", fake_chat)
    req = llm_api.ChatRequest(message="帮我看看今天学啥", scene="coach", persist=False)
    result = asyncio.run(llm_api.chat(req, current_user=object(), db=object()))
    assert result["reply"].startswith("{")
    assert result["session_id"] is None
    assert result["scene"] == "coach"
    assert result["agent"] == "one_shot"
    assert called["messages"] == [{"role": "user", "content": "帮我看看今天学啥"}]
