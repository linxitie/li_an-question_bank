#!/usr/bin/env python3
"""Build the T-02 taxonomy alias review CSV for the 505 legacy PDF points.

Scope: T-02 only (read-only audit artifact). This script never writes to the
database. It opens ``backend/data/question_bank.db`` with ``mode=ro`` and sets
``PRAGMA query_only=ON`` before reading anything.

The canonical tree is read from ``KNOWLEDGE_TREE_V2`` in
``backend/scripts/admin/seed.py`` via AST literal parsing, so the script does
not import application modules or touch settings / sessions.

Usage:
    python backend/scripts/migrate/build_taxonomy_v2.py make-aliases
    python backend/scripts/migrate/build_taxonomy_v2.py --make-aliases

Output:
    backend/data/audit/taxonomy_alias_review.csv
"""
from __future__ import annotations

import argparse
import ast
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"
SEED_PATH = BACKEND_DIR / "scripts" / "admin" / "seed.py"
OUT_PATH = BACKEND_DIR / "data" / "audit" / "taxonomy_alias_review.csv"

LEGACY_MIN = 127
LEGACY_MAX = 631
EXPECTED_LEGACY = 505

CSV_COLUMNS = [
    "old_id",
    "old_name",
    "subject",
    "sub_category",
    "new_id",
    "new_name",
    "match_type",
    "confidence",
    "note",
]

SUBJECT_NAMES = {1: "行测", 2: "申论", 3: "公专"}

# Old sub_category -> canonical L2s that may own a mapping for that category.
L2_GROUPS = {
    ("行测", "政治理论"): (
        "党的二十大精神",
        "马克思主义基本原理",
        "党和国家方针政策",
        "政治立场与政治敏锐性",
    ),
    ("行测", "常识判断"): (
        "经济常识",
        "文化常识",
        "社会常识",
        "生态常识",
        "法律常识",
        "科技常识",
        "时政热点",
    ),
    ("行测", "言语理解与表达"): ("逻辑填空", "片段阅读", "语句表达"),
    ("行测", "数量关系"): ("数字推理", "数学运算"),
    ("行测", "判断推理"): ("图形推理", "逻辑判断", "类比推理", "定义判断"),
    ("行测", "资料分析"): ("资料类型", "统计术语", "速算技巧"),
    ("行测", "科学推理"): ("物理", "化学", "生物", "地理"),
    ("行测", "知觉速度与准确性"): ("同符查找", "数字区间定位", "字符替换"),
}

