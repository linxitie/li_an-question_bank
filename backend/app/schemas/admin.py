"""
管理员端 Pydantic 验证模型
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== 通用响应 ====================

class AdminBaseResponse(BaseModel):
    """管理员端基础响应"""
    success: bool = True
    message: str = ""


# ==================== 系统总览 ====================

class DashboardStats(BaseModel):
    """系统总览统计数据"""
    total_users: int = 0
    total_students: int = 0
    total_teachers: int = 0
    total_admins: int = 0
    total_questions: int = 0
    total_papers: int = 0
    today_active_users: int = 0
    today_practice_count: int = 0
    new_users_today: int = 0
    pending_approval_papers: int = 0


class WeeklyActiveTrend(BaseModel):
    """7天活跃趋势"""
    dates: List[str] = []
    active_counts: List[int] = []


class SubjectDistribution(BaseModel):
    """各科目题目占比（单项）"""
    subject: str = ""
    count: int = 0


class DashboardResponse(AdminBaseResponse):
    """系统总览响应"""
    stats: DashboardStats
    weekly_trend: WeeklyActiveTrend
    subject_distribution: List[SubjectDistribution] = []
    recent_logs: List[dict] = []


# ==================== 用户管理 ====================

class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=2, max_length=100, description="用户名")
    user_no: str = Field(..., description="用户编号/学号")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    user_type: str = Field("student", description="用户类型: student/teacher/admin")
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = "未知"
    department: Optional[str] = None
    class_name: Optional[str] = None
    school: Optional[str] = None
    role_level: int = Field(0, description="权限级别: 0学生/1教师/2管理员/3超级管理员")


class UserUpdate(BaseModel):
    """编辑用户"""
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    avatar: Optional[str] = None
    department: Optional[str] = None
    class_name: Optional[str] = None
    school: Optional[str] = None
    # role_level 不在资料编辑中接收：改角色走 PUT /users/{id}/role（仅超管）


class UserDisableRequest(BaseModel):
    """禁用/启用用户"""
    is_disabled: bool = True
    reason: Optional[str] = None


class UserResetPasswordRequest(BaseModel):
    """重置密码"""
    new_password: Optional[str] = Field(None, min_length=6, description="新密码，为空则自动生成")


class UserRoleUpdate(BaseModel):
    """改角色（仅超管；与资料编辑分离）"""
    user_type: str = Field(..., description="student/teacher/admin")
    role_level: int = Field(..., ge=0, le=3, description="0学生/1教师/2管理员/3超级管理员")
    reason: str = Field("", max_length=255, description="变更原因")


class UserDeleteRequest(BaseModel):
    """软删除用户"""
    reason: str = Field(..., min_length=2, max_length=255, description="删除原因")


class UserPurgeRequest(BaseModel):
    """匿名化注销（保留 user_id 墓碑）"""
    reason: str = Field(..., min_length=2, max_length=255, description="注销原因")
    confirm_username: str = Field(..., description="输入用户名确认，防止误操作")


class PermissionChangeItem(BaseModel):
    """单条权限覆盖变更"""
    permission_code: str = Field(..., max_length=64)
    effect: str = Field(..., description="grant/deny/inherit")
    expires_at: Optional[datetime] = Field(None, description="到期时间，空=永久")


class UserPermissionUpdate(BaseModel):
    """单用户权限变更"""
    reason: str = Field(..., min_length=2, max_length=255)
    changes: List[PermissionChangeItem] = Field(..., min_length=1, max_length=30)


class UserBatchTarget(BaseModel):
    """用户批量目标：显式 ids 或服务端重放筛选。"""
    mode: str = Field("ids", description="ids/filter")
    user_ids: List[int] = Field(default_factory=list, max_length=500)
    filter: dict = Field(default_factory=dict)
    expected_count: Optional[int] = Field(None, ge=1, le=500)


class UserBatchRequest(BaseModel):
    """用户批量操作。"""
    action: str = Field(..., description="disable/enable/delete/restore/update_profile/assign_role/reset_password")
    target: UserBatchTarget
    payload: dict = Field(default_factory=dict)
    expected_count: Optional[int] = Field(None, ge=1, le=500)


class PermissionBatchTarget(BaseModel):
    """批量目标：显式 ids 或服务端重放筛选条件。"""
    mode: str = Field("ids", description="ids/filter")
    user_ids: List[int] = Field(default_factory=list, max_length=500)
    filter: dict = Field(default_factory=dict)
    expected_count: Optional[int] = Field(None, ge=1, le=500)


class PermissionBatchRequest(BaseModel):
    """批量权限预览/应用。"""
    target: PermissionBatchTarget
    operation: str = Field(..., description="grant/deny/inherit")
    permissions: List[str] = Field(..., min_length=1, max_length=30)
    expires_at: Optional[datetime] = None
    reason: str = Field(..., min_length=2, max_length=255)
    dry_run: bool = True


class PermissionBatchUndoRequest(BaseModel):
    """撤销批次。"""
    reason: str = Field("撤销批量权限变更", max_length=255)


class UserListQuery(BaseModel):
    """用户列表查询参数"""
    keyword: Optional[str] = None
    user_type: Optional[str] = None
    status: Optional[int] = None
    is_disabled: Optional[int] = None
    school: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ==================== 公告管理 ====================

class AnnouncementCreate(BaseModel):
    """创建公告"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    level: str = Field("info", description="级别: info/warning/urgent")
    target_role: str = Field("all", description="目标角色: all/student/teacher/admin")
    is_pinned: int = Field(0, description="是否置顶")
    expire_time: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    """编辑公告"""
    title: Optional[str] = None
    content: Optional[str] = None
    level: Optional[str] = None
    target_role: Optional[str] = None
    is_pinned: Optional[int] = None
    expire_time: Optional[datetime] = None
    status: Optional[int] = None


# ==================== 题目审核 ====================

class QuestionAuditRequest(BaseModel):
    """题目审核"""
    audit_status: int = Field(..., description="审核状态: 1通过/2驳回")
    audit_comment: Optional[str] = None


class QuestionUpdateRequest(BaseModel):
    """题目编辑（管理员）"""
    subject_id: Optional[int] = None
    type_id: Optional[int] = None
    question_content: Optional[str] = None
    options: Optional[str] = None
    answer: Optional[str] = None
    answer_analysis: Optional[str] = None
    difficulty: Optional[int] = None
    source: Optional[str] = None
    group_id: Optional[int] = None
    shared_content: Optional[str] = None
    shared_content_images: Optional[str] = None


# ==================== 试卷审批 ====================

class PaperApproveRequest(BaseModel):
    """试卷审批通过"""
    opinion: Optional[str] = None


class PaperRejectRequest(BaseModel):
    """试卷审批驳回"""
    opinion: str = Field(..., description="驳回理由（必填）")


# ==================== 系统设置 ====================

class SystemSettingsUpdate(BaseModel):
    """系统设置更新"""
    settings: dict = Field(..., description="键值对配置")


class PermissionRoleUpdate(BaseModel):
    """权限角色配置更新"""
    role: str = Field(..., description="角色: student/teacher/admin")
    permissions: List[str] = Field(..., description="权限码列表")
    reason: str = Field("", max_length=255, description="变更原因（新页必填，旧页可空）")


# ==================== 备份管理 ====================

class BackupCreateRequest(BaseModel):
    """创建备份"""
    backup_type: str = Field("full", description="备份类型: full/incremental")
    backup_name: Optional[str] = None


class BackupRestoreRequest(BaseModel):
    """恢复备份"""
    confirm: bool = Field(True, description="二次确认")
