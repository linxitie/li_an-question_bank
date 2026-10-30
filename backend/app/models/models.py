"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, SmallInteger, Float, Boolean, String, Text, DateTime, Date, DECIMAL,
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
    
    user_id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    user_no = Column(String(50), nullable=False, unique=True, comment="用户编号")
    username = Column(String(100), nullable=False, comment="用户名")
    password = Column(String(255), nullable=False, comment="密码")
    email = Column(String(100), comment="邮箱")
    phone = Column(String(20), nullable=False, comment="手机号")
    avatar = Column(String(500), comment="头像URL")
    avatar_frame = Column(String(50), comment="头像框标识(金币购商城兑换)")
    nickname = Column(String(50), comment="论坛昵称(为空时回退username)")
    signature = Column(String(200), comment="个性签名")
    gender = Column(Enum("男", "女", "未知"), default="未知", comment="性别")
    user_type = Column(Enum("student", "teacher", "admin"), nullable=False, comment="用户类型")
    department = Column(String(100), comment="学院/部门")
    class_name = Column(String(100), comment="班级")
    school = Column(String(100), default="中国人民警察大学", comment="学校")
    nianji = Column(String(50), comment="年级")
    id_card = Column(String(20), comment="身份证号")
    title = Column(String(50), comment="职称")
    specialty = Column(String(100), comment="专业领域")
    role_level = Column(Integer, default=1, comment="权限级别")
    status = Column(Integer, default=1, comment="状态")
    total_coins = Column(Integer, default=0, comment="金币总数")
    continuous_checkin_days = Column(Integer, default=0, comment="连续签到天数")
    total_checkin_days = Column(Integer, default=0, comment="累计签到天数")
    register_time = Column(DateTime, default=datetime.now, comment="注册时间")
    last_login = Column(DateTime, comment="最后登录时间")

    # === 三端分离架构新增字段 ===
    is_disabled = Column(Integer, default=0, comment="是否禁用 0正常/1禁用")
    disabled_reason = Column(String(255), comment="禁用原因")
    last_login_ip = Column(String(45), comment="最后登录IP地址")
    password_reset_token = Column(String(255), comment="密码重置令牌(哈希)")
    password_reset_expire = Column(DateTime, comment="密码重置令牌过期时间")
    created_by = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="创建人ID(管理员创建教师)")
    school_id = Column(Integer, comment="所属学校/机构ID")
    device_sessions = Column(JSON, default=list, comment="设备会话列表")

    # === 学生端「我的」模块新增字段 ===
    growth_points = Column(Integer, default=0, comment="累计成长值(学习等级)")
    settings = Column(JSON, comment="通知/隐私偏好JSON")
    accuracy80_streak = Column(Integer, default=0, comment="连续练习正确率≥80%次数")
    perfect_streak = Column(Integer, default=0, comment="连续练习全部答对次数")

    # === 徽章生成器新增计数字段 ===
    ai_qa_total = Column(Integer, default=0, comment="AI问答累计次数")
    news_read_total = Column(Integer, default=0, comment="时政资讯阅读累计次数")
    news_read_today = Column(Integer, default=0, comment="时政资讯当日阅读次数")
    news_read_date = Column(Date, comment="时政资讯当日计数对应日期")
    recruit_read_total = Column(Integer, default=0, comment="招考信息浏览累计次数")
    recruit_read_today = Column(Integer, default=0, comment="招考信息当日浏览次数")
    recruit_read_date = Column(Date, comment="招考信息当日计数对应日期")
    ai_qa_count = Column(Integer, default=0, comment="AI问答累计次数")
    news_read_count = Column(Integer, default=0, comment="时政资讯阅读累计次数")
    recruit_read_count = Column(Integer, default=0, comment="招考信息浏览累计次数")

    # 自引用关系：创建人
    creator = relationship("SysUser", remote_side=[user_id], foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_user_no", user_no),
        Index("idx_user_type", user_type),
        Index("idx_status_sysuser", status),
        Index("idx_is_disabled", is_disabled),
        Index("idx_department", department, class_name),
        Index("idx_school_id", school_id),
    )

class SysLoginLog(Base):
    """用户登录日志表"""
    __tablename__ = "sys_login_log"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    login_time = Column(DateTime, default=datetime.now, comment="登录时间")
    login_ip = Column(String(50), comment="登录IP")
    login_device = Column(String(200), comment="登录设备")
    login_status = Column(Integer, default=1, comment="登录状态")
    failure_reason = Column(String(200), comment="失败原因")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id_sysloginlog", user_id),
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
        Index("idx_type_subject_id", subject_id),
    )

class KnowledgePoint(Base):
    """知识点/考点表 — 支持三级分类（科目→子科目→考点）"""
    __tablename__ = "knowledge_point"

    point_id = Column(Integer, primary_key=True, autoincrement=True, comment="知识点ID")
    point_name = Column(String(200), nullable=False, comment="知识点名称")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="所属科目")
    sub_category_id = Column(Integer, ForeignKey("sub_categories.id"), nullable=True, comment="所属子科目ID（三级分类）")
    parent_id = Column(BigInteger, ForeignKey("knowledge_point.point_id"), default=0, comment="父知识点ID（旧树形结构）")
    level = Column(Integer, default=1, comment="层级")
    description = Column(String(500), comment="知识点描述")
    sort_order = Column(Integer, default=1, comment="排序")
    status = Column(Integer, default=1, comment="状态：1正常/0隐藏")

    subject = relationship("QuestionSubject")
    sub_category = relationship("SubCategory", foreign_keys=[sub_category_id])
    parent = relationship("KnowledgePoint", remote_side=[point_id])

    __table_args__ = (
        Index("idx_subject_point", subject_id, point_name),
        Index("idx_parent_id", parent_id),
        Index("idx_kp_sub_category", sub_category_id),
    )

class QuestionBank(Base):
    """题库主表"""
    __tablename__ = "question_bank"
    
    question_id = Column(Integer, primary_key=True, autoincrement=True, comment="题目ID")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="科目ID")
    type_id = Column(Integer, ForeignKey("question_type.type_id"), nullable=False, comment="题型ID")
    question_content = Column(Text, nullable=False, comment="题目内容")
    options = Column(JSON, comment="选项")
    answer = Column(Text, nullable=False, comment="正确答案")
    answer_analysis = Column(Text, comment="答案解析")
    point_id = Column(BigInteger, ForeignKey("knowledge_point.point_id"), comment="知识点ID")
    sub_category_id = Column(Integer, ForeignKey("sub_categories.id"), nullable=True, comment="归一化子科目ID（NULL=未分类）")
    difficulty = Column(Integer, default=3, comment="难度")
    score = Column(DECIMAL(5, 2), default=0.00, comment="题目分值")
    year = Column(Integer, comment="考试年份")
    source = Column(String(200), comment="题目来源")
    tags = Column(String(500), comment="标签")
    video_url = Column(String(500), comment="讲解视频URL")
    accuracy_rate = Column(DECIMAL(5, 2), default=0.00, comment="正确率")
    exam_frequency = Column(Integer, default=0, comment="考试频率")
    
    # 子科目分类（行测/申论/公专）
    # 注：科学推理 为实测补充（4 套卷以「科学推理」替代「数量关系」：广东/河南等）。
    # 实测 SQLite 侧为 VARCHAR(7) 且无 CHECK 约束（SQLAlchemy 2.0 Enum.create_constraint
    # 默认 False），故补该值**无需 DB 结构迁移**。
    xingce_subcategory = Column(Enum(
        "政治理论", "常识判断", "言语理解与表达", "数量关系",
        "判断推理", "资料分析", "知觉速度与准确性", "科学推理",
        "常识", "速度与知觉训练", "语言理解与表达", "无"  # 旧值兼容
    ), default="无", comment="行测细分类型")
    shenlun_subcategory = Column(Enum(
        "归纳概括", "综合分析", "提出对策", "应用文写作", "议论文写作", "无"
    ), default="无", comment="申论细分类型")
    gongzhuan_subcategory = Column(Enum(
        "职业素养", "基础知识", "基本警务能力",
        "法律知识", "业务能力", "无"  # 旧值兼容
    ), default="无", comment="公专细分类型")
    
    creator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="创建人ID")
    auditor_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="审核人ID")
    audit_status = Column(Integer, default=0, comment="审核状态")
    audit_comment = Column(String(500), comment="审核意见")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    status = Column(Integer, default=1, comment="状态")
    version = Column(Integer, default=1, comment="版本号")

    # ===== 复合题（题组）扩展字段（v1.1 §3.1 表2；group_id=0 表示非复合题）=====
    group_id = Column(Integer, default=0, comment="所属题组ID（question_groups.id，0=非复合题）")
    parent_id = Column(Integer, default=0, comment="母题ID（0=无母题）")
    question_level = Column(Integer, default=1, comment="题目层级：1=母题/独立题 2=小题")
    sort_order = Column(Integer, default=0, comment="题组内排序")
    question_number = Column(String(10), comment="原题号（如71、72）")
    # P1/P3b：题型判定置信度不足时置 1，交由教师在「题目管理 → 待复核」筛选中人工确认。
    # 0=已确认/无需复核，1=待复核。写入时机：导入管线判定 confidence < 阈值时。
    # 待人工复核标记。**语义已由任务 13 扩展**，原注释仅写「题型存疑」，
    # 与实际用途不符会误导后续维护者。四类触发情形（任一命中即置 1）：
    #   1. 选项待补文字 —— 选项 A/B/C/D 键存在但值全空（纯图片选项）
    #   2. 答案缺失
    #   3. 解析缺失
    #   4. 材料关联异常 —— 资料分析题未关联到材料块
    # 另保留原语义：题型存疑（解析器判定 suspicious）。
    # 注意与 question_import 的 `blocked` 是两套语义：`blocked` 阻断确认入库，
    # `need_review` 只标红提示且**仍然入库**（用户决策：不达标也入库，不静默丢弃）。
    need_review = Column(Integer, default=0, comment="待人工复核标记：1=题型存疑/选项待补文字/答案缺失/解析缺失/材料关联异常 0=正常")
    # 申论题目要求（乙方案）：采集/作答/格式要求原文，可能是纯文本也可能是「（1）（2）」分点。
    # 独立成列而非塞进 question_content：要求是采分点依据，题库要能单独检索与比对。
    # 缺解析时留空，绝不伪造。
    requirements = Column(Text, comment="申论题目要求（作答要求/采分点依据）")

    subject = relationship("QuestionSubject")
    type = relationship("QuestionType")
    point = relationship("KnowledgePoint")
    sub_category = relationship("SubCategory")
    creator = relationship("SysUser", foreign_keys=[creator_id])
    auditor = relationship("SysUser", foreign_keys=[auditor_id])

    __table_args__ = (
        Index("idx_subject", subject_id),
        Index("idx_type", type_id),
        Index("idx_point", point_id),
        Index("idx_question_sub_category", sub_category_id),
        Index("idx_difficulty", difficulty),
        Index("idx_audit_status", audit_status),
        Index("idx_creator_questionbank", creator_id),
        Index("idx_questions_subject_status", "subject_id", "status"),
        Index("idx_questions_creator_status", "creator_id", "status"),
        Index("idx_group_id", group_id),
    )


