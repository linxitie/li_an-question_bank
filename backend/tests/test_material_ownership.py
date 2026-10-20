"""材料归属 golden corpus（P0-4）。

语料来自 P0-3 入库的 5 个真实案例 + 1 个 not_found 记录：
`backend/tests/fixtures/material_ownership/manifest.json`。

本文件只锁定 P3 目标行为，不修改解析器。P3 未落地前，5 个 found 案例
以 `xfail(strict=True)` 记录；P3-13 验收时应移除 xfail 标记并确保全绿。
"""
import hashlib
import json
from pathlib import Path

import pytest

from app.services.text_parser import extract_question_blocks

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "material_ownership"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]
FOUND_CASES = [case for case in CASES if case["status"] == "found"]
NOT_FOUND_CASES = [case for case in CASES if case["status"] == "not_found"]

_MATERIAL_LEAK_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="P3 MATERIAL_OWNERSHIP_V2 target; remove at P3-13",
)


def _read_raw(case: dict) -> str:
    return (FIXTURE_ROOT / case["raw_file"]).read_text(encoding="utf-8")


def _blocks(case: dict) -> list[dict]:
    return extract_question_blocks(_read_raw(case))


def _block_for_q(blocks: list[dict], qnum: int) -> dict:
    for block in blocks:
        if block.get("question_number") == qnum:
            return block
    pytest.fail(
        f"question {qnum} not parsed; "
        f"qnums={[block.get('question_number') for block in blocks]}"
    )


def _all_material(blocks: list[dict]) -> str:
    """兼容文档级 doc_material 和块级 material_text 两种落点。"""
    parts: list[str] = []
    for block in blocks:
        doc_material = block.get("doc_material")
        if doc_material:
            parts.append(str(doc_material))
        material_text = block.get("material_text")
        if material_text:
            parts.append(str(material_text))
    return "\n".join(parts)


def _assert_question_clean(block: dict, phrases: list[str]) -> None:
    for key in ("content", "analysis"):
        value = str(block.get(key) or "")
        for phrase in phrases:
            assert phrase not in value, (
                f"{phrase!r} leaked into question "
                f"{block.get('question_number')} {key}: {value[:300]!r}"
            )


def test_manifest_integrity():
    assert MANIFEST["schema_version"] == 1
    assert len(CASES) == 6
    assert len(FOUND_CASES) == 5
    assert len(NOT_FOUND_CASES) == 1

    for case in FOUND_CASES:
        raw_path = FIXTURE_ROOT / case["raw_file"]
        assert raw_path.is_file(), f"missing fixture: {raw_path}"
        payload = raw_path.read_bytes()
        assert not payload.startswith(b"\xef\xbb\xbf"), f"BOM in {raw_path}"
        assert len(payload) == case["raw_bytes"], case["id"]
        assert hashlib.sha256(payload).hexdigest() == case["raw_sha256"], case["id"]
        assert payload.decode("utf-8")


def test_case_03_not_found_is_documented():
    case3 = NOT_FOUND_CASES[0]
    assert case3["id"] == "case_03_material_after_analysis"
    assert case3["raw_file"] is None
    assert case3["source_path"] is None
    assert case3["expected"] is None
    assert case3["search_scope"]
    assert "合成" in case3["notes"] or "synthetic" in case3["notes"].lower()


@pytest.mark.parametrize("case", FOUND_CASES, ids=[case["id"] for case in FOUND_CASES])
@_MATERIAL_LEAK_XFAIL
def test_golden_case(case):
    blocks = _blocks(case)
    material = _all_material(blocks)
    case_id = case["id"]

    if case_id == "case_01_q85_tail_material":
        q85 = _block_for_q(blocks, 85)
        _assert_question_clean(q85, ["五、根据以下情境材料"])
        assert "五、根据以下情境材料" in material
        assert "2024年11月26日8时15分" in material

    elif case_id == "case_02_2017_unmarked_material":
        q85 = _block_for_q(blocks, 85)
        phrase = "某日，有群众报警，称本市六盘岭街道无言路8号"
        _assert_question_clean(q85, [phrase])
        assert phrase in material

    elif case_id == "case_04_material_after_last_qnum":
        q97 = _block_for_q(blocks, 97)
        _assert_question_clean(q97, ["（十）", "98－100"])
        assert "（十）" in material
        assert "98－100" in material

    elif case_id == "case_05_essay_material_before_q1":
        q1 = _block_for_q(blocks, 1)
        phrase = "梨子成为范家塘村招商引资的招牌"
        _assert_question_clean(q1, [phrase])
        assert phrase in material

    elif case_id == "case_06_unnumbered_doc_material":
        q1 = _block_for_q(blocks, 1)
        for qnum in (2, 3, 4, 5):
            _block_for_q(blocks, qnum)
        assert "根据“给定资料1”" in str(q1.get("content") or "")
        phrase = "W 公司是我国一家著名的装备制造企业"
        _assert_question_clean(q1, [phrase])
        assert phrase in material
        assert "材料5" in material

    else:  # pragma: no cover - manifest guard
        pytest.fail(f"unhandled case id: {case_id}")
