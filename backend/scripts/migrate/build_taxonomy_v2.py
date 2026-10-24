#!/usr/bin/env python3
"""Taxonomy migration helpers (T-02 alias CSV, T-03 tree, T-04 aliases, T-05 relations).

Four commands:

``make-aliases`` (T-02, read-only)    Build ``backend/data/audit/taxonomy_alias_review.csv`` for the 505 legacy
    PDF points. Opens ``backend/data/question_bank.db`` with ``mode=ro`` and
    ``PRAGMA query_only=ON``; never writes.

``build-tree`` (T-03)
    Dry-run by default: reads the production DB read-only and prints (optionally
    writes) a JSON report. With ``--apply --db <path>`` it materialises the
    canonical ``KNOWLEDGE_TREE_V2`` tree (518 nodes) in that database inside a
    single transaction, hides the 26 obsolete seed nodes and merges the 35
    legacy ``其他`` rows. ``--apply`` refuses the production database unless a
    future ``--allow-production`` flag is passed (not used in T-03).

``apply-aliases`` (T-04)
    Dry-run by default: read-only, prints (optionally writes) a JSON report.
    With ``--apply --db <path> --csv <path>`` it writes the 505 legacy alias
    rows in one transaction: ``status=0``, ``alias_of`` pointing at the
    canonical L3/其他 leaf (or ``NULL`` for hidden noise), and aligns
    ``sub_category_id`` for mapped rows. ``--apply`` refuses the production
    database unless a future ``--allow-production`` flag is passed (not used).
    ``alias_of`` is only touched through raw SQL.

``migrate-relations`` (T-05)
    Dry-run by default: read-only, prints (optionally writes) a JSON report.
    With ``--apply --db <path>`` it remaps ``question_knowledge`` rows from
    hidden legacy points to their canonical ``alias_of`` target (or a documented
    manual canonical L3), deduplicates ``(question_id, point_id)`` pairs and
    keeps unmapped relations in place as ``unmigrated``, all in one transaction.
    ``--apply`` refuses the production database unless a future
    ``--allow-production`` flag is passed (not used).

The canonical tree is read from ``KNOWLEDGE_TREE_V2`` in
``backend/scripts/admin/seed.py`` via AST literal parsing, so the script does
not import application modules or touch settings / sessions.

Usage:
    python backend/scripts/migrate/build_taxonomy_v2.py make-aliases
    python backend/scripts/migrate/build_taxonomy_v2.py --make-aliases
    python backend/scripts/migrate/build_taxonomy_v2.py build-tree
    python backend/scripts/migrate/build_taxonomy_v2.py build-tree \
        --apply --db <path> [--report <path>]
    python backend/scripts/migrate/build_taxonomy_v2.py apply-aliases [--db <path>]
    python backend/scripts/migrate/build_taxonomy_v2.py apply-aliases \
        --apply --db <path> --csv <path> [--report <path>]
    python backend/scripts/migrate/build_taxonomy_v2.py migrate-relations [--db <path>]
    python backend/scripts/migrate/build_taxonomy_v2.py migrate-relations \
        --apply --db <path> [--report <path>]

Output:
    backend/data/audit/taxonomy_alias_review.csv   (make-aliases)
    stdout JSON (build-tree), plus --report <path> when given
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"
SEED_PATH = BACKEND_DIR / "scripts" / "admin" / "seed.py"
OUT_PATH = BACKEND_DIR / "data" / "audit" / "taxonomy_alias_review.csv"

LEGACY_MIN = 127
LEGACY_MAX = 631
EXPECTED_LEGACY = 505

SEED_MAX = 126
EXPECTED_SEED = 126
EXPECTED_OTHER_ROWS = 35
CANONICAL_L2 = 91
CANONICAL_L3 = 427
CANONICAL_TOTAL = 518
OTHER_LEAF = "其他"

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


class AliasMappingError(RuntimeError):
    """A T-04 alias row cannot be mapped to exactly one canonical target."""


def is_canonical_point(point_id: int) -> bool:
    """Canonical rows are reused seed rows plus rows inserted after 631."""
    return point_id <= SEED_MAX or point_id > LEGACY_MAX


def build_canonical_index(rows) -> dict:
    """Index the visible canonical tree for alias mapping.

    ``rows`` accepts sqlite3.Row or dict rows with ``point_id``, ``point_name``,
    ``subject_id``, ``sub_category_id``, ``parent_id``, ``level``, ``status``
    and ``alias_of``. Only canonical rows with ``status=1 AND alias_of IS NULL``
    participate.
    """
    visible: list[dict] = []
    exact: dict[tuple, list[int]] = defaultdict(list)
    l2_by_name: dict[tuple[int, str], int] = {}
    l3_by_parent: dict[tuple, list[int]] = defaultdict(list)
    by_id: dict[int, dict] = {}

    for raw in rows:
        row = dict(raw)
        point_id = row["point_id"]
        if not is_canonical_point(point_id):
            continue
        if row.get("status") != 1 or row.get("alias_of") is not None:
            continue
        visible.append(row)
        by_id[point_id] = row
        if row["level"] == 3:
            exact[
                (row["subject_id"], row["sub_category_id"], row["point_name"])
            ].append(point_id)
            l3_by_parent[
                (row["subject_id"], row["parent_id"], row["point_name"])
            ].append(point_id)
        elif row["level"] == 2:
            key = (row["subject_id"], row["point_name"])
            existing = l2_by_name.get(key)
            if existing is not None and existing != point_id:
                raise AliasMappingError(
                    f"duplicate canonical L2 {key}: {existing} and {point_id}"
                )
            l2_by_name[key] = point_id

    return {
        "visible": visible,
        "by_id": by_id,
        "exact": exact,
        "l2_by_name": l2_by_name,
        "l3_by_parent": l3_by_parent,
    }


def find_exact_target(
    index: dict,
    old_id: int,
    subject_id: int,
    sub_category_id: int | None,
    new_name: str,
) -> dict:
    """Return the single canonical L3 matching (subject, sub-category, name)."""
    if not new_name:
        raise AliasMappingError(
            f"old_id {old_id}: exact/alias row has an empty new_name"
        )
    hits = index["exact"].get((subject_id, sub_category_id, new_name), [])
    if len(hits) != 1:
        raise AliasMappingError(
            f"old_id {old_id}: expected exactly one canonical L3 {new_name!r} "
            f"under subject {subject_id}/sub_category {sub_category_id}, "
            f"found {len(hits)}: {hits}"
        )
    return index["by_id"][hits[0]]


def find_other_target(index: dict, old_id: int, subject_id: int, l2_name: str) -> dict:
    """Return the canonical ``其他`` L3 leaf owned by the given canonical L2."""
    l2_id = index["l2_by_name"].get((subject_id, l2_name))
    if l2_id is None:
        raise AliasMappingError(
            f"old_id {old_id}: no canonical L2 {l2_name!r} under subject {subject_id}"
        )
    hits = index["l3_by_parent"].get((subject_id, l2_id, OTHER_LEAF), [])
    if len(hits) != 1:
        raise AliasMappingError(
            f"old_id {old_id}: expected one canonical 其他 leaf under L2 "
            f"{l2_name!r} ({l2_id}), found {len(hits)}: {hits}"
        )
    return index["by_id"][hits[0]]


def read_alias_csv(csv_path: str | Path) -> list[dict]:
    path = Path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_COLUMNS:
            raise RuntimeError(
                f"unexpected CSV columns in {path}: {reader.fieldnames!r}"
            )
        rows = list(reader)
    if len(rows) != EXPECTED_LEGACY:
        raise RuntimeError(
            f"expected {EXPECTED_LEGACY} CSV rows in {path}, found {len(rows)}"
        )
    return rows


def plan_alias_updates(
    csv_rows: list[dict],
    legacy_rows: dict[int, dict],
    all_rows: dict[int, dict],
    subcat_names: dict[int, str],
    l2_index: dict,
    canonical_index: dict,
) -> tuple[list[dict], Counter, list[int]]:
    """Turn T-02 CSV rows into ``status`` / ``alias_of`` updates.

    Rules mirror ``make-aliases``: exact/alias point at the canonical L3,
    ``subcategory_other`` points at the resolved L2's 其他 leaf, hidden rows get
    ``alias_of=NULL``. Any unmappable row fails loudly with its old_id.
    """
    resolve = make_resolver(all_rows, subcat_names, l2_index)
    updates: list[dict] = []
    match_counts: Counter = Counter()
    unresolved: list[int] = []

    for csv_row in csv_rows:
        try:
            old_id = int(csv_row["old_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AliasMappingError(f"invalid old_id in CSV row: {csv_row!r}") from exc

        match_type = csv_row.get("match_type") or ""
        match_counts[match_type] += 1
        legacy = legacy_rows.get(old_id)
        if legacy is None:
            raise AliasMappingError(f"old_id {old_id}: not a legacy row in the database")

        target: dict | None = None
        if match_type == "hidden":
            pass
        elif match_type in ("exact", "alias"):
            target = find_exact_target(
                canonical_index,
                old_id,
                legacy["subject_id"],
                legacy["sub_category_id"],
                csv_row.get("new_name") or "",
            )
        elif match_type == "subcategory_other":
            l2, _source, _detail = resolve(old_id)
            if l2 is None and legacy["point_name"] == OTHER_LEAF:
                parent_id = legacy["parent_id"]
                if parent_id and parent_id in all_rows:
                    l2, _source, _detail = resolve(parent_id)
            if l2 is None:
                unresolved.append(old_id)
                continue
            target = find_other_target(
                canonical_index, old_id, legacy["subject_id"], l2
            )
        else:
            raise AliasMappingError(
                f"old_id {old_id}: unknown match_type {match_type!r}"
            )

        updates.append(
            {
                "old_id": old_id,
                "match_type": match_type,
                "status": 0,
                "alias_of": target["point_id"] if target is not None else None,
                "sub_category_id": (
                    target["sub_category_id"]
                    if target is not None
                    else legacy["sub_category_id"]
                ),
            }
        )

    if unresolved:
        raise AliasMappingError(
            f"subcategory_other rows without a canonical L2 target: {unresolved}"
        )
    return updates, match_counts, unresolved


def project_alias_rows(rows: list[dict], updates: list[dict]) -> list[dict]:
    """Return a copy of ``rows`` with the planned updates applied in memory."""
    projected = [dict(row) for row in rows]
    by_id = {row["point_id"]: row for row in projected}
    for update in updates:
        row = by_id[update["old_id"]]
        row["status"] = 0
        row["alias_of"] = update["alias_of"]
        row["sub_category_id"] = update["sub_category_id"]
    return projected


def apply_alias_updates(
    conn: sqlite3.Connection, updates: list[dict], canonical_index: dict
) -> None:
    """Write every alias update inside one transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for update in updates:
            target_id = update["alias_of"]
            if target_id is not None:
                target = canonical_index["by_id"].get(target_id)
                if (
                    target is None
                    or target["status"] != 1
                    or target.get("alias_of") is not None
                ):
                    raise AliasMappingError(
                        f"old_id {update['old_id']}: target {target_id} is not a "
                        f"visible canonical point"
                    )
            conn.execute(
                "UPDATE knowledge_point SET status=0, alias_of=?, sub_category_id=? "
                "WHERE point_id=?",
                (
                    update["alias_of"],
                    update["sub_category_id"],
                    update["old_id"],
                ),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def build_alias_report(
    mode: str,
    db_path: Path,
    rows: list[dict],
    updates: list[dict],
    csv_count: int,
    match_counts: Counter,
) -> dict:
    legacy = [r for r in rows if LEGACY_MIN <= r["point_id"] <= LEGACY_MAX]
    return {
        "mode": mode,
        "db": str(db_path),
        "csv_rows": csv_count,
        "mapped": sum(1 for u in updates if u["alias_of"] is not None),
        "hidden": match_counts.get("hidden", 0),
        "alias_nonnull": sum(1 for r in legacy if r["alias_of"] is not None),
        "alias_null": sum(1 for r in legacy if r["alias_of"] is None),
        "status_zero_total": sum(1 for r in rows if r["status"] == 0),
        "visible_canonical": sum(
            1
            for r in rows
            if is_canonical_point(r["point_id"])
            and r["status"] == 1
            and r["alias_of"] is None
        ),
        "legacy_visible": sum(1 for r in legacy if r["status"] == 1),
        "total_rows": len(rows),
        "unresolved": [],
        "match_type_counts": dict(sorted(match_counts.items())),
    }


def _load_alias_rows(conn: sqlite3.Connection) -> tuple[list[dict], set[str]]:
    columns = {
        r["name"] for r in conn.execute("PRAGMA table_info(knowledge_point)")
    }
    if "status" not in columns:
        raise RuntimeError("knowledge_point.status is missing from the database")
    alias_expr = "alias_of" if "alias_of" in columns else "NULL AS alias_of"
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT point_id, point_name, subject_id, sub_category_id, parent_id, "
            f"level, sort_order, status, {alias_expr} FROM knowledge_point"
        )
    ]
    return rows, columns


