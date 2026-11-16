"""文本归一化：全半角、大小写、零宽字符、插符号绕过。

归一化后的字符串与原文保持索引映射，屏蔽时只替换命中的原始字符，
因此 "傻.逼" 这类插符号写法也能被定位与打码，而不会误伤分隔符。
"""
from __future__ import annotations

import unicodedata

# 零宽 / 方向控制字符：肉眼不可见，是常见绕过手段
_ZERO_WIDTH = {
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
}


def _is_cjk(code: int) -> bool:
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2FA1F
    )


def _keep(ch: str) -> bool:
    if ch in _ZERO_WIDTH:
        return False
    if ch.isalnum():
        return True
    return _is_cjk(ord(ch))


def compact(text: str) -> tuple[str, list[int]]:
    """返回 (归一化字符串, 每个字符对应的原文下标)。"""
    if not text:
        return "", []
    chars: list[str] = []
    index: list[int] = []
    for pos, raw in enumerate(text):
        folded = unicodedata.normalize("NFKC", raw).lower()
        for ch in folded:
            if _keep(ch):
                chars.append(ch)
                index.append(pos)
    return "".join(chars), index


def normalize(text: str) -> str:
    """只看文本时用这个；需要回写位置时用 compact()。"""
    return compact(text)[0]


def mask_original(
    text: str, spans: list[tuple[int, int]], index: list[int], char: str = "*"
) -> str:
    """把归一化区间 [start, end) 映射回原文并替换为占位符。

    只替换真正命中的字符；插入的分隔符保留，阅读时仍能看出原文结构。
    """
    if not spans or not text:
        return text
    targets: set[int] = set()
    for start, end in spans:
        for i in range(start, min(end, len(index))):
            targets.add(index[i])
    if not targets:
        return text
    out = list(text)
    for pos in targets:
        if 0 <= pos < len(out):
            out[pos] = char
    return "".join(out)


def snippet(
    text: str, spans: list[tuple[int, int]], index: list[int], limit: int = 200
) -> str:
    """脱敏摘要：命中词替换为 *，再截断，避免把违规原文写进审计库。"""
    masked = mask_original(text, spans, index, char="*")
    masked = " ".join(masked.split())
    if len(masked) <= limit:
        return masked
    return masked[: limit - 1] + "…"
