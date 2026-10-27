"""
测试配置文件
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, get_db
from app.foundation.schema import ddl_statements, FOUNDATION_TABLES
from app.main import app
from app.models.models import SysUser, QuestionSubject, QuestionType
from app.core.security import get_password_hash, create_access_token

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def _reset_foundation_tables():
    """F2b 的 Outbox 写入需要 foundation 表；内存库不经过启动期迁移。"""
    with engine.begin() as conn:
        for table in FOUNDATION_TABLES:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table}")
        for statement in ddl_statements():
            conn.exec_driver_sql(statement)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _reset_foundation_tables()
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db_fixture():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db_fixture
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db_session):
    user = SysUser(
        user_no="test001",
        username="测试用户",
        password=get_password_hash("password123"),
        phone="13800138000",
        user_type="student",
        role_level=1,
        status=1
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_admin(db_session):
    admin = SysUser(
        user_no="admin001",
        username="管理员",
        password=get_password_hash("admin123"),
        phone="13900139000",
        user_type="admin",
        role_level=3,
        status=1
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture
def test_subject(db_session):
    subject = QuestionSubject(
        subject_name="申论",
        subject_code="SHENLUN",
        status=1
    )
    db_session.add(subject)
    db_session.commit()
    db_session.refresh(subject)
    return subject

@pytest.fixture
def test_question_type(db_session):
    qtype = QuestionType(
        type_name="单选题",
        type_code="SINGLE",
        is_objective=1
    )
    db_session.add(qtype)
    db_session.commit()
    db_session.refresh(qtype)
    return qtype

@pytest.fixture
def auth_token(test_user):
    return create_access_token(data={"user_id": test_user.user_id, "user_no": test_user.user_no})

@pytest.fixture
def admin_token(test_admin):
    return create_access_token(data={"user_id": test_admin.user_id, "user_no": test_admin.user_no})

@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}