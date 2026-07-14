"""创建管理员用户"""
import sys
sys.path.insert(0, 'd:/砺安题库/砺安题库/backend')
from app.core.database import SessionLocal
from app.models.models import SysUser
from app.core.security import get_password_hash
from datetime import datetime

db = SessionLocal()

existing = db.query(SysUser).filter(SysUser.username == 'admin').first()
if existing:
    existing.password = get_password_hash('Admin123456')
    print(f'Updated admin password: id={existing.user_id}')
else:
    admin = SysUser(
        user_no='admin001',
        username='admin',
        password=get_password_hash('Admin123456'),
        phone='13800000000',
        user_type='admin',
        role_level=3,
        status=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f'Created admin: id={admin.user_id}, username={admin.username}')

db.close()
print('Done.')
