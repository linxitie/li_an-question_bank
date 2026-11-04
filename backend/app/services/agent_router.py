# -*- coding: utf-8 -*-
"""
模块7 v2 - 多 Agent 备考陪伴系统：Agent 路由 + 档案上下文装配 + 长期记忆抽取
设计要点（token 极简）：
- 路由用关键词规则打分，不调 LLM（零额外 token）
- 档案上下文只取摘要与统计，不塞原文
- 长期记忆从画像确定性抽取（幂等 upsert），不依赖 LLM
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ==================== Agent 定义与 system prompt ====================
# 每个 Agent 独立 system prompt（简洁，控制 token）

AGENT_META: Dict[str, Dict[str, str]] = {
    "choose_post": {
        "name": "选岗顾问",
        "prompt": (
            "你是'砺安小智'的选岗顾问。考生会问'我能报哪些岗位''选岗建议''地区/专业/条件能否报考'等。"
            "回答要点：结合公安联考的岗位类型（公安系统内岗位、按生源地与专业限制）、考生条件给出筛选思路；"
            "提醒以当年官方招录公告为准，不确定就说'以官方公告为准'。回答 250 字内，分点。"
        ),
        "keywords": [
            ("选岗", 3),
            ("岗位", 3),
            ("报哪", 3),
            ("报考条件", 3),
            ("生源地", 3),
            ("职位", 2),
            ("调剂", 2),
            ("入职", 2),
            ("分配", 2),
            ("安置", 2),
            ("户籍", 2),
            ("专业限制", 3),
            ("限专业", 3),
        ],
    },
    "interview": {
        "name": "面试教练",
        "prompt": (
            "你是'砺安小智'的面试教练。考生会问公安联考结构化面试怎么准备、要一道面试题、答题框架、模拟追问等。"
            "回答要点：先给结构化面试常见题型与答题框架（见下方面试题库框架）；"
            "出模拟题时附示范要点和一个追问；表达用'第一/第二/第三'条理作答，结合公安岗位实际，不空喊口号。"
            "回答 300 字内，条理清晰。"
        ),
        "keywords": [
            ("面试", 3),
            ("结构化", 3),
            ("答题框架", 3),
            ("模拟", 2),
            ("考官", 2),
            ("自我介绍", 2),
            ("应急处突", 3),
            ("综合分析", 3),
            ("组织管理", 3),
            ("人际沟通", 3),
            ("追问", 3),
            ("答题思路", 2),
            ("上岸面试", 2),
        ],
        # 结构化面试四类题型答题框架（命中面试教练时随 system prompt 注入，token 受控）
        "bank_frame": (
            "【结构化面试四类题型答题框架】"
            "①综合分析（现象/政策/观点）：亮明表态→分析原因与正反影响→提出对策或结合自身践行；"
            "②应急处突（群众冲突/执法现场/突发事件）：控制现场保安全→快速研判分轻重缓急处置→善后汇报与长效防范；"
            "③组织管理（宣传/培训/调研/活动）：明确目的意义→事前定方案（人员物资流程预案）→事中协调推进→事后总结复盘归档；"
            "④人际沟通（与同事/群众/领导的矛盾）：换位思考稳定情绪→主动沟通澄清事实→就事论事解决问题→反思改进维护关系。"
            "通用要求：开头扣题表态，主体分点，结尾落到公安岗位做法；不背模板空话。"
        ),
    },
    "psychology": {
        "name": "心理辅导",
        "prompt": (
            "你是'砺安小智'的心理辅导师。考生表达焦虑、压力、失眠、自我怀疑、疲惫等情绪问题。"
            "回答要点：先共情，不评判；再用温和专业的语言疏导，给一个当下可执行的调节小方法（如呼吸法、任务拆解）。"
            "不直接讲题、不灌鸡汤。回答 150 字内，语气像靠谱的学长学姐。若对方情绪严重异常，提示寻求专业心理支持。"
        ),
        "keywords": [
            ("焦虑", 3),
            ("压力", 3),
            ("心态", 3),
            ("紧张", 3),
            ("失眠", 3),
            ("睡不着", 3),
            ("崩溃", 3),
            ("坚持不住", 3),
            ("想放弃", 3),
            ("没信心", 3),
            ("慌", 2),
            ("emo", 2),
            ("烦躁", 2),
            ("emo了", 2),
            ("累", 1),
        ],
    },
    "shenlun": {
        "name": "申论教练",
        "prompt": (
            "你是'砺安小智'的申论教练。考生会问申论归纳概括、综合分析、提出对策、公文写作、大作文等。"
            "回答要点：给方法框架+示例结构；批改思路时说清采分点与常见失分；涉及范文只给要点不给整篇。"
            "回答 300 字内，分点。"
        ),
        "keywords": [
            ("申论", 3),
            ("大作文", 3),
            ("归纳概括", 3),
            ("综合分析题", 3),
            ("提出对策", 3),
            ("公文", 2),
            ("应用文", 3),
            ("作文", 2),
            ("材料题", 2),
            ("议论文", 2),
            ("策论文", 3),
            ("分论点", 3),
        ],
    },
    "xingce": {
        "name": "行测讲师",
        "prompt": (
            "你是'砺安小智'的行测讲师。考生会问行测言语理解、数量关系、判断推理、资料分析、常识判断的题与技巧。"
            "回答要点：先给思路/口诀，再讲解析；计算类给关键步骤即可，不用长篇演算。"
            "回答 300 字内，分点。"
        ),
        "keywords": [
            ("行测", 3),
            ("资料分析", 3),
            ("数量关系", 3),
            ("言语理解", 3),
            ("判断推理", 3),
            ("逻辑填空", 3),
            ("图形推理", 3),
            ("类比推理", 3),
            ("片段阅读", 3),
            ("常识", 2),
            ("速算", 2),
            ("蒙题", 2),
        ],
    },
    "gongzhuan": {
        "name": "公专导师",
        "prompt": (
            "你是'砺安小智'的公安专业知识导师。考生会问公安专业科目知识点、法条适用、情景题、执法规范等。"
            "回答要点：结合《公安专业科目》考纲与常用法律法规（治安管理处罚法、人民警察法、刑法等）作答，"
            "法条引用到条即可，注明'以现行有效法条为准'，不编造条文。回答 300 字内，分点。"
        ),
        "keywords": [
            ("公专", 3),
            ("公安专业", 3),
            ("法条", 2),
            ("治安管理处罚法", 3),
            ("人民警察法", 3),
            ("情景题", 3),
            ("执法", 2),
            ("盘查", 2),
            ("逮捕", 2),
            ("拘留", 2),
            ("刑法", 2),
            ("行政处罚", 3),
        ],
    },
}

GENERAL_AGENT_ID = "qa"
GENERAL_AGENT_NAME = "联考小智"
GENERAL_SYSTEM_PROMPT = (
    "你是'砺安小智'，一名公安联考备考助手。考生会问行测、申论、公安专业科目、备考方法等。"
    "请准确、简洁作答；不确定的明确说'建议查阅官方教材/公告'，不要编造。回答 300 字内，条理清晰。"
)

_ROUTE_THRESHOLD = 3


def route_agent(message: str) -> Tuple[str, str, int]:
    """
    关键词规则路由：返回 (agent_id, agent_name, score)。
    score >= _ROUTE_THRESHOLD 才走专业 Agent，否则通用兜底。
    同一关键词命中多个 Agent 时取最高分；同分按定义顺序。
    """
    text = (message or "").strip().lower()
    best_id = GENERAL_AGENT_ID
    best_score = 0
    for agent_id, meta in AGENT_META.items():
        score = 0
        for kw, w in meta["keywords"]:
            if kw.lower() in text:
                score += w
        if score > best_score:
            best_score = score
            best_id = agent_id
    if best_score < _ROUTE_THRESHOLD:
        return GENERAL_AGENT_ID, GENERAL_AGENT_NAME, best_score
    return best_id, AGENT_META[best_id]["name"], best_score


def agent_system_prompt(agent_id: str) -> str:
    if agent_id == GENERAL_AGENT_ID or agent_id not in AGENT_META:
        return GENERAL_SYSTEM_PROMPT
    meta = AGENT_META[agent_id]
    parts = [meta["prompt"]]
    if meta.get("bank_frame"):
        parts.append(meta["bank_frame"])
    return "\n".join(parts)


# ==================== 结构化面试示例题库（可扩展，零 LLM 取题） ====================
# 每个题型 2 道典型题 + 答题要点；模拟任务按题型抽取注入，避免一次性塞满上下文。
INTERVIEW_BANK: Dict[str, List[Dict[str, List[str]]]] = {
    "综合分析": [
        {
            "question": "有人说“基层民警既要会破案办案，也要会做群众工作”，谈谈你的理解。",
            "points": [
                "破题：执法办案与群众工作相辅相成，群众路线是公安工作的根本路线。",
                "办案维护社会治安与法律权威；群众工作获取线索、化解矛盾、提升执法公信力。",
                "践行：熟练执法业务的同时主动下沉社区、倾听诉求、用群众听得懂的话普法服务。",
            ],
        },
        {
            "question": "现在很多社区推行“警民议事会”制度，你怎么看？",
            "points": [
                "表态：是枫桥经验与共建共治的落地，值得肯定。",
                "意义：提前化解邻里与治安隐患，密切警民关系，降低接处警成本。",
                "完善建议：固定议事周期、形成问题清单闭环办理、结果向居民反馈。",
            ],
        },
    ],
    "应急处突": [
        {
            "question": "你在巡逻时发现两名群众因摊位争执升级为肢体冲突，周围有不少围观群众，你如何处置？",
            "points": [
                "第一时间上前分开双方、控制现场，确认有无人员受伤并报告指挥中心。",
                "分别询问起因、调取周边监控，依法依规调解，防止二次冲突和舆情围观。",
                "事后登记信息、跟进调解结果，必要时移交属地派出所，向周边商户做安全提示。",
            ],
        },
        {
            "question": "接到群众报警称辖区楼道有疑似易燃易爆物品，你作为先期到场民警怎么办？",
            "points": [
                "划定警戒范围、疏散群众、严禁明火与电子设备靠近，立即上报并请求专业排爆力量。",
                "核实物品来源与危险性，配合专业人员处置，保护现场物证。",
                "事后排查楼道堆物隐患、开展安全宣传，形成处置记录归档。",
            ],
        },
    ],
    "组织管理": [
        {
            "question": "单位让你牵头组织一次辖区反诈宣传进校园活动，你怎么组织？",
            "points": [
                "目的：提升学生反诈意识，压发电信网络诈骗案件。",
                "事前：对接学校确定时间场地与人数，准备案例短片、宣传册与互动问答，分工明确、留应急预案。",
                "事中：讲解常见套路（刷单、冒充客服、游戏交易），现场答疑与扫码测试，维持秩序。",
                "事后：收集反馈、留存照片台账，联合学校持续推送提醒，总结经验固化做法。",
            ],
        },
        {
            "question": "领导安排你调研辖区夜间治安状况，你如何开展？",
            "points": [
                "明确调研目标：掌握高发时段、地段与警情类型，指导布控。",
                "准备：整理近三个月接处警数据，设计访谈与蹲点路线，分两组配合社区民警。",
                "实施：实地查看夜市、公交站等重点部位，访谈商户与居民，记录问题。",
                "汇总：形成数据图表与问题清单，提出巡逻布控和宣传建议报领导参考。",
            ],
        },
    ],
    "人际沟通": [
        {
            "question": "你和老民警搭档出警，对方经验丰富但不采纳你的建议，你怎么办？",
            "points": [
                "摆正心态：尊重老同志经验，不急于争辩，先配合把任务完成。",
                "选合适时机委婉说明建议依据，倾听其顾虑，求同存异。",
                "事后复盘请教、取长补短，在协作中建立信任、共同提升。",
            ],
        },
        {
            "question": "群众对你的处理结果不满意，当场情绪激动指责你偏袒一方，你如何应对？",
            "points": [
                "先稳定对方情绪、请其到安静场所沟通，避免在街头激化围观。",
                "耐心倾听诉求，对照法定程序与证据说明处理依据，不激化矛盾。",
                "对符合复议申诉途径的告知权利，确有不足的及时上报纠正，事后反思沟通方式。",
            ],
        },
    ],
}

INTERVIEW_QTYPES = list(INTERVIEW_BANK.keys())


def interview_sample(qtype: str = "", index: int = 0) -> str:
    """按题型取一道示例题与答题要点；题型为空或越界时回退综合分析首题。返回可注入文本。"""
    qtype = (qtype or "").strip()
    if qtype not in INTERVIEW_BANK:
        qtype = "综合分析"
    bank = INTERVIEW_BANK[qtype]
    item = bank[index % len(bank)]
    lines = [f"【示例·{qtype}】题目：{item['question']}", "答题要点："]
    lines += [f"{i + 1}. {p}" for i, p in enumerate(item["points"])]
    return "\n".join(lines)


def assemble_context(user_id: int, db) -> str:
    """
    档案上下文装配（"带着档案来对话"）：只取摘要与统计，控制 token。
    来源：user_profile + 当前学习计划 + 学情统计（做题量/正确率/错题分布/最近错题Top3）。
    返回拼接好的上下文块；无档案时返回空串。
    """
    from ..models.models import PracticeRecord, StudyGoal, UserProfile, WrongQuestionPersonal

    parts: List[str] = []

    # 1. 画像（模块4共享）
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id, UserProfile.profile_status == 1)
        .first()
    )
    if profile:
        p = []
        if profile.grade:
            p.append(f"年级/阶段：{profile.grade}")
        if profile.exam_date:
            p.append(f"目标考试：{profile.exam_date}")
        if profile.target_score:
            p.append(f"目标分数：{profile.target_score}")
        if profile.self_level:
            p.append(f"自评水平：{profile.self_level}")
        if profile.daily_hours:
            p.append(f"每日可学时长：{profile.daily_hours}小时")
        if profile.subject_strengths:
            p.append(f"优势科目：{profile.subject_strengths}")
        if profile.subject_weaknesses:
            p.append(f"薄弱科目：{profile.subject_weaknesses}")
        if p:
            parts.append("【考生档案】" + "；".join(p) + "。")

    # 2. 当前学习计划摘要 + 今日任务数
    plan = (
        db.query(StudyGoal)
        .filter(StudyGoal.user_id == user_id, StudyGoal.status == 1, StudyGoal.plan_id.isnot(None))
        .order_by(StudyGoal.create_time.desc())
        .first()
    )
    if plan:
        import json as _json

        meta = {}
        try:
            meta = _json.loads(plan.plan_meta or "{}")
        except (ValueError, TypeError):
            meta = {}
        summary = str(meta.get("summary", ""))[:120]
        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        today_total = (
            db.query(StudyGoal)
            .filter(
                StudyGoal.user_id == user_id, StudyGoal.status == 1, StudyGoal.task_date == today
            )
            .count()
        )
        plan_parts = [f"当前备考计划：{summary}。今日任务 {today_total} 项"]
        if meta.get("phases"):
            plan_parts.append(
                f"阶段规划：{'；'.join(str(x.get('name', '')) for x in meta['phases'][:3])}"
            )
        parts.append("【学习计划】" + "；".join(plan_parts) + "。")

    # 3. 学情统计：做题量 / 正确率 / 错题分布 / 最近错题 Top3 / 模考成绩
    practice_total = db.query(PracticeRecord).filter(PracticeRecord.user_id == user_id).count()
    practice_correct = (
        db.query(PracticeRecord)
        .filter(PracticeRecord.user_id == user_id, PracticeRecord.is_correct == 1)
        .count()
    )
    acc = round(practice_correct / practice_total * 100) if practice_total else None
    wrong_total = (
        db.query(WrongQuestionPersonal).filter(WrongQuestionPersonal.user_id == user_id).count()
    )
    study_parts = []
    if practice_total:
        study_parts.append(f"累计做题 {practice_total} 题，正确率 {acc}%")
    if wrong_total:
        study_parts.append(f"错题本 {wrong_total} 题")
    # 错题科目分布 Top3 + 掌握度
    try:
        from sqlalchemy import func

        from ..models.models import QuestionSubject

        subj_rows = (
            db.query(QuestionSubject.subject_name, func.count(WrongQuestionPersonal.wrong_id))
            .join(QuestionSubject, WrongQuestionPersonal.subject_id == QuestionSubject.subject_id)
            .filter(
                WrongQuestionPersonal.user_id == user_id,
                WrongQuestionPersonal.collection_type == "WRONG",
            )
            .group_by(QuestionSubject.subject_name)
            .order_by(func.count(WrongQuestionPersonal.wrong_id).desc())
            .limit(3)
            .all()
        )
        if subj_rows:
            study_parts.append(
                "薄弱科目：" + "、".join(f"{name}({cnt}题)" for name, cnt in subj_rows)
            )
        mastery = (
            db.query(
                WrongQuestionPersonal.mastery_level, func.count(WrongQuestionPersonal.wrong_id)
            )
            .filter(
                WrongQuestionPersonal.user_id == user_id,
                WrongQuestionPersonal.collection_type == "WRONG",
            )
            .group_by(WrongQuestionPersonal.mastery_level)
            .all()
        )
        if mastery:
            parts_m = [f"{m}({c})" for m, c in mastery]
            study_parts.append("错题掌握度：" + "、".join(parts_m))
    except Exception as e:
        logger.warning("错题分布统计失败: %s", e)
    # B：错题明细（最近3条 WRONG：科目/题干摘要/我的错选/正解/掌握度；
    # 每条限长，防 token 爆炸；无关联题目时 outerjoin 兜底不报错）
    try:
        from ..models.models import QuestionBank

        wrong_details = (
            db.query(WrongQuestionPersonal, QuestionBank, QuestionSubject.subject_name)
            .outerjoin(QuestionBank, WrongQuestionPersonal.question_id == QuestionBank.question_id)
            .outerjoin(
                QuestionSubject, WrongQuestionPersonal.subject_id == QuestionSubject.subject_id
            )
            .filter(
                WrongQuestionPersonal.user_id == user_id,
                WrongQuestionPersonal.collection_type == "WRONG",
            )
            .order_by(WrongQuestionPersonal.add_time.desc())
            .limit(3)
            .all()
        )
        if wrong_details:
            mastery_cn = {"UNMASTERED": "未掌握", "PARTIAL": "部分掌握", "MASTERED": "已掌握"}
            detail_parts = []
            for w, q, subj_name in wrong_details:
                stem = (getattr(q, "question_content", None) or (w.user_answer or "无题面记录"))[
                    :30
                ]
                mine = (w.user_answer or "未记录")[:12]
                right = (getattr(q, "answer", None) or "缺正解")[:12]
                mastery = mastery_cn.get(w.mastery_level, w.mastery_level or "")
                detail_parts.append(
                    f"[{subj_name or '未分科'}] {stem}｜错选:{mine}｜正解:{right}｜{mastery}"
                )
            study_parts.append("错题明细：" + "；".join(detail_parts))
    except Exception as e:
        logger.warning("错题明细装配失败: %s", e)
    # 模考成绩（最近3条已评分）
    try:
        from ..models.models import ExamPaper, ExamRecord

        exams = (
            db.query(ExamRecord, ExamPaper.paper_name)
            .join(ExamPaper, ExamRecord.paper_id == ExamPaper.paper_id)
            .filter(
                ExamRecord.user_id == user_id,
                ExamRecord.is_scored == 1,
                ExamRecord.is_completed == 1,
            )
            .order_by(ExamRecord.submit_time.desc())
            .limit(3)
            .all()
        )
        if exams:
            score_parts = []
            for rec, title in exams:
                t = rec.submit_time or rec.create_time
                score_parts.append(
                    f"{title or '模考'}:{rec.total_score}分({t.strftime('%m-%d') if t else '-'})"
                )
            study_parts.append("模考成绩：" + "；".join(score_parts))
    except Exception as e:
        logger.warning("模考成绩统计失败: %s", e)
    if study_parts:
        parts.append("【学情】" + "；".join(study_parts) + "。")

    # 4. 备考轨迹（长期陪伴：进度/打卡/里程碑）
    try:
        traj = build_trajectory(user_id, db)
        if traj:
            parts.append(traj)
    except Exception as e:
        logger.warning("轨迹装配失败: %s", e)

    if not parts:
        return ""
    return "以下为该考生的档案摘要，回答时请自然结合（不要复述整段）：\n" + "\n".join(parts)


def build_trajectory(user_id: int, db) -> str:
    """
    备考轨迹（长期陪伴）：计划总进度 / 连续打卡 / 阶段进展 / 里程碑记忆。
    零 LLM、纯统计，token 受限。无数据返回空串。
    """
    from datetime import datetime

    from ..models.models import StudyGoal, UserMemory

    plan = (
        db.query(StudyGoal)
        .filter(StudyGoal.user_id == user_id, StudyGoal.status == 1, StudyGoal.plan_id.isnot(None))
        .order_by(StudyGoal.create_time.desc())
        .first()
    )
    if not plan:
        return ""

    total = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == user_id, StudyGoal.plan_id == plan.plan_id, StudyGoal.status == 1
        )
        .count()
    )
    done = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == user_id,
            StudyGoal.plan_id == plan.plan_id,
            StudyGoal.status == 1,
            StudyGoal.is_completed == 1,
        )
        .count()
    )
    parts = []
    if total:
        pct = round(done / total * 100)
        parts.append(f"备考总进度 {done}/{total}（{pct}%）")
    streak = 0
    cursor = datetime.now().date()
    while True:
        day = cursor.strftime("%Y-%m-%d")
        cnt = (
            db.query(StudyGoal)
            .filter(StudyGoal.user_id == user_id, StudyGoal.status == 1, StudyGoal.task_date == day)
            .count()
        )
        dcnt = (
            db.query(StudyGoal)
            .filter(
                StudyGoal.user_id == user_id,
                StudyGoal.status == 1,
                StudyGoal.task_date == day,
                StudyGoal.is_completed == 1,
            )
            .count()
        )
        if cnt == 0:
            break  # 该日无任务，视为断点
        if dcnt == 0:
            break  # 该日有任务但未完成，断点
        streak += 1
        cursor -= __import__("datetime").timedelta(days=1)
        if streak > 365:
            break
    if streak:
        parts.append(f"连续打卡 {streak} 天")
    milestones = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.memory_type == "milestone")
        .order_by(UserMemory.create_time.desc())
        .limit(3)
        .all()
    )
    if milestones:
        parts.append("备考里程碑：" + "；".join((m.content or "")[:40] for m in milestones))
    if not parts:
        return ""
    return "【备考轨迹】" + "；".join(parts) + "。"


def extract_memories(user_id: int, db):
    """
    长期记忆抽取：从画像确定性 upsert 关键事实（幂等，不依赖 LLM）。
    返回本次写入/更新的记忆条数。
    """
    from ..models.models import UserMemory, UserProfile

    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id, UserProfile.profile_status == 1)
        .first()
    )
    if not profile:
        return 0

    facts = []
    if profile.target_score:
        facts.append(("goal_score", f"目标分数 {profile.target_score}", profile.update_time))
    if profile.subject_weaknesses:
        facts.append(
            ("weak_subject", f"薄弱科目 {profile.subject_weaknesses}", profile.update_time)
        )
    if profile.daily_hours:
        facts.append(
            ("daily_hours", f"每日可学时长 {profile.daily_hours} 小时", profile.update_time)
        )
    if profile.exam_date:
        facts.append(("exam_date", f"目标考试日期 {profile.exam_date}", profile.update_time))
    if profile.grade:
        facts.append(("grade", f"当前阶段 {profile.grade}", profile.update_time))

    written = 0
    for mtype, content, ts in facts:
        row = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.memory_type == mtype)
            .first()
        )
        if row:
            if row.content != content:
                row.content = content
                row.update_time = ts
                written += 1
        else:
            db.add(
                UserMemory(
                    user_id=user_id,
                    memory_type=mtype,
                    content=content,
                    source="profile",
                    update_time=ts,
                )
            )
            written += 1
    db.commit()
    return written


def extract_chat_memory(user_id: int, db, message: str) -> int:
    """
    对话自动记忆（长期陪伴）：从用户消息中规则提取稳定偏好/目标写入 UserMemory。
    零 LLM、幂等（同内容不重复写）。返回本次写入条数。
    覆盖：意向地区/岗位、每周每天可投入时间、目标分数调整。
    """
    import re

    from ..models.models import UserMemory

    if not message or not message.strip():
        return 0
    msg = message.strip()[:200]
    patterns = [
        # 意向地区/城市/岗位
        (
            r"(意向|想|打算|希望)(去|在|考)?(地区|城市|岗位|工作)?"
            r"(是|为|定在|在)?[：:\s]*("
            r"山东|北京|上海|天津|河北|河南|山西|江苏|浙江|安徽|福建|江西|"
            r"湖南|湖北|广东|广西|海南|四川|重庆|贵州|云南|西藏|陕西|甘肃|"
            r"青海|宁夏|新疆|内蒙古|辽宁|吉林|黑龙江|廊坊|济南|青岛|烟台|潍坊|"
            r"石家庄|唐山|保定|邯郸|郑州|洛阳|开封|南京|苏州|无锡|徐州|杭州|"
            r"宁波|温州|嘉兴|福州|厦门|广州|深圳|珠海|武汉|长沙|成都|西安|"
            r"兰州|西宁|银川|乌鲁木齐|呼和浩特|沈阳|大连|长春|哈尔滨"
            r")",
            "意向地区",
        ),
        # 每周/每天可学时间
        (
            r"(每周|每天|每日|一天|一天能)\s*(能|可)?\s*(学|学习|复习|刷题|安排|投入)?\s*(\d+)\s*(小时|分钟)",
            "时间投入",
        ),
        # 目标分数调整
        (r"(目标|想考)(分数|总分|分)\s*(到|为|在)?\s*(\d+)", "目标分数"),
        # 想考的岗位类型
        (
            r"(想|意向|打算)(考|报)?\s*(综合|执法|技术|网安|技侦|经侦|刑侦|治安|特警|交警|监所|文职)\s*(岗|职位|岗位)?",
            "岗位意向",
        ),
    ]
    written = 0
    for pattern, tag in patterns:
        m = re.search(pattern, msg)
        if not m:
            continue
        content = f"{tag}：{m.group(0)[:40]}"
        exists = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.content == content)
            .first()
        )
        if exists:
            continue
        db.add(
            UserMemory(
                user_id=user_id,
                memory_type="pref",
                content=content,
                source="chat-auto",
            )
        )
        written += 1
    if written:
        db.commit()
    return written


# ==================== 知识库检索（Phase3 自生长知识库接入） ====================
# 从 approved 知识节点按关键词打分召回，只取摘要（控制 token），带出处

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "law": [
        "法",
        "治安",
        "警察",
        "刑法",
        "处罚",
        "拘留",
        "传唤",
        "条例",
        "公安",
        "法条",
        "违法",
        "执法",
        "处罚法",
    ],
    "recruit": ["报考", "岗位", "联考", "报名", "招录", "选岗", "公告", "生源地", "职位", "时间线"],
    "exam_point": [
        "行测",
        "申论",
        "公专",
        "资料分析",
        "考点",
        "技巧",
        "题",
        "速算",
        "公式",
        "作答",
    ],
    "wrong": ["错题", "薄弱", "复盘", "易错", "陷阱", "笔记"],
}
_IGNORE_CHARS = set("的了吗呢是在我你有没个" "：")


def retrieve_knowledge(user_id: int, db, message: str, limit: int = 3, max_chars: int = 120) -> str:
    """
    按用户消息关键词从已入库(approved)知识节点召回 TopN，返回带出处的摘要块。
    零 LLM 调用；单次召回 token 上限约 limit*max_chars。
    """
    from ..models.models import KnowledgeNode

    if not message or not message.strip():
        return ""
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.status == "approved").all()
    if not nodes:
        return ""

    scored: List[Tuple[int, KnowledgeNode]] = []
    for n in nodes:
        s = 0
        text = f"{n.title} {n.content or ''}"
        for k in CATEGORY_KEYWORDS.get(n.category, []):
            if k and k in message:
                s += 3 if k in text else 2
        # 标题/内容里的实词命中
        for ch in set(n.title):
            if ch in message and ch not in _IGNORE_CHARS:
                s += 1
        for ch in set(n.content or ""):
            if ch in message and ch not in _IGNORE_CHARS and s < 99:
                pass
        if s > 0:
            scored.append((s, n))

    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    top = [n for _, n in scored[:limit]]
    lines = []
    for n in top:
        body = (n.content or "")[:max_chars].replace("\n", " ")
        lines.append(f"- [{n.title}]({n.category}) {body}")
    return (
        "【知识库参考（已入库，引用时注明出处，涉法条以现行有效法条为准）】\n"
        + "\n".join(lines)
        + "\n"
    )
