"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, DECIMAL, 
    Enum, JSON, ForeignKey, Index, UniqueConstraint, BigInteger
)
from sqlalchemy.orm import relationship
from ..core.database import Base

# ------------------------------
# 用户模型
# ------------------------------

class SysUser(Base):
    """系统用户表"""
    __tablename__ = "sys_user"
    
    user_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    user_no = Column(String(50), nullable=False, unique=True, comment="用户编号")
    username = Column(String(100), nullable=False, comment="用户名")
    password = Column(String(255), nullable=False, comment="密码")
    email = Column(String(100), comment="邮箱")
    phone = Column(String(20), nullable=False, comment="手机号")
    avatar = Column(String(500), comment="头像URL")
    gender = Column(Enum("男", "女", "未知"), default="未知", comment="性别")
    user_type = Column(Enum("student", "teacher", "admin"), nullable=False, comment="用户类型")
    department = Column(String(100), comment="学院/部门")
    class_name = Column(String(100), comment="班级")
    school = Column(String(100), default="中国人民警察大学", comment="学校")
    title = Column(String(50), comment="职称")
    specialty = Column(String(100), comment="专业领域")
    role_level = Column(Integer, default=1, comment="权限级别")
    status = Column(Integer, default=1, comment="状态")
    total_coins = Column(Integer, default=0, comment="金币总数")
    continuous_checkin_days = Column(Integer, default=0, comment="连续签到天数")
    total_checkin_days = Column(Integer, default=0, comment="累计签到天数")
    register_time = Column(DateTime, default=datetime.now, comment="注册时间")
    last_login = Column(DateTime, comment="最后登录时间")
    
    __table_args__ = (
        Index("idx_user_no", user_no),
        Index("idx_user_type", user_type),
        Index("idx_status", status),
        Index("idx_department", department, class_name),
    )

class SysLoginLog(Base):
    """用户登录日志表"""
    __tablename__ = "sys_login_log"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    login_time = Column(DateTime, default=datetime.now, comment="登录时间")
    login_ip = Column(String(50), comment="登录IP")
    login_device = Column(String(200), comment="登录设备")
    login_status = Column(Integer, default=1, comment="登录状态")
    failure_reason = Column(String(200), comment="失败原因")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_login_time", login_time),
    )

# ------------------------------
# 题库模型
# ------------------------------

class QuestionSubject(Base):
    """科目分类表"""
    __tablename__ = "question_subject"
    
    subject_id = Column(Integer, primary_key=True, autoincrement=True, comment="科目ID")
    subject_name = Column(String(50), nullable=False, comment="科目名称")
    subject_code = Column(String(20), unique=True, comment="科目代码")
    description = Column(String(500), comment="科目描述")
    sort_order = Column(Integer, default=1, comment="排序")
    status = Column(Integer, default=1, comment="状态")
    
    __table_args__ = (
        Index("idx_subject_code", subject_code),
    )

class QuestionType(Base):
    """题型表"""
    __tablename__ = "question_type"
    
    type_id = Column(Integer, primary_key=True, autoincrement=True, comment="题型ID")
    type_name = Column(String(50), nullable=False, comment="题型名称")
    type_code = Column(String(20), unique=True, comment="题型代码")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), comment="关联科目ID")
    description = Column(String(500), comment="题型描述")
    is_objective = Column(Integer, default=1, comment="是否客观题")
    sort_order = Column(Integer, default=1, comment="排序")
    
    subject = relationship("QuestionSubject")
    
    __table_args__ = (
        Index("idx_type_code", type_code),
        Index("idx_subject_id", subject_id),
    )