# Small, explicit alias dictionary. Only documented name variants or
# well-established subtype -> canonical class mappings. Anything ambiguous is
# left to the heuristic fallback ("其他") with an explanatory note.
ALIASES = {
    ("行测", "政治理论"): {
        "法治建设": "全面依法治国",
    },
    ("行测", "常识判断"): {
        "生物常识": "生物",
        "物理常识": "物理",
        "化学常识": "化学",
        "生活常识": "生活科技",
        "环境常识": "环境保护",
        "热点事件": "社会热点",
        "行政管理": "公共管理",
    },
    ("行测", "言语理解与表达"): {
        "中心理解题": "主旨概括",
        "契合文段中心": "主旨概括",
        "细节判断题": "细节判断",
        "标题填入题": "标题填入",
        "词句理解题": "词句理解",
        "语句填空题": "语句填空",
        "语句排序题": "语句排序",
        "接语选择题": "接语选择",
        "病句": "病句辨析",
        "实词": "实词填空",
        "成语混搭填空": "混搭填空",
        "关联关系": "关联词",
        "关联词的后半部分": "关联词",
    },
    ("行测", "数量关系"): {
        "经济利润问题": "经济利润",
        "基础排列组合": "排列组合",
        "排列组合问题": "排列组合",
        "平面几何": "几何问题",
        "几何小题型（新）": "几何问题",
        "三角形基础（新）": "几何问题",
        "勾股定理（新）": "几何问题",
        "面积相关（新）": "几何问题",
        "给情况求概率": "概率问题",
        "给概率求概率": "概率问题",
        "普通行程": "行程问题",
        "相遇追及": "行程问题",
        "流水行船": "行程问题",
        "火车过桥": "行程问题",
        "平均速度": "行程问题",
        "给效率比例型": "工程问题",
        "给完工时间型": "工程问题",
    },
    ("行测", "判断推理"): {
        # 类比推理 relation classes
        "近义关系": "语义关系",
        "反义关系": "语义关系",
        "比喻象征义": "语义关系",
        "语义": "语义关系",
        "矛盾关系": "逻辑关系",
        "反对关系": "逻辑关系",
        "交叉关系": "逻辑关系",
        "全同关系": "逻辑关系",
        "种属关系": "逻辑关系",
        "组成关系": "逻辑关系",
        "包容": "逻辑关系",
        "逻辑": "逻辑关系",
        "语法": "语法关系",
        "词性": "语法关系",
        "偏正": "语法关系",
        # 图形推理 class mappings (documented textbook subtypes)
        "常规类平移": "位置规律",
        "旋转": "位置规律",
        "翻转": "位置规律",
        "位置等": "位置规律",
        "对称性的区分": "属性规律",
        "对称轴的方向": "属性规律",
        "对称轴与图形的关系": "属性规律",
        "对称性": "属性规律",
        "开闭性": "属性规律",
        "曲直性": "属性规律",
        "面数量": "数量规律",
        "部分数": "数量规律",
        "个数": "数量规律",
        "笔画数": "数量规律",
        "直线数": "数量规律",
        "曲线数": "数量规律",
        "交点数": "数量规律",
        "直角数": "数量规律",
        "曲直交点": "数量规律",
        "小面": "数量规律",
        "素": "数量规律",
        "元素的种类": "数量规律",
        "部分面": "数量规律",
        "加减同异": "样式规律",
        "先加减同异": "样式规律",
        "后加减同异": "样式规律",
        "黑白运算": "样式规律",
        "内部图案遍历": "样式规律",
        "遍历": "样式规律",
        "相加": "样式规律",
        "相减": "样式规律",
        "六面体": "空间重构",
        "四面体": "空间重构",
        "三视图": "空间重构",
        "截面图": "空间重构",
        "立体拼合": "空间重构",
        "平面拼合": "空间重构",
        "空间类": "空间重构",
        "多面体折叠": "空间重构",
        "画边法": "空间重构",
        "相对面": "空间重构",
        "公共边": "空间重构",
    },
    ("行测", "资料分析"): {
        "综合资料": "混合资料",
        "文字": "文字资料",
        "统计表": "表格资料",
        "统计图": "图形资料",
        "现期比重": "比重",
        "基期比重": "比重",
        "两期比重": "比重",
        "混合比重": "比重",
        "比值计算": "比重",
        "比值比较": "比重",
        "现期倍数": "倍数",
        "基期倍数": "倍数",
        "平均数问题": "平均数",
        "现期平均数": "平均数",
        "基期平均数": "平均数",
        "两期平均数比较": "平均数",
        "一般增长率": "增长率",
        "年均增长率": "增长率",
        "间隔增长率": "增长率",
        "混合增长率": "增长率",
        "平均数的增长率": "增长率",
    },
    ("行测", "科学推理"): {
        "两溶液混合": "溶液",
        "水和溶液": "溶液",
        "多溶液混合": "溶液",
        "物质的性质": "物质性质",
        "电路分析": "电学",
        "家庭电路": "电学",
        "自转与公转": "地球运动",
        "光现象": "光学",
        "运动图像": "运动学",
        "力学综合": "力学",
        "受力分析": "力学",
        "功和能": "力学",
        "摩擦力": "力学",
        "气候与气象": "气候气象",
    },
}

# Names that are placeholders / noise and should stay hidden even when the old
# sub_category itself is known.
NOISE_NAMES = {
    "数量",
    "科学推理",
    "常识判断",
    "纯常识",
    "能指出",
    "企业管理",
    "市场",
    "时间不够长等",
}

# Cross-domain or ambiguous names that must not be forced into a parent.
HIDDEN_NAMES = {
    ("判断推理", "两集合"): "cross-domain: 集合计数属于数量关系，但旧 sub_category 是判断推理；隐藏",
    ("判断推理", "三集合"): "cross-domain: 集合计数属于数量关系，但旧 sub_category 是判断推理；隐藏",
    ("判断推理", "确定捆绑"): "cross-domain: 语句排序术语出现在判断推理；隐藏",
    ("判断推理", "相邻问题"): "ambiguous: 可能是图形相邻面，也可能是数量相邻排列；隐藏",
    ("判断推理", "不相邻问题"): "ambiguous: 可能是图形相邻面，也可能是数量相邻排列；隐藏",
}

GENERIC_L3_NAMES = {"其他"}


