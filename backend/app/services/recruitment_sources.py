"""招考官方来源配置：一期启用广东/江苏/山东/河南/四川。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RecruitmentSource:
    code: str
    name: str
    list_url: str
    category: str = "国考省考"
    adapter: str = "http"
    link_regex: str = r"/(?:art|content|post|article|t\d+_|ARTI|20\d{2})"
    enabled: bool = False

    @property
    def host(self) -> str:
        return urlparse(self.list_url).netloc.lower()


SOURCES = (
    RecruitmentSource("gd", "广东人事考试网", "http://rsks.gd.gov.cn/", link_regex=r"/zwgk/gzdt/content/post_\d+\.html$", enabled=True),
    RecruitmentSource("js", "江苏省人事考试网", "http://jshrss.jiangsu.gov.cn/col/col57253/", link_regex=r"/art/20\d{2}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html$", enabled=True),
    RecruitmentSource("sd", "山东人事考试信息网", "http://hrss.shandong.gov.cn/rsks/", link_regex=r"/articles/ch\d+/\d{6}/[a-f0-9-]+\.shtml$", enabled=True),
    RecruitmentSource("hn", "河南人事考试网", "http://www.hnrsks.com", link_regex=r"/article[a-f0-9]+\.html$", enabled=True),
    RecruitmentSource("sc", "四川人事考试专栏", "https://www.scpta.com.cn", adapter="playwright", link_regex=r"/.*?/\d+\.html$|article", enabled=True),
    RecruitmentSource("bj", "北京市人事考试网", "http://rsj.beijing.gov.cn/ywsite/bjpta/"),
    RecruitmentSource("tj", "天津人事考试网", "http://hrss.tj.gov.cn/jsdw/rsksw/"),
    RecruitmentSource("heb", "河北省人事考试网", "https://www.hebpta.com.cn"),
    RecruitmentSource("sx", "山西人事考试专栏", "http://rst.shanxi.gov.cn/rsks/"),
    RecruitmentSource("nmg", "内蒙古人事考试网", "http://www.impta.com.cn"),
    RecruitmentSource("ln", "辽宁人事考试网", "https://www.lnrsks.com/"),
    RecruitmentSource("jl", "吉林公务员考试网", "http://www.jlgwyks.cn"),
    RecruitmentSource("hlj", "黑龙江省公务员考试网", "http://www.hljsgwy.org.cn"),
    RecruitmentSource("sh", "上海市公务员局", "https://www.shacs.gov.cn"),
    RecruitmentSource("zj", "浙江人事考试网", "http://www.zjks.com/"),
    RecruitmentSource("ah", "安徽省人事考试网", "http://www.apta.gov.cn"),
    RecruitmentSource("fj", "福建省公务员考试录用网", "http://gwykl.fujian.gov.cn"),
    RecruitmentSource("jx", "江西人事考试网", "http://www.jxpta.com/"),
    RecruitmentSource("hubei", "湖北省人事考试网", "https://rst.hubei.gov.cn/hbrsksw/"),
    RecruitmentSource("hunan", "湖南人事考试网", "http://www.hunanpea.com/"),
    RecruitmentSource("gx", "广西人事考试网", "http://www.gxpta.com.cn"),
    RecruitmentSource("hainan", "海南省考试局网站", "http://ea.hainan.gov.cn"),
    RecruitmentSource("cq", "重庆市人力资源和社会保障局", "https://rlsbj.cq.gov.cn"),
    RecruitmentSource("gz", "贵州人事考试信息网", "http://www.gzrsks.com.cn"),
    RecruitmentSource("yn", "云岭先锋公务员招录", "http://www.ynylxf.cn/topicweb/ynskslygwy/index.html"),
    RecruitmentSource("xz", "西藏人社厅", "http://hrss.xizang.gov.cn"),
    RecruitmentSource("shaanxi", "陕西人事考试网", "http://www.sxrsks.cn"),
    RecruitmentSource("gs", "甘肃省人事考试网", "http://ks.rst.gansu.gov.cn/ncms/index.shtml"),
    RecruitmentSource("qh", "青海省人事考试信息网", "http://www.qhpta.com/ncms/index.shtml"),
    RecruitmentSource("nx", "宁夏人事考试中心", "http://www.nxpta.com"),
    RecruitmentSource("xj", "新疆人事考试中心", "http://www.xjrsks.com.cn"),
    RecruitmentSource("bt", "新疆生产建设兵团考试信息网", "http://btpta.xjbt.gov.cn"),
    RecruitmentSource("sd_police", "山东省公安厅", "http://gat.shandong.gov.cn", category="公安招警"),
    RecruitmentSource("hlj_police", "黑龙江省公安厅龙警网", "https://gat.hlj.gov.cn/", category="公安招警"),
    RecruitmentSource("shaanxi_police", "陕西省公安厅", "http://gat.shaanxi.gov.cn", category="公安招警"),
    RecruitmentSource("gs_police", "甘肃省公安厅", "http://www.gsgaw.gov.cn/", category="公安招警"),
    RecruitmentSource("qh_police", "青海省公安厅", "http://www.qhga.gov.cn/", category="公安招警"),
    RecruitmentSource("xj_police", "新疆公安厅", "http://www.xjgat.gov.cn/", category="公安招警"),
)


def source_by_code(code: str) -> RecruitmentSource | None:
    return next((item for item in SOURCES if item.code == code), None)
