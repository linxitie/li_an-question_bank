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
from .links import (  # I-7：考点关联 + 科目/题型取建（pure move 自 api/v1/question_import.py）
    _link_knowledge_points,             # 分类引擎 → QuestionKnowledge 关联（幂等、异常不阻断）
    _get_or_create_subject,             # 科目取建（强制走 SUBJECT_NAME_MAP 预定义 subject_id）
    _get_or_create_type,                # 题型取建（type_code 带 subject_id 前缀，跨科目唯一）
)

# I-7：单题/行测落库 + 去重检测（pure move 自 api/v1/question_import.py）
#
# ★ 惰性 re-export（PEP-562）：`upsert.py` **反向依赖** `api.v1.question_import` 的
#   `coerce_difficulty` / `NEED_REVIEW_CONFIDENCE` / `_subcategory_tuple` /
#   `_normalize_requirements` / `_get_or_create_shenlun_material_group`。
#   `question_import.py` 在其文件头导入本包，若此处 eager 导入 upsert，
#   upsert 会在 `question_import` 只执行到导入区时就尝试取上述符号 → ImportError
#   （"partially initialized module"）。故改为属性访问时惰性导入；
#   `from app.services.question_ingest import _upsert_question_core` 仍然可用。
_UPSERT_EXPORTS = frozenset({
    '_detect_duplicate',
    '_get_duplicate_info',
    '_upsert_question_core',
    '_upsert_xingce_question',
})


def __getattr__(name: str):
    if name in _UPSERT_EXPORTS:
        from . import upsert
        return getattr(upsert, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