def load_canonical_tree() -> dict:
    """Read KNOWLEDGE_TREE_V2 from seed.py without importing app modules."""
    source = SEED_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "KNOWLEDGE_TREE_V2":
                return ast.literal_eval(node.value)
    raise RuntimeError(f"KNOWLEDGE_TREE_V2 not found in {SEED_PATH}")


def build_indexes(tree: dict):
    """Return L2 -> L3 list per subject and L3 -> [(L2, L3)] per subject."""
    l2_index: dict[str, dict[str, list[str]]] = {}
    l3_index: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for subject, groups in tree.items():
        l2_index[subject] = {}
        l3_index[subject] = {}
        for _group, l2s in groups.items():
            for l2, l3s in l2s.items():
                l2_index[subject][l2] = list(l3s)
                for l3 in l3s:
                    l3_index[subject].setdefault(l3, []).append((l2, l3))
    return l2_index, l3_index


def allowed_targets(subject: str, sub_category: str, l2_index: dict):
    """L3 name -> [(L2, L3)] for canonical L2s allowed under an old subcat."""
    out: dict[str, list[tuple[str, str]]] = {}
    for l2 in L2_GROUPS[(subject, sub_category)]:
        for l3 in l2_index[subject][l2]:
            out.setdefault(l3, []).append((l2, l3))
    return out


def validate_aliases(subject: str, sub_category: str, targets: dict) -> None:
    for old_name, new_name in ALIASES.get((subject, sub_category), {}).items():
        hits = targets.get(new_name, [])
        if len(hits) != 1:
            raise RuntimeError(
                f"alias target is not unique in {subject}/{sub_category}: "
                f"{old_name!r} -> {new_name!r} ({len(hits)} hits)"
            )


