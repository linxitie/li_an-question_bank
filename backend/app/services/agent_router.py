# -*- coding: utf-8 -*-
"""
模块7 v2 - 多 Agent 备考陪伴系统：Agent 路由 + 档案上下文装配 + 长期记忆抽取
设计要点（token 极简）：
- 路由用关键词规则打分，不调 LLM（零额外 token）
- 档案上下文只取摘要与统计，不塞原文
- 长期记忆从画像确定性抽取（幂等 upsert），不依赖 LLM
"""
from __future__ import annotations

from typing import Dict, List, Tuple

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
        "keywords": [("选岗", 3), ("岗位", 3), ("报哪", 3), ("报考条件", 3), ("生源地", 3), ("职位", 2), ("调剂", 2), ("入职", 2), ("分配", 2), ("安置", 2), ("户籍", 2), ("专业限制", 3), ("限专业", 3)],
    },
    "interview": {
        "name": "面试教练",
        "prompt": (
            "你是'砺安小智'的面试教练。考生会问公安联考结构化面试怎么准备、要一道面试题、答题框架、模拟追问等。"
            "回答要点：给出结构化面试常见题型（综合分析/应急处突/组织管理/人际沟通）与答题框架（表态-分析-对策）；"
            "可出一道模拟题并给示范要点。回答 300 字内，条理清晰。"
        ),
        "keywords": [("面试", 3), ("结构化", 3), ("答题框架", 3), ("模拟", 2), ("考官", 2), ("自我介绍", 2), ("应急处突", 3), ("综合分析", 3), ("组织管理", 3), ("人际沟通", 3), ("追问", 3)],
    },
    "psychology": {
        "name": "心理辅导",
        "prompt": (
            "你是'砺安小智'的心理辅导师。考生表达焦虑、压力、失眠、自我怀疑、疲惫等情绪问题。"
            "回答要点：先共情，不评判；再用温和专业的语言疏导，给一个当下可执行的调节小方法（如呼吸法、任务拆解）。"
            "不直接讲题、不灌鸡汤。回答 150 字内，语气像靠谱的学长学姐。若对方情绪严重异常，提示寻求专业心理支持。"
        ),
        "keywords": [("焦虑", 3), ("压力", 3), ("心态", 3), ("紧张", 3), ("失眠", 3), ("睡不着", 3), ("崩溃", 3), ("坚持不住", 3), ("想放弃", 3), ("没信心", 3), ("慌", 2), ("emo", 2), ("烦躁", 2), ("emo了", 2), ("累", 1)],
    },
    "shenlun": {
        "name": "申论教练",
        "prompt": (
            "你是'砺安小智'的申论教练。考生会问申论归纳概括、综合分析、提出对策、公文写作、大作文等。"
            "回答要点：给方法框架+示例结构；批改思路时说清采分点与常见失分；涉及范文只给要点不给整篇。"
            "回答 300 字内，分点。"
        ),
        "keywords": [("申论", 3), ("大作文", 3), ("归纳概括", 3), ("综合分析题", 3), ("提出对策", 3), ("公文", 2), ("应用文", 3), ("作文", 2), ("材料题", 2), ("议论文", 2), ("策论文", 3), ("分论点", 3)],
    },
    "xingce": {
        "name": "行测讲师",
        "prompt": (
            "你是'砺安小智'的行测讲师。考生会问行测言语理解、数量关系、判断推理、资料分析、常识判断的题与技巧。"
            "回答要点：先给思路/口诀，再讲解析；计算类给关键步骤即可，不用长篇演算。"
            "回答 300 字内，分点。"
        ),
        "keywords": [("行测", 3), ("资料分析", 3), ("数量关系", 3), ("言语理解", 3), ("判断推理", 3), ("逻辑填空", 3), ("图形推理", 3), ("类比推理", 3), ("片段阅读", 3), ("常识", 2), ("速算", 2), ("蒙题", 2)],
    },
    "gongzhuan": {
        "name": "公专导师",
        "prompt": (
            "你是'砺安小智'的公安专业知识导师。考生会问公安专业科目知识点、法条适用、情景题、执法规范等。"
            "回答要点：结合《公安专业科目》考纲与常用法律法规（治安管理处罚法、人民警察法、刑法等）作答，"
            "法条引用到条即可，注明'以现行有效法条为准'，不编造条文。回答 300 字内，分点。"
        ),
        "keywords": [("公专", 3), ("公安专业", 3), ("法条", 2), ("治安管理处罚法", 3), ("人民警察法", 3), ("情景题", 3), ("执法", 2), ("盘查", 2), ("逮捕", 2), ("拘留", 2), ("刑法", 2), ("行政处罚", 3)],
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
    return AGENT_META[agent_id]["prompt"]


def assemble_context(user_id: int, db) -> str:
    """
    档案上下文装配（"带着档案来对话"）：只取摘要与统计，控制 token。
    来源：user_profile + 当前学习计划 + 学情统计（做题量/正确率/错题分布/最近错题Top3）。
    返回拼接好的上下文块；无档案时返回空串。
    """
    from sqlalchemy import func
    from ..models.models import UserProfile, StudyGoal, WrongQuestionPersonal, PracticeRecord

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
            .filter(StudyGoal.user_id == user_id, StudyGoal.status == 1, StudyGoal.task_date == today)
            .count()
        )
        plan_parts = [f"当前备考计划：{summary}。今日任务 {today_total} 项"]
        if meta.get("phases"):
            plan_parts.append(f"阶段规划：{'；'.join(str(x.get('name', '')) for x in meta['phases'][:3])}")
        parts.append("【学习计划】" + "；".join(plan_parts) + "。")

    # 3. 学情统计：做题量 / 正确率 / 错题分布 / 最近错题 Top3
    practice_total = db.query(PracticeRecord).filter(PracticeRecord.user_id == user_id).count()
    practice_correct = (
        db.query(PracticeRecord)
        .filter(PracticeRecord.user_id == user_id, PracticeRecord.is_correct == 1)
        .count()
    )
    acc = round(practice_correct / practice_total * 100) if practice_total else None
    wrong_total = db.query(WrongQuestionPersonal).filter(WrongQuestionPersonal.user_id == user_id).count()
    recent_wrong = (
        db.query(WrongQuestionPersonal)
        .filter(WrongQuestionPersonal.user_id == user_id)
        .order_by(WrongQuestionPersonal.add_time.desc())
        .limit(3)
        .all()
    )
    study_parts = []
    if practice_total:
        study_parts.append(f"累计做题 {practice_total} 题，正确率 {acc}%")
    if wrong_total:
        study_parts.append(f"错题本 {wrong_total} 题")
    if recent_wrong:
        names = []
        for w in recent_wrong:
            q = getattr(w, "question", None)
            content = getattr(q, "question_content", None) if q else None
            nm = (content or "")[:40] if content else (w.user_answer or "")[:40]
            names.append(nm)
        if names:
            study_parts.append(f"最近错题：{'、'.join(names)}")
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
    from sqlalchemy import func
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
        .filter(StudyGoal.user_id == user_id, StudyGoal.plan_id == plan.plan_id, StudyGoal.status == 1)
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
    from ..models.models import UserProfile, UserMemory

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
        facts.append(("weak_subject", f"薄弱科目 {profile.subject_weaknesses}", profile.update_time))
    if profile.daily_hours:
        facts.append(("daily_hours", f"每日可学时长 {profile.daily_hours} 小时", profile.update_time))
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
            db.add(UserMemory(
                user_id=user_id, memory_type=mtype, content=content,
                source="profile", update_time=ts,
            ))
            written += 1
    db.commit()
    return written


# ==================== 知识库检索（Phase3 自生长知识库接入） ====================
# 从 approved 知识节点按关键词打分召回，只取摘要（控制 token），带出处

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "law": ["法", "治安", "警察", "刑法", "处罚", "拘留", "传唤", "条例", "公安", "法条", "违法", "执法", "处罚法"],
    "recruit": ["报考", "岗位", "联考", "报名", "招录", "选岗", "公告", "生源地", "职位", "时间线"],
    "exam_point": ["行测", "申论", "公专", "资料分析", "考点", "技巧", "题", "速算", "公式", "作答"],
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
    nodes = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.status == "approved")
        .all()
    )
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
    return "【知识库参考（已入库，引用时注明出处，涉法条以现行有效法条为准）】\n" + "\n".join(lines) + "\n"