class KnowledgePoint(Base):
    """知识点表"""
    __tablename__ = "knowledge_point"
    
    point_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识点ID")
    point_name = Column(String(200), nullable=False, comment="知识点名称")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="所属科目")
    parent_id = Column(BigInteger, default=0, comment="父知识点ID")
    level = Column(Integer, default=1, comment="层级")
    description = Column(String(500), comment="知识点描述")
    sort_order = Column(Integer, default=1, comment="排序")
    
    subject = relationship("QuestionSubject")
    parent = relationship("KnowledgePoint", remote_side=[point_id])
    
    __table_args__ = (
        Index("idx_subject_point", subject_id, point_name),
        Index("idx_parent_id", parent_id),
    )

class QuestionBank(Base):
    """题库主表"""
    __tablename__ = "question_bank"
    
    question_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="题目ID")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="科目ID")
    type_id = Column(Integer, ForeignKey("question_type.type_id"), nullable=False, comment="题型ID")
    question_content = Column(Text, nullable=False, comment="题目内容")
    options = Column(JSON, comment="选项")
    answer = Column(Text, nullable=False, comment="正确答案")
    answer_analysis = Column(Text, comment="答案解析")
    point_id = Column(BigInteger, ForeignKey("knowledge_point.point_id"), comment="知识点ID")
    difficulty = Column(Integer, default=3, comment="难度")
    score = Column(DECIMAL(5, 2), default=0.00, comment="题目分值")
    year = Column(Integer, comment="考试年份")
    source = Column(String(200), comment="题目来源")
    tags = Column(String(500), comment="标签")
    video_url = Column(String(500), comment="讲解视频URL")
    accuracy_rate = Column(DECIMAL(5, 2), default=0.00, comment="正确率")
    exam_frequency = Column(Integer, default=0, comment="考试频率")
    creator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="创建人ID")
    auditor_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="审核人ID")
    audit_status = Column(Integer, default=0, comment="审核状态")
    audit_comment = Column(String(500), comment="审核意见")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    status = Column(Integer, default=1, comment="状态")
    version = Column(Integer, default=1, comment="版本号")
    
    subject = relationship("QuestionSubject")
    type = relationship("QuestionType")
    point = relationship("KnowledgePoint")
    creator = relationship("SysUser", foreign_keys=[creator_id])
    auditor = relationship("SysUser", foreign_keys=[auditor_id])
    
    __table_args__ = (
        Index("idx_subject", subject_id),
        Index("idx_type", type_id),
        Index("idx_point", point_id),
        Index("idx_difficulty", difficulty),
        Index("idx_audit_status", audit_status),
        Index("idx_creator", creator_id),
    )

class QuestionEditLog(Base):
    """题库编辑日志表"""
    __tablename__ = "question_edit_log"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    editor_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="编辑人ID")
    action_type = Column(Enum("CREATE", "UPDATE", "DELETE", "AUDIT"), comment="操作类型")
    old_data = Column(JSON, comment="修改前数据")
    new_data = Column(JSON, comment="修改后数据")
    edit_time = Column(DateTime, default=datetime.now, comment="操作时间")
    remark = Column(String(500), comment="备注")
    
    question = relationship("QuestionBank")
    editor = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_question_id", question_id),
        Index("idx_editor_id", editor_id),
        Index("idx_edit_time", edit_time),
    )

# ------------------------------
# 试卷模型
# ------------------------------

