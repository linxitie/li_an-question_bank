"""
统一题目统计服务: 按角色差异化过滤
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from ..models.models import QuestionBank, SysUser

class QuestionStatsService:
    """题目统计服务 - 统一各端统计口径"""

    @classmethod
    def visible_query(cls, db: Session, include_offline: bool = False,
                      include_pending: bool = False):
        """题目可见性统一入口：默认只看正常状态 + 审核通过。

        Args:
            include_offline: True 时不限制 status（含禁用/草稿等）
            include_pending: True 时不限制 audit_status（含未审核）
        """
        query = db.query(QuestionBank)
        if not include_offline:
            query = query.filter(QuestionBank.status == 1)
        if not include_pending:
            query = query.filter(QuestionBank.audit_status == 1)
        return query

    @staticmethod
    def get_stats(db: Session, user: SysUser, include_offline: bool = False,
                  include_pending: bool = False, mine: bool = False) -> Dict:
        """
        获取题目统计信息

        Args:
            db: 数据库会话
            user: 当前用户
            include_offline: 是否包含非正常状态题目
            include_pending: 是否包含未审核题目
            mine: 教师端是否只看自己创建的题目

        Returns:
            {
                "total": int,             # 总数（按可见性/角色过滤）
                "by_subject": dict,       # 按科目分布
                "by_type": dict,          # 按题型分布
                "by_difficulty": dict,    # 按难度分布
                "by_status": dict,        # 按状态分布
                "visible_total": int,     # 默认可见题目数（学生口径）
                "my_total": int,          # 教师创建的全部题目数（仅教师）
                "student_available": int  # 学生可练习数（仅教师/管理员可见）
            }
        """
        role = str(user.user_type)
        user_id = int(user.user_id)

        # 学生口径（永远只看正常 + 审核通过）
        visible_total = QuestionStatsService.visible_query(db).count()

        # 统计基础查询：默认与学生口径一致
        base_query = QuestionStatsService.visible_query(
            db,
            include_offline=include_offline,
            include_pending=include_pending,
        )

        if role == "teacher" and mine:
            base_query = base_query.filter(QuestionBank.creator_id == user_id)

        total = base_query.count()
        dist_query = base_query

        # 按科目分布
        subject_dist = dist_query.join(
            QuestionBank.subject
        ).with_entities(
            QuestionBank.subject_id,
            func.count(QuestionBank.question_id)
        ).group_by(QuestionBank.subject_id).all()
        
        # 需要科目名称映射
        from ..models.models import QuestionSubject
        subject_names = {s.subject_id: s.subject_name for s in 
                        db.query(QuestionSubject).all()}
        
        by_subject = {subject_names.get(sid, f"科目{sid}"): cnt for sid, cnt in subject_dist}
        
        # 按题型分布
        type_dist = dist_query.join(
            QuestionBank.type
        ).with_entities(
            QuestionBank.type_id,
            func.count(QuestionBank.question_id)
        ).group_by(QuestionBank.type_id).all()
        
        from ..models.models import QuestionType
        type_names = {t.type_id: t.type_name for t in 
                     db.query(QuestionType).all()}
        
        by_type = {type_names.get(tid, f"题型{tid}"): cnt for tid, cnt in type_dist}
        
        # 按难度分布
        diff_dist = dist_query.with_entities(
            QuestionBank.difficulty,
            func.count(QuestionBank.question_id)
        ).group_by(QuestionBank.difficulty).all()
        
        diff_names = {1: "简单", 2: "较易", 3: "中等", 4: "较难", 5: "困难"}
        by_difficulty = {diff_names.get(d, f"难度{d}"): cnt for d, cnt in diff_dist}
        
        # 按状态分布
        status_dist = dist_query.with_entities(
            QuestionBank.status,
            func.count(QuestionBank.question_id)
        ).group_by(QuestionBank.status).all()
        
        status_names = {1: "正常", 0: "禁用", 2: "草稿"}
        by_status = {status_names.get(s, f"状态{s}"): cnt for s, cnt in status_dist}
        
        result = {
            "total": total,
            "by_subject": by_subject,
            "by_type": by_type,
            "by_difficulty": by_difficulty,
            "by_status": by_status,
            "visible_total": visible_total,
        }

        if role == "teacher":
            result["my_total"] = db.query(QuestionBank).filter(
                QuestionBank.creator_id == user_id
            ).count()

        if role in ["teacher", "admin"]:
            result["student_available"] = visible_total

        return result
    
    @staticmethod
    def get_paper_stats(db: Session, user: SysUser) -> Dict:
        """
        获取试卷统计信息
        """
        from ..models.models import ExamPaper
        
        role = user.user_type
        user_id = user.user_id
        
        if role == "student":
            # 学生只看已发布的试卷
            base_query = db.query(ExamPaper).filter(
                ExamPaper.paper_type == "PUBLISHED"
            )
        elif role == "teacher":
            base_query = db.query(ExamPaper).filter(
                ExamPaper.creator_id == user_id
            )
        else:
            base_query = db.query(ExamPaper)
        
        total = base_query.count()
        
        # 按状态分布
        status_dist = base_query.with_entities(
            ExamPaper.paper_type,
            func.count(ExamPaper.paper_id)
        ).group_by(ExamPaper.paper_type).all()
        
        by_status = {str(s): cnt for s, cnt in status_dist}
        
        return {
            "total": total,
            "by_status": by_status,
        }
    
    @staticmethod
    def get_question_count_by_filters(
        db: Session,
        subject_id: Optional[int] = None,
        type_id: Optional[int] = None,
        difficulty: Optional[int] = None,
        status: Optional[int] = None,
        audit_status: Optional[int] = None,
        creator_id: Optional[int] = None,
        for_student: bool = False
    ) -> int:
        """
        通用题目计数，支持多种过滤条件
        
        Args:
            for_student: 是否为学生视角（自动加上 status=1, audit_status=1）
        """
        query = QuestionStatsService.visible_query(db) if for_student \
            else db.query(QuestionBank)
        
        if subject_id:
            query = query.filter(QuestionBank.subject_id == subject_id)
        if type_id:
            query = query.filter(QuestionBank.type_id == type_id)
        if difficulty:
            query = query.filter(QuestionBank.difficulty == difficulty)
        if status is not None:
            query = query.filter(QuestionBank.status == status)
        if audit_status is not None:
            query = query.filter(QuestionBank.audit_status == audit_status)
        if creator_id:
            query = query.filter(QuestionBank.creator_id == creator_id)
        
        return query.count()