def route_l2(subject: str, sub_category: str, name: str) -> str | None:
    """Heuristic L2 routing inside one old sub_category."""
    if sub_category == "政治理论":
        if any(
            key in name
            for key in (
                "马克思主义",
                "马克思",
                "哲学",
                "唯物",
                "辩证",
                "认识论",
                "商品与货币",
                "科学社会主义",
                "毛泽东思想",
            )
        ):
            return "马克思主义基本原理"
        if "新思想" in name or "习近平" in name:
            return "习近平新时代中国特色社会主义思想"
        if any(key in name for key in ("法治", "依法治国")):
            return "党的二十大精神"
        if any(key in name for key in ("立场", "忠诚", "敏锐", "鉴别")):
            return "政治立场与政治敏锐性"
        if any(
            key in name
            for key in (
                "文件",
                "会议",
                "讲话",
                "政策",
                "建设",
                "外交",
                "国防",
                "市场",
                "经济",
                "理论",
                "方针",
            )
        ):
            return "党和国家方针政策"
        return None

    if sub_category == "常识判断":
        if any(
            key in name
            for key in (
                "法律",
                "法规",
                "法理",
                "宪法",
                "民法",
                "刑法",
                "行政法",
                "诉讼法",
                "劳动法",
                "公务员法",
                "经济法",
                "条例",
                "法治",
            )
        ):
            return "法律常识"
        if any(key in name for key in ("历史", "文学", "文化", "公文", "民俗", "传统")):
            return "文化常识"
        if any(key in name for key in ("生物", "物理", "化学", "科技", "生活", "自然", "科学")):
            return "科技常识"
        if any(key in name for key in ("生态", "环境", "资源")):
            return "生态常识"
        if any(key in name for key in ("经济", "市场", "金融", "财政")):
            return "经济常识"
        if any(
            key in name
            for key in ("时政", "热点", "北京", "广东", "山东", "陕西", "上海", "事件", "时事")
        ):
            return "时政热点"
        if any(key in name for key in ("社会", "国情", "社情", "政府", "管理", "公共", "行政")):
            return "社会常识"
        return None

    if sub_category == "言语理解与表达":
        statement_keys = (
            "语句排序",
            "语句填空",
            "接语选择",
            "病句",
            "语句",
            "排序",
            "首句",
            "尾句",
            "横线",
            "承上启下",
            "前后呼应",
            "启下",
            "非首句",
            "总结前文",
            "概括后文",
            "7句",
            "4句",
            "指代",
            "代词",
            "句子",
            "时间脉络",
        )
        logical_keys = (
            "填空",
            "实词",
            "成语",
            "虚词",
            "关联词",
            "词的辨析",
            "词义",
            "搭配对象",
            "程度轻重",
            "感情色彩",
            "形象表达",
            "生动形象",
            "短语",
        )
        fragment_keys = (
            "主旨",
            "中心",
            "意图",
            "细节",
            "标题",
            "词句理解",
            "态度",
            "主题词",
            "转折",
            "因果",
            "并列",
            "对策",
            "观点",
            "背景",
            "举例",
            "多角度",
            "篇章",
            "概括",
            "提问",
            "故事",
            "散文",
            "文言文",
            "数据资料",
            "全文",
            "概述",
            "表述",
            "解释说明",
            "行文逻辑",
            "分述",
        )
        if any(key in name for key in statement_keys):
            return "语句表达"
        if any(key in name for key in logical_keys):
            return "逻辑填空"
        if any(key in name for key in fragment_keys):
            return "片段阅读"
        return None

    if sub_category == "数量关系":
        if any(
            key in name
            for key in ("数列", "递推", "作商", "因数分解", "幂次", "数字")
        ):
            return "数字推理"
        # Everything else in this old category is calculation / application.
        return "数学运算"

    if sub_category == "判断推理":
        if "定义" in name:
            return "定义判断"
        if any(
            key in name
            for key in (
                "种属",
                "组成",
                "对应",
                "功能",
                "原材料",
                "工艺",
                "词性",
                "偏正",
                "方式目的",
                "近义",
                "反义",
                "交叉",
                "全同",
                "包容",
                "拆词",
                "拆分",
                "语义",
                "语法",
                "类比",
                "主客体",
            )
        ):
            return "类比推理"
        if any(
            key in name
            for key in (
                "削弱",
                "加强",
                "论据",
                "论点",
                "搭桥",
                "拆桥",
                "假设",
                "前提",
                "因果",
                "他因",
                "实验",
                "论证",
                "翻译",
                "推理",
                "真假",
                "两真两假",
                "矛盾",
                "反对",
                "集合",
                "日常",
                "原因",
                "补充",
                "选非",
                "一拖五",
                "确定信息",
                "最大信息",
                "条件",
                "行动顺序",
                "先后",
                "排除",
                "排序",
                "材料",
                "问题",
                "时间",
                "求同",
                "求异",
            )
        ):
            return "逻辑判断"
        if any(
            key in name
            for key in (
                "图形",
                "面",
                "线",
                "点",
                "黑白",
                "对称",
                "位置",
                "样式",
                "平移",
                "旋转",
                "翻转",
                "遍历",
                "笔画",
                "元素",
                "小方块",
                "外框",
                "开闭",
                "曲直",
                "直角",
                "平行",
                "连线",
                "切点",
                "公共",
                "相邻",
                "相对",
                "画边",
                "立体",
                "空间",
                "六面体",
                "四面体",
                "三视图",
                "截面",
                "拼合",
                "折叠",
                "加减同异",
                "相加",
                "相减",
                "叠加",
                "数量",
                "属性",
                "标记",
                "框",
                "素",
                "个数",
                "部分",
                "内外",
                "结构",
                "排列",
                "碎片",
                "机械划分",
                "字母",
            )
        ):
            return "图形推理"
        return None

    if sub_category == "资料分析":
        if any(
            key in name
            for key in (
                "增长率",
                "增长量",
                "比重",
                "倍数",
                "平均数",
                "平均",
                "比值",
                "基期",
                "现期",
                "间隔",
                "年均",
                "百分",
                "比例",
            )
        ):
            return "统计术语"
        if any(key in name for key in ("计算", "找数", "加减", "追赶", "速算", "估算", "截位")):
            return "速算技巧"
        if any(key in name for key in ("资料", "文字", "统计表", "统计图", "表格", "图形", "混合资料")):
            return "资料类型"
        return None

    if sub_category == "科学推理":
        if any(key in name for key in ("溶液", "物质", "化学", "反应")):
            return "化学"
        if any(key in name for key in ("细胞", "光合", "生态", "生物")):
            return "生物"
        if any(key in name for key in ("地球", "自转", "公转", "气候", "气象", "地形", "地貌", "地理")):
            return "地理"
        if any(key in name for key in ("力", "运动", "电", "光", "压强", "摩擦", "功")):
            return "物理"
        return None

    return None


