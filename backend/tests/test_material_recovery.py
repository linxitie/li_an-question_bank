# -*- coding: utf-8 -*-
"""P5：JSON 入库前必须能从历史 PDF 预览恢复整组材料。"""
from app.api.v1.catalog.question_import import _recover_composite_materials
from app.models.models import QuestionImportRecord


def test_recover_group_material_for_every_member(db_session, test_user):
    """预览只在组首题挂材料，恢复时必须覆盖组内每一道小题。"""
    material = "材料一\n" + "某市推进政务服务数字化的背景与做法。" * 20
    preview = {
        "groups": [{
            "group_key": "m_demo",
            "material_text": material,
            "material_titles": ["材料1"],
            "questions": [
                {"question_number": 1, "question_content": "根据给定材料，概括主要举措。（20分）要求：准确全面。"},
                {"question_number": 2, "question_content": "阅读材料4-6，分析当前科技服务存在的主要问题。（15分）"},
            ],
        }],
        "items": [],
    }
    db_session.add(QuestionImportRecord(
        user_id=test_user.user_id,
        original_filename="2023年北京市公务员考试《申论》题本.pdf",
        file_type="PDF",
        import_status="PREVIEW",
        preview_data=preview,
    ))
    db_session.commit()

    items = [
        # 入库题干尾部多了“要求”，与预览不是严格相等，靠前缀兜底
        {"question_number": 1, "question_content": "根据给定材料，概括主要举措。（20分）要求：准确全面。"},
        {"question_number": 2, "question_content": "阅读材料4-6，分析当前科技服务存在的主要问题。（15分）"},
    ]
    filled = _recover_composite_materials(db_session, items, "申论")

    assert filled == 2
    assert all(item["material_text"] == material for item in items)
    assert all(item["material_group"]["group_type"] == "shenlun_material" for item in items)


def test_recover_keeps_items_without_match_untouched(db_session, test_user):
    """匹配不到时不能乱塞材料，交由调用方决定是否拒收。"""
    db_session.add(QuestionImportRecord(
        user_id=test_user.user_id,
        original_filename="other.pdf",
        file_type="PDF",
        import_status="PREVIEW",
        preview_data={"groups": [{
            "group_key": "m_x",
            "material_text": "完全不同的材料" * 10,
            "questions": [{"question_number": 1, "question_content": "另一道题的题干"}],
        }]},
    ))
    db_session.commit()

    item = {"question_number": 1, "question_content": "这道题在历史预览里不存在"}
    assert _recover_composite_materials(db_session, [item], "申论") == 0
    assert "material_text" not in item
