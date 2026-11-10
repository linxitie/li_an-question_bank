"""已授权的金句外部来源配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalQuoteSource:
    code: str
    name: str
    list_url: str
    category: str
    link_regex: str
    allowed_host: str
    max_articles: int = 3


EXTERNAL_QUOTE_SOURCES = (
    ExternalQuoteSource(
        code="people_theory",
        name="人民网·理论频道",
        list_url="http://theory.people.com.cn/",
        category="理论",
        link_regex=r"/n1/20\d{2}/\d{4}/c\d+-\d+\.html$",
        allowed_host="theory.people.com.cn",
    ),
    ExternalQuoteSource(
        code="gmw_comment",
        name="光明网·时评频道",
        list_url="https://guancha.gmw.cn/",
        category="评论",
        link_regex=r"/20\d{2}-\d{2}/\d{2}/content_\d+\.htm$",
        allowed_host="guancha.gmw.cn",
    ),
    ExternalQuoteSource(
        code="qstheory",
        name="求是网",
        list_url="https://www.qstheory.cn/",
        category="理论",
        link_regex=r"/20\d{6}/[a-f0-9]+/c\.html$",
        allowed_host="www.qstheory.cn",
    ),
    ExternalQuoteSource(
        code="ccdi",
        name="中央纪委国家监委网站",
        list_url="https://www.ccdi.gov.cn/",
        category="党建",
        link_regex=r"/(?:toutun|yaowenn)/\d{6}/t\d+_\d+\.html$",
        allowed_host="www.ccdi.gov.cn",
    ),
    ExternalQuoteSource(
        code="12371",
        name="共产党员网",
        list_url="https://www.12371.cn/",
        category="党建",
        link_regex=r"/20\d{2}/\d{2}/\d{2}/ARTI\d+\.shtml$",
        allowed_host="www.12371.cn",
    ),
)


def source_by_code(code: str) -> ExternalQuoteSource | None:
    return next((item for item in EXTERNAL_QUOTE_SOURCES if item.code == code), None)
