"""llm_client 配置与鉴权错误的回归测试。

背景（2026-10-31）：学习计划 `POST /api/plan/generate` 返回 503，前端提示
「大模型返回错误（401）」。根因是后端读不到密钥（根 .env 用 DEEPSEEK_API_KEY、
后端只认 LLM_API_KEY 且只读 backend/.env），于是带 `Bearer None` 打上游。
本测试锁住三件事：
1. 没有密钥时立刻报可执行的配置错误（llm_no_key），不再把请求打出去；
2. 上游 401/403 归为鉴权错误（llm_unauthorized），不再混同为通用错误；
3. 有密钥时 Authorization 头必须真实携带。
"""

import asyncio

import pytest

from app.services import llm_client


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = b"{}"

    def json(self):
        return self._payload


class _FakeClient:
    """替身 httpx.AsyncClient：返回预置响应并记录请求头。"""

    last_headers: dict = {}
    last_url: str = ""
    status_code: int = 200
    payload: dict | None = None

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        _FakeClient.last_headers = headers or {}
        _FakeClient.last_url = url
        return _FakeResponse(_FakeClient.status_code, _FakeClient.payload)


def _call_plan():
    return asyncio.run(llm_client.chat_plan("ping"))


def test_missing_key_raises_config_error(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", None)

    with pytest.raises(llm_client.LLMClientError) as exc:
        _call_plan()

    assert exc.value.code == "llm_no_key"
    assert "LLM_API_KEY" in exc.value.message


def test_placeholder_key_treated_as_missing(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", "<负责人填写>")

    with pytest.raises(llm_client.LLMClientError) as exc:
        _call_plan()

    assert exc.value.code == "llm_no_key"


def test_upstream_401_maps_to_unauthorized(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", "sk-test-key")
    _FakeClient.status_code = 401
    _FakeClient.payload = None
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", _FakeClient())

    with pytest.raises(llm_client.LLMClientError) as exc:
        _call_plan()

    assert exc.value.code == "llm_unauthorized"
    assert "401" in exc.value.message


def test_valid_key_is_sent_in_header(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", "sk-test-key")
    _FakeClient.status_code = 200
    _FakeClient.payload = {"choices": [{"message": {"content": "ok"}}]}
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", _FakeClient())

    assert _call_plan() == "ok"
    assert _FakeClient.last_headers["Authorization"] == "Bearer sk-test-key"
