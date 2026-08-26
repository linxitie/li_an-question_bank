"""富文本白名单消毒——所有入库 HTML 的唯一信任边界（spec 6.1）。

规则：
- 只保留备考资料需要的展示性标签，script/style/iframe/on*事件 全部剥离；
- img src 仅允许站内 /uploads/ 路径（防外链跟踪与恶意图片注入）；
- a href 仅允许 http/https 并强制补 rel。
"""
import re

import bleach

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "u", "blockquote",
    "h2", "h3", "h4", "ul", "ol", "li",
    "img", "a", "table", "thead", "tbody", "tr", "th", "td", "span",
]
ALLOWED_ATTRS = {
    "img": ["src", "alt"],
    "a": ["href"],
}

_EXTERNAL_IMG = re.compile(r'<img\s+src="(?!/uploads/)[^"]*"')


def sanitize_html(html: str) -> str:
    if not html:
        return ""
    result = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https"],
        strip=True,
    )
    # 站内图片白名单：剥离一切非 /uploads/ 的 img src
    result = _EXTERNAL_IMG.sub('<img src=""', result)
    return result