class QuestionGroup(Base):
    """题组表（复合题：共享材料/情境 → 小题集合）。

    设计原则（方案 v1.1 §7.5 适配层）：题组仅是"展示聚合视图"，不是新业务实体——
    组卷/答题/计分/统计仍以 question_bank 扁平小题为操作单元。
    SQLite 兼容：JSON 类字段用 TEXT 存储 JSON 串；自增用 Integer PK。
    """
    __tablename__ = "question_groups"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="题组ID")
    group_type = Column(String(20), default="material",
                        comment="题组类型：material/scenario/passage/data_analysis")
    shared_content = Column(Text, comment="共享内容（材料/情境/文章）")
    shared_content_images = Column(Text, comment="共享内容图片URL列表（JSON串）")
    title = Column(String(200), comment="题组标题（如：根据以下情境材料，回答71-73题）")
    subject = Column(String(20), comment="科目：行测/申论/公专")
    difficulty = Column(String(10), comment="整体难度")
    source = Column(String(50), comment="来源（试卷名/年份）")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_qgroup_subject", subject),
    )

class QuestionEditLog(Base):
    """题库编辑日志表"""
    __tablename__ = "question_edit_log"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
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
        Index("idx_question_id_questioneditlog", question_id),
        Index("idx_editor_id", editor_id),
        Index("idx_edit_time", edit_time),
    )

# ------------------------------
# 试卷模型
# ------------------------------

class ExamPaper(Base):
    """试卷主表"""
    __tablename__ = "exam_paper"
    
    paper_id = Column(Integer, primary_key=True, autoincrement=True, comment="试卷ID")
    paper_name = Column(String(200), nullable=False, comment="试卷名称")
    original_title = Column(Text, comment="原始文档标题")
    paper_code = Column(String(50), unique=True, nullable=False, comment="试卷编号")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="科目ID")
    subject_confidence = Column(DECIMAL(3, 2), comment="科目识别置信度")
    is_manually_confirmed = Column(Integer, default=0, comment="是否人工确认 0否/1是")
    detected_subject = Column(String(50), comment="系统识别的科目")
    composition_method = Column(Enum("AUTO", "MANUAL", "TEMPLATE", "SMART", "IMPORT"), nullable=False, comment="组卷方式")
    creator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="出卷人ID")
    approver_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="审批人ID")
    duration = Column(Integer, nullable=False, comment="考试时长")
    total_score = Column(DECIMAL(10, 2), nullable=False, comment="试卷总分")
    difficulty = Column(Integer, default=3, comment="难度")
    question_count = Column(Integer, default=0, comment="题目数量")
    exam_type = Column(Enum("SIMULATION", "PRACTICE", "FORMAL"), default="SIMULATION", comment="考试类型")
    paper_type = Column(Enum("DRAFT", "PENDING", "APPROVED", "PUBLISHED", "ENDED"), default="DRAFT", comment="试卷状态")
    publish_target = Column(String(20), comment="发布目标: past_paper(历年试卷)/mock_exam(小模考)")
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
        Index("idx_creator_exampaper", creator_id),
        Index("idx_paper_type", paper_type),
        Index("idx_exam_time", exam_time),
        Index("idx_papers_subject_status", "subject_id", "paper_type"),
        Index("idx_papers_creator_status", "creator_id", "paper_type"),
    )

class PaperQuestionRelation(Base):
    """试卷题目关联表"""
    __tablename__ = "paper_question_relation"
    
    relation_id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    question_order = Column(Integer, nullable=False, comment="题目顺序")
    question_score = Column(DECIMAL(5, 2), nullable=False, comment="本题分数")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    paper = relationship("ExamPaper")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        UniqueConstraint("paper_id", "question_id", name="uk_paper_question"),
        Index("idx_paper_id_paperquestionrelation", paper_id),
        Index("idx_question_id_paperquestionrelation", question_id),
    )

class PaperApproval(Base):
    """试卷审批记录表"""
    __tablename__ = "paper_approval"
    
    approval_id = Column(Integer, primary_key=True, autoincrement=True, comment="审批记录ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    approver_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="审批人ID")
    approval_result = Column(Enum("PENDING", "APPROVED", "REJECTED"), default="PENDING", comment="审批结果")
    approval_opinion = Column(Text, comment="审批意见")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    approval_time = Column(DateTime, comment="审批时间")
    
    paper = relationship("ExamPaper")
    approver = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_paper_id_paperapproval", paper_id),
        Index("idx_approver_id", approver_id),
    )

# ------------------------------
# 考试执行模型
# ------------------------------

class ExamRecord(Base):
    """考试记录表"""
    __tablename__ = "exam_record"
    
    record_id = Column(Integer, primary_key=True, autoincrement=True, comment="考试记录ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="考生ID")
    exam_type = Column(Enum("SELF_TEST", "MOCK_EXAM"), nullable=False, comment="考试类型: SELF_TEST自测/MOCK_EXAM模考")
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
        # B4修复: 移除uk_paper_user唯一约束，允许多次参加同一试卷
        Index("idx_paper_id_examrecord", paper_id),
        Index("idx_user_id_examrecord", user_id),
        Index("idx_paper_user_examrecord", paper_id, user_id),
        Index("idx_start_time", start_time),
        Index("idx_is_completed_examrecord", is_completed),
    )

class ExamAnswerDetail(Base):
    """答题详情表"""
    __tablename__ = "exam_answer_detail"
    
    detail_id = Column(Integer, primary_key=True, autoincrement=True, comment="答题详情ID")
    record_id = Column(BigInteger, ForeignKey("exam_record.record_id"), nullable=False, comment="考试记录ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    student_answer = Column(Text, comment="学生答案")
    is_correct = Column(Integer, comment="是否正确")
    time_spent = Column(Integer, comment="答题耗时")
    score_obtained = Column(DECIMAL(5, 2), default=0.00, comment="获得分数")
    difficulty = Column(Integer, comment="题目难度")
    correct_answer = Column(Text, comment="正确答案")
    answer_analysis = Column(Text, comment="答案解析")
    knowledge_point = Column(String(200), comment="知识点")
    note = Column(Text, comment="学生笔记")
    frequency = Column(Integer, default=0, comment="出题频率")
    correct_rate = Column(DECIMAL(10, 2), comment="正确率")
    create_time = Column(DateTime, default=datetime.now, comment="答题时间")
    
    record = relationship("ExamRecord")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_record_id_examanswerdetail", record_id),
        Index("idx_question_id_examanswerdetail", question_id),
        Index("idx_is_correct", is_correct),
    )

class ScoreAnalysis(Base):
    """成绩分析表"""
    __tablename__ = "score_analysis"
    
    analysis_id = Column(Integer, primary_key=True, autoincrement=True, comment="分析ID")
    record_id = Column(BigInteger, ForeignKey("exam_record.record_id"), nullable=False, comment="考试记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="学生ID")
    teacher_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="指导教师ID")
    exam_type = Column(String(50), comment="考试类型")
    total_score = Column(DECIMAL(10, 2), nullable=False, comment="总分")
    score_percentage = Column(DECIMAL(5, 2), comment="得分率")
    subject_scores = Column(JSON, comment="各科目得分")
    question_type_scores = Column(JSON, comment="各题型得分")
    knowledge_scores = Column(JSON, comment="各知识点得分")
    shenlun_score = Column(DECIMAL(10,2), default=0.00, comment="申论得分")
    xingce_score = Column(DECIMAL(10,2), default=0.00, comment="行测得得分")
    police_score = Column(DECIMAL(10,2), default=0.00, comment="公专得分")
    single_correct_count = Column(Integer, default=0, comment="单选题正确数")
    multiple_correct_count = Column(Integer, default=0, comment="多选题正确数")
    essay_score = Column(DECIMAL(10,2), default=0.00, comment="论述题得分")
    practical_score = Column(DECIMAL(10,2), default=0.00, comment="应用文写作得分")
    argument_score = Column(DECIMAL(10,2), default=0.00, comment="议论文写作得分")
    analysis_chart_data = Column(JSON, comment="分析图数据")
    weak_points = Column(JSON, comment="薄弱知识点")
    improvement_suggestion = Column(Text, comment="提升建议")
    analysis_time = Column(DateTime, default=datetime.now, comment="分析时间")
    
    student = relationship("SysUser", foreign_keys=[user_id])
    teacher = relationship("SysUser", foreign_keys=[teacher_id])
    record = relationship("ExamRecord")
    
    __table_args__ = (
        Index("idx_record_id_scoreanalysis", record_id),
    )

# ------------------------------
# 学习行为模型
# ------------------------------

