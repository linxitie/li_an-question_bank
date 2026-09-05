"""
管理员端 API — 用户管理、系统设置、日志审计、数据备份、权限管理
"""
import os
import json
import logging
import secrets
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from ...core.database import get_db, engine
from ...core.security import (
    get_current_admin, get_current_super_admin, get_password_hash,
    check_permission, Permission
)
from ...models.models import (
    SysUser, SysOperationLog, SysConfig, SysAnnouncement,
    SysBackupRecord, SysVersion, SysDictType, SysDictData,
    School, QuestionBank, ExamPaper, ExamRecord, PracticeRecord,
    Banji, PaperApprovalWorkflow
)
from ...schemas.admin import (
    DashboardStats, DashboardResponse, WeeklyActiveTrend,
    SubjectDistribution,
    UserCreate, UserUpdate, UserDisableRequest, UserResetPasswordRequest,
    AnnouncementCreate, AnnouncementUpdate,
    QuestionAuditRequest,
    SystemSettingsUpdate, PermissionRoleUpdate,
    BackupCreateRequest, BackupRestoreRequest,
)

router = APIRouter(prefix="/api/admin", tags=["管理员端"])
logger = logging.getLogger(__name__)

# ==================== 辅助函数 ====================

def record_operation(db: Session, user: SysUser, op_type: str, module: str,
                     desc: str, request_url: str = "", request_params: str = "",
                     ip_address: str = "", duration: int = 0):
    """记录管理员操作日志"""
    try:
        log_entry = SysOperationLog(
            user_id=user.user_id,
            user_name=user.username,
            operation_type=op_type,
            module_name=module,
            operation_desc=desc,
            request_url=request_url,
            request_params=request_params,
            ip_address=ip_address,
            duration=duration,
            response_result="success"
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"操作日志记录失败: {e}")


def _format_user(user: SysUser) -> dict:
    """格式化用户信息"""
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
        "total_coins": user.total_coins,
        "continuous_checkin_days": user.continuous_checkin_days,
        "register_time": user.register_time.isoformat() if user.register_time else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "last_login_ip": getattr(user, 'last_login_ip', ''),
    }


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
    total_papers = db.query(func.count(ExamPaper.paper_id)).scalar()

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
    distribution = SubjectDistribution(
        labels=[subject_names.get(s[0], f"科目{s[0]}") for s in subjects],
        values=[s[1] for s in subjects],
        colors=["#1A3C6D", "#C41E3A", "#409EFF"]
    )

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
    keyword: Optional[str] = Query(None, description="搜索关键词(姓名/学号)"),
    user_type: Optional[str] = Query(None, description="用户类型"),
    is_disabled: Optional[int] = Query(None, description="禁用状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """分页查询用户列表"""
    base_query = db.query(SysUser)

    if keyword:
        base_query = base_query.filter(or_(
            SysUser.username.contains(keyword),
            SysUser.user_no.contains(keyword),
            SysUser.phone.contains(keyword),
        ))
    if user_type:
        base_query = base_query.filter(SysUser.user_type == user_type)
    if is_disabled is not None:
        base_query = base_query.filter(SysUser.is_disabled == is_disabled)

    total = base_query.count()
    users = base_query.order_by(
        desc(SysUser.register_time), desc(SysUser.user_id)
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_user(u) for u in users],
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
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    record_operation(db, current_user, "UPDATE", "用户管理",
                     f"编辑用户 {user.username}(ID:{user_id})")

    return {"success": True, "message": "用户更新成功", "user": _format_user(user)}


@router.put("/users/{user_id}/disable", summary="禁用/启用用户")
async def toggle_disable_user(
    user_id: int,
    data: UserDisableRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """禁用或启用用户账号"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

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
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

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

@router.get("/questions", summary="全部题目列表（含审核）")
async def list_all_questions(
    keyword: Optional[str] = Query(None),
    subject_id: Optional[int] = Query(None),
    audit_status: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """管理员查看全部题目（含审核状态）"""
    base_query = db.query(QuestionBank)
    if keyword:
        base_query = base_query.filter(QuestionBank.question_content.contains(keyword))
    if subject_id:
        base_query = base_query.filter(QuestionBank.subject_id == subject_id)
    if audit_status is not None:
        base_query = base_query.filter(QuestionBank.audit_status == audit_status)

    total = base_query.count()
    questions = base_query.order_by(
        desc(QuestionBank.create_time), desc(QuestionBank.question_id)
    ).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for q in questions:
        items.append({
            "question_id": q.question_id,
            "subject_id": q.subject_id,
            "type_id": q.type_id,
            "type_name": q.type.type_name if q.type else "",
            "question_content": q.question_content[:100] if q.question_content else "",
            "full_content": q.question_content,
            "options": q.options,
            "answer": q.answer,
            "answer_analysis": q.answer_analysis or "",
            "difficulty": q.difficulty,
            "score": float(q.score) if q.score else 0,
            "audit_status": q.audit_status,
            "audit_comment": q.audit_comment,
            "creator_id": q.creator_id,
            "source": q.source,
            "year": q.year,
            "create_time": q.create_time.isoformat() if q.create_time else None,
            "status": q.status,
            "xingce_subcategory": q.xingce_subcategory,
            "shenlun_subcategory": q.shenlun_subcategory,
            "gongzhuan_subcategory": q.gongzhuan_subcategory,
        })

    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


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
            "operation_type": l.operation_type,
            "module_name": l.module_name,
            "operation_desc": l.operation_desc,
            "request_method": l.request_method,
            "request_url": l.request_url,
            "ip_address": l.ip_address,
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
            "operation_type": e.operation_type,
            "operation_desc": e.operation_desc,
            "request_url": e.request_url,
            "response_result": e.response_result,
            "operation_time": e.operation_time.isoformat() if e.operation_time else None,
        } for e in errors]
    }


