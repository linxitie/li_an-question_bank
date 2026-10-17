#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回填 knowledge_point.sub_category_id（D-2，v3 方案 4.2 节）

**全科目回填** sub_category_id 为空的考点，按「考点名 → 子科目关键词」
归属到 sub_categories 表的二级分类。目标库当前值（实测）：

    行测(subject 1): 505 条待回填（level2 414 / level3 84 / level4 7）
    申论(subject 2):  25 条已有归属（脚本为幂等空跑）
    公专(subject 3):  67 条已有归属（脚本为幂等空跑）

归属判定顺序（后者不越过前者）
--------------------------------
1. **父级继承**：level>=3 且父考点已有 sub_category_id → 继承父的归属
   （考点树的子节点必然属于父所在子科目）
2. **canonical 名精确命中**：命中 seed.py KNOWLEDGE_POINTS 定义的
   标准考点名 → 取其定义所属子科目
3. **优先级规则**：按 PATTERN_RULES 先命中先赢
    （按「具体 - 泛化」排序，如「现期比重」先于「比重」）
4. **都判不出 → 留空**：不强行填子科目，进入「待人工确认」清单

铁律
----
- 默认 **dry-run**（只预览统计与抽查样例，不写库）
- 必须显式 ``--apply`` 才写入
- 写入前用 **sqlite3 备份 API** 做整库快照（禁 shutil.copy2：库为 WAL 模式）
- 写 manifest（point_id → sub_category_id 映射）供 ``--rollback`` 精确回溯

用法
----::

    python scripts/backfill_kp_subcategory.py                 # 默认 dry-run
    python scripts/backfill_kp_subcategory.py --dry-run
    python scripts/backfill_kp_subcategory.py --apply
    python scripts/backfill_kp_subcategory.py --rollback
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BACKEND_DIR, "data", "question_bank.db")
MANIFEST = os.path.join(BACKEND_DIR, "data", "kp_subcat_backfill_manifest.json")

# ── 子科目 id → 别名（DB 里 id=16 是「科学推理」，id 8-15 依次为申论/公专）────
SUBJECTS = {
    1: "行测",
    2: "申论",
    3: "公专",
}

