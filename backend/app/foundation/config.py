"""F1 配置：纯环境变量与路径，不依赖 app.core（可被迁移脚本/测试独立导入）。"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
DDL_FILE = MIGRATIONS_DIR / "20261027_001_foundation_core.sql"
# F3 媒体资产表：独立 DDL，不混入 F1 的 7 表定义。
MEDIA_DDL_FILE = MIGRATIONS_DIR / "20261027_002_media_assets.sql"
DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "question_bank.db"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# 一键停用：关掉后 lifespan 不建表、不启动 Dispatcher，/health/foundation 报 disabled
FOUNDATION_ENABLED = _bool("FOUNDATION_ENABLED", True)
FOUNDATION_DISPATCH_MS = int(os.environ.get("FOUNDATION_DISPATCH_MS", "500") or 500)
FOUNDATION_MAX_ATTEMPTS = int(os.environ.get("FOUNDATION_MAX_ATTEMPTS", "8") or 8)
# 写入守卫总开关：false 时 6 类校验整体短路，回到 F1 行为（回滚开关）。
FOUNDATION_VALIDATION_ENABLED = _bool("FOUNDATION_VALIDATION_ENABLED", True)
# F2b：业务事件写入 Outbox（同事务）。false 时回到 F2 的 events.publish + 同步兜底。
EVENT_OUTBOX_ENABLED = _bool("EVENT_OUTBOX_ENABLED", True)
# 同机多 worker 的 Dispatcher 单写者锁；相对路径按 backend/ 解析。
DISPATCHER_LOCK_PATH = os.environ.get("DISPATCHER_LOCK_PATH") or "./data/foundation/dispatcher.lock"

# ==================== F3 对象存储 ====================
# 与 app.core.config 同源；脚本可只导入本模块，避免拉起 pydantic Settings。
MEDIA_STORE_ENABLED = _bool("MEDIA_STORE_ENABLED", True)
OBJECT_STORE_BACKEND = (os.environ.get("OBJECT_STORE_BACKEND") or "local").strip().lower()
OBJECT_STORE_ROOT = os.environ.get("OBJECT_STORE_ROOT") or "./data/foundation/objects"
MINIO_ENDPOINT = (os.environ.get("MINIO_ENDPOINT") or "").strip()
MINIO_BUCKET = (os.environ.get("MINIO_BUCKET") or "").strip()
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or ""
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or ""
MINIO_SECURE = _bool("MINIO_SECURE", False)
MINIO_REGION = (os.environ.get("MINIO_REGION") or "us-east-1").strip()
MEDIA_STRICT_BACKEND = _bool("MEDIA_STRICT_BACKEND", False)
MEDIA_ORPHAN_GRACE_DAYS = int(os.environ.get("MEDIA_ORPHAN_GRACE_DAYS", "7") or 7)


def sqlite_path() -> Path:
    """与 app.core.config 同源：SQLITE_PATH 相对路径按 backend/ 解析。"""
    raw = os.environ.get("SQLITE_PATH") or str(DEFAULT_SQLITE_PATH)
    path = Path(raw)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def dispatcher_lock_path() -> Path:
    path = Path(DISPATCHER_LOCK_PATH)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def object_store_root() -> Path:
    """local 根目录；相对路径按 backend/ 解析，与 SQLITE_PATH 一致。"""
    path = Path(OBJECT_STORE_ROOT)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()
