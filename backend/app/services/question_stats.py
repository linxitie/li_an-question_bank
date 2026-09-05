"""
统一题目统计服务: 按角色差异化过滤
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from ..models.models import QuestionBank, SysUser

class QuestionStatsService:
    """题目统计服务 - 统一各端统计口径"""
    
    @staticmethod
    def get_stats(db: Session, user: SysUser) -> Dict:
        """
        获取题目统计信息
        
        Args:
            db: 数据库会话
            user: 当前用户
            
        Returns:
            {
                "total": int,           # 总数（按角色过滤）
                "by_subject": dict,     # 按科目分布
                "by_type": dict,        # 按题型分布
                "by_difficulty": dict,  # 按难度分布
                "by_status": dict,      # 按状态分布
                "student_available": int  # 学生可练习数（仅教师/管理员可见）
            }
        """
        role = str(user.user_type)
        user_id = int(user.user_id)
        
        if role == "student":
            # 学生端：只看已发布、可用的题目
            base_query = db.query(QuestionBank).filter(
                QuestionBank.status == 1,  # 正常状态
                QuestionBank.audit_status == 1,  # 审核通过
            )
            total = base_query.count()
            student_available = total
            
        elif role == "teacher":
            # 教师端：看自己创建的所有题目 + 学生可练习题目数
            my_questions = db.query(QuestionBank).filter(
                QuestionBank.creator_id == user_id
            )
            total = my_questions.count()
            
            # 学生可练习数（供对比显示）
            student_available = db.query(QuestionBank).filter(
                QuestionBank.status == 1,
                QuestionBank.audit_status == 1,
            ).count()
            
        else:  # admin
            # 管理员端：看所有题目
            base_query = db.query(QuestionBank)
            total = base_query.count()
            student_available = db.query(QuestionBank).filter(
                QuestionBank.status == 1,
                QuestionBank.audit_status == 1,
            ).count()
        
        # 通用分布查询（根据角色调整基础查询）
        if role == "student":
            dist_query = db.query(QuestionBank).filter(
                QuestionBank.status == 1,
                QuestionBank.audit_status == 1,
            )
        elif role == "teacher":
            dist_query = db.query(QuestionBank).filter(
                QuestionBank.creator_id == user_id
            )
        else:
            dist_query = db.query(QuestionBank)
        
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
        }
        
        # 教师/管理员额外显示学生可用数
        if role in ["teacher", "admin"]:
            result["student_available"] = student_available
        
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
        query = db.query(QuestionBank)
        
        if for_student:
            query = query.filter(
                QuestionBank.status == 1,
                QuestionBank.audit_status == 1,
            )
        
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