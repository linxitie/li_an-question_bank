# -*- coding: utf-8 -*-
"""exam 域对外契约：试卷的「可作答性」（P5，2026-11-08）。

背景
----
《试卷管理收敛_单一入口与上架即审批_方案_v1.md》§2.3 规定：`exam_paper` 降为投影，
**唯一真源是 `study_material.status`**；资料上架 → 卷 `PUBLISHED`，资料下架/删除 → 卷 `DRAFT`，
反方向不驱动。

`paper_type` 的合法值集合与迁移规则属于**考试域知识**（PENDING/APPROVED 是审批中间态、
ENDED 是回收站），所以规则写在这里、只写一次；library 域不 import `ExamPaper`
（`scripts/gates/check_module_boundary.py` 的 cross_write 规则），改由
`app/services/material_paper_sync.py` 做薄接线。

本契约**会写** `exam_paper.paper_type`（与 `catalog/contract.py` 那种只读契约不同），
因此刻意做成：
  · 不 commit —— 成败由调用方的事务决定，保证「资料状态 + 卷状态 + 审计」同生共死；
  · 返回值含 before/after/changed/skipped —— 便于调用方写审计与回包；
  · 不碰 ENDED —— 回收站里的卷不因一次上架被复活（题目关系可能已残缺）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ....models.models import ExamPaper

#: 可作答状态（学生考试链路 7 处判据都只看这个值）
VISIBLE_TYPE = "PUBLISHED"
#: 不可作答但可恢复的状态
HIDDEN_TYPE = "DRAFT"
#: 回收站卷：本契约永不改写
TERMINAL_TYPE = "ENDED"
#: 允许被本契约翻转的状态（ENDED 不在其中）
_FLIPPABLE = {"DRAFT", "PENDING", "APPROVED", VISIBLE_TYPE}


def find_paper(db: Session, paper_code: Optional[str]) -> Optional[ExamPaper]:
    """按编号取卷；空编号直接返回 None（不查全表）。"""
    code = (paper_code or "").strip()
    if not code:
        return None
    return db.query(ExamPaper).filter(ExamPaper.paper_code == code).first()


def sync_paper_visibility(db: Session, paper_code: Optional[str], *,
                          visible: bool) -> dict:
    """把一张卷的可作答性对齐到 `visible`（不 commit）。

    Args:
        db: 调用方的事务会话
        paper_code: `study_material.paper_code`（空则调用方应回落 badge）
        visible: True=可作答（PUBLISHED）；False=不可作答（DRAFT）

    返回:
        {
          "paper_id": int | None, "paper_code": str,
          "before": str | None, "after": str | None,
          "changed": bool,
          "skipped": None | "empty_code" | "no_paper" | "ended",
        }

    规则（与方案 §3 的 D-P5-1/2/3 一致）:
        · 上架：DRAFT / PENDING / APPROVED → PUBLISHED（"上架即终审"，避免"已上架但考不到"）
        · 下架：PUBLISHED → DRAFT（PENDING/APPROVED 也回 DRAFT：资料不可见即不可考）
        · ENDED：永不动，返回 skipped="ended"
        · 无卷 / 空编号：不报错，返回 skipped
    """
    code = (paper_code or "").strip()
    result = {"paper_id": None, "paper_code": code, "before": None,
              "after": None, "changed": False, "skipped": None}
    if not code:
        result["skipped"] = "empty_code"
        return result

    paper = find_paper(db, code)
    if paper is None:
        result["skipped"] = "no_paper"
        return result

    before = paper.paper_type
    result["paper_id"] = paper.paper_id
    result["before"] = before
    result["after"] = before

    if before == TERMINAL_TYPE or before not in _FLIPPABLE:
        result["skipped"] = "ended" if before == TERMINAL_TYPE else "not_flippable"
        return result

    target = VISIBLE_TYPE if visible else HIDDEN_TYPE
    if before == target:
        return result

    paper.paper_type = target
    if target == VISIBLE_TYPE:
        paper.publish_time = paper.publish_time or datetime.now()
    # update_time 由 onupdate 自动刷新，这里不手写，避免覆盖他人并发改动的时间戳
    result["after"] = target
    result["changed"] = True
    return result


def paper_is_answerable(db: Session, paper_code: Optional[str]) -> bool:
    """只读判断：该编号的卷当前是否可作答（供巡检/调试复用）。"""
    paper = find_paper(db, paper_code)
    return bool(paper and paper.paper_type == VISIBLE_TYPE)


# ==================== P2（2026-11-09）：考试开关 + 定时窗口 ====================
# 为什么用"读取时计算"而不是定时任务：
#   · 定时任务在开发机/单机部署里经常不跑（无 supervisor / 进程重启），一旦漏跑，
#     学生要么进不去、要么该关的没关；
#   · 判定只需要三个字段 + 当前时间，算一次是纯函数，天然幂等、无状态、可回放。
# 语义（与方案 §4.2 一致）：
#   exam_open      = 1 表示"总闸开"（NULL 兼容为开）；
#   开始/结束时间  只限制"窗口内"，留空 = 该侧不限；
#   question_count 必须 > 0 —— 0 题的卷不允许开考（否则学生进空卷）。


def _get(paper, name, default=None):
    """兼容 ORM 对象与老数据（未迁移时属性可能不存在）。"""
    return getattr(paper, name, default)


def question_total(db: Optional[Session], paper) -> int:
    """这张卷**真实**有多少题（`question_count` 只是缓存值）。

    为什么要兜底：`exam_paper.question_count` 由导入/挂题各环节增量维护，实测漂移过
    （`services/paper_stats.py` 的注释里有「导入 110 题却写成 1」的案例）。
    如果只看缓存值，一旦它被写成 0，学生就会被"这场考试还没有题目"挡在门外 ——
    而卷里其实有题。所以：缓存值 > 0 直接信它（常见路径零额外查询）；
    为 0/NULL 时才数一次 `paper_question_relation`（少见，且只有这一条卷）。
    """
    cached = int(_get(paper, "question_count", 0) or 0)
    if cached > 0 or db is None or paper is None:
        return max(cached, 0)
    from sqlalchemy import func

    from ....models.models import PaperQuestionRelation
    return int(db.query(func.count(PaperQuestionRelation.relation_id))
               .filter(PaperQuestionRelation.paper_id == paper.paper_id)
               .scalar() or 0)


def _manual_open(paper) -> int:
    """手动总闸：NULL 兼容为 1（老数据/未迁移）。

    注意不能写成 `int(getattr(...) or 1)` —— `0 or 1` 会得到 1，
    实测把"已关闭"的卷算成"开着"，状态文案还落到 `expired`（P2 单测抓到）。
    """
    value = _get(paper, "exam_open", 1)
    return 1 if value is None else int(value)


def exam_is_open(paper, now: Optional[datetime] = None) -> bool:
    """当前这一刻是否允许学生进入这场考试（不看 paper_type）。"""
    if paper is None:
        return False
    now = now or datetime.now()
    if _manual_open(paper) == 0:
        return False
    open_at = _get(paper, "exam_open_at")
    close_at = _get(paper, "exam_close_at")
    if open_at and now < open_at:
        return False
    if close_at and now >= close_at:
        return False
    return True


def answer_gap(db: Optional[Session], paper) -> int:
    """卷面有多少道题**还没有答案**（2026-11-11 用户批准的开考闸门）。

    为什么必须拦：答案没录的卷，学生交卷后 `is_correct` 全为 0 —— 白考一场，
    而且结果页看不出"是没答案还是全错"。判分完全依赖 `question_bank.answer`，
    所以这里与 `question_total` 同源：以 `paper_question_relation` 为准，
    **题目行丢失也算缺失**（否则会漏判）。

    返回：缺失答案的题数；`0` 表示可以开考。取不到卷/无 db 时返回 0（不拦）。
    """
    if db is None or paper is None:
        return 0
    from sqlalchemy import func

    from ....models.models import PaperQuestionRelation, QuestionBank

    paper_id = getattr(paper, "paper_id", None)
    if paper_id is None:
        return 0
    rel_n = int(db.query(func.count(PaperQuestionRelation.relation_id))
                .filter(PaperQuestionRelation.paper_id == paper_id)
                .scalar() or 0)
    if rel_n <= 0:
        return 0
    filled = int(db.query(func.count(PaperQuestionRelation.relation_id))
                 .join(QuestionBank,
                       QuestionBank.question_id == PaperQuestionRelation.question_id)
                 .filter(PaperQuestionRelation.paper_id == paper_id,
                         QuestionBank.answer.isnot(None),
                         func.trim(QuestionBank.answer) != "")
                 .scalar() or 0)
    return max(rel_n - filled, 0)


def exam_ready(paper, now: Optional[datetime] = None, *,
               questions: Optional[int] = None,
               answers_missing: Optional[int] = None) -> bool:
    """完整判据：已发布 + 开关/窗口放行 + 有题 + **答案已录全**。学生端只应看这个值。

    Args:
        questions: 真实题量（调用方有 db 时传 `question_total(db, paper)`）；
            不传则退回缓存值 `paper.question_count`。
        answers_missing: 未录答案的题数（传 `answer_gap(db, paper)`）；
            `None` 表示跳过该校验（兼容老调用方/纯单测）。
    """
    if paper is None or paper.paper_type != VISIBLE_TYPE:
        return False
    count = int(paper.question_count or 0) if questions is None else int(questions)
    if count <= 0:
        return False
    if answers_missing is not None and int(answers_missing) > 0:
        return False
    return exam_is_open(paper, now)


def exam_state(paper, now: Optional[datetime] = None, *,
               questions: Optional[int] = None,
               answers_missing: Optional[int] = None) -> dict:
    """给管理端/资料页的只读状态块（含"为什么不能考"的原因码）。

    `answers_missing`（未录答案题数）为 2026-11-11 新增闸门；不传则不校验。
    判定顺序：未发布 → 无题 → 开关/窗口 → **答案未录全** → ready
    （时间类原因优先：学生先该知道"这场考试关了/没到点"，而不是"题库没答案"）。
    """
    now = now or datetime.now()
    stamp = now.replace(microsecond=0).isoformat(sep=" ")
    if paper is None:
        return {"known": False, "published": False, "open": False, "ready": False,
                "reason": "no_paper", "open_at": None, "close_at": None,
                "question_count": 0, "answers_missing": None, "server_now": stamp}
    open_at = _get(paper, "exam_open_at")
    close_at = _get(paper, "exam_close_at")
    is_open = exam_is_open(paper, now)
    published = paper.paper_type == VISIBLE_TYPE
    count = int(paper.question_count or 0) if questions is None else int(questions)
    has_questions = count > 0
    missing = None if answers_missing is None else max(int(answers_missing), 0)
    if not published:
        reason = "draft"
    elif not has_questions:
        reason = "no_questions"
    elif not is_open:
        # 区分"总闸关"和"不在窗口内"，界面要给不同文案
        if _manual_open(paper) == 0:
            reason = "closed"
        elif open_at and now < open_at:
            reason = "not_started"
        else:
            reason = "expired"
    elif missing:
        # 答案没录全：判分全靠 question_bank.answer，进来只会得到一片 0 分
        reason = "no_answers" if missing >= count else "answers_incomplete"
    else:
        reason = "ready"
    return {
        "known": True,
        "published": published,
        "open": is_open,
        "ready": published and is_open and has_questions and not (missing or 0),
        "reason": reason,
        "open_at": open_at.isoformat(sep=" ") if open_at else None,
        "close_at": close_at.isoformat(sep=" ") if close_at else None,
        "question_count": count,
        "answers_missing": missing,
        # 判定用的是**服务器本地时间**（决策 S1）；把它回给前端，
        # 管理端弹层显示"现在 20:41 在窗口内"才是准的（浏览器时区可能不同）。
        "server_now": stamp,
    }


def open_conditions(now: Optional[datetime] = None) -> list:
    """SQLAlchemy 条件列表：给列表查询用（与 exam_ready 同一口径）。

    为什么单独给一份 SQL：`/api/papers/list` 是分页查询，取回后在 Python 里筛会让
    分页数与实际条数不一致；把条件下推到 SQL 才能保证 total 正确。

    注意 1：本函数只覆盖「开关 + 窗口 + 有题」，**不含 `paper_type`**——
    调用方（列表查询）本来就有自己的可见性分支（学生只看 PUBLISHED / 教师看自己的），
    这里再加一次会让教师的草稿卷被误筛掉。

    注意 2：「有题」这一条不能只判 `question_count > 0`：该字段是缓存值，可能漏更，
    实测存在"挂了题但计数仍是 0"的卷。因此缓存为 0/NULL 时再查一次关系表
    （EXISTS 子查询，命中索引，代价可忽略），与 `question_total()` 口径一致。
    """
    from sqlalchemy import and_, exists, or_

    from ....models.models import PaperQuestionRelation

    now = now or datetime.now()
    has_questions = or_(
        ExamPaper.question_count > 0,
        and_(or_(ExamPaper.question_count.is_(None), ExamPaper.question_count == 0),
             exists().where(
                 PaperQuestionRelation.paper_id == ExamPaper.paper_id)),
    )
    return [
        and_(or_(ExamPaper.exam_open.is_(None), ExamPaper.exam_open == 1)),
        or_(ExamPaper.exam_open_at.is_(None), ExamPaper.exam_open_at <= now),
        or_(ExamPaper.exam_close_at.is_(None), ExamPaper.exam_close_at > now),
        has_questions,
    ]


#: 原因码 → 学生能看懂的一句话（前端直接展示，不用自己拼文案）
REASON_TEXT = {
    "no_paper": "试卷不存在",
    "draft": "试卷不存在或未发布",
    "no_questions": "这场考试还没有题目，暂时不能开始",
    "closed": "考试已关闭，暂时不能开始（历史成绩不受影响）",
    "not_started": "考试还没到开始时间",
    "expired": "考试已结束",
    # 2026-11-11：答案没录全的卷不允许开考（否则判分全靠空答案，学生白考一场）
    "no_answers": "这套卷还没有录入正确答案，暂时不能开始",
    "answers_incomplete": "这套卷还有部分题没录正确答案，暂时不能开始",
    "ready": "",
}


def exam_block_message(state: Optional[dict] = None, now: Optional[datetime] = None) -> str:
    """把原因码翻成一句人话；`ready` 返回空串。

    Args:
        state: `exam_state()` 的返回值；不传时只按 `now` 给通用文案（调用方已有 paper 时请传 state）
    """
    if not state:
        return "考试暂时不能开始"
    reason = state.get("reason") or "ready"
    text = REASON_TEXT.get(reason, "考试暂时不能开始")
    # 定时场景补上具体时间，学生不用再去问管理员
    if reason == "not_started" and state.get("open_at"):
        text = f"{text}（{state['open_at'][:16]} 开始）"
    elif reason == "expired" and state.get("close_at"):
        text = f"{text}（{state['close_at'][:16]} 结束）"
    elif reason in ("no_answers", "answers_incomplete") and state.get("answers_missing"):
        text = f"{text}（还差 {state['answers_missing']} 题，请联系管理员补答案）"
    return text
