# -*- coding: utf-8 -*-
"""答案上传（P4，2026-11-09）对外入口。

调用方只认这些：
  · `parse_answers(...)`  解析答案文件 → 草稿（pdf/docx/xlsx/txt）
  · `items_of` / `draft_brief` / `latest_of`  只读视图
  · `update_items(...)`   人工改/补
  · `apply_draft(...)`    写入 `question_bank.answer` / `answer_analysis`
  · `discard_draft(...)` / `cleanup_expired(...)`

`extractor.py` 是纯函数实现细节（四层取答案 + 幻影题号），测试可单独 import。
"""
from .service import (AnswerIngestError, apply_draft, cleanup_expired,
                      discard_draft, draft_brief, draft_payload, items_of,
                      latest_of, paper_brief, paper_questions, parse_answers,
                      update_items)

__all__ = [
    "AnswerIngestError", "apply_draft", "cleanup_expired", "discard_draft",
    "draft_brief", "draft_payload", "items_of", "latest_of", "paper_brief",
    "paper_questions", "parse_answers", "update_items",
]