def run_apply_aliases(
    apply: bool,
    db_path: str | None = None,
    csv_path: str | None = None,
    report_path: str | None = None,
    allow_production: bool = False,
) -> int:
    target = Path(db_path).resolve() if db_path else DB_PATH.resolve()

    if apply:
        if not db_path:
            raise SystemExit("apply-aliases --apply requires an explicit --db <path>")
        if target == DB_PATH.resolve() and not allow_production:
            raise SystemExit(
                "refusing to write the production database; pass a temp --db path"
            )
        if not target.exists():
            raise SystemExit(f"database not found: {target}")
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.isolation_level = None
    else:
        if not target.exists():
            raise FileNotFoundError(f"database not found: {target}")
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

    try:
        rows, columns = _load_alias_rows(conn)
        if apply and "alias_of" not in columns:
            raise SystemExit(
                "database has no alias_of column; run build-tree --apply on it first"
            )

        csv_rows = read_alias_csv(csv_path or OUT_PATH)
        tree = load_canonical_tree()
        l2_index, _l3_index = build_indexes(tree)
        subcat_names = {
            r["id"]: r["name"]
            for r in conn.execute("SELECT id, name FROM sub_categories")
        }
        all_rows = {r["point_id"]: r for r in rows}
        legacy_rows = {
            pid: r
            for pid, r in all_rows.items()
            if LEGACY_MIN <= pid <= LEGACY_MAX
        }
        if len(legacy_rows) != EXPECTED_LEGACY:
            raise RuntimeError(
                f"expected {EXPECTED_LEGACY} legacy rows, found {len(legacy_rows)}"
            )

        canonical_index = build_canonical_index(rows)
        canonical_visible = len(canonical_index["visible"])
        if canonical_visible != CANONICAL_TOTAL:
            if apply:
                raise RuntimeError(
                    f"expected {CANONICAL_TOTAL} visible canonical rows, found "
                    f"{canonical_visible}; run build-tree --apply first"
                )
            # Read-only readiness report for a DB that has no canonical tree yet
            # (e.g. production). No writes, no fabricated target ids.
            match_counts = Counter(
                (row.get("match_type") or "") for row in csv_rows
            )
            unresolved = [
                int(row["old_id"])
                for row in csv_rows
                if row.get("match_type") != "hidden"
            ]
            report = build_alias_report(
                "dry-run", target, rows, [], len(csv_rows), match_counts
            )
            report["unresolved"] = unresolved
            emit_report(report, report_path)
            return 0

        updates, match_counts, unresolved = plan_alias_updates(
            csv_rows, legacy_rows, all_rows, subcat_names, l2_index, canonical_index
        )
        if unresolved:
            raise AliasMappingError(
                f"subcategory_other rows without a canonical L2 target: {unresolved}"
            )

        if apply:
            apply_alias_updates(conn, updates, canonical_index)
            rows, _columns = _load_alias_rows(conn)
        else:
            rows = project_alias_rows(rows, updates)

        report = build_alias_report(
            "apply" if apply else "dry-run",
            target,
            rows,
            updates,
            len(csv_rows),
            match_counts,
        )
        emit_report(report, report_path)
        return 0
    finally:
        conn.close()


