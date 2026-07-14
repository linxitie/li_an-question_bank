"""
Seed 脚本 — 初始化模拟用户和系统配置
仅 DEBUG 模式自动执行，生产环境需手动运行
"""
import logging
from datetime import datetime

from .core.config import settings
from .core.database import SessionLocal
from .core.security import get_password_hash
from .models.models import SysUser, SysConfig

logger = logging.getLogger(__name__)

# 模拟用户种子数据
SEED_USERS = [
    {
        "user_no": "ycc5678",
        "username": "ycc5678",
        "password": "ycc5678",
        "user_type": "teacher",
        "role_level": 1,
        "phone": "13800001001",
        "school": "中国人民警察大学",
        "department": "公安基础教研部",
        "title": "讲师",
        "email": "ycc5678@example.com",
    },
    {
        "user_no": "cbrycc",
        "username": "cbrycc",
        "password": "cbrycc",
        "user_type": "admin",
        "role_level": 3,  # 超级管理员
        "phone": "13800001002",
        "school": "中国人民警察大学",
        "email": "cbrycc@example.com",
    },
]

# 系统默认配置
DEFAULT_CONFIGS = [
    ("site_name", "砺安题库", "站点名称", "STRING"),
    ("max_login_attempts", "5", "最大登录尝试次数", "NUMBER"),
    ("exam_auto_submit_minutes", "120", "考试自动提交时间(分钟)", "NUMBER"),
    ("maintenance_mode", "false", "维护模式", "BOOLEAN"),
    ("register_open", "true", "是否开放注册", "BOOLEAN"),
    ("password_min_length", "6", "密码最小长度", "NUMBER"),
    ("announcement_default_visible", "all", "公告默认可见角色", "STRING"),
]


def seed_users():
    """创建模拟用户（幂等：已存在则跳过）"""
    db = SessionLocal()
    created_count = 0
    try:
        for user_data in SEED_USERS:
            existing = db.query(SysUser).filter(
                SysUser.user_no == user_data["user_no"]
            ).first()
            if existing:
                logger.info(f"Seed: 用户 {user_data['username']} 已存在，跳过")
                continue

            new_user = SysUser(
                user_no=user_data["user_no"],
                username=user_data["username"],
                password=get_password_hash(user_data["password"]),
                user_type=user_data["user_type"],
                role_level=user_data["role_level"],
                phone=user_data["phone"],
                school=user_data.get("school", "中国人民警察大学"),
                department=user_data.get("department"),
                title=user_data.get("title"),
                email=user_data.get("email"),
                status=1,
                is_disabled=0,
                register_time=datetime.now(),
            )
            db.add(new_user)
            created_count += 1
            logger.info(
                f"Seed: 创建{user_data['user_type']}用户 "
                f"{user_data['username']} (role_level={user_data['role_level']})"
            )

        db.commit()
        if created_count > 0:
            logger.info(f"Seed: 共创建 {created_count} 个模拟用户")
    except Exception as e:
        db.rollback()
        logger.error(f"Seed: 创建用户失败 - {e}")
        raise
    finally:
        db.close()


def seed_configs():
    """初始化系统默认配置（幂等：已存在则跳过）"""
    db = SessionLocal()
    try:
        created = 0
        for key, value, desc, ctype in DEFAULT_CONFIGS:
            existing = db.query(SysConfig).filter(
                SysConfig.config_key == key
            ).first()
            if existing:
                continue
            db.add(SysConfig(
                config_key=key,
                config_value=value,
                config_desc=desc,
                config_type=ctype,
            ))
            created += 1

        db.commit()
        if created > 0:
            logger.info(f"Seed: 初始化 {created} 个系统默认配置")
    except Exception as e:
        db.rollback()
        logger.warning(f"Seed: 配置初始化失败（可忽略） - {e}")
    finally:
        db.close()


def run_seed():
    """执行所有 Seed 任务"""
    logger.info("=" * 50)
    logger.info("Seed: 开始执行数据初始化...")
    logger.info("=" * 50)

    # 仅在 DEBUG 模式自动执行
    if not settings.DEBUG:
        logger.info("Seed: 非 DEBUG 模式，跳过自动种子数据。手动执行: python -m app.seed")
        return

    seed_configs()
    seed_users()

    logger.info("Seed: 数据初始化完成")
    logger.info("=" * 50)
    logger.info("模拟用户:")
    logger.info("  教师端: ycc5678 / ycc5678 (teacher, role_level=1)")
    logger.info("  管理员端: cbrycc / cbrycc (admin, role_level=3)")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_seed()
