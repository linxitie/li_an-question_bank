"""备考资料解析服务单测（T4）。运行：
    cd backend && python -m pytest tests/test_material_parser.py -v
fixture 现场生成 docx/xlsx 样例，不依赖外部素材。
"""
import pytest
from docx import Document
from openpyxl import Workbook

from app.services.material_sanitizer import sanitize_html
from app.services.material_parser import (
    parse_docx, parse_xlsx, build_cards)


@pytest.fixture(scope="module")
def sample_docx(tmp_path_factory):
    p = tmp_path_factory.mktemp("fx") / "s.docx"
    d = Document()
    d.add_heading("第一章 总论", level=1)
    d.add_paragraph("这是正文第一段。")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "A"; t.cell(0, 1).text = "B"
    t.cell(1, 0).text = "1"; t.cell(1, 1).text = "2"
    d.add_heading("第二章 方法", level=1)
    d.save(str(p))
    return str(p)


@pytest.fixture(scope="module")
def sample_xlsx(tmp_path_factory):
    p = tmp_path_factory.mktemp("fx") / "s.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["词语", "释义", "分类"])
    ws.append(["南辕北辙", "比喻行动和目的相反", "成语"])
    ws.append(["大相径庭", "指彼此相差很远", "成语"])
    ws.append([None, None, None])                          # 空行应跳过
    ws.append(["南辕北辙", "比喻行动和目的相反", "成语"])     # 重复应去重
    wb.save(str(p))
    return str(p)


# ---------- sanitizer ----------

def test_sanitize_strips_script_and_onclick():
    dirty = '<p onclick="x()">hi</p><script>alert(1)</script><img src="/uploads/a.png">'
    clean = sanitize_html(dirty)
    assert "<script" not in clean and "onclick" not in clean
    assert '/uploads/a.png' in clean


def test_sanitize_blocks_external_img():
    clean = sanitize_html('<img src="https://evil.com/x.png">')
    assert "evil.com" not in clean


def test_sanitize_keeps_table_and_heading():
    dirty = "<h2>章节</h2><table><tbody><tr><td>1</td></tr></tbody></table>"
    clean = sanitize_html(dirty)
    assert "<h2>" in clean and "<table>" in clean and "<td>1</td>" in clean


# ---------- docx ----------

def test_parse_docx_structure(sample_docx):
    out = parse_docx(sample_docx)
    titles = [c["title"] for c in out["chapters"]]
    assert titles == ["第一章 总论", "第二章 方法"]
    assert "<table>" in out["html"] and "<td>A</td>" in out["html"]
    assert "正文第一段" in out["html"]
    assert out["word_count"] > 0


# ---------- xlsx / cards ----------

def _all_rows(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = [list(r) for r in (ws.iter_rows(values_only=True) if ws else [])]
    wb.close()
    return [[("" if v is None else str(v).strip()) for v in r] for r in rows][1:]


def test_parse_xlsx_headers_and_rows(sample_xlsx):
    out = parse_xlsx(sample_xlsx)
    assert out["headers"][0] == "词语"
    assert out["total_rows"] == 3          # 含空行与重复行


def test_build_cards_dedup_and_skip_empty(sample_xlsx):
    raw = _all_rows(sample_xlsx)
    cards = build_cards(raw, 0, 1, 2)
    assert len(cards) == 2                 # 空行跳过 + 重复去重
    assert cards[0]["card_front"] == "南辕北辙"
    assert cards[0]["category"] == "成语"


def test_build_cards_over_limit_raises():
    rows = [[f"k{i}", f"v{i}", "c"] for i in range(501)]
    with pytest.raises(ValueError):
        build_cards(rows, 0, 1, 2)
