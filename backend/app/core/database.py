"""
数据库连接模块 — WAL 模式 + 并发优化
"""
import time

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
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
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        # 读多写少的题库场景：把页缓存与 mmap 放大，避免每次查询都回读磁盘。
        # cache_size 为负数表示 KB（-32000 = 32MB/连接），mmap_size 为字节。
        cursor.execute("PRAGMA cache_size=-32000;")
        cursor.execute("PRAGMA mmap_size=134217728;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
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


def commit_with_retry(db, max_retries: int = 3, base_delay: float = 0.5):
    """
    提交事务；遇到 SQLite "database is locked" 自动重试（指数退避）。

    用于登录等关键写路径，避免与后台爬虫/定时任务偶发锁冲突导致 500。
    注意：重试 sleep 为阻塞式，仅用于低频锁冲突场景（正常路径一次 commit 即返回）。
    """
    for attempt in range(max_retries):
        try:
            db.commit()
            return
        except OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise

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