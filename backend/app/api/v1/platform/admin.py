"""
管理员端 API — 用户管理、系统设置、日志审计、数据备份、权限管理
"""
import os
import json
import logging
import secrets
import uuid
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from ....core.database import get_db, engine
from ....core.security import (
    get_current_admin, get_current_super_admin, get_password_hash,
    check_permission, Permission, get_effective_permissions,
    get_role_base_permissions, get_user_permissions_with_db,
    permission_catalog, PERMISSION_META, PROTECTED_PERMISSIONS,
    SUPER_ADMIN_PERMISSIONS,
)
from ....models.models import (
    SysUser, SysOperationLog, SysConfig, SysAnnouncement,
    SysBackupRecord, SysVersion, SysDictType, SysDictData,
    School, QuestionBank, ExamPaper, ExamRecord, PracticeRecord,
    Banji, PaperApprovalWorkflow, UserPermissionOverride,
    PermissionChangeBatch,
)
from ....services.question_stats import QuestionStatsService
from ....services.question_ingest.groups import upsert_question_material
from ....schemas.admin import (
    DashboardStats, DashboardResponse, WeeklyActiveTrend,
    SubjectDistribution,
    UserCreate, UserUpdate, UserDisableRequest, UserResetPasswordRequest,
    AnnouncementCreate, AnnouncementUpdate,
    QuestionAuditRequest, QuestionUpdateRequest,
    SystemSettingsUpdate, PermissionRoleUpdate,
    UserRoleUpdate, UserDeleteRequest, UserPurgeRequest,
    UserPermissionUpdate, PermissionBatchRequest, PermissionBatchUndoRequest,
    UserBatchRequest,
    BackupCreateRequest, BackupRestoreRequest,
)

router = APIRouter(prefix="/api/admin", tags=["管理员端"])
logger = logging.getLogger(__name__)

# ==================== 辅助函数 ====================

def record_operation(db: Session, user: SysUser, op_type: str, module: str,
                     desc: str, request_url: str = "", request_params: str = "",
                     ip_address: str = "", duration: int = 0, request=None):
    """记录管理员操作日志（增强版）"""
    try:
        # 自动获取IP地址
        if not ip_address and request:
            ip_address = request.client.host if request.client else ""
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip_address = forwarded.split(",")[0].strip()
        
        # 查询用户角色
        role_map = {"admin": "管理员", "teacher": "教师", "student": "学生"}
        user_role = role_map.get(user.user_type, "未知")
        
        # 模块名称中文化
        module_map = {
            "用户管理": "用户管理",
            "题库管理": "题库管理",
            "公告管理": "公告管理",
            "日志审计": "日志审计",
            "数据备份": "数据备份",
            "系统设置": "系统设置",
            "权限管理": "权限管理",
            "试卷审批": "试卷审批",
            "资料管理": "资料管理",
            "BATCH": "批量操作",
        }
        module_name = module_map.get(module, module)
        
        log_entry = SysOperationLog(
            user_id=user.user_id,
            user_name=user.username,
            user_role=user_role,
            operation_type=op_type,
            module_name=module_name,
            operation_desc=desc,
            request_url=request_url,
            request_params=request_params,
            ip_address=ip_address,
            duration=duration,
            response_result="success",
            operation_time=datetime.now()
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"操作日志记录失败: {e}")


# ==================== 日志字段中文化映射 ====================
# 历史数据中 operation_type / module_name 存的是英文值，前端直接渲染会出现英文。
# 统一在接口返回时转换为中文，保证界面全中文显示。

OPERATION_TYPE_CN = {
    "CREATE": "创建", "create": "创建",
    "UPDATE": "更新", "update": "更新",
    "DELETE": "删除", "delete": "删除",
    "LOGIN": "登录", "login": "登录",
    "LOGOUT": "退出登录", "logout": "退出登录",
    "AUDIT": "审核", "audit": "审核",
    "BACKUP": "备份", "backup": "备份",
    "RESTORE": "恢复", "restore": "恢复",
    "EXPORT": "导出", "export": "导出",
    "import_confirm": "导入入库",
    "import_upload": "上传素材",
    "upload_image": "上传图片",
    "status": "状态变更",
    "create_material": "新建资料",
    "batch_create": "批量创建",
    "batch_delete": "批量删除",
    "batch_publish": "批量上架",
    "batch_unpublish": "批量下架",
    "SENSITIVE_VIOLATION": "敏感词拦截",
    "BATCH": "批量操作",
    "REJECT": "驳回", "reject": "驳回",
}

MODULE_NAME_CN = {
    "materials": "资料管理",
    "forum": "论坛",
    "用户管理": "用户管理",
    "题库管理": "题库管理",
    "公告管理": "公告管理",
    "日志审计": "日志审计",
    "数据备份": "数据备份",
    "系统设置": "系统设置",
    "权限管理": "权限管理",
    "试卷审批": "试卷审批",
    "资料管理": "资料管理",
}

RESULT_CN = {
    "success": "成功",
    "failed": "失败",
    "error": "失败",
    "masked": "已脱敏",
    "rejected": "已拒绝",
}


def _translate_operation_type(op_type: str) -> str:
    """操作类型英转中"""
    if not op_type:
        return "-"
    return OPERATION_TYPE_CN.get(op_type, op_type)


def _translate_module_name(module_name: str) -> str:
    """模块名英转中"""
    if not module_name:
        return "-"
    return MODULE_NAME_CN.get(module_name, module_name)


def _format_user(user: SysUser, override_count: int = 0) -> dict:
    """格式化用户信息（override_count 由列表聚合一次查出，避免逐行查询）。"""
    return {
        "user_id": user.user_id,
        "user_no": user.user_no,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "avatar": user.avatar,
        "gender": user.gender,
        "user_type": user.user_type,
        "department": user.department,
        "class_name": user.class_name,
        "school": user.school,
        "role_level": user.role_level,
        "status": user.status,
        "is_disabled": getattr(user, 'is_disabled', 0),
        "disabled_reason": getattr(user, 'disabled_reason', ''),
        "is_deleted": getattr(user, 'is_deleted', 0) or 0,
        "deleted_at": user.deleted_at.isoformat() if getattr(user, 'deleted_at', None) else None,
        "deleted_by": getattr(user, 'deleted_by', None),
        "delete_reason": getattr(user, 'delete_reason', '') or '',
        "override_count": override_count,
        "total_coins": user.total_coins,
        "continuous_checkin_days": user.continuous_checkin_days,
        "register_time": user.register_time.isoformat() if user.register_time else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "last_login_ip": getattr(user, 'last_login_ip', ''),
    }


def _active_super_count(db: Session) -> int:
    """当前可用超管数（未删除、未禁用、未停用）。"""
    return db.query(func.count(SysUser.user_id)).filter(
        SysUser.user_type == "admin",
        SysUser.role_level >= 3,
        SysUser.status != 0,
        SysUser.is_disabled == 0,
        SysUser.is_deleted == 0,
    ).scalar() or 0


def _is_active_super(user: SysUser) -> bool:
    return (
        user.user_type == "admin"
        and user.role_level >= 3
        and user.status != 0
        and getattr(user, "is_disabled", 0) == 0
        and (getattr(user, "is_deleted", 0) or 0) == 0
    )


def _assert_not_last_super(db: Session, target: SysUser) -> None:
    """删除/禁用/降级/关键权限拒绝前调用；唯一超管不可失能。"""
    if _is_active_super(target) and _active_super_count(db) <= 1:
        raise HTTPException(
            status_code=409,
            detail="系统必须保留至少一个可用超级管理员，操作已阻止",
        )


def _assert_can_manage_target(operator: SysUser, target: SysUser) -> None:
    """越级保护：不能自伤、不能改同级/更高级、非超管不能动管理员。"""
    if operator.user_id == target.user_id:
        raise HTTPException(status_code=403, detail="不能对自己的账号执行此操作")
    if target.role_level >= operator.role_level:
        raise HTTPException(status_code=403, detail="不能修改同级或更高级别的用户")
    if target.user_type == "admin" and operator.role_level < 3:
        raise HTTPException(status_code=403, detail="只有超级管理员可以操作管理员账号")


