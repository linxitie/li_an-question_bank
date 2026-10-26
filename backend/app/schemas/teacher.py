"""
教师端 Pydantic 验证模型
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 工作台 ====================

class TeacherDashboardStats(BaseModel):
    """教师工作台统计"""
    total_questions: int = 0
    monthly_new_papers: int = 0
    today_practice_users: int = 0
    pending_approval_count: int = 0
    my_papers_count: int = 0
    total_imported_questions: int = 0


class PracticeTrend(BaseModel):
    """近7天每日练习人数趋势"""
    dates: List[str] = []      # 例 ["08-09",...,"08-15"]
    counts: List[int] = []     # 每日去重 user_id 数


class SubjectAccuracyItem(BaseModel):
    """三大科目总体正确率"""
    subject_id: int
    subject_name: str          # 行测/申论/公专
    total: int = 0             # 该科答题总数
    correct: int = 0           # 该科答对数
    accuracy: float = 0.0      # 正确率%，round(1)


class PendingApprovalItem(BaseModel):
    """待审批试卷项"""
    paper_id: int
    paper_name: str
    subject_name: str
    creator_name: str
    question_count: int
    total_score: float
    create_time: str


class RecentStudentActivity(BaseModel):
    """最新学生动态"""
    user_name: str
    action: str
    action_time: str
    detail: Optional[str] = None


class TeacherDashboardResponse(BaseModel):
    """教师工作台响应"""
    success: bool = True
    stats: TeacherDashboardStats
    pending_approvals: List[PendingApprovalItem] = []
    recent_activities: List[RecentStudentActivity] = []
    practice_trend: PracticeTrend = PracticeTrend()
    subject_accuracy: List[SubjectAccuracyItem] = []


# ==================== 题目管理 ====================

class TeacherQuestionQuery(BaseModel):
    """教师题目查询参数"""
    keyword: Optional[str] = None
    subject_id: Optional[int] = None
    type_id: Optional[int] = None
    difficulty: Optional[int] = None
    audit_status: Optional[int] = None
    xingce_subcategory: Optional[str] = None
    shenlun_subcategory: Optional[str] = None
    gongzhuan_subcategory: Optional[str] = None
    sort_by: str = Field("create_time", description="排序字段")
    sort_order: str = Field("desc", description="排序方向: asc/desc")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class TeacherQuestionUpdate(BaseModel):
    """教师编辑题目"""
    question_content: Optional[str] = None
    options: Optional[Any] = None
    answer: Optional[str] = None
    answer_analysis: Optional[str] = None
    difficulty: Optional[int] = None
    score: Optional[float] = None
    year: Optional[int] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    subject_id: Optional[int] = None
    type_id: Optional[int] = None
    point_id: Optional[int] = None
    group_id: Optional[int] = None
    shared_content: Optional[str] = None
    shared_content_images: Optional[str] = None


class TeacherQuestionCreate(BaseModel):
    """教师自设计题目"""
    subject_id: int
    type_name: str = Field(..., description="题型名称: 单选题/多选题/论述题/写作题")
    question_content: str = Field(..., min_length=1)
    options: Optional[Any] = None  # 选项列表 [{"key":"A","value":"..."}]
    answer: str = Field(..., description="正确答案")
    answer_analysis: Optional[str] = None
    difficulty: int = Field(3, ge=1, le=5)
    score: float = Field(5.0)
    year: Optional[int] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    point_id: Optional[int] = None
    group_id: Optional[int] = None
    shared_content: Optional[str] = None
    shared_content_images: Optional[str] = None


# ==================== 试卷管理 ====================

class TeacherPaperCreate(BaseModel):
    """教师创建试卷"""
    paper_name: str = Field(..., min_length=1, max_length=200)
    subject_id: int
    duration: int = Field(120, description="考试时长(分钟)")
    total_score: float = Field(100.0, description="试卷总分")
    difficulty: int = Field(3, ge=1, le=5)
    exam_type: str = Field("SIMULATION", description="考试类型")
    description: Optional[str] = None
    shuffle_questions: int = Field(0)
    shuffle_options: int = Field(1)
    max_attempts: int = Field(1)


class TeacherPaperUpdate(BaseModel):
    """教师编辑试卷"""
    paper_name: Optional[str] = None
    duration: Optional[int] = None
    total_score: Optional[float] = None
    difficulty: Optional[int] = None
    description: Optional[str] = None
    shuffle_questions: Optional[int] = None
    shuffle_options: Optional[int] = None
    max_attempts: Optional[int] = None
    anti_cheating: Optional[int] = None


class PaperQuestionItem(BaseModel):
    """试卷题目项"""
    question_id: int
    question_order: int
    question_score: float = 5.0


class PaperAddQuestions(BaseModel):
    """添加题目到试卷"""
    questions: List[PaperQuestionItem]


class AutoGenerateRequest(BaseModel):
    """AI 智能组卷请求"""
    paper_name: str = Field(..., description="试卷名称")
    subject_id: int = Field(..., description="科目ID")
    difficulty: int = Field(3, ge=1, le=5)
    total_score: float = Field(100.0)
    duration: int = Field(120)
    question_config: dict = Field(default_factory=dict, description="题型配置 如{'single_choice': 50, 'multi_choice': 20}")
    exam_type: str = Field("SIMULATION")


class SubmitApprovalRequest(BaseModel):
    """提交试卷审批"""
    paper_id: int
    approver_id: Optional[int] = None  # 指定审批人，为空则由管理员审批


class PublishPaperRequest(BaseModel):
    """发布试卷（双轨制）"""
    publish_target: str = Field(..., description="past_paper(历年试卷直发) / mock_exam(小模考审批)")


class PaperQuestionScoreUpdate(BaseModel):
    """调整试卷题目分值"""
    question_score: float = Field(..., gt=0, le=100, description="题目分值")


class PaperQuestionOrderUpdate(BaseModel):
    """调整试卷题目顺序"""
    question_ids: List[int] = Field(..., description="有序的题目ID列表")


class PaperQuestionContentUpdate(BaseModel):
    """P5：试卷内题目内容编辑（改题干/选项/答案/解析/题型）

    所有字段均为可选，只更新传入的字段；未传字段保持原值。
    校验放在 Pydantic 层，避免脏数据进入库：
      - content 长度上限 50000（与导入管线一致）
      - answer 归一化到 20 字符以内
      - type_name 只接受注册表里存在的题型名
    """
    question_content: Optional[str] = Field(None, max_length=50000, description="题干（含 HTML/img 标签）")
    options: Optional[List[Dict[str, Any]]] = Field(None, description="选项列表 [{key,value}]")
    answer: Optional[str] = Field(None, max_length=20, description="答案，如 A / ABC / 正确")
    answer_analysis: Optional[str] = Field(None, max_length=50000, description="答案解析")
    type_name: Optional[str] = Field(None, max_length=20, description="题型名")
    difficulty: Optional[int] = Field(None, ge=1, le=5, description="难度 1..5")
    score: Optional[float] = Field(None, gt=0, le=100, description="本卷分值")


# ==================== 成绩管理 ====================

class ScoreOverviewQuery(BaseModel):
    """成绩总览查询"""
    paper_id: Optional[int] = None
    class_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ScoreDistribution(BaseModel):
    """成绩分布"""
    score_ranges: List[str] = []  # ["0-60", "60-70", ...]
    student_counts: List[int] = []


class QuestionCorrectRate(BaseModel):
    """各题正确率"""
    question_id: int
    question_content: str  # 截取前50字
    correct_rate: float
    total_attempts: int


class StudentScoreItem(BaseModel):
    """学生成绩明细"""
    rank: int
    user_id: int
    user_no: str
    user_name: str
    class_name: Optional[str]
    total_score: float
    xingce_score: Optional[float]
    shenlun_score: Optional[float]
    police_score: Optional[float]
    duration_used: Optional[int]
    submit_time: Optional[str]


class ScoreOverviewResponse(BaseModel):
    """成绩总览响应"""
    success: bool = True
    distribution: ScoreDistribution
    question_rates: List[QuestionCorrectRate] = []
    student_scores: List[StudentScoreItem] = []
    total_students: int = 0
    avg_score: float = 0
    max_score: float = 0
    min_score: float = 0
    pass_rate: float = 0  # 及格率(>=60分)


# ==================== 个人设置 ====================

class TeacherProfileResponse(BaseModel):
    """教师个人信息响应"""
    success: bool = True
    user_id: int
    username: str
    user_no: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[str] = None
    role: Optional[str] = None
    class_count: int = 0
    student_count: int = 0
    paper_count: int = 0
    question_count: int = 0


class TeacherProfileUpdate(BaseModel):
    """教师个人信息更新"""
    username: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ==================== 班级管理 ====================

class ClassItem(BaseModel):
    """班级列表项"""
    class_id: int
    class_name: str
    student_count: int = 0
    avg_score: Optional[float] = None
    create_time: Optional[str] = None


class ClassDetailResponse(BaseModel):
    """班级详情响应"""
    success: bool = True
    class_id: int
    class_name: str
    student_count: int = 0
    avg_score: Optional[float] = None
    create_time: Optional[str] = None
    students: List[dict] = []


class ClassCreateRequest(BaseModel):
    """创建班级请求"""
    class_name: str = Field(..., min_length=1, max_length=100)


class ClassStudentAdd(BaseModel):
    """添加学生到班级"""
    user_ids: List[int] = Field(..., description="学生用户ID列表")


# ==================== 消息中心 ====================

class MessageItem(BaseModel):
    """消息列表项"""
    message_id: int
    message_type: str
    title: str
    content: Optional[str] = None
    is_read: bool = False
    related_id: Optional[int] = None
    created_at: Optional[str] = None


class MessageListResponse(BaseModel):
    """消息列表响应"""
    success: bool = True
    total: int = 0
    unread_count: int = 0
    items: List[MessageItem] = []


# ==================== 数据分析 ====================

class ClassTrendPoint(BaseModel):
    """班级趋势单点"""
    date: str          # 输出格式 "09-01"
    avg_score: float


class ClassTrendSeries(BaseModel):
    """班级成绩趋势序列"""
    class_id: Optional[int] = None
    class_name: str
    points: List[ClassTrendPoint] = []


class AnalyticsOverview(BaseModel):
    """学情总览"""
    total_students: int = 0
    total_exams: int = 0
    avg_score: float = 0
    pass_rate: float = 0
    score_trend: dict = {}  # {dates: [], scores: []}
    class_trend: List[ClassTrendSeries] = []  # 每班级一条趋势序列
    subject_comparison: List[dict] = []  # [{subject_name, avg_score, exam_count}]


class QuestionUsageItem(BaseModel):
    """题目使用频率"""
    question_id: int
    question_content: str
    usage_count: int = 0
    correct_rate: float = 0
    subject_name: Optional[str] = None


class KnowledgeMasteryItem(BaseModel):
    """知识点掌握度"""
    point_id: int
    point_name: str
    total_attempts: int = 0
    correct_count: int = 0
    mastery_rate: float = 0
    subject_name: Optional[str] = None
