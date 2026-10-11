# question_ingest 包 — 题目导入管线的模块化拆分
# 保持 from ...question_import import X 全兼容（re-export）

from .docx_reader import (  # I-3：畸形 docx 三级容错（pure move 自 api/v1/question_import.py）
    _rels_base_dir,
    _sanitize_docx_rels,
    _extract_text_from_docx_raw_xml,
    _open_docx_resilient,
    _extract_text_from_docx,
)
