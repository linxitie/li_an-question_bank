"""
考试业务服务: 开始、提交、进度保存
"""
import json
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.models import (
    ExamPaper, ExamRecord, ExamAnswerDetail, QuestionBank,
    PaperQuestionRelation, SysUser
)

class ExamService:
    """考试核心业务逻辑"""
    
    @staticmethod
    def start_exam(
        db: Session,
        paper_id: int,
        user_id: int,
        exam_type: str = "SELF_TEST"
    ) -> Dict:
        """
        开始或继续考试
        
        Args:
            db: 数据库会话
            paper_id: 试卷ID
            user_id: 用户ID
            exam_type: 考试类型 SELF_TEST/MOCK_EXAM
            
        Returns:
            {
                "exam_id": int,
                "questions": List[Dict],
                "time_limit": int,
                "paper_name": str,
                "total_score": float,
                "is_continuation": bool
            }
        """
        # 1. 验证试卷存在且已发布
        paper = db.query(ExamPaper).filter(
            ExamPaper.paper_id == paper_id,
            ExamPaper.paper_type == "PUBLISHED"
        ).first()
        
        if not paper:
            raise ValueError("试卷不存在或未发布")
        
        # 2. 检查是否有进行中的考试记录
        existing_record = db.query(ExamRecord).filter(
            ExamRecord.paper_id == paper_id,
            ExamRecord.user_id == user_id,
            ExamRecord.is_completed == 0
        ).first()
        
        if existing_record:
            # 继续之前的考试
            return ExamService._continue_exam(db, existing_record, paper)
        
        # 3. 创建新的考试记录
        exam_record = ExamRecord(
            paper_id=paper_id,
            user_id=user_id,
            exam_type=exam_type,
            start_time=datetime.now(),
            is_completed=0,
            is_scored=0,
            attempt_count=1,
        )
        db.add(exam_record)
        db.flush()
        
        # 4. 获取题目（根据试卷设置决定是否打乱）
        questions = ExamService._get_paper_questions(db, paper)
        
        # 5. 返回考试数据
        return {
            "exam_id": exam_record.record_id,
            "questions": questions,
            "time_limit": paper.duration,
            "paper_name": paper.paper_name,
            "total_score": float(paper.total_score),
            "is_continuation": False,
            "paper": {
                "paper_id": paper.paper_id,
                "paper_name": paper.paper_name,
                "duration": paper.duration,
                "total_score": float(paper.total_score),
                "shuffle_questions": bool(paper.shuffle_questions),
                "shuffle_options": bool(paper.shuffle_options),
            }
        }
    
    @staticmethod
    def _continue_exam(db: Session, record: ExamRecord, paper: ExamPaper) -> Dict:
        """继续之前的考试"""
        # 获取已作答记录
        answered = db.query(ExamAnswerDetail).filter(
            ExamAnswerDetail.record_id == record.record_id
        ).all()
        
        answered_map = {a.question_id: a for a in answered}
        
        # 获取试卷题目
        questions = ExamService._get_paper_questions(db, paper)
        
        # 合并已作答数据
        for q in questions:
            if q["question_id"] in answered_map:
                ans = answered_map[q["question_id"]]
                q["student_answer"] = ans.student_answer
                q["time_spent"] = ans.time_spent or 0
        
        # 计算已用时间
        duration_used = int((datetime.now() - record.start_time).total_seconds())
        
        return {
            "exam_id": record.record_id,
            "questions": questions,
            "time_limit": paper.duration,
            "paper_name": paper.paper_name,
            "total_score": float(paper.total_score),
            "is_continuation": True,
            "duration_used": duration_used,
            "answered_count": len(answered),
            "paper": {
                "paper_id": paper.paper_id,
                "paper_name": paper.paper_name,
                "duration": paper.duration,
                "total_score": float(paper.total_score),
                "shuffle_questions": bool(paper.shuffle_questions),
                "shuffle_options": bool(paper.shuffle_options),
            }
        }
    
    @staticmethod
    def _get_paper_questions(db: Session, paper: ExamPaper) -> List[Dict]:
        """获取试卷题目，支持打乱顺序和选项"""
        # 查询关联题目
        relations = db.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper.paper_id
        ).order_by(PaperQuestionRelation.question_order).all()
        
        question_ids = [r.question_id for r in relations]
        score_map = {r.question_id: float(r.question_score) for r in relations}
        
        # 批量查询题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_id.in_(question_ids)
        ).all()
        
        # 构建题目字典
        q_map = {q.question_id: q for q in questions}
        
        # 按原始顺序或打乱顺序组装
        if paper.shuffle_questions:
            random.shuffle(question_ids)
        
        result = []
        for idx, qid in enumerate(question_ids):
            q = q_map.get(qid)
            if not q:
                continue
            
            # 处理选项
            options = q.options or []
            if paper.shuffle_options and options:
                # 保持正确答案对应关系，记录原始索引
                indexed_options = [(i, opt) for i, opt in enumerate(options)]
                random.shuffle(indexed_options)
                shuffled_options = [opt for _, opt in indexed_options]
                # 需要记录映射关系用于评分
                option_map = {new_i: old_i for new_i, (old_i, _) in enumerate(indexed_options)}
            else:
                shuffled_options = options
                option_map = {i: i for i in range(len(options))}
            
            result.append({
                "question_id": q.question_id,
                "question_order": idx + 1,
                "question_content": q.question_content,
                "clean_content": q.question_content,
                "options": shuffled_options,
                "option_map": option_map,  # 前端评分时需要
                "question_type": q.type.type_name if q.type else "未知",
                "type_id": q.type_id,
                "score": score_map.get(qid, q.score or 0),
                "difficulty": q.difficulty,
                "answer_analysis": q.answer_analysis,  # 考试时不返回，提交后返回
            })
        
        return result
    
    @staticmethod
    def save_progress(
        db: Session,
        exam_id: int,
        answers: List[Dict],
        user_id: int
    ) -> Dict:
        """
        保存答题进度
        
        Args:
            answers: [
                {"question_id": 123, "answer": "A", "time_spent": 45},
                ...
            ]
        """
        record = db.query(ExamRecord).filter(
            ExamRecord.record_id == exam_id,
            ExamRecord.user_id == user_id,
            ExamRecord.is_completed == 0
        ).first()
        
        if not record:
            raise ValueError("考试记录不存在或已结束")
        
        for ans in answers:
            question_id = ans.get("question_id")
            student_answer = ans.get("answer", "")
            time_spent = ans.get("time_spent", 0)
            
            # 查找或创建答题详情
            detail = db.query(ExamAnswerDetail).filter(
                ExamAnswerDetail.record_id == exam_id,
                ExamAnswerDetail.question_id == question_id
            ).first()
            
            if detail:
                detail.student_answer = student_answer
                detail.time_spent = time_spent
                detail.create_time = datetime.now()
            else:
                detail = ExamAnswerDetail(
                    record_id=exam_id,
                    question_id=question_id,
                    student_answer=student_answer,
                    time_spent=time_spent,
                )
                db.add(detail)
        
        db.commit()
        
        # 返回当前进度
        answered_count = db.query(ExamAnswerDetail).filter(
            ExamAnswerDetail.record_id == exam_id
        ).count()
        
        return {
            "success": True,
            "answered_count": answered_count,
            "saved_at": datetime.now().isoformat()
        }
    
    @staticmethod
    def submit_exam(
        db: Session,
        exam_id: int,
        user_id: int,
        answers: Optional[List[Dict]] = None
    ) -> Dict:
        """
        提交考试并自动评分
        
        Returns:
            {
                "exam_id": int,
                "total_score": float,
                "score_percentage": float,
                "is_passed": bool,
                "details": List[Dict],
                "analysis": Dict
            }
        """
        record = db.query(ExamRecord).filter(
            ExamRecord.record_id == exam_id,
            ExamRecord.user_id == user_id
        ).first()
        
        if not record:
            raise ValueError("考试记录不存在")
        
        if record.is_completed:
            raise ValueError("考试已完成，不可重复提交")
        
        # 如果提供了最新答案，先保存
        if answers:
            ExamService.save_progress(db, exam_id, answers, user_id)
        
        # 获取所有答题详情
        details = db.query(ExamAnswerDetail).filter(
            ExamAnswerDetail.record_id == exam_id
        ).all()
        
        # 获取题目信息用于评分
        question_ids = [d.question_id for d in details]
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_id.in_(question_ids)
        ).all()
        q_map = {q.question_id: q for q in questions}
        
        # 自动评分
        total_score = 0
        correct_count = 0
        detail_results = []
        
        for detail in details:
            q = q_map.get(detail.question_id)
            if not q:
                continue
            
            is_correct = ExamService._check_answer(q, detail.student_answer)
            score = float(q.score) if is_correct else 0
            total_score += score
            if is_correct:
                correct_count += 1
            
            # 更新详情
            detail.is_correct = 1 if is_correct else 0
            detail.score_obtained = score
            detail.correct_answer = q.answer
            detail.answer_analysis = q.answer_analysis
            detail.difficulty = q.difficulty
            
            detail_results.append({
                "question_id": q.question_id,
                "question_content": q.question_content,
                "clean_content": q.question_content,
                "student_answer": detail.student_answer,
                "correct_answer": q.answer,
                "is_correct": is_correct,
                "score": score,
                "max_score": float(q.score),
                "answer_analysis": q.answer_analysis,
                "question_type": q.type.type_name if q.type else "未知",
            })
        
        # 更新考试记录
        record.is_completed = 1
        record.is_scored = 1
        record.end_time = datetime.now()
        record.submit_time = datetime.now()
        record.duration_used = int((datetime.now() - record.start_time).total_seconds())
        record.total_score = total_score
        
        # 计算得分率
        max_total = sum(float(q_map.get(d.question_id, QuestionBank()).score or 0) for d in details)
        score_percentage = (total_score / max_total * 100) if max_total > 0 else 0
        
        db.commit()
        
        # 生成分析数据
        analysis = ExamService._generate_analysis(db, record, detail_results, q_map)
        
        return {
            "exam_id": exam_id,
            "total_score": total_score,
            "max_score": max_total,
            "score_percentage": round(score_percentage, 2),
            "correct_count": correct_count,
            "total_questions": len(details),
            "duration_used": record.duration_used,
            "details": detail_results,
            "analysis": analysis,
        }
    
    @staticmethod
    def _check_answer(question: QuestionBank, student_answer: str) -> bool:
        """检查答案是否正确"""
        if not student_answer or not question.answer:
            return False
        
        std_answer = question.answer.strip()
        stu_answer = student_answer.strip()
        
        # 判断题
        if question.type and question.type.type_name in ["判断题", "真假题"]:
            true_vals = ["正确", "对", "t", "true", "yes", "是", "1"]
            false_vals = ["错误", "错", "f", "false", "no", "否", "0"]
            
            std_norm = std_answer.lower()
            stu_norm = stu_answer.lower()
            
            std_is_true = std_norm in true_vals
            stu_is_true = stu_norm in true_vals
            
            return std_is_true == stu_is_true
        
        # 选择题：标准化选项字母
        std_letters = set(re.findall(r'[A-Z]', std_answer.upper()))
        stu_letters = set(re.findall(r'[A-Z]', stu_answer.upper()))
        
        # 单选题：完全匹配
        if question.type and question.type.type_name in ["单选题", "单项选择题"]:
            return len(std_letters) == 1 and std_letters == stu_letters
        
        # 多选题/不定项：集合相等
        return std_letters == stu_letters
    
    @staticmethod
    def _generate_analysis(
        db: Session,
        record: ExamRecord,
        details: List[Dict],
        q_map: Dict
    ) -> Dict:
        """生成考试分析数据"""
        # 按题型统计
        type_stats = {}
        for d in details:
            q_type = d.get("question_type", "未知")
            if q_type not in type_stats:
                type_stats[q_type] = {"total": 0, "correct": 0, "score": 0}
            type_stats[q_type]["total"] += 1
            if d["is_correct"]:
                type_stats[q_type]["correct"] += 1
            type_stats[q_type]["score"] += d["score"]
        
        # 按知识点统计
        kp_stats = {}
        for d in details:
            q = q_map.get(d["question_id"])
            if q and q.point:
                kp_name = q.point.point_name
                if kp_name not in kp_stats:
                    kp_stats[kp_name] = {"total": 0, "correct": 0}
                kp_stats[kp_name]["total"] += 1
                if d["is_correct"]:
                    kp_stats[kp_name]["correct"] += 1
        
        # 薄弱知识点（错误率高的）
        weak_points = []
        for kp, stats in kp_stats.items():
            if stats["total"] >= 2:
                error_rate = 1 - stats["correct"] / stats["total"]
                if error_rate > 0.5:
                    weak_points.append({
                        "knowledge_point": kp,
                        "error_rate": round(error_rate * 100, 1),
                        "total": stats["total"],
                        "correct": stats["correct"]
                    })
        
        weak_points.sort(key=lambda x: x["error_rate"], reverse=True)
        
        return {
            "type_stats": type_stats,
            "weak_points": weak_points[:5],
            "score_percentage": round(record.total_score / sum(d["max_score"] for d in details) * 100, 1) if details else 0,
            "duration_used": record.duration_used,
        }
    
    @staticmethod
    def get_exam_preview(db: Session, paper_id: int) -> Dict:
        """
        获取试卷预览（不含答案）
        """
        paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
        if not paper:
            raise ValueError("试卷不存在")
        
        relations = db.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper_id
        ).order_by(PaperQuestionRelation.question_order).all()
        
        question_ids = [r.question_id for r in relations]
        questions = db.query(QuestionBank).filter(
            QuestionBank.question_id.in_(question_ids)
        ).all()
        
        q_map = {q.question_id: q for q in questions}
        
        preview_questions = []
        for r in relations:
            q = q_map.get(r.question_id)
            if not q:
                continue
            
            options = q.options or []
            preview_questions.append({
                "question_id": q.question_id,
                "question_order": r.question_order,
                "question_content": q.question_content,
                "clean_content": q.question_content,
                "options": options,
                "question_type": q.type.type_name if q.type else "未知",
                "score": float(r.question_score),
                "difficulty": q.difficulty,
                # 不包含 answer, answer_analysis
            })
        
        return {
            "paper_id": paper.paper_id,
            "paper_name": paper.paper_name,
            "paper_code": paper.paper_code,
            "subject": paper.subject.subject_name if paper.subject else "未知",
            "duration": paper.duration,
            "total_score": float(paper.total_score),
            "question_count": len(preview_questions),
            "questions": preview_questions,
        }