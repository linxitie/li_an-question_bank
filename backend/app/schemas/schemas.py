"""
数据验证模型定义
"""
from datetime import datetime
from typing import Optional, List, Any,Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum




#-------------------------------
#通用枚举类型
#-------------------------------
class QuestionTypeEnum(str,Enum):
    SINGLE_CHOICE = "单选题"
    MULTIPLE_CHOICE = "多选题"
    CASE_ANALYSIS = "情境题"
    ESSAY = "议论文"
    DISCUSSION = "论述题"
class DifficultyEnum(int,Enum):
    EASY = 1
    MEDIUM_EASY = 2
    MEDIUM = 3
    MEDIUM_HARD = 4
    HARD = 5

class AuditStatusEnum(int,Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2

class CollectionTypeEnum(str,Enum):
    WRONG = "错题"
    JINJU = "申论金句"
    ESSAY = "申论范文"


# ------------------------------
# 学习目标相关Schema
# ------------------------------

class GoalTypeEnum(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class StudyGoalCreate(BaseModel):
    """创建学习目标"""
    title: str = Field(..., min_length=1, max_length=200, description="目标标题")
    description: Optional[str] = Field(None, max_length=500, description="目标描述")
    goal_type: GoalTypeEnum = Field(GoalTypeEnum.DAILY, description="目标类型")
    target_count: int = Field(..., ge=1, description="目标数量")
    deadline: Optional[datetime] = Field(None, description="截止时间")
    priority: int = Field(1, ge=1, le=3, description="优先级 1低/2中/3高")


class StudyGoalUpdate(BaseModel):
    """更新学习目标"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    target_count: Optional[int] = Field(None, ge=1)
    current_count: Optional[int] = Field(None, ge=0)
    deadline: Optional[datetime] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    is_completed: Optional[bool] = None


class StudyGoalResponse(BaseModel):
    """学习目标响应"""
    model_config = ConfigDict(from_attributes=True)

    goal_id: int
    user_id: int
    title: str
    description: Optional[str]
    goal_type: str
    target_count: int
    current_count: int
    deadline: Optional[datetime]
    priority: int
    is_completed: bool
    completed_time: Optional[datetime]
    create_time: datetime
    update_time: datetime
    progress_percent: float = Field(0.0, description="完成百分比")


class StudyGoalListResponse(BaseModel):
    total: int
    items: List[StudyGoalResponse]


# ------------------------------
# 用户相关Schema
# ------------------------------

class UserBase(BaseModel):
    user_no: str = Field(..., min_length=1, max_length=50, description="用户编号")
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: str = Field(..., min_length=11, max_length=20, description="手机号")
    gender: Optional[str] = Field("未知", description="性别")
    user_type: str = Field(..., description="用户类型")
    department: Optional[str] = Field(None, description="学院/部门")
    class_name: Optional[str] = Field(None, description="班级")
    title: Optional[str] = Field(None, description="职称")
    specialty: Optional[str] = Field(None, description="专业领域")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128, description="密码")

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None)
    phone: Optional[str] = Field(None)
    avatar: Optional[str] = Field(None)
    gender: Optional[str] = Field(None)
    department: Optional[str] = Field(None)
    class_name: Optional[str] = Field(None)
    title: Optional[str] = Field(None)
    specialty: Optional[str] = Field(None)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)
    user_id: int
    user_no: str
    username: str
    email: Optional[str] = None
    phone: str = ''
    avatar: Optional[str] = None
    gender: str = ''
    user_type: str = 'student'
    department: Optional[str] = None
    class_name: Optional[str] = None
    school: str = ''
    title: Optional[str] = None
    specialty: Optional[str] = None
    role_level: int = 1
    status: int = 1
    total_coins: int = 0
    register_time: Optional[datetime] = None
    


# ------------------------------
# 认证相关Schema
# ------------------------------

class LoginRequest(BaseModel):
    user_no: str = Field(..., description="用户编号")
    password: str = Field(..., description="密码")

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[int] = None
    user_no: Optional[str] = None


# ------------------------------
# 科目与知识点Schema
# ------------------------------

class SubjectCreate(BaseModel):
    subject_name: str = Field(..., max_length=50, description="科目名称")
    subject_code: str = Field(..., max_length=20, description="科目代码")
    description: Optional[str] = Field(None, max_length=500)
    sort_order: int = Field(1, description="排序")


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    subject_name: str
    subject_code: str
    description: Optional[str]
    sort_order: int
    status: int


class KnowledgePointCreate(BaseModel):
    point_name: str = Field(..., max_length=200, description="知识点名称")
    subject_id: int = Field(..., description="所属科目ID")
    parent_id: int = Field(0, description="父知识点ID")
    level: int = Field(1, description="层级")
    description: Optional[str] = Field(None, max_length=500)
    sort_order: int = Field(1, description="排序")


class KnowledgePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    point_id: int
    point_name: str
    subject_id: int
    parent_id: int
    level: int
    description: Optional[str]
    sort_order: int


# ------------------------------
# 题库相关Schema
# ------------------------------
class QuestionOptionItem(BaseModel):
    """题目选项项"""
    key: str = Field(..., description="选项标识(A/B/C/D)")
    value: str = Field(..., description="选项内容")


class QuestionCreate(BaseModel):
    subject_id: int = Field(..., description="科目ID")
    type_id: int = Field(..., description="题型ID")
    question_content: str = Field(..., description="题目内容")
    options: Optional[List[QuestionOptionItem]] = Field(None, description="选项列表")
    answer: str = Field(..., description="正确答案")
    answer_analysis: Optional[str] = Field(None, description="答案解析")
    point_id: Optional[int] = Field(None, description="知识点ID")
    difficulty: DifficultyEnum = Field(DifficultyEnum.MEDIUM, description="难度等级")
    score: float = Field(0.0, ge=0, description="题目分值")
    year: Optional[int] = Field(None, description="考试年份")
    source: Optional[str] = Field(None, max_length=200, description="题目来源")
    tags: Optional[str] = Field(None, max_length=500, description="标签")
    video_url: Optional[str] = Field(None, max_length=500, description="讲解视频URL")


class QuestionUpdate(BaseModel):
    subject_id: Optional[int] = None
    type_id: Optional[int] = None
    question_content: Optional[str] = None
    options: Optional[List[QuestionOptionItem]] = None
    answer: Optional[str] = None
    answer_analysis: Optional[str] = None
    point_id: Optional[int] = None
    difficulty: Optional[DifficultyEnum] = None
    score: Optional[float] = None
    year: Optional[int] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    video_url: Optional[str] = None
    audit_status: Optional[AuditStatusEnum] = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int
    subject_id: int
    type_id: int
    question_content: str
    options: Optional[dict] = None
    answer: str
    answer_analysis: Optional[str] = None
    question_type_detail: Optional[str] = None
    point_id: Optional[int] = None
    difficulty: int = 3
    score: float = 1.0
    year: Optional[int] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    video_url: Optional[str] = None
    accuracy_rate: float = 0.0
    exam_frequency: int = 0
    creator_id: int = 0
    auditor_id: Optional[int] = None
    audit_status: int = 0
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    status: int = 1
    version: int = 1


class QuestionListQuery(BaseModel):
    """题目列表查询参数"""
    subject_id: Optional[int] = Field(None, description="科目ID")
    type_id: Optional[int] = Field(None, description="题型ID")
    point_id: Optional[int] = Field(None, description="知识点ID")
    difficulty: Optional[DifficultyEnum] = Field(None, description="难度等级")
    audit_status: Optional[AuditStatusEnum] = Field(None, description="审核状态")
    year: Optional[int] = Field(None, description="考试年份")
    keyword: Optional[str] = Field(None, max_length=100, description="搜索关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class QuestionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[QuestionResponse]


class BatchImportQuestionItem(QuestionCreate):
    """批量导入题目项"""
    pass


class BatchImportQuestionsRequest(BaseModel):
    """批量导入题目请求"""
    questions: List[BatchImportQuestionItem] = Field(..., min_items=1, max_items=100, description="题目列表")
    overwrite: bool = Field(False, description="是否覆盖已存在的题目")


class BatchImportResponse(BaseModel):
    success_count: int = Field(..., description="成功导入数量")
    failed_count: int = Field(..., description="失败数量")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误详情")



# ------------------------------
# 随机抽题与组卷Schema
# ------------------------------

class RandomQuestionRequest(BaseModel):
    """随机抽题请求"""
    subject_id: Optional[int] = Field(None, description="科目ID")
    type_id: Optional[int] = Field(None, description="题型ID")
    point_id: Optional[int] = Field(None, description="知识点ID")
    difficulty: Optional[DifficultyEnum] = Field(None, description="难度等级")
    count: int = Field(..., ge=1, le=100, description="抽取数量")
    exclude_question_ids: Optional[List[int]] = Field(None, description="排除的题目ID列表")

class RandomQuestionResponse(BaseModel):
    questions: List[QuestionResponse]
    total_available: int = Field(..., description="符合条件的题目总数")

class PaperQuestionConfig(BaseModel):
    """试卷题目配置"""
    type_id: int = Field(..., description="题型ID")
    count: int = Field(..., ge=1, description="该题型数量")
    difficulty: Optional[DifficultyEnum] = Field(None, description="难度要求")
    points: Optional[List[int]] = Field(None, description="指定知识点ID列表")

class AutoGeneratePaperRequest(BaseModel):
    """自动组卷请求"""
    paper_name: str = Field(..., max_length=200, description="试卷名称")
    subject_id: int = Field(..., description="科目ID")
    duration: int = Field(..., gt=0, description="考试时长(分钟)")
    total_score: float = Field(..., gt=0, description="试卷总分")
    difficulty: DifficultyEnum = Field(DifficultyEnum.MEDIUM, description="整体难度")
    question_configs: List[PaperQuestionConfig] = Field(..., description="各题型配置")
    shuffle_questions: bool = Field(False, description="是否打乱题目顺序")
    shuffle_options: bool = Field(True, description="是否打乱选项顺序")

class ManualGeneratePaperRequest(BaseModel):
    """手动组卷请求"""
    paper_name: str = Field(..., max_length=200, description="试卷名称")
    subject_id: int = Field(..., description="科目ID")
    duration: int = Field(..., gt=0, description="考试时长(分钟)")
    question_ids: List[int] = Field(..., min_items=1, description="题目ID列表")
    question_scores: Optional[Dict[int, float]] = Field(None, description="题目分值映射")

class GeneratePaperResponse(BaseModel):
    paper_id: int
    paper_code: str
    paper_name: str
    question_count: int
    total_score: float
    message: str

# ------------------------------
# 试卷相关Schema
# ------------------------------


class PaperBase(BaseModel):
    paper_name: str = Field(..., max_length=200, description="试卷名称")
    paper_code: str = Field(..., max_length=50, description="试卷编号")
    subject_id: int = Field(..., description="科目ID")
    composition_method: str = Field(..., description="组卷方式")
    duration: int = Field(..., gt=0, description="考试时长(分钟)")
    total_score: float = Field(..., gt=0, description="试卷总分")
    difficulty: int = Field(3, ge=1, le=5, description="难度等级")
    exam_type: str = Field("SIMULATION", description="考试类型")
    description: Optional[str] = Field(None, description="试卷描述")
    knowledge_range: Optional[str] = Field(None, description="知识点范围")
    question_ratio: Optional[dict] = Field(None, description="题型比例")
    shuffle_questions: bool = Field(False, description="是否打乱题目顺序")
    shuffle_options: bool = Field(True, description="是否打乱选项顺序")
    max_attempts: int = Field(1, description="最大答题次数")


class PaperCreate(PaperBase):
    pass


class PaperUpdate(BaseModel):
    paper_name: Optional[str] = None
    duration: Optional[int] = None
    total_score: Optional[float] = None
    difficulty: Optional[DifficultyEnum] = None
    description: Optional[str] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None


class PaperDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paper_id: int
    paper_name: str
    paper_code: str
    subject_id: int
    composition_method: str
    creator_id: int
    approver_id: Optional[int]
    duration: int
    total_score: float
    difficulty: int
    question_count: int
    exam_type: str
    paper_type: str
    exam_time: Optional[datetime]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    description: Optional[str]
    knowledge_range: Optional[str]
    question_ratio: Optional[dict]
    shuffle_questions: bool
    shuffle_options: bool
    anti_cheating: bool
    show_result_quickly: bool
    show_answer_quickly: bool
    max_attempts: int
    allow_late_submit: bool
    create_time: datetime
    update_time: datetime
    publish_time: Optional[datetime]
    questions: Optional[List[QuestionResponse]] = None


class PaperListQuery(BaseModel):
    subject_id: Optional[int] = None
    paper_type: Optional[str] = None
    exam_type: Optional[str] = None
    keyword: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


class PaperListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[PaperDetailResponse]
        

# ------------------------------
# LLM智能功能Schema
# ------------------------------

class SmartGradingRequest(BaseModel):
    """智能批改主观题请求"""
    question_id: int = Field(..., description="题目ID")
    student_answer: str = Field(..., min_length=1, max_length=10000, description="学生答案")
    reference_answer: Optional[str] = Field(None, description="参考答案")
    grading_criteria: Optional[str] = Field(None, description="评分标准")
    max_score: float = Field(..., gt=0, description="满分分值")

class SmartGradingResponse(BaseModel):
    score: float = Field(..., description="得分")
    feedback: str = Field(..., description="评语反馈")
    strengths: List[str] = Field(default_factory=list, description="优点")
    weaknesses: List[str] = Field(default_factory=list, description="不足")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    confidence: float = Field(..., ge=0, le=1, description="置信度")

class GenerateAnalysisRequest(BaseModel):
    """智能生成解析请求"""
    question_id: int = Field(..., description="题目ID")
    question_content: str = Field(..., description="题目内容")
    correct_answer: str = Field(..., description="正确答案")
    question_type: str = Field(..., description="题型")
    difficulty: Optional[DifficultyEnum] = None
    style: str = Field("detailed", description="解析风格: simple/detailed/step_by_step")

class GenerateAnalysisResponse(BaseModel):
    analysis: str = Field(..., description="生成的解析内容")
    key_points: List[str] = Field(default_factory=list, description="关键考点")
    common_mistakes: List[str] = Field(default_factory=list, description="常见错误")
    related_knowledge: List[str] = Field(default_factory=list, description="相关知识点")

class DailyGoldenSentenceResponse(BaseModel):
    """申论金句日更响应"""
    date: str = Field(..., description="日期")
    category: str = Field(..., description="分类")
    content: str = Field(..., description="金句内容")
    author: Optional[str] = Field(None, description="出处/作者")
    explanation: Optional[str] = Field(None, description="释义")
    application_scenarios: List[str] = Field(default_factory=list, description="适用场景")

class RecruitmentInfoItem(BaseModel):
    """招考信息项"""
    id: int
    title: str
    region: str
    department: str
    position: str
    requirements: str
    deadline: Optional[datetime]
    link: str
    publish_date: datetime

class RecruitmentInfoResponse(BaseModel):
    total: int
    items: List[RecruitmentInfoItem]

# ------------------------------
# 考试执行相关Schema
# ------------------------------

class ExamRecordBase(BaseModel):
    paper_id: int = Field(..., description="试卷ID")
    exam_type: str = Field(..., description="考试类型")

class ExamRecordCreate(ExamRecordBase):
    pass

class ExamRecordResponse(ExamRecordBase):
    record_id: int
    user_id: int
    start_time: datetime
    end_time: Optional[datetime]
    duration_used: Optional[int]
    total_score: float
    is_completed: bool
    is_scored: bool
    submit_time: Optional[datetime]
    create_time: datetime
    
    class Config:
        orm_mode = True

class AnswerDetailBase(BaseModel):
    question_id: int = Field(..., description="题目ID")
    student_answer: Optional[str] = Field(None, description="学生答案")

class AnswerDetailResponse(AnswerDetailBase):
    detail_id: int
    record_id: int
    is_correct: Optional[bool]
    time_spent: Optional[int]
    score_obtained: float
    create_time: datetime
    
    class Config:
        orm_mode = True

# ------------------------------
# 视频资源相关Schema
# ------------------------------

class VideoUploadResponse(BaseModel):
    video_id: int
    title: str
    storage_path: str
    thumbnail_path: Optional[str]
    duration: int
    file_size: int
    format: str
    resolution: Optional[str]
    status: str
    upload_time: datetime
    stream_url: str


# 视频资源响应（匹配 VideoResource 模型）
class VideoResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    video_id: int
    question_id: Optional[int]
    title: str
    original_filename: Optional[str]
    storage_path: str
    thumbnail_path: Optional[str]
    duration: int
    file_size: int
    format: Optional[str]
    resolution: Optional[str]
    bitrate: Optional[int]
    status: str
    create_time: datetime
    process_time: Optional[datetime]


class VideoListQuery(BaseModel):
    question_id: Optional[int] = None
    status: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=50)

class VideoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[VideoResourceResponse]

class VideoPermissionUpdate(BaseModel):
    """视频权限更新"""
    video_id: int = Field(..., description="视频ID")
    is_public: bool = Field(False, description="是否公开")
    allowed_user_types: Optional[List[str]] = Field(None, description="允许的用户类型")
    allowed_user_ids: Optional[List[int]] = Field(None, description="允许的用户ID列表")
    expire_time: Optional[datetime] = Field(None, description="过期时间")
# ------------------------------
# 大模型接口Schema
# ------------------------------

class LLMRequest(BaseModel):
    prompt: str = Field(..., description="提示词")
    model: Optional[str] = Field("gpt-3.5-turbo", description="模型名称")
    max_tokens: int = Field(2048, description="最大输出长度")
    temperature: float = Field(0.7, ge=0, le=1, description="温度系数")
    top_p: float = Field(1.0, ge=0, le=1, description="Top-P采样")

class LLMResponse(BaseModel):
    success: bool
    content: str
    model: str
    token_usage: Optional[dict]
    response_time: float

class SmartSearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    subject_id: Optional[int] = Field(None, description="科目ID")
    type_id: Optional[int] = Field(None, description="题型ID")
    difficulty: Optional[int] = Field(None, description="难度等级")
    limit: int = Field(10, description="返回数量")

class SmartSearchResponse(BaseModel):
    total: int
    results: List[dict]

# ------------------------------
# 通用响应Schema
# ------------------------------

class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    code: int = 400
    details: Optional[Any] = None

class PaginationResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[Any]

class MessageResponse(BaseModel):
    message: str