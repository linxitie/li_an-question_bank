"""后端富文本信任边界（RT-7）。

所有**写路径**落库前必须经过 :func:`sanitize_rich_text`：

* 只保留展示必需的标签（段落/表格/列表/代码/图片/链接等）；
* 属性白名单最小化 —— `a` 仅 href/title/target/rel，`img` 仅 src/alt/title，
  `span` 仅 class；`style` 与全部 `on*` 事件一律剥离；
* 协议白名单 http/https/mailto，`javascript:`、`data:text/html` 被移除；
  相对路径（`/static/...`、`#anchor`）没有 scheme，原样保留；
* `<a>` 统一补 `target="_blank"` + `rel="noopener noreferrer"`（RT-A1）。

清洗只做「信任边界」这一件事，不做 Markdown 转换、不改文案。
空值/None 返回空串，调用方可安全落库。
"""
from __future__ import annotations

import re

import bleach

# 展示侧需要的合法标签（RT-A3）。
ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "blockquote",
    "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "code", "pre", "span", "a", "img",
]

# 属性最小化：span 不接受 style，避免清洗后再引入样式型攻击面。
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title"],
    "span": ["class"],
}

# 仅这三种协议可保留；无 scheme 的相对路径不受影响。
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_ANCHOR_OPEN_RE = re.compile(r"<a\b([^>]*)>", re.IGNORECASE)
_ANCHOR_TARGET_ATTR_RE = re.compile(
    r"""\s(?:target|rel)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""",
    re.IGNORECASE,
)

_LINK_TARGET = '_blank'
_LINK_REL = 'noopener noreferrer'


def _normalize_anchor_attrs(match: re.Match) -> str:
    """剥掉已有的 target/rel，再统一追加安全值（幂等）。"""
    attrs = _ANCHOR_TARGET_ATTR_RE.sub("", match.group(1)).rstrip()
    return '<a%s target="%s" rel="%s">' % (attrs, _LINK_TARGET, _LINK_REL)


def sanitize_rich_text(html: str) -> str:
    """清洗一段富文本 HTML；空值/None 返回空串。

    :param html: 待落库的 HTML 片段
    :return: 只含白名单标签/属性/协议的 HTML
    """
    if not html or not isinstance(html, str):
        return ""

    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return _ANCHOR_OPEN_RE.sub(_normalize_anchor_attrs, cleaned)