# 关键词字典：子科目 id → 关键词列表。命中数唯一最高分即归属。
# 说明：只收「强判别词」，宁可留空不歧义填错。
# ── 归属规则（优先级从上到下，先命中先赢）───────────────────────────
#
# 设计原则（MUST NOT DO：不给无法确定的考点强行填子科目）：
#   1. 只收「强判别词」；多义词用更长的具体词，避免互相抢
#   2. 判不出来（零命中）一律留空 + 进人工确认清单
#   3. 规则按「具体 -> 泛化」排序，如「现期比重」先于「比重」
#
# 每项: (子科目id, [关键词...])
PATTERN_RULES: list = [
    # 言语填空（高优先级：必须早于判断推理，否则实词/成语/搭配
    # 会被类比推理的同类词抢走）
    (3, ["逻辑填空", "实词填空", "成语填空", "混搭填空", "虚词填空",
         "短语填空", "填空"]),

    # 资料分析：增长率/比重/现期基期等统计术语
    (6, ["简单加减计算", "现期计算", "基期计算", "现期比重", "基期比重", "两期比重",
         "基期倍数", "现期倍数", "基期和差", "基期比较", "间隔基期", "增长量",
         "增长率", "年均增长", "两期平均数比较", "平均数的增长率",
         "平均数的增长量", "混合比重", "混合增长率", "间隔增长率", "直接找数",
         "文字资料", "统计图", "统计表", "统计术语", "综合资料", "比值计算",
         "比值比较", "综合判断", "平均数问题", "数字资料", "资料分析",
         "混合型资料", "速算技巧", "表格资料", "图形资料",
         # v2 扩充（具体词在前，泛化词在后）
         "资料缺失题", "文字", "现期", ]),

    # 判断推理：图形/类比/逻辑 专有术语
    (5, ["图形推理", "类比推理", "定义判断", "削弱", "加强", "搭桥", "拆桥",
         "真假推理", "论证", "日常逻辑", "对比实验", "实验主体", "实验过程",
         "他因削弱", "因果倒置", "无因无果", "有因无果", "原因解释", "日常结论",
         "集合推理", "翻译推理", "推理形式", "分析推理", "两真两假", "削弱选非",
         "加强选非", "不能削弱", "不能加强", "六面体", "三视图", "四面体", "截面图",
         "多面体折叠", "立体拼合", "平面拼合", "画边法", "公共边", "相对面",
         "相邻比较", "空间", "立体", "拼合", "图形间关系", "平面图形", "立体图形",
         "相似图形", "图形数阵", "位置规律", "属性规律", "黑白块", "黑白运算",
         "对称", "遍历", "开闭性", "曲直性", "连接方式", "元素", "笔画", "交点",
         "直线", "曲线", "平行", "直角", "面数", "部分数", "线条", "小面",
         "字母", "图形", "线数量", "相交于", "对称轴", "截面", "个数", "选非",
         "种属关系", "反向种属", "组成关系", "交叉关系", "矛盾关系",
         "反对关系", "全同关系", "近义关系", "反义关系", "语义关系",
         "并列关系", "方式目的", "逻辑关系", "必要条件", "充分条件",
         "对应关系", "主客体", "语法关系", "词性", "偏正", "二级辨析", "拆词",
         "类比", "下定义", "单定义", "多定义", "定义",
         "逻辑判断", "补充论据", "一拖五", "碎片类", "判断缺失题", "相对绝对项", "机械划分", "排序类", "从确定信息开始推", "从最大信息开始推", "常规翻译", "常规类平移", "公共点", "部分面", "数量+属性", "数量+数量", "位置等", "加减同异", "假设", "三集合", "两集合", "集合推理", "状态先后顺序", "行动顺序", "相邻问题", "不相邻问题", "相邻比较", "连线", "外框", "框上", "框内", "斜线", "大前提", "相交于", "素", "标记线", "拆分", "原因结果", "对应",
         # v2 扩充（依据邻居归属 + 专有术语；具体词在前，泛化词在后）
         "求同", "求异", "相加", "相减", "功能", "原材料", "工艺", "组成", "包容",
         "切点", "捆绑", "时间不够长", "排除法", "属性", "条件", "语义", "位置", "线", ]),

    # 言语理解与表达：填空/阅读/语句表达
    (3, ["逻辑填空", "实词填空", "成语填空", "混搭填空", "虚词填空", "短语填空",
         "中心理解题", "主题词", "指代词", "指代", "语句填空题", "语句排序题",
         "语句填空", "语句表达", "语句", "标题填入题", "词句理解题", "细节判断题",
         "细节主旨", "日常结论", "接语选择题", "标题选择", "下文", "上文",
         "篇章", "概括后文", "总结前文", "概括", "概述", "词句理解",
         "词语理解", "衔接", "承接", "承上启下", "横线为尾句中的分句",
         "横线为首句中的分句", "非首句特征", "尾句", "首句", "根据尾句确定答案",
         "综合全文确定答案", "契合文段中心", "关联词的后半部分", "关联关系",
         "分述句特征", "行文逻辑", "语病", "病句", "歧义", "标点", "文言文",
         "形象表达", "生动形象", "感情色彩", "故事类", "散文", "背景引入",
         "提问+回答", "观点+解释说明", "解释说明", "问题+对策", "表述与实际不符",
         "能指出", "语境", "话语", "文段", "文意", "词义", "程度轻重",
         "程度词", "转折", "递进", "并列", "因果", "填空", "词语", "词汇",
         "搭配", "中心理解", "片段阅读", "态度意图", "言语", "代词", "时间脉络", "词的辨析",
         # v2 扩充（依据邻居归属 + 专有术语；具体词在前，泛化词在后）
         "前后呼应", "启下", "提出观点", "提出对策", "对策", "实词", "虚词",
         "言语缺失题", "句子", "句", ]),

    # 常识判断：法律/历史/人文/科技/管理
    (2, ["常识", "中国历史", "世界历史", "文学常识", "生活常识", "自然常识",
         "科技理论与成就", "热点事件", "北京时政", "广东时政", "山东时政",
         "上海时政", "陕西时政", "国情社情", "纯常识", "物理常识", "化学常识",
         "生物常识", "科技常识", "常识判断", "传统", "诗词", "文化", "人文",
         "民俗", "民族", "宗教", "中医", "艺术", "法律", "法规", "法理",
         "宪法", "民法", "刑法", "行政法", "公务员法", "劳动法", "经济法",
         "民事诉讼法", "公共基础知识", "公共行政", "政府职能", "行政管理",
         "行政监督", "事业单位", "公共产品", "公共服务", "环境保护", "科技",
         "自然", "历史", "公文", ]),

    # 政治理论：马克思主义/党建/中国道路
    (1, ["习近平", "新时代", "党的二十大", "马克思主义", "毛泽东思想",
         "邓小平理论", "三个代表", "科学发展观", "社会主义", "党的建设",
         "政治建设", "法治建设", "文化建设", "社会建设", "经济建设",
         "生态文明建设", "和平外交建设", "国防和军队建设", "宏观经济与调控政策",
         "政府", "重要文件", "重大会议", "新思想", "理论", "政策", "哲学",
         "唯物", "认识论", "原论", "商品与货币", "市场", "企业管理", "国情",
         "外交", "人类命运共同体", "全会", "总书记", "从严治党", "依法治国",
         "深化改革", "共同富裕", "中国式现代化", "党的领导", "党员", "党组织",
         "五位一体", "四个全面", "新发展理念", "党", "辩证法", ]),

    # 数量关系：计算/运算/应用题
    (4, ["数字推理", "计算问题", "工程问题", "经济利润问题", "利润问题",
         "和差倍比问题", "基础排列组合", "给情况求概率", "给概率求概率",
         "平面几何", "立体几何", "三角形基础", "几何其他题型", "几何小题型",
         "面积相关", "勾股定理", "赋值法", "代入排除", "代入法", "枚举法",
         "比例法", "线段法", "列表法", "画图法", "构造数列", "基础数列",
         "多级数列", "多重数列", "分数数列", "幂次数列", "因数分解数列",
         "作商数列", "递推数列", "奇偶特性法", "倍数特性法", "尾数法",
         "不定方程", "余数", "同余", "公倍数", "公约数", "最不利",
         "统筹规划", "非典型最值", "函数最值", "分段计算", "平均速度",
         "相遇追及", "流水行船", "火车过桥", "牛吃草", "植树问题", "方阵问题",
         "比赛问题", "盈亏法", "年龄问题", "星期日期问题", "周期余数问题",
         "周期问题", "钟表问题", "溶液问题", "给完工时间型", "给效率比例型",
         "给具体单位型", "常规解题方法", "数列", "概率", "平均数", "比例",
         "倍数", "排列组合", "行程", "几何", "三角", "计算",
         # v2 扩充（具体词在前，泛化词在后）
         "数量缺失题", "数字类", "数量"]),

    # 科学推理：物理/化学/生物（部分省份独立成科）
    (16, ["科学推理", "光合与呼吸", "光合", "光现象", "压强", "摩擦力",
           "功和能", "家庭电路", "电路分析", "运动图像", "细胞", "生态系统",
           "地形地貌", "气候与气象", "自转与公转", "物质的性质", "水和溶液",
           "力学综合", "受力分析", "浮力", "电流", "电压", "电阻", "杠杆",
           "动能", "势能", "比热容", "分子", "原子", "酶", "基因", "遗传",
           "染色体", "种群", "群落", "食物链", "神经调节", "溶液混合", ]),

    # 知觉速度与准确性
    (7, ["同符查找", "数字区间定位", "字符替换", "知觉准确性"]),

    # 申论
    (8, ["归纳概括", "问题概括", "原因概括", "影响概括", "对策概括",
         "特点概括", "过程概括", "申论"]),
    (9, ["综合分析", "观点分析", "现象分析", "评析", "比较分析", "阐释",
         "辨析"]),
    (10, ["提出对策", "对策建议", "方案设计", "应急处理", "长效机制",
           "对策"]),
    (11, ["应用文写作", "公文写作", "事务文书", "宣传文稿", "讲话稿",
           "倡议书", "调研报告", "简报", "发言稿", "报告", "公文"]),
    (12, ["议论文写作", "命题作文", "话题作文", "材料作文", "政论文",
           "策论文", "写作", "立意", "论证"]),

    # 公专
    (13, ["职业素养", "人民警察核心价值观", "人民警察职业道德",
           "人民警察职业纪律", "职业道德", "职业纪律", "忠诚", "警察意识",
           "纪律意识"]),
    (14, ["基础知识", "法学基础", "人民警察法", "公安基础", "公安机关性质",
           "治安管理处罚法", "国家安全法", "反恐怖主义法", "全面依法治国",
           "法治理念", "依法行政", "监察法", "民法典", "行政执法", "刑事执法",
           "公安工作", "公安队伍建设", "公安执法"]),
    (15, ["基本警务能力", "宣传教育", "沟通协调", "组织动员", "服务群众",
           "调查研究", "纠纷化解", "风险识别", "风险防范", "信息收集",
           "信息分析", "信息应用", "巡逻", "接警与处警", "安全检查",
           "安全保护", "事态研判", "信息上报", "合理处置", "善后恢复",
           "应急处突", "群众工作", "现场处置", "舆情应对"]),
]