def _normalize_expiry(value: Optional[datetime]) -> Optional[datetime]:
    """统一为 naive 本地时间；已过期直接 400。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    if value <= datetime.now():
        raise HTTPException(status_code=400, detail="到期时间必须晚于当前时间")
    return value


def _active_override_rows(user_id: int, db: Session) -> List[UserPermissionOverride]:
    rows = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.status == "active",
        UserPermissionOverride.scope_type == "global",
    ).all()
    now = datetime.now()
    return [row for row in rows if not row.expires_at or row.expires_at > now]


def _permission_detail(user: SysUser, db: Session) -> dict:
    """权限来源解释：角色基线 / 能力包 / 加授 / 拒绝 / 有效。"""
    baseline = set(get_role_base_permissions(user, db))
    capabilities = set(get_user_permissions_with_db(user, db)) - baseline
    effective = set(get_effective_permissions(user, db))
    rows = _active_override_rows(user.user_id, db)
    grant_codes = {r.permission_code for r in rows if r.effect == "grant"}
    deny_codes = {r.permission_code for r in rows if r.effect == "deny"}
    override_by_code = {r.permission_code: r for r in rows}

    items = []
    for permission in Permission:
        code = permission.value
        is_protected_deny = (
            code in deny_codes
            and user.role_level >= 3
            and permission in PROTECTED_PERMISSIONS
        )
        if is_protected_deny:
            state = "inherit"
        elif code in deny_codes:
            state = "deny"
        elif code in grant_codes:
            state = "grant"
        else:
            state = "inherit"
        row = override_by_code.get(code)
        meta = PERMISSION_META.get(permission, {})
        items.append({
            "permission_code": code,
            "label": meta.get("label", code),
            "group": meta.get("group", "其他"),
            "risk": meta.get("risk", "low"),
            "description": meta.get("description", ""),
            "state": state,
            "effective": code in effective,
            "sources": {
                "role": permission in baseline,
                "capability": permission in capabilities,
                "grant": code in grant_codes,
                "deny": code in deny_codes and not is_protected_deny,
            },
            "expires_at": row.expires_at.isoformat() if row and row.expires_at else None,
            "reason": row.reason if row else "",
            "protected_deny_ignored": is_protected_deny,
        })
    return {
        "effective_permissions": sorted(p.value for p in effective),
        "baseline_permissions": sorted(p.value for p in baseline),
        "capability_permissions": sorted(p.value for p in capabilities),
        "granted_permissions": sorted(grant_codes),
        "denied_permissions": sorted(deny_codes),
        "items": items,
        "override_count": len(rows),
    }


def _write_batch(db: Session, operator: SysUser, action: str,
                 target_count: int, reason: str,
                 before: dict, after: dict,
                 batch_id: Optional[str] = None) -> str:
    """写入权限变更批次，10 分钟内可撤销；返回 batch_id。"""
    batch_id = batch_id or str(uuid.uuid4())
    db.add(PermissionChangeBatch(
        batch_id=batch_id,
        operator_id=operator.user_id,
        action=action,
        target_count=target_count,
        reason=reason,
        before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(after, ensure_ascii=False),
        undo_deadline=datetime.now() + timedelta(minutes=10),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    ))
    return batch_id


def _resolve_permission_batch_targets(
    db: Session, target, operator: SysUser,
    allow_deleted: bool = False, deleted_only: bool = False,
) -> List[SysUser]:
    """解析批量目标并做越级/删除态校验；数量与预期不符直接 409。"""
    query = db.query(SysUser)
    if target.mode == "ids":
        if not target.user_ids:
            raise HTTPException(status_code=400, detail="请选择至少一个用户")
        if target.expected_count is not None and len(set(target.user_ids)) != target.expected_count:
            raise HTTPException(status_code=409, detail="目标数量已变化，请重新选择")
        users = query.filter(SysUser.user_id.in_(set(target.user_ids))).all()
        found_ids = {u.user_id for u in users}
        missing = sorted(set(target.user_ids) - found_ids)
        if missing:
            raise HTTPException(status_code=404, detail=f"用户不存在: {missing[0]}")
    elif target.mode == "filter":
        filters = target.filter or {}
        allowed = {
            "keyword", "user_type", "role_level", "department",
            "class_name", "school", "is_disabled", "has_override",
        }
        unknown = set(filters) - allowed
        if unknown:
            raise HTTPException(status_code=400, detail=f"不支持的筛选字段: {sorted(unknown)[0]}")
        if "keyword" in filters:
            kw = str(filters["keyword"])
            query = query.filter(or_(
                SysUser.username.contains(kw),
                SysUser.user_no.contains(kw),
                SysUser.phone.contains(kw),
            ))
        for field in ("user_type", "role_level", "department", "class_name", "school", "is_disabled"):
            if filters.get(field) is not None:
                query = query.filter(getattr(SysUser, field) == filters[field])
        if filters.get("has_override") is not None:
            sub = db.query(UserPermissionOverride.user_id).filter(
                UserPermissionOverride.status == "active",
                UserPermissionOverride.scope_type == "global",
            ).subquery()
            if filters["has_override"]:
                query = query.filter(SysUser.user_id.in_(sub))
            else:
                query = query.filter(~SysUser.user_id.in_(sub))
        actual = query.filter(SysUser.is_deleted == (1 if deleted_only else 0)).count()
        if target.expected_count is not None and actual != target.expected_count:
            raise HTTPException(
                status_code=409,
                detail=f"筛选结果已变化：预期 {target.expected_count} 人，实际 {actual} 人",
            )
        users = query.filter(SysUser.is_deleted == (1 if deleted_only else 0)).all()
    else:
        raise HTTPException(status_code=400, detail="target.mode 必须是 ids 或 filter")

    if len(users) > 500:
        raise HTTPException(status_code=422, detail="单次批量最多 500 人")
    for user in users:
        deleted = (getattr(user, "is_deleted", 0) or 0) != 0
        if deleted and not allow_deleted:
            raise HTTPException(status_code=422, detail=f"批量包含已删除用户: {user.user_id}")
        if not deleted and deleted_only:
            raise HTTPException(status_code=422, detail=f"目标不在回收站: {user.user_id}")
        if user.user_id == operator.user_id:
            raise HTTPException(status_code=403, detail="不能对本人执行批量操作")
        if user.role_level >= operator.role_level:
            raise HTTPException(status_code=403, detail=f"不能修改同级或更高级别用户: {user.username}")
        if user.user_type == "admin" and operator.role_level < 3:
            raise HTTPException(status_code=403, detail="只有超级管理员可以操作管理员账号")
    return users


def _validate_batch_permissions(
    db: Session, operator: SysUser, permissions: List[str], operation: str
) -> List[Permission]:
    if operation not in ("grant", "deny", "inherit"):
        raise HTTPException(status_code=400, detail=f"无效的 operation: {operation}")
    resolved: List[Permission] = []
    seen = set()
    operator_effective = set(get_effective_permissions(operator, db))
    for code in permissions:
        permission = Permission._value2member_map_.get(code)
        if permission is None:
            raise HTTPException(status_code=422, detail=f"权限码不存在: {code}")
        if permission.value in seen:
            continue
        seen.add(permission.value)
        meta = PERMISSION_META[permission]
        if meta["risk"] == "critical" and operator.role_level < 3:
            raise HTTPException(status_code=403, detail=f"只有超级管理员可以变更关键权限: {code}")
        if operation == "grant" and operator.role_level < 3 and permission not in operator_effective:
            raise HTTPException(status_code=403, detail=f"不能授出自己不具备的权限: {code}")
        resolved.append(permission)
    return resolved


def _override_states(rows, now=None) -> dict:
    """把 active 行转成 {user_id:code: state}；过期行视为 inherit。"""
    now = now or datetime.now()
    states = {}
    for row in rows:
        if row.expires_at and row.expires_at <= now:
            continue
        states[f"{row.user_id}:{row.permission_code}"] = row.effect
    return states


# ==================== 系统总览 ====================

@router.get("/dashboard", summary="系统总览数据")
async def get_dashboard(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取管理端系统总览核心数据"""
    # 用户统计
    total_users = db.query(func.count(SysUser.user_id)).scalar()
    total_students = db.query(func.count(SysUser.user_id)).filter(
        SysUser.user_type == "student"
    ).scalar()
    total_teachers = db.query(func.count(SysUser.user_id)).filter(
        SysUser.user_type == "teacher"
    ).scalar()
    total_admins = db.query(func.count(SysUser.user_id)).filter(
        SysUser.user_type == "admin"
    ).scalar()

    # 题目统计
    total_questions = db.query(func.count(QuestionBank.question_id)).filter(
        QuestionBank.status == 1
    ).scalar()
    # 试卷总数：只统计已发布的试卷（paper_type == "PUBLISHED"），
    # 草稿/审批中/已结束的试卷不计入"已有试卷"数，与教师端"点击发布才统计"口径一致
    total_papers = db.query(func.count(ExamPaper.paper_id)).filter(
        ExamPaper.paper_type == "PUBLISHED"
    ).scalar()

    # 今日活跃
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_active = db.query(func.count(func.distinct(PracticeRecord.user_id))).filter(
        PracticeRecord.practice_time >= today_start
    ).scalar()
    today_practice = db.query(func.count(PracticeRecord.record_id)).filter(
        PracticeRecord.practice_time >= today_start
    ).scalar()
    new_users_today = db.query(func.count(SysUser.user_id)).filter(
        SysUser.register_time >= today_start
    ).scalar()
    pending_papers = db.query(func.count(PaperApprovalWorkflow.workflow_id)).filter(
        PaperApprovalWorkflow.status == "pending"
    ).scalar()

    stats = DashboardStats(
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        total_admins=total_admins,
        total_questions=total_questions,
        total_papers=total_papers,
        today_active_users=today_active,
        today_practice_count=today_practice,
        new_users_today=new_users_today,
        pending_approval_papers=pending_papers,
    )

    # 7天活跃趋势
    dates = []
    counts = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        dates.append(d.strftime("%m-%d"))
        day_start = datetime.combine(d, datetime.min.time())
        day_end = datetime.combine(d + timedelta(days=1), datetime.min.time())
        cnt = db.query(func.count(func.distinct(PracticeRecord.user_id))).filter(
            PracticeRecord.practice_time >= day_start,
            PracticeRecord.practice_time < day_end
        ).scalar()
        counts.append(cnt)

    weekly_trend = WeeklyActiveTrend(dates=dates, active_counts=counts)

    # 科目题目分布
    subjects = db.query(QuestionBank.subject_id, func.count(QuestionBank.question_id)).filter(
        QuestionBank.status == 1
    ).group_by(QuestionBank.subject_id).all()
    subject_names = {1: "行测", 2: "申论", 3: "公专"}
    distribution = [
        SubjectDistribution(
            subject=subject_names.get(s[0], f"科目{s[0]}"),
            count=s[1],
        )
        for s in subjects
    ]

    # 最近操作日志
    recent_logs = []
    logs = db.query(SysOperationLog).order_by(
        desc(SysOperationLog.operation_time)
    ).limit(10).all()
    for log in logs:
        recent_logs.append({
            "time": log.operation_time.isoformat() if log.operation_time else "",
            "user": log.user_name,
            "module": log.module_name,
            "desc": log.operation_desc,
            "ip": log.ip_address,
        })

    return DashboardResponse(
        stats=stats,
        weekly_trend=weekly_trend,
        subject_distribution=distribution,
        recent_logs=recent_logs
    )


# ==================== 用户管理 ====================

