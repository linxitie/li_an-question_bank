"""F3 媒体资产元数据模型。

表结构以 backend/migrations/20261027_002_media_assets.sql 为准；这里只做 ORM 映射。
"""
from sqlalchemy import Column, Integer, String, Text

from ..core.database import Base


class MediaAsset(Base):
    """媒体资产元数据（事实源）；字节在 ObjectStore 投影中。"""

    __tablename__ = "media_assets"

    asset_id = Column(String(32), primary_key=True)
    sha256 = Column(String(64), nullable=False)
    object_key = Column(String(80), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)
    original_name = Column(String(255))
    created_by = Column(Integer)
    status = Column(String(10), nullable=False, default="active")
    created_at = Column(Text, nullable=False)
    deleted_at = Column(Text)