class PracticeRecord(Base):
    """刷题记录表"""
    __tablename__ = "practice_record"

    record_id = Column(Integer, primary_key=True, autoincrement=True, comment="刷题记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), comment="科目ID")
    type_id = Column(Integer, ForeignKey("question_type.type_id"), comment="题型ID")
    answer = Column(Text, comment="用户答案")
    is_correct = Column(Integer, nullable=False, comment="是否正确")
    practice_time = Column(DateTime, default=datetime.now, comment="刷题时间")
    practice_date = Column(Date, comment="刷题日期（用于按日统计）")
    time_spent = Column(Integer, comment="耗时（秒）")
    source_type = Column(String(50), comment="刷题来源（随机练习/章节练习/错题复习/快速练习/历年试卷/智能组卷）")

    user = relationship("SysUser")
    question = relationship("QuestionBank")
    subject = relationship("QuestionSubject")
    question_type = relationship("QuestionType")

    __table_args__ = (
        Index("idx_user_id_practicerecord", user_id),
        Index("idx_question_id_practicerecord", question_id),
        Index("idx_practice_time", practice_time),
        Index("idx_practice_date", practice_date),
        # 目标进度与全时段统计都按「某用户 + 某日期区间 + 某科目」聚合，
        # 现有单列索引无法同时命中这三个条件，会退化为扫描 user_id 后再过滤。
        # 该复合索引顺序与查询的等值/范围条件顺序一致（user_id 等值 →
        # practice_date 范围 → subject_id 分组）。
        Index(
            "idx_user_date_subject_practicerecord",
            user_id,
            practice_date,
            subject_id,
        ),
    )

class SmartExamRecord(Base):
    """智能组卷练习记录表"""
    __tablename__ = "smart_exam_record"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    paper_id = Column(Integer, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    exam_record_id = Column(Integer, ForeignKey("exam_record.record_id"), nullable=True, comment="关联考试记录ID（提交后创建）")
    paper_name = Column(String(200), comment="试卷名称快照")
    subject_mode = Column(String(20), comment="科目模式: xingce/shenlun/gongzhuan/mixed")
    total_questions = Column(Integer, default=0, comment="总题数")
    completed_count = Column(Integer, default=0, comment="已答题数")
    total_score = Column(DECIMAL(10, 2), default=0.00, comment="试卷总分")
    earned_score = Column(DECIMAL(10, 2), nullable=True, comment="得分")
    status = Column(String(20), default="incomplete", comment="状态: incomplete/completed")
    current_index = Column(Integer, default=0, comment="当前答题索引（断点续答）")
    answers_json = Column(Text, comment="已作答答案JSON快照")
    marked_questions = Column(Text, comment="标记题目ID列表JSON")
    time_spent = Column(Integer, default=0, comment="已用时间（秒）")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="完成时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    user = relationship("SysUser")
    paper = relationship("ExamPaper", foreign_keys=[paper_id])

    __table_args__ = (
        Index("idx_smart_user_id", user_id),
        Index("idx_smart_paper_id", paper_id),
        Index("idx_smart_status", status),
        Index("idx_smart_create_time", create_time),
    )

class WrongQuestionPersonal(Base):
    """个人错题集表"""
    __tablename__ = "wrong_question_personal"
    
    wrong_id = Column(Integer, primary_key=True, autoincrement=True, comment="错题ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), comment="科目ID")
    collection_type = Column(Enum("WRONG", "FAVORITE", "ESSAY"), default="WRONG", comment="收藏类型")
    error_count = Column(Integer, default=1, comment="错误次数")
    mastery_level = Column(Enum("UNMASTERED", "PARTIAL", "MASTERED"), default="UNMASTERED", comment="掌握程度")
    is_cut = Column(Integer, default=0, comment="是否已斩题")
    accuracy_rate = Column(DECIMAL(5, 2), default=0.00, comment="正确率")
    cut_time = Column(DateTime, comment="斩题时间")
    auto_delete_time = Column(DateTime, comment="自动删除时间")
    review_count = Column(Integer, default=0, comment="复习次数")
    correct_count = Column(Integer, default=0, comment="答对次数（用于答对3次自动斩题）")
    last_review_time = Column(DateTime, comment="最后复习时间")
    user_answer = Column(Text, comment="用户最近一次复习的答案")
    note = Column(Text, comment="备注")
    status = Column(Integer, default=1, comment="状态")
    add_time = Column(DateTime, default=datetime.now, comment="添加时间")
    
    user = relationship("SysUser")
    question = relationship("QuestionBank")
    
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", "collection_type", name="uk_user_question"),
        Index("idx_user_id_wrongquestionpersonal", user_id),
        Index("idx_question_id_wrongquestionpersonal", question_id),
        Index("idx_mastery_level", mastery_level),
    )

class VideoWatchRecord(Base):
    """视频观看记录表"""
    __tablename__ = "video_watch_record"
    
    record_id = Column(Integer, primary_key=True, autoincrement=True, comment="观看记录ID")
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
        Index("idx_user_id_videowatchrecord", user_id),
        Index("idx_question_id_videowatchrecord", question_id),
        Index("idx_watch_time", watch_time),
    )

# ------------------------------
# 互动社区模型
# ------------------------------

class ForumPost(Base):
    """论坛帖子表"""
    __tablename__ = "forum_post"
    
    post_id = Column(Integer, primary_key=True, autoincrement=True, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="发帖人ID")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    share_type = Column(Enum("EXPERIENCE", "RESOURCE", "DISCUSSION", "FEELING", "QUESTION"), default="EXPERIENCE", comment="分享类型")
    tags = Column(String(500), comment="标签")
    is_top = Column(Integer, default=0, comment="是否置顶")
    is_essence = Column(Integer, default=0, comment="是否精华")
    like_count = Column(Integer, default=0, comment="点赞数")
    comment_count = Column(Integer, default=0, comment="评论数")
    view_count = Column(Integer, default=0, comment="浏览量")
    collect_count = Column(Integer, default=0, comment="收藏数")
    status = Column(Enum("NORMAL", "DELETED", "BLOCKED"), default="NORMAL", comment="状态")
    attachments = Column(JSON, comment="附件列表JSON:[{name,url,size,type}]")
    # === P1 个性化/互动扩展 ===
    title_color = Column(String(16), default="default", comment="标题颜色 token")
    is_locked = Column(Integer, default=0, comment="是否关闭评论 0否/1是")
    question_id = Column(BigInteger, comment="关联题目ID")
    feedback_id = Column(BigInteger, comment="关联反馈工单ID")
    # === P3 可见范围（2026-10-26）===
    visibility = Column(String(16), default="ALL", comment="可见范围: ALL 全校 | CLASSES 指定班级")
    visible_classes = Column(JSON, comment="可见班级名列表 JSON，visibility=CLASSES 时生效")
    last_activity_time = Column(DateTime, default=datetime.now, comment="最后活跃时间")
    deleted_by = Column(BigInteger, comment="删除人ID")
    deleted_reason = Column(String(200), comment="删除原因")
    deleted_at = Column(DateTime, comment="删除时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    user = relationship("SysUser")

    __table_args__ = (
        Index("idx_user_id_forumpost", user_id),
        Index("idx_create_time", create_time),
        Index("idx_status_forumpost", status),
        Index("idx_status_top_time", status, is_top, create_time),
        Index("idx_post_activity", status, last_activity_time),
    )

class ForumComment(Base):
    """论坛评论表"""
    __tablename__ = "forum_comment"
    
    comment_id = Column(Integer, primary_key=True, autoincrement=True, comment="评论ID")
    post_id = Column(BigInteger, ForeignKey("forum_post.post_id"), nullable=False, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="评论人ID")
    parent_comment_id = Column(BigInteger, ForeignKey("forum_comment.comment_id"), comment="父评论ID")
    content = Column(Text, nullable=False, comment="评论内容")
    like_count = Column(Integer, default=0, comment="点赞数")
    status = Column(Integer, default=1, comment="状态 1正常/0删除/2隐藏")
    # === P1 评论区扩展 ===
    is_pinned = Column(Integer, default=0, comment="是否置顶 0否/1是")
    reply_to_user_id = Column(BigInteger, comment="回复目标用户ID")
    attachments = Column(JSON, comment="评论附件 JSON:[{name,url,size,type}]")
    deleted_by = Column(BigInteger, comment="删除/隐藏操作人ID")
    deleted_reason = Column(String(200), comment="删除/隐藏原因")
    deleted_at = Column(DateTime, comment="删除/隐藏时间")
    create_time = Column(DateTime, default=datetime.now, comment="评论时间")
    
    post = relationship("ForumPost")
    user = relationship("SysUser")
    parent_comment = relationship("ForumComment", remote_side=[comment_id])
    
    __table_args__ = (
        Index("idx_post_id", post_id),
        Index("idx_user_id_forumcomment", user_id),
        Index("idx_parent_comment", parent_comment_id),
    )

# ------------------------------
# 积分与任务模型
# ------------------------------

class CoinRecord(Base):
    """金币记录表"""
    __tablename__ = "coin_record"
    
    record_id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    coin_change = Column(Integer, nullable=False, comment="金币变化")
    current_balance = Column(Integer, nullable=False, comment="当前余额")
    transaction_type = Column(Enum("GAIN", "SPEND"), nullable=False, comment="交易类型")
    source_type = Column(Enum("CHECKIN", "TASK", "EXAM", "SYSTEM", "PURCHASE", "RANDOM_TASK", "GOAL", "SHOP"), comment="来源/用途")
    related_id = Column(BigInteger, comment="关联ID")
    description = Column(String(500), comment="描述")
    transaction_time = Column(DateTime, default=datetime.now, comment="交易时间")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id_coinrecord", user_id),
        Index("idx_transaction_time", transaction_time),
        Index("idx_source_type", source_type),
    )

class ShopProduct(Base):
    """金币商城商品表"""
    __tablename__ = "shop_products"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="商品ID")
    name = Column(String(200), nullable=False, comment="商品名称")
    category = Column(String(20), default="", comment="分类: 限定称号/专属头像框")
    product_type = Column(String(20), default="virtual", comment="类型: virtual/physical")
    coin_price = Column(Integer, nullable=False, default=0, comment="金币价格")
    cash_price = Column(DECIMAL(10, 2), nullable=True, comment="现金价格(后置预留)")
    stock = Column(Integer, default=-1, comment="库存(-1=不限)")
    image_url = Column(String(300), default="", comment="封面图(emoji或URL)")
    description = Column(Text, comment="商品详情")
    deliverable_type = Column(String(30), default="none", comment="权益类型: title/avatar_frame")
    deliverable_payload = Column(JSON, comment="权益参数JSON")
    status = Column(String(20), default="on_sale", comment="状态: on_sale/off_shelf")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_shop_product_status", status),
        Index("idx_shop_product_category", category),
    )


