"""监控告警服务 — 跟踪导入成功率、失败率，触发阈值告警"""
import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import MaterialImportRecord

logger = logging.getLogger(__name__)


class ImportMonitor:
    """导入监控器 — 内存指标 + 数据库阈值检查"""

    def __init__(self):
        self.metrics = {
            "total_imports": 0,
            "failed_imports": 0,
            "timeout_imports": 0,
            "duplicate_matches": 0,
        }

    # ------------------------------------------------------------------
    # 记录方法
    # ------------------------------------------------------------------

    def record_import(self, success: bool, timeout: bool = False) -> None:
        """记录一次导入结果。"""
        self.metrics["total_imports"] += 1
        if not success:
            self.metrics["failed_imports"] += 1
        if timeout:
            self.metrics["timeout_imports"] += 1

    def record_duplicate_match(self) -> None:
        """记录一次去重匹配命中。"""
        self.metrics["duplicate_matches"] += 1

    # ------------------------------------------------------------------
    # 告警检查
    # ------------------------------------------------------------------

    def check_alerts(self, db: Session) -> List[dict]:
        """检查数据库中的导入记录，返回超阈值的告警列表。"""
        alerts: List[dict] = []

        since = datetime.now() - timedelta(hours=24)

        total = (
            db.query(func.count(MaterialImportRecord.import_id))
            .filter(MaterialImportRecord.create_time >= since)
            .scalar()
            or 0
        )

        failed = (
            db.query(func.count(MaterialImportRecord.import_id))
            .filter(
                MaterialImportRecord.create_time >= since,
                MaterialImportRecord.parse_status == "failed",
            )
            .scalar()
            or 0
        )

        if total > 0:
            failure_rate = failed / total
            if failure_rate > 0.05:  # 5% 阈值
                alerts.append(
                    {
                        "type": "high_failure_rate",
                        "level": "warning",
                        "message": f"导入失败率过高: {failure_rate:.1%}",
                        "threshold": "5%",
                        "current": f"{failure_rate:.1%}",
                    }
                )

        return alerts

    # ------------------------------------------------------------------
    # 指标摘要
    # ------------------------------------------------------------------

    def get_metrics_summary(self) -> dict:
        """返回内存中的指标摘要。"""
        total = self.metrics["total_imports"]
        failed = self.metrics["failed_imports"]
        return {
            "total_imports": total,
            "failed_imports": failed,
            "timeout_imports": self.metrics["timeout_imports"],
            "duplicate_matches": self.metrics["duplicate_matches"],
            "failure_rate": round(failed / total, 4) if total > 0 else 0.0,
        }


# 全局单例
import_monitor = ImportMonitor()
