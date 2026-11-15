# -*- coding: utf-8 -*-
"""试卷文件名解析（C2a，2026-11-08）。

目标：管理员把 `2019年北京市公务员考试《公安专业科目》真题.docx` 丢进来，
系统能自己认出 **科目 / 年份 / 地区 / 题本或答案 / 卷别**，并生成人读编号
（方案 D24：`GZ-2019-BJ-T`）。解析不出来的项**留空**，绝不猜。

为什么是纯函数：文件名千奇百怪，规则必须可单测、可回归；
解析结果写给谁（资料字段 / exam_paper 元数据 / 审计）由调用方决定。

**不做的事**：不读文件内容、不查库、不推断题量。C2b 的「改信息」是人工兜底。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

# ---------------------------------------------------------------- 词表
#: 科目 → 代码（编号前缀）
SUBJECT_CODES = {"xingce": "XC", "shenlun": "SL", "gongzhuan": "GZ"}

#: 科目关键词（顺序敏感：先匹配更具体的）
SUBJECT_PATTERNS = (
    ("gongzhuan", re.compile(r"公安专业科目|公安基础知识|公安专业|公专|公安")),
    ("shenlun", re.compile(r"申论")),
    ("xingce", re.compile(r"行政职业能力测验|行测")),
)

#: 地区 → (代码, 标准名)。**长名在前**，避免"江苏"吃掉"江苏省"之外的写法
REGIONS = (
    ("BJ", "北京", re.compile(r"北京")),
    ("JS", "江苏", re.compile(r"江苏")),
    ("ZJ", "浙江", re.compile(r"浙江")),
    ("GD", "广东", re.compile(r"广东")),
    ("SD", "山东", re.compile(r"山东")),
    ("SH", "上海", re.compile(r"上海")),
    ("TJ", "天津", re.compile(r"天津")),
    ("CQ", "重庆", re.compile(r"重庆")),
    ("HE", "河北", re.compile(r"河北")),
    ("HA", "河南", re.compile(r"河南")),
    ("HB", "湖北", re.compile(r"湖北")),
    ("HN", "湖南", re.compile(r"湖南")),
    ("SC", "四川", re.compile(r"四川")),
    ("FJ", "福建", re.compile(r"福建")),
    ("AH", "安徽", re.compile(r"安徽")),
    ("JX", "江西", re.compile(r"江西")),
    ("SX", "山西", re.compile(r"山西")),
    ("SN", "陕西", re.compile(r"陕西")),
    ("LN", "辽宁", re.compile(r"辽宁")),
    ("JL", "吉林", re.compile(r"吉林")),
    ("HLJ", "黑龙江", re.compile(r"黑龙江")),
    ("GX", "广西", re.compile(r"广西")),
    ("YN", "云南", re.compile(r"云南")),
    ("GZ", "贵州", re.compile(r"贵州")),
    ("NM", "内蒙古", re.compile(r"内蒙古")),
    ("GS", "甘肃", re.compile(r"甘肃")),
    ("XJ", "新疆", re.compile(r"新疆")),
    ("NX", "宁夏", re.compile(r"宁夏")),
    ("QH", "青海", re.compile(r"青海")),
    ("HI", "海南", re.compile(r"海南")),
    ("XZ", "西藏", re.compile(r"西藏")),
    # 国考/联考没有省级地区码，单独标
    ("GK", "国考", re.compile(r"国考|国家公务员|中央机关")),
    ("LK", "联考", re.compile(r"联考|多省联考")),
)
REGION_BY_CODE = {code: name for code, name, _ in REGIONS}

#: 题本 / 答案 / 解析
BOOK_KINDS = (
    ("T", "题本", re.compile(r"题本|真题(?!解析)|试卷|原卷|题目（?!答案）|题目(?!答案)")),
    ("A", "答案", re.compile(r"答案解析|答案|参考答案")),
    ("J", "解析", re.compile(r"解析|详解")),
)

#: 卷别（第几卷）
VOLUME_RE = re.compile(r"第\s*([一二三四五六七八九十\d]+)\s*卷|卷\s*([一二三四五六七八九十\d]+)")
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

#: 年份：2019 / 2019年；避免把 100 题、120 分钟当成年份
YEAR_RE = re.compile(r"(?<!\d)(19|20)(\d{2})(?:\s*年|(?=[^\d]|$))")


@dataclass(frozen=True)
class PaperMeta:
    """解析结果。**全部字段可空**：解析不出就是 None，不猜。"""

    year: Optional[int] = None
    region_code: Optional[str] = None
    region_name: Optional[str] = None
    subject: Optional[str] = None
    book_kind: Optional[str] = None
    book_kind_label: Optional[str] = None
    volume: Optional[int] = None
    paper_code: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "year": self.year,
            "region_code": self.region_code,
            "region_name": self.region_name,
            "subject": self.subject,
            "book_kind": self.book_kind,
            "book_kind_label": self.book_kind_label,
            "volume": self.volume,
            "paper_code": self.paper_code,
        }

    @property
    def has_any(self) -> bool:
        return any([self.year, self.region_code, self.subject, self.book_kind])


def _strip_ext(name: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1]
    return re.sub(r"\.(docx?|pdf|xlsx?)$", "", base, flags=re.I)


def parse_year(text: str) -> Optional[int]:
    """取**最后一个**合理年份（文件名里常有「2024 版 2019 真题」这种）。"""
    years = [int(m.group(0)[:4]) for m in YEAR_RE.finditer(text)]
    years = [y for y in years if 1990 <= y <= 2100]
    return years[-1] if years else None


def parse_region(text: str) -> tuple:
    for code, name, pattern in REGIONS:
        if pattern.search(text):
            return code, name
    return None, None


def parse_subject(text: str) -> Optional[str]:
    for key, pattern in SUBJECT_PATTERNS:
        if pattern.search(text):
            return key
    return None


def parse_book_kind(text: str) -> tuple:
    """先判**答案/解析**，再判题本——「真题答案解析」里同时出现两者，答案优先。"""
    for code in ("A", "J", "T"):
        for kind_code, label, pattern in BOOK_KINDS:
            if kind_code == code and pattern.search(text):
                return kind_code, label
    return None, None


def parse_volume(text: str) -> Optional[int]:
    m = VOLUME_RE.search(text)
    if not m:
        return None
    raw = (m.group(1) or m.group(2) or "").strip()
    if raw.isdigit():
        return int(raw)
    return CN_NUM.get(raw)


def build_paper_code(meta: PaperMeta) -> Optional[str]:
    """`GZ-2019-BJ-T`；缺年份或缺地区就不生成（宁缺勿错）。"""
    if not (meta.subject and meta.year and meta.region_code):
        return None
    parts = [SUBJECT_CODES.get(meta.subject, meta.subject.upper()),
             str(meta.year), meta.region_code]
    if meta.book_kind:
        parts.append(meta.book_kind)
    if meta.volume:
        parts.append(f"V{meta.volume}")
    return "-".join(parts)


def suggest_paper_code(title: str, subject: str = "", *, existing: str = "",
                       material_id: int = 0, today=None) -> str:
    """给「没有编号」的试卷资料推一个可用编号（D10，2026-11-15）。

    优先级（越靠前越可读，都不成功才用兜底，保证**永远有编号可用**）：
      1. 资料已有编号（`paper_code` / `badge`）→ 原样返回；
      2. 标题能解析出「科目 + 年份 + 地区」→ `build_paper_code()`，如 `GZ-2025-LK`；
      3. 兜底 `MAT-{YYYYMMDD}-{material_id}`，唯一且能一眼看出是自动生成的。

    为什么需要它：文件名叫「验收探针_扫描5页」这种，解析不出年份/地区 → 没有编号 →
    没有编号就没有可作答卷 → 导题最后一步入库被打回（material 139 的真机现场）。
    """
    code = (existing or "").strip().upper()
    if code:
        return code
    meta = parse_paper_file_name(title or "")
    if subject and not getattr(meta, "subject", None):
        meta = PaperMeta(**{**meta.as_dict(), "subject": subject})
    built = build_paper_code(meta)
    if built:
        return built
    day = (today or date.today()).strftime("%Y%m%d")
    return f"MAT-{day}-{int(material_id or 0)}"


def parse_paper_file_name(name: str) -> PaperMeta:
    """文件名 → 试卷元数据。解析不出的项为 None。"""
    text = _strip_ext(name)
    if not text.strip():
        return PaperMeta()

    year = parse_year(text)
    region_code, region_name = parse_region(text)
    subject = parse_subject(text)
    book_kind, book_kind_label = parse_book_kind(text)
    volume = parse_volume(text)

    partial = PaperMeta(
        year=year, region_code=region_code, region_name=region_name,
        subject=subject, book_kind=book_kind, book_kind_label=book_kind_label,
        volume=volume,
    )
    return PaperMeta(**{**partial.as_dict(), "paper_code": build_paper_code(partial)})


def format_meta_label(meta: PaperMeta) -> str:
    """给列表/抽屉展示的一行摘要，如 `2019 · 北京 · 题本`；全空返回空串。"""
    bits = []
    if meta.year:
        bits.append(str(meta.year))
    if meta.region_name:
        bits.append(meta.region_name)
    if meta.book_kind_label:
        bits.append(meta.book_kind_label)
    if meta.volume:
        bits.append(f"第 {meta.volume} 卷")
    return " · ".join(bits)