class CoinExchange(Base):
    """金币兑换记录表"""
    __tablename__ = "coin_exchanges"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="兑换ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    product_id = Column(Integer, comment="商品ID")
    product_name = Column(String(200), comment="商品名称快照")
    product_type = Column(String(20), comment="商品类型快照")
    coin_cost = Column(Integer, nullable=False, default=0, comment="消耗金币")
    cash_cost = Column(DECIMAL(10, 2), nullable=True, comment="现金支付(后置预留)")
    status = Column(String(20), default="completed", comment="状态: pending/completed/refunded")
    deliverable_type = Column(String(30), comment="权益类型快照")
    deliverable_payload = Column(JSON, comment="权益参数快照")
    request_id = Column(String(64), nullable=False, comment="幂等键(客户端请求ID)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    completed_at = Column(DateTime, comment="完成时间")

    user = relationship("SysUser")

    __table_args__ = (
        UniqueConstraint("request_id", name="uk_coin_exchange_request"),
        Index("idx_coin_exchange_user", user_id),
        Index("idx_coin_exchange_product", product_id),
    )


class DailyCheckin(Base):
    """每日签到表"""
    __tablename__ = "daily_checkin"
    
    checkin_id = Column(Integer, primary_key=True, autoincrement=True, comment="签到ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    checkin_date = Column(String(10), nullable=False, comment="签到日期")
    checkin_time = Column(DateTime, default=datetime.now, comment="签到时间")
    continuous_days = Column(Integer, default=1, comment="连续签到天数")
    total_days = Column(Integer, default=1, comment="累计签到天数")
    has_makeup = Column(Integer, default=0, comment="是否补签")
    coin_reward = Column(Integer, default=0, comment="金币奖励")
    streak_bonus = Column(Integer, default=0, comment="连续奖励")
    makeup_card_count = Column(Integer, default=0, comment="补签卡数量")
    practice_count_after_checkin = Column(Integer, default=0, comment="签到后做题量")
    
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

    goal_id = Column(Integer, primary_key=True, autoincrement=True, comment="目标ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    title = Column(String(200), nullable=False, comment="目标标题")
    description = Column(String(500), comment="目标描述")
    goal_type = Column(Enum("DAILY", "WEEKLY", "MONTHLY", "CUSTOM"), default="DAILY", comment="目标类型")
    target_count = Column(Integer, nullable=False, default=0, comment="目标数量")
    current_count = Column(Integer, default=0, comment="当前完成数")
    # 今日学习科目：0=混科（不限定科目），>0=单科 subject_id
    subject_mode = Column(Integer, default=0, comment="今日学习科目 0混科/>0单科subject_id")
    # 单日预期学习时长（分钟），0=未设置
    expected_minutes = Column(Integer, default=0, comment="单日预期学习时长(分钟)")
    deadline = Column(DateTime, comment="截止时间")
    priority = Column(Integer, default=1, comment="优先级 1低/2中/3高")
    is_completed = Column(Integer, default=0, comment="是否完成")
    completed_time = Column(DateTime, comment="完成时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    status = Column(Integer, default=1, comment="状态 1正常/0删除")

    # === 金币购：四维加权奖励字段 ===
    base_reward = Column(Integer, default=20, comment="基础奖励金币")
    reward_coins = Column(Integer, default=0, comment="最终发放金币")
    difficulty_factor = Column(Float, default=1.0, comment="难度系数")
    quality_score = Column(Float, default=0.0, comment="质量分")
    persistence_score = Column(Float, default=0.0, comment="坚持分")
    improvement_score = Column(Float, default=0.0, comment="进步分")
    baseline_accuracy = Column(Float, default=0.0, comment="基线正确率(创建时快照)")
    baseline_count = Column(Integer, default=0, comment="基线做题量(创建时快照)")

    user = relationship("SysUser")

    __table_args__ = (
        Index("idx_user_id_studygoal", user_id),
        Index("idx_goal_type", goal_type),
        Index("idx_is_completed_studygoal", is_completed),
        Index("idx_deadline", deadline),
    )


# ------------------------------
# 媒体资源模型
# ------------------------------

class VideoResource(Base):
    """视频资源表"""
    __tablename__ = "video_resource"
    
    video_id = Column(Integer, primary_key=True, autoincrement=True, comment="视频ID")
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
        Index("idx_question_id_videoresource", question_id),
        Index("idx_status_videoresource", status),
    )

class FileResource(Base):
    """文件资源表"""
    __tablename__ = "file_resource"
    
    file_id = Column(Integer, primary_key=True, autoincrement=True, comment="文件ID")
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
    
    config_id = Column(Integer, primary_key=True, autoincrement=True, comment="配置ID")
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
    
    log_id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="操作人ID")
    user_name = Column(String(100), comment="操作人姓名")
    user_role = Column(String(50), comment="操作人角色")
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
        Index("idx_user_id_sysoperationlog", user_id),
        Index("idx_operation_time", operation_time),
    )

# ------------------------------
# 试卷标签模型（新增）
# ------------------------------

class ExamPaperTag(Base):
    """试卷标签表"""
    __tablename__ = "exam_paper_tag"
    
    tag_id = Column(Integer, primary_key=True, autoincrement=True, comment="标签ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    exam_year = Column(Integer, comment="考试年份")
    exam_province = Column(String(50), comment="考试省份")
    exam_type = Column(String(50), comment="考试类型（联考/省考/国考）")
    subject_category = Column(Enum("行测", "申论", "公专", "其他"), comment="科目大类")
    is_complete = Column(Integer, default=1, comment="是否完整试卷")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    paper = relationship("ExamPaper")
    
    __table_args__ = (
        Index("idx_paper_id_exampapertag", paper_id),
        Index("idx_exam_year", exam_year),
        Index("idx_subject_category", subject_category),
    )

# ------------------------------
# 题目详细分类模型（新增）
# ------------------------------

class QuestionDetailCategory(Base):
    """题目详细分类表"""
    __tablename__ = "question_detail_category"
    
    category_id = Column(Integer, primary_key=True, autoincrement=True, comment="分类ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    
    # 行测细分类
    # 注：科学推理 为实测补充（4 套卷以「科学推理」替代「数量关系」）。
    # 本处必须与 QuestionBank.xingce_subcategory 保持一致 —— 前序 README 根因表
    # 第 1 条即「两处事实来源分裂导致 122 道题型错位」，故两处同步修改。
    xingce_subcategory = Column(Enum(
        "政治理论", "常识判断", "言语理解与表达", "数量关系",
        "判断推理", "资料分析", "知觉速度与准确性", "科学推理",
        "常识", "速度与知觉训练", "语言理解与表达", "无"
    ), default="无", comment="行测细分类型")

    # 申论细分类
    shenlun_subcategory = Column(Enum(
        "归纳概括", "综合分析", "提出对策", "应用文写作", "议论文写作", "无"
    ), default="无", comment="申论细分类型")

    # 公专细分类
    gongzhuan_subcategory = Column(Enum(
        "职业素养", "基础知识", "基本警务能力",
        "法律知识", "业务能力", "无"
    ), default="无", comment="公专细分类型")
    
    # 其他分类
    other_subcategory = Column(String(100), default="无", comment="其他细分类型")
    
    # 题型细分
    question_type_detail = Column(Enum(
        "单选题", "多选题", "不定项", "选择题",
        "写作题", "简答题", "案例分析题", "论述题", "无"
    ), default="选择题", comment="题型详细分类")
    
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    question = relationship("QuestionBank")
    
    __table_args__ = (
        UniqueConstraint("question_id", name="uk_question_category"),
        Index("idx_question_id_questiondetailcategory", question_id),
        Index("idx_xingce_sub", xingce_subcategory),
        Index("idx_shenlun_sub", shenlun_subcategory),
        Index("idx_gongzhuan_sub", gongzhuan_subcategory),
    )

# ------------------------------
# 题目图片关联模型（新增）
# ------------------------------

class QuestionImage(Base):
    """题目图片关联表"""
    __tablename__ = "question_image"
    
    image_id = Column(Integer, primary_key=True, autoincrement=True, comment="图片ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    image_path = Column(String(500), nullable=False, comment="图片存储路径")
    image_type = Column(Enum("题干图", "选项图", "解析图", "其他"), default="题干图", comment="图片类型")
    ocr_text = Column(Text, comment="OCR识别文本")
    image_order = Column(Integer, default=0, comment="图片顺序")
    file_size = Column(BigInteger, comment="文件大小")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    question = relationship("QuestionBank")
    
    __table_args__ = (
        Index("idx_question_id_questionimage", question_id),
        Index("idx_image_type", image_type),
    )

# ------------------------------
# 题目导入记录模型（新增）
# ------------------------------

class QuestionImportRecord(Base):
    """题目导入记录表"""
    __tablename__ = "question_import_record"
    
    import_id = Column(Integer, primary_key=True, autoincrement=True, comment="导入记录ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), comment="关联试卷ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="导入人ID")
    original_filename = Column(String(200), comment="原始文件名")
    file_type = Column(Enum("WORD", "PDF", "EXCEL", "JSON"), comment="文件类型")
    total_questions = Column(Integer, default=0, comment="识别题目总数")
    success_count = Column(Integer, default=0, comment="成功入库数")
    failed_count = Column(Integer, default=0, comment="失败数")
    duplicate_count = Column(Integer, default=0, comment="重复题目数")
    import_status = Column(Enum("PARSING", "PREVIEW", "CONFIRMED", "COMPLETED", "FAILED"), default="PARSING", comment="导入状态")
    preview_data = Column(JSON, comment="预览数据")
    error_messages = Column(JSON, comment="错误信息")
    import_time = Column(DateTime, default=datetime.now, comment="导入时间")
    complete_time = Column(DateTime, comment="完成时间")
    # 2026-09-29 新增：异步解析真实进度（由 _process_import_async 写、状态接口读）
    progress_percent = Column(Integer, default=0, comment="解析进度 0-100")
    current_phase = Column(String(50), comment="当前阶段标识")
    
    paper = relationship("ExamPaper")
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_id_questionimportrecord", user_id),
        Index("idx_paper_id_questionimportrecord", paper_id),
        Index("idx_import_status", import_status),
        Index("idx_import_time", import_time),
    )

# ------------------------------
# 班级模型（新增）
# ------------------------------

class Banji(Base):
    """班级表"""
    __tablename__ = "banji"
    
    class_id = Column(Integer, primary_key=True, autoincrement=True, comment="班级ID")
    class_name = Column(String(100), nullable=False, comment="班级名称")
    school = Column(String(100), comment="学校名称")
    teacher_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="班主任ID")
    student_count = Column(Integer, default=0, comment="学生数量")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    status = Column(Integer, default=1, comment="状态")
    
    teacher = relationship("SysUser", foreign_keys=[teacher_id])
    
    __table_args__ = (
        Index("idx_teacher_id_banji", teacher_id),
        Index("idx_school", school),
    )

# ------------------------------
# 论坛点赞模型（新增）
# ------------------------------

class ForumLike(Base):
    """论坛点赞表"""
    __tablename__ = "forum_like"
    
    like_id = Column(Integer, primary_key=True, autoincrement=True, comment="点赞ID")
    post_id = Column(BigInteger, ForeignKey("forum_post.post_id"), comment="帖子ID")
    comment_id = Column(BigInteger, ForeignKey("forum_comment.comment_id"), comment="评论ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    reaction_code = Column(String(16), default="like", comment="表情反应码: like/love/haha/wow/sad/angry")
    create_time = Column(DateTime, default=datetime.now, comment="点赞时间")
    
    post = relationship("ForumPost")
    comment = relationship("ForumComment")
    user = relationship("SysUser")
    
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uk_post_user_like"),
        UniqueConstraint("comment_id", "user_id", name="uk_comment_user_like"),
        Index("idx_post_id_forumlike", post_id),
        Index("idx_comment_id_forumlike", comment_id),
        Index("idx_user_id_forumlike", user_id),
    )


class ForumFavorite(Base):
    """论坛收藏表（P3，2026-10-26）

    与 /api/collection（题目/新闻收藏）互不相干：本表只服务于论坛帖子收藏。
    一个用户对同一帖子只能收藏一次，取消即删除行。
    """
    __tablename__ = "forum_favorite"

    favorite_id = Column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    post_id = Column(BigInteger, ForeignKey("forum_post.post_id"), nullable=False, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    create_time = Column(DateTime, default=datetime.now, comment="收藏时间")

    post = relationship("ForumPost")
    user = relationship("SysUser")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uk_post_user_favorite"),
        Index("idx_user_id_forumfavorite", user_id),
        Index("idx_post_id_forumfavorite", post_id),
    )


class ForumSticker(Base):
    """论坛表情包（系统内置 + 用户自定义）"""
    __tablename__ = "forum_sticker"

    sticker_id = Column(Integer, primary_key=True, autoincrement=True, comment="表情包ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="上传者ID; NULL=系统内置")
    name = Column(String(50), nullable=False, comment="表情包名称")
    url = Column(String(500), nullable=False, comment="图片URL")
    category = Column(String(16), default="sticker", comment="分类: emoji/sticker")
    sort_order = Column(Integer, default=0, comment="排序")
    enabled = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_forum_sticker_user", user_id),
        Index("idx_forum_sticker_enabled", enabled),
    )

# ------------------------------
# 全校错题统计模型（新增）
# ------------------------------

class WrongQuestionClass(Base):
    """全校/班级错题统计表"""
    __tablename__ = "wrong_question_class"
    
    stat_id = Column(Integer, primary_key=True, autoincrement=True, comment="统计ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    class_id = Column(BigInteger, ForeignKey("banji.class_id"), comment="班级ID")
    wrong_count = Column(Integer, default=0, comment="错误次数")
    total_attempts = Column(Integer, default=0, comment="总答题次数")
    error_rate = Column(DECIMAL(5, 2), default=0.00, comment="错误率")
    common_mistake = Column(Text, comment="常见错误")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    question = relationship("QuestionBank")
    banji = relationship("Banji")
    
    __table_args__ = (
        Index("idx_question_id_wrongquestionclass", question_id),
        Index("idx_class_id", class_id),
    )

# ------------------------------
# 历年试卷模型（新增）
# ------------------------------

class YearPaper(Base):
    """历年试卷表"""
    __tablename__ = "year_paper"
    
    year_paper_id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    record_id = Column(BigInteger, ForeignKey("exam_record.record_id"), nullable=False, unique=True, comment="考试记录ID")
    year = Column(Integer, comment="年份")
    paper_title = Column(String(200), comment="试卷标题")
    subject_category = Column(String(50), comment="科目大类")
    province = Column(String(50), comment="省份")
    exam_type = Column(String(50), comment="考试类型")
    total_score = Column(DECIMAL(10, 2), comment="试卷总分")
    total_questions = Column(Integer, comment="题目总数")
    answer_time = Column(Integer, comment="答题用时")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    
    record = relationship("ExamRecord", uselist=False)
    
    __table_args__ = (
        Index("idx_year", year),
        Index("idx_subject_category_yearpaper", subject_category),
    )

# ------------------------------
# 招聘信息模型（新增）
# ------------------------------

class RecruitmentInfo(Base):
    """招聘信息表"""
    __tablename__ = "recruitment_info"

    recruitment_id = Column(Integer, primary_key=True, autoincrement=True, comment="招聘ID")
    title = Column(String(200), nullable=False, comment="招聘标题")
    organization = Column(String(200), comment="发布单位")
    category = Column(String(50), comment="招聘分类")
    region = Column(String(100), comment="地区")
    content = Column(Text, comment="招聘内容")
    content_html = Column(Text, comment="过滤后的HTML正文")
    requirements = Column(Text, comment="要求")
    images = Column(JSON, comment="图片列表")
    registration_start = Column(String(50), comment="报名开始时间")
    registration_end = Column(String(50), comment="报名截止时间")
    deadline = Column(String(20), comment="截止日期(旧字段)")
    exam_format = Column(String(50), comment="考试方式")
    contact_info = Column(String(200), comment="联系方式")
    tag = Column(String(50), comment="标签")
    tag_color = Column(String(20), comment="标签颜色")
    view_count = Column(Integer, default=0, comment="浏览量")
    url = Column(String(500), comment="原始链接")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="入库时间(爬取时刻,非内容发布时间)")
    # 源站真实发布日期。爬虫早已抓到该值但此前从未落库(表无此列)，
    # 导致接口只能按 create_time 排序；而 create_time 是插入时间戳(同批次跨度仅微秒级)，
    # 叠加爬虫按页码 1→5 插入，最终把最旧内容排在最前——即用户所见的"内容永不更新"。
    publish_date = Column(String(20), comment="源站发布日期(YYYY-MM-DD)")

    __table_args__ = (
        Index("idx_category", category),
        Index("idx_region", region),
        Index("idx_create_time_recruitment", create_time),
        Index("idx_publish_date_recruitment", publish_date),
    )

# ------------------------------
# 考试日历模型（新增）
# ------------------------------

class ExamCalendar(Base):
    """考试日历表"""
    __tablename__ = "exam_calendar"

    event_id = Column(Integer, primary_key=True, autoincrement=True, comment="事件ID")
    title = Column(String(200), nullable=False, comment="考试名称")
    exam_date = Column(DateTime, nullable=False, comment="考试日期")
    month = Column(String(2), comment="考试月份")
    day = Column(String(2), comment="考试日")
    province = Column(String(50), comment="省份")
    exam_type = Column(String(50), comment="考试类型")
    exam_format = Column(String(50), comment="考试形式: 笔试/面试/笔试+面试")
    description = Column(Text, comment="考试描述")
    registration_start = Column(DateTime, comment="报名开始时间")
    registration_end = Column(DateTime, comment="报名截止时间")
    url = Column(String(500), comment="原始链接")
    content_html = Column(Text, comment="考试详情HTML")
    recruitment_count = Column(String(20), comment="招聘人数")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_exam_date", exam_date),
        Index("idx_province_examcalendar", province),
    )

# ------------------------------
# 备考资料模型 v2.2（重建：subject 三科 / type 四类内容）
# ------------------------------

class StudyMaterial(Base):
    """备考资料表"""
    __tablename__ = "study_material"

    material_id = Column(Integer, primary_key=True, autoincrement=True, comment="资料ID")
    subject = Column(String(20), nullable=False, comment="科目: xingce/shenlun/gongzhuan")
    type = Column(String(20), nullable=False, comment="类型: video_intro/video_advanced/article/card")
    category = Column(String(50), comment="分类标签")
    title = Column(String(200), nullable=False, comment="标题")
    summary = Column(String(500), comment="摘要")
    content = Column(Text, comment="文章HTML(bleach消毒后)；卡片时为背面详述")
    card_front = Column(String(200), comment="卡片正面")
    card_back = Column(Text, comment="卡片背面")
    cover_image = Column(String(500), comment="封面图URL")
    video_id = Column(Integer, comment="关联video_resource.video_id")
    duration = Column(Integer, default=0, comment="视频时长(秒)")
    read_time = Column(Integer, default=0, comment="阅读时长(分钟)")
    difficulty = Column(Integer, default=1, comment="难度1-3")
    badge = Column(String(20), comment="徽章: 热门/精华/重要/NEW")
    sort_order = Column(Integer, default=0, comment="排序权重")
    status = Column(Integer, default=1, comment="0下架/1上架")
    view_count = Column(Integer, default=0, comment="浏览量")
    study_count = Column(Integer, default=0, comment="完成人数")
    creator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="创建人")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    content_hash = Column(String(64), comment="内容MD5哈希(去重用)")

    __table_args__ = (
        Index("idx_subject_type", subject, type),
        Index("idx_status_sort", status, sort_order),
    )