class ExamPaper(Base):
    """试卷主表"""
    __tablename__ = "exam_paper"
    
    paper_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="试卷ID")
    paper_name = Column(String(200), nullable=False, comment="试卷名称")
    paper_code = Column(String(50), unique=True, nullable=False, comment="试卷编号")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="科目ID")
    composition_method = Column(Enum("AUTO", "MANUAL", "TEMPLATE"), nullable=False, comment="组卷方式")
    creator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="出卷人ID")
    approver_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="审批人ID")
    duration = Column(Integer, nullable=False, comment="考试时长")
    total_score = Column(DECIMAL(10, 2), nullable=False, comment="试卷总分")
    difficulty = Column(Integer, default=3, comment="难度")
    question_count = Column(Integer, default=0, comment="题目数量")
    exam_type = Column(Enum("SIMULATION", "PRACTICE", "FORMAL"), default="SIMULATION", comment="考试类型")
    paper_type = Column(Enum("DRAFT", "PENDING", "APPROVED", "PUBLISHED", "ENDED"), default="DRAFT", comment="试卷状态")
    exam_time = Column(DateTime, comment="考试时间")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    description = Column(Text, comment="试卷描述")
    knowledge_range = Column(String(1000), comment="知识点范围")
    question_ratio = Column(JSON, comment="题型比例")
    shuffle_questions = Column(Integer, default=0, comment="是否打乱题目顺序")
    shuffle_options = Column(Integer, default=1, comment="是否打乱选项顺序")
    anti_cheating = Column(Integer, default=0, comment="是否防作弊")
    show_result_quickly = Column(Integer, default=0, comment="是否立即显示结果")
    show_answer_quickly = Column(Integer, default=0, comment="是否立即显示答案")
    max_attempts = Column(Integer, default=1, comment="最大答题次数")
    allow_late_submit = Column(Integer, default=1, comment="是否允许迟交")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    publish_time = Column(DateTime, comment="发布时间")
    
    subject = relationship("QuestionSubject")
    creator = relationship("SysUser", foreign_keys=[creator_id])
    approver = relationship("SysUser", foreign_keys=[approver_id])
    
    __table_args__ = (
        Index("idx_paper_code", paper_code),
        Index("idx_subject_id", subject_id),
        Index("idx_creator", creator_id),
        Index("idx_paper_type", paper_type),
        Index("idx_exam_time", exam_time),
    )

class PaperQuestionRelation(Base):
    """试卷题目关联表"""
    __tablename__ = "paper_question_relation"
    
    relation_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="关联ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    question_order = Column(Integer, nullable=False, comment="题目顺序")
    question_score = Column(DECIMAL(5, 2), nullable=False, comment="本题分数")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    paper = relationship("ExamPaper")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        UniqueConstraint("paper_id", "question_id", name="uk_paper_question"),
        Index("idx_paper_id", paper_id),
        Index("idx_question_id", question_id),
    )

class PaperApproval(Base):
    """试卷审批记录表"""
    __tablename__ = "paper_approval"
    
    approval_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="审批记录ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    approver_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="审批人ID")
    approval_result = Column(Enum("PENDING", "APPROVED", "REJECTED"), default="PENDING", comment="审批结果")
    approval_opinion = Column(Text, comment="审批意见")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    approval_time = Column(DateTime, comment="审批时间")
    
    paper = relationship("ExamPaper")
    approver = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_paper_id", paper_id),
        Index("idx_approver_id", approver_id),
    )

# ------------------------------
# 考试执行模型
# ------------------------------

class ExamRecord(Base):
    """考试记录表"""
    __tablename__ = "exam_record"
    
    record_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="考试记录ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="考生ID")
    exam_type = Column(Enum("SIMULATION", "PRACTICE"), nullable=False, comment="考试类型")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration_used = Column(Integer, comment="用时")
    total_score = Column(DECIMAL(10, 2), default=0.00, comment="总分")
    is_completed = Column(Integer, default=0, comment="是否完成")
    is_scored = Column(Integer, default=0, comment="是否已评分")
    submit_time = Column(DateTime, comment="提交时间")
    is_late = Column(Integer, default=0, comment="是否迟交")
    attempt_count = Column(Integer, default=1, comment="答题次数")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    paper = relationship("ExamPaper")
    user = relationship("SysUser")
    
    __table_args__ = (
        UniqueConstraint("paper_id", "user_id", name="uk_paper_user"),
        Index("idx_paper_id", paper_id),
        Index("idx_user_id", user_id),
        Index("idx_start_time", start_time),
        Index("idx_is_completed", is_completed),
    )

