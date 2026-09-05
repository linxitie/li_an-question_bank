"""重置 202516001 密码并测试 API"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.models import SysUser
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

user = db.query(SysUser).filter(SysUser.username == '202516001').first()
if user:
    old_hash = user.password
    new_hash = pwd_context.hash('cbr1234')
    user.password = new_hash
    db.commit()
    print(f"✓ 已重置 202516001 密码为 cbr1234")
    print(f"  user_id: {user.user_id}")
    print(f"  old_hash: {old_hash[:30]}...")
    print(f"  new_hash: {new_hash[:30]}...")
else:
    print("✗ 用户 202516001 不存在")

db.close()