class UserMaterialProgress(Base):
    """备考资料学习进度表（每用户每资料一行，UNIQUE 幂等 UPSERT）"""
    __tablename__ = "user_material_progress"

    progress_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("study_material.material_id"), nullable=False)
    status = Column(SmallInteger, default=0, comment="0未学/1学习中/2已完成")
    progress_percent = Column(Float, default=0, comment="0-100")
    is_favorite = Column(Boolean, default=False)
    completed_at = Column(DateTime, comment="完成时间")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("user_id", "material_id", name="uq_progress_user_material"),
        Index("idx_progress_user", user_id),
    )


class MaterialImportRecord(Base):
    """备考资料导入记录（内容工厂流水追溯）"""
    __tablename__ = "material_import_record"

    import_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_type = Column(String(10), comment="docx/xlsx/pdf/image")
    file_size = Column(BigInteger, comment="字节")
    parse_mode = Column(String(20), comment="sync / async(mineru)")
    parse_status = Column(String(20), default="pending", comment="pending/processing/success/failed/consumed")
    parse_result = Column(Text, comment="JSON结构化产物快照")
    error_message = Column(String(1000), comment="失败原因")
    uploader_id = Column(BigInteger, ForeignKey("sys_user.user_id"))
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        # 索引名必须数据库全局唯一：原先与 QuestionImportRecord 的索引同名
        # （均为 idx_import_status），SQLite 建表时第二张表即抛
        # "index idx_import_status already exists"，导致 52 个测试 error，
        # 且 migrate_study_materials.py 的 IF NOT EXISTS 静默跳过。
        Index("idx_material_parse_status", parse_status),
    )

