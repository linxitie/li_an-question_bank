"""
教师端 Pydantic 验证模型
"""
from typing import Optional, List, Any
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
