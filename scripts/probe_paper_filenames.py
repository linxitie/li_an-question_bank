# -*- coding: utf-8 -*-
"""试卷文件名解析探针（只读，不改库、不改文件）。

用途：D32 决定「试卷元数据去掉表单必填，只从文件名解析」，本脚本用真实
517 份试卷文件名验证解析规则的实际命中率，并把逐文件结果落成 CSV 供人工抽查。

用法：
    python scripts/probe_paper_filenames.py            # 只打印统计
    python scripts/probe_paper_filenames.py --csv out.csv

退出码：0 恒定（探针不参与门禁）。
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import hashlib
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, "题库")

# 目录 -> 科目（目录名是科目最可靠的来源：行测/申论/公安*）
DIR_SUBJECT = {
    "行测": "行测",
    "申论": "申论",
    "公安题目（打印）": "公专",
    "答案解析（不用打印）": "公专",
}

PROVINCES = [
    "北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆", "香港", "澳门", "台湾",
]

EXAM_TYPES = [
    ("国家公务员", "国考"),
    ("国考", "国考"),
    ("公安院校联考", "公安院校联考"),
    ("多省", "联考"),
    ("联考", "联考"),
    ("招警", "招警"),
    ("辅警", "辅警"),
    ("选调", "选调"),
    ("事业单位", "事业单位"),
    ("公务员录用考试", "省考"),
    ("公务员考试", "省考"),
    ("公考", "省考"),
    ("公安机动勤务", "其他"),
    ("公安机关", "其他"),
]

RE_YEAR = re.compile(r"(20\d{2})\s*年")
RE_YEAR_LOOSE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
RE_ANSWER = re.compile(r"答案|解析")
RE_PAPER = re.compile(r"题本|真题|试卷|考试|题")
RE_COUNT = re.compile(r"(\d{2,3})\s*道?题")
RE_SCORE = re.compile(r"(\d{2,3})\s*分")
RE_PAREN = re.compile(r"[（(]([^（）()]*)[）)]")
RE_SUBJECT_TAG = re.compile(r"《([^》]+)》")

SUBJECT_CODE = {"行测": "XC", "申论": "SL", "公专": "GZ"}
KIND_CODE = {"题本": "T", "答案": "A"}
REGION_CODE = {
    "北京": "BJ", "天津": "TJ", "上海": "SH", "重庆": "CQ", "河北": "HE",
    "山西": "SX", "内蒙古": "NM", "辽宁": "LN", "吉林": "JL", "黑龙江": "HL",
    "江苏": "JS", "浙江": "ZJ", "安徽": "AH", "福建": "FJ", "江西": "JX",
    "山东": "SD", "河南": "HA", "湖北": "HB", "湖南": "HN", "广东": "GD",
    "广西": "GX", "海南": "HI", "四川": "SC", "贵州": "GZ", "云南": "YN",
    "西藏": "XZ", "陕西": "SN", "甘肃": "GS", "青海": "QH", "宁夏": "NX",
    "新疆": "XJ", "全国": "GK", "多省": "LK", "公安院校": "GA",
    "深圳": "SZN", "广州": "GZH",
}


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


CITIES = {
    "深圳": "广东", "广州": "广东", "杭州": "浙江", "南京": "江苏", "苏州": "江苏",
    "成都": "四川", "武汉": "湖北", "西安": "陕西", "济南": "山东", "青岛": "山东",
    "大连": "辽宁", "沈阳": "辽宁", "长春": "吉林", "哈尔滨": "黑龙江", "福州": "福建",
    "厦门": "福建", "南昌": "江西", "长沙": "湖南", "郑州": "河南", "太原": "山西",
    "合肥": "安徽", "昆明": "云南", "贵阳": "贵州", "南宁": "广西", "兰州": "甘肃",
    "西宁": "青海", "银川": "宁夏", "石家庄": "河北", "呼和浩特": "内蒙古",
}

VAR_TOKENS = [
    ("区级及以上", "QQ"), ("行政执法", "ZF"), ("普通选调", "XD"), ("副省级", "FS"),
    ("副省", "FS"), ("省级", "FS"), ("地市级", "DS"), ("地市", "DS"),
    ("县镇", "XZ"), ("县乡", "XX"), ("县级", "XJ"), ("市级", "SJ"), ("省市", "SS"),
    ("省直", "SZ"), ("旗县", "QX"), ("盟市", "MS"), ("乡镇", "XZ"), ("通用", "TY"),
    ("公安", "GA"), ("综合", "ZH"), ("甲", "A"), ("乙", "B"), ("丙", "C"),
    ("A", "A"), ("B", "B"), ("C", "C"),
]

# 独立组织考试的市：地区单独编码，避免与所在省考撞码
CITY_REGIONS = {"深圳": "SZN", "广州": "GZH"}

# 括号里出现这些内容说明它不是"卷别"，而是来源/完整性标注
SKIP_PAREN = (
    "部分", "完整版", "打印版", "含解析", "两套答案", "精选题", "无答案",
    "市、区", "市区", "专业科目", "网友回忆版", "回忆版",
)


def find_region(stem: str) -> str | None:
    """地区：独立市 > 省份 > 常见市（归到省）> 国考/联考兜底。"""
    for city in CITY_REGIONS:
        if city in stem:
            return city
    for prov in PROVINCES:
        if prov in stem:
            return prov
    for city, prov in CITIES.items():
        if city in stem:
            return prov
    if "国家" in stem or "国考" in stem or "公安部" in stem:
        return "全国"
    if "公安院校联考" in stem:
        return "公安院校"
    if "多省" in stem:
        return "多省"
    if "联考" in stem:
        return "多省"
    return None


def find_exam_type(stem: str) -> str | None:
    # 按 EXAM_TYPES 顺序优先匹配更具体的词
    for kw, val in EXAM_TYPES:
        if kw in stem:
            return val
    return None


def find_kind(stem: str) -> str | None:
    if RE_ANSWER.search(stem):
        return "答案"
    if RE_PAPER.search(stem):
        return "题本"
    return None


def find_variant(stem: str) -> str | None:
    """卷别取最后一个有效括号（先剥掉"回忆版"来源标注，再排除非卷别内容）。"""
    picked = None
    for g in RE_PAREN.findall(stem):
        g2 = g.replace("网友回忆版", "").replace("回忆版", "").strip()
        if not g2 or g2 in SKIP_PAREN:
            continue
        picked = g2
    return picked


def variant_code(v: str | None) -> str:
    """卷别 -> 短码（人读）。词表外退回 md5 前 2 位，保证确定性。"""
    if not v:
        return ""
    s = v.replace("网友回忆版", "").replace("回忆版", "").replace("卷", "").replace("类", "")
    for prov in PROVINCES:
        s = s.replace(prov, "")
    for city in CITIES:
        s = s.replace(city, "")
    s = s.replace("、", "").replace("，", "").replace(",", "")
    codes = []
    for tok, code in VAR_TOKENS:
        if tok in s:
            codes.append(code)
            s = s.replace(tok, "")
    if codes:
        return "".join(codes)
    return hashlib.md5(v.encode("utf-8")).hexdigest()[:2].upper()


def parse(name: str, dirname: str) -> dict:
    stem = os.path.splitext(name)[0]
    s = nfkc(stem)
    year = None
    m = RE_YEAR.search(s) or RE_YEAR_LOOSE.search(s)
    if m:
        year = int(m.group(1))
    subject = None
    tag = RE_SUBJECT_TAG.search(s)
    inner = tag.group(1) if tag else ""
    if "行测" in inner or "职业能力" in inner:
        subject = "行测"
    elif "申论" in inner:
        subject = "申论"
    elif "公安" in inner or "警察" in inner:
        subject = "公专"
    if subject is None:
        subject = DIR_SUBJECT.get(dirname)
    region = find_region(s)
    exam_type = find_exam_type(s)
    kind = find_kind(s)
    cnt = RE_COUNT.search(s)
    score = RE_SCORE.search(s)
    variant = find_variant(s)
    vcode = variant_code(variant)
    code = None
    if subject and year and region and kind:
        code = "%s-%d-%s-%s" % (
            SUBJECT_CODE.get(subject, "XX"),
            year,
            REGION_CODE.get(region, "XX"),
            KIND_CODE.get(kind, "X"),
        )
        if vcode:
            code += "-" + vcode
    return {
        "file": name,
        "dir": dirname,
        "stem": stem,
        "subject": subject,
        "year": year,
        "region": region,
        "exam_type": exam_type,
        "kind": kind,
        "variant": variant,
        "var_code": vcode,
        "count": int(cnt.group(1)) if cnt else None,
        "score": int(score.group(1)) if score else None,
        "recall": "回忆版" in s,
        "code": code,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    args = ap.parse_args()

    rows = []
    for dirname in DIR_SUBJECT:
        base = os.path.join(ROOT, dirname)
        if not os.path.isdir(base):
            continue
        for cur, _dirs, files in os.walk(base):
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in (".pdf", ".docx", ".doc"):
                    continue
                rows.append(parse(fn, dirname))

    total = len(rows)
    fields = ["subject", "year", "region", "exam_type", "kind", "code", "count", "score"]
    print("== 试卷文件名解析命中率（n=%d） ==" % total)
    for f in fields:
        hit = sum(1 for r in rows if r[f] not in (None, ""))
        print("  %-10s %4d / %4d  %5.1f%%" % (f, hit, total, hit * 100.0 / total))
    full = sum(1 for r in rows if r["code"])
    print("  %-10s %4d / %4d  %5.1f%%" % ("code(四要素齐)", full, total, full * 100.0 / total))

    print("\n== 按科目 ==")
    from collections import Counter
    sc = Counter(r["subject"] for r in rows)
    for k, v in sc.items():
        print("  %s: %d" % (k, v))

    print("\n== 按解析出的地区 ==")
    rc = Counter(r["region"] for r in rows)
    for k, v in rc.most_common():
        print("  %s: %d" % (k, v))

    print("\n== 按考试类型 ==")
    ec = Counter(r["exam_type"] for r in rows)
    for k, v in ec.most_common():
        print("  %s: %d" % (k, v))

    print("\n== 按 题本/答案 ==")
    kc = Counter(r["kind"] for r in rows)
    for k, v in kc.items():
        print("  %s: %d" % (k, v))

    bad = [r for r in rows if not r["code"]]
    print("\n== 四要素未齐（%d 份），前 25 条 ==" % len(bad))
    for r in bad[:25]:
        miss = [f for f in ("subject", "year", "region", "kind") if not r[f]]
        print("  [缺 %s] %s" % (",".join(miss), r["stem"]))

    # 题本/答案 配对率：同一 (subject, year, region, exam_type, variant) 是否成对
    from collections import defaultdict
    pair = defaultdict(set)
    for r in rows:
        key = (r["subject"], r["year"], r["region"], r["exam_type"], r["variant"])
        pair[key].add(r["kind"])
    paired = sum(1 for v in pair.values() if {"题本", "答案"} <= v)
    print("\n== 题本/答案解析配对（按 科目+年份+地区+类型+卷别） ==")
    print("  成对组: %d / 共 %d 组" % (paired, len(pair)))

    # code 冲突
    cc = Counter(r["code"] for r in rows if r["code"])
    dup = [(k, v) for k, v in cc.items() if v > 1]
    print("== paper_code 冲突 ==")
    print("  重复 code: %d 个（最大重复 %d 份）" % (len(dup), max([v for _, v in dup], default=0)))
    for k, v in sorted(dup, key=lambda x: -x[1])[:8]:
        print("  %s × %d" % (k, v))

    if args.csv:
        out = os.path.join(REPO, args.csv) if not os.path.isabs(args.csv) else args.csv
        with open(out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("\nCSV -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
