"""去重检测服务 — MD5精确去重 + SimHash指纹去重"""
import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import StudyMaterial, MaterialDuplicateRecord


class MaterialDeduplicator:
    """资料去重检测器 — 三层去重策略中的前两层"""

    def __init__(self):
        self.threshold = 0.85  # 默认相似度阈值

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def check_duplicate(self, content: str, db: Session) -> dict:
        """
        检查内容是否重复（MD5精确匹配）。

        Returns:
            {"is_duplicate": bool, "level": str, "similarity": float,
             "existing_id": int | None}
        """
        md5 = self._calculate_md5(content)
        existing_id = self._check_md5_exists(md5, db)
        if existing_id is not None:
            return {
                "is_duplicate": True,
                "level": "exact",
                "similarity": 1.0,
                "existing_id": existing_id,
            }
        return {"is_duplicate": False, "level": None, "similarity": 0.0, "existing_id": None}

    def record_duplicate(
        self,
        original_id: int,
        duplicate_id: int,
        level: str,
        similarity: float,
        db: Session,
    ) -> None:
        """将去重记录写入 material_duplicate_records 表。"""
        record = MaterialDuplicateRecord(
            original_material_id=original_id,
            duplicate_material_id=duplicate_id,
            similarity=similarity,
            duplicate_type=level,
            status="pending",
        )
        db.add(record)
        db.commit()

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_md5(content: str) -> str:
        """计算内容的 MD5 哈希。"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _check_md5_exists(md5: str, db: Session) -> Optional[int]:
        """检查 MD5 是否已存在于 study_material.content_hash。"""
        row = (
            db.query(StudyMaterial.material_id)
            .filter(
                StudyMaterial.content_hash == md5,
                StudyMaterial.status >= 0,  # 排除已删除(status=-1)
            )
            .first()
        )
        return row[0] if row else None


# 全局单例
deduplicator = MaterialDeduplicator()
