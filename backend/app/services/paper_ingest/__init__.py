# -*- coding: utf-8 -*-
"""上传即导题（P3，2026-11-09）对外入口。

调用方只认这四个：
  · `parse_material(...)`  解析原件 → 草稿（上传后台任务 / 手动重试用）
  · `latest_pending` / `latest_of` / `draft_brief`  列表与抽屉要的只读视图
  · `confirm_draft(...)`   确认入库（题目 + 挂卷 + 图片落地）
  · `cleanup_expired(...)` 30 天保留期清理（幂等，可启动期调用）

其它（`readers` / `splitter`）是纯函数实现细节，测试可以单独 import。
"""
from .service import (IngestError, cleanup_expired, confirm_draft, create_draft,
                      discard_draft, draft_brief, fill_draft, items_of, latest_of,
                      latest_pending, parse_material, read_qno_gaps, update_items,
                      warnings_of, write_qno_gaps)

__all__ = [
    "IngestError", "cleanup_expired", "confirm_draft", "discard_draft",
    "create_draft", "fill_draft", "draft_brief", "items_of", "latest_of", "latest_pending",
    "parse_material", "update_items", "warnings_of",
    # Q1/Q2（2026-11-15，导题缺号定位）：缺号坐标的读写（sidecar，非库表）
    "read_qno_gaps", "write_qno_gaps",
]