# ==================== 数据备份 ====================

@router.post("/backup", summary="手动备份数据库")
async def create_backup(
    data: BackupCreateRequest,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """创建数据库备份（SQLite导出）"""
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = data.backup_name or f"backup_{timestamp}"
    file_path = os.path.join(backup_dir, f"{backup_name}.sql")

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
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "question_bank.db")
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

@router.get("/permissions", summary="获取权限配置")
async def get_permissions(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """获取各角色权限配置"""
    from ...core.security import ROLE_PERMISSIONS, SUPER_ADMIN_PERMISSIONS
    roles_config = {}
    for role, perms in ROLE_PERMISSIONS.items():
        perm_list = [p.value for p in perms]
        if role == "admin":
            perm_list.extend([p.value for p in SUPER_ADMIN_PERMISSIONS])
        roles_config[role] = {
            "permissions": perm_list,
            "description": {
                "student": "学生 — 查看题目、参加考试、使用AI助手",
                "teacher": "教师 — 管理题目、创建试卷、查看成绩",
                "admin": "管理员 — 用户管理、系统配置、数据审计",
            }.get(role, "")
        }

    return {"success": True, "roles": roles_config}


@router.put("/permissions", summary="更新权限配置")
async def update_permissions(
    data: PermissionRoleUpdate,
    current_user: SysUser = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """更新角色权限（仅超级管理员，存储到SysConfig）"""
    perm_str = json.dumps(data.permissions, ensure_ascii=False)
    config = db.query(SysConfig).filter(
        SysConfig.config_key == f"role_permissions_{data.role}"
    ).first()
    if config:
        config.config_value = perm_str
    else:
        db.add(SysConfig(
            config_key=f"role_permissions_{data.role}",
            config_value=perm_str,
            config_desc=f"{data.role}角色权限配置",
            config_type="JSON"
        ))
    db.commit()

    record_operation(db, current_user, "UPDATE", "权限管理",
                     f"更新 {data.role} 角色权限: {len(data.permissions)} 项")
    return {"success": True, "message": f"{data.role} 角色权限已更新"}
