from ....services.event_consumer import record_user_action
from ....core.trigger_types import TRIGGER_CHECKIN_DONE
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Form, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db, commit_with_retry
from ....models.models import SysUser
from ....schemas.schemas import UserResponse, LoginResponse, TokenData
from ....core.config import settings
from ....core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    token_manager,
    get_client_ip,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 设备管理常量
MAX_DEVICES = 3


def detect_platform(request: Request) -> str:
    """检测用户平台"""
    ua = request.headers.get("user-agent", "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    elif "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "pc"


def extract_browser(request: Request) -> str:
    """提取浏览器信息"""
    user_agent = request.headers.get("user-agent", "")
    if "Chrome" in user_agent:
        return "Chrome"
    elif "Firefox" in user_agent:
        return "Firefox"
    elif "Safari" in user_agent:
        return "Safari"
    elif "Edge" in user_agent:
        return "Edge"
    return "Unknown"


def extract_os(request: Request) -> str:
    """提取操作系统信息"""
    user_agent = request.headers.get("user-agent", "")
    if "Windows" in user_agent:
        return "Windows"
    elif "Mac" in user_agent:
        return "macOS"
    elif "Linux" in user_agent:
        return "Linux"
    elif "Android" in user_agent:
        return "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        return "iOS"
    return "Unknown"


def hash_token(token: str) -> str:
    """哈希token用于存储"""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


class RegisterForm(BaseModel):
    """注册表单"""
    username: str
    password: str
    email: Optional[str] = None
    phone: str
    user_no: Optional[str] = None
    user_type: str = "student"


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db),
        request: Request = None,
        client_type: str = Form("web", description="客户端类型: web/mobile/tablet"),
):
    """
    用户登录接口

    - 支持用户名或手机号登录
    - 返回 access_token 和 refresh_token
    - 记录登录日志
    """
    logger = logging.getLogger(__name__)

    user = db.query(SysUser).filter(
        (SysUser.username == form_data.username) |
        (SysUser.phone == form_data.username)
    ).first()

    if not user:
        logger.warning(f"登录失败: 用户不存在 username={form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户名不存在: {form_data.username}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.password):
        logger.warning(f"登录失败: 密码错误 username={form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误，请重新输入",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # 移动端/平板端仅允许学生登录（教师/管理员请使用电脑端）
    # 三端分离安全约束：移动端是学生学习端，教师端/管理员端仅限电脑端访问
    if client_type in ("mobile", "tablet") and user.user_type != "student":
        logger.warning(
            f"移动端登录被拒: 非学生角色 username={form_data.username} "
            f"role={user.user_type} client_type={client_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="移动端/平板端仅支持学生登录，教师/管理员请使用电脑端",
        )

    # 三端分离：JWT payload 含角色和权限，前端路由守卫依赖此信息
    from ....core.security import get_user_permissions_with_db
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id,
            "user_no": user.user_no,
            "user_type": user.user_type,
            "role_level": user.role_level,
            "permissions": [p.value for p in get_user_permissions_with_db(user, db)],
        },
        expires_delta=access_token_expires
    )

    refresh_token = create_refresh_token(
        data={"user_id": user.user_id}
    )

    client_ip = get_client_ip(request) if request else "unknown"
    token_manager.store_refresh_token(
        refresh_token,
        user.user_id,
        device_info=client_ip
    )

    # 注册设备会话
    if request:
        device_info = {
            "device_id": str(uuid.uuid4()),
            "platform": detect_platform(request),
            "browser": extract_browser(request),
            "os": extract_os(request),
            "ip": client_ip,
            "token_hash": hash_token(access_token),
            "last_active": datetime.utcnow().isoformat(),
            "is_current": True
        }
        
        # 更新设备会话列表
        sessions = user.device_sessions or []
        sessions = [s for s in sessions if s.get("device_id") != device_info["device_id"]]
        sessions.append(device_info)
        
        # 限制最多3个设备
        if len(sessions) > MAX_DEVICES:
            sessions = sessions[-MAX_DEVICES:]
        
        user.device_sessions = sessions

    user.last_login = datetime.now()
    commit_with_retry(db)

    # 触发「初来乍到」成就（首次登录，幂等）
    try:
        await record_user_action(db, user.user_id, TRIGGER_CHECKIN_DONE)
    except Exception as e:
        logger.warning(f"首次登录成就判定失败: {e}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/register", summary="用户注册")
async def register_user(
        form: RegisterForm,
        db: Session = Depends(get_db)
):
    """用户注册接口"""
    username = (form.username or "").strip()
    phone = (form.phone or "").strip()
    user_no = (form.user_no or username).strip()

    if not username or not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名和手机号不能为空"
        )

    existing = db.query(SysUser).filter(
        (SysUser.username == username) |
        (SysUser.user_no == user_no) |
        (SysUser.phone == phone)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名、编号或手机号已存在"
        )

    hashed_password = get_password_hash(form.password)
    new_user = SysUser(
        username=username,
        password=hashed_password,
        email=form.email,
        phone=phone,
        user_no=user_no,
        # 安全策略：注册仅创建学生账号，教师/管理员由管理员后台创建
        user_type="student",
        role_level=0,
        status=1
    )

    db.add(new_user)
    commit_with_retry(db)
    db.refresh(new_user)

    return {"message": "注册成功", "user_id": new_user.user_id}


