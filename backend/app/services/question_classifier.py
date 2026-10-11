"""
题目三级分类引擎
科目(Subject) → 子科目(SubCategory) → 考点(KnowledgePoint)

设计原则：
1. 关键词加权计分：核心词×3, 高权词×2, 普通词×1
2. 正则模式匹配：处理结构化表达
3. 逐层分类：先定子科目，再定考点
4. 置信度输出：低分标记待人工审核
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, NamedTuple

logger = logging.getLogger(__name__)


# ============================================================
# 分类结果
# ============================================================

class ClassifyResult(NamedTuple):
    subject_id: int
    sub_category_id: Optional[int]
    sub_category_name: str
    knowledge_point_id: Optional[int]
    knowledge_point_name: str
    confidence: float  # 0.0 ~ 1.0
    # 考点层（knowledge_point.level=3），可选以保持向后兼容：
    # 既有按位置构造 6 字段的调用方无需改动。
    exam_point_id: Optional[int] = None
    exam_point_name: str = ""


# ============================================================
# 权重常量
# ============================================================

CORE_WEIGHT = 3.0    # 核心关键词：几乎唯一对应某考点
HIGH_WEIGHT = 2.0    # 高权重关键词：强烈指向某考点
NORMAL_WEIGHT = 1.0  # 普通关键词
MIN_CONFIDENCE = 0.15  # 低于此值标记为"待人工审核"
TEXT_SCAN_LENGTH = 800  # 扫描前800字符


# ============================================================
# 子科目ID映射（运行时从DB反查，此处为空容器）
# 格式: (subject_id, name) → sub_categories.id
# 唯一事实来源 = sub_categories 表；首次分类时由 _load_taxonomy() 填充。
# 禁止再硬编码 id 数字（历史假ID教训：与真实 DB point_id 不符导致挂错考点）。
# ============================================================

SUB_CATEGORY_IDS: Dict[Tuple[int, str], int] = {}

# ============================================================
# 知识点/考点ID映射（运行时从DB反查）
#   _KP_ID_BY_SC     : (sub_category_id, 知识点名) → knowledge_point.point_id
#   _KP_ID_BY_SUBJECT: (subject_id, 知识点名)      → knowledge_point.point_id
#                      （子科目ID缺失时的窄范围回退）
#   _EP_ID           : (父知识点名, 考点名)        → knowledge_point.point_id
# 全部由 _load_taxonomy() 一次性从 knowledge_point 表填充，进程内缓存。
# 关键：只索引 SUB_CATEGORY_KP_MAP / EXAM_POINT_PARENT 里出现的名称，
# 避免语料中的同名噪声（如 35 条「其他」）抢占真实 taxonomy 考点。
# ============================================================

_KP_ID_BY_SC: Dict[Tuple[int, str], int] = {}
_KP_ID_BY_SUBJECT: Dict[Tuple[int, str], int] = {}
_EP_ID: Dict[Tuple[str, str], int] = {}
_TAXONOMY_LOADED = False
_TAXONOMY_ATTEMPTED = False

UNCLASSIFIED = "无法分类"


def _taxonomy_point_names() -> set:
    """返回需要做 DB id 反查的受管名称集合（词表内名称，不含语料噪声）。"""
    names = set()
    for kp_list in SUB_CATEGORY_KP_MAP.values():
        for kp_name in kp_list:
            names.add(kp_name)
    names.update(EXAM_POINT_PARENT.keys())
    names.update(EXAM_POINT_PARENT.values())
    return names


def clear_id_caches() -> None:
    """清空进程内 taxonomy ID 缓存。

    当 taxonomy 表在进程生命周期内发生变化（seed/回填脚本、测试夹具）时调用，
    强制下次分类重新从 DB 反查，保证 id 与权威表一致。
    """
    global _TAXONOMY_LOADED, _TAXONOMY_ATTEMPTED
    SUB_CATEGORY_IDS.clear()
    _KP_ID_BY_SC.clear()
    _KP_ID_BY_SUBJECT.clear()
    _EP_ID.clear()
    _TAXONOMY_LOADED = False
    _TAXONOMY_ATTEMPTED = False


def _open_db():
    """打开一个独立的 DB 会话（仅在调用方未提供 session 时使用）。"""
    from ..core.database import SessionLocal
    return SessionLocal()


def _load_taxonomy(db_session=None) -> bool:
    """从三张 taxonomy 表加载 ID 映射到进程内缓存。

    Args:
        db_session: 可选 SQLAlchemy session。传入时优先复用（可看到未提交数据），
                    否则自建 session 并在用完后关闭。

    Returns:
        True 表示加载成功，False 表示查库失败（分类降级为「有名称、无 ID」，
        但绝不再返回假 ID）。失败只尝试一次，避免每题重试拖慢导入链路。
    """
    global _TAXONOMY_LOADED, _TAXONOMY_ATTEMPTED
    if _TAXONOMY_LOADED or _TAXONOMY_ATTEMPTED:
        return _TAXONOMY_LOADED
    _TAXONOMY_ATTEMPTED = True

    from ..models.models import SubCategory, KnowledgePoint

    own_session = db_session is None
    db = None
    try:
        if own_session:
            db = _open_db()
        else:
            db = db_session

        # 1) 子科目 ID
        for sc in db.query(SubCategory).all():
            # getattr 取值规避 ORM Column 的静态类型收窄问题
            SUB_CATEGORY_IDS[(int(getattr(sc, "subject_id")), str(getattr(sc, "name")))] = \
                int(getattr(sc, "id"))

        # 2) 知识点 / 考点 ID —— 只索引词表内名称
        managed = _taxonomy_point_names()
        candidates: Dict[Tuple[int, str], Tuple[int, int, Optional[int]]] = {}
        for row in db.query(KnowledgePoint).all():
            # getattr 取值规避 ORM Column 的静态类型收窄问题
            nm = getattr(row, "point_name", None)
            if nm is None or nm not in managed:
                continue
            subject_id = int(getattr(row, "subject_id"))
            point_id = int(getattr(row, "point_id"))
            sc_raw = getattr(row, "sub_category_id", None)
            sc_id = int(sc_raw) if sc_raw is not None else None
            key = (subject_id, nm)
            # 排序优先级：有 sub_category_id 的 > 无 sub_category_id 的；point_id 小的 > 大的
            rank = 0 if sc_id is not None else 1
            entry = (rank, point_id, sc_id)
            cur = candidates.get(key)
            if cur is None or entry[:2] < cur[:2]:
                candidates[key] = entry
            # 考点层（level=3）反查父知识点名
            if int(getattr(row, "level", 0)) == 3 and getattr(row, "parent_id", None):
                parent = db.query(KnowledgePoint).filter(
                    KnowledgePoint.point_id == row.parent_id
                ).first()
                if parent is not None:
                    ep_name = getattr(parent, "point_name", None)
                    if ep_name is not None:
                        _EP_ID[(str(ep_name), str(nm))] = point_id

        for (subject_id, nm), (_, pid, scid) in candidates.items():
            _KP_ID_BY_SUBJECT[(subject_id, nm)] = pid
            if scid is not None:
                _KP_ID_BY_SC[(scid, nm)] = pid

        _TAXONOMY_LOADED = True
    except Exception as e:
        # 查库失败不应阻断分类，降级为空映射（返回名称但 ID 为 None）
        logger.debug(f"taxonomy ID 反查失败，分类将退化为无ID模式: {e}")
    finally:
        if own_session and db is not None:
            try:
                db.close()
            except Exception:
                pass
    return _TAXONOMY_LOADED

# 子科目名称 → 其下考点名称列表（**不含 ID**）
#
# 方案 v3 W1-2（假 ID 治理）：原先这里是「假 kp id → 考点名」的硬编码表
# （101~1519），与真实 DB `knowledge_point.point_id`（1~126）不符，调用方直接
# 使用即挂错考点。现收敛为「子科目名 → 考点名列表」的纯名称表，
# 真实 point_id 一律由 `_load_taxonomy()` 运行时从 DB 反查。
SUB_CATEGORY_KP_MAP: Dict[str, List[str]] = {
    "政治理论": [
        "习近平新时代中国特色社会主义思想",
        "党的二十大精神",
        "马克思主义基本原理",
        "党和国家方针政策",
        "政治立场与政治敏锐性",
    ],
    "常识判断": [
        "经济常识", "文化常识", "社会常识",
        "生态常识", "法律常识", "科技常识", "时政热点",
    ],
    "言语理解与表达": [
        "逻辑填空", "片段阅读", "语句表达",
        "中心理解", "词语理解", "态度意图",
    ],
    "数量关系": [
        "数字推理", "数学运算",
    ],
    "判断推理": [
        "图形推理", "逻辑判断", "类比推理", "定义判断",
    ],
    "资料分析": [
        "文字资料分析", "图形资料分析", "表格资料分析",
        "混合型资料", "统计术语", "速算技巧",
    ],
    "知觉速度与准确性": [
        "同符查找", "数字区间定位", "字符替换", "知觉准确性",
    ],
    # 科学推理：实测 4 套卷以「科学推理」替代「数量关系」（广东/河南等）。
    # 考点留空 —— 其考点将来自行测答案解析的【考点】字段（任务 5/10 建树），
    # 不在此处臆造，否则会与常识判断的「生物常识/科技常识」互抢。
    "科学推理": [],
    "归纳概括": [
        "问题概括", "原因概括", "影响概括",
        "对策概括", "特点概括", "过程概括",
    ],
    "综合分析": [
        "观点分析", "现象分析", "词句理解",
        "评析辨析", "比较分析",
    ],
    "提出对策": [
        "问题识别", "对策建议", "方案设计",
        "应急处理", "长效机制",
    ],
    "应用文写作": [
        "公文写作", "事务文书", "案例分析", "宣传文稿",
    ],
    "议论文写作": [
        "命题作文", "话题作文", "材料作文",
        "政论文", "策论文",
    ],
    "职业素养": [
        "政治立场与忠诚度", "政治敏锐性与鉴别力",
        "人民警察核心价值观", "人民警察职业道德", "人民警察职业纪律",
    ],
    "基础知识": [
        "中国特色社会主义法治理论", "法学基础理论",
        "宪法基础知识", "民法基础知识", "人民警察法基础知识",
        "行政执法基础知识", "刑事执法基础知识",
        "公安机关性质与职能", "公安工作根本原则",
        "公安队伍建设", "公安执法监督",
    ],
    "基本警务能力": [
        "宣传教育", "沟通协调", "组织动员",
        "服务群众", "调查研究", "纠纷化解",
        "风险识别", "风险防范", "信息收集",
        "信息分析", "信息应用", "巡逻",
        "接警与处警", "安全检查", "安全保护",
        "事态研判", "信息上报", "合理处置", "善后恢复",
    ],
}


# ============================================================
# 考点级关键词字典 (weighted)
# 格式: { kp_name: [(keyword, weight), ...] }
# ============================================================

# 考点层（level=3）关键词字典 —— 第 1 批 5 个知识点下的 29 个考点
# 格式: { 考点名(带所属知识点前缀): [(keyword, weight), ...] }
# 复用既有的 CORE_WEIGHT / HIGH_WEIGHT / NORMAL_WEIGHT 权重体系，不新建机制。
# ============================================================

EXAM_POINT_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    # ---------- 公安机关性质与职能 (id=72) ----------
    "公安机关的性质": [
        ("公安机关的性质", CORE_WEIGHT), ("性质", HIGH_WEIGHT),
        ("人民民主专政", CORE_WEIGHT), ("专政机关", HIGH_WEIGHT),
        ("国家暴力机关", HIGH_WEIGHT), ("执法机关", NORMAL_WEIGHT),
    ],
    "公安机关的职能职责": [
        ("职能", CORE_WEIGHT), ("职责", CORE_WEIGHT), ("职能职责", CORE_WEIGHT),
        ("维护国家安全", HIGH_WEIGHT), ("社会治安秩序", HIGH_WEIGHT),
        ("预防打击犯罪", HIGH_WEIGHT),
    ],
    "公安机关的权限": [
        ("权限", CORE_WEIGHT), ("职权", HIGH_WEIGHT), ("权力", HIGH_WEIGHT),
        ("侦查权", HIGH_WEIGHT), ("拘传", HIGH_WEIGHT), ("搜查", HIGH_WEIGHT),
    ],
    "公安机关的义务": [
        ("义务", CORE_WEIGHT), ("职责要求", HIGH_WEIGHT),
        ("依法履行", HIGH_WEIGHT), ("保障人民民主", NORMAL_WEIGHT),
    ],
    "公安机关的组织管理": [
        ("组织管理", CORE_WEIGHT), ("组织体系", HIGH_WEIGHT),
        ("公安机关负责人", HIGH_WEIGHT), ("内设机构", HIGH_WEIGHT),
    ],
    "公安机关与其他国家机关的关系": [
        ("其他国家机关", CORE_WEIGHT), ("关系", HIGH_WEIGHT),
        ("公安机关与", HIGH_WEIGHT), ("协作", NORMAL_WEIGHT),
    ],
    # ---------- 接警与处警 (id=88) ----------
    "接警受理": [
        ("接警", CORE_WEIGHT), ("受理", CORE_WEIGHT), ("接警受理", CORE_WEIGHT),
        ("报警", HIGH_WEIGHT), ("警情", HIGH_WEIGHT),
    ],
    "指挥调度": [
        ("指挥", CORE_WEIGHT), ("调度", CORE_WEIGHT), ("指挥调度", CORE_WEIGHT),
        ("下达指令", HIGH_WEIGHT),
    ],
    "出警途中处置": [
        ("出警途中", CORE_WEIGHT), ("途中", HIGH_WEIGHT), ("赶赴现场", HIGH_WEIGHT),
    ],
    "现场处置": [
        ("现场处置", CORE_WEIGHT), ("现场", CORE_WEIGHT),
        ("现场勘查", HIGH_WEIGHT), ("处置现场", HIGH_WEIGHT),
    ],
    "带回所处理": [
        ("带回", CORE_WEIGHT), ("带回所", CORE_WEIGHT), ("带回公安机关", HIGH_WEIGHT),
        ("传唤", HIGH_WEIGHT),
    ],
    "移交与反馈": [
        ("移交", CORE_WEIGHT), ("反馈", CORE_WEIGHT), ("移交与反馈", CORE_WEIGHT),
        ("移送", HIGH_WEIGHT), ("告知", NORMAL_WEIGHT),
    ],
    # ---------- 刑事执法基础知识 (id=71) ----------
    "刑事立案": [
        ("立案", CORE_WEIGHT), ("刑事立案", CORE_WEIGHT),
        ("受案", HIGH_WEIGHT), ("不予立案", HIGH_WEIGHT),
    ],
    "侦查措施": [
        ("侦查措施", CORE_WEIGHT), ("侦查", CORE_WEIGHT),
        ("讯问", HIGH_WEIGHT), ("询问", HIGH_WEIGHT), ("勘验", HIGH_WEIGHT),
    ],
    "强制措施": [
        ("强制措施", CORE_WEIGHT), ("拘传", CORE_WEIGHT),
        ("取保候审", CORE_WEIGHT), ("监视居住", CORE_WEIGHT), ("拘留", HIGH_WEIGHT),
    ],
    "强制措施适用": [
        ("适用", CORE_WEIGHT), ("强制措施的适用", CORE_WEIGHT),
        ("条件", HIGH_WEIGHT), ("期限", HIGH_WEIGHT),
    ],
    "案件移送": [
        ("移送", CORE_WEIGHT), ("案件移送", CORE_WEIGHT),
        ("移送审查起诉", CORE_WEIGHT), ("起诉", HIGH_WEIGHT),
    ],
    "涉案财物管理": [
        ("涉案财物", CORE_WEIGHT), ("扣押", CORE_WEIGHT),
        ("冻结", HIGH_WEIGHT), ("保管", HIGH_WEIGHT), ("涉案", HIGH_WEIGHT),
    ],
    # ---------- 行政执法基础知识 (id=70) ----------
    "行政处罚概述": [
        ("行政处罚", CORE_WEIGHT), ("概述", NORMAL_WEIGHT),
        ("行政处罚法", HIGH_WEIGHT),
    ],
    "行政处罚种类与设定": [
        ("种类", CORE_WEIGHT), ("设定", CORE_WEIGHT),
        ("警告", HIGH_WEIGHT), ("罚款", HIGH_WEIGHT), ("没收", HIGH_WEIGHT),
        ("暂扣", HIGH_WEIGHT), ("吊销", HIGH_WEIGHT),
    ],
    "行政处罚程序": [
        ("程序", CORE_WEIGHT), ("行政处罚程序", CORE_WEIGHT),
        ("告知", HIGH_WEIGHT), ("听证", HIGH_WEIGHT), ("送达", HIGH_WEIGHT),
    ],
    "行政强制": [
        ("行政强制", CORE_WEIGHT), ("强制执行", HIGH_WEIGHT),
        ("查封", HIGH_WEIGHT), ("扣押", NORMAL_WEIGHT),
    ],
    "行政许可": [
        ("行政许可", CORE_WEIGHT), ("许可", CORE_WEIGHT),
        ("审批", HIGH_WEIGHT), ("颁发", NORMAL_WEIGHT),
    ],
    "行政复议": [
        ("行政复议", CORE_WEIGHT), ("复议", CORE_WEIGHT),
        ("复核", HIGH_WEIGHT), ("争议", HIGH_WEIGHT),
    ],
    # ---------- 巡逻 (id=87) ----------
    "巡逻勤务规范": [
        ("巡逻勤务", CORE_WEIGHT), ("勤务规范", CORE_WEIGHT),
        ("巡逻", HIGH_WEIGHT),
    ],
    "巡逻方式与勤务安排": [
        ("巡逻方式", CORE_WEIGHT), ("勤务安排", CORE_WEIGHT),
        ("徒步巡逻", HIGH_WEIGHT), ("驾车巡逻", HIGH_WEIGHT), ("排班", NORMAL_WEIGHT),
    ],
    "巡逻重点与路线": [
        ("巡逻重点", CORE_WEIGHT), ("巡逻路线", CORE_WEIGHT),
        ("重点", HIGH_WEIGHT), ("路线", HIGH_WEIGHT),
    ],
    "巡逻装备": [
        ("巡逻装备", CORE_WEIGHT), ("装备", CORE_WEIGHT),
        ("警用装备", HIGH_WEIGHT), ("器械", HIGH_WEIGHT),
    ],
    "巡逻中的处置": [
        ("巡逻中", CORE_WEIGHT), ("巡逻处置", CORE_WEIGHT),
        ("发现可疑", HIGH_WEIGHT), ("盘查", HIGH_WEIGHT),
    ],
}

# 考点 -> 所属知识点（用于反查 parent_id）
EXAM_POINT_PARENT: Dict[str, str] = {
    "公安机关的性质": "公安机关性质与职能",
    "公安机关的职能职责": "公安机关性质与职能",
    "公安机关的权限": "公安机关性质与职能",
    "公安机关的义务": "公安机关性质与职能",
    "公安机关的组织管理": "公安机关性质与职能",
    "公安机关与其他国家机关的关系": "公安机关性质与职能",
    "接警受理": "接警与处警",
    "指挥调度": "接警与处警",
    "出警途中处置": "接警与处警",
    "现场处置": "接警与处警",
    "带回所处理": "接警与处警",
    "移交与反馈": "接警与处警",
    "刑事立案": "刑事执法基础知识",
    "侦查措施": "刑事执法基础知识",
    "强制措施": "刑事执法基础知识",
    "强制措施适用": "刑事执法基础知识",
    "案件移送": "刑事执法基础知识",
    "涉案财物管理": "刑事执法基础知识",
    "行政处罚概述": "行政执法基础知识",
    "行政处罚种类与设定": "行政执法基础知识",
    "行政处罚程序": "行政执法基础知识",
    "行政强制": "行政执法基础知识",
    "行政许可": "行政执法基础知识",
    "行政复议": "行政执法基础知识",
    "巡逻勤务规范": "巡逻",
    "巡逻方式与勤务安排": "巡逻",
    "巡逻重点与路线": "巡逻",
    "巡逻装备": "巡逻",
    "巡逻中的处置": "巡逻",
}

KNOWLEDGE_POINT_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    # ======================== 行测 ========================
    # --- 政治理论 ---
    "习近平新时代中国特色社会主义思想": [
        ("习近平新时代中国特色社会主义思想", CORE_WEIGHT), ("新时代", HIGH_WEIGHT),
        ("治国理政", HIGH_WEIGHT), ("中国式现代化", HIGH_WEIGHT), ("新质生产力", HIGH_WEIGHT),
        ("高质量发展", HIGH_WEIGHT), ("四个意识", CORE_WEIGHT), ("四个自信", CORE_WEIGHT),
        ("两个维护", CORE_WEIGHT), ("五位一体", HIGH_WEIGHT), ("四个全面", HIGH_WEIGHT),
        ("初心使命", NORMAL_WEIGHT), ("新发展理念", NORMAL_WEIGHT),
    ],
    "党的二十大精神": [
        ("二十大", CORE_WEIGHT), ("党的二十大", CORE_WEIGHT),
        ("现代化强国", HIGH_WEIGHT), ("第二个百年", HIGH_WEIGHT),
        ("共同富裕", HIGH_WEIGHT), ("中国式现代化", NORMAL_WEIGHT),
    ],
    "马克思主义基本原理": [
        ("马克思", CORE_WEIGHT), ("恩格斯", HIGH_WEIGHT),
        ("唯物辩证法", CORE_WEIGHT), ("唯物史观", CORE_WEIGHT),
        ("矛盾论", HIGH_WEIGHT), ("实践论", HIGH_WEIGHT),
        ("生产力", HIGH_WEIGHT), ("生产关系", HIGH_WEIGHT),
        ("经济基础", HIGH_WEIGHT), ("上层建筑", HIGH_WEIGHT),
        ("否定之否定", CORE_WEIGHT), ("量变质变", CORE_WEIGHT), ("对立统一", CORE_WEIGHT),
        ("物质与意识", NORMAL_WEIGHT),
    ],
    "党和国家方针政策": [
        ("方针政策", CORE_WEIGHT), ("政府工作报告", CORE_WEIGHT),
        ("五年规划", HIGH_WEIGHT), ("十四五", HIGH_WEIGHT), ("2035", HIGH_WEIGHT),
        ("远景目标", HIGH_WEIGHT), ("基本国策", HIGH_WEIGHT),
        ("民生保障", HIGH_WEIGHT), ("乡村振兴", CORE_WEIGHT),
        ("一带一路", HIGH_WEIGHT), ("新发展格局", HIGH_WEIGHT),
        ("供给侧改革", HIGH_WEIGHT), ("国家政策", NORMAL_WEIGHT),
    ],
    "政治立场与政治敏锐性": [
        ("政治立场", CORE_WEIGHT), ("政治敏锐", CORE_WEIGHT),
        ("政治鉴别", CORE_WEIGHT), ("政治判断", HIGH_WEIGHT),
        ("政治领悟", HIGH_WEIGHT), ("政治执行", HIGH_WEIGHT),
        ("政治站位", HIGH_WEIGHT), ("大局意识", HIGH_WEIGHT),
        ("核心意识", HIGH_WEIGHT), ("看齐意识", HIGH_WEIGHT),
    ],

    # --- 常识判断 ---
    "经济常识": [
        ("GDP", HIGH_WEIGHT), ("通货膨胀", CORE_WEIGHT), ("货币政策", CORE_WEIGHT),
        ("财政政策", CORE_WEIGHT), ("市场经济", HIGH_WEIGHT), ("宏观调控", CORE_WEIGHT),
        ("汇率", HIGH_WEIGHT), ("关税", HIGH_WEIGHT), ("贸易", NORMAL_WEIGHT),
        ("税收", HIGH_WEIGHT), ("基尼系数", HIGH_WEIGHT), ("恩格尔系数", HIGH_WEIGHT),
        ("供给侧", NORMAL_WEIGHT), ("需求侧", NORMAL_WEIGHT),
    ],
    "文化常识": [
        ("传统文化", CORE_WEIGHT), ("诸子百家", CORE_WEIGHT), ("儒家", HIGH_WEIGHT),
        ("道家", HIGH_WEIGHT), ("文学", NORMAL_WEIGHT), ("艺术", NORMAL_WEIGHT),
        ("绘画", NORMAL_WEIGHT), ("书法", NORMAL_WEIGHT), ("诗词", NORMAL_WEIGHT),
        ("典故", NORMAL_WEIGHT), ("民俗", NORMAL_WEIGHT), ("非遗", CORE_WEIGHT),
        ("世界遗产", HIGH_WEIGHT),
    ],
    "社会常识": [
        ("社会保障", CORE_WEIGHT), ("医疗保险", HIGH_WEIGHT), ("养老保险", HIGH_WEIGHT),
        ("人口老龄化", HIGH_WEIGHT), ("三孩政策", HIGH_WEIGHT), ("基层治理", CORE_WEIGHT),
        ("社区服务", HIGH_WEIGHT), ("公益", NORMAL_WEIGHT), ("志愿者", NORMAL_WEIGHT),
        ("社会救助", HIGH_WEIGHT), ("民生", NORMAL_WEIGHT),
    ],
    "生态常识": [
        ("碳中和", CORE_WEIGHT), ("碳达峰", CORE_WEIGHT), ("生态文明", CORE_WEIGHT),
        ("绿色发展", HIGH_WEIGHT), ("污染防治", HIGH_WEIGHT), ("垃圾分类", HIGH_WEIGHT),
        ("生物多样性", HIGH_WEIGHT), ("节能减排", HIGH_WEIGHT), ("清洁能源", HIGH_WEIGHT),
        ("低碳", NORMAL_WEIGHT), ("绿水青山", HIGH_WEIGHT), ("可持续发展", HIGH_WEIGHT),
    ],
    "法律常识": [
        ("消费者权益", HIGH_WEIGHT), ("劳动合同", HIGH_WEIGHT), ("知识产权", CORE_WEIGHT),
        ("公司法", HIGH_WEIGHT), ("婚姻法", HIGH_WEIGHT), ("继承法", HIGH_WEIGHT),
        ("侵权责任", HIGH_WEIGHT), ("行政处罚", NORMAL_WEIGHT), ("行政复议", NORMAL_WEIGHT),
    ],
    "科技常识": [
        ("人工智能", CORE_WEIGHT), ("5G", HIGH_WEIGHT), ("大数据", HIGH_WEIGHT),
        ("区块链", HIGH_WEIGHT), ("量子", HIGH_WEIGHT), ("芯片", HIGH_WEIGHT),
        ("航天", HIGH_WEIGHT), ("卫星", HIGH_WEIGHT), ("高铁", NORMAL_WEIGHT),
        ("新能源汽车", HIGH_WEIGHT), ("基因编辑", HIGH_WEIGHT), ("克隆", HIGH_WEIGHT),
        ("AI", HIGH_WEIGHT), ("光伏", NORMAL_WEIGHT), ("新能源", NORMAL_WEIGHT),
    ],
    "时政热点": [
        ("两会", HIGH_WEIGHT), ("政府工作", HIGH_WEIGHT), ("中央经济", HIGH_WEIGHT),
        ("冬奥", HIGH_WEIGHT), ("亚运", HIGH_WEIGHT), ("进博会", HIGH_WEIGHT),
        ("博鳌", HIGH_WEIGHT), ("G20", HIGH_WEIGHT), ("金砖", HIGH_WEIGHT),
        ("数字经济", HIGH_WEIGHT), ("RCEP", HIGH_WEIGHT),
    ],

    # --- 言语理解与表达 ---
    "逻辑填空": [
        ("填入", CORE_WEIGHT), ("横线", CORE_WEIGHT), ("最恰当的", CORE_WEIGHT),
        ("依次填入", CORE_WEIGHT), ("空缺", HIGH_WEIGHT), ("空白处", HIGH_WEIGHT),
        ("选出最恰当", HIGH_WEIGHT), ("填入.*最恰当", CORE_WEIGHT),
    ],
    "片段阅读": [
        ("这段文字", CORE_WEIGHT), ("文字主要", HIGH_WEIGHT), ("主要说明", HIGH_WEIGHT),
        ("主要介绍了", HIGH_WEIGHT), ("意在说明", CORE_WEIGHT), ("文段", HIGH_WEIGHT),
        ("这段文字.*意在", CORE_WEIGHT),
    ],
    "语句表达": [
        ("语句排序", CORE_WEIGHT), ("语序最恰当", CORE_WEIGHT), ("排列最恰当", HIGH_WEIGHT),
        ("语句填入", HIGH_WEIGHT), ("衔接最恰当", HIGH_WEIGHT), ("病句", CORE_WEIGHT),
        ("有语病的", CORE_WEIGHT), ("没有语病", CORE_WEIGHT),
    ],
    "中心理解": [
        ("主旨", CORE_WEIGHT), ("中心意思", CORE_WEIGHT), ("主要观点", CORE_WEIGHT),
        ("核心观点", CORE_WEIGHT), ("意在强调", CORE_WEIGHT), ("主要谈论", HIGH_WEIGHT),
        ("主要阐述", HIGH_WEIGHT),
    ],
    "词语理解": [
        ("指代", CORE_WEIGHT), ("指的是", CORE_WEIGHT), ("意思是", HIGH_WEIGHT),
        ("词语理解", CORE_WEIGHT), ("划线词语", CORE_WEIGHT), ("加点词语", CORE_WEIGHT),
        ("中指", HIGH_WEIGHT),
    ],
    "态度意图": [
        ("作者态度", CORE_WEIGHT), ("意图", HIGH_WEIGHT), ("用意", HIGH_WEIGHT),
        ("目的", NORMAL_WEIGHT), ("倾向", HIGH_WEIGHT), ("隐含", HIGH_WEIGHT),
        ("暗示", HIGH_WEIGHT), ("作者认为", CORE_WEIGHT), ("作者看法", CORE_WEIGHT),
    ],

    # --- 数量关系 ---
    "数字推理": [
        ("数列", CORE_WEIGHT), ("数字推理", CORE_WEIGHT), ("找规律", HIGH_WEIGHT),
        ("排列规律", HIGH_WEIGHT), ("等差数列", CORE_WEIGHT), ("等比数列", CORE_WEIGHT),
        ("平方", NORMAL_WEIGHT), ("立方", NORMAL_WEIGHT),
    ],
    "数学运算": [
        ("工程问题", CORE_WEIGHT), ("行程问题", CORE_WEIGHT), ("相遇", HIGH_WEIGHT),
        ("追及", HIGH_WEIGHT), ("排列组合", CORE_WEIGHT), ("概率", HIGH_WEIGHT),
        ("利润", HIGH_WEIGHT), ("利润率", HIGH_WEIGHT), ("浓度", HIGH_WEIGHT),
        ("年龄问题", HIGH_WEIGHT), ("日期问题", HIGH_WEIGHT), ("容斥原理", CORE_WEIGHT),
        ("鸡兔同笼", CORE_WEIGHT), ("牛吃草", CORE_WEIGHT), ("最值问题", HIGH_WEIGHT),
        ("方程", NORMAL_WEIGHT), ("不等式", NORMAL_WEIGHT),
    ],

    # --- 判断推理 ---
    "图形推理": [
        ("图形", HIGH_WEIGHT), ("图中", NORMAL_WEIGHT), ("如图所示", HIGH_WEIGHT),
        ("下图", NORMAL_WEIGHT), ("空间", NORMAL_WEIGHT), ("折叠", HIGH_WEIGHT),
        ("展开图", CORE_WEIGHT), ("立体", HIGH_WEIGHT), ("视图", NORMAL_WEIGHT),
        ("截面", HIGH_WEIGHT), ("九宫格", CORE_WEIGHT),
    ],
    "逻辑判断": [
        ("如果.*那么", CORE_WEIGHT), ("只有.*才", CORE_WEIGHT), ("除非.*否则", CORE_WEIGHT),
        ("削弱", CORE_WEIGHT), ("加强", CORE_WEIGHT), ("前提", HIGH_WEIGHT),
        ("假设", HIGH_WEIGHT), ("真假", HIGH_WEIGHT), ("矛盾", HIGH_WEIGHT),
        ("推理", NORMAL_WEIGHT), ("推断", NORMAL_WEIGHT), ("必然", NORMAL_WEIGHT),
    ],
    "类比推理": [
        ("类比", CORE_WEIGHT), ("相当于", CORE_WEIGHT), ("之于", CORE_WEIGHT),
        ("相似", NORMAL_WEIGHT), ("类比推理", CORE_WEIGHT),
    ],
    "定义判断": [
        ("定义", NORMAL_WEIGHT), ("符合定义", CORE_WEIGHT), ("不符合定义", CORE_WEIGHT),
        ("属于", NORMAL_WEIGHT), ("不属于", NORMAL_WEIGHT), ("根据上述定义", CORE_WEIGHT),
        ("概念", NORMAL_WEIGHT), ("是指", NORMAL_WEIGHT), ("称为", NORMAL_WEIGHT),
    ],

    # --- 资料分析 ---
    "文字资料分析": [
        ("文字资料", CORE_WEIGHT), ("文字材料", CORE_WEIGHT), ("根据资料", HIGH_WEIGHT),
        ("根据材料", HIGH_WEIGHT), ("根据上文", HIGH_WEIGHT), ("根据上述资料", HIGH_WEIGHT),
    ],
    "图形资料分析": [
        ("柱状图", CORE_WEIGHT), ("折线图", CORE_WEIGHT), ("饼图", CORE_WEIGHT),
        ("条形图", CORE_WEIGHT), ("趋势图", CORE_WEIGHT), ("如图所示", NORMAL_WEIGHT),
    ],
    "表格资料分析": [
        ("表格", CORE_WEIGHT), ("统计表", CORE_WEIGHT), ("如表", HIGH_WEIGHT),
        ("如下表", HIGH_WEIGHT), ("表中数据", HIGH_WEIGHT),
    ],
    "混合型资料": [
        ("图表结合", CORE_WEIGHT), ("文字表格", CORE_WEIGHT), ("综合资料", HIGH_WEIGHT),
    ],
    "统计术语": [
        ("同比增长", CORE_WEIGHT), ("环比增长", CORE_WEIGHT), ("增长率", HIGH_WEIGHT),
        ("增幅", HIGH_WEIGHT), ("比重", HIGH_WEIGHT), ("占比", HIGH_WEIGHT),
        ("倍数", HIGH_WEIGHT), ("翻番", HIGH_WEIGHT), ("百分点", HIGH_WEIGHT),
        ("成数", HIGH_WEIGHT), ("指数", HIGH_WEIGHT), ("基期", CORE_WEIGHT),
        ("报告期", CORE_WEIGHT), ("年均增长", HIGH_WEIGHT), ("累计增长", HIGH_WEIGHT),
    ],
    "速算技巧": [
        ("估算", CORE_WEIGHT), ("速算", CORE_WEIGHT), ("首数法", CORE_WEIGHT),
        ("尾数法", CORE_WEIGHT), ("特征数字", HIGH_WEIGHT), ("截位", HIGH_WEIGHT),
        ("插值", HIGH_WEIGHT), ("差分", HIGH_WEIGHT), ("十字交叉", CORE_WEIGHT),
    ],

    # --- 知觉速度与准确性 ---
    "同符查找": [
        ("同符", CORE_WEIGHT), ("相同字符", CORE_WEIGHT), ("相同符号", CORE_WEIGHT),
        ("共有字符", HIGH_WEIGHT), ("包含相同", HIGH_WEIGHT),
    ],
    "数字区间定位": [
        ("区间", CORE_WEIGHT), ("数字区间", CORE_WEIGHT), ("定位", HIGH_WEIGHT),
        ("范围内", HIGH_WEIGHT), ("属于哪个区间", CORE_WEIGHT),
    ],
    "字符替换": [
        ("字符替换", CORE_WEIGHT), ("替换", NORMAL_WEIGHT), ("编码", NORMAL_WEIGHT),
        ("密码", NORMAL_WEIGHT), ("对应关系", NORMAL_WEIGHT),
    ],
    "知觉准确性": [
        ("知觉", CORE_WEIGHT), ("感知", NORMAL_WEIGHT), ("识别速度", HIGH_WEIGHT),
        ("快速判断", HIGH_WEIGHT), ("核对", HIGH_WEIGHT), ("缺失", NORMAL_WEIGHT),
        ("多出", NORMAL_WEIGHT),
    ],

    # ======================== 申论 ========================
    # --- 归纳概括 ---
    "问题概括": [
        ("概括.*问题", CORE_WEIGHT), ("归纳.*问题", HIGH_WEIGHT),
        ("问题.*概括", HIGH_WEIGHT), ("存在.*问题", NORMAL_WEIGHT),
        ("问题有", NORMAL_WEIGHT), ("主要问题", HIGH_WEIGHT),
    ],
    "原因概括": [
        ("原因", NORMAL_WEIGHT), ("根源", HIGH_WEIGHT), ("因素", NORMAL_WEIGHT),
        ("为什么", NORMAL_WEIGHT), ("成因", HIGH_WEIGHT), ("起因", HIGH_WEIGHT),
        ("导致.*原因", CORE_WEIGHT), ("深层原因", CORE_WEIGHT),
    ],
    "影响概括": [
        ("影响", NORMAL_WEIGHT), ("后果", NORMAL_WEIGHT), ("作用", NORMAL_WEIGHT),
        ("意义", NORMAL_WEIGHT), ("危害", HIGH_WEIGHT), ("效果", NORMAL_WEIGHT),
        ("结果", NORMAL_WEIGHT), ("成效", NORMAL_WEIGHT), ("效应", NORMAL_WEIGHT),
    ],
    "对策概括": [
        ("概括.*对策", CORE_WEIGHT), ("归纳.*对策", HIGH_WEIGHT),
        ("概括.*措施", HIGH_WEIGHT), ("做法", NORMAL_WEIGHT),
        ("经验", NORMAL_WEIGHT), ("启示", NORMAL_WEIGHT),
    ],
    "特点概括": [
        ("特点", CORE_WEIGHT), ("特征", CORE_WEIGHT), ("性质", HIGH_WEIGHT),
        ("特色", HIGH_WEIGHT), ("风格", NORMAL_WEIGHT), ("模式", NORMAL_WEIGHT),
        ("方式", NORMAL_WEIGHT),
    ],
    "过程概括": [
        ("过程", CORE_WEIGHT), ("流程", CORE_WEIGHT), ("步骤", HIGH_WEIGHT),
        ("环节", HIGH_WEIGHT), ("阶段", HIGH_WEIGHT), ("历程", HIGH_WEIGHT),
        ("经过", NORMAL_WEIGHT), ("程序", NORMAL_WEIGHT),
    ],

    # --- 综合分析 ---
    "观点分析": [
        ("观点", NORMAL_WEIGHT), ("看法", NORMAL_WEIGHT), ("主张", NORMAL_WEIGHT),
        ("认为", NORMAL_WEIGHT), ("立场", HIGH_WEIGHT), ("态度", HIGH_WEIGHT),
        ("倾向", NORMAL_WEIGHT), ("评价", HIGH_WEIGHT),
    ],
    "现象分析": [
        ("现象", NORMAL_WEIGHT), ("分析.*现象", CORE_WEIGHT), ("反映", NORMAL_WEIGHT),
        ("说明", NORMAL_WEIGHT), ("揭示了", HIGH_WEIGHT), ("背后", NORMAL_WEIGHT),
    ],
    "词句理解": [
        ("理解", NORMAL_WEIGHT), ("解释", NORMAL_WEIGHT), ("含义", HIGH_WEIGHT),
        ("意思", NORMAL_WEIGHT), ("如何理解", CORE_WEIGHT), ("谈谈.*理解", CORE_WEIGHT),
        ("划线句子", CORE_WEIGHT), ("谈谈你对", CORE_WEIGHT),
    ],
    "评析辨析": [
        ("评析", CORE_WEIGHT), ("辨析", CORE_WEIGHT), ("评论", HIGH_WEIGHT),
        ("评议", HIGH_WEIGHT), ("评判", HIGH_WEIGHT), ("判断.*对错", HIGH_WEIGHT),
        ("如何看待", HIGH_WEIGHT),
    ],
    "比较分析": [
        ("比较", CORE_WEIGHT), ("对比", CORE_WEIGHT), ("异同", CORE_WEIGHT),
        ("区别", HIGH_WEIGHT), ("联系", NORMAL_WEIGHT), ("相似", NORMAL_WEIGHT),
        ("不同点", HIGH_WEIGHT), ("相同点", HIGH_WEIGHT), ("比较分析", CORE_WEIGHT),
        ("不同于", HIGH_WEIGHT),
    ],

    # --- 提出对策 ---
    "问题识别": [
        ("不足", NORMAL_WEIGHT), ("短板", CORE_WEIGHT), ("缺陷", HIGH_WEIGHT),
        ("困难", NORMAL_WEIGHT), ("挑战", NORMAL_WEIGHT), ("存在", NORMAL_WEIGHT),
        ("缺乏", HIGH_WEIGHT), ("不够", NORMAL_WEIGHT),
    ],
    "对策建议": [
        ("提出.*对策", CORE_WEIGHT), ("对策.*建议", CORE_WEIGHT),
        ("解决.*办法", HIGH_WEIGHT), ("措施", NORMAL_WEIGHT),
        ("方案", NORMAL_WEIGHT), ("思路", NORMAL_WEIGHT),
        ("办法", NORMAL_WEIGHT), ("途径", HIGH_WEIGHT),
    ],
    "方案设计": [
        ("方案", NORMAL_WEIGHT), ("计划", NORMAL_WEIGHT), ("规划", HIGH_WEIGHT),
        ("设计", NORMAL_WEIGHT), ("制定", HIGH_WEIGHT), ("拟定", HIGH_WEIGHT),
        ("编制", HIGH_WEIGHT), ("工作方案", CORE_WEIGHT), ("实施方案", CORE_WEIGHT),
    ],
    "应急处理": [
        ("应急", CORE_WEIGHT), ("突发", CORE_WEIGHT), ("紧急", HIGH_WEIGHT),
        ("危机", HIGH_WEIGHT), ("事故", HIGH_WEIGHT), ("救援", HIGH_WEIGHT),
        ("抢险", HIGH_WEIGHT), ("处置", NORMAL_WEIGHT),
        ("应急预案", CORE_WEIGHT), ("突发事件", CORE_WEIGHT),
    ],
    "长效机制": [
        ("机制", NORMAL_WEIGHT), ("制度", NORMAL_WEIGHT), ("体系", NORMAL_WEIGHT),
        ("长效机制", CORE_WEIGHT), ("常态化", CORE_WEIGHT), ("长效", HIGH_WEIGHT),
        ("制度化", HIGH_WEIGHT), ("规范化", HIGH_WEIGHT), ("持续", NORMAL_WEIGHT),
        ("保障机制", HIGH_WEIGHT),
    ],

    # --- 应用文写作 ---
    "公文写作": [
        ("公文", CORE_WEIGHT), ("通知", HIGH_WEIGHT), ("报告", HIGH_WEIGHT),
        ("请示", HIGH_WEIGHT), ("批复", HIGH_WEIGHT), ("函", HIGH_WEIGHT),
        ("决定", HIGH_WEIGHT), ("公告", HIGH_WEIGHT), ("通告", HIGH_WEIGHT),
        ("通报", HIGH_WEIGHT), ("纪要", HIGH_WEIGHT), ("命令", HIGH_WEIGHT),
        ("意见", NORMAL_WEIGHT), ("议案", HIGH_WEIGHT),
    ],
    "事务文书": [
        ("简报", CORE_WEIGHT), ("总结", NORMAL_WEIGHT), ("讲话稿", CORE_WEIGHT),
        ("倡议书", CORE_WEIGHT), ("公开信", CORE_WEIGHT), ("建议书", CORE_WEIGHT),
        ("申请书", HIGH_WEIGHT), ("调研报告", CORE_WEIGHT), ("汇报", HIGH_WEIGHT),
    ],
    "案例分析": [
        ("案例", CORE_WEIGHT), ("案情", CORE_WEIGHT), ("事例", HIGH_WEIGHT),
        ("实例", HIGH_WEIGHT), ("结合案例", CORE_WEIGHT), ("根据案例", CORE_WEIGHT),
        ("案例分析", CORE_WEIGHT), ("案情分析", CORE_WEIGHT), ("以案说法", CORE_WEIGHT),
    ],
    "宣传文稿": [
        ("宣传", NORMAL_WEIGHT), ("报道", NORMAL_WEIGHT), ("新闻稿", CORE_WEIGHT),
        ("通讯", HIGH_WEIGHT), ("倡议", NORMAL_WEIGHT), ("宣讲", HIGH_WEIGHT),
        ("演讲稿", CORE_WEIGHT), ("宣传稿", CORE_WEIGHT), ("广播稿", CORE_WEIGHT),
    ],

    # --- 议论文写作 ---
    "命题作文": [
        ("以.*为题", CORE_WEIGHT), ("题目.*自拟", HIGH_WEIGHT),
        ("请以", HIGH_WEIGHT), ("围绕", NORMAL_WEIGHT), ("试以", HIGH_WEIGHT),
    ],
    "话题作文": [
        ("以.*为话题", CORE_WEIGHT), ("话题", CORE_WEIGHT),
        ("自选角度", CORE_WEIGHT), ("自拟题目", CORE_WEIGHT), ("角度自选", HIGH_WEIGHT),
    ],
    "材料作文": [
        ("根据.*材料", CORE_WEIGHT), ("阅读.*材料", CORE_WEIGHT),
        ("材料.*作文", CORE_WEIGHT), ("结合.*材料", HIGH_WEIGHT),
        ("联系.*材料", HIGH_WEIGHT),
    ],
    "政论文": [
        ("政论文", CORE_WEIGHT), ("政策", NORMAL_WEIGHT), ("治理", NORMAL_WEIGHT),
        ("政府", NORMAL_WEIGHT), ("执政", HIGH_WEIGHT), ("国家治理", CORE_WEIGHT),
        ("治理能力", HIGH_WEIGHT), ("治理体系", HIGH_WEIGHT), ("中国之治", CORE_WEIGHT),
    ],
    "策论文": [
        ("策论文", CORE_WEIGHT), ("路径", NORMAL_WEIGHT), ("方略", HIGH_WEIGHT),
        ("攻坚", HIGH_WEIGHT), ("破解", HIGH_WEIGHT), ("应对", NORMAL_WEIGHT),
        ("推进", NORMAL_WEIGHT), ("深化", NORMAL_WEIGHT), ("完善", NORMAL_WEIGHT),
    ],

    # ======================== 公专 ========================
    # --- 职业素养 ---
    "政治立场与忠诚度": [
        ("忠诚", CORE_WEIGHT), ("政治立场", NORMAL_WEIGHT), ("忠于党", CORE_WEIGHT),
        ("忠于人民", CORE_WEIGHT), ("忠于祖国", CORE_WEIGHT), ("绝对忠诚", CORE_WEIGHT),
        ("对党忠诚", CORE_WEIGHT), ("政治本色", HIGH_WEIGHT), ("政治信念", HIGH_WEIGHT),
    ],
    "政治敏锐性与鉴别力": [
        ("敏锐性", CORE_WEIGHT), ("鉴别力", CORE_WEIGHT), ("政治敏锐", NORMAL_WEIGHT),
        ("是非", HIGH_WEIGHT), ("鉴别", HIGH_WEIGHT), ("辨别", HIGH_WEIGHT),
        ("政治判断", NORMAL_WEIGHT), ("看得清", HIGH_WEIGHT), ("辨得明", HIGH_WEIGHT),
    ],
    "人民警察核心价值观": [
        ("核心价值观", CORE_WEIGHT), ("警察核心价值", CORE_WEIGHT),
        ("人民警察.*价值观", CORE_WEIGHT), ("忠诚.*为民.*公正.*廉洁", CORE_WEIGHT),
        ("警察核心价值观", CORE_WEIGHT),
    ],
    "人民警察职业道德": [
        ("职业道德", CORE_WEIGHT), ("职业操守", HIGH_WEIGHT), ("警风", HIGH_WEIGHT),
        ("作风", NORMAL_WEIGHT), ("清廉", HIGH_WEIGHT), ("公正执法", HIGH_WEIGHT),
        ("执法为民", CORE_WEIGHT), ("文明执法", HIGH_WEIGHT), ("公正廉洁", HIGH_WEIGHT),
        ("秉公执法", HIGH_WEIGHT), ("道德规范", HIGH_WEIGHT),
    ],
    "人民警察职业纪律": [
        ("职业纪律", CORE_WEIGHT), ("纪律", NORMAL_WEIGHT), ("禁令", CORE_WEIGHT),
        ("条令", CORE_WEIGHT), ("违规", NORMAL_WEIGHT), ("处分", HIGH_WEIGHT),
        ("禁闭", HIGH_WEIGHT), ("督查", HIGH_WEIGHT), ("监察", HIGH_WEIGHT),
        ("违纪", HIGH_WEIGHT), ("警纪", HIGH_WEIGHT), ("从严治警", HIGH_WEIGHT),
    ],

    # --- 基础知识 ---
    "中国特色社会主义法治理论": [
        ("法治理论", CORE_WEIGHT), ("依法治国", CORE_WEIGHT), ("法治国家", HIGH_WEIGHT),
        ("法治政府", HIGH_WEIGHT), ("法治社会", HIGH_WEIGHT),
        ("全面依法治国", CORE_WEIGHT), ("法治思想", CORE_WEIGHT),
        ("依宪治国", HIGH_WEIGHT), ("法治体系", HIGH_WEIGHT),
        ("中国特色社会主义法治", CORE_WEIGHT),
    ],
    "法学基础理论": [
        ("法理学", CORE_WEIGHT), ("法学基础", CORE_WEIGHT), ("法律关系", HIGH_WEIGHT),
        ("法律规范", HIGH_WEIGHT), ("法律责任", HIGH_WEIGHT), ("法律效力", HIGH_WEIGHT),
        ("法的本质", CORE_WEIGHT), ("法的适用", HIGH_WEIGHT), ("法律解释", HIGH_WEIGHT),
        ("法系", HIGH_WEIGHT), ("法的渊源", HIGH_WEIGHT), ("法律部门", HIGH_WEIGHT),
        ("法律行为", HIGH_WEIGHT),
    ],
    "宪法基础知识": [
        ("宪法", CORE_WEIGHT), ("根本法", HIGH_WEIGHT), ("国家机构", HIGH_WEIGHT),
        ("公民权利", HIGH_WEIGHT), ("基本权利", HIGH_WEIGHT), ("国家权力", HIGH_WEIGHT),
        ("全国人大", HIGH_WEIGHT), ("国务院", NORMAL_WEIGHT),
        ("宪法修正", HIGH_WEIGHT), ("宪法监督", HIGH_WEIGHT),
        ("选举", NORMAL_WEIGHT), ("国家主席", HIGH_WEIGHT),
    ],
    "民法基础知识": [
        ("民法", CORE_WEIGHT), ("民法典", CORE_WEIGHT), ("民事", HIGH_WEIGHT),
        ("合同", NORMAL_WEIGHT), ("侵权", HIGH_WEIGHT), ("物权", HIGH_WEIGHT),
        ("债权", HIGH_WEIGHT), ("婚姻", NORMAL_WEIGHT), ("继承", HIGH_WEIGHT),
        ("人格权", HIGH_WEIGHT), ("代理", HIGH_WEIGHT), ("民事行为", HIGH_WEIGHT),
        ("自然人", HIGH_WEIGHT), ("法人", HIGH_WEIGHT), ("监护", HIGH_WEIGHT),
    ],
    "人民警察法基础知识": [
        ("人民警察法", CORE_WEIGHT), ("警察法", HIGH_WEIGHT), ("警察职权", CORE_WEIGHT),
        ("警察义务", CORE_WEIGHT), ("警察权限", CORE_WEIGHT), ("警察职责", CORE_WEIGHT),
        ("警察组织", HIGH_WEIGHT), ("警衔", HIGH_WEIGHT),
        ("武器警械", HIGH_WEIGHT), ("警察权利", HIGH_WEIGHT),
        ("警务保障", HIGH_WEIGHT), ("录用", HIGH_WEIGHT),
    ],
    "行政执法基础知识": [
        ("行政执法", CORE_WEIGHT), ("行政法", HIGH_WEIGHT), ("行政许可", HIGH_WEIGHT),
        ("行政强制", CORE_WEIGHT), ("行政处罚法", CORE_WEIGHT),
        ("行政复议法", CORE_WEIGHT), ("行政诉讼法", CORE_WEIGHT),
        ("国家赔偿法", HIGH_WEIGHT), ("行政程序", HIGH_WEIGHT),
        ("行政裁量", HIGH_WEIGHT), ("具体行政行为", CORE_WEIGHT),
        ("抽象行政行为", CORE_WEIGHT), ("治安管理处罚", HIGH_WEIGHT),
        ("治安处罚", HIGH_WEIGHT), ("突发事件应对", HIGH_WEIGHT),
        ("反恐怖主义", HIGH_WEIGHT),
    ],
    "刑事执法基础知识": [
        ("刑事执法", CORE_WEIGHT), ("刑法", HIGH_WEIGHT), ("刑事诉讼", HIGH_WEIGHT),
        ("犯罪构成", CORE_WEIGHT), ("故意", NORMAL_WEIGHT), ("过失", NORMAL_WEIGHT),
        ("正当防卫", CORE_WEIGHT), ("紧急避险", CORE_WEIGHT), ("共同犯罪", HIGH_WEIGHT),
        ("数罪并罚", HIGH_WEIGHT), ("刑罚", HIGH_WEIGHT), ("刑事证据", HIGH_WEIGHT),
        ("刑事程序", HIGH_WEIGHT), ("刑事侦查", HIGH_WEIGHT), ("立案", HIGH_WEIGHT),
        ("侦查", NORMAL_WEIGHT), ("起诉", NORMAL_WEIGHT), ("审判", NORMAL_WEIGHT),
        ("取保候审", HIGH_WEIGHT), ("逮捕", HIGH_WEIGHT),
    ],
    "公安机关性质与职能": [
        ("公安机关", CORE_WEIGHT), ("公安性质", CORE_WEIGHT), ("公安职能", CORE_WEIGHT),
        ("公安任务", CORE_WEIGHT), ("公安职权", HIGH_WEIGHT),
        ("人民民主专政", CORE_WEIGHT), ("治安行政", HIGH_WEIGHT),
        ("刑事司法", HIGH_WEIGHT), ("专门机关", HIGH_WEIGHT), ("武装性质", HIGH_WEIGHT),
    ],
    "公安工作根本原则": [
        ("根本原则", CORE_WEIGHT), ("党的领导", HIGH_WEIGHT), ("群众路线", CORE_WEIGHT),
        ("公安工作原则", CORE_WEIGHT), ("公安工作方针", CORE_WEIGHT),
        ("公安政策", HIGH_WEIGHT), ("专门工作.*群众路线", CORE_WEIGHT),
        ("宽严相济", HIGH_WEIGHT),
    ],
    "公安队伍建设": [
        ("公安队伍", CORE_WEIGHT), ("队伍建设", CORE_WEIGHT), ("公安民警", HIGH_WEIGHT),
        ("公安教育", HIGH_WEIGHT), ("公安培训", HIGH_WEIGHT), ("公安宣传", HIGH_WEIGHT),
        ("公安文化", HIGH_WEIGHT), ("正规化", HIGH_WEIGHT), ("专业化", HIGH_WEIGHT),
        ("职业化", HIGH_WEIGHT), ("从优待警", HIGH_WEIGHT), ("科技强警", HIGH_WEIGHT),
    ],
    "公安执法监督": [
        ("执法监督", CORE_WEIGHT), ("监督机制", CORE_WEIGHT), ("内部监督", HIGH_WEIGHT),
        ("外部监督", HIGH_WEIGHT), ("社会监督", HIGH_WEIGHT), ("舆论监督", HIGH_WEIGHT),
        ("检察监督", HIGH_WEIGHT), ("司法监督", HIGH_WEIGHT), ("人大监督", HIGH_WEIGHT),
        ("警务督察", CORE_WEIGHT), ("执法过错", CORE_WEIGHT),
        ("责任追究", HIGH_WEIGHT), ("执法规范化", CORE_WEIGHT), ("执法质量", HIGH_WEIGHT),
    ],

    # --- 基本警务能力 ---
    "宣传教育": [
        ("法制宣传", CORE_WEIGHT), ("安全教育", CORE_WEIGHT), ("防范宣传", CORE_WEIGHT),
        ("普法", HIGH_WEIGHT), ("宣讲", HIGH_WEIGHT), ("讲解", NORMAL_WEIGHT),
    ],
    "沟通协调": [
        ("沟通", CORE_WEIGHT), ("协调", CORE_WEIGHT), ("交流", NORMAL_WEIGHT),
        ("对话", HIGH_WEIGHT), ("协商", HIGH_WEIGHT), ("调解", NORMAL_WEIGHT),
        ("谈判", HIGH_WEIGHT), ("劝说", HIGH_WEIGHT), ("说服", HIGH_WEIGHT),
    ],
    "组织动员": [
        ("组织", NORMAL_WEIGHT), ("动员", CORE_WEIGHT), ("发动", HIGH_WEIGHT),
        ("号召", HIGH_WEIGHT), ("组织.*群众", CORE_WEIGHT), ("动员.*群众", CORE_WEIGHT),
        ("依靠.*群众", HIGH_WEIGHT), ("群防群治", CORE_WEIGHT),
    ],
    "服务群众": [
        ("服务", NORMAL_WEIGHT), ("便民", CORE_WEIGHT), ("利民", CORE_WEIGHT),
        ("上门", NORMAL_WEIGHT), ("帮扶", HIGH_WEIGHT), ("排忧解难", CORE_WEIGHT),
        ("办好事", HIGH_WEIGHT), ("解难题", HIGH_WEIGHT),
        ("服务.*群众", CORE_WEIGHT), ("受理.*求助", CORE_WEIGHT),
    ],
    "调查研究": [
        ("调查", NORMAL_WEIGHT), ("走访", CORE_WEIGHT), ("摸排", CORE_WEIGHT),
        ("调研", HIGH_WEIGHT), ("排查", CORE_WEIGHT), ("摸底", HIGH_WEIGHT),
        ("核实", CORE_WEIGHT),
    ],
    "纠纷化解": [
        ("纠纷", CORE_WEIGHT), ("矛盾", NORMAL_WEIGHT), ("调解", NORMAL_WEIGHT),
        ("化解", CORE_WEIGHT), ("调处", CORE_WEIGHT), ("和解", HIGH_WEIGHT),
        ("平息", HIGH_WEIGHT), ("争议", HIGH_WEIGHT), ("冲突", HIGH_WEIGHT),
        ("邻里", HIGH_WEIGHT), ("家庭矛盾", CORE_WEIGHT),
    ],
    "风险识别": [
        ("风险", NORMAL_WEIGHT), ("隐患", CORE_WEIGHT), ("识别", NORMAL_WEIGHT),
        ("预判", HIGH_WEIGHT), ("危机", NORMAL_WEIGHT), ("危险", NORMAL_WEIGHT),
        ("苗头", CORE_WEIGHT), ("征兆", HIGH_WEIGHT), ("预警", CORE_WEIGHT),
    ],
    "风险防范": [
        ("防范", CORE_WEIGHT), ("预防", HIGH_WEIGHT), ("防止", HIGH_WEIGHT),
        ("遏制", HIGH_WEIGHT), ("制止", HIGH_WEIGHT), ("杜绝", HIGH_WEIGHT),
        ("防控", CORE_WEIGHT), ("安全防范", CORE_WEIGHT), ("预防.*犯罪", CORE_WEIGHT),
    ],
    "信息收集": [
        ("信息", NORMAL_WEIGHT), ("情报", HIGH_WEIGHT), ("收集", CORE_WEIGHT),
        ("采集", HIGH_WEIGHT), ("获取", NORMAL_WEIGHT), ("搜集", HIGH_WEIGHT),
        ("情报信息", CORE_WEIGHT), ("信息.*工作", NORMAL_WEIGHT),
    ],
    "信息分析": [
        ("分析", NORMAL_WEIGHT), ("研判", CORE_WEIGHT), ("评估", NORMAL_WEIGHT),
        ("推断", NORMAL_WEIGHT), ("信息.*分析", CORE_WEIGHT),
        ("情报.*分析", CORE_WEIGHT), ("数据分析", HIGH_WEIGHT), ("综合研判", CORE_WEIGHT),
    ],
    "信息应用": [
        ("应用", NORMAL_WEIGHT), ("运用", NORMAL_WEIGHT), ("利用", NORMAL_WEIGHT),
        ("信息.*应用", CORE_WEIGHT), ("情报.*应用", CORE_WEIGHT),
        ("科技.*应用", HIGH_WEIGHT), ("信息技术", HIGH_WEIGHT),
    ],
    "巡逻": [
        ("巡逻", CORE_WEIGHT), ("巡查", CORE_WEIGHT), ("巡视", HIGH_WEIGHT),
        ("盘查", CORE_WEIGHT), ("设卡", CORE_WEIGHT), ("堵截", HIGH_WEIGHT),
        ("巡逻防控", CORE_WEIGHT), ("街面", HIGH_WEIGHT),
    ],
    "接警与处警": [
        ("接警", CORE_WEIGHT), ("处警", CORE_WEIGHT), ("出警", CORE_WEIGHT),
        ("现场", NORMAL_WEIGHT), ("处置", NORMAL_WEIGHT),
        ("受理.*报警", CORE_WEIGHT), ("报警", HIGH_WEIGHT), ("110", HIGH_WEIGHT),
    ],
    "安全检查": [
        ("安全检查", CORE_WEIGHT), ("安检", CORE_WEIGHT), ("消防检查", CORE_WEIGHT),
        ("隐患排查", CORE_WEIGHT), ("治安检查", CORE_WEIGHT),
        ("日常检查", HIGH_WEIGHT), ("专项检查", HIGH_WEIGHT),
    ],
    "安全保护": [
        ("安全保护", CORE_WEIGHT), ("保卫", CORE_WEIGHT), ("警卫", CORE_WEIGHT),
        ("守护", HIGH_WEIGHT), ("看护", HIGH_WEIGHT), ("看守", HIGH_WEIGHT),
        ("警戒", HIGH_WEIGHT), ("安全.*保卫", CORE_WEIGHT),
    ],
    "事态研判": [
        ("事态", CORE_WEIGHT), ("研判", NORMAL_WEIGHT),
        ("形势.*判断", CORE_WEIGHT), ("局势", HIGH_WEIGHT), ("态势", CORE_WEIGHT),
        ("预判", NORMAL_WEIGHT), ("走向", NORMAL_WEIGHT), ("趋势", NORMAL_WEIGHT),
        ("动向", HIGH_WEIGHT), ("评估.*形势", CORE_WEIGHT),
    ],
    "信息上报": [
        ("上报", CORE_WEIGHT), ("汇报", HIGH_WEIGHT), ("请示", NORMAL_WEIGHT),
        ("通报", NORMAL_WEIGHT), ("呈报", CORE_WEIGHT), ("报送", CORE_WEIGHT),
        ("上报.*信息", CORE_WEIGHT), ("报告.*情况", HIGH_WEIGHT),
    ],
    "合理处置": [
        ("处置", NORMAL_WEIGHT), ("处理", NORMAL_WEIGHT), ("措施", NORMAL_WEIGHT),
        ("应对", NORMAL_WEIGHT), ("解决", NORMAL_WEIGHT), ("依法.*处理", CORE_WEIGHT),
        ("果断", NORMAL_WEIGHT), ("及时.*处置", CORE_WEIGHT),
        ("妥善.*处理", CORE_WEIGHT), ("现场.*处置", CORE_WEIGHT),
    ],
    "善后恢复": [
        ("善后", CORE_WEIGHT), ("恢复", NORMAL_WEIGHT), ("重建", NORMAL_WEIGHT),
        ("安抚", CORE_WEIGHT), ("赔偿", NORMAL_WEIGHT), ("救治", HIGH_WEIGHT),
        ("清理", NORMAL_WEIGHT), ("恢复.*秩序", CORE_WEIGHT),
        ("后续.*处理", CORE_WEIGHT), ("跟进", NORMAL_WEIGHT),
    ],
}


# ============================================================
# 子科目快速检测关键词（用于二级分类）
# ============================================================

SUB_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    # 行测
    "政治理论": ["政治理论", "习近平", "马克思", "二十大", "方针政策", "政治立场", "政治敏锐"],
    "常识判断": ["常识", "经济常识", "文化常识", "科技常识", "法律常识", "时政热点", "社会常识", "生态常识"],
    "言语理解与表达": ["言语理解", "语言理解", "逻辑填空", "片段阅读", "语句排序", "中心理解", "填入", "横线"],
    "数量关系": ["数量关系", "数学运算", "数字推理", "工程问题", "行程问题", "排列组合", "概率", "数列"],
    "判断推理": ["判断推理", "图形推理", "逻辑判断", "类比推理", "定义判断", "削弱", "加强"],
    "资料分析": ["资料分析", "增长率", "同比", "环比", "统计表", "柱状图", "折线图", "比重"],
    "知觉速度与准确性": ["知觉速度", "知觉准确性", "同符", "数字区间", "字符替换"],
    # 科学推理：仅用分区名词本身作关键词。实测语料中「物理/化学/生物」类词
    # 归属常识判断（如「生物常识」），扩写会造成两个分区互抢，故按前序铁律
    # 「关键词靠语料穷举、不靠推理完备」保持最小词表。
    "科学推理": ["科学推理"],
    # 申论
    "归纳概括": ["概括", "归纳", "总结", "概述", "提炼"],
    "综合分析": ["分析", "综合", "评析", "评述", "理解", "解释", "现象", "观点分析"],
    "提出对策": ["对策", "措施", "建议", "方案", "办法", "应急", "机制"],
    "应用文写作": ["应用文", "公文", "报告", "函", "简报", "讲话稿", "倡议书", "案例"],
    "议论文写作": ["议论文", "作文", "文章写作", "论证", "论点", "政论文", "策论文"],
    # 公专
    "职业素养": [
        "职业素养", "职业道德", "职业纪律", "职业素质", "职业标准", "核心价值观", "忠诚",
        "警风", "廉洁", "清廉", "警纪", "禁令", "作风", "警容", "警服", "着装", "风纪",
        "收受", "礼品", "购物卡", "吃请", "受贿", "以权谋私", "违纪", "处分", "执法为民",
        "公正执法", "文明执法", "秉公执法", "警察形象", "为民服务", "从警", "政治立场",
        "政治敏锐", "党风廉政", "情趣健康", "纪律",
    ],
    "基础知识": [
        "法律", "法规", "法治", "法制", "依法", "违法", "合法", "法学", "法理", "法的作用",
        "宪法", "民法", "刑法", "行政法", "诉讼法", "刑事诉讼", "刑事政策", "认罪",
        "治安", "处罚", "罚款", "拘留", "逮捕", "犯罪", "犯罪嫌疑人", "罪犯", "刑罚",
        "侦查", "取证", "证据", "起诉", "审判", "诉讼", "法院", "检察院", "管辖", "立法",
        "司法", "行政处罚", "行政复议", "治安处罚", "危险物品", "枪支", "爆炸", "刑事",
        "权利", "义务", "责任", "公安体制", "公安改革", "公安管理", "公安机关", "人民警察",
        "派出所", "诈骗", "盗窃", "抢劫", "强奸", "共谋", "从犯", "主犯", "中止", "未遂",
        "防卫", "紧急避险", "酒驾", "醉驾", "交通违法", "立案", "取保候审",
    ],
    "基本警务能力": [
        "警务能力", "警务", "勤务", "巡逻", "盘查", "盘问", "接警", "处警", "出警",
        "安全检查", "安检", "警械", "武器", "控制", "应急", "实战", "战术", "防范", "走访",
        "排查", "摸排", "警力", "发案", "踩踏", "避险处", "纠纷", "沟通", "协调", "调解",
        "帮扶", "宣传", "警戒", "保卫", "守卫", "看护", "现场处置", "应急处置", "群体性事件",
        "疏导", "押解", "逃生", "安全因素", "安全合约", "临时停车", "临时停放", "警情",
        "研判", "事态", "群众工作", "宣传教育", "信息收集", "信息分析", "服务群众", "监控",
        "交通管制", "交通疏导",
    ],
}


# ============================================================
# 分类引擎
# ============================================================

class QuestionClassifier:
    """三级分类引擎：科目→子科目→考点"""

    MIN_CONFIDENCE = MIN_CONFIDENCE
    TEXT_SCAN_LENGTH = TEXT_SCAN_LENGTH

    def classify(self, content: str, subject_id: int) -> ClassifyResult:
        """
        对单道题目进行完整三级分类（方案 v3 W1-2：**一律返回真实 DB ID**）。

        子科目 ID 与考点 ID 均由 `_load_taxonomy()` 运行时从 `sub_categories` /
        `knowledge_point` 两表反查。**不再返回任何硬编码假 ID**；
        若 DB 不可用，退化为「有名称、无 ID」而不是「挂错 ID」。

        Args:
            content: 题目内容文本
            subject_id: 科目ID (1=行测, 2=申论, 3=公专)

        Returns:
            ClassifyResult: 包含子科目、考点和置信度，ID 均为真实 DB 值
        """
        sc_name, sc_confidence, kp_name, kp_confidence, ep_name = self._classify_names(
            content, subject_id
        )

        if sc_name is None:
            return ClassifyResult(
                subject_id, None, UNCLASSIFIED, None, UNCLASSIFIED, sc_confidence
            )

        sc_id = self._sub_category_id(subject_id, sc_name)
        kp_id = self._knowledge_point_id(subject_id, sc_id, kp_name)

        # 考点层（level=3）：仅在知识点已命中且属于已建考点层的知识点时生效，
        # 否则返回空以保持三级结构的向后兼容。
        ep_id = self._exam_point_id(kp_name, ep_name)

        return ClassifyResult(
            subject_id, sc_id, sc_name, kp_id, kp_name or UNCLASSIFIED,
            kp_confidence, ep_id, ep_name or ""
        )

    def classify_with_db(self, content: str, subject_id: int, db_session) -> ClassifyResult:
        """
        使用传入的 DB session 解析真实 ID（方案 v3 W1-2 与 `classify()` 语义合并）。

        与 `classify()` 的唯一区别：ID 反查**优先通过调用方 session** 执行，
        这样调用方在同一事务中未提交的新增 taxonomy 也能被识别；同时结果
        会回填进程内缓存，供后续 `classify()` 无参调用复用。

        返回值与 `classify()` 完全同构（8 字段，含 exam_point_*），
        不再像旧版那样丢掉 exam_point_id / exam_point_name。

        Args:
            content: 题目内容
            subject_id: 科目ID
            db_session: SQLAlchemy session

        Returns:
            ClassifyResult: 含真实DB ID的分类结果
        """
        sc_name, sc_confidence, kp_name, kp_confidence, ep_name = self._classify_names(
            content, subject_id
        )

        if sc_name is None:
            return ClassifyResult(
                subject_id, None, UNCLASSIFIED, None, UNCLASSIFIED, sc_confidence
            )

        sc_id = self._sub_category_id(subject_id, sc_name, db_session=db_session)
        kp_id = self._knowledge_point_id(subject_id, sc_id, kp_name, db_session=db_session)
        ep_id = self._exam_point_id(kp_name, ep_name, db_session=db_session)

        return ClassifyResult(
            subject_id, sc_id, sc_name, kp_id, kp_name or UNCLASSIFIED,
            kp_confidence, ep_id, ep_name or ""
        )

    def _classify_names(self, content: str, subject_id: int):
        """分类的名称层判定（不含任何 ID）。

        Returns:
            (子科目名, 子科目置信度, 考点名, 考点置信度, 考点层名)
            子科目名为 None 表示无法分类（空文本或置信度不足）。
        """
        if not content:
            return None, 0.0, None, 0.0, None

        # 预处理
        text = content[:self.TEXT_SCAN_LENGTH]
        text = self._normalize(text)

        # 二级分类：确定子科目
        sc_name, sc_confidence = self._detect_subcategory(text, subject_id)

        if not sc_name or sc_confidence < self.MIN_CONFIDENCE:
            return None, sc_confidence, None, 0.0, None

        # 三级分类：确定考点
        kp_name, kp_confidence = self._detect_knowledge_point(text, sc_name)

        # 考点层（level=3）：仅在知识点已命中且属于已建考点层的知识点时生效，
        # 否则返回空以保持三级结构的向后兼容。
        ep_name, _ep_confidence = self._detect_exam_point(text, kp_name or "")

        return sc_name, sc_confidence, kp_name, kp_confidence, ep_name

    # ---------- ID 反查（单一事实来源 = taxonomy 三表） ----------

    def _sub_category_id(self, subject_id: int, sc_name: Optional[str],
                         db_session=None) -> Optional[int]:
        """子科目名 → `sub_categories.id`（真实 DB ID，无则 None）。"""
        if not sc_name or sc_name == UNCLASSIFIED:
            return None
        if _load_taxonomy(db_session):
            return SUB_CATEGORY_IDS.get((subject_id, sc_name))
        return None

    def _knowledge_point_id(self, subject_id: int, sc_id: Optional[int],
                            kp_name: Optional[str], db_session=None) -> Optional[int]:
        """考点名 → `knowledge_point.point_id`（真实 DB ID，无则 None）。

        优先按 (子科目ID, 考点名) 精确定位；子科目 ID 缺失时
        （如 DB 里该考点尚未回填 sub_category_id）降级到
        (科目ID, 考点名) 的窄范围回退。
        """
        if not kp_name or kp_name == UNCLASSIFIED:
            return None
        if not _load_taxonomy(db_session):
            return None
        if sc_id:
            pid = _KP_ID_BY_SC.get((sc_id, kp_name))
            if pid is not None:
                return pid
        return _KP_ID_BY_SUBJECT.get((subject_id, kp_name))

    def _exam_point_id_map(self, db_session=None) -> Dict[Tuple[str, str], int]:
        """(父知识点名, 考点名) → `knowledge_point.point_id`，运行时从 DB 反查。

        带进程内缓存，避免每次分类都查库。
        """
        _load_taxonomy(db_session)
        return _EP_ID

    def _exam_point_id(self, kp_name: Optional[str], ep_name: Optional[str],
                       db_session=None) -> Optional[int]:
        """考点层名 → 真实 `knowledge_point.point_id`（无则 None）。"""
        if not kp_name or not ep_name:
            return None
        if not _load_taxonomy(db_session):
            return None
        return _EP_ID.get((kp_name, ep_name))

    def _normalize(self, text: str) -> str:
        """预处理文本：全角转半角、折叠空白、拉丁字母大写（消除大小写敏感）"""
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:  # 全角空格
                result.append(' ')
            else:
                result.append(ch)
        text = ''.join(result)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.upper()

    def _detect_subcategory(self, text: str, subject_id: int) -> Tuple[Optional[str], float]:
        """
        检测子科目。
        优先用 SUB_CATEGORY_KEYWORDS，无匹配时回退到 KNOWLEDGE_POINT_KEYWORDS 聚合计分。
        返回 (子科目名称, 置信度)
        """
        subject_sc_names = {
            1: ["政治理论", "常识判断", "言语理解与表达", "数量关系", "判断推理", "资料分析", "知觉速度与准确性", "科学推理"],
            2: ["归纳概括", "综合分析", "提出对策", "应用文写作", "议论文写作"],
            3: ["职业素养", "基础知识", "基本警务能力"],
        }
        candidates = subject_sc_names.get(subject_id, [])
        if not candidates:
            return None, 0.0

        # 第一轮：子科目关键词
        scores = {}
        for sc_name in candidates:
            keywords = SUB_CATEGORY_KEYWORDS.get(sc_name, [])
            score = sum(1.0 for kw in keywords if kw in text)
            if score > 0:
                scores[sc_name] = score

        # 第二轮回退：如果第一轮全无匹配，使用考点关键词聚合计分
        if not scores:
            for sc_name in candidates:
                kp_list = SUB_CATEGORY_KP_MAP.get(sc_name, [])
                total_kp_score = 0.0
                for kp_name in kp_list:
                    kw_list = KNOWLEDGE_POINT_KEYWORDS.get(kp_name, [])
                    for kw, weight in kw_list:
                        if '.*' in kw:
                            try:
                                if re.search(kw, text):
                                    total_kp_score += weight
                            except re.error:
                                if kw in text:
                                    total_kp_score += weight
                        else:
                            if kw in text:
                                total_kp_score += weight
                if total_kp_score > 0:
                    scores[sc_name] = total_kp_score

        if not scores:
            return None, 0.0

        best = max(scores, key=scores.get)
        best_score = scores[best]
        total = sum(scores.values())
        confidence = min(best_score / max(total, 1), 1.0)

        if len(scores) == 1 and best_score >= 3:
            confidence = 0.8 + min(best_score * 0.05, 0.2)

        return best, round(confidence, 3)

    def _detect_exam_point(self, text: str, kp_name: str) -> Tuple[Optional[str], float]:
        """
        考点层判定（level=3）：在已确定知识点后，再细分到该知识点下的考点。

        仅对已建考点层的 5 个知识点生效，其余知识点返回 (None, 0.0)，
        调用方据此回退到知识点级展示，保证向后兼容。

        Returns:
            (考点名, 置信度)；无匹配时考点名为 None。
        """
        if not kp_name:
            return None, 0.0

        # EXAM_POINT_PARENT 以「考点名」为键、值为「所属知识点名」，
        # 因此这里不能用 kp_name 直接查表（那会恒为 None 导致方法永不生效），
        # 正确做法是收集该知识点名下的所有考点。
        target_points = [ep for ep, parent in EXAM_POINT_PARENT.items() if parent == kp_name]
        if not target_points:
            return None, 0.0

        scores: Dict[str, float] = {}
        for ep_name in target_points:
            total = 0.0
            for kw, weight in EXAM_POINT_KEYWORDS.get(ep_name, []):
                if kw in text:
                    total += weight
            if total > 0:
                scores[ep_name] = total

        if not scores:
            return None, 0.0

        best = max(scores, key=lambda k: scores[k])
        best_score = scores[best]
        total_score = sum(scores.values())
        confidence = min(best_score / max(total_score, 1), 1.0)
        if confidence < self.MIN_CONFIDENCE:
            return None, confidence
        return best, confidence

    def _detect_knowledge_point(self, text: str, sc_name: str) -> Tuple[Optional[str], float]:
        """
        在已确定子科目的前提下检测具体考点。
        返回 (考点名称, 置信度)
        """
        kp_list = SUB_CATEGORY_KP_MAP.get(sc_name, [])
        if not kp_list:
            return None, 0.0

        scores = {}
        for kp_name in kp_list:
            kw_list = KNOWLEDGE_POINT_KEYWORDS.get(kp_name, [])
            if not kw_list:
                continue

            score = 0.0
            for kw, weight in kw_list:
                # 正则关键词
                if '.*' in kw or '.*' in kw:
                    try:
                        if re.search(kw, text):
                            score += weight
                    except re.error:
                        if kw in text:
                            score += weight
                else:
                    if kw in text:
                        score += weight

            if score > 0:
                scores[kp_name] = score

        if not scores:
            return None, 0.0

        best = max(scores, key=scores.get)
        best_score = scores[best]
        total = sum(scores.values())
        confidence = min(best_score / max(total, 1), 1.0)

        # 高绝对分数意味着高置信度
        if best_score >= 5:
            confidence = max(confidence, 0.7)
        if best_score >= 8:
            confidence = max(confidence, 0.85)

        return best, round(confidence, 3)


# ============================================================
# 便利函数（向后兼容旧 _detect_subcategory）
# ============================================================

_classifier_instance = None

def get_classifier() -> QuestionClassifier:
    """获取分类器单例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = QuestionClassifier()
    return _classifier_instance


def detect_subcategory_enhanced(subject_id: int, content: str, type_name: str = '') -> str:
    """
    增强版子科目检测（向后兼容旧接口）。
    返回子科目名称字符串。
    注意：'无法分类' 不在 question_bank ENUM 允许值中，必须回退为 '无'。

    方案 v3 W1-2：内部转发到 `classify()`（现强制解析真实 DB ID），
    但本函数只消费 `sub_category_name` 名称层，对外契约与返回字符串不变。
    """
    classifier = get_classifier()
    result = classifier.classify(content, subject_id)
    sc = result.sub_category_name
    if not sc or sc == UNCLASSIFIED:
        return '无'
    return sc
