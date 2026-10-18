"""成就成长枢纽判据引擎（P2-51）。

输入是 ``user.action.v1`` 的 ``trigger_type``（E1–E10，E5 拆成
``note.created`` / ``favorite.added`` 两个字符串值，共 11 个），输出是：

- ``badge_task`` 任务进度（``mode=event`` 事件累计 / ``mode=calc`` 历史重算）；
- 可解锁 / 可升档的成就决策（仅判定，不发奖）。

硬约束
------
- **零反向依赖**：本文件不 import 任何业务域 API 模块；成就判据复用
  ``achievement_service``（同域），奖励由 ``achievement_reward`` 单点发放。
- **幂等去重**：去重键为 ``user_id + trigger_type + session 身份``。同一
  ``trigger_type`` 携带同一 session（如同一练习会话、同一错题、同一帖子）
  重复投递只计一次。无 session 的历史事件不做去重（没有稳定身份）。
- **可回放**：``recalculate()`` 只依赖数据库历史，可对 ``calc`` 任务与全部
  成就判据重算；事件累计型任务因无事件日志不回放（历史投递本身已去重）。
"""
from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.models import PracticeRecord, SysUser, Task, UserTaskProgress
from . import achievement_service

logger = logging.getLogger(__name__)

#: 进程内去重窗口。与 practice_grading 的会话去重保持同一量级；
#: 超出窗口后最旧键淘汰，避免长驻进程无限增长。
DEDUPE_LIMIT = 8192
_DEDUPE: "OrderedDict[Tuple[int, str, str], None]" = OrderedDict()

#: session 中可作为稳定身份的键，优先级从高到低。
_SESSION_IDENTITY_KEYS = (
    "session_id",
    "record_id",
    "exam_record_id",
    "wrong_id",
    "post_id",
    "exchange_id",
    "news_id",
    "material_id",
    "question_id",
    "note_id",
    "product_id",
    "action",
    "date",
    "practice_date",
    "period_key",
)


def reset_dedupe() -> None:
    """清空去重窗口（测试 / 进程重启场景）。"""
    _DEDUPE.clear()


def _session_identity(session: Optional[Dict[str, Any]]) -> str:
    if not session:
        return ""
    if not isinstance(session, dict):
        return str(session)

    parts = [
        f"{key}={session[key]}"
        for key in _SESSION_IDENTITY_KEYS
        if key in session and session[key] is not None
    ]
    if parts:
        return "|".join(parts)
    # 没有已知身份键时退回完整 session 序列化，保证同载荷可去重。
    return json.dumps(session, sort_keys=True, ensure_ascii=False, default=str)


def _dedupe_key(
    user_id: int, trigger_type: str, session: Optional[Dict[str, Any]]
) -> Optional[Tuple[int, str, str]]:
    identity = _session_identity(session)
    if not identity:
        return None
    return (int(user_id), trigger_type, identity)


def _remember(key: Tuple[int, str, str]) -> bool:
    """返回 True 表示首次出现，False 表示重复。"""
    if key in _DEDUPE:
        return False
    _DEDUPE[key] = None
    while len(_DEDUPE) > DEDUPE_LIMIT:
        _DEDUPE.popitem(last=False)
    return True


# ---------------------------------------------------------------------------
# badge_task 周期与进度
# ---------------------------------------------------------------------------

def _period_key(task: Task, now: Optional[datetime] = None) -> str:
    current = now or datetime.now()
    if task.t_type == "weekly":
        iso = current.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if task.t_type == "season":
        return current.strftime("%Y%m")
    return current.strftime("%Y%m%d")


def _metric_matches(metric: str, trigger_type: str) -> bool:
    """任务指标码是否由该 trigger_type 驱动（兼容历史值）。"""
    if not metric or not trigger_type:
        return False
    if metric == trigger_type:
        return True

    from ..core.trigger_types import LEGACY_TRIGGER_ALIASES

    if metric in LEGACY_TRIGGER_ALIASES.get(trigger_type, ()):
        return True
    # 反向：任务登记的是新常量，事件仍在使用历史值
    for canonical, legacy_values in LEGACY_TRIGGER_ALIASES.items():
        if metric == canonical and trigger_type in legacy_values:
            return True
    return False


def _get_or_create_progress(
    db: Session, user_id: int, task: Task, period_key: str
) -> UserTaskProgress:
    progress = (
        db.query(UserTaskProgress)
        .filter(
            UserTaskProgress.user_id == user_id,
            UserTaskProgress.task_id == task.task_id,
            UserTaskProgress.period_key == period_key,
        )
        .first()
    )
    if progress is None:
        progress = UserTaskProgress(
            user_id=user_id,
            task_id=task.task_id,
            period_key=period_key,
            current=0,
            completed=0,
            claimed=0,
        )
        db.add(progress)
    return progress


def _calc_metric(user_id: int, metric: str, db: Session) -> float:
    """按历史数据重算进度指标（不依赖任何 api 模块）。"""
    now = datetime.now()
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = now - timedelta(days=7)

    if metric == "today_questions":
        return float(
            db.query(PracticeRecord)
            .filter(
                PracticeRecord.user_id == user_id,
                PracticeRecord.practice_time >= today_start,
            )
            .count()
        )

    if metric == "week_questions":
        return float(
            db.query(PracticeRecord)
            .filter(
                PracticeRecord.user_id == user_id,
                PracticeRecord.practice_time >= week_start,
            )
            .count()
        )

    if metric == "total_questions":
        return float(
            db.query(PracticeRecord)
            .filter(PracticeRecord.user_id == user_id)
            .count()
        )

    if metric in ("today_accuracy", "week_accuracy"):
        query = db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id
        )
        if metric == "today_accuracy":
            query = query.filter(PracticeRecord.practice_time >= today_start)
        else:
            query = query.filter(PracticeRecord.practice_time >= week_start)
        rows = query.all()
        if not rows:
            return 0.0
        correct = sum(1 for row in rows if row.is_correct == 1)
        return round(correct / len(rows) * 100, 1)

    if metric == "streak_days":
        user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
        return float(user.continuous_checkin_days or 0) if user else 0.0

    return 0.0