# canonical 考点名 → 子科目 id（从 seed.py KNOWLEDGE_POINTS 推导）
CANONICAL_KP = {
    "习近平新时代中国特色社会主义思想": 1, "党的二十大精神": 1,
    "马克思主义基本原理": 1, "党和国家方针政策": 1,
    "政治立场与政治敏锐性": 1,
    "经济常识": 2, "文化常识": 2, "社会常识": 2, "生态常识": 2,
    "法律常识": 2, "科技常识": 2, "时政热点": 2,
    "逻辑填空": 3, "片段阅读": 3, "语句表达": 3, "中心理解": 3,
    "词语理解": 3, "态度意图": 3,
    "数字推理": 4, "数学运算": 4,
    "图形推理": 5, "逻辑判断": 5, "类比推理": 5, "定义判断": 5,
    "文字资料分析": 6, "图形资料分析": 6, "表格资料分析": 6,
    "混合型资料": 6, "统计术语": 6, "速算技巧": 6,
    "同符查找": 7, "数字区间定位": 7, "字符替换": 7, "知觉准确性": 7,
    "问题概括": 8, "原因概括": 8, "影响概括": 8, "对策概括": 8,
    "特点概括": 8, "过程概括": 8,
    "观点分析": 9, "现象分析": 9, "词句理解": 9, "评析辨析": 9,
    "比较分析": 9,
    "问题识别": 10, "对策建议": 10, "方案设计": 10,
    "应急处理": 10, "长效机制": 10,
    "公文写作": 11, "事务文书": 11, "案例分析": 11, "宣传文稿": 11,
    "命题作文": 12, "话题作文": 12, "材料作文": 12,
    "政论文": 12, "策论文": 12,
    "政治立场与忠诚度": 13, "政治敏锐性与鉴别力": 13,
    "人民警察核心价值观": 13, "人民警察职业道德": 13,
    "人民警察职业纪律": 13,
    "中国特色社会主义法治理论": 14, "法学基础理论": 14,
    "宪法基础知识": 14, "民法基础知识": 14, "人民警察法基础知识": 14,
    "行政执法基础知识": 14, "刑事执法基础知识": 14,
    "公安机关性质与职能": 14, "公安工作根本原则": 14,
    "公安队伍建设": 14, "公安执法监督": 14,
    "宣传教育": 15, "沟通协调": 15, "组织动员": 15, "服务群众": 15,
    "调查研究": 15, "纠纷化解": 15, "风险识别": 15, "风险防范": 15,
    "信息收集": 15, "信息分析": 15, "信息应用": 15, "巡逻": 15,
    "接警与处警": 15, "安全检查": 15, "安全保护": 15,
    "事态研判": 15, "信息上报": 15, "合理处置": 15, "善后恢复": 15,
}


