"""docx 读取 — python-docx 弹性打开 + 畸形 docx 三级容错 + 图片占位符提取。

I-3：pure move 自 backend/app/api/v1/question_import.py（任务 38），
五个函数体一字未改；question_import.py 改为从本模块导入并 re-export，
外部调用方（verify_parser_regression / image_service）零改动。
"""
import logging
import os
from typing import Dict, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _rels_base_dir(rels_name: str) -> str:
    """`<dir>/_rels/<name>.rels` → `<dir>/`（关系目标相对于其宿主 part 所在目录）。"""
    d = os.path.dirname(rels_name)          # e.g. word/_rels
    if os.path.basename(d) == '_rels':
        d = os.path.dirname(d)             # e.g. word
    return d


def _sanitize_docx_rels(buf: bytes) -> Optional[bytes]:
    """移除指向不存在 part 的 relationship，返回可被 python-docx 正常打开的新 docx 字节。

    根治的必要性：python-docx 在**打开包**阶段就遍历全部物理 part 并逐个
    `zipf.read(membername)`，只要有任何一个 relationship 指向不存在的成员，
    整个 `Document()` 就抛 KeyError —— 连纯文本都取不出来。
    典型畸形文件（实测 37 份真实题库中命中 1 份）：
        2019年深圳市公安局第四批公开招聘警务辅助人员考试《行政职业能力测验》真题.docx
        word/_rels/document.xml.rels 含 <Relationship ... Target="../NULL"/>，
        解析后为包内成员 "NULL"，而 zip 中并无该条目 →
        KeyError: "There is no item named 'NULL' in the archive"

    仅删除**确实悬空**的内部关系，外部链接(External)与有效关系一律保留，
    因此图片等正常资源仍可被解析（不是降级为"只取文本"）。
    """
    import io as _io
    import re as _re
    import zipfile as _zip
    import xml.etree.ElementTree as _ET

    try:
        src = _zip.ZipFile(_io.BytesIO(buf))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"文件不是有效的 docx（无法作为 zip 打开）：{e}")

    with src:
        names = set(src.namelist())
        rels_files = [n for n in names if n.endswith('.rels')]
        if not rels_files:
            raise HTTPException(status_code=400, detail="docx 缺少关系文件（.rels），文件可能已损坏")

        patched: Dict[str, bytes] = {}
        removed_total = 0
        for rels_name in rels_files:
            base = _rels_base_dir(rels_name)
            try:
                xml_bytes = src.read(rels_name)
                root = _ET.fromstring(xml_bytes)
            except Exception:  # noqa: BLE001 — 单个 rels 坏掉不阻断其它
                continue
            removed = 0
            for rel_el in list(root):
                tgt = rel_el.get('Target')
                mode = (rel_el.get('TargetMode') or '')
                if not tgt or mode.lower() == 'external':
                    continue
                if tgt.startswith(('http://', 'https://', 'mailto:', 'file:', 'ftp://')):
                    continue
                if tgt.startswith('/'):
                    resolved = os.path.normpath(tgt.lstrip('/')).replace('\\', '/')
                else:
                    resolved = os.path.normpath(os.path.join(base, tgt)).replace('\\', '/').lstrip('/')
                if resolved not in names:
                    root.remove(rel_el)
                    removed += 1
            if removed:
                removed_total += removed
                patched[rels_name] = _ET.tostring(root, encoding='UTF-8', xml_declaration=True)

        if not removed_total:
            return None  # 没有悬空关系 → 不是这个问题，交给上层报错

        out = _io.BytesIO()
        with _zip.ZipFile(out, 'w', _zip.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = patched.get(item.filename) or src.read(item.filename)
                dst.writestr(item, data)
        logger.warning(f"[docx] 清洗掉 {removed_total} 个悬空 relationship 后重试打开")
        return out.getvalue()


def _extract_text_from_docx_raw_xml(buf: bytes) -> str:
    """最后兜底：直接从 zip 里读 word/document.xml 提取纯文本。

    仅在 python-docx 完全无法打开时使用（畸形 docx）。放弃图片与排版，
    但保证「文本不丢」——题目导入的最小可用信息是题干/选项/答案。
    """
    import io as _io
    import re as _re
    import zipfile as _zip

    try:
        with _zip.ZipFile(_io.BytesIO(buf)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"无法解析该 Word 文件：文件结构已损坏（既不是有效 docx，也无法读取其 XML 内容）。请用 Word/WPS 打开后另存为 .docx 再上传。原始错误：{e}",
        )
    # 按段落切分，保留题号/选项的换行结构
    xml = _re.sub(r'</w:p>', '\n', xml)
    xml = _re.sub(r'<w:br[^>]*/>', '\n', xml)
    texts = _re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', xml, _re.S)
    joined = ''.join(texts) if len(texts) <= 1 else '\n'.join(texts)
    if not joined.strip():
        # 回退：粗暴剥标签
        joined = _re.sub(r'<[^>]+>', '', xml)
    return joined


def _open_docx_resilient(buf: bytes, Document):
    """弹性打开 docx：直接开 → 清洗悬空关系后开 → 失败返回 None（交由 XML 兜底）。"""
    import io as _io
    try:
        return Document(_io.BytesIO(buf))
    except HTTPException:
        raise
    except Exception as first_err:  # noqa: BLE001
        logger.warning(f"[docx] 直接打开失败({type(first_err).__name__}: {first_err})，尝试清洗关系后重试")
    try:
        fixed = _sanitize_docx_rels(buf)
        if fixed:
            return Document(_io.BytesIO(fixed))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[docx] 清洗后仍无法打开({type(e).__name__}: {e})，转 XML 兜底")
    return None


def _extract_text_from_docx(buf: bytes) -> str:
    """从docx提取文本+图片占位标记。

    图片定位：通过段落内部 _p 元素的 XPath 精准提取，
    IMAGE 占位符追加到对应段落文本末尾。
    后续 extract_question_blocks 自然按行分离 stem 和 options：
      - 图片在题干段落 → marker 在 stem 中 → 前端题干区展示
      - 图片在选项段落(A.xxx) → marker 在选项值中 → 前端选项区展示
      - 独立图片段落(无文本) → 附加到最近段落，归属当前题号

    容错（2026-09-25 实测修复）：真实题库中存在 python-docx 无法打开的畸形 docx
    （relationship 指向包内不存在的成员），此前直接 500 且整次导入失败。
    现改为三级降级：直接打开 → 清洗悬空 relationship 后打开 → 纯 XML 取文本。
    """
    import io, os, re, uuid
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 python-docx 库")

    _session_id = uuid.uuid4().hex[:8]  # 每次导入唯一前缀，避免跨文件覆盖
    doc = _open_docx_resilient(buf, Document)
    if doc is None:
        logger.warning("[docx] python-docx 无法打开，转用纯 XML 兜底提取")
        return _extract_text_from_docx_raw_xml(buf)
    paragraphs = list(doc.paragraphs)

    # 构建图片关系映射: rId -> image_blob
    image_rel_map = {}
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            image_rel_map[rel.rId] = rel.target_part.blob

    # 图片存储目录
    _current_file = os.path.abspath(__file__)
    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))
    img_dir = os.path.join(_backend_dir, 'static', 'questions')
    os.makedirs(img_dir, exist_ok=True)

    # 命名空间
    DML = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    WPD = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
    REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

    # 题号检测正则（search 支持段中题号）
    # 负向后顾/前顾排除区间引用（如「第98~100题」）：数字两侧不得紧邻数字或 ~，
    # 否则 100 会被误判为独立题号，导致图片归属错位。
    qn_re = re.compile(r'(?:第\s*)?(?<![\d~])(\d+)(?![\d~])\s*(?:[.、．)）\]】]|\s*题)')

    # --- 辅助函数：从段落 lxml 元素中提取所有图片 rId ---
    def _extract_rids(p_elem):
        rids = []
        # 内联图片 (wp:inline)
        for blip in p_elem.iterdescendants('{%s}blip' % DML):
            rId = blip.get('{%s}embed' % REL_NS)
            if rId and rId in image_rel_map:
                rids.append(rId)
        # 浮动图片 (wp:anchor)
        for anchor in p_elem.iterdescendants('{%s}anchor' % WPD):
            for blip in anchor.iterdescendants('{%s}blip' % DML):
                rId = blip.get('{%s}embed' % REL_NS)
                if rId and rId in image_rel_map:
                    rids.append(rId)
        return rids

    # --- 扫描段落，构建输出 ---
    parts = []
    current_qn = None
    img_seq = {}
    pending_imgs = []  # 缓冲首题之前或独立图片段的 rId

    for para in paragraphs:
        text = para.text or ''
        stripped = text.strip()

        # 检测题号（search 而非 match，支持段首或段中）
        m = qn_re.search(stripped) if stripped else None
        if m:
            current_qn = int(m.group(1))

        # 提取该段图片
        rids = _extract_rids(para._p)

        if rids:
            if current_qn is not None:
                # 有题号 → 图片归属于当前题号
                for rId in rids:
                    img_seq.setdefault(current_qn, 0)
                    seq = img_seq[current_qn]
                    img_path = os.path.join(img_dir, f'{_session_id}_{current_qn}_{seq}.png')
                    with open(img_path, 'wb') as f:
                        f.write(image_rel_map[rId])
                    text += f' [IMAGE:{_session_id}_{current_qn}_{seq}]'
                    img_seq[current_qn] += 1
            else:
                # 首题之前 → 缓冲
                pending_imgs.extend(rids)

        if text.strip():
            parts.append(text.strip())

    # 缓冲图片（首题之前）附加到第一个段落
    if pending_imgs and parts:
        first_qn = current_qn or 1
        for rId in pending_imgs:
            img_seq.setdefault(first_qn, 0)
            seq = img_seq[first_qn]
            img_path = os.path.join(img_dir, f'{_session_id}_{first_qn}_{seq}.png')
            with open(img_path, 'wb') as f:
                f.write(image_rel_map[rId])
            parts[0] += f' [IMAGE:{_session_id}_{first_qn}_{seq}]'
            img_seq[first_qn] += 1

    # --- 表格内容（文本+图片） ---
    for table in doc.tables:
        for row in table.rows:
            row_texts = []
            for cell in row.cells:
                ct = cell.text.strip()
                for cp in cell.paragraphs:
                    for rId in _extract_rids(cp._p):
                        if current_qn is not None:
                            img_seq.setdefault(current_qn, 0)
                            seq = img_seq[current_qn]
                            img_path = os.path.join(img_dir, f'{_session_id}_{current_qn}_{seq}.png')
                            with open(img_path, 'wb') as f:
                                f.write(image_rel_map[rId])
                            marker = f'[IMAGE:{_session_id}_{current_qn}_{seq}]'
                            ct = f'{ct} {marker}'.strip() if ct else marker
                            img_seq[current_qn] += 1
                if ct:
                    row_texts.append(ct)
            if row_texts:
                parts.append(' | '.join(row_texts))

    return '\n'.join(parts)
