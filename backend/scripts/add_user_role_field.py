"""
添加user_role字段到sys_operation_log表
运行方式: python -m backend.scripts.add_user_role_field
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 切换到backend目录
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(backend_dir)

from backend.app.core.database import SessionLocal, engine
from sqlalchemy import text

def add_user_role_field():
    """添加user_role字段"""
    db = SessionLocal()
    try:
        # 检查字段是否已存在
        check_sql = text("PRAGMA table_info(sys_operation_log)")
        result = db.execute(check_sql)
        columns = [row[1] for row in result.fetchall()]
        
        if 'user_role' in columns:
            print("user_role字段已存在")
            return
        
        # 添加字段
        add_column_sql = text("ALTER TABLE sys_operation_log ADD COLUMN user_role VARCHAR(50)")
        db.execute(add_column_sql)
        db.commit()
        
        print("成功添加user_role字段")
        
    except Exception as e:
        print(f"添加字段失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_user_role_field()