"""考点关联 + 科目/题型取建（I-7：pure move 自 backend/app/api/v1/question_import.py，任务 42）

三个函数体逐字节原样搬迁，**零逻辑变更**：
  · `_link_knowledge_points` —— 分类引擎 → QuestionKnowledge 关联（幂等、异常不阻断）
  · `_get_or_create_subject` —— 科目取建（强制走 SUBJECT_NAME_MAP 预定义 subject_id）
  · `_get_or_create_type`    —— 题型取建（type_code 带 subject_id 前缀，跨科目唯一）

依赖方向单向：本模块只依赖 models / question_classifier / text_parser / .tags，
**不反向依赖 api.v1.question_import**，故 `question_ingest/__init__.py` 可直接 eager re-export。
"""
import logging

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ...models.models import QuestionKnowledge, QuestionSubject, QuestionType
from ..question_classifier import QuestionClassifier
from .tags import SUBJECT_NAME_MAP

logger = logging.getLogger(__name__)


def _link_knowledge_points(db: Session, questions) -> int:
    """对导入的题目运行分类引擎并建立考点关联（幂等、异常不阻断导入）。

    仅 db.add 关联，不 commit，由调用方在合适时机提交。
    返回成功建立考点关联的题目数。
    """
    if not questions:
        return 0
    linked = 0
    classifier = QuestionClassifier()
    for q in questions:
        try:
            result = classifier.classify_with_db(
                q.question_content or "", q.subject_id, db
            )
            if result.knowledge_point_id:
                existing = db.query(QuestionKnowledge).filter(
                    QuestionKnowledge.question_id == q.question_id,
                    QuestionKnowledge.knowledge_point_id == result.knowledge_point_id
                ).first()
                if not existing:
                    db.add(QuestionKnowledge(
                        question_id=q.question_id,
                        knowledge_point_id=result.knowledge_point_id
                    ))
                    linked += 1
        except Exception as e:
            logger.warning(f"考点关联失败 question_id={getattr(q, 'question_id', None)}: {e}")
    return linked


def _get_or_create_subject(db: Session, name: str) -> QuestionSubject:
    """获取或创建科目（强制使用预定义 subject_id 映射）"""
    # 首先尝试预定义的 subject_id 查找
    sid = SUBJECT_NAME_MAP.get(name)
    if sid:
        subject = db.query(QuestionSubject).filter(
            QuestionSubject.subject_id == sid
        ).first()
        if subject:
            return subject

    # 按名称查找
    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_name == name
    ).first()
    if subject:
        return subject

    # 创建新科目（使用预定义 ID 或自增）
    if sid:
        subject = QuestionSubject(
            subject_id=sid,
            subject_name=name,
            subject_code=f"auto_{name}"
        )
    else:
        subject = QuestionSubject(subject_name=name, subject_code=f"auto_{name}")
    try:
        db.add(subject)
        db.flush()
    except Exception:
        db.rollback()
        subject = db.query(QuestionSubject).filter(
            QuestionSubject.subject_name == name
        ).first()
    return subject


def _get_or_create_type(db: Session, type_name: str, subject_id: int) -> QuestionType:
    """
    获取或创建题型（处理并发重复插入与跨科目 type_code 冲突）。

    根因修复：原 type_code=f"auto_{type_name}" 在跨科目（如行测与公专都有"单选题"）时
    违反 type_code 的 UNIQUE 约束 → commit 失败 → rollback → 再查询 (type_name, subject_id)
    仍返回 None → qtype.type_id 抛 AttributeError。
    修复：type_code 改为带 subject_id 前缀，确保跨科目唯一；并加 fallback 防止返回 None。
    """
    # 规范化 type_name（防止脏数据）
    if not type_name:
        type_name = '选择题'

    # 1. 主查询：(type_name, subject_id)
    qtype = db.query(QuestionType).filter(
        and_(
            QuestionType.type_name == type_name,
            QuestionType.subject_id == subject_id
        )
    ).first()
    if qtype:
        return qtype

    # 2. 兼容旧数据：按 type_code 查询（旧格式 "auto_{type_name}"，可能跨科目存在）
    legacy_code = f"auto_{type_name}"
    qtype = db.query(QuestionType).filter(
        QuestionType.type_code == legacy_code
    ).first()
    if qtype:
        # 旧记录存在但 subject_id 不匹配 → 复用其 type_id 关联到当前科目
        # 为避免破坏其他科目已有引用，这里改为：在该 type_id 下创建一条科目映射
        # 实际上更安全的做法是新建一条带新 type_code 的记录
        pass  # 落到下面的创建逻辑

    # 3. 创建新记录：type_code 带 subject_id 前缀确保跨科目唯一
    new_type_code = f"auto_{subject_id}_{type_name}"
    qtype = QuestionType(
        type_name=type_name,
        type_code=new_type_code,
        subject_id=subject_id,
        is_objective=1 if type_name in ('选择题', '单选题', '多选题') else 0
    )
    try:
        db.add(qtype)
        db.commit()
        db.refresh(qtype)
        return qtype
    except Exception as e:
        db.rollback()
        logger.warning(f"_get_or_create_type 创建失败(type_name={type_name}, subject_id={subject_id}): {e}")
        # 4. 并发场景：重新查询
        qtype = db.query(QuestionType).filter(
            and_(
                QuestionType.type_name == type_name,
                QuestionType.subject_id == subject_id
            )
        ).first()
        if qtype:
            return qtype
        # 5. 终极兜底：按新 type_code 再查一次
        qtype = db.query(QuestionType).filter(
            QuestionType.type_code == new_type_code
        ).first()
        if qtype:
            return qtype
        # 6. 仍失败：抛出明确异常，避免返回 None 导致上层 qtype.type_id 报错
        raise HTTPException(
            status_code=500,
            detail=f"题型创建失败: type_name={type_name}, subject_id={subject_id}, code={new_type_code}"
        )
