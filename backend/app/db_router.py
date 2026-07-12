"""
数据库读写分离路由
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import event
from sqlalchemy.sql import Insert, Update, Delete

class ReadWriteRouter:
    """
    读写分离路由器
    自动将读操作路由到从库，写操作路由到主库
    """
    
    def __init__(self):
        self.master_engine = None
        self.slave_engines = []
        self.current_slave_index = 0
    
    def configure(self, master_url: str, slave_urls: list):
        """
        配置主从数据库连接
        :param master_url: 主库连接URL
        :param slave_urls: 从库连接URL列表
        """
        self.master_engine = create_engine(master_url, pool_size=20, max_overflow=50)
        
        for url in slave_urls:
            slave_engine = create_engine(url, pool_size=20, max_overflow=50)
            self.slave_engines.append(slave_engine)
    
    def get_engine(self, clause=None):
        """
        根据操作类型获取数据库引擎
        :param clause: SQL语句对象
        :return: 数据库引擎
        """
        if clause is None:
            # 默认使用从库（负载均衡）
            return self._get_slave_engine()
        
        # 判断是否为写操作
        if isinstance(clause, (Insert, Update, Delete)):
            return self.master_engine
        
        # 读操作使用从库
        return self._get_slave_engine()
    
    def _get_slave_engine(self):
        """
        获取从库引擎（简单轮询负载均衡）
        """
        if not self.slave_engines:
            # 如果没有从库，使用主库
            return self.master_engine
        
        engine = self.slave_engines[self.current_slave_index]
        self.current_slave_index = (self.current_slave_index + 1) % len(self.slave_engines)
        return engine
    
    def create_session(self, clause=None):
        """
        根据操作类型创建会话
        """
        engine = self.get_engine(clause)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        return Session()

# 全局读写分离路由器
db_router = ReadWriteRouter()

def setup_read_write_separation(master_url: str, slave_urls: list):
    """
    设置读写分离
    """
    db_router.configure(master_url, slave_urls)
    print(f"读写分离配置完成: 主库 x1, 从库 x{len(slave_urls)}")

def get_db_for_read():
    """
    获取读库会话
    """
    session = db_router.create_session()
    try:
        yield session
    finally:
        session.close()

def get_db_for_write():
    """
    获取写库会话
    """
    session = db_router.create_session(Insert())  # 强制使用写库
    try:
        yield session
    finally:
        session.close()

# ------------------------------
# SQLAlchemy事件监听实现读写分离
# ------------------------------

def attach_router_to_session(session):
    """
    将读写分离路由器附加到会话
    """
    @event.listens_for(session, "before_execute")
    def before_execute(conn, clauseelement, multiparams, params):
        # 根据SQL类型切换连接
        if isinstance(clauseelement, (Insert, Update, Delete)):
            # 写操作切换到主库
            conn.connection = db_router.master_engine.connect()
        else:
            # 读操作使用从库
            conn.connection = db_router._get_slave_engine().connect()

# ------------------------------
# 主从复制状态监控
# ------------------------------

def check_replication_status():
    """
    检查主从复制状态
    :return: 复制状态信息
    """
    status = {
        "master": {"status": "online", "lag": 0},
        "slaves": []
    }
    
    # 检查主库状态
    try:
        with db_router.master_engine.connect() as conn:
            result = conn.execute("SHOW MASTER STATUS")
            master_info = result.fetchone()
            status["master"]["file"] = master_info[0] if master_info else None
            status["master"]["position"] = master_info[1] if master_info else None
    except Exception as e:
        status["master"]["status"] = "offline"
        status["master"]["error"] = str(e)
    
    # 检查从库状态
    for i, slave_engine in enumerate(db_router.slave_engines):
        slave_status = {"index": i, "status": "online", "lag": 0}
        try:
            with slave_engine.connect() as conn:
                result = conn.execute("SHOW SLAVE STATUS")
                slave_info = result.fetchone()
                if slave_info:
                    slave_status["slave_io_running"] = slave_info[10]
                    slave_status["slave_sql_running"] = slave_info[11]
                    slave_status["seconds_behind_master"] = slave_info[32]
                    slave_status["lag"] = slave_info[32] if slave_info[32] else 0
        except Exception as e:
            slave_status["status"] = "offline"
            slave_status["error"] = str(e)
        
        status["slaves"].append(slave_status)
    
    return status

# ------------------------------
# 故障转移机制
# ------------------------------

def failover_to_slave(slave_index: int = 0):
    """
    故障转移：将从库提升为主库
    :param slave_index: 要提升的从库索引
    """
    if not db_router.slave_engines:
        raise Exception("没有可用的从库")
    
    if slave_index >= len(db_router.slave_engines):
        raise Exception("指定的从库不存在")
    
    # 将指定从库设为主库
    db_router.master_engine = db_router.slave_engines[slave_index]
    
    # 移除该从库
    db_router.slave_engines.pop(slave_index)
    
    print(f"故障转移完成: 从库 {slave_index} 已提升为主库")