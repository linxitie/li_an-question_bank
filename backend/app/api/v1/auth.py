from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.models import SysUser
from ...schemas.schemas import UserResponse, LoginResponse, TokenData
from ...core.config import settings
from ...core.security import (
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


class RegisterForm(BaseModel):
    """注册表单"""
    username: str
    password: str
    email: Optional[str] = None
    phone: str
    user_no: str
    user_type: str = "student"


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db),
        request: Request = None,
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

    # 三端分离：JWT payload 含角色和权限，前端路由守卫依赖此信息
    from ...core.security import get_user_permissions
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id,
            "user_no": user.user_no,
            "user_type": user.user_type,
            "role_level": user.role_level,
            "permissions": [p.value for p in get_user_permissions(user)],
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

    user.last_login = datetime.now()
    db.commit()

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
    existing = db.query(SysUser).filter(
        (SysUser.username == form.username) |
        (SysUser.user_no == form.user_no) |
        (SysUser.phone == form.phone)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名、编号或手机号已存在"
        )

    hashed_password = get_password_hash(form.password)
    new_user = SysUser(
        username=form.username,
        password=hashed_password,
        email=form.email,
        phone=form.phone,
        user_no=form.user_no,
        # 安全策略：注册仅创建学生账号，教师/管理员由管理员后台创建
        user_type="student",
        role_level=0,
        status=1
    )

    db.add(new_user)
    db.commit()
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
    from ...core.security import get_user_permissions as _get_perms_sms
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id, "user_no": user.user_no,
            "user_type": user.user_type, "role_level": user.role_level,
            "permissions": [p.value for p in _get_perms_sms(user)],
        },
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
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
    from ...core.security import get_user_permissions as _get_perms_refresh
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "user_id": user.user_id, "user_no": user.user_no,
            "user_type": user.user_type, "role_level": user.role_level,
            "permissions": [p.value for p in _get_perms_refresh(user)],
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
    db.commit()
    db.refresh(current_user)
    return {"success": True, "message": "个人信息已更新", "user": UserResponse.model_validate(current_user)}