def _apply_task_progress(
    user_id: int,
    trigger_type: str,
    db: Session,
    session: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按 badge_task 的 mode 计算进度，返回发生变化的条目。"""
    tasks = db.query(Task).filter(Task.enabled == 1).all()
    updates: List[Dict[str, Any]] = []

    for task in tasks:
        mode = (task.mode or "calc").lower()
        if mode == "event":
            if not _metric_matches(task.metric or "", trigger_type):
                continue
            period_key = _period_key(task)
            progress = _get_or_create_progress(db, user_id, task, period_key)
            progress.current = int(progress.current or 0) + 1
            changed = True
        elif mode == "calc":
            period_key = _period_key(task)
            value = int(round(_calc_metric(user_id, task.metric or "", db)))
            progress = _get_or_create_progress(db, user_id, task, period_key)
            changed = value != int(progress.current or 0)
            progress.current = value
        else:
            continue

        threshold = int(task.threshold or 1)
        if progress.current >= threshold and not progress.completed:
            progress.completed = 1
            progress.completed_at = datetime.now()

        if changed:
            updates.append(
                {
                    "task_id": task.task_id,
                    "task_code": task.task_code,
                    "mode": mode,
                    "period_key": period_key,
                    "current": int(progress.current or 0),
                    "threshold": threshold,
                    "completed": bool(progress.completed),
                }
            )

    # 测试会话通常是 autoflush=False；显式 flush 让进度行立即可读，
    # 也让并发插入的唯一约束在事务内尽早暴露。
    if updates:
        db.flush()
    return updates


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------

def judge_action(
    user_id: int,
    trigger_type: str,
    db: Session,
    session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """消费一条行为事件：更新任务进度并判定成就。

    返回结构::

        {
          "trigger_type": str,
          "duplicate": bool,
          "task_progress": [...],
          "newly_unlocked": [...],   # 仅判定，未发奖
        }

    调用方（事件消费者）必须对 ``newly_unlocked`` 调用
    ``achievement_reward.grant_newly`` 完成发奖。
    """
    result: Dict[str, Any] = {
        "trigger_type": trigger_type,
        "duplicate": False,
        "task_progress": [],
        "newly_unlocked": [],
    }
    if not trigger_type:
        return result

    key = _dedupe_key(user_id, trigger_type, session)
    if key is not None and key in _DEDUPE:
        result["duplicate"] = True
        logger.debug(
            "重复事件已忽略 user=%s trigger=%s session=%s",
            user_id,
            trigger_type,
            key[2],
        )
        return result

    # 先判定成就（其内部单条异常会 rollback），再写任务进度，
    # 避免判据异常把已写入的任务进度一并回滚。
    decisions = achievement_service.evaluate_unlocks(
        user_id, trigger_type, db, session=session
    )
    result["newly_unlocked"] = [
        achievement_service.newly_item(decision) for decision in decisions
    ]
    result["task_progress"] = _apply_task_progress(
        user_id, trigger_type, db, session
    )

    if key is not None:
        _remember(key)
    return result


def recalculate(user_id: int, db: Session) -> Dict[str, Any]:
    """历史回放重算：按数据库现状重算 calc 任务与全部成就判据。

    - ``calc`` 任务直接按历史记录重算；
    - 成就判据对 E1–E10 全部 trigger_type 各评估一次，按 achievement_id
      去重保留最高档位；
    - 只判定不发奖，调用方可对 ``newly_unlocked`` 走 reward 单点。
    """
    from ..core.trigger_types import ALL_TRIGGER_TYPES

    task_updates: List[Dict[str, Any]] = []
    tasks = db.query(Task).filter(Task.enabled == 1).all()
    for task in tasks:
        if (task.mode or "calc").lower() != "calc":
            continue
        period_key = _period_key(task)
        value = int(round(_calc_metric(user_id, task.metric or "", db)))
        progress = _get_or_create_progress(db, user_id, task, period_key)
        if value != int(progress.current or 0):
            progress.current = value
            threshold = int(task.threshold or 1)
            if value >= threshold and not progress.completed:
                progress.completed = 1
                progress.completed_at = datetime.now()
            task_updates.append(
                {
                    "task_id": task.task_id,
                    "task_code": task.task_code,
                    "mode": "calc",
                    "period_key": period_key,
                    "current": value,
                    "threshold": threshold,
                    "completed": bool(progress.completed),
                }
            )

    best: Dict[int, Any] = {}
    for trigger_type in ALL_TRIGGER_TYPES:
        for decision in achievement_service.evaluate_unlocks(
            user_id, trigger_type, db, session=None
        ):
            achievement_id = int(decision["achievement"].achievement_id)
            current = best.get(achievement_id)
            if current is None or int(decision["tier"]) > int(current["tier"]):
                best[achievement_id] = decision

    return {
        "task_progress": task_updates,
        "newly_unlocked": [
            achievement_service.newly_item(decision)
            for decision in best.values()
        ],
    }