class RelationMappingError(RuntimeError):
    """A T-05 question_knowledge relation cannot be mapped safely."""


# Legacy hidden points without ``alias_of`` that have a documented canonical L3.
# Targets are resolved by (subject_id, sub_category_id, L3 name); ids are never
# hardcoded here. 124/125/126 are subcategory-wide placeholders and intentionally
# have no entry: their relations stay put and are reported as unmigrated.
MANUAL_TARGET_L3 = {
    17: "词句理解",
    18: "意图判断",
    25: "文字资料",
    26: "图形资料",
}


def _is_visible_canonical(row) -> bool:
    return row.get("status") == 1 and row.get("alias_of") is None


def _load_relation_inputs(conn: sqlite3.Connection):
    """Load knowledge_point rows and question_knowledge relations."""
    kp_columns = {
        r["name"] for r in conn.execute("PRAGMA table_info(knowledge_point)")
    }
    if "status" not in kp_columns:
        raise RuntimeError("knowledge_point.status is missing from the database")
    alias_expr = "alias_of" if "alias_of" in kp_columns else "NULL AS alias_of"
    points = [
        dict(r)
        for r in conn.execute(
            "SELECT point_id, point_name, subject_id, sub_category_id, parent_id, "
            f"level, status, {alias_expr} FROM knowledge_point"
        )
    ]

    relation_columns = {
        r["name"] for r in conn.execute("PRAGMA table_info(question_knowledge)")
    }
    if not {"question_id", "knowledge_point_id"} <= relation_columns:
        raise RuntimeError(
            "question_knowledge is missing question_id/knowledge_point_id"
        )
    has_id = "id" in relation_columns
    id_expr = "id" if has_id else "NULL AS id"
    relations = [
        dict(r)
        for r in conn.execute(
            f"SELECT {id_expr}, question_id, knowledge_point_id "
            "FROM question_knowledge ORDER BY question_id, knowledge_point_id"
        )
    ]
    return points, relations, has_id, "alias_of" in kp_columns


