from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from rich import status

from fastapi import APIRouter, Depends, HTTPException, Request
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
        request: Request = None
):
    """
    用户登录接口

    - 支持用户名或手机号登录
    - 返回 access_token 和 refresh_token
    - 记录登录日志
    """
    # 尝试用用户名或手机号查找用户
    user = db.query(SysUser).filter(
        (SysUser.username == form_data.username) |
        (SysUser.phone == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # 创建令牌
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.user_id, "user_no": user.user_no},
        expires_delta=access_token_expires
    )

    refresh_token = create_refresh_token(
        data={"user_id": user.user_id}
    )

    # 存储刷新令牌
    client_ip = get_client_ip(request) if request else "unknown"
    token_manager.store_refresh_token(
        refresh_token,
        user.user_id,
        device_info=client_ip
    )

    # 更新最后登录时间
    user.last_login = datetime.now()
    db.commit()

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.post("/register", summary="用户注册")
async def register_user(
        form: RegisterForm,
        db: Session = Depends(get_db)
):
    """用户注册接口"""
    # 检查是否已存在
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

    # 创建新用户
    hashed_password = get_password_hash(form.password)
    new_user = SysUser(
        username=form.username,
        password=hashed_password,
        email=form.email,
        phone=form.phone,
        user_no=form.user_no,
        user_type=form.user_type,
        role_level=1 if form.user_type == "student" else 2,
        status=1
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "注册成功", "user_id": new_user.user_id}


@router.post("/refresh", summary="刷新令牌")
async def refresh_access_token(
        refresh_token: str,
        db: Session = Depends(get_db)
):
    """使用刷新令牌获取新的访问令牌"""
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

    # 创建新的访问令牌
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.user_id, "user_no": user.user_no},
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


@router.get("/profile", response_model=UserResponse, summary="获取用户信息")
async def get_user_profile(
        current_user: SysUser = Depends(get_current_user)
):
    """获取当前用户信息"""
    return current_user
