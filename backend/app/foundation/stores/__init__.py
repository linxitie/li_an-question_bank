"""存储协议与本地实现：Dispatcher 只依赖 Protocol，换 PG/MySQL 时替换实现即可。"""
from app.foundation.stores.base import CursorStore, OutboxEvent, OutboxStore
from app.foundation.stores.local import SqliteCursorStore, SqliteOutboxStore

__all__ = [
    "CursorStore", "OutboxEvent", "OutboxStore",
    "SqliteCursorStore", "SqliteOutboxStore",
]