# ------------------------------
# 新闻资讯模型（新增）
# ------------------------------

class NewsArticle(Base):
    """新闻资讯表"""
    __tablename__ = "news_article"
    
    news_id = Column(Integer, primary_key=True, autoincrement=True, comment="新闻ID")
    title = Column(String(500), nullable=False, comment="新闻标题")
    url = Column(String(1000), nullable=False, comment="原始链接")
    source = Column(String(50), nullable=False, comment="来源: cpd/people")
    category = Column(String(50), comment="分类: 理论/党史/公安报")
    publish_date = Column(DateTime, comment="发布日期")
    summary = Column(Text, comment="摘要")
    content = Column(Text, comment="文章正文")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="入库时间")
    
    __table_args__ = (
        UniqueConstraint("title", "source", name="uq_news_title_source"),
        Index("idx_source_news", source),
        Index("idx_publish_date_news", publish_date),
    )

class NewsRead(Base):
    """新闻阅读记录表（P2-32）

    按 (user_id, news_id) 唯一。同一用户同一篇新闻只留一条，
    是 ``news.read``（E7）事件「同篇不重复发」的持久化依据，
    同时为前端提供后端权威的已读状态（不落 localStorage）。
    """
    __tablename__ = "news_read"

    read_id = Column(Integer, primary_key=True, autoincrement=True, comment="阅读记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    news_id = Column(BigInteger, ForeignKey("news_article.news_id"), nullable=False, comment="新闻ID")
    create_time = Column(DateTime, default=datetime.now, comment="首次阅读时间")

    user = relationship("SysUser")
    news = relationship("NewsArticle")

    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="uq_news_read_user_news"),
        Index("idx_user_id_newsread", user_id),
        Index("idx_news_id_newsread", news_id),
    )


# ------------------------------
# 收藏/笔记/标记模型（新增）
# ------------------------------

class FavoriteQuestion(Base):
    """题目收藏表"""
    __tablename__ = "favorite_question"

    fav_id = Column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    create_time = Column(DateTime, default=datetime.now, comment="收藏时间")

    user = relationship("SysUser")
    question = relationship("QuestionBank")

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question_fav"),
        Index("idx_user_id_fav", user_id),
        Index("idx_question_id_fav", question_id),
    )


class QuestionNote(Base):
    """题目笔记表"""
    __tablename__ = "question_note"

    note_id = Column(Integer, primary_key=True, autoincrement=True, comment="笔记ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    note_text = Column(Text, nullable=False, comment="笔记内容")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    user = relationship("SysUser")
    question = relationship("QuestionBank")

    __table_args__ = (
        Index("idx_user_id_note", user_id),
        Index("idx_question_id_note", question_id),
    )


class QuestionMarker(Base):
    """题目标记表（重要/疑难/易错等）"""
    __tablename__ = "question_marker"

    marker_id = Column(Integer, primary_key=True, autoincrement=True, comment="标记ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    marker_type = Column(String(20), nullable=False, comment="标记类型: difficult/important/confusing/tricky")
    marker_label = Column(String(50), comment="标记标签（自定义）")
    create_time = Column(DateTime, default=datetime.now, comment="标记时间")

    user = relationship("SysUser")
    question = relationship("QuestionBank")

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question_marker"),
        Index("idx_user_id_marker", user_id),
        Index("idx_question_id_marker", question_id),
    )

# ============================================================
# 三端分离架构新增模型
# ============================================================

class School(Base):
    """学校/机构表 — 支持多校区管理"""
    __tablename__ = "school"

    school_id = Column(Integer, primary_key=True, autoincrement=True, comment="学校ID")
    school_name = Column(String(100), nullable=False, comment="学校名称")
    school_code = Column(String(50), unique=True, comment="学校代码")
    region = Column(String(100), comment="所在地区")
    contact = Column(String(50), comment="联系人电话")
    address = Column(String(200), comment="详细地址")
    status = Column(Integer, default=1, comment="状态 1正常/0禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_school_code", school_code),
        Index("idx_school_region", region),
        Index("idx_school_status", status),
    )


class SysAnnouncement(Base):
    """系统公告表 — 管理员发布、三端可见"""
    __tablename__ = "sys_announcement"

    announcement_id = Column(Integer, primary_key=True, autoincrement=True, comment="公告ID")
    title = Column(String(200), nullable=False, comment="公告标题")
    content = Column(Text, nullable=False, comment="公告内容(支持HTML)")
    level = Column(Enum("info", "warning", "urgent"), default="info", comment="公告级别")
    target_role = Column(String(100), default="all", comment="目标角色: all/student/teacher/admin, 逗号分隔")
    publisher_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="发布人ID")
    is_pinned = Column(Integer, default=0, comment="是否置顶")
    view_count = Column(Integer, default=0, comment="浏览次数")
    publish_time = Column(DateTime, default=datetime.now, comment="发布时间")
    expire_time = Column(DateTime, comment="过期时间(空=永不过期)")
    status = Column(Integer, default=1, comment="状态 1正常/0删除")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    publisher = relationship("SysUser")

    __table_args__ = (
        Index("idx_publish_time", publish_time),
        Index("idx_target_role", target_role),
        Index("idx_level_sysannouncement", level),
        Index("idx_status_sysannouncement", status),
    )


class SysBackupRecord(Base):
    """数据备份记录表 — 管理员端数据备份与恢复"""
    __tablename__ = "sys_backup_record"

    backup_id = Column(Integer, primary_key=True, autoincrement=True, comment="备份ID")
    backup_type = Column(Enum("full", "incremental"), default="full", comment="备份类型")
    backup_name = Column(String(200), comment="备份名称")
    file_path = Column(String(500), nullable=False, comment="备份文件路径")
    file_size = Column(BigInteger, default=0, comment="文件大小(字节)")
    table_count = Column(Integer, default=0, comment="备份表数量")
    record_count = Column(Integer, default=0, comment="备份记录数")
    status = Column(Enum("running", "completed", "failed"), default="running", comment="备份状态")
    error_message = Column(Text, comment="错误信息")
    operator_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="操作人ID")
    start_time = Column(DateTime, default=datetime.now, comment="开始时间")
    end_time = Column(DateTime, comment="完成时间")

    operator = relationship("SysUser")

    __table_args__ = (
        Index("idx_backup_status", status),
        Index("idx_backup_start_time", start_time),
        Index("idx_backup_type", backup_type),
    )


class SysVersion(Base):
    """系统版本管理表 — 版本更新与功能开发"""
    __tablename__ = "sys_version"

    version_id = Column(Integer, primary_key=True, autoincrement=True, comment="版本ID")
    version_code = Column(String(20), unique=True, nullable=False, comment="版本号 如 2.1.0")
    version_name = Column(String(100), comment="版本名称")
    release_notes = Column(Text, comment="更新日志(支持Markdown)")
    download_url = Column(String(500), comment="下载地址")
    file_size = Column(BigInteger, comment="安装包大小(字节)")
    force_update = Column(Integer, default=0, comment="是否强制更新 0否/1是")
    platform = Column(String(50), default="all", comment="平台: web/ios/android/all")
    publish_time = Column(DateTime, default=datetime.now, comment="发布时间")
    publisher_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="发布人ID")
    status = Column(Integer, default=1, comment="状态 1正常/0废弃")

    publisher = relationship("SysUser")

    __table_args__ = (
        Index("idx_version_code", version_code),
        Index("idx_publish_time_sysversion", publish_time),
        Index("idx_platform", platform),
    )


class SysDictType(Base):
    """数据字典类型表"""
    __tablename__ = "sys_dict_type"

    dict_type_id = Column(Integer, primary_key=True, autoincrement=True, comment="字典类型ID")
    dict_name = Column(String(100), nullable=False, comment="字典名称")
    dict_code = Column(String(50), unique=True, nullable=False, comment="字典编码")
    description = Column(String(200), comment="字典描述")
    status = Column(Integer, default=1, comment="状态")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_dict_code", dict_code),
    )


class SysDictData(Base):
    """数据字典数据表"""
    __tablename__ = "sys_dict_data"

    dict_data_id = Column(Integer, primary_key=True, autoincrement=True, comment="字典数据ID")
    dict_type_id = Column(Integer, ForeignKey("sys_dict_type.dict_type_id"), nullable=False, comment="字典类型ID")
    label = Column(String(100), nullable=False, comment="字典标签(显示)")
    value = Column(String(100), nullable=False, comment="字典值(存储)")
    css_class = Column(String(50), comment="样式类名(如标签颜色)")
    sort_order = Column(Integer, default=1, comment="排序")
    is_default = Column(Integer, default=0, comment="是否默认值")
    status = Column(Integer, default=1, comment="状态")
    remark = Column(String(200), comment="备注")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")

    dict_type = relationship("SysDictType")

    __table_args__ = (
        UniqueConstraint("dict_type_id", "value", name="uk_dict_type_value"),
        Index("idx_dict_type_id", dict_type_id),
        Index("idx_dict_sort_order", sort_order),
    )