def connect_readonly() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"database not found: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def load_rows(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        SELECT kp.point_id, kp.point_name, kp.subject_id, kp.sub_category_id,
               sc.name AS sub_category, kp.level, kp.parent_id
        FROM knowledge_point kp
        LEFT JOIN sub_categories sc ON sc.id = kp.sub_category_id
        WHERE kp.point_id BETWEEN ? AND ?
        ORDER BY kp.point_id
        """,
        (LEGACY_MIN, LEGACY_MAX),
    ).fetchall()
    if len(rows) != EXPECTED_LEGACY:
        raise RuntimeError(
            f"expected {EXPECTED_LEGACY} legacy rows ({LEGACY_MIN}-{LEGACY_MAX}), "
            f"found {len(rows)}"
        )
    all_rows = {
        r["point_id"]: r
        for r in conn.execute(
            "SELECT point_id, point_name, subject_id, sub_category_id, level, parent_id "
            "FROM knowledge_point"
        )
    }
    subcat_names = {
        r["id"]: r["name"]
        for r in conn.execute("SELECT id, name FROM sub_categories")
    }
    return rows, all_rows, subcat_names


def make_resolver(all_rows, subcat_names, l2_index):
    memo: dict[int, tuple[str | None, str, str | None]] = {}

    def resolve(point_id: int, stack: tuple[int, ...] = ()) -> tuple[str | None, str, str | None]:
        if point_id in memo:
            return memo[point_id]
        if point_id in stack:
            return None, "none", "parent cycle"
        row = all_rows[point_id]
        subject = SUBJECT_NAMES.get(row["subject_id"])
        sub_category = subcat_names.get(row["sub_category_id"]) if row["sub_category_id"] else None
        if (
            subject is None
            or sub_category is None
            or (subject, sub_category) not in L2_GROUPS
        ):
            result = (None, "none", None)
            memo[point_id] = result
            return result

        name = row["point_name"]
        targets = allowed_targets(subject, sub_category, l2_index)
        allowed = L2_GROUPS[(subject, sub_category)]

        if name not in GENERIC_L3_NAMES:
            hits = targets.get(name, [])
            if len(hits) == 1:
                l2, l3 = hits[0]
                result = (l2, "exact", l3)
                memo[point_id] = result
                return result

            alias_target = ALIASES.get((subject, sub_category), {}).get(name)
            if alias_target:
                l2, _l3 = targets[alias_target][0]
                result = (l2, "alias", alias_target)
                memo[point_id] = result
                return result

            if name in allowed:
                result = (name, "l2name", name)
                memo[point_id] = result
                return result

        parent_id = row["parent_id"]
        if parent_id and parent_id != point_id and parent_id in all_rows:
            parent_l2, parent_source, _ = resolve(parent_id, stack + (point_id,))
            # A parent from another old sub_category must never leak into this
            # row's allowed L2 set.
            if parent_l2 is not None and parent_l2 in allowed and parent_source != "none":
                result = (parent_l2, "parent", all_rows[parent_id]["point_name"])
                memo[point_id] = result
                return result

        if name in GENERIC_L3_NAMES:
            result = (None, "none", None)
            memo[point_id] = result
            return result

        l2 = route_l2(subject, sub_category, name)
        if l2 is not None:
            result = (l2, "keyword", l2)
            memo[point_id] = result
            return result

        if len(allowed) == 1:
            result = (allowed[0], "single", allowed[0])
            memo[point_id] = result
            return result

        result = (None, "none", None)
        memo[point_id] = result
        return result

    return resolve


def hidden_result(old_id, name, subject, sub_category, note, confidence=0.1):
    return {
        "old_id": old_id,
        "old_name": name,
        "subject": subject,
        "sub_category": sub_category,
        "new_id": "",
        "new_name": "",
        "match_type": "hidden",
        "confidence": confidence,
        "note": note,
    }


def build_review_rows(rows, all_rows, subcat_names, l2_index) -> list[dict]:
    resolve = make_resolver(all_rows, subcat_names, l2_index)
    results: list[dict] = []
    for row in rows:
        old_id = row["point_id"]
        name = row["point_name"]
        subject = SUBJECT_NAMES.get(row["subject_id"], "")
        sub_category = row["sub_category"] or ""
        subcat_name = subcat_names.get(row["sub_category_id"]) if row["sub_category_id"] else None

        # 1) No old sub_category: never invent a parent.
        if subcat_name is None or (subject, subcat_name) not in L2_GROUPS:
            results.append(
                hidden_result(
                    old_id,
                    name,
                    subject,
                    sub_category,
                    "old sub_category is NULL or has no canonical L2 mapping; "
                    "hidden without inventing a parent",
                )
            )
            continue

        # 2) Noise / placeholders.
        if "缺失题" in name:
            results.append(
                hidden_result(
                    old_id,
                    name,
                    subject,
                    sub_category,
                    "noise/meta: 缺失题 placeholder, not a real knowledge point",
                )
            )
            continue
        if name in NOISE_NAMES:
            results.append(
                hidden_result(
                    old_id,
                    name,
                    subject,
                    sub_category,
                    f"noise/ambiguous token: {name!r} has no stable canonical mapping",
                )
            )
            continue
        hidden_key = (subcat_name, name)
        if hidden_key in HIDDEN_NAMES:
            results.append(
                hidden_result(old_id, name, subject, sub_category, HIDDEN_NAMES[hidden_key])
            )
            continue

        l2, source, detail = resolve(old_id)
        if l2 is None:
            results.append(
                hidden_result(
                    old_id,
                    name,
                    subject,
                    sub_category,
                    f"heuristic unavailable: cannot resolve a canonical L2 within "
                    f"old sub_category {subcat_name!r}; hidden",
                )
            )
            continue

        if source == "exact":
            results.append(
                {
                    "old_id": old_id,
                    "old_name": name,
                    "subject": subject,
                    "sub_category": sub_category,
                    "new_id": "",
                    "new_name": detail,
                    "match_type": "exact",
                    "confidence": 0.95,
                    "note": "",
                }
            )
            continue

        if source == "alias":
            results.append(
                {
                    "old_id": old_id,
                    "old_name": name,
                    "subject": subject,
                    "sub_category": sub_category,
                    "new_id": "",
                    "new_name": detail,
                    "match_type": "alias",
                    "confidence": 0.85,
                    "note": f"alias matched: {name} -> {detail}",
                }
            )
            continue

        # All remaining matches collapse into the target L2's canonical 其他.
        if source == "parent":
            note = (
                f"heuristic: parent {detail!r} resolved to L2 {l2!r}; "
                f"fallback to its 其他 leaf"
            )
            confidence = 0.6
        elif source == "l2name":
            note = (
                f"heuristic: legacy node name equals canonical L2 {l2!r}; "
                f"collapsed into its 其他 leaf"
            )
            confidence = 0.6
        elif source == "single":
            note = (
                f"heuristic: only canonical L2 {l2!r} under old sub_category "
                f"{subcat_name!r}; fallback to 其他"
            )
            confidence = 0.6
        else:  # keyword
            note = (
                f"heuristic: keyword routing placed {name!r} under L2 {l2!r}; "
                f"fallback to 其他"
            )
            confidence = 0.5

        results.append(
            {
                "old_id": old_id,
                "old_name": name,
                "subject": subject,
                "sub_category": sub_category,
                "new_id": "",
                "new_name": "其他",
                "match_type": "subcategory_other",
                "confidence": confidence,
                "note": note,
            }
        )

    return results


def write_csv(results: list[dict]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)


def run_make_aliases() -> int:
    tree = load_canonical_tree()
    l2_index, _l3_index = build_indexes(tree)

    # Validate every alias against the canonical tree before touching the DB.
    for subject, sub_category in L2_GROUPS:
        if subject not in tree:
            continue
        targets = allowed_targets(subject, sub_category, l2_index)
        validate_aliases(subject, sub_category, targets)

    conn = connect_readonly()
    try:
        rows, all_rows, subcat_names = load_rows(conn)
        results = build_review_rows(rows, all_rows, subcat_names, l2_index)
    finally:
        conn.close()

    if len(results) != EXPECTED_LEGACY:
        raise RuntimeError(f"expected {EXPECTED_LEGACY} output rows, got {len(results)}")

    write_csv(results)

    counts = Counter(item["match_type"] for item in results)
    print(f"wrote {OUT_PATH} ({len(results)} rows)")
    print("match_type distribution:")
    for match_type in ("exact", "alias", "subcategory_other", "hidden"):
        print(f"  {match_type}: {counts.get(match_type, 0)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T-02: build the 505-row taxonomy alias review CSV (read-only)."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["make-aliases"],
        help="command to run (aliases: --make-aliases)",
    )
    parser.add_argument(
        "--make-aliases",
        action="store_true",
        dest="make_aliases_flag",
        help="alias for the make-aliases command",
    )
    args = parser.parse_args(argv)

    if args.command == "make-aliases" or args.make_aliases_flag:
        return run_make_aliases()

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
