"""
清理数据库中的测试用户
运行方式: python -m backend.scripts.clean_test_users
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 切换到backend目录
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(backend_dir)

from backend.app.core.database import SessionLocal
from backend.app.models.models import SysUser

def clean_test_users():
    """清理无法登录的测试用户"""
    db = SessionLocal()
    try:
        # 查找并删除无法登录的测试用户
        test_users = db.query(SysUser).filter(
            SysUser.user_no.in_(['FNL001', 'yyc5678'])
        ).all()
        
        if test_users:
            for user in test_users:
                print(f"删除测试用户: {user.username} (编号: {user.user_no})")
                db.delete(user)
            db.commit()
            print(f"共删除 {len(test_users)} 个测试用户")
        else:
            print("未找到需要清理的测试用户")
            
        # 显示当前有效用户数
        valid_count = db.query(SysUser).filter(
            SysUser.status == 1,
            SysUser.is_disabled == 0,
            SysUser.user_no.isnot(None),
            SysUser.user_no != ''
        ).count()
        print(f"当前有效用户数: {valid_count}")
        
    except Exception as e:
        print(f"清理失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_test_users()