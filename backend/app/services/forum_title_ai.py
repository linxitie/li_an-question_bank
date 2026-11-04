"""论坛无标题帖的 AI 标题生成（2026-11-03 第 3 轮）。

设计边界：
- 只服务于「空标题 + 有正文」的帖子，**绝不覆盖已有标题**；
- 生成失败一律返回 None，由调用方记日志并跳过，不影响发帖主流程；
- 结果必须当普通标题处理（纯文本、≤200 字），不引入 HTML 面；
- 本模块不读环境变量以外的任何配置，密钥由 `settings.LLM_API_KEY` 提供（用户本人填写）。

为什么要单独成文件而不是塞进 forum.py：
`forum.py` 已 1900+ 行，AI 调用与论坛业务耦合后更难测；
独立模块可以只 mock `llm_client.chat` 就覆盖全部清洗逻辑。
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from .llm_client import LLMClientError, chat

logger = logging.getLogger(__name__)

# 标题上限与 forum_post.title 列一致
MAX_TITLE_LEN = 200
# AI 标题期望长度（超过就截断，避免生成一段话）
IDEAL_TITLE_LEN = 18

SYSTEM_PROMPT = (
    "你是学习论坛的标题助手。请为给定的帖子正文生成一个简洁中文标题。要求：\n"
    "1) 不超过 18 个字；\n"
    "2) 只输出标题本身，不要引号、不要序号、不要『标题：』前缀、不要表情符号；\n"
    "3) 概括正文主题，不要复述原文；\n"
    "4) 如果正文没有可用信息，只输出：无标题"
)

# 生成后可能出现的包裹符号，统一剥掉
_QUOTE_PAIRS = [
    ('"', '"'),
    ("'", "'"),
    ("“", "”"),
    ("‘", "’"),
    ("「", "」"),
    ("《", "》"),
    ("【", "】"),
]
_PREFIX_PATTERN = re.compile(r"^(标题|题目|Title)\s*[:：]\s*", re.IGNORECASE)


def strip_html(content: str) -> str:
    """把富文本正文压成纯文本：去标签、去表情包占位符、压平空白。"""
    text = str(content or "")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[\[sticker:[^\]]+\]\]", " ", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_title(raw: str) -> str:
    """清洗模型输出：去 markdown 强调符/前缀/引号/多余标点、压平、截断。空结果返回空串。"""
    title = str(raw or "").strip()
    if not title:
        return ""

    # 只取第一行（模型偶尔会给出解释段）
    title = title.splitlines()[0].strip()
    # 先去掉 markdown 强调符，否则 "**标题：** xxx" 里的前缀识别不到
    title = title.replace("**", "").replace("__", "").strip()
    title = _PREFIX_PATTERN.sub("", title).strip()

    for left, right in _QUOTE_PAIRS:
        if len(title) >= 2 and title.startswith(left) and title.endswith(right):
            title = title[1:-1].strip()

    # 去掉模型自带的结尾标点，标题不需要句号
    title = title.rstrip("。.，,；;：:！!？?").strip()
    # 前缀可能被引号包住，去掉引号后再尝试一次
    title = _PREFIX_PATTERN.sub("", title).strip()
    for left, right in _QUOTE_PAIRS:
        if len(title) >= 2 and title.startswith(left) and title.endswith(right):
            title = title[1:-1].strip()

    if not title:
        return ""
    if len(title) > IDEAL_TITLE_LEN:
        title = title[:IDEAL_TITLE_LEN].rstrip()
    return title[:MAX_TITLE_LEN]


def _meaningful_chars(text: str) -> int:
    """统计「有效文字」数量：只算中日韩文字、字母、数字。

    为什么要这一步：库里存在正文只有表情（😄😍🤨）或标点（。。。。）的帖子，
    对它们调模型只会拿到「无标题」这种结果，既浪费 token 又污染标题。
    """
    return len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9]", text or ""))


def has_meaningful_content(content: str, min_chars: int = 8) -> bool:
    """正文是否有足够「有效文字」可用来概括标题（供接口层快速拒绝）。"""
    return _meaningful_chars(strip_html(content or "")) >= min_chars


def needs_ai_title(title: Optional[str], content: Optional[str]) -> bool:
    """是否需要 AI 生成标题：标题为空/(无标题)，且正文有足够「有效文字」。

    门槛取 8 个有效字符：低于这个量无法概括出有意义的标题。
    """
    normalized = (title or "").strip()
    if normalized and normalized != "(无标题)":
        return False
    return has_meaningful_content(content or "")


async def generate_forum_title(content: str, content_format: str = "TEXT") -> Optional[str]:
    """调用大模型生成标题；任何失败都返回 None（调用方据此跳过，不阻断业务）。"""
    plain = strip_html(content or "")
    # 正文有效文字太少时直接放弃，不浪费 token
    if _meaningful_chars(plain) < 8:
        logger.info("AI 标题跳过：正文有效文字不足（%s 字）", _meaningful_chars(plain))
        return None

    # 正文过长时截断，控制 token 成本
    user_content = plain[:1200]

    try:
        raw = await chat(
            [{"role": "user", "content": f"帖子正文：\n{user_content}"}],
            scene="qa",
            extra_system=SYSTEM_PROMPT,
        )
    except LLMClientError as exc:
        logger.warning("AI 标题生成失败（LLM 不可用）: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - 任何异常都不能打断发帖
        logger.warning("AI 标题生成异常: %s", exc)
        return None

    title = clean_title(raw)
    if not title or title == "无标题":
        return None
    logger.info("AI 标题生成成功: %s", title)
    return title
