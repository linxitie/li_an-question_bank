# -*- coding: utf-8 -*-
"""RT-7 后端富文本清洗测试（信任边界 + XSS 向量）。"""
from typing import cast

from app.services.rich_text import sanitize_rich_text


def test_link_preserved_with_target_and_rel():
    out = sanitize_rich_text(
        '<p>见 <a href="https://example.com/a">链接</a></p>'
    )
    assert '<p>' in out
    assert 'href="https://example.com/a"' in out
    assert 'target="_blank"' in out
    assert 'rel="noopener noreferrer"' in out


def test_mailto_preserved():
    out = sanitize_rich_text('<a href="mailto:a@b.com">邮件</a>')
    assert 'href="mailto:a@b.com"' in out


def test_javascript_href_stripped():
    out = sanitize_rich_text('<a href="javascript:alert(1)">x</a>')
    assert 'javascript:' not in out.lower()
    assert '<a' in out


def test_data_text_html_stripped():
    out = sanitize_rich_text(
        '<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>'
    )
    assert 'data:text/html' not in out.lower()
    assert 'href=' not in out


def test_static_relative_image_preserved():
    out = sanitize_rich_text(
        '<img src="/static/question-groups/12/a.png" alt="材料">'
    )
    assert 'src="/static/question-groups/12/a.png"' in out
    assert 'alt="材料"' in out


def test_javascript_image_src_stripped():
    out = sanitize_rich_text('<img src="javascript:alert(1)">')
    assert 'javascript:' not in out.lower()


def test_script_iframe_and_event_handlers_stripped():
    out = sanitize_rich_text(
        '<script>alert(1)</script>'
        '<iframe src="https://evil.example"></iframe>'
        '<img src="/static/x.png" onerror="alert(1)">'
        '<p onclick="alert(2)">文字</p>'
    )
    lowered = out.lower()
    assert '<script' not in lowered
    assert '<iframe' not in lowered
    assert 'onerror' not in lowered
    assert 'onclick' not in lowered
    assert '文字' in out


def test_table_and_list_preserved():
    out = sanitize_rich_text(
        '<table><thead><tr><th>列</th></tr></thead>'
        '<tbody><tr><td>值</td></tr></tbody></table>'
        '<ul><li>一</li></ul><ol><li>二</li></ol>'
    )
    for tag in ('<table>', '<thead>', '<tbody>', '<tr>', '<th>', '<td>',
                '<ul>', '<ol>', '<li>'):
        assert tag in out


def test_span_class_kept_but_style_stripped():
    out = sanitize_rich_text('<span class="ok" style="color:red">x</span>')
    assert 'class="ok"' in out
    assert 'style=' not in out


def test_empty_none_and_repeated_sanitize_are_safe():
    assert sanitize_rich_text('') == ''
    assert sanitize_rich_text(cast(str, None)) == ''
    once = sanitize_rich_text('<a href="https://x.example">x</a>')
    assert sanitize_rich_text(once) == once
