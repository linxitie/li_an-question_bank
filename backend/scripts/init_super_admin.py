"""
初始化超级管理员测试账号
运行方式: python -m backend.scripts.init_super_admin
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 切换到backend目录
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(backend_dir)

from backend.app.core.database import SessionLocal
from backend.app.models.models import SysUser
from backend.app.core.security import get_password_hash

def init_super_admin():
    """初始化超级管理员测试账号"""
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(SysUser).filter(
            SysUser.user_no == 'ADMIN001'
        ).first()
        
        if existing:
            print(f"超级管理员账号已存在: {existing.username}")
            return
        
        # 创建超级管理员
        admin_user = SysUser(
            user_no='ADMIN001',
            username='cbr1234',
            password=get_password_hash('cbr1234'),
            phone='13800138000',
            gender='未知',
            user_type='admin',
            department='系统管理部',
            role_level=1,
            status=1,
            is_disabled=0,
            register_time=__import__('datetime').datetime.now()
        )
        
        db.add(admin_user)
        db.commit()
        
        print("超级管理员账号创建成功:")
        print(f"  用户名: cbr1234")
        print(f"  密码: cbr1234")
        print(f"  用户编号: ADMIN001")
        
    except Exception as e:
        print(f"创建失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_super_admin()