class PaperApprovalWorkflow(Base):
    """试卷审批工作流表 — 增强版，支持多级审批"""
    __tablename__ = "paper_approval_workflow"

    workflow_id = Column(Integer, primary_key=True, autoincrement=True, comment="工作流ID")
    paper_id = Column(BigInteger, ForeignKey("exam_paper.paper_id"), nullable=False, comment="试卷ID")
    submitter_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="提交人ID(教师)")
    approver_id = Column(BigInteger, ForeignKey("sys_user.user_id"), comment="审批人ID(教研组长/管理员)")
    step = Column(Integer, default=1, comment="审批步骤 1初审/2复审")
    status = Column(Enum("pending", "approved", "rejected"), default="pending", comment="审批状态")
    opinion = Column(Text, comment="审批意见")
    submit_time = Column(DateTime, default=datetime.now, comment="提交时间")
    approve_time = Column(DateTime, comment="审批时间")

    paper = relationship("ExamPaper")
    submitter = relationship("SysUser", foreign_keys=[submitter_id])
    approver = relationship("SysUser", foreign_keys=[approver_id])

    __table_args__ = (
        Index("idx_workflow_paper_id", paper_id),
        Index("idx_workflow_submitter", submitter_id),
        Index("idx_workflow_approver", approver_id),
        Index("idx_workflow_status", status),
    )


# ------------------------------
# 新闻增强模型（图片/收藏/笔记）
# ------------------------------

class NewsImage(Base):
    """新闻图片关联表"""
    __tablename__ = "news_image"
    image_id = Column(Integer, primary_key=True, autoincrement=True)
    news_id = Column(BigInteger, ForeignKey("news_article.news_id"), nullable=False)
    image_path = Column(String(500), nullable=False)
    image_order = Column(Integer, default=0)
    create_time = Column(DateTime, default=datetime.now)
    news = relationship("NewsArticle")
    __table_args__ = (Index("idx_news_id_newsimage", news_id),)


class NewsFavorite(Base):
    """新闻收藏表"""
    __tablename__ = "news_favorite"
    fav_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False)
    news_id = Column(BigInteger, ForeignKey("news_article.news_id"), nullable=False)
    create_time = Column(DateTime, default=datetime.now)
    user = relationship("SysUser")
    news = relationship("NewsArticle")
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="uq_user_news_fav"),
        Index("idx_user_id_newsfav", user_id),
        Index("idx_news_id_newsfav", news_id),
    )


# ------------------------------
# 快速练习模块 — 子科目 & 题目-考点关联
# ------------------------------

class SubCategory(Base):
    """子科目表 — 科目下的二级分类（如行测→政治理论）"""
    __tablename__ = "sub_categories"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="子科目ID")
    subject_id = Column(Integer, ForeignKey("question_subject.subject_id"), nullable=False, comment="所属科目ID")
    name = Column(String(100), nullable=False, comment="子科目名称")
    description = Column(String(500), comment="子科目描述")
    sort_order = Column(Integer, default=1, comment="排序序号")
    status = Column(Integer, default=1, comment="状态 1正常/0禁用")

    subject = relationship("QuestionSubject")

    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_subject_subcategory_name"),
        Index("idx_sub_category_subject", subject_id),
        Index("idx_sub_category_sort", sort_order),
    )


class QuestionKnowledge(Base):
    """题目-考点关联表 — 多对多关系"""
    __tablename__ = "question_knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    question_id = Column(BigInteger, ForeignKey("question_bank.question_id"), nullable=False, comment="题目ID")
    knowledge_point_id = Column(BigInteger, ForeignKey("knowledge_point.point_id"), nullable=False, comment="考点ID")

    question = relationship("QuestionBank")
    knowledge_point = relationship("KnowledgePoint")

    __table_args__ = (
        UniqueConstraint("question_id", "knowledge_point_id", name="uq_question_knowledge"),
        Index("idx_qk_question", question_id),
        Index("idx_qk_knowledge", knowledge_point_id),
    )


class NewsNote(Base):
    """新闻笔记表（划线+想法）"""
    __tablename__ = "news_note"
    note_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False)
    news_id = Column(BigInteger, ForeignKey("news_article.news_id"), nullable=False)
    note_text = Column(Text, nullable=False, comment="想法内容")
    quote_text = Column(Text, comment="划线原文")
    quote_position = Column(Integer, comment="位置锚点")
    color = Column(String(10), default="#FFD700", comment="划线颜色")
    line_style = Column(String(20), default='wavy', comment="划线样式: wavy/straight/marker")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    user = relationship("SysUser")
    news = relationship("NewsArticle")
    __table_args__ = (
        Index("idx_user_id_newsnote", user_id),
        Index("idx_news_id_newsnote", news_id),
    )


# ------------------------------
# 申论金句模块
# ------------------------------

class EssayQuote(Base):
    """申论金句表"""
    __tablename__ = "essay_quote"
    quote_id = Column(Integer, primary_key=True, autoincrement=True, comment="金句ID")
    content = Column(Text, nullable=False, comment="金句内容")
    source = Column(String(200), comment="来源")
    category = Column(String(50), comment="分类: 哲理/治国/民生/法治/品德")
    author = Column(String(100), comment="作者")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    status = Column(Integer, default=1, comment="状态 1正常/0禁用")

    __table_args__ = (
        Index("idx_category_essayquote", category),
        Index("idx_status_essayquote", status),
    )


class QuoteFavorite(Base):
    """金句收藏表"""
    __tablename__ = "quote_favorite"
    fav_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False)
    quote_id = Column(Integer, ForeignKey("essay_quote.quote_id"), nullable=True)
    obsidian_source = Column(String(200), nullable=True, comment="Obsidian 金句来源标识（文件名）")
    create_time = Column(DateTime, default=datetime.now)

    user = relationship("SysUser")
    quote = relationship("EssayQuote")

    __table_args__ = (
        UniqueConstraint("user_id", "quote_id", name="uq_user_quote_fav"),
        UniqueConstraint("user_id", "obsidian_source", name="uq_user_obsidian_fav"),
        Index("idx_user_id_quotefavorite", user_id),
    )


# ------------------------------
# 操作审计日志模型 (新增)
# ------------------------------

class OperationLog(Base):
    """试卷/题目操作审计日志表"""
    __tablename__ = "operation_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="操作人ID")
    action = Column(String(50), nullable=False, comment="操作类型: delete_paper/update_paper/confirm_paper/batch_update_type/batch_add_explanation")
    target_type = Column(String(50), nullable=False, comment="目标类型: paper/question")
    target_id = Column(BigInteger, comment="目标ID")
    details = Column(Text, comment="操作详情(JSON)")
    ip_address = Column(String(45), comment="IP地址")
    user_agent = Column(String(500), comment="用户代理")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    
    user = relationship("SysUser")
    
    __table_args__ = (
        Index("idx_user_action_time", "user_id", "action", "created_at"),
        Index("idx_target", "target_type", "target_id"),
    )


class MaterialClassificationRule(Base):
    """资料分类规则表"""
    __tablename__ = "material_classification_rules"
    
    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(50), nullable=False, comment="format/content/keyword")
    rule_config = Column(JSON, comment="规则配置")
    priority = Column(Integer, default=0, comment="优先级")
    enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class MaterialDuplicateRecord(Base):
    """资料去重记录表"""
    __tablename__ = "material_duplicate_records"
    
    record_id = Column(Integer, primary_key=True, autoincrement=True)
    original_material_id = Column(Integer, ForeignKey("study_material.material_id"), comment="原始资料ID")
    duplicate_material_id = Column(Integer, ForeignKey("study_material.material_id"), comment="重复资料ID")
    similarity = Column(DECIMAL(5, 4), comment="相似度")
    duplicate_type = Column(String(20), comment="exact/fingerprint/semantic")
    status = Column(String(20), default="pending", comment="pending/confirmed/ignored")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# ------------------------------
# 学生端「我的」模块模型（成就/反馈）
# ------------------------------

class Achievement(Base):
    """成就目录表"""
    __tablename__ = "achievement"

    achievement_id = Column(Integer, primary_key=True, autoincrement=True, comment="成就ID")
    category = Column(String(32), nullable=False, comment="分类: 坚持/数量/正确率/错题/社交/综合/联考特色/隐藏/赛季限定")
    name = Column(String(50), nullable=False, comment="成就名称")
    icon = Column(String(16), default="", comment="图标(emoji)")
    condition_desc = Column(String(200), nullable=False, comment="获得条件描述")
    reward_coins = Column(Integer, default=0, comment="奖励金币")
    trigger_type = Column(String(32), nullable=False, comment="触发类型")
    condition_code = Column(String(32), nullable=False, comment="判定条件码")
    threshold = Column(Integer, default=0, comment="条件阈值")
    extra = Column(String(32), comment="附加参数")
    sort_order = Column(Integer, default=0, comment="排序")
    is_hidden = Column(Integer, default=0, comment="是否隐藏成就: 1=条件对学生隐藏(仅剪影)")
    style_params = Column(JSON, comment="徽章视觉参数JSON(shape/material/palette/icon等)")
    tier_times = Column(JSON, comment="五档升级阈值倍数数组如[1,2,4,8,16]; NULL=不升档")

    __table_args__ = (
        Index("idx_achievement_category", category),
        Index("idx_achievement_trigger", trigger_type),
    )


class UserAchievement(Base):
    """用户成就表（幂等核心：唯一约束）"""
    __tablename__ = "user_achievement"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    achievement_id = Column(Integer, ForeignKey("achievement.achievement_id"), nullable=False, comment="成就ID")
    obtained_at = Column(DateTime, default=datetime.now, comment="获得时间")
    tier = Column(Integer, default=1, comment="徽章档位: 1铜/2银/3金/4铂金/5钻石")

    user = relationship("SysUser")

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uk_user_achievement"),
        Index("idx_user_achievement_user", user_id),
    )


class BadgeNameBank(Base):
    """徽章名称库表（规则引擎/LLM 产出统一入库）"""
    __tablename__ = "badge_name_bank"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="名称ID")
    name = Column(String(50), nullable=False, comment="徽章名称(2-6字)")
    category = Column(String(32), comment="适用类别")
    prefix_word = Column(String(20), comment="前缀词")
    body_word = Column(String(30), comment="主体词")
    suffix_word = Column(String(10), comment="后缀词")
    score = Column(DECIMAL(8, 2), default=0, comment="音韵/契合度评分")
    source = Column(String(16), default="rule", comment="来源: rule/llm/manual")
    used = Column(Integer, default=0, comment="是否已被占用")
    style_seed = Column(String(32), comment="生成种子(可复现)")
    created_at = Column(DateTime, default=datetime.now, comment="入库时间")

    __table_args__ = (
        Index("idx_badge_name_name", name),
        Index("idx_badge_name_cat", category),
    )


