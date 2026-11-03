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
    link_contains: str = ""
    category_code: str = ""
    category: str = ""
    region_code: str = ""
    trust_level: int = 70
    enabled: int = 1


NEWS_SOURCES: tuple[NewsSourceConfig, ...] = (
    NewsSourceConfig(
        "xinhua",
        "新华网",
        "https://www.news.cn",
        "https://www.news.cn/politics/",
        category_code="current_politics",
        category="时政",
        trust_level=90,
    ),
    NewsSourceConfig(
        "people",
        "人民网",
        "http://politics.people.com.cn",
        "http://politics.people.com.cn/GB/1024/index.html",
        adapter="http",
        category_code="current_politics",
        category="时政",
        trust_level=85,
    ),
    NewsSourceConfig(
        "mps",
        "公安部",
        "https://www.mps.gov.cn",
        "https://www.mps.gov.cn/n2253534/n2253535/index.html",
        adapter="playwright",
        link_contains="/n2253534/n2253535/",
        category_code="police_news",
        category="公安要闻",
        trust_level=95,
    ),
    NewsSourceConfig(
        "beijing",
        "北京市公安局",
        "https://gaj.beijing.gov.cn",
        "https://gaj.beijing.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="110000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "guangdong",
        "广东省公安厅",
        "https://gdga.gd.gov.cn",
        "https://gdga.gd.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="440000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "shandong",
        "山东省公安厅",
        "http://gat.shandong.gov.cn",
        "http://gat.shandong.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="370000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "henan",
        "河南省公安厅",
        "https://hnga.henan.gov.cn",
        "https://hnga.henan.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="410000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "sichuan",
        "四川省公安厅",
        "https://gat.sc.gov.cn",
        "https://gat.sc.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="510000",
        trust_level=80,
    ),
    # 第二批：华北/华东/华中 8 个省级公安来源
    NewsSourceConfig(
        "tianjin",
        "天津市公安局",
        "http://ga.tj.gov.cn",
        "http://ga.tj.gov.cn/gaxc/jcdt/",
        link_contains="/t202",
        category_code="police_news",
        category="公安要闻",
        region_code="120000",
        trust_level=80,
        enabled=0,
    ),
    NewsSourceConfig(
        "hebei",
        "河北省公安厅",
        "http://gat.hebei.gov.cn",
        "http://gat.hebei.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="130000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "shanghai",
        "上海市公安局",
        "https://gaj.sh.gov.cn",
        "https://gaj.sh.gov.cn/shga/jwbd.html",
        link_contains="/shga/wzXxfbGj/detail",
        category_code="police_news",
        category="公安要闻",
        region_code="310000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "jiangsu",
        "江苏省公安厅",
        "https://gat.jiangsu.gov.cn",
        "https://gat.jiangsu.gov.cn/",
        adapter="playwright",
        category_code="police_news",
        category="公安要闻",
        region_code="320000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "zhejiang",
        "浙江省公安厅",
        "http://gat.zj.gov.cn",
        "http://gat.zj.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="330000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "fujian",
        "福建省公安厅",
        "http://gat.fujian.gov.cn",
        "http://gat.fujian.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="350000",
        trust_level=80,
    ),
    NewsSourceConfig(
        "hubei",
        "湖北省公安厅",
        "http://gat.hubei.gov.cn",
        "http://gat.hubei.gov.cn/bmdt/gayw/",
        link_contains="/t202",
        category_code="police_news",
        category="公安要闻",
        region_code="420000",
        trust_level=80,
        enabled=0,
    ),
    NewsSourceConfig(
        "hunan",
        "湖南省公安厅",
        "http://gat.hunan.gov.cn",
        "http://gat.hunan.gov.cn/",
        category_code="police_news",
        category="公安要闻",
        region_code="430000",
        trust_level=80,
    ),
)

SOURCE_BY_CODE = {source.code: source for source in NEWS_SOURCES}
