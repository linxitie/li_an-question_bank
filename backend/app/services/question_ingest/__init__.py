# question_ingest 包 — 题目导入管线的模块化拆分
# 保持 from ...question_import import X 全兼容（re-export）

from .docx_reader import (  # I-3：畸形 docx 三级容错（pure move 自 api/v1/question_import.py）
    _rels_base_dir,
    _sanitize_docx_rels,
    _extract_text_from_docx_raw_xml,
    _open_docx_resilient,
    _extract_text_from_docx,
)
from .tags import (  # I-4：标签检测 + 自动建卷（pure move 自 api/v1/question_import.py）
    _auto_detect_tags,
    _detect_complete_paper,
    _extract_paper_name,
    _get_or_create_import_paper,
    SUBJECT_NAME_MAP,
)
from .images import (  # I-5：题目图提取/落盘 + 占位符协议（pure move 自 api/v1/question_import.py）
    _extract_and_save_images,
    save_images_for_group,
)
from .pdf_reader import (  # I-6：PDF 提取全套 + 三级回退（pure move 自 api/v1/question_import.py）
    _pdf_image_to_png,
    _extract_text_from_pdf,
    _extract_text_from_scanned_pdf,
    _extract_images_from_pdf_page,
    _decode_pdf_image,
    _pdf_has_images_only,
)
