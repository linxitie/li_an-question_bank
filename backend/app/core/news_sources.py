"""R2.1 首批新闻来源配置（3 国家级 + 5 重点省份）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSourceConfig:
    code: str
    name: str
    base_url: str
    list_url: str
    adapter: str = "http"
    category_code: str = ""
    category: str = ""
    region_code: str = ""
    trust_level: int = 70
    enabled: int = 1


NEWS_SOURCES: tuple[NewsSourceConfig, ...] = (
    NewsSourceConfig(
        "xinhua", "新华网", "https://www.news.cn", "https://www.news.cn/politics/",
        category_code="current_politics", category="时政", trust_level=90,
    ),
    NewsSourceConfig(
        "people", "人民网", "http://politics.people.com.cn", "http://politics.people.com.cn/",
        adapter="playwright", category_code="current_politics", category="时政", trust_level=85,
    ),
    NewsSourceConfig(
        "mps", "公安部", "https://www.mps.gov.cn", "https://www.mps.gov.cn/n2255079/index.html",
        adapter="playwright", category_code="police_news", category="公安要闻", trust_level=95,
    ),
    NewsSourceConfig(
        "beijing", "北京市公安局", "https://gaj.beijing.gov.cn", "https://gaj.beijing.gov.cn/",
        category_code="police_news", category="公安要闻", region_code="110000", trust_level=80,
    ),
    NewsSourceConfig(
        "guangdong", "广东省公安厅", "https://gdga.gd.gov.cn", "https://gdga.gd.gov.cn/",
        category_code="police_news", category="公安要闻", region_code="440000", trust_level=80,
    ),
    NewsSourceConfig(
        "shandong", "山东省公安厅", "http://gat.shandong.gov.cn", "http://gat.shandong.gov.cn/",
        category_code="police_news", category="公安要闻", region_code="370000", trust_level=80,
    ),
    NewsSourceConfig(
        "henan", "河南省公安厅", "https://hnga.henan.gov.cn", "https://hnga.henan.gov.cn/",
        category_code="police_news", category="公安要闻", region_code="410000", trust_level=80,
    ),
    NewsSourceConfig(
        "sichuan", "四川省公安厅", "https://gat.sc.gov.cn", "https://gat.sc.gov.cn/",
        category_code="police_news", category="公安要闻", region_code="510000", trust_level=80,
    ),
)

SOURCE_BY_CODE = {source.code: source for source in NEWS_SOURCES}