@router.get("/users", summary="用户列表")
async def list_users(
    keyword: Optional[str] = Query(None, description="搜索关键词(姓名/学号/手机号)"),
    user_type: Optional[str] = Query(None, description="用户类型"),
    role_level: Optional[int] = Query(None, ge=0, le=3, description="权限级别"),
    is_disabled: Optional[int] = Query(None, description="禁用状态"),
    department: Optional[str] = Query(None, description="部门"),
    class_name: Optional[str] = Query(None, description="班级"),
    school: Optional[str] = Query(None, description="学校"),
    has_override: Optional[bool] = Query(None, description="是否有个人权限覆盖"),
    last_login_before: Optional[datetime] = Query(None, description="最后登录早于该时间"),
    include_deleted: bool = Query(False, description="包含回收站用户"),
    sort: str = Query("register_time_desc", description="排序: register_time_desc/last_login_desc/username_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """分页查询用户列表（默认排除回收站；覆盖数批量聚合，避免 N+1）。"""
    base_query = db.query(SysUser)

    if not include_deleted:
        base_query = base_query.filter(SysUser.is_deleted == 0)
    if keyword:
        base_query = base_query.filter(or_(
            SysUser.username.contains(keyword),
            SysUser.user_no.contains(keyword),
            SysUser.phone.contains(keyword),
        ))
    if user_type:
        base_query = base_query.filter(SysUser.user_type == user_type)
    if role_level is not None:
        base_query = base_query.filter(SysUser.role_level == role_level)
    if is_disabled is not None:
        base_query = base_query.filter(SysUser.is_disabled == is_disabled)
    if department:
        base_query = base_query.filter(SysUser.department == department)
    if class_name:
        base_query = base_query.filter(SysUser.class_name == class_name)
    if school:
        base_query = base_query.filter(SysUser.school == school)
    if last_login_before:
        base_query = base_query.filter(
            SysUser.last_login.isnot(None),
            SysUser.last_login < last_login_before,
        )
    if has_override is not None:
        override_users = db.query(UserPermissionOverride.user_id).filter(
            UserPermissionOverride.status == "active",
            UserPermissionOverride.scope_type == "global",
        ).subquery()
        if has_override:
            base_query = base_query.filter(SysUser.user_id.in_(override_users))
        else:
            base_query = base_query.filter(~SysUser.user_id.in_(override_users))

    total = base_query.count()
    order_map = {
        "register_time_desc": (desc(SysUser.register_time), desc(SysUser.user_id)),
        "last_login_desc": (desc(SysUser.last_login), desc(SysUser.user_id)),
        "username_asc": (SysUser.username.asc(), SysUser.user_id.asc()),
    }
    users = base_query.order_by(
        *order_map.get(sort, order_map["register_time_desc"])
    ).offset((page - 1) * page_size).limit(page_size).all()

    ids = [u.user_id for u in users]
    counts = {}
    if ids:
        counts = dict(db.query(
            UserPermissionOverride.user_id,
            func.count(UserPermissionOverride.id),
        ).filter(
            UserPermissionOverride.user_id.in_(ids),
            UserPermissionOverride.status == "active",
            UserPermissionOverride.scope_type == "global",
        ).group_by(UserPermissionOverride.user_id).all())

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_user(u, counts.get(u.user_id, 0)) for u in users],
    }


@router.post("/users", summary="创建用户")
async def create_user(
    data: UserCreate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员创建新用户（学生/教师/管理员）"""
    # 检查用户名唯一性
    existing = db.query(SysUser).filter(
        or_(SysUser.username == data.username, SysUser.user_no == data.user_no)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或编号已存在")

    new_user = SysUser(
        user_no=data.user_no,
        username=data.username,
        password=get_password_hash(data.password),
        email=data.email,
        phone=data.phone or "",
        gender=data.gender or "未知",
        user_type=data.user_type,
        department=data.department,
        class_name=data.class_name,
        school=data.school or "中国人民警察大学",
        role_level=data.role_level,
        status=1,
        is_disabled=0,
        created_by=current_user.user_id,
        register_time=datetime.now(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    record_operation(db, current_user, "CREATE", "用户管理",
                     f"创建用户 {data.username}({data.user_type})")

    return {"success": True, "message": "用户创建成功", "user": _format_user(new_user)}


@router.put("/users/{user_id}", summary="编辑用户")
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """编辑用户信息"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    _assert_can_manage_target(current_user, user)

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"编辑用户 {user.username}(ID:{user_id})")

    return {"success": True, "message": "用户更新成功", "user": _format_user(user)}


@router.get("/users/stats", summary="用户概览计数")
async def user_stats(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """一次聚合返回用户管理页顶部的计数卡，避免前端发多次请求。"""
    active = db.query(SysUser).filter(SysUser.is_deleted == 0)
    total = active.count()
    by_type = dict(
        active.with_entities(SysUser.user_type, func.count(SysUser.user_id))
        .group_by(SysUser.user_type).all()
    )
    return {
        "success": True,
        "total": total,
        "student": by_type.get("student", 0),
        "teacher": by_type.get("teacher", 0),
        "admin": by_type.get("admin", 0),
        "disabled": active.filter(SysUser.is_disabled == 1).count(),
        "deleted": db.query(SysUser).filter(SysUser.is_deleted == 1).count(),
        "with_override": db.query(UserPermissionOverride.user_id).filter(
            UserPermissionOverride.status == "active",
            UserPermissionOverride.scope_type == "global",
        ).distinct().count(),
    }


@router.get("/users/{user_id}", summary="用户详情")
async def get_user_detail(
    user_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """用户详情 + 角色 + 权限摘要（编辑弹窗与抽屉共用）。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    detail = _format_user(user, len(_active_override_rows(user_id, db)))
    permissions = _permission_detail(user, db)
    detail["role"] = {
        "user_type": user.user_type,
        "role_level": user.role_level,
        "role_name": {"student": "学生", "teacher": "教师", "admin": "管理员"}.get(user.user_type, user.user_type),
    }
    detail["permissions"] = {
        "effective_count": len(permissions["effective_permissions"]),
        "override_count": permissions["override_count"],
        "effective_permissions": permissions["effective_permissions"],
    }
    return {"success": True, "user": detail}


@router.put("/users/{user_id}/role", summary="修改用户角色（仅超管）")
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """改 user_type/role_level；与资料编辑分离，禁止自改与制造同级/更高级。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    _assert_can_manage_target(current_user, user)

    if data.user_type not in ("student", "teacher", "admin"):
        raise HTTPException(status_code=400, detail="无效的用户类型")
    if data.role_level >= current_user.role_level:
        raise HTTPException(status_code=403, detail="不能把用户提升到同级或更高级别")
    if data.user_type == "admin" and data.role_level < 2:
        raise HTTPException(status_code=400, detail="管理员角色的权限级别不能低于 2")
    if data.user_type != "admin" and data.role_level >= 3:
        raise HTTPException(status_code=400, detail="超级管理员必须是管理员角色")
    if _is_active_super(user):
        _assert_not_last_super(db, user)

    before = {"user_type": user.user_type, "role_level": user.role_level}
    user.user_type = data.user_type
    user.role_level = data.role_level
    batch_id = _write_batch(
        db, current_user, "role_change", 1, data.reason,
        {"users": {str(user_id): before}},
        {"users": {str(user_id): {"user_type": data.user_type, "role_level": data.role_level}}},
    )
    db.commit()
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"修改用户 {user.username}(ID:{user_id}) 角色为 {data.user_type}/{data.role_level}；原因: {data.reason or '未填写'}")
    return {
        "success": True,
        "message": "角色已更新",
        "batch_id": batch_id,
        "user": _format_user(user, len(_active_override_rows(user_id, db))),
    }


@router.delete("/users/{user_id}", summary="软删除用户")
async def delete_user(
    user_id: int,
    data: UserDeleteRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """移入回收站：保留行与历史引用，禁止登录；物理行不删除。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=409, detail="用户已在回收站")
    _assert_can_manage_target(current_user, user)
    _assert_not_last_super(db, user)

    user.is_deleted = 1
    user.deleted_at = datetime.now()
    user.deleted_by = current_user.user_id
    user.delete_reason = data.reason
    user.is_disabled = 1
    user.disabled_reason = f"账号已删除：{data.reason}"
    db.commit()
    record_operation(db, current_user, "DELETE", "用户管理",
                     f"删除用户 {user.username}(ID:{user_id}) 到回收站；原因: {data.reason}")
    return {"success": True, "message": "用户已移入回收站"}


@router.post("/users/{user_id}/restore", summary="从回收站恢复用户")
async def restore_user(
    user_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (getattr(user, "is_deleted", 0) or 0) == 0:
        raise HTTPException(status_code=409, detail="用户不在回收站")
    if user.user_type == "admin" and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="只有超级管理员可以恢复管理员账号")

    user.is_deleted = 0
    user.deleted_at = None
    user.deleted_by = None
    user.delete_reason = ""
    user.is_disabled = 0
    user.disabled_reason = ""
    db.commit()
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"从回收站恢复用户 {user.username}(ID:{user_id})")
    return {"success": True, "message": "用户已恢复"}


def _anonymize_user(db: Session, user: SysUser, operator: SysUser, reason: str) -> str:
    """把回收站用户匿名化为墓碑；返回原用户名，供审计记录。"""
    user_id = user.user_id
    original_username = user.username
    user.username = f"deleted_{user_id}"
    user.user_no = f"deleted_{user_id}"
    user.phone = ""
    user.email = None
    user.avatar = None
    user.password = get_password_hash(secrets.token_urlsafe(32))
    user.device_sessions = []
    user.user_type = "student"
    user.role_level = 0
    user.is_disabled = 1
    user.is_deleted = 2
    user.delete_reason = reason

    # 权限与能力包同步失效，避免墓碑账号残留授权。
    db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id == user_id,
        UserPermissionOverride.status == "active",
    ).update({
        UserPermissionOverride.status: "revoked",
        UserPermissionOverride.revoked_by: operator.user_id,
        UserPermissionOverride.revoked_at: datetime.now(),
        UserPermissionOverride.updated_at: datetime.now(),
    }, synchronize_session=False)
    try:
        from ....models.models import UserCapability
        db.query(UserCapability).filter(UserCapability.user_id == user_id).delete(
            synchronize_session=False
        )
    except Exception:
        pass
    return original_username


@router.post("/users/{user_id}/purge", summary="匿名化注销用户（仅超管）")
async def purge_user(
    user_id: int,
    data: UserPurgeRequest,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """彻底清除 PII，但保留 user_id 墓碑，避免题目/试卷/考试记录悬空。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (getattr(user, "is_deleted", 0) or 0) != 1:
        raise HTTPException(status_code=409, detail="只能注销回收站中的用户")
    if data.confirm_username != user.username:
        raise HTTPException(status_code=400, detail="确认用户名不匹配")
    _assert_not_last_super(db, user)

    original_username = _anonymize_user(db, user, current_user, data.reason)
    db.commit()
    record_operation(db, current_user, "DELETE", "用户管理",
                     f"匿名化注销用户 {original_username}(ID:{user_id})；原因: {data.reason}")
    return {"success": True, "message": "用户已匿名化注销，历史引用保留"}


@router.post("/users/batch", summary="批量操作用户")
async def batch_operate_users(
    data: UserBatchRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """批量禁用/启用/删除/恢复/改资料/改角色/重置密码；任一目标不合法整批拒绝。"""
    allowed = {
        "disable", "enable", "delete", "restore",
        "update_profile", "assign_role", "reset_password", "purge",
    }
    if data.action not in allowed:
        raise HTTPException(status_code=400, detail=f"无效的 action: {data.action}")
    payload = data.payload or {}
    reason = str(payload.get("reason", "")).strip()
    if data.action in ("disable", "delete", "assign_role", "purge") and len(reason) < 2:
        raise HTTPException(status_code=400, detail="该批量操作必须填写原因")
    if data.action in ("assign_role", "reset_password", "purge") and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="只有超级管理员可以批量改角色、重置密码或彻底注销")

    recycle_mode = data.action in ("restore", "purge")
    users = _resolve_permission_batch_targets(
        db, data.target, current_user,
        allow_deleted=recycle_mode, deleted_only=recycle_mode,
    )
    if data.expected_count is not None and len(users) != data.expected_count:
        raise HTTPException(status_code=409, detail="目标数量已变化，请重新选择")

    # 先整批预检，避免处理到一半才发现最后超管保护，留下未提交的半批修改。
    if data.action == "purge":
        for user in users:
            if (getattr(user, "is_deleted", 0) or 0) != 1:
                raise HTTPException(status_code=409, detail=f"只能注销回收站中的用户: {user.username}")
            _assert_not_last_super(db, user)

    changed = 0
    credentials = []
    now = datetime.now()
    for user in users:
        if data.action == "disable":
            _assert_not_last_super(db, user)
            user.is_disabled = 1
            user.disabled_reason = reason
        elif data.action == "enable":
            user.is_disabled = 0
            user.disabled_reason = ""
        elif data.action == "delete":
            _assert_not_last_super(db, user)
            if (getattr(user, "is_deleted", 0) or 0) != 0:
                raise HTTPException(status_code=409, detail=f"用户已在回收站: {user.username}")
            user.is_deleted = 1
            user.deleted_at = now
            user.deleted_by = current_user.user_id
            user.delete_reason = reason
            user.is_disabled = 1
            user.disabled_reason = f"账号已删除：{reason}"
        elif data.action == "restore":
            user.is_deleted = 0
            user.deleted_at = None
            user.deleted_by = None
            user.delete_reason = ""
            user.is_disabled = 0
            user.disabled_reason = ""
        elif data.action == "update_profile":
            for field in ("gender", "department", "class_name", "school"):
                if field in payload:
                    setattr(user, field, payload[field])
        elif data.action == "assign_role":
            user_type = payload.get("user_type")
            role_level = payload.get("role_level")
            if user_type not in ("student", "teacher", "admin"):
                raise HTTPException(status_code=400, detail="user_type 必须是 student/teacher/admin")
            if not isinstance(role_level, int) or not 0 <= role_level <= 3:
                raise HTTPException(status_code=400, detail="role_level 必须在 0..3")
            if role_level < 3:
                _assert_not_last_super(db, user)
            user.user_type = user_type
            user.role_level = role_level
        elif data.action == "reset_password":
            password = secrets.token_urlsafe(9)
            user.password = get_password_hash(password)
            credentials.append({"user_id": user.user_id, "username": user.username, "new_password": password})
        elif data.action == "purge":
            _anonymize_user(db, user, current_user, reason)
        changed += 1

    batch_id = str(uuid.uuid4())
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_operation(
        db, current_user, "DELETE" if data.action == "purge" else "UPDATE", "用户管理",
        f"批量{data.action} {changed} 人；原因: {reason or '无'}；批次: {batch_id}",
    )
    return {
        "success": True,
        "batch_id": batch_id,
        "action": data.action,
        "affected": changed,
        "credentials": credentials,
    }


@router.put("/users/{user_id}/disable", summary="禁用/启用用户")
async def toggle_disable_user(
    user_id: int,
    data: UserDisableRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """禁用或启用用户账号"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    _assert_can_manage_target(current_user, user)
    if data.is_disabled:
        _assert_not_last_super(db, user)

    user.is_disabled = 1 if data.is_disabled else 0
    user.disabled_reason = data.reason if data.is_disabled else ""
    db.commit()

    action = "禁用" if data.is_disabled else "启用"
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"{action}用户 {user.username}(ID:{user_id}) 原因: {data.reason or '无'}")

    return {"success": True, "message": f"用户已{action}"}


@router.put("/users/{user_id}/reset-password", summary="重置密码")
async def reset_user_password(
    user_id: int,
    data: UserResetPasswordRequest = UserResetPasswordRequest(),
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """重置用户密码（仅超级管理员）"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    _assert_can_manage_target(current_user, user)

    new_password = data.new_password or secrets.token_urlsafe(8)[:12]
    user.password = get_password_hash(new_password)

    # 清除重置令牌
    user.password_reset_token = None
    user.password_reset_expire = None

    db.commit()
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"重置用户 {user.username}(ID:{user_id}) 的密码")

    return {"success": True, "message": "密码已重置", "new_password": new_password}


# ==================== 题库管理 ====================

@router.get("/questions/stats", summary="题目统计")
async def get_question_stats(
    include_offline: bool = Query(False, description="包含禁用/草稿题目"),
    include_pending: bool = Query(False, description="包含待审核题目"),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取题目统计数据"""
    base_query = QuestionStatsService.visible_query(
        db, include_offline=include_offline, include_pending=include_pending
    )

    # 总题目数
    total = base_query.count()

    # 各科目题目数
    xingce = base_query.filter(QuestionBank.subject_id == 1).count()
    shenlun = base_query.filter(QuestionBank.subject_id == 2).count()
    gongzhuan = base_query.filter(QuestionBank.subject_id == 3).count()

    # 待审核数
    pending = db.query(func.count(QuestionBank.question_id)).filter(
        QuestionBank.audit_status == 0,
        QuestionBank.status == 1
    ).scalar()

    return {
        "success": True,
        "total": total,
        "xingce": xingce,
        "shenlun": shenlun,
        "gongzhuan": gongzhuan,
        "pending": pending
    }


@router.get("/questions", summary="全部题目列表（含审核）")
async def list_all_questions(
    keyword: Optional[str] = Query(None),
    subject_id: Optional[int] = Query(None),
    type_id: Optional[int] = Query(None, description="题型ID筛选"),
    audit_status: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_offline: bool = Query(False, description="包含禁用/草稿题目"),
    include_pending: bool = Query(False, description="包含待审核题目"),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员查看全部题目（默认与学生端同口径，开关放宽）"""
    base_query = QuestionStatsService.visible_query(
        db, include_offline=include_offline, include_pending=include_pending
    )
    if keyword:
        base_query = base_query.filter(QuestionBank.question_content.contains(keyword))
    if subject_id:
        base_query = base_query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        # 历史数据错位：type_id=1 和 type_id=3 都表示"单选题"，筛选单选题时同时命中两者
        if type_id == 1:
            base_query = base_query.filter(QuestionBank.type_id.in_([1, 3]))
        else:
            base_query = base_query.filter(QuestionBank.type_id == type_id)
    if audit_status is not None:
        base_query = base_query.filter(QuestionBank.audit_status == audit_status)

    total = base_query.count()
    # 按 ID 严格升序（用户要求，之前是倒序）
    questions = base_query.order_by(
        QuestionBank.question_id.asc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    import re as _re
    items = []
    for q in questions:
        # 列表摘要：先移除 img 标签再截断，避免标签被切断导致前端显示断裂的 <img> 文本
        _summary = q.question_content or ""
        _summary = _re.sub(r'<img[^>]*>?', '[图片]', _summary)
        items.append({
            "question_id": q.question_id,
            "subject_id": q.subject_id,
            "subject_name": q.subject.subject_name if q.subject else "",
            "type_id": q.type_id,
            "type_name": q.type.type_name if q.type else "",
            "question_content": _summary[:100],
            "full_content": q.question_content,
            "options": q.options,
            "answer": q.answer,
            "answer_analysis": q.answer_analysis or "",
            "requirements": q.requirements or "",
            "difficulty": q.difficulty,
            "score": float(q.score) if q.score else 0,
            "audit_status": q.audit_status,
            "audit_comment": q.audit_comment,
            "creator_id": q.creator_id,
            "source": q.source or "",
            "year": q.year,
            "create_time": q.create_time.isoformat() if q.create_time else None,
            "status": q.status,
            "xingce_subcategory": q.xingce_subcategory,
            "shenlun_subcategory": q.shenlun_subcategory,
            "gongzhuan_subcategory": q.gongzhuan_subcategory,
            # B4/P1-2: 题组标记（>0 表示复合题小题，前端详情弹窗据此聚合渲染材料）
            "group_id": q.group_id or 0,
        })

    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


@router.put("/questions/{question_id}", summary="编辑题目")
async def update_question(
    question_id: int,
    data: QuestionUpdateRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员编辑题目（题干/选项/答案/解析/科目/题型/难度/来源）"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    update_data = data.model_dump(exclude_unset=True)
    material_keys = ("group_id", "shared_content", "shared_content_images")
    material_data = {k: update_data.pop(k) for k in material_keys if k in update_data}
    try:
        for key, value in update_data.items():
            setattr(q, key, value)
        if material_data:
            upsert_question_material(
                db,
                q,
                group_id=material_data.get("group_id"),
                shared_content=material_data.get("shared_content"),
                shared_content_images=material_data.get("shared_content_images"),
                current_user=current_user,
            )
        q.update_time = datetime.now()
        db.commit()
    except PermissionError:
        db.rollback()
        raise HTTPException(status_code=403, detail="无权修改此题目材料")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))

    record_operation(db, current_user, "UPDATE", "题库管理",
                     f"编辑题目 {question_id}")
    return {"success": True, "message": "题目已更新"}


@router.put("/questions/{question_id}/audit", summary="审核题目")
async def audit_question(
    question_id: int,
    data: QuestionAuditRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员审核题目"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    q.audit_status = data.audit_status
    q.audit_comment = data.audit_comment
    q.auditor_id = current_user.user_id
    q.update_time = datetime.now()
    db.commit()

    status_text = {0: "待审核", 1: "通过", 2: "驳回"}.get(data.audit_status, "未知")
    record_operation(db, current_user, "AUDIT", "题库管理",
                     f"审核题目 {question_id}: {status_text}")

    return {"success": True, "message": f"题目已{status_text}"}


@router.put("/questions/{question_id}/archive", summary="归档题目")
async def archive_question(
    question_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """软删除/归档题目"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    q.status = 0
    q.update_time = datetime.now()
    db.commit()

    record_operation(db, current_user, "DELETE", "题库管理", f"归档题目 {question_id}")
    return {"success": True, "message": "题目已归档"}


# ==================== 公告管理 ====================

@router.get("/announcements", summary="公告列表")
async def list_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取公告列表"""
    base_query = db.query(SysAnnouncement).filter(SysAnnouncement.status == 1)
    total = base_query.count()
    items = base_query.order_by(
        desc(SysAnnouncement.publish_time), desc(SysAnnouncement.announcement_id)
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True, "total": total, "page": page, "page_size": page_size,
        "items": [{
            "announcement_id": a.announcement_id,
            "title": a.title,
            "content": a.content,
            "level": a.level,
            "target_role": a.target_role,
            "is_pinned": a.is_pinned,
            "view_count": a.view_count,
            "publish_time": a.publish_time.isoformat() if a.publish_time else None,
            "expire_time": a.expire_time.isoformat() if a.expire_time else None,
        } for a in items]
    }


@router.post("/announcements", summary="创建公告")
async def create_announcement(
    data: AnnouncementCreate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员发布系统公告"""
    announcement = SysAnnouncement(
        title=data.title,
        content=data.content,
        level=data.level,
        target_role=data.target_role,
        publisher_id=current_user.user_id,
        is_pinned=data.is_pinned,
        expire_time=data.expire_time,
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    record_operation(db, current_user, "CREATE", "公告管理", f"发布公告: {data.title}")
    return {"success": True, "message": "公告已发布", "announcement_id": announcement.announcement_id}


@router.put("/announcements/{announcement_id}", summary="编辑公告")
async def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """编辑公告"""
    a = db.query(SysAnnouncement).filter(
        SysAnnouncement.announcement_id == announcement_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="公告不存在")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(a, key, value)
    db.commit()

    return {"success": True, "message": "公告已更新"}


@router.delete("/announcements/{announcement_id}", summary="删除公告")
async def delete_announcement(
    announcement_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """删除公告（软删除）"""
    a = db.query(SysAnnouncement).filter(
        SysAnnouncement.announcement_id == announcement_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="公告不存在")

    a.status = 0
    db.commit()
    record_operation(db, current_user, "DELETE", "公告管理", f"删除公告: {a.title}")
    return {"success": True, "message": "公告已删除"}


# ==================== 日志审计 ====================

@router.get("/logs", summary="操作日志列表")
async def list_operation_logs(
    keyword: Optional[str] = Query(None, description="操作人"),
    operation_type: Optional[str] = Query(None),
    module_name: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """分页查询操作日志"""
    query = db.query(SysOperationLog)

    if keyword:
        query = query.filter(SysOperationLog.user_name.contains(keyword))
    if operation_type:
        query = query.filter(SysOperationLog.operation_type == operation_type)
    if module_name:
        query = query.filter(SysOperationLog.module_name == module_name)
    if start_date:
        query = query.filter(SysOperationLog.operation_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(SysOperationLog.operation_time <= datetime.fromisoformat(end_date))

    total = query.count()
    logs = query.order_by(desc(SysOperationLog.operation_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True, "total": total, "page": page, "page_size": page_size,
        "items": [{
            "log_id": l.log_id,
            "user_name": l.user_name,
            "user_role": l.user_role or "-",
            "operation_type": _translate_operation_type(l.operation_type),
            "module_name": _translate_module_name(l.module_name),
            "operation_desc": l.operation_desc,
            "request_method": l.request_method,
            "request_url": l.request_url,
            "ip_address": l.ip_address,
            "success": (l.response_result == "success") if l.response_result else False,
            "status_cn": RESULT_CN.get(l.response_result or "", "未知"),
            "operation_time": l.operation_time.isoformat() if l.operation_time else None,
            "duration": l.duration,
        } for l in logs]
    }


@router.get("/logs/errors", summary="错误日志统计")
async def get_error_logs(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取最近的错误日志（response_result非success的记录）"""
    errors = db.query(SysOperationLog).filter(
        SysOperationLog.response_result != "success"
    ).order_by(desc(SysOperationLog.operation_time)).limit(50).all()

    return {
        "success": True,
        "total": len(errors),
        "items": [{
            "log_id": e.log_id,
            "user_name": e.user_name,
            "operation_type": _translate_operation_type(e.operation_type),
            "module_name": _translate_module_name(e.module_name),
            "operation_desc": e.operation_desc,
            "request_url": e.request_url,
            "response_result": RESULT_CN.get(e.response_result or "", e.response_result or "未知"),
            "operation_time": e.operation_time.isoformat() if e.operation_time else None,
        } for e in errors]
    }


@router.get("/logs/export", summary="导出操作日志(CSV)")
async def export_operation_logs(
    keyword: Optional[str] = Query(None, description="操作人"),
    operation_type: Optional[str] = Query(None),
    module_name: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """导出操作日志为 CSV 文件（UTF-8 BOM 便于 Excel 打开）"""
    query = db.query(SysOperationLog)
    if keyword:
        query = query.filter(SysOperationLog.user_name.contains(keyword))
    if operation_type:
        query = query.filter(SysOperationLog.operation_type == operation_type)
    if module_name:
        query = query.filter(SysOperationLog.module_name == module_name)
    if start_date:
        query = query.filter(SysOperationLog.operation_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(SysOperationLog.operation_time <= datetime.fromisoformat(end_date))

    logs = query.order_by(desc(SysOperationLog.operation_time)).limit(5000).all()

    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    # 表头
    writer.writerow(["日志ID", "操作用户", "角色", "操作类型", "模块", "操作描述",
                     "请求URL", "IP地址", "操作时间", "耗时(ms)"])
    for l in logs:
        writer.writerow([
            l.log_id, l.user_name, l.user_role or "-",
            _translate_operation_type(l.operation_type),
            _translate_module_name(l.module_name),
            l.operation_desc, l.request_url, l.ip_address,
            (l.operation_time.isoformat() if l.operation_time else ""),
            l.duration or 0,
        ])

    csv_content = buf.getvalue()
    # 加 BOM 防止 Excel 中文乱码
    bom = "\ufeff" + csv_content
    record_operation(db, current_user, "EXPORT", "日志审计",
                     f"导出操作日志 {len(logs)} 条")
    return Response(
        content=bom.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="operation_logs.csv"'}
    )


# ==================== 数据备份 ====================

@router.get("/backup/stats", summary="备份统计信息")
async def get_backup_stats(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取数据库大小、备份存储占用、自动备份开关等统计信息"""
    # backend 根目录 = admin.py 向上 4 层（backend/app/api/v1/admin.py → backend/）
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    # 数据库文件大小（优先用 settings.SQLITE_PATH 配置，回退到 data/question_bank.db）
    db_size = 0
    try:
        from ....core.config import settings
        sqlite_path = settings.SQLITE_PATH
        db_candidates = [os.path.join(backend_root, sqlite_path.lstrip("./")),
                         os.path.join(backend_root, "data", "question_bank.db"),
                         os.path.join(backend_root, "question_bank.db")]
        for db_path in db_candidates:
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                break
    except Exception:
        db_size = 0

    # 备份目录占用
    backup_dir = os.path.join(backend_root, "backups")
    backup_size = 0
    if os.path.exists(backup_dir):
        for f in os.listdir(backup_dir):
            fp = os.path.join(backup_dir, f)
            if os.path.isfile(fp):
                backup_size += os.path.getsize(fp)

    # 自动备份开关（从系统配置读取，默认关闭）
    auto_backup = False
    config = db.query(SysConfig).filter(SysConfig.config_key == "auto_backup").first()
    if config and config.config_value.lower() in ("true", "1", "on"):
        auto_backup = True

    return {
        "success": True,
        "db_size": db_size,
        "backup_size": backup_size,
        "auto_backup": auto_backup,
    }


@router.post("/backup", summary="手动备份数据库")
async def create_backup(
    data: BackupCreateRequest,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """创建数据库备份（SQLite导出）"""
    # backend 根目录 = admin.py 向上 4 层（backend/app/api/v1/admin.py → backend/）
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    backup_dir = os.path.join(backend_root, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # 备份显示名使用中文（不含时间戳）；文件名用时间戳保证唯一，避免同名覆盖
    backup_name = data.backup_name or "系统全量备份"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(backup_dir, f"{timestamp}_{backup_name}.sql")

    backup_record = SysBackupRecord(
        backup_type=data.backup_type,
        backup_name=backup_name,
        file_path=file_path,
        file_size=0,
        status="running",
        operator_id=current_user.user_id,
    )
    db.add(backup_record)
    db.commit()
    db.refresh(backup_record)

    try:
        # SQLite 备份：导出所有表为SQL
        import sqlite3
        db_path = os.path.join(backend_root, "data", "question_bank.db")
        if os.path.exists(db_path):
            src = sqlite3.connect(db_path)
            with open(file_path, 'w', encoding='utf-8') as f:
                for line in src.iterdump():
                    f.write(f"{line}\n")
            src.close()
            file_size = os.path.getsize(file_path)
        else:
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")

        backup_record.file_size = file_size
        backup_record.status = "completed"
        backup_record.end_time = datetime.now()
        db.commit()

        record_operation(db, current_user, "BACKUP", "数据备份",
                         f"完成备份: {backup_name} ({file_size} bytes)")
        return {"success": True, "message": "备份完成", "backup_id": backup_record.backup_id,
                "file_size": file_size}

    except Exception as e:
        backup_record.status = "failed"
        backup_record.error_message = str(e)
        backup_record.end_time = datetime.now()
        db.commit()
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")


@router.get("/backups", summary="备份记录列表")
async def list_backups(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取备份记录"""
    backups = db.query(SysBackupRecord).order_by(
        desc(SysBackupRecord.start_time)
    ).limit(50).all()

    return {
        "success": True,
        "items": [{
            "backup_id": b.backup_id,
            "backup_name": b.backup_name,
            "backup_type": b.backup_type,
            "file_path": b.file_path,
            "file_size": b.file_size,
            "status": b.status,
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "end_time": b.end_time.isoformat() if b.end_time else None,
        } for b in backups]
    }


@router.post("/backups/{backup_id}/restore", summary="恢复备份")
async def restore_backup(
    backup_id: int,
    data: BackupRestoreRequest,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """从备份恢复数据库（需超级管理员二次确认）"""
    if not data.confirm:
        raise HTTPException(status_code=400, detail="需要确认恢复操作")

    backup = db.query(SysBackupRecord).filter(
        SysBackupRecord.backup_id == backup_id
    ).first()
    if not backup or backup.status != "completed":
        raise HTTPException(status_code=404, detail="备份记录不存在或未完成")

    if not os.path.exists(backup.file_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    record_operation(db, current_user, "RESTORE", "数据备份",
                     f"恢复备份: {backup.backup_name}")
    return {"success": True, "message": "备份恢复请求已提交，请手动执行数据库恢复操作"}


# ==================== 系统设置 ====================

@router.get("/settings", summary="获取系统设置")
async def get_settings(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取所有系统配置"""
    configs = db.query(SysConfig).filter(SysConfig.config_key != None).all()
    settings = {}
    for c in configs:
        settings[c.config_key] = {
            "value": c.config_value,
            "desc": c.config_desc,
            "type": c.config_type,
        }
    return {"success": True, "settings": settings}


@router.put("/settings", summary="更新系统设置")
async def update_settings(
    data: SystemSettingsUpdate,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """更新系统配置（仅超级管理员）"""
    for key, value in data.settings.items():
        config = db.query(SysConfig).filter(SysConfig.config_key == key).first()
        if config:
            config.config_value = str(value)
            config.update_time = datetime.now()
        else:
            db.add(SysConfig(config_key=key, config_value=str(value)))

    db.commit()
    record_operation(db, current_user, "UPDATE", "系统设置", f"更新系统设置: {list(data.settings.keys())}")
    return {"success": True, "message": "设置已更新"}


# ==================== 权限管理 ====================

ROLE_NAME_CN = {"student": "学生", "teacher": "教师", "admin": "管理员"}


def _permission_groups() -> List[dict]:
    """把 33 项按 group 聚成前端可直接渲染的分组。"""
    groups: dict[str, List[dict]] = {}
    for permission in Permission:
        meta = PERMISSION_META[permission]
        groups.setdefault(meta["group"], []).append({
            "code": permission.value,
            "label": meta["label"],
            "risk": meta["risk"],
            "description": meta["description"],
        })
    return [{"name": name, "permissions": items} for name, items in groups.items()]


@router.get("/permissions", summary="获取权限配置")
async def get_permissions(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取角色权限配置 + 33 项目录；保留旧字段供旧页回滚。"""
    from ....core.security import ROLE_PERMISSIONS, SUPER_ADMIN_PERMISSIONS

    name_map = {p.value: PERMISSION_META[p]["label"] for p in Permission}
    roles_config = {}
    for role_key, perms in ROLE_PERMISSIONS.items():
        # ROLE_PERMISSIONS 的键是 UserRole 枚举；SysConfig 键与前端角色名都用字符串值。
        role = role_key.value if hasattr(role_key, "value") else role_key
        perm_list = [p.value for p in perms]
        if role == "admin":
            perm_list = list(dict.fromkeys(
                perm_list + [p.value for p in SUPER_ADMIN_PERMISSIONS]
            ))
        # 若该角色有自定义权限配置（SysConfig），则显示自定义配置（当前实际生效值）
        config = db.query(SysConfig).filter(
            SysConfig.config_key == f"role_permissions_{role}"
        ).first()
        if config and config.config_value:
            try:
                custom_list = json.loads(config.config_value)
                if custom_list:
                    perm_list = custom_list
                    if role == "admin":
                        # 超管附加权限不可被模板编辑移除
                        perm_list = list(dict.fromkeys(
                            perm_list + [p.value for p in SUPER_ADMIN_PERMISSIONS]
                        ))
            except Exception:
                pass
        roles_config[role] = {
            "role_name": ROLE_NAME_CN.get(role, role),
            "permissions": perm_list,
            "permission_names": {p: name_map.get(p, p) for p in perm_list},
            "description": {
                "student": "查看题目、参加考试、使用 AI 助手",
                "teacher": "管理题目、创建试卷、查看成绩",
                "admin": "用户管理、系统配置、数据审计",
            }.get(role, "")
        }

    return {
        "success": True,
        "roles": roles_config,
        "permission_names": name_map,
        "catalog": permission_catalog(),
        "groups": _permission_groups(),
        "total": len(Permission),
    }


@router.get("/permissions/catalog", summary="权限目录（33 项元数据）")
async def get_permission_catalog(
    current_user: SysUser = Depends(get_current_admin),
):
    """权限矩阵的唯一目录来源：分组、风险等级、范围支持与说明。"""
    return {
        "success": True,
        "total": len(Permission),
        "catalog": permission_catalog(),
        "groups": _permission_groups(),
        "protected_permissions": sorted(p.value for p in PROTECTED_PERMISSIONS),
    }


@router.get("/users/{user_id}/permissions", summary="用户权限详情")
async def get_user_permissions_detail(
    user_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """返回角色基线 / 能力包 / 加授 / 拒绝 / 有效权限，供 Tri-state 矩阵。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    return {
        "success": True,
        "user_id": user.user_id,
        "username": user.username,
        "role": {"user_type": user.user_type, "role_level": user.role_level},
        **_permission_detail(user, db),
    }


@router.put("/users/{user_id}/permissions", summary="修改用户权限覆盖")
async def update_user_permissions_detail(
    user_id: int,
    data: UserPermissionUpdate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """单用户加授/拒绝/恢复继承；关键权限仅超管，非超管只能授出自己已有的权限。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or (getattr(user, "is_deleted", 0) or 0) != 0:
        raise HTTPException(status_code=404, detail="用户不存在或已在回收站")
    _assert_can_manage_target(current_user, user)

    codes = [item.permission_code for item in data.changes]
    if len(set(codes)) != len(codes):
        raise HTTPException(status_code=400, detail="同一权限码不能重复提交")

    before_effective = set(get_effective_permissions(user, db))
    operator_effective = set(get_effective_permissions(current_user, db))
    existing_rows = {
        row.permission_code: row
        for row in db.query(UserPermissionOverride).filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.scope_type == "global",
        ).all()
    }
    before_snapshot = {
        code: {
            "effect": row.effect,
            "status": row.status,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
        for code, row in existing_rows.items()
    }
    after_snapshot = {}
    batch_id = str(uuid.uuid4())
    changed = 0

    for item in data.changes:
        permission = Permission._value2member_map_.get(item.permission_code)
        if permission is None:
            raise HTTPException(
                status_code=422,
                detail=f"权限码不存在: {item.permission_code}",
            )
        if item.effect not in ("grant", "deny", "inherit"):
            raise HTTPException(status_code=400, detail=f"无效的 effect: {item.effect}")
        meta = PERMISSION_META[permission]
        if meta["risk"] == "critical" and current_user.role_level < 3:
            raise HTTPException(status_code=403, detail=f"只有超级管理员可以变更关键权限: {item.permission_code}")
        if item.effect == "grant" and current_user.role_level < 3 and permission not in operator_effective:
            raise HTTPException(
                status_code=403,
                detail=f"不能授出自己不具备的权限: {item.permission_code}",
            )
        if (
            item.effect == "deny"
            and user.role_level >= 3
            and permission in PROTECTED_PERMISSIONS
        ):
            raise HTTPException(status_code=409, detail=f"不能拒绝超管保护权限: {item.permission_code}")

        row = existing_rows.get(item.permission_code)
        if item.effect == "inherit":
            if row and row.status == "active":
                row.status = "revoked"
                row.revoked_by = current_user.user_id
                row.revoked_at = datetime.now()
                row.updated_at = datetime.now()
                changed += 1
                after_snapshot[item.permission_code] = {"effect": "inherit", "status": "revoked"}
            continue

        expires_at = _normalize_expiry(item.expires_at)
        if row is None:
            row = UserPermissionOverride(
                user_id=user_id,
                permission_code=item.permission_code,
                effect=item.effect,
                scope_type="global",
                scope_id=0,
                scope_key="",
                status="active",
                reason=data.reason,
                granted_by=current_user.user_id,
                granted_at=datetime.now(),
                expires_at=expires_at,
                batch_id=batch_id,
                updated_at=datetime.now(),
            )
            db.add(row)
            existing_rows[item.permission_code] = row
        else:
            row.effect = item.effect
            row.status = "active"
            row.reason = data.reason
            row.granted_by = current_user.user_id
            row.granted_at = datetime.now()
            row.expires_at = expires_at
            row.revoked_by = None
            row.revoked_at = None
            row.batch_id = batch_id
            row.updated_at = datetime.now()
        changed += 1
        after_snapshot[item.permission_code] = {
            "effect": item.effect,
            "status": "active",
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

    if changed == 0:
        db.rollback()
        return {
            "success": True,
            "message": "没有需要变更的权限",
            "batch_id": None,
            "summary": {"added": 0, "removed": 0, "changed": 0},
        }

    _write_batch(
        db, current_user, "single_user_permissions", 1, data.reason,
        {"user_id": user_id, "overrides": before_snapshot},
        {"user_id": user_id, "overrides": after_snapshot},
        batch_id=batch_id,
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    after_effective = set(get_effective_permissions(user, db))
    record_operation(
        db, current_user, "UPDATE", "权限管理",
        f"修改用户 {user.username}(ID:{user_id}) 权限 {changed} 项；原因: {data.reason}",
    )
    return {
        "success": True,
        "message": "权限已更新",
        "batch_id": batch_id,
        "summary": {
            "changed": changed,
            "added": len(after_effective - before_effective),
            "removed": len(before_effective - after_effective),
            "unchanged": len(after_effective & before_effective),
        },
        "effective_permissions": sorted(p.value for p in after_effective),
    }


def _permission_batch_plan(db: Session, operator: SysUser, data: PermissionBatchRequest):
    """解析目标/权限/到期时间并给出冲突，供预览与应用共用。"""
    users = _resolve_permission_batch_targets(db, data.target, operator)
    permissions = _validate_batch_permissions(db, operator, data.permissions, data.operation)
    expires_at = _normalize_expiry(data.expires_at)
    codes = [p.value for p in permissions]
    user_ids = [u.user_id for u in users]
    rows = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id.in_(user_ids),
        UserPermissionOverride.permission_code.in_(codes),
        UserPermissionOverride.scope_type == "global",
    ).all()
    states = _override_states(rows)
    conflicts = []
    if data.operation == "deny":
        for user in users:
            if user.role_level < 3:
                continue
            for permission in permissions:
                if permission in PROTECTED_PERMISSIONS:
                    conflicts.append({
                        "user_id": user.user_id,
                        "username": user.username,
                        "permission_code": permission.value,
                        "reason": "超级管理员保护权限不可拒绝",
                    })
    return users, permissions, expires_at, rows, states, conflicts


def _batch_summary(users, permissions, states, operation):
    summary = {"users": len(users), "added": 0, "removed": 0, "unchanged": 0}
    for user in users:
        for permission in permissions:
            key = f"{user.user_id}:{permission.value}"
            before = states.get(key, "inherit")
            if before == operation:
                summary["unchanged"] += 1
            elif operation == "grant":
                summary["added"] += 1
            elif before == "grant" and operation != "grant":
                summary["removed"] += 1
            else:
                summary["unchanged"] += 1
    return summary


@router.post("/users/permissions/preview", summary="批量权限变更预览")
async def preview_user_permissions_batch(
    data: PermissionBatchRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """计算批量差异与越权/保护冲突，不写入数据库。"""
    users, permissions, _expires_at, _rows, states, conflicts = _permission_batch_plan(
        db, current_user, data
    )
    items = []
    truncated = False
    for user in users:
        for permission in permissions:
            if len(items) >= 2000:
                truncated = True
                break
            key = f"{user.user_id}:{permission.value}"
            before = states.get(key, "inherit")
            items.append({
                "user_id": user.user_id,
                "username": user.username,
                "permission_code": permission.value,
                "before": before,
                "after": data.operation,
                "risk": PERMISSION_META[permission]["risk"],
            })
        if truncated:
            break
    return {
        "success": not conflicts,
        "dry_run": True,
        "batch_id": None,
        "summary": _batch_summary(users, permissions, states, data.operation),
        "items": items,
        "truncated": truncated,
        "conflicts": conflicts,
    }


@router.post("/users/permissions/apply", summary="批量应用权限变更")
async def apply_user_permissions_batch(
    data: PermissionBatchRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """整批写入 override，并登记可撤销批次；存在冲突时整批拒绝。"""
    users, permissions, expires_at, rows, states, conflicts = _permission_batch_plan(
        db, current_user, data
    )
    if conflicts:
        raise HTTPException(status_code=409, detail=f"批量存在 {len(conflicts)} 处冲突，整批拒绝")

    row_map = {f"{r.user_id}:{r.permission_code}": r for r in rows}
    batch_id = str(uuid.uuid4())
    before_snapshot = {}
    after_snapshot = {}
    changed = 0
    now = datetime.now()
    for user in users:
        for permission in permissions:
            key = f"{user.user_id}:{permission.value}"
            current = states.get(key, "inherit")
            before_snapshot[key] = {"effect": current, "status": "active" if current != "inherit" else "revoked"}
            after_snapshot[key] = {
                "effect": data.operation,
                "status": "active" if data.operation != "inherit" else "revoked",
            }
            row = row_map.get(key)
            if data.operation == "inherit":
                if row and row.status == "active":
                    row.status = "revoked"
                    row.revoked_by = current_user.user_id
                    row.revoked_at = now
                    row.updated_at = now
                    changed += 1
                continue
            if row is None:
                row = UserPermissionOverride(
                    user_id=user.user_id,
                    permission_code=permission.value,
                    effect=data.operation,
                    scope_type="global",
                    scope_id=0,
                    scope_key="",
                    status="active",
                    reason=data.reason,
                    granted_by=current_user.user_id,
                    granted_at=now,
                    expires_at=expires_at,
                    batch_id=batch_id,
                    updated_at=now,
                )
                db.add(row)
                row_map[key] = row
            else:
                row.effect = data.operation
                row.status = "active"
                row.reason = data.reason
                row.granted_by = current_user.user_id
                row.granted_at = now
                row.expires_at = expires_at
                row.revoked_by = None
                row.revoked_at = None
                row.batch_id = batch_id
                row.updated_at = now
            changed += 1

    if changed == 0:
        db.rollback()
        return {
            "success": True,
            "batch_id": None,
            "message": "没有需要变更的权限",
            "summary": _batch_summary(users, permissions, states, data.operation),
            "items": [],
            "conflicts": [],
        }

    _write_batch(
        db, current_user, "batch_user_permissions", len(users), data.reason,
        {"overrides": before_snapshot}, {"overrides": after_snapshot}, batch_id=batch_id,
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_operation(
        db, current_user, "UPDATE", "权限管理",
        f"批量{data.operation} {len(users)} 人 × {len(permissions)} 项；原因: {data.reason}",
    )
    items = []
    for user in users:
        for permission in permissions:
            key = f"{user.user_id}:{permission.value}"
            items.append({
                "user_id": user.user_id,
                "username": user.username,
                "permission_code": permission.value,
                "before": states.get(key, "inherit"),
                "after": data.operation,
                "risk": PERMISSION_META[permission]["risk"],
            })
    return {
        "success": True,
        "batch_id": batch_id,
        "summary": _batch_summary(users, permissions, states, data.operation),
        "items": items[:2000],
        "truncated": len(items) > 2000,
        "conflicts": [],
    }


@router.post("/permission-batches/{batch_id}/undo", summary="撤销权限变更批次")
async def undo_permission_batch(
    batch_id: str,
    data: PermissionBatchUndoRequest,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """仅超管、10 分钟内可撤销；当前值偏离批次结果时整批拒绝。"""
    batch = db.query(PermissionChangeBatch).filter(
        PermissionChangeBatch.batch_id == batch_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    if batch.undone_at:
        raise HTTPException(status_code=409, detail="该批次已撤销")
    if batch.undo_deadline and datetime.now() > batch.undo_deadline:
        raise HTTPException(status_code=409, detail="已超过 10 分钟撤销窗口")

    if batch.action == "role_template_update":
        try:
            before_payload = json.loads(batch.before_json or "{}")
            after_payload = json.loads(batch.after_json or "{}")
        except ValueError:
            raise HTTPException(status_code=500, detail="批次快照损坏")
        role = after_payload.get("role")
        after_permissions = after_payload.get("permissions") or []
        before_permissions = before_payload.get("permissions") or []
        if not role:
            raise HTTPException(status_code=409, detail="批次缺少角色信息")
        config = db.query(SysConfig).filter(
            SysConfig.config_key == f"role_permissions_{role}"
        ).first()
        if not config:
            raise HTTPException(status_code=409, detail="角色模板已不存在")
        try:
            current_permissions = json.loads(config.config_value or "[]")
        except ValueError:
            raise HTTPException(status_code=409, detail="角色模板配置损坏")
        if sorted(current_permissions) != sorted(after_permissions):
            raise HTTPException(status_code=409, detail="角色模板已被后续修改，拒绝撤销")
        config.config_value = json.dumps(before_permissions, ensure_ascii=False)
        batch.undone_at = datetime.now()
        batch.undone_by = current_user.user_id
        batch.updated_at = datetime.now()
        db.commit()
        record_operation(db, current_user, "UPDATE", "权限管理", f"撤销角色模板批次 {batch_id}")
        return {"success": True, "batch_id": batch_id, "undone_at": batch.undone_at.isoformat()}

    try:
        before_payload = json.loads(batch.before_json or "{}")
        after_payload = json.loads(batch.after_json or "{}")
        before = before_payload.get("overrides", {})
        after = after_payload.get("overrides", {})
    except ValueError:
        raise HTTPException(status_code=500, detail="批次快照损坏")
    if not after:
        raise HTTPException(status_code=409, detail="批次没有可撤销的权限变更")

    # 两种历史格式：批量批次键为 "user_id:code"，单用户批次旧数据键仅为 code。
    scoped_keys = all(
        ":" in key and key.split(":", 1)[0].isdigit() for key in after
    )
    if scoped_keys:
        user_ids = sorted({int(key.split(":", 1)[0]) for key in after})
        codes = sorted({key.split(":", 1)[1] for key in after})
    else:
        codes = sorted({key for key in after})
        target_user_id = after_payload.get("user_id") or before_payload.get("user_id")
        if target_user_id:
            user_ids = [int(target_user_id)]
        else:
            # 兼容修复前写入的单用户批次：变更行上仍带 batch_id，可反查目标用户。
            batch_rows = db.query(UserPermissionOverride).filter(
                UserPermissionOverride.batch_id == batch.batch_id,
            ).all()
            user_ids = sorted({r.user_id for r in batch_rows})
        if len(user_ids) != 1:
            raise HTTPException(status_code=409, detail="批次缺少唯一目标用户，无法撤销")
        target_user_id = user_ids[0]
        after = {f"{target_user_id}:{key}": value for key, value in after.items()}
        before = {f"{target_user_id}:{key}": value for key, value in before.items()}

    rows = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id.in_(user_ids),
        UserPermissionOverride.permission_code.in_(codes),
        UserPermissionOverride.scope_type == "global",
        UserPermissionOverride.status == "active",
    ).all()
    current_states = _override_states(rows)
    conflicts = []
    for key, expected in after.items():
        current = current_states.get(key, "inherit")
        if current != expected.get("effect"):
            conflicts.append({"key": key, "current": current, "expected": expected.get("effect")})
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"message": "批次结果已被后续修改，整批拒绝撤销", "conflicts": conflicts[:50]},
        )

    now = datetime.now()
    row_map = {f"{r.user_id}:{r.permission_code}": r for r in rows}
    all_rows = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.user_id.in_(user_ids),
        UserPermissionOverride.permission_code.in_(codes),
        UserPermissionOverride.scope_type == "global",
    ).all()
    for key in after:
        target = before.get(key, {"effect": "inherit"})
        user_id, code = key.split(":", 1)
        row = row_map.get(key)
        if not row:
            row = next(
                (r for r in all_rows if str(r.user_id) == user_id and r.permission_code == code),
                None,
            )
        if target.get("effect") == "inherit" or target.get("status") == "revoked":
            if row and row.status == "active":
                row.status = "revoked"
                row.revoked_by = current_user.user_id
                row.revoked_at = now
                row.updated_at = now
            continue
        expires_raw = target.get("expires_at")
        expires_at = datetime.fromisoformat(expires_raw) if expires_raw else None
        if row is None:
            row = UserPermissionOverride(
                user_id=int(user_id), permission_code=code,
                effect=target["effect"], scope_type="global", scope_id=0, scope_key="",
                status="active", reason=f"撤销批次: {data.reason}",
                granted_by=current_user.user_id, granted_at=now,
                expires_at=expires_at, batch_id=batch.batch_id, updated_at=now,
            )
            db.add(row)
        else:
            row.effect = target["effect"]
            row.status = "active"
            row.reason = f"撤销批次: {data.reason}"
            row.granted_by = current_user.user_id
            row.granted_at = now
            row.expires_at = expires_at
            row.revoked_by = None
            row.revoked_at = None
            row.updated_at = now
    batch.undone_at = now
    batch.undone_by = current_user.user_id
    batch.updated_at = now
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    record_operation(db, current_user, "UPDATE", "权限管理", f"撤销权限批次 {batch_id}")
    return {"success": True, "batch_id": batch_id, "undone_at": now.isoformat()}


@router.get("/permission-audit", summary="权限变更审计")
async def list_permission_audit(
    page: int = 1,
    page_size: int = 20,
    operator_id: Optional[int] = None,
    action: Optional[str] = None,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """按批次列出权限变更，含撤销窗口状态。"""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    query = db.query(PermissionChangeBatch)
    if operator_id:
        query = query.filter(PermissionChangeBatch.operator_id == operator_id)
    if action:
        query = query.filter(PermissionChangeBatch.action == action)
    total = query.count()
    rows = query.order_by(PermissionChangeBatch.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    operator_ids = {r.operator_id for r in rows}
    operators = {
        u.user_id: u.username
        for u in db.query(SysUser).filter(SysUser.user_id.in_(operator_ids)).all()
    } if operator_ids else {}
    now = datetime.now()
    items = [{
        "batch_id": r.batch_id,
        "operator_id": r.operator_id,
        "operator": operators.get(r.operator_id, ""),
        "action": r.action,
        "target_count": r.target_count,
        "reason": r.reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "undo_deadline": r.undo_deadline.isoformat() if r.undo_deadline else None,
        "undone_at": r.undone_at.isoformat() if r.undone_at else None,
        "can_undo": bool(
            not r.undone_at and r.undo_deadline and now <= r.undo_deadline
        ),
    } for r in rows]
    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/permission-health", summary="权限健康扫描")
async def permission_health(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """检查最后超管、过期授权、孤儿覆盖与保护权限异常。"""
    now = datetime.now()
    active_users = db.query(SysUser).filter(SysUser.is_deleted == 0).all()
    supers = [u for u in active_users if u.role_level >= 3 and u.is_disabled == 0]
    overrides = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.status == "active",
        UserPermissionOverride.scope_type == "global",
    ).all()
    user_ids = {u.user_id for u in active_users}
    expired = [r for r in overrides if r.expires_at and r.expires_at <= now]
    expiring = [
        r for r in overrides
        if r.expires_at and now < r.expires_at <= now + timedelta(days=7)
    ]
    orphan = [r for r in overrides if r.user_id not in user_ids]
    ignored_protected_deny = sum(
        1 for r in overrides
        if r.effect == "deny" and r.permission_code in {p.value for p in PROTECTED_PERMISSIONS}
        and any(u.user_id == r.user_id and u.role_level >= 3 for u in active_users)
    )
    alerts = []
    if len(supers) <= 1:
        alerts.append({"level": "critical", "code": "LAST_SUPER", "message": "仅剩 1 个可用超级管理员"})
    if ignored_protected_deny:
        alerts.append({
            "level": "warning", "code": "PROTECTED_DENY_IGNORED",
            "message": f"{ignored_protected_deny} 条超管保护权限拒绝已被忽略",
        })
    if orphan:
        alerts.append({"level": "warning", "code": "ORPHAN_OVERRIDE", "message": f"{len(orphan)} 条覆盖指向不存在用户"})
    if expired:
        alerts.append({"level": "info", "code": "EXPIRED_OVERRIDE", "message": f"{len(expired)} 条覆盖已过期"})
    return {
        "success": True,
        "checked_at": now.isoformat(),
        "stats": {
            "active_users": len(active_users),
            "super_admins": len(supers),
            "active_overrides": len(overrides),
            "expiring_7d": len(expiring),
            "expired": len(expired),
            "orphan": len(orphan),
        },
        "alerts": alerts,
    }


@router.put("/permissions", summary="更新权限配置")
async def update_permissions(
    data: PermissionRoleUpdate,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """更新角色权限模板（仅超管）；保留旧接口，同时写变更批次。"""
    if data.role not in ("student", "teacher", "admin"):
        raise HTTPException(status_code=400, detail="无效的角色")
    unknown = [p for p in data.permissions if p not in Permission._value2member_map_]
    if unknown:
        raise HTTPException(status_code=422, detail=f"权限码不存在: {unknown[0]}")

    permission_values = list(dict.fromkeys(data.permissions))
    if data.role == "admin":
        # 超管保护项不可从模板中移除，否则一次误操作会锁死管理入口。
        required = {
            p.value for p in (PROTECTED_PERMISSIONS | set(SUPER_ADMIN_PERMISSIONS))
        }
        permission_values = list(dict.fromkeys(permission_values + sorted(required)))

    before_config = db.query(SysConfig).filter(
        SysConfig.config_key == f"role_permissions_{data.role}"
    ).first()
    before_value = before_config.config_value if before_config else None
    perm_str = json.dumps(permission_values, ensure_ascii=False)
    if before_config:
        before_config.config_value = perm_str
    else:
        db.add(SysConfig(
            config_key=f"role_permissions_{data.role}",
            config_value=perm_str,
            config_desc=f"{data.role}角色权限配置",
            config_type="JSON"
        ))
    batch_id = _write_batch(
        db, current_user, "role_template_update", 0, data.reason or f"更新 {data.role} 角色模板",
        {"role": data.role, "permissions": json.loads(before_value) if before_value else []},
        {"role": data.role, "permissions": permission_values},
    )
    db.commit()

    record_operation(db, current_user, "UPDATE", "权限管理",
                     f"更新 {data.role} 角色权限: {len(permission_values)} 项；原因: {data.reason or '未填写'}")
    return {
        "success": True,
        "message": f"{data.role} 角色权限已更新",
        "batch_id": batch_id,
        "permissions": permission_values,
    }