@router.post("/sms-login", summary="验证码登录")
async def sms_login(
        body: Dict[str, Any],
        db: Session = Depends(get_db)
):
    """
    验证码登录接口
    body: { "username": "学号/编号", "phone": "手机号", "code": "验证码" }
    """
    username = body.get('username', '')
    phone = body.get('phone', '')
    code = body.get('code', '')

    if not username or not phone or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名、手机号和验证码不能为空"
        )

    # 模拟验证码校验 (生产环境需对接短信服务)
    if code != '123456':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )

    user = db.query(SysUser).filter(
        (SysUser.username == username) | (SysUser.user_no == username)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    if user.phone and user.phone != phone:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号与注册手机号不一致"
        )

    if user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )

    # sms-login: JWT payload 含角色权限
    from ....core.security import get_user_permissions_with_db as _get_perms_sms
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id, "user_no": user.user_no,
            "user_type": user.user_type, "role_level": user.role_level,
            "permissions": [p.value for p in _get_perms_sms(user, db)],
        },
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token="",
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", summary="刷新令牌")
async def refresh_access_token(
        body: Dict[str, Any],
        db: Session = Depends(get_db)
):
    """使用刷新令牌获取新的访问令牌"""
    refresh_token = body.get('refresh_token', '')
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 refresh_token"
        )
    user_id = token_manager.validate_refresh_token(refresh_token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user or user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )

    # refresh: JWT payload 含角色权限
    from ....core.security import get_user_permissions_with_db as _get_perms_refresh
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id, "user_no": user.user_no,
            "user_type": user.user_type, "role_level": user.role_level,
            "permissions": [p.value for p in _get_perms_refresh(user, db)],
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", summary="用户登出")
async def logout_user(
        refresh_token: Optional[str] = None,
        current_user: SysUser = Depends(get_current_user)
):
    """用户登出，撤销令牌"""
    if refresh_token:
        token_manager.revoke_refresh_token(refresh_token)

    return {"message": "登出成功"}


class ProfileUpdateForm(BaseModel):
    """个人信息编辑表单 — 仅允许编辑非敏感字段"""
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    department: Optional[str] = None
    class_name: Optional[str] = None
    school: Optional[str] = None


@router.get("/profile", response_model=UserResponse, summary="获取用户信息")
async def get_user_profile(
        current_user: SysUser = Depends(get_current_user)
):
    """获取当前用户完整信息"""
    return current_user


class ChangePasswordForm(BaseModel):
    """修改密码表单"""
    old_password: Optional[str] = None
    new_password: str
    password: Optional[str] = None  # 兼容前端字段名


@router.post("/change-password", summary="修改密码")
async def change_password(
        form: ChangePasswordForm,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """当前用户修改自己的密码（需验证旧密码）"""
    new_pwd = form.new_password or form.password or ""
    if not new_pwd:
        raise HTTPException(status_code=400, detail="新密码不能为空")
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    # 若提供了旧密码则校验，否则（首次设置等场景）允许直接改
    if form.old_password:
        if not verify_password(form.old_password, current_user.password):
            raise HTTPException(status_code=400, detail="当前密码错误")
    current_user.password = get_password_hash(new_pwd)
    commit_with_retry(db)
    return {"success": True, "message": "密码修改成功"}


@router.put("/profile", summary="编辑个人信息")
async def update_user_profile(
        form: ProfileUpdateForm,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """当前用户编辑自己的个人信息（不可修改用户名/角色等敏感字段）"""
    update_data = form.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    commit_with_retry(db)
    db.refresh(current_user)
    return {"success": True, "message": "个人信息已更新", "user": UserResponse.model_validate(current_user)}


# 头像上传允许的扩展名 + 大小上限（2MB）
_ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MAX_AVATAR_SIZE = 2 * 1024 * 1024


@router.post("/avatar", summary="上传头像")
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """学生端上传头像（白名单 + 大小限制 + UUID 重命名）"""
    # 1. 扩展名白名单校验
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png/gif/webp 格式")

    # 2. 读取内容并校验大小
    content = await file.read()
    if len(content) > _MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="头像大小不能超过 2MB")
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 3. UUID 重命名（防路径穿越/覆盖），存 uploads/avatars/
    filename = f"avatar_{current_user.user_id}_{uuid.uuid4().hex[:8]}{ext}"
    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # 4. 更新 avatar 字段
    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar = avatar_url
    commit_with_retry(db)

    logging.getLogger(__name__).info(f"用户 {current_user.user_id} 上传头像: {avatar_url}")
    return {"success": True, "message": "头像上传成功", "avatar_url": avatar_url}
