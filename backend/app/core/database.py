"""
数据库连接模块
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from .config import settings

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=50,
    pool_timeout=30,
    pool_recycle=1800,
    echo=False
)

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