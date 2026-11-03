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

# 属性最小化：span 不接受 style（默认），避免清洗后再引入样式型攻击面。
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title"],
    "span": ["class"],
}

# ===== 受限内联样式（2026-11-03，用户批准）=====
# 背景：富文本发帖需要「字体颜色 / 字号 / 对齐」，wangEditor 输出的是内联 style；
# 默认全剥离会让这些功能保存后丢失。这里只放开 4 个属性，且**逐个值做正则校验**，
# 其余（position/z-index/width/background-image/expression…）一律不进白名单。
# 为什么不直接用 bleach 的 CSSSanitizer：本机 bleach 6.3 缺 tinycss2，且不引入新依赖更稳。
ALLOWED_STYLE_TAGS = ("span", "p", "td", "th")

_COLOR_PATTERN = re.compile(
    r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}"
    r"|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(\s*,\s*[0-9.]+)?\s*\)"
    r"|[a-zA-Z]{3,20})$"
)
_FONT_SIZE_PATTERN = re.compile(r"^(?:[1-9]|[12]\d|3[0-6])px$")
_TEXT_ALIGN_PATTERN = re.compile(r"^(?:left|center|right|justify)$")

_ALLOWED_CSS_PROPS = {
    "color": _COLOR_PATTERN,
    "background-color": _COLOR_PATTERN,
    "font-size": _FONT_SIZE_PATTERN,
    "text-align": _TEXT_ALIGN_PATTERN,
}

# 允许承载受限样式的四个标签；其余标签的 style 仍被剥离
ALLOWED_ATTRIBUTES_STYLE = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title"],
    "span": ["class", "data-sf-tmp"],
    "p": ["data-sf-tmp"],
    "td": ["data-sf-tmp"],
    "th": ["data-sf-tmp"],
}

_STYLE_ATTR_RE = re.compile(r"""\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<(span|p|td|th)\b([^>]*)>", re.IGNORECASE)
_TMP_ATTR_RE = re.compile(r"""\sdata-sf-tmp\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
# 连内容一起丢掉：bleach 的 strip=True 只剥标签、保留脚本文本，会让 <script>alert(1)</script>
# 变成可见的 "alert(1)"。语义上它属于脚本而不是正文，整段删掉更干净。
_SCRIPT_STYLE_BLOCK_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)


def _validated_style(value: str) -> str:
    """把一条 style 值按白名单+值正则过滤，返回可安全回写的声明串。"""
    kept = []
    for raw_decl in value.split(";"):
        if ":" not in raw_decl:
            continue
        prop, _, val = raw_decl.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        pattern = _ALLOWED_CSS_PROPS.get(prop)
        if pattern is None or not pattern.match(val):
            continue
        kept.append(f"{prop}:{val}")
    return ";".join(kept)

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


def _stash_inline_styles(html: str) -> str:
    """把白名单标签上「校验通过」的 style 暂存为 data-sf-tmp，交给 bleach 保留。

    为什么要绕这一步：bleach 会整段剥离 style；而我们需要保留 4 个受限属性。
    做法是「先校验、再改名暂存、clean 之后改回」，这样 bleach 从不接触未校验的样式。
    """
    def _rewrite_tag(match: re.Match) -> str:
        tag, attrs = match.group(1), match.group(2)

        def _rewrite_style(style_match: re.Match) -> str:
            raw = style_match.group(1) if style_match.group(1) is not None else style_match.group(2)
            validated = _validated_style(raw or "")
            # 校验后为空就彻底删掉这个 style，不留给 bleach 任何原文
            return f' data-sf-tmp="{validated}"' if validated else ""

        return f"<{tag}{_STYLE_ATTR_RE.sub(_rewrite_style, attrs)}>"

    return _STYLE_TAG_RE.sub(_rewrite_tag, html)


def _restore_inline_styles(html: str) -> str:
    """把 data-sf-tmp 还原成 style（值已在校验阶段被白名单化）。"""
    def _rewrite_tmp(match: re.Match) -> str:
        value = match.group(1) if match.group(1) is not None else match.group(2)
        return f' style="{value}"' if value else ""

    return _TMP_ATTR_RE.sub(_rewrite_tmp, html)


def sanitize_rich_text(html: str, allow_inline_style: bool = False) -> str:
    """清洗一段富文本 HTML；空值/None 返回空串。

    :param html: 待落库的 HTML 片段
    :param allow_inline_style: 是否保留受限内联样式（颜色/背景色/字号/对齐）。
        默认 False：新闻/资料等既有调用方行为完全不变。
    :return: 只含白名单标签/属性/协议的 HTML
    """
    if not html or not isinstance(html, str):
        return ""

    staged = _SCRIPT_STYLE_BLOCK_RE.sub("", html)
    if allow_inline_style:
        staged = _stash_inline_styles(staged)

    cleaned = bleach.clean(
        staged,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES_STYLE if allow_inline_style else ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    if allow_inline_style:
        cleaned = _restore_inline_styles(cleaned)
    return _ANCHOR_OPEN_RE.sub(_normalize_anchor_attrs, cleaned)