class Task(Base):
    """任务目录表（每日/周常/赛季）"""
    __tablename__ = "badge_task"

    task_id = Column(Integer, primary_key=True, autoincrement=True, comment="任务ID")
    task_code = Column(String(50), unique=True, nullable=False, comment="任务代码")
    t_type = Column(String(16), nullable=False, comment="周期: daily/weekly/season")
    title = Column(String(100), nullable=False, comment="任务名称")
    description = Column(String(300), comment="任务描述")
    metric = Column(String(32), nullable=False, comment="进度指标码(calc)/事件码(event)")
    mode = Column(String(16), default="calc", comment="进度模式: calc=重算/event=事件累计")
    threshold = Column(Integer, default=1, comment="目标值")
    reward_coins = Column(Integer, default=0, comment="奖励金币")
    reward_growth = Column(Integer, default=0, comment="奖励成长值")
    sort_order = Column(Integer, default=0, comment="排序")
    enabled = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_badge_task_type", t_type),
    )


class UserTaskProgress(Base):
    """用户任务进度表（按周期幂等）"""
    __tablename__ = "user_task_progress"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    task_id = Column(Integer, ForeignKey("badge_task.task_id"), nullable=False, comment="任务ID")
    period_key = Column(String(20), nullable=False, comment="周期键: 如20260916/2026-W38/202609")
    current = Column(Integer, default=0, comment="当前进度")
    completed = Column(Integer, default=0, comment="是否已完成")
    claimed = Column(Integer, default=0, comment="是否已领取奖励")
    completed_at = Column(DateTime, comment="完成时间")
    claimed_at = Column(DateTime, comment="领取时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    user = relationship("SysUser")

    __table_args__ = (
        UniqueConstraint("user_id", "task_id", "period_key", name="uk_user_task_period"),
        Index("idx_user_task_user", user_id),
    )


class Title(Base):
    """称号目录表"""
    __tablename__ = "badge_title"

    title_id = Column(Integer, primary_key=True, autoincrement=True, comment="称号ID")
    title_code = Column(String(50), unique=True, nullable=False, comment="称号代码")
    name = Column(String(50), nullable=False, comment="称号名称")
    description = Column(String(200), comment="称号描述")
    unlock_level = Column(Integer, nullable=False, comment="解锁所需学习等级")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_badge_title_level", unlock_level),
    )


class UserTitle(Base):
    """用户称号表（已解锁 + 佩戴状态）"""
    __tablename__ = "user_title"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="用户ID")
    title_id = Column(Integer, ForeignKey("badge_title.title_id"), nullable=False, comment="称号ID")
    obtained_at = Column(DateTime, default=datetime.now, comment="解锁时间")
    equipped = Column(Integer, default=0, comment="是否佩戴: 1=佩戴")

    user = relationship("SysUser")

    __table_args__ = (
        UniqueConstraint("user_id", "title_id", name="uk_user_title"),
        Index("idx_user_title_user", user_id),
    )

class UserFeedback(Base):
    """用户意见反馈表"""
    __tablename__ = "user_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True, comment="反馈ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="提交人ID")
    category = Column(String(32), nullable=False, comment="分类: 功能异常/数据错误/界面问题/其他")
    content = Column(Text, nullable=False, comment="反馈内容")
    contact = Column(String(100), comment="联系方式(可选)")
    status = Column(String(20), default="pending", comment="状态: pending/claimed/replied/resolved/rejected/merged")
    reply = Column(Text, comment="管理员/教师回复（兼容旧字段）")
    reply_by = Column(BigInteger, comment="回复人ID")
    replied_at = Column(DateTime, comment="回复时间")
    created_at = Column(DateTime, default=datetime.now, comment="提交时间")

    # === 工单化扩展（P0） ===
    ticket_no = Column(String(24), unique=True, comment="工单号 FBYYYYMMDD-000001")
    feedback_type = Column(String(32), comment="类型: question_content/answer/analysis/function/other")
    question_id = Column(BigInteger, comment="关联题目ID")
    practice_record_id = Column(BigInteger, comment="关联练习记录ID")
    attachments = Column(JSON, comment="截图列表 JSON")
    priority = Column(String(10), default="normal", comment="优先级 low/normal/high")
    handler_id = Column(BigInteger, comment="处理人ID")
    claimed_at = Column(DateTime, comment="认领时间")
    first_response_at = Column(DateTime, comment="首次响应时间（SLA 24h）")
    resolved_at = Column(DateTime, comment="解决/驳回时间（SLA 72h）")
    source = Column(String(20), default="form", comment="来源 form/forum/practice")
    forum_post_id = Column(BigInteger, comment="来源论坛帖子ID")
    subject_id = Column(Integer, comment="科目ID（用于范围分配）")
    merged_into = Column(BigInteger, comment="合并到的主工单ID")

    user = relationship("SysUser")

    __table_args__ = (
        Index("idx_feedback_user", user_id),
        Index("idx_feedback_status", status),
        Index("idx_feedback_created", created_at),
        Index("idx_feedback_ticket", ticket_no),
        Index("idx_feedback_handler", handler_id),
        Index("idx_feedback_question", question_id),
    )


class FeedbackReply(Base):
    """反馈工单的多轮回复。"""
    __tablename__ = "feedback_reply"

    reply_id = Column(Integer, primary_key=True, autoincrement=True, comment="回复ID")
    feedback_id = Column(Integer, ForeignKey("user_feedback.feedback_id"), nullable=False, comment="工单ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="回复人ID")
    role = Column(String(20), comment="回复人角色 student/practice_admin/teacher/admin")
    content = Column(Text, nullable=False, comment="回复内容")
    attachments = Column(JSON, comment="附件 JSON")
    created_at = Column(DateTime, default=datetime.now, comment="回复时间")

    __table_args__ = (
        Index("idx_feedback_reply_feedback", feedback_id, created_at),
    )
class UserCapability(Base):
    """按用户授予的能力包（练习管理员等）。

    与角色权限分离：角色决定基础能力，能力包决定额外授权与范围。
    scope_type: global / subject / class；scope_id 对应科目或班级标识。
    """
    __tablename__ = "user_capability"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="被授权用户")
    capability_code = Column(String(32), nullable=False, comment="能力码: practice_admin_teacher/practice_admin_student")
    scope_type = Column(String(16), nullable=False, default="subject", comment="范围: global/subject/class")
    scope_id = Column(Integer, comment="科目ID（scope_type=subject 时使用）")
    scope_key = Column(String(64), comment="范围键（scope_type=class 时存班级名）")
    status = Column(String(16), nullable=False, default="active", comment="状态: active/revoked")
    granted_by = Column(BigInteger, comment="授权人ID")
    granted_at = Column(DateTime, default=datetime.now, comment="授权时间")
    revoked_at = Column(DateTime, comment="撤销时间")
    note = Column(String(255), comment="任命说明")

    user = relationship("SysUser", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "capability_code", "scope_type", "scope_id", name="uk_user_capability"),
        Index("idx_capability_user_status", user_id, status),
        Index("idx_capability_scope", capability_code, scope_type, scope_id),
    )


class ForumReport(Base):
    """论坛举报（帖子/评论/用户）。"""
    __tablename__ = "forum_report"

    report_id = Column(Integer, primary_key=True, autoincrement=True, comment="举报ID")
    reporter_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="举报人")
    target_type = Column(String(10), nullable=False, comment="目标类型: POST/COMMENT/USER")
    target_id = Column(BigInteger, nullable=False, comment="目标ID")
    reason_code = Column(String(20), nullable=False, comment="原因: spam/abuse/illegal/other")
    reason_text = Column(String(200), comment="补充说明")
    status = Column(String(16), nullable=False, default="PENDING", comment="PENDING/ACCEPTED/REJECTED")
    handled_by = Column(BigInteger, comment="处理人")
    handled_at = Column(DateTime, comment="处理时间")
    created_at = Column(DateTime, default=datetime.now, comment="举报时间")

    __table_args__ = (
        UniqueConstraint("reporter_id", "target_type", "target_id", name="uk_forum_report_once"),
        Index("idx_forum_report_status", status, created_at),
        Index("idx_forum_report_target", target_type, target_id),
    )


class ForumMention(Base):
    """论坛 @提及。"""
    __tablename__ = "forum_mention"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    post_id = Column(BigInteger, ForeignKey("forum_post.post_id"), comment="帖子ID")
    comment_id = Column(BigInteger, ForeignKey("forum_comment.comment_id"), comment="评论ID")
    mentioned_user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="被提及用户")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_forum_mention_user", mentioned_user_id, created_at),
    )


class UserNotification(Base):
    """统一站内信（学生/教师/管理员共用）。"""
    __tablename__ = "user_notification"

    notification_id = Column(Integer, primary_key=True, autoincrement=True, comment="通知ID")
    user_id = Column(BigInteger, ForeignKey("sys_user.user_id"), nullable=False, comment="接收人")
    type = Column(String(20), nullable=False, default="system", comment="feedback/forum/mention/system")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, comment="正文")
    link = Column(String(300), comment="前端路由")
    related_type = Column(String(20), comment="关联类型")
    related_id = Column(BigInteger, comment="关联ID")
    is_read = Column(Integer, default=0, comment="0未读/1已读")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_notification_user_read", user_id, is_read, created_at),
    )


class ForumModeration(Base):
    """论坛内容删除/复核记录。

    action: TEACHER_HIDE / ADMIN_DELETE / RESTORE
    status: PENDING / APPROVED / REJECTED / RESTORED
    """
    __tablename__ = "forum_moderation"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    target_type = Column(String(10), nullable=False, comment="POST/COMMENT")
    target_id = Column(BigInteger, nullable=False, comment="目标ID")
    action = Column(String(20), nullable=False, comment="TEACHER_HIDE/ADMIN_DELETE/RESTORE")
    reason = Column(String(200), comment="原因")
    actor_id = Column(BigInteger, comment="操作人")
    status = Column(String(16), nullable=False, default="PENDING", comment="PENDING/APPROVED/REJECTED/RESTORED")
    reviewed_by = Column(BigInteger, comment="复核人")
    reviewed_at = Column(DateTime, comment="复核时间")
    review_note = Column(String(200), comment="复核意见")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_moderation_status", status, created_at),
        Index("idx_moderation_target", target_type, target_id),
    )