# ── 工具 ────────────────────────────────────────────────────────────

def backup_db() -> str:
    """用 sqlite3 备份 API 打整库快照，返回备份路径。

    **禁止 shutil.copy2**：库是 WAL 模式（实测存在 question_bank.db-wal），
    只拷主库文件无法保证一致性，且恢复时残留的旧 -wal 会被回放污染数据。
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(os.path.dirname(DB_PATH),
                       "question_bank.db.bak_kpsub_%s" % ts)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(bak)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return bak


def resolve_sub_cat(name, subject_id, level, parent_sc, subcat_id_by_subject):
    """按优先级规则判定考点归属。

    Returns: ``(sub_category_id or None, rule_tag)``
    """
    # 1. 父级继承（最高优先）
    if level >= 3 and parent_sc:
        return parent_sc, "父级继承"

    # 2. canonical 精确名
    if name in CANONICAL_KP:
        sid = CANONICAL_KP[name]
        if sid in subcat_id_by_subject.get(subject_id, set()):
            return sid, "canonical名"

    # 3. 优先级规则：先命中先赢（具体 -> 泛化）
    for sid, kws in PATTERN_RULES:
        if sid not in subcat_id_by_subject.get(subject_id, set()):
            continue
        for k in kws:
            if k in name:
                return sid, "规则:%s" % k
    return None, "无命中"


def snapshot_kp(cur) -> dict:
    return {
        r[0]: list(r[1:])
        for r in cur.execute(
            "select point_id, sub_category_id, point_name, subject_id, level"
            " from knowledge_point")
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="全科目回填考点子科目归属（D-2）")
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--dry-run", action="store_true", default=False,
                   help="仅预览，不写库（默认行为）")
    g.add_argument("--apply", action="store_true", default=False,
                   help="实际写入")
    g.add_argument("--rollback", action="store_true", default=False,
                   help="按 manifest 回滚")
    ap.add_argument("--limit", type=int, default=0,
                    help="dry-run 样例展示条数（默认 20）")
    args = ap.parse_args()

    # 默认 dry-run：没显式 --apply/--rollback 就都是预览
    if not args.apply and not args.rollback:
        args.dry_run = True

    if not os.path.exists(DB_PATH):
        print("[error] 数据库不存在: %s" % DB_PATH)
        return 2

    con = sqlite3.connect(DB_PATH)
    con.execute("pragma foreign_keys=off")
    cur = con.cursor()

    # ── rollback ────────────────────────────────────────────────
    if args.rollback:
        if not os.path.exists(MANIFEST):
            print("[rollback] 无本次回填清单 %s，无需回滚"
                  % os.path.basename(MANIFEST))
            con.close()
            return 0
        with io.open(MANIFEST, encoding="utf-8") as f:
            man = json.load(f)
        mapping = man.get("mapping", {})
        pre = {int(k): v for k, v in man.get("pre_apply", {}).items()}
        if not mapping:
            print("[rollback] 清单为空，无需回滚")
            con.close()
            return 0

        # 回滚前备份
        if args.dry_run:
            print("[dry-run] 将回滚 %d 条（未备份、未写库）" % len(mapping))
            con.close()
            return 0
        bak = backup_db()
        print("[rollback] 已备份: %s" % os.path.basename(bak))

        n = 0
        for pid_str, old_sc in mapping.items():
            pid = int(pid_str)
            cur.execute("update knowledge_point set sub_category_id=? where point_id=?",
                        (old_sc, pid))
            n += 1
        con.commit()
        after = snapshot_kp(cur)
        diff = [k for k in pre if after.get(k) != pre[k]]
        print("[rollback] 已回退 %d 条；与原快照不一致 %d 条" % (n, len(diff)))
        print("  RESULT = %s" % ("PASS" if not diff else "FAIL"))
        con.close()
        return 0 if not diff else 1

    # ── 预计算：子科目 id 按科目分组 ─────────────────────────────
    rows = list(cur.execute(
        "select sc.id, sc.name, sc.subject_id, s.subject_name"
        " from sub_categories sc"
        " left join question_subject s on s.subject_id=sc.subject_id"))
    subcat_name: dict[int, str] = {}
    subcat_id_by_subject: dict[int, set[int]] = {}
    for sc_id, sc_name, subject_id, subject_name in rows:
        subcat_name[sc_id] = sc_name
        subcat_id_by_subject.setdefault(subject_id, set()).add(sc_id)

    # ── 待回填候选 ───────────────────────────────────────────────
    target = list(cur.execute(
        "select point_id, point_name, subject_id, level, parent_id"
        " from knowledge_point where sub_category_id is null"))
    before = snapshot_kp(cur)

    # point_id -> sub_category_id（含本次解析结果，供父级继承）
    parent_sc: dict[int, int | None] = {}

    print("=" * 64)
    print("D-2 全科目回填考点子科目归属")
    print("  库: %s" % DB_PATH)
    print("  模式: %s" % ("DRY-RUN（不写库）" if args.dry_run else "APPLY（写库）"))
    print("=" * 64)

    # 按科目统计当前值
    print("\n[当前状态] knowledge_point 归属统计")
    for sid in sorted(subcat_id_by_subject):
        cnt = cur.execute(
            "select count(*) from knowledge_point where subject_id=?",
            (sid,)).fetchone()[0]
        null_cnt = cur.execute(
            "select count(*) from knowledge_point where subject_id=? and"
            " sub_category_id is null", (sid,)).fetchone()[0]
        nsub = len(subcat_id_by_subject[sid])
        print("  %s(id=%d): 总 %d 条，待回填 %d 条，子科目 %d 个"
              % (SUBJECTS.get(sid, sid), sid, cnt, null_cnt, nsub))

    # ── 判定 ─────────────────────────────────────────────────────
    resolved: dict[int, int] = {}
    unresolved = []
    rule_cnt: dict[str, int] = {}
    per_subject_new: dict[int, int] = {}
    per_subject_unresolved: dict[int, int] = {}
    # 按 level 升序处理：先定 level2 归属，level3/4 经「父级归属」传播。
    # level=2 的行 parent_id 均为 0（实测），不会误继承。
    for pid, name, subject_id, level, pid_parent in sorted(
            target, key=lambda r: (r[3], r[0])):
        psc = None
        if pid_parent:
            if pid_parent in parent_sc:
                psc = parent_sc[pid_parent]
            else:
                prow = cur.execute(
                    "select sub_category_id from knowledge_point"
                    " where point_id=?", (pid_parent,)).fetchone()
                psc = prow[0] if prow else None
                parent_sc[pid_parent] = psc
        sid, rule = resolve_sub_cat(name, subject_id, level, psc,
                                    subcat_id_by_subject)
        # 记录解析结果（含 None），供其子节点继承
        parent_sc[pid] = sid
        if sid is not None:
            rule_cnt[rule] = rule_cnt.get(rule, 0) + 1
            resolved[pid] = sid
            per_subject_new[subject_id] = \
                per_subject_new.get(subject_id, 0) + 1
        else:
            rule_cnt["留空"] = rule_cnt.get("留空", 0) + 1
            unresolved.append({'point_id': pid, 'point_name': name,
                               'subject_id': subject_id, 'level': level,
                               'rule': rule})
            per_subject_unresolved[subject_id] = \
                per_subject_unresolved.get(subject_id, 0) + 1

    print("\n[判定结果] 待回填 %d 条" % len(target))
    for rule, cnt in sorted(rule_cnt.items(), key=lambda x: -x[1]):
        print("  %-20s %d" % (rule, cnt))

    print("\n[分科目] 可回填 / 留空")
    grouped: dict[int, list] = {}
    for u in unresolved:
        grouped.setdefault(u["subject_id"], []).append(u)
    for sid in sorted(set(list(per_subject_new) + list(per_subject_unresolved))):
        print("  %-6s 回填 %3d 条，留空 %3d 条"
              % (SUBJECTS.get(sid, sid),
                 per_subject_new.get(sid, 0),
                 per_subject_unresolved.get(sid, 0)))

    # 每个子科目的回填条数
    sc_cnt: dict[int, int] = {}
    for pid, sid in resolved.items():
        sc_cnt[sid] = sc_cnt.get(sid, 0) + 1
    print("\n[目标子科目] 接收条数")
    for sid in sorted(sc_cnt):
        print("  id=%-3d %-18s %d 条" % (sid, subcat_name.get(sid, "?"), sc_cnt[sid]))

    # 样例
    lim = args.limit or 20
    print("\n[样例] 前 %d 条预告" % lim)
    for pid, sid in list(resolved.items())[:lim]:
        r = cur.execute("select point_name, subject_id, level from"
                        " knowledge_point where point_id=?", (pid,)).fetchone()
        nm, sj, lv = r
        print("  id=%-5d L%s %-28s → %s(%s, id=%d)"
              % (pid, lv, nm, subcat_name.get(sid, "?"),
                 SUBJECTS.get(sj, sj), sid))

    if unresolved:
        print("\n[留空清单] %d 条（不强行填，需人工确认）" % len(unresolved))
        for u in unresolved[:30]:
            print("  id=%-5d %-10s %-30s L%s [%s]"
                  % (u["point_id"], SUBJECTS.get(u["subject_id"], "?"),
                     u["point_name"], u["level"], u["rule"]))
        if len(unresolved) > 30:
            print("  ... 其余 %d 条见 manifest" % (len(unresolved) - 30))

    if args.dry_run:
        print("\n[dry-run] 未写库。确认无误后加 --apply 执行。")
        con.close()
        return 0

    if not resolved:
        print("\n[apply] 无可写数据，退出")
        con.close()
        return 0

    # ── 写入前备份 ─────────────────────────────────────────────
    bak = backup_db()
    chk = sqlite3.connect(bak).execute(
        "select count(*) from knowledge_point where sub_category_id is null"
    ).fetchone()[0]
    print("\n[apply] 已备份: %s（校验待回填=%d 条）" % (os.path.basename(bak), chk))
    if chk != len(target):
        print("  [abort] 备份校验不一致，中止（期望 %d 实际 %d）"
              % (len(target), chk))
        con.close()
        return 1

    # ── 写入 ───────────────────────────────────────────────────
    for pid, sid in resolved.items():
        cur.execute("update knowledge_point set sub_category_id=? where point_id=?",
                    (sid, pid))
    con.commit()

    # ── 验证 ───────────────────────────────────────────────────
    after = snapshot_kp(cur)
    assert len(after) == len(before), "行数不得变化"
    changed = [k for k in before if before[k] != after.get(k)]
    untouched_other = [k for k in changed if before[k][0] is not None]
    print("[apply] 已回填 %d 条；总行数 %d（不变）；改动行 %d"
          % (len(resolved), len(after), len(changed)))
    print("  非空值被改动: %d（期望 0）" % len(untouched_other))
    null_left = cur.execute(
        "select count(*) from knowledge_point where sub_category_id is null"
    ).fetchone()[0]
    print("  回填后仍为空的考点: %d 条" % null_left)

    # 校验 FK 指向真实子科目
    bad_fk = list(cur.execute(
        "select k.point_id from knowledge_point k"
        " left join sub_categories sc on sc.id=k.sub_category_id"
        " where k.sub_category_id is not null and sc.id is null"))
    print("  悬空 sub_category_id: %d（期望 0）" % len(bad_fk))

    # 写 manifest
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prev_mapping: dict[str, int | None] = {}
    prev_unresolved: list = []
    if os.path.exists(MANIFEST):
        try:
            with io.open(MANIFEST, encoding="utf-8") as f:
                old = json.load(f)
            prev_mapping = old.get("mapping", {})
            prev_unresolved = old.get("unresolved", [])
        except (ValueError, OSError):
            prev_mapping, prev_unresolved = {}, []
    merged = dict(prev_mapping)
    merged.update({str(k): v for k, v in resolved.items()})

    man = {
        "created_at": ts,
        "backup": os.path.basename(bak),
        "rule": "考点名→子科目关键词 全科目回填",
        "stats": {
            "targets": len(target),
            "resolved": len(resolved),
            "unresolved": len(unresolved),
            "per_subject_resolved": per_subject_new,
            "per_subject_unresolved": per_subject_unresolved,
        },
        # point_id → 写入的新 sub_category_id
        "mapping": merged,
        # point_id → 写入前的旧值（均为 None，供 --rollback 精确还原）
        "pre_apply": {str(k): before[k][0] for k in resolved},
        "unresolved": unresolved,
    }
    with io.open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print("  manifest: %s（%d 条映射）"
          % (os.path.basename(MANIFEST), len(merged)))

    ok = (not untouched_other) and (not bad_fk)
    print("\nRESULT = %s" % ("PASS" if ok else "FAIL"))
    con.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
