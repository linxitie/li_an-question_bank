"""富文本发帖（2026-11-03）：消毒白名单、XSS 剥离、contentFormat 契约。

这些用例是第 9 项的安全护栏，防止后续有人「顺手」放宽 style 白名单而不自知。
"""
from __future__ import annotations

from app.services.rich_text import sanitize_rich_text


# --------------------------- 纯函数：消毒白名单 ---------------------------

def test_allows_color_and_font_size_on_span():
    html = '<p><span style="color:#ff0000;font-size:18px">红色</span></p>'
    out = sanitize_rich_text(html, allow_inline_style=True)
    assert 'color:#ff0000' in out
    assert 'font-size:18px' in out


def test_allows_text_align_on_paragraph():
    out = sanitize_rich_text('<p style="text-align:center">居中</p>', allow_inline_style=True)
    assert 'text-align:center' in out


def test_rejects_layout_style_properties():
    """position / z-index 这类布局属性必须被剥离，否则可用来做遮罩攻击。"""
    html = '<p style="position:fixed;z-index:9999;color:#00ff00">攻击</p>'
    out = sanitize_rich_text(html, allow_inline_style=True)
    assert 'position' not in out
    assert 'z-index' not in out
    assert 'color:#00ff00' in out


def test_rejects_out_of_range_font_size():
    out = sanitize_rich_text('<span style="font-size:9999px">巨大</span>', allow_inline_style=True)
    assert 'font-size' not in out


def test_script_block_removed_with_content():
    """bleach strip=True 只剥标签，脚本正文会变成可见文字；这里要求整段消失。"""
    out = sanitize_rich_text('<script>alert(1)</script><p>正常</p>', allow_inline_style=True)
    assert 'alert(1)' not in out
    assert '<p>正常</p>' in out


def test_event_handler_and_javascript_url_removed():
    out = sanitize_rich_text(
        '<img src=x onerror="alert(1)"><a href="javascript:alert(2)">坏链接</a>',
        allow_inline_style=True,
    )
    assert 'onerror' not in out
    assert 'javascript:' not in out


def test_default_keeps_legacy_behaviour_without_style():
    """既有调用方（新闻/资料）不传 allow_inline_style，样式仍应被整段剥离。"""
    out = sanitize_rich_text('<p style="text-align:center">居中</p>')
    assert out == '<p>居中</p>'


# --------------------------- 接口：落库与契约 ---------------------------

def _create_post(client, headers, **overrides):
    payload = {
        "title": "富文本验证帖",
        "content": "<p>默认正文</p>",
        "content_format": "HTML",
        "share_type": "DISCUSSION",
        "visibility": "ALL",
    }
    payload.update(overrides)
    return client.post("/api/forum/posts", data=payload, headers=headers)


def test_html_post_is_sanitized_before_saving(client, auth_headers):
    resp = _create_post(
        client,
        auth_headers,
        content=(
            '<p style="text-align:center"><span style="color:#ff0000">红</span></p>'
            "<script>alert(1)</script>"
            '<img src=x onerror="alert(2)">'
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    content = body["content"]
    assert "color:#ff0000" in content
    assert "text-align:center" in content
    assert "script" not in content
    assert "onerror" not in content
    assert body["contentFormat"] == "HTML"


def test_text_post_keeps_content_format_text(client, auth_headers):
    resp = _create_post(client, auth_headers, content="纯文本正文", content_format="TEXT")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contentFormat"] == "TEXT"
    assert body["content"] == "纯文本正文"


def test_html_with_only_empty_tags_counts_as_empty(client, auth_headers):
    """<p><br></p> 这种「看起来有内容」的空富文本不应被当成正文。"""
    resp = _create_post(client, auth_headers, title="", content="<p><br></p>")
    assert resp.status_code in (400, 422), resp.text


def test_detail_returns_content_format(client, auth_headers):
    created = _create_post(client, auth_headers).json()
    detail = client.get(f"/api/forum/posts/{created['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["contentFormat"] == "HTML"
