"""ORM 模型包：导入时注册独立模型，保证 create_all 能解析全部 FK。"""
from .media_asset import MediaAsset  # noqa: F401
from .content_guard import (  # noqa: F401
    CgAuditEvent,
    CgCase,
    CgEdge,
    CgJudgment,
    CgPolicy,
    CgProposal,
    CgRedteamSample,
    CgStatDaily,
    CgSyncState,
    CgTask,
    CgTerm,
    CgVariant,
)