def relation_metrics(points, relations) -> dict:
    """Count relation totals and hidden-point usage for the current rows."""
    by_id = {int(p["point_id"]): p for p in points}
    pairs: set[tuple] = set()
    alias_nonnull = 0
    hidden_null = 0
    hidden_counter: Counter = Counter()
    for rel in relations:
        point_id = int(rel["knowledge_point_id"])
        row = by_id.get(point_id)
        if row is None:
            raise RelationMappingError(
                f"relation {rel.get('id')}: unknown knowledge point {point_id}"
            )
        pairs.add((rel["question_id"], point_id))
        if _is_visible_canonical(row):
            continue
        if row.get("alias_of") is not None:
            alias_nonnull += 1
        else:
            hidden_null += 1
            hidden_counter[point_id] += 1
    by_point = [
        {
            "point_id": point_id,
            "point_name": by_id[point_id]["point_name"],
            "count": count,
        }
        for point_id, count in sorted(
            hidden_counter.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "relations": len(relations),
        "distinct_pairs": len(pairs),
        "duplicate_pairs": len(relations) - len(pairs),
        "relations_to_alias_nonnull": alias_nonnull,
        "relations_to_hidden_null": hidden_null,
        "unmigrated_by_point": by_point,
    }


def plan_relation_migration(points, relations, canonical_index=None) -> dict:
    """Map legacy relations onto canonical points and deduplicate the result.

    Only canonical visible rows are left untouched. Hidden rows follow
    ``alias_of``; hidden rows without an alias are resolved through
    ``MANUAL_TARGET_L3`` when the canonical index is available, otherwise they
    are kept and counted as unmigrated. A remapped relation whose canonical
    pair already exists is deleted.
    """
    by_id = {int(p["point_id"]): p for p in points}
    for rel in relations:
        if int(rel["knowledge_point_id"]) not in by_id:
            raise RelationMappingError(
                f"relation {rel.get('id')}: unknown knowledge point "
                f"{rel['knowledge_point_id']}"
            )

    resolved_manual: dict[int, int] = {}
    manual_targets: dict[str, dict] = {}
    if canonical_index is not None:
        for old_id, l3_name in MANUAL_TARGET_L3.items():
            row = by_id.get(old_id)
            if row is None or _is_visible_canonical(row):
                continue
            if row.get("alias_of") is not None:
                continue
            hits = canonical_index["exact"].get(
                (row["subject_id"], row["sub_category_id"], l3_name), []
            )
            if len(hits) != 1:
                raise RelationMappingError(
                    f"old point {old_id} ({row['point_name']!r}): expected "
                    f"exactly one canonical L3 {l3_name!r} under subject "
                    f"{row['subject_id']}/sub_category {row['sub_category_id']}, "
                    f"found {len(hits)}: {hits}"
                )
            target = canonical_index["by_id"].get(hits[0])
            if target is None or not _is_visible_canonical(target):
                raise RelationMappingError(
                    f"old point {old_id}: manual target {hits[0]} is not a "
                    f"visible canonical point"
                )
            resolved_manual[old_id] = hits[0]
            manual_targets[str(old_id)] = {"id": hits[0], "name": l3_name}

    target_cache: dict[int, int | None] = {}

    def target_for(point_id: int) -> int | None:
        if point_id in target_cache:
            return target_cache[point_id]
        row = by_id[point_id]
        if _is_visible_canonical(row):
            target: int | None = point_id
        elif row.get("alias_of") is not None:
            alias_id = int(row["alias_of"])
            alias_row = by_id.get(alias_id)
            if alias_row is None or not _is_visible_canonical(alias_row):
                raise RelationMappingError(
                    f"point {point_id}: alias_of {alias_id} is not a visible "
                    f"canonical point"
                )
            target = alias_id
        else:
            target = resolved_manual.get(point_id)
        target_cache[point_id] = target
        return target

    before = relation_metrics(points, relations)
    live_pairs: set[tuple] = set()
    for rel in relations:
        live_pairs.add((rel["question_id"], int(rel["knowledge_point_id"])))

    actions: list[dict] = []
    migrated = deduped = unmigrated = 0
    unmigrated_counter: Counter = Counter()

    for rel in sorted(
        relations,
        key=lambda r: (
            r.get("id") if r.get("id") is not None else -1,
            r["question_id"],
            r["knowledge_point_id"],
        ),
    ):
        old_id = int(rel["knowledge_point_id"])
        target_id = target_for(old_id)
        if target_id is None:
            unmigrated += 1
            unmigrated_counter[old_id] += 1
            continue
        if target_id == old_id:
            continue

        question_id = rel["question_id"]
        live_pairs.discard((question_id, old_id))
        action = {
            "id": rel.get("id"),
            "question_id": question_id,
            "old_point_id": old_id,
            "target_id": target_id,
        }
        if (question_id, target_id) in live_pairs:
            actions.append({**action, "kind": "delete"})
            deduped += 1
        else:
            actions.append({**action, "kind": "update"})
            live_pairs.add((question_id, target_id))
            migrated += 1

    relations_after = len(relations) - deduped
    unmigrated_by_point = [
        {
            "point_id": point_id,
            "point_name": by_id[point_id]["point_name"],
            "count": count,
        }
        for point_id, count in sorted(
            unmigrated_counter.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "actions": actions,
        "relations_before": before["relations"],
        "distinct_pairs_before": before["distinct_pairs"],
        "duplicates_before": before["duplicate_pairs"],
        "migrated": migrated,
        "deduped": deduped,
        "unmigrated": unmigrated,
        "relations_after": relations_after,
        "distinct_pairs_after": len(live_pairs),
        "duplicate_pairs_after": relations_after - len(live_pairs),
        "relations_to_alias_nonnull": 0,
        "relations_to_hidden_null": unmigrated,
        "manual_targets": manual_targets,
        "unmigrated_by_point": unmigrated_by_point,
    }


def apply_relation_actions(
    conn: sqlite3.Connection, actions: list[dict], has_id: bool
) -> None:
    """Write delete/update actions in one transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for action in actions:
            if action["kind"] == "delete":
                if has_id and action["id"] is not None:
                    conn.execute(
                        "DELETE FROM question_knowledge WHERE id=?",
                        (action["id"],),
                    )
                else:
                    conn.execute(
                        "DELETE FROM question_knowledge WHERE question_id=? "
                        "AND knowledge_point_id=?",
                        (action["question_id"], action["old_point_id"]),
                    )
            else:
                if has_id and action["id"] is not None:
                    conn.execute(
                        "UPDATE question_knowledge SET knowledge_point_id=? WHERE id=?",
                        (action["target_id"], action["id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE question_knowledge SET knowledge_point_id=? "
                        "WHERE question_id=? AND knowledge_point_id=?",
                        (
                            action["target_id"],
                            action["question_id"],
                            action["old_point_id"],
                        ),
                    )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def build_relation_report(mode: str, db_path: Path, plan: dict) -> dict:
    return {
        "mode": mode,
        "db": str(db_path),
        "relations_before": plan["relations_before"],
        "distinct_pairs_before": plan["distinct_pairs_before"],
        "duplicates_before": plan["duplicates_before"],
        "migrated": plan["migrated"],
        "deduped": plan["deduped"],
        "unmigrated": plan["unmigrated"],
        "relations_after": plan["relations_after"],
        "distinct_pairs_after": plan["distinct_pairs_after"],
        "duplicate_pairs_after": plan["duplicate_pairs_after"],
        "relations_to_alias_nonnull": plan["relations_to_alias_nonnull"],
        "relations_to_hidden_null": plan["relations_to_hidden_null"],
        "manual_targets": plan["manual_targets"],
        "unmigrated_by_point": plan["unmigrated_by_point"],
    }


def build_relation_readiness_report(db_path: Path, points, relations) -> dict:
    """Read-only report for a DB without the canonical tree (e.g. production)."""
    metrics = relation_metrics(points, relations)
    return {
        "mode": "dry-run",
        "db": str(db_path),
        "relations_before": metrics["relations"],
        "distinct_pairs_before": metrics["distinct_pairs"],
        "duplicates_before": metrics["duplicate_pairs"],
        "migrated": 0,
        "deduped": 0,
        "unmigrated": metrics["relations_to_hidden_null"],
        "relations_after": metrics["relations"],
        "distinct_pairs_after": metrics["distinct_pairs"],
        "duplicate_pairs_after": metrics["duplicate_pairs"],
        "relations_to_alias_nonnull": metrics["relations_to_alias_nonnull"],
        "relations_to_hidden_null": metrics["relations_to_hidden_null"],
        "manual_targets": {},
        "unmigrated_by_point": metrics["unmigrated_by_point"],
    }


def run_migrate_relations(
    apply: bool,
    db_path: str | None = None,
    report_path: str | None = None,
    allow_production: bool = False,
) -> int:
    target = Path(db_path).resolve() if db_path else DB_PATH.resolve()

    if apply:
        if not db_path:
            raise SystemExit(
                "migrate-relations --apply requires an explicit --db <path>"
            )
        if target == DB_PATH.resolve() and not allow_production:
            raise SystemExit(
                "refusing to write the production database; pass a temp --db path"
            )
        if not target.exists():
            raise SystemExit(f"database not found: {target}")
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.isolation_level = None
    else:
        if not target.exists():
            raise FileNotFoundError(f"database not found: {target}")
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

    try:
        points, relations, has_id, has_alias = _load_relation_inputs(conn)
        if apply and not has_alias:
            raise SystemExit(
                "database has no alias_of column; run build-tree --apply on it first"
            )

        canonical_index = build_canonical_index(points)
        if len(canonical_index["visible"]) != CANONICAL_TOTAL:
            if apply:
                raise SystemExit(
                    f"expected {CANONICAL_TOTAL} visible canonical rows, found "
                    f"{len(canonical_index['visible'])}; run build-tree --apply first"
                )
            report = build_relation_readiness_report(target, points, relations)
            emit_report(report, report_path)
            return 0

        plan = plan_relation_migration(points, relations, canonical_index)
        if apply:
            apply_relation_actions(conn, plan["actions"], has_id)
            points, relations, _has_id, _has_alias = _load_relation_inputs(conn)
            metrics = relation_metrics(points, relations)
            report = build_relation_report("apply", target, plan)
            report["relations_after"] = metrics["relations"]
            report["distinct_pairs_after"] = metrics["distinct_pairs"]
            report["duplicate_pairs_after"] = metrics["duplicate_pairs"]
            report["relations_to_alias_nonnull"] = metrics[
                "relations_to_alias_nonnull"
            ]
            report["relations_to_hidden_null"] = metrics["relations_to_hidden_null"]
        else:
            report = build_relation_report("dry-run", target, plan)

        emit_report(report, report_path)
        return 0
    finally:
        conn.close()


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


def node_key(node: dict) -> tuple:
    return (
        node["subject_id"],
        node["sub_category_id"],
        node["level"],
        node["parent_name"],
        node["name"],
    )


def row_key(row, parent_names: dict) -> tuple:
    parent_name = None
    if row["level"] != 2 and row["parent_id"]:
        parent_name = parent_names.get(row["parent_id"])
    return (
        row["subject_id"],
        row["sub_category_id"],
        row["level"],
        parent_name,
        row["point_name"],
    )


def flatten_canonical(tree: dict, subject_map: dict, subcat_map: dict) -> list[dict]:
    nodes: list[dict] = []
    for subject, groups in tree.items():
        if subject not in subject_map:
            raise RuntimeError(f"subject missing from question_subject: {subject!r}")
        subject_id = subject_map[subject]
        for group, l2s in groups.items():
            if group not in subcat_map:
                raise RuntimeError(f"sub_category missing from sub_categories: {group!r}")
            subcat_id = subcat_map[group]
            for l2_order, (l2, l3s) in enumerate(l2s.items(), start=1):
                nodes.append(
                    {
                        "subject_id": subject_id,
                        "sub_category_id": subcat_id,
                        "level": 2,
                        "parent_name": None,
                        "name": l2,
                        "sort_order": l2_order,
                        "subject": subject,
                        "group": group,
                    }
                )
                for l3_order, l3 in enumerate(l3s, start=1):
                    nodes.append(
                        {
                            "subject_id": subject_id,
                            "sub_category_id": subcat_id,
                            "level": 3,
                            "parent_name": l2,
                            "name": l3,
                            "sort_order": l3_order,
                            "subject": subject,
                            "group": group,
                        }
                    )
    return nodes


def validate_canonical(nodes: list[dict]) -> dict:
    l2s = [n for n in nodes if n["level"] == 2]
    l3s = [n for n in nodes if n["level"] == 3]
    if (len(l2s), len(l3s), len(nodes)) != (CANONICAL_L2, CANONICAL_L3, CANONICAL_TOTAL):
        raise RuntimeError(
            f"canonical tree counts mismatch: L2={len(l2s)} L3={len(l3s)} "
            f"total={len(nodes)} (expected {CANONICAL_L2}/{CANONICAL_L3}/{CANONICAL_TOTAL})"
        )
    duplicates = [k for k, c in Counter(node_key(n) for n in nodes).items() if c > 1]
    if duplicates:
        raise RuntimeError(f"duplicate canonical sibling names: {duplicates}")

    l2_names = {(n["subject_id"], n["sub_category_id"], n["name"]) for n in l2s}
    if any(name == OTHER_LEAF for _s, _c, name in l2_names):
        raise RuntimeError("canonical tree must not contain an L2 named 其他")

    other_counts = Counter(
        (n["subject_id"], n["sub_category_id"], n["parent_name"])
        for n in l3s
        if n["name"] == OTHER_LEAF
    )
    missing = [key for key in l2_names if other_counts.get(key, 0) != 1]
    extra = [key for key in other_counts if key not in l2_names]
    if missing or extra:
        raise RuntimeError(f"其他 leaf rule violated: missing={missing} extra={extra}")

    by_subject = Counter(n["level"] for n in nodes)
    per_subject = {}
    for n in nodes:
        bucket = per_subject.setdefault(n["subject"], {2: 0, 3: 0})
        bucket[n["level"]] += 1
    return {
        "l2": len(l2s),
        "l3": len(l3s),
        "total": len(nodes),
        "by_subject": {k: dict(v) for k, v in per_subject.items()},
        "level_totals": dict(by_subject),
    }


def unique_alias_key(row, nodes: list[dict]) -> tuple | None:
    hits = [
        node_key(n)
        for n in nodes
        if n["subject_id"] == row["subject_id"]
        and n["sub_category_id"] == row["sub_category_id"]
        and n["name"] == row["point_name"]
    ]
    return hits[0] if len(hits) == 1 else None


def classify_seed_rows(seed_rows, parent_names: dict, nodes: list[dict]):
    by_key = {node_key(n): n for n in nodes}
    reused: list[tuple] = []
    obsolete: list[dict] = []
    for row in seed_rows:
        key = row_key(row, parent_names)
        if key in by_key:
            reused.append((row, by_key[key]))
        else:
            obsolete.append(
                {
                    "point_id": row["point_id"],
                    "point_name": row["point_name"],
                    "subject_id": row["subject_id"],
                    "sub_category_id": row["sub_category_id"],
                    "level": row["level"],
                    "alias_key": unique_alias_key(row, nodes),
                }
            )
    return reused, obsolete


def plan_legacy_others(other_rows, all_rows, subcat_names, l2_index) -> list[dict]:
    resolve = make_resolver(all_rows, subcat_names, l2_index)
    plans: list[dict] = []
    for row in other_rows:
        plan = {
            "point_id": row["point_id"],
            "subject_id": row["subject_id"],
            "parent_id": row["parent_id"],
            "l2": None,
            "reason": "",
        }
        if row["level"] == 2 or not row["parent_id"] or row["parent_id"] not in all_rows:
            plan["reason"] = "not an L3/L4 row with a resolvable parent"
            plans.append(plan)
            continue
        l2, _source, _detail = resolve(row["parent_id"])
        if l2 is None:
            plan["reason"] = "parent has no canonical L2 within its old sub_category"
            plans.append(plan)
            continue
        plan["l2"] = l2
        plans.append(plan)
    return plans


def canonical_other_index(nodes: list[dict], ids: dict) -> dict:
    out = {}
    for n in nodes:
        if n["level"] != 3 or n["name"] != OTHER_LEAF:
            continue
        key = (n["subject_id"], n["parent_name"])
        out[key] = {"node": n, "id": ids.get(node_key(n))}
    return out


def build_tree_report(
    mode: str,
    db_path: Path,
    counts: dict,
    reused: int,
    inserted: int,
    obsolete: list[dict],
    other_plans: list[dict],
    metrics: dict,
) -> dict:
    unresolved = sorted(p["point_id"] for p in other_plans if p["l2"] is None)
    merged = sum(1 for p in other_plans if p["l2"] is not None)
    return {
        "mode": mode,
        "db": str(db_path),
        "canonical_counts": counts,
        "reused_seed": reused,
        "inserted": inserted,
        "obsolete_seed_hidden": len(obsolete),
        "obsolete_seed": [
            {
                "point_id": o["point_id"],
                "point_name": o["point_name"],
                "level": o["level"],
                "alias_of": metrics["obsolete_alias"].get(o["point_id"]),
            }
            for o in obsolete
        ],
        "legacy_other_total": len(other_plans),
        "legacy_other_merged": merged,
        "legacy_other_unresolved_ids": unresolved,
        "status_zero_total": metrics["status_zero_total"],
        "visible_canonical": metrics["visible_canonical"],
        "pending_t04_legacy": metrics["pending_t04_legacy"],
        "total_rows": metrics["total_rows"],
        "duplicate_canonical_siblings": metrics["duplicate_canonical_siblings"],
    }


def _load_tree_inputs(conn: sqlite3.Connection):
    tree = load_canonical_tree()
    l2_index, _l3_index = build_indexes(tree)
    subject_map = {
        r["subject_name"]: r["subject_id"]
        for r in conn.execute("SELECT subject_name, subject_id FROM question_subject")
    }
    subcat_map = {
        r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM sub_categories")
    }
    return tree, l2_index, subject_map, subcat_map


def apply_tree(
    conn: sqlite3.Connection,
    nodes: list[dict],
    reused: list[tuple],
    obsolete: list[dict],
    other_plans: list[dict],
) -> dict:
    conn.execute("BEGIN IMMEDIATE")
    try:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(knowledge_point)")}
        if "alias_of" not in columns:
            conn.execute("ALTER TABLE knowledge_point ADD COLUMN alias_of INTEGER")

        ids: dict[tuple, int] = {
            node_key(node): row["point_id"] for row, node in reused
        }
        l2_ids: dict[tuple, int] = {}
        inserted = 0
        for node in nodes:
            key = node_key(node)
            if node["level"] == 2:
                parent_id = 0
            else:
                parent_id = l2_ids[(node["subject_id"], node["parent_name"])]
            point_id = ids.get(key)
            if point_id is None:
                point_id = _find_existing_canonical(conn, node)
            if point_id is None:
                cur = conn.execute(
                    "INSERT INTO knowledge_point (point_name, subject_id, parent_id, level, "
                    "description, sort_order, sub_category_id, status, alias_of) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, 1, NULL)",
                    (
                        node["name"],
                        node["subject_id"],
                        parent_id,
                        node["level"],
                        node["sort_order"],
                        node["sub_category_id"],
                    ),
                )
                if cur.lastrowid is None:
                    raise RuntimeError(f"insert did not return an id for {key}")
                point_id = int(cur.lastrowid)
                inserted += 1
            else:
                conn.execute(
                    "UPDATE knowledge_point SET parent_id=?, level=?, sort_order=?, "
                    "sub_category_id=?, status=1, alias_of=NULL WHERE point_id=?",
                    (
                        parent_id,
                        node["level"],
                        node["sort_order"],
                        node["sub_category_id"],
                        point_id,
                    ),
                )
            ids[key] = point_id
            if node["level"] == 2:
                l2_ids[(node["subject_id"], node["name"])] = point_id

        obsolete_alias: dict[int, int | None] = {}
        for item in obsolete:
            alias_id = ids.get(item["alias_key"]) if item["alias_key"] else None
            obsolete_alias[item["point_id"]] = alias_id
            conn.execute(
                "UPDATE knowledge_point SET status=0, alias_of=? WHERE point_id=?",
                (alias_id, item["point_id"]),
            )

        other_index = canonical_other_index(nodes, ids)
        for plan in other_plans:
            if plan["l2"] is None:
                conn.execute(
                    "UPDATE knowledge_point SET status=0, alias_of=NULL WHERE point_id=?",
                    (plan["point_id"],),
                )
                continue
            target = other_index.get((plan["subject_id"], plan["l2"]))
            if target is None or target["id"] is None:
                raise RuntimeError(
                    f"canonical 其他 leaf missing for {plan['subject_id']}/{plan['l2']!r}"
                )
            conn.execute(
                "UPDATE knowledge_point SET status=0, alias_of=?, sub_category_id=? "
                "WHERE point_id=?",
                (target["id"], target["node"]["sub_category_id"], plan["point_id"]),
            )

        report = collect_apply_metrics(conn, ids, obsolete, other_plans, inserted)
        conn.execute("COMMIT")
        return {"inserted": inserted, "ids": ids, "obsolete_alias": obsolete_alias, **report}
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _find_existing_canonical(conn: sqlite3.Connection, node: dict) -> int | None:
    rows = conn.execute(
        "SELECT kp.point_id, p.point_name AS parent_name FROM knowledge_point kp "
        "LEFT JOIN knowledge_point p ON p.point_id = kp.parent_id "
        "WHERE kp.point_id > ? AND kp.subject_id=? AND kp.sub_category_id=? "
        "AND kp.level=? AND kp.point_name=?",
        (
            LEGACY_MAX,
            node["subject_id"],
            node["sub_category_id"],
            node["level"],
            node["name"],
        ),
    ).fetchall()
    candidates = [
        r["point_id"]
        for r in rows
        if node["level"] == 2 or r["parent_name"] == node["parent_name"]
    ]
    if len(candidates) > 1:
        raise RuntimeError(
            f"ambiguous existing canonical rows for {node_key(node)}: {candidates}"
        )
    return candidates[0] if candidates else None


def collect_apply_metrics(
    conn: sqlite3.Connection,
    ids: dict,
    obsolete: list[dict],
    other_plans: list[dict],
    inserted: int,
) -> dict:
    canonical_ids = set(ids.values())
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT point_id, point_name, subject_id, sub_category_id, parent_id, "
            "level, status, alias_of FROM knowledge_point"
        )
    ]
    visible = [
        r
        for r in rows
        if r["point_id"] in canonical_ids and r["status"] == 1 and r["alias_of"] is None
    ]
    dup = Counter(
        (r["subject_id"], r["sub_category_id"], r["parent_id"], r["point_name"])
        for r in visible
    )
    other_ids = {p["point_id"] for p in other_plans}
    by_id = {r["point_id"]: r for r in rows}
    return {
        "status_zero_total": sum(1 for r in rows if r["status"] == 0),
        "visible_canonical": len(visible),
        "pending_t04_legacy": sum(
            1
            for r in rows
            if LEGACY_MIN <= r["point_id"] <= LEGACY_MAX
            and r["status"] == 1
            and r["point_id"] not in other_ids
        ),
        "total_rows": len(rows),
        "duplicate_canonical_siblings": sum(1 for c in dup.values() if c > 1),
        "inserted": inserted,
        "obsolete_alias": {
            o["point_id"]: by_id[o["point_id"]]["alias_of"] for o in obsolete
        },
        "legacy_other_merged": sum(
            1 for pid in other_ids if by_id[pid]["alias_of"] is not None
        ),
    }


def run_build_tree(
    apply: bool,
    db_path: str | None = None,
    report_path: str | None = None,
    allow_production: bool = False,
) -> int:
    target = Path(db_path).resolve() if db_path else DB_PATH.resolve()
    if apply:
        if not db_path:
            raise SystemExit("build-tree --apply requires an explicit --db <path>")
        if target == DB_PATH.resolve() and not allow_production:
            raise SystemExit(
                "refusing to write the production database; pass a temp --db path"
            )
        if not target.exists():
            raise SystemExit(f"database not found: {target}")
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.isolation_level = None
    else:
        if not target.exists():
            raise FileNotFoundError(f"database not found: {target}")
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

    try:
        tree, l2_index, subject_map, subcat_map = _load_tree_inputs(conn)
        subcat_names = {sid: name for name, sid in subcat_map.items()}
        nodes = flatten_canonical(tree, subject_map, subcat_map)
        counts = validate_canonical(nodes)

        all_rows = {
            r["point_id"]: dict(r)
            for r in conn.execute(
                "SELECT point_id, point_name, subject_id, sub_category_id, level, "
                "parent_id, sort_order, status FROM knowledge_point"
            )
        }
        parent_names = {pid: r["point_name"] for pid, r in all_rows.items()}
        seed_rows = [r for pid, r in all_rows.items() if pid <= SEED_MAX]
        if len(seed_rows) != EXPECTED_SEED:
            raise RuntimeError(
                f"expected {EXPECTED_SEED} seed rows, found {len(seed_rows)}"
            )
        seed_rows.sort(key=lambda r: r["point_id"])
        other_rows = [
            r
            for pid, r in sorted(all_rows.items())
            if r["point_name"] == OTHER_LEAF and LEGACY_MIN <= pid <= LEGACY_MAX
        ]
        if len(other_rows) != EXPECTED_OTHER_ROWS:
            raise RuntimeError(
                f"expected {EXPECTED_OTHER_ROWS} legacy 其他 rows, found {len(other_rows)}"
            )

        reused, obsolete = classify_seed_rows(seed_rows, parent_names, nodes)
        other_plans = plan_legacy_others(
            other_rows, all_rows, subcat_names, l2_index
        )
    except Exception:
        conn.close()
        raise

    if not apply:
        conn.close()
        inserted = len(nodes) - len(reused)
        metrics = project_dry_run_metrics(
            all_rows, nodes, obsolete, other_plans, inserted
        )
        report = build_tree_report(
            "dry-run", target, counts, len(reused), inserted, obsolete, other_plans, metrics
        )
        emit_report(report, report_path)
        return 0

    result = apply_tree(conn, nodes, reused, obsolete, other_plans)
    conn.close()
    report = build_tree_report(
        "apply",
        target,
        counts,
        len(reused),
        result["inserted"],
        obsolete,
        other_plans,
        result,
    )
    emit_report(report, report_path)
    return 0


def project_dry_run_metrics(all_rows, nodes, obsolete, other_plans, inserted) -> dict:
    other_ids = {p["point_id"] for p in other_plans}
    obsolete_ids = {o["point_id"] for o in obsolete}
    status_zero = 0
    pending_t04 = 0
    total = len(all_rows) + inserted
    for pid, row in all_rows.items():
        hide = pid in other_ids or pid in obsolete_ids
        status_zero += 1 if (row["status"] == 0 or hide) else 0
        if LEGACY_MIN <= pid <= LEGACY_MAX and row["status"] == 1 and pid not in other_ids:
            pending_t04 += 1
    return {
        "status_zero_total": status_zero,
        "visible_canonical": len(nodes),
        "pending_t04_legacy": pending_t04,
        "total_rows": total,
        "duplicate_canonical_siblings": 0,
        "inserted": inserted,
        "obsolete_alias": {o["point_id"]: None for o in obsolete},
    }


def emit_report(report: dict, report_path: str | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


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
        description=(
            "Taxonomy helpers: T-02 alias review CSV, T-03 canonical tree build, "
            "T-04 legacy alias hide."
        )
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=[
            "make-aliases",
            "build-tree",
            "apply-aliases",
            "migrate-relations",
        ],
        help="command to run (aliases: --make-aliases)",
    )
    parser.add_argument(
        "--make-aliases",
        action="store_true",
        dest="make_aliases_flag",
        help="alias for the make-aliases command",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="build-tree/apply-aliases/migrate-relations: write to --db instead of dry-run",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="build-tree/apply-aliases/migrate-relations: database path (required with --apply)",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help=f"apply-aliases: alias review CSV (default {OUT_PATH})",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="build-tree/apply-aliases/migrate-relations: also write the JSON report to this path",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        dest="allow_production",
        help="reserved: allow --apply against the production database (unused in T-03)",
    )
    args = parser.parse_args(argv)

    if args.command == "make-aliases" or args.make_aliases_flag:
        return run_make_aliases()

    if args.command == "build-tree":
        return run_build_tree(
            apply=args.apply,
            db_path=args.db,
            report_path=args.report,
            allow_production=args.allow_production,
        )

    if args.command == "apply-aliases":
        return run_apply_aliases(
            apply=args.apply,
            db_path=args.db,
            csv_path=args.csv,
            report_path=args.report,
            allow_production=args.allow_production,
        )

    if args.command == "migrate-relations":
        return run_migrate_relations(
            apply=args.apply,
            db_path=args.db,
            report_path=args.report,
            allow_production=args.allow_production,
        )

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
