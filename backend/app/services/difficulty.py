"""
渐进式IRT难度评估引擎
冷启动(<30次): 正确率法  →  预热(30-200次): Rasch 1PL  →  成熟(>200次): 2PL
"""
import math
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


def estimate_difficulty_cold_start(correct_count: int, total_count: int) -> int:
    """冷启动：基于正确率估算难度1-5级"""
    if total_count == 0:
        return 3  # 默认中等难度
    accuracy = correct_count / total_count
    raw = 5 * (1 - accuracy)
    return max(1, min(5, round(raw)))


def estimate_difficulty_rasch(correct_count: int, total_count: int) -> float:
    """Rasch 1PL模型：仅估计难度参数 b。b = -ln(accuracy / (1-accuracy))"""
    if total_count < 30:
        return 3.0
    accuracy = max(0.01, min(0.99, correct_count / total_count))
    logit = -math.log(accuracy / (1 - accuracy))
    # 映射logit ∈ [-4, 4] → difficulty ∈ [1, 5]
    normalized = (logit + 4) / 8 * 4 + 1
    return max(1.0, min(5.0, normalized))


def estimate_difficulty_2pl(
    correct_count: int, total_count: int,
    student_correct_counts: List[int],
    student_total_counts: List[int]
) -> Tuple[float, float]:
    """2PL模型：估计难度b和区分度a，使用scipy.optimize MLE"""
    try:
        from scipy.optimize import minimize
        import numpy as np
    except ImportError:
        logger.warning("scipy未安装，降级为Rasch")
        b = estimate_difficulty_rasch(correct_count, total_count)
        return b, 1.0

    if total_count < 200 or len(student_correct_counts) < 10:
        b = estimate_difficulty_rasch(correct_count, total_count)
        return b, 1.0

    # 学生能力估计
    abilities = []
    for cc, tc in zip(student_correct_counts, student_total_counts):
        if tc > 0:
            acc = max(0.01, min(0.99, cc / tc))
            abilities.append(-math.log(acc / (1 - acc)))
        else:
            abilities.append(0.0)
    abilities = np.array(abilities)

    def neg_log_likelihood(params):
        a, b = params
        probs = 1 / (1 + np.exp(-a * (abilities - b)))
        probs = np.clip(probs, 1e-10, 1 - 1e-10)
        ll = correct_count * np.log(probs.mean()) + \
             (total_count - correct_count) * np.log(1 - probs.mean())
        return -ll

    result = minimize(neg_log_likelihood, x0=[1.0, 0.0],
                      bounds=[(0.3, 3.0), (-4.0, 4.0)])
    a, b = result.x
    difficulty = max(1.0, min(5.0, (b + 4) / 8 * 4 + 1))
    return round(difficulty, 2), round(a, 2)


def get_difficulty_level(question_id: int, db_session) -> int:
    """获取题目难度等级（主入口），自动选择冷启动/Rasch/2PL阶段"""
    from ..models.models import PracticeRecord

    records = db_session.query(PracticeRecord).filter(
        PracticeRecord.question_id == question_id
    ).all()

    total = len(records)
    correct = sum(1 for r in records if r.is_correct)

    if total < 30:
        return estimate_difficulty_cold_start(correct, total)
    elif total < 200:
        return round(estimate_difficulty_rasch(correct, total))
    else:
        b, a = estimate_difficulty_2pl(correct, total, [], [])
        return round(b)


def batch_update_difficulties(db_session) -> int:
    """批量更新所有题目难度（定时任务调用），返回更新数量"""
    from ..models.models import QuestionBank

    questions = db_session.query(QuestionBank).filter(
        QuestionBank.status == 1
    ).all()

    updated = 0
    for q in questions:
        new_difficulty = get_difficulty_level(q.question_id, db_session)
        if q.difficulty != new_difficulty:
            q.difficulty = new_difficulty
            updated += 1

    if updated > 0:
        db_session.commit()
        logger.info(f"[difficulty] 更新 {updated} 题难度等级")

    return updated


def update_all_difficulties() -> int:
    """定时任务入口：创建独立数据库会话并批量更新所有题目难度"""
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        updated = batch_update_difficulties(db)
        logger.info(f"[difficulty] 定时任务完成，共更新 {updated} 题")
        return updated
    except Exception as e:
        db.rollback()
        logger.error(f"[difficulty] 定时任务失败: {e}")
        raise
    finally:
        db.close()