class ExamAnswerDetail(Base):
    """答题详情表"""
    __tablename__ = "exam_answer_detail"
    
    detail_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="答题详情ID")
    record_id = Column(BigInteger, ForeignKey("exam_record.record_id"), nullable=False, comment="考试记录ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    student_answer = Column(Text, comment="学生答案")
    is_correct = Column(Integer, comment="是否正确")
    time_spent = Column(Integer, comment="答题耗时")
    score_obtained = Column(DECIMAL(5, 2), default=0.00, comment="获得分数")
    create_time = Column(DateTime, default=datetime.now, comment="答题时间")
    
    record = relationship("ExamRecord")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_record_id", record_id),
        Index("idx_question_id", question_id),
        Index("idx_is_correct", is_correct),
    )

class ScoreAnalysis(Base):
    """成绩分析表"""
    __tablename__ = "score_analysis"
    
    analysis_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="分析ID")
    record_id = Column(BigInteger, ForeignKey("exam_record.record_id"), nullable=False, comment="考试记录ID")
    total_score = Column(DECIMAL(10, 2), nullable=False, comment="总分")
    score_percentage = Column(DECIMAL(5, 2), comment="得分率")
    subject_scores = Column(JSON, comment="各科目得分")
    question_type_scores = Column(JSON, comment="各题型得分")
    knowledge_scores = Column(JSON, comment="各知识点得分")
    weak_points = Column(JSON, comment="薄弱知识点")
    improvement_suggestion = Column(Text, comment="提升建议")
    analysis_time = Column(DateTime, default=datetime.now, comment="分析时间")
    
    record = relationship("ExamRecord")
    
    __table_args__ = (
        Index("idx_record_id", record_id),
    )

# ------------------------------
# 学习行为模型
# ------------------------------

class PracticeRecord(Base):
    """刷题记录表"""
    __tablename__ = "practice_record"
    
    record_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="刷题记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    answer = Column(Text, comment="用户答案")
    is_correct = Column(Integer, nullable=False, comment="是否正确")
    practice_time = Column(DateTime, default=datetime.now, comment="刷题时间")
    time_spent = Column(Integer, comment="耗时")
    source_type = Column(Enum("RANDOM", "CHAPTER", "WRONG"), comment="刷题来源")
    
    user = relationship("SysUser")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_question_id", question_id),
        Index("idx_practice_time", practice_time),
    )

class WrongQuestionPersonal(Base):
    """个人错题集表"""
    __tablename__ = "wrong_question_personal"
    
    wrong_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="错题ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    collection_type = Column(Enum("WRONG", "FAVORITE", "ESSAY"), default="WRONG", comment="收藏类型")
    error_count = Column(Integer, default=1, comment="错误次数")
    mastery_level = Column(Enum("UNMASTERED", "PARTIAL", "MASTERED"), default="UNMASTERED", comment="掌握程度")
    cut_time = Column(DateTime, comment="斩题时间")
    auto_delete_time = Column(DateTime, comment="自动删除时间")
    review_count = Column(Integer, default=0, comment="复习次数")
    last_review_time = Column(DateTime, comment="最后复习时间")
    note = Column(Text, comment="备注")
    status = Column(Integer, default=1, comment="状态")
    add_time = Column(DateTime, default=datetime.now, comment="添加时间")
    
    user = relationship("SysUser")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", "collection_type", name="uk_user_question"),
        Index("idx_user_id", user_id),
        Index("idx_question_id", question_id),
        Index("idx_mastery_level", mastery_level),
    )

class VideoWatchRecord(Base):
    """视频观看记录表"""
    __tablename__ = "video_watch_record"
    
    record_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="观看记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    video_url = Column(String(500), nullable=False, comment="视频地址")
    watch_duration = Column(Integer, default=0, comment="观看时长")
    total_duration = Column(Integer, nullable=False, comment="视频总时长")
    completion_rate = Column(DECIMAL(5, 2), default=0.00, comment="完成率")
    is_completed = Column(Integer, default=0, comment="是否看完")
    watch_time = Column(DateTime, default=datetime.now, comment="观看时间")
    
    user = relationship("SysUser")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_question_id", question_id),
        Index("idx_watch_time", watch_time),
    )

