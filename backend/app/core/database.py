"""
数据库连接模块 — WAL 模式 + 并发优化
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from .config import settings

# 创建数据库引擎（SQLite 不接受 pool_* / max_overflow 参数，按 dialect 自动跳过）
_engine_kwargs: dict = (
    {
        "connect_args": {
            "check_same_thread": False,
            "timeout": 30,  # SQLite 锁等待超时（秒）
        },
    } if settings.DB_TYPE == "sqlite"
    else {
        "pool_size": 20,
        "max_overflow": 50,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    }
)
engine = create_engine(settings.DATABASE_URL, echo=False, **_engine_kwargs)

# 启用 SQLite WAL 模式（允许并发读写）
if settings.DB_TYPE == "sqlite":
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建线程安全的会话
session_factory = sessionmaker(bind=engine)
ScopedSession = scoped_session(session_factory)

# 声明基类
Base = declarative_base()

def get_db():
    """
    获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_scoped_db():
    """
    获取线程安全的数据库会话
    """
    db = ScopedSession()
    try:
        yield db
    finally:
        db.close()

class ReadWriteRouter:
    """
    读写分离路由器
    """
    def __init__(self):
        self.read_engine = None
        self.write_engine = engine
    
    def set_read_engine(self, read_url: str):
        """设置读库引擎"""
        self.read_engine = create_engine(read_url)
    
    def get_bind(self, mapper=None, clause=None):
        """获取数据库连接"""
        from sqlalchemy.sql import Insert, Update, Delete
        
        if self.read_engine and clause is not None:
            if isinstance(clause, (Insert, Update, Delete)):
                return self.write_engine
            return self.read_engine
        return self.write_engine

# 初始化读写分离路由器
rw_router = ReadWriteRouter()