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
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2026-11-07（B1）：把**上传/原件目录**指到系统临时盘，必须在 import app.* 之前设置。
#
# 为什么要这么做：本机仓库在 OneDrive 同步目录里，`_save_tmp()` 往
# `backend/uploads/materials/tmp/` 写文件时，偶尔被同步扫描/杀软卡住 ~30s（faulthandler
# 抓到阻塞点在 `Path.write_bytes`）。表现为"跑了 4 个用例后整进程卡死、没有 summary"，
# 且与用例内容无关、随机复现。指到 %TEMP% 后跑满 17 个用例 3s 内结束（实测）。
#
# 用 setdefault：外部显式指定（CI/其它机器）时以外部为准。
_TEST_UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "li_an_test_uploads")
_TEST_FILES_ROOT = os.path.join(tempfile.gettempdir(), "li_an_test_material_files")
os.environ.setdefault("UPLOAD_DIR", _TEST_UPLOAD_ROOT)
os.environ.setdefault("MATERIAL_FILES_DIR", _TEST_FILES_ROOT)
# StaticFiles 挂载要求目录已存在（main.py 里 mount /uploads），否则 import 阶段直接抛 RuntimeError
os.makedirs(_TEST_UPLOAD_ROOT, exist_ok=True)
os.makedirs(_TEST_FILES_ROOT, exist_ok=True)

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
def test_teacher(db_session):
    teacher = SysUser(
        user_no="teacher001",
        username="教师甲",
        password=get_password_hash("teacher123"),
        phone="13700137000",
        user_type="teacher",
        role_level=1,
        status=1,
        class_name="一班",
        department="法学",
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)
    return teacher


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
def teacher_token(test_teacher):
    return create_access_token(data={"user_id": test_teacher.user_id, "user_no": test_teacher.user_no})


@pytest.fixture
def admin_token(test_admin):
    return create_access_token(data={"user_id": test_admin.user_id, "user_no": test_admin.user_no})

@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def teacher_headers(teacher_token):
    return {"Authorization": f"Bearer {teacher_token}"}


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}