# ------------------------------
# 互动社区模型
# ------------------------------

class ForumPost(Base):
    """论坛帖子表"""
    __tablename__ = "forum_post"
    
    post_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="发帖人ID")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    share_type = Column(Enum("EXPERIENCE", "RESOURCE", "DISCUSSION", "FEELING"), default="EXPERIENCE", comment="分享类型")
    tags = Column(String(500), comment="标签")
    is_top = Column(Integer, default=0, comment="是否置顶")
    is_essence = Column(Integer, default=0, comment="是否精华")
    like_count = Column(Integer, default=0, comment="点赞数")
    comment_count = Column(Integer, default=0, comment="评论数")
    view_count = Column(Integer, default=0, comment="浏览量")
    collect_count = Column(Integer, default=0, comment="收藏数")
    status = Column(Enum("NORMAL", "DELETED", "BLOCKED"), default="NORMAL", comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="发布时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_create_time", create_time),
        Index("idx_status", status),
    )

class ForumComment(Base):
    """论坛评论表"""
    __tablename__ = "forum_comment"
    
    comment_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="评论ID")
    post_id = Column(BigInteger, ForeignKey("forum_post.post_id"), nullable=False, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="评论人ID")
    parent_comment_id = Column(BigInteger, ForeignKey("forum_comment.comment_id"), comment="父评论ID")
    content = Column(Text, nullable=False, comment="评论内容")
    like_count = Column(Integer, default=0, comment="点赞数")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="评论时间")
    
    post = relationship("ForumPost")
    user = relationship("SysUser")
    parent_comment = relationship("ForumComment", remote_side=[comment_id])
    
    __table_args__ = (
        Index("idx_post_id", post_id),
        Index("idx_user_id", user_id),
        Index("idx_parent_comment", parent_comment_id),
    )

# ------------------------------
# 积分与任务模型
# ------------------------------

class CoinRecord(Base):
    """金币记录表"""
    __tablename__ = "coin_record"
    
    record_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    coin_change = Column(Integer, nullable=False, comment="金币变化")
    current_balance = Column(Integer, nullable=False, comment="当前余额")
    transaction_type = Column(Enum("GAIN", "SPEND"), nullable=False, comment="交易类型")
    source_type = Column(Enum("CHECKIN", "TASK", "EXAM", "SYSTEM", "PURCHASE"), comment="来源/用途")
    related_id = Column(BigInteger, comment="关联ID")
    description = Column(String(500), comment="描述")
    transaction_time = Column(DateTime, default=datetime.now, comment="交易时间")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_transaction_time", transaction_time),
        Index("idx_source_type", source_type),
    )

class DailyCheckin(Base):
    """每日签到表"""
    __tablename__ = "daily_checkin"
    
    checkin_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="签到ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    checkin_date = Column(String(10), nullable=False, comment="签到日期")
    checkin_time = Column(DateTime, default=datetime.now, comment="签到时间")
    continuous_days = Column(Integer, default=1, comment="连续签到天数")
    total_days = Column(Integer, default=1, comment="累计签到天数")
    has_makeup = Column(Integer, default=0, comment="是否补签")
    coin_reward = Column(Integer, default=0, comment="金币奖励")
    streak_bonus = Column(Integer, default=0, comment="连续奖励")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uk_user_date"),
        Index("idx_user_date", user_id, checkin_date),
        Index("idx_checkin_date", checkin_date),
    )


# ------------------------------
# 学习目标模型
# ------------------------------

class StudyGoal(Base):
    """学习目标表"""
    __tablename__ = "study_goal"

    goal_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="目标ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    title = Column(String(200), nullable=False, comment="目标标题")
    description = Column(String(500), comment="目标描述")
    goal_type = Column(Enum("DAILY", "WEEKLY", "MONTHLY", "CUSTOM"), default="DAILY", comment="目标类型")
    target_count = Column(Integer, nullable=False, default=0, comment="目标数量")
    current_count = Column(Integer, default=0, comment="当前完成数")
    deadline = Column(DateTime, comment="截止时间")
    priority = Column(Integer, default=1, comment="优先级 1低/2中/3高")
    is_completed = Column(Integer, default=0, comment="是否完成")
    completed_time = Column(DateTime, comment="完成时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    status = Column(Integer, default=1, comment="状态 1正常/0删除")

    user = relationship("SysUser")

    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_goal_type", goal_type),
        Index("idx_is_completed", is_completed),
        Index("idx_deadline", deadline),
    )


# ------------------------------
# 媒体资源模型
# ------------------------------

class VideoResource(Base):
    """视频资源表"""
    __tablename__ = "video_resource"
    
    video_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="视频ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), comment="关联题目ID")
    title = Column(String(200), nullable=False, comment="视频标题")
    original_filename = Column(String(200), comment="原始文件名")
    storage_path = Column(String(500), nullable=False, comment="存储路径")
    thumbnail_path = Column(String(500), comment="封面路径")
    duration = Column(Integer, nullable=False, comment="时长")
    file_size = Column(BigInteger, nullable=False, comment="文件大小")
    format = Column(String(20), comment="格式")
    resolution = Column(String(20), comment="分辨率")
    bitrate = Column(Integer, comment="码率")
    status = Column(Enum("UPLOADING", "PROCESSING", "COMPLETED", "FAILED"), default="UPLOADING", comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="上传时间")
    process_time = Column(DateTime, comment="处理完成时间")
    
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_question_id", question_id),
        Index("idx_status", status),
    )

class FileResource(Base):
    """文件资源表"""
    __tablename__ = "file_resource"
    
    file_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="文件ID")
    title = Column(String(200), comment="文件标题")
    original_filename = Column(String(200), nullable=False, comment="原始文件名")
    storage_path = Column(String(500), nullable=False, comment="存储路径")
    file_type = Column(Enum("DOC", "PDF", "IMAGE", "OTHER"), comment="文件类型")
    file_size = Column(BigInteger, nullable=False, comment="文件大小")
    mime_type = Column(String(100), comment="MIME类型")
    uploader_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="上传人ID")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="上传时间")
    
    uploader = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_uploader_id", uploader_id),
        Index("idx_file_type", file_type),
    )

# ------------------------------
# 系统配置模型
# ------------------------------

class SysConfig(Base):
    """系统配置表"""
    __tablename__ = "sys_config"
    
    config_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="配置ID")
    config_key = Column(String(100), unique=True, nullable=False, comment="配置键")
    config_value = Column(Text, comment="配置值")
    config_desc = Column(String(500), comment="配置描述")
    config_type = Column(Enum("STRING", "NUMBER", "JSON", "BOOLEAN"), default="STRING", comment="配置类型")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    __table_args__ = (
        Index("idx_config_key", config_key),
    )

class SysOperationLog(Base):
    """操作日志表"""
    __tablename__ = "sys_operation_log"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="操作人ID")
    user_name = Column(String(100), comment="操作人姓名")
    operation_type = Column(String(50), comment="操作类型")
    module_name = Column(String(100), comment="模块名称")
    operation_desc = Column(String(500), comment="操作描述")
    request_method = Column(String(10), comment="请求方法")
    request_url = Column(String(500), comment="请求URL")
    request_params = Column(Text, comment="请求参数")
    response_result = Column(Text, comment="响应结果")
    ip_address = Column(String(50), comment="IP地址")
    operation_time = Column(DateTime, default=datetime.now, comment="操作时间")
    duration = Column(Integer, comment="耗时")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id", user_id),
        Index("idx_operation_time", operation_time),
    )