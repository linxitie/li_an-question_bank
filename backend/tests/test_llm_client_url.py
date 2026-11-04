"""LLM endpoint URL 拼接的回归测试。"""

from app.services import llm_client


def test_chat_completions_url_accepts_full_endpoint(monkeypatch):
    monkeypatch.setattr(
        llm_client.settings, "LLM_API_URL", "https://api.deepseek.com/chat/completions"
    )
    assert llm_client._chat_completions_url() == "https://api.deepseek.com/chat/completions"


def test_chat_completions_url_accepts_base_url(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_API_URL", "https://api.deepseek.com/v1/")
    assert llm_client._chat_completions_url() == "https://api.deepseek.com/v1/chat/completions"
