"""F1 一致性内核（Outbox / 投影 / 对账）。只增不改既有业务代码。

模块边界：本包不得 import backend/app/api 或 models，避免与业务层形成环。
"""

__all__ = ["config", "schema"]
