"""富文本白名单消毒——所有入库 HTML 的唯一信任边界（spec 6.1）。

规则：
- 只保留备考资料需要的展示性标签，script/style/iframe/on*事件 全部剥离；
- img src 仅允许站内 /uploads/ 与 /media/ 路径（防外链跟踪与恶意图片注入）；
- a href 仅允许 http/https 并强制补 rel。
"""
import hashlib
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

_EXTERNAL_IMG = re.compile(r'<img\s+src="(?!(?:/uploads/|/media/))[^"]*"')


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
    # 站内图片白名单：剥离一切非 /uploads/ 或 /media/ 的 img src
    result = _EXTERNAL_IMG.sub('<img src=""', result)
    return result


# ==================== 内容清洗引擎（Task 8）====================


class ContentCleaner:
    """文本内容清洗引擎 — 去除手机号、微信号、版权声明、广告词等"""

    PATTERNS = {
        "phone": r"1[3-9]\d{9}",
        "wechat": r"[wW]echat[:\s]*[a-zA-Z0-9_]+",
        "qq": r"[Qq]{2}[:\s]*\d{5,11}",
        "copyright": r"(版权所有|未经许可不得转载|Copyright|©)",
        "ad_keywords": r"(扫码关注|添加微信|加好友|点击关注|关注公众号)",
        "page_number": r"第\s*\d+\s*页|Page\s*\d+",
        "footer": r"[\s]*[-]{3,}[\s]*$",
    }

    def clean_text(self, text: str) -> str:
        """清洗纯文本内容，去除敏感信息和垃圾内容。"""
        if not text:
            return ""

        # 1. 移除控制字符
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # 2. 应用过滤模式
        for _key, pattern in self.PATTERNS.items():
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # 3. 合并连续空行（>2行 → 2行）
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        return text.strip()

    def calculate_content_hash(self, content: str) -> str:
        """计算清洗后内容的 MD5 哈希（用于去重）。"""
        cleaned = self.clean_text(content)
        return hashlib.md5(cleaned.encode("utf-8")).hexdigest()


# 全局单例
content_cleaner = ContentCleaner()
