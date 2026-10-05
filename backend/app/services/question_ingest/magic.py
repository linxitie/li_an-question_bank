"""文件头嗅探 — 按 magic bytes 判定真实文件类型，不依赖扩展名。"""
import logging

logger = logging.getLogger(__name__)


def sniff(buf: bytes) -> str:
    """根据文件头返回真实类型: 'PDF' | 'WORD' | 'EXCEL' | 'UNKNOWN'"""
    if buf[:5] == b'%PDF-':
        return 'PDF'
    if buf[:4] == b'PK\x03\x04':
        # OOXML: 进一步区分 docx/xlsx
        if b'word/' in buf[:2000]:
            return 'WORD'
        if b'xl/' in buf[:2000]:
            return 'EXCEL'
        return 'WORD'  # 默认按 WORD 处理（docx 最常见）
    if buf[:4] == b'\xd0\xcf\x11\xe0':
        # 旧 OLE 格式
        if b'WordDocument' in buf[:2000]:
            return 'WORD'
        if b'Workbook' in buf[:2000]:
            return 'EXCEL'
        return 'WORD'
    return 'UNKNOWN'


def resolve_type(buf: bytes, filename: str) -> tuple[str, bool]:
    """返回 (file_type, conflict)。以文件头为准，冲突时 warning。"""
    import os
    ext = os.path.splitext(filename or '')[1].lower()
    ext_map = {'.xlsx': 'EXCEL', '.xls': 'EXCEL', '.csv': 'EXCEL', '.docx': 'WORD', '.pdf': 'PDF'}
    ext_type = ext_map.get(ext, 'EXCEL')

    sniffed = sniff(buf)
    if sniffed == 'UNKNOWN':
        return ext_type, False

    if sniffed != ext_type:
        logger.warning(f'[magic] 扩展名与文件头不一致: 扩展名={ext}({ext_type}), 文件头={sniffed}, 文件={filename}')
        return sniffed, True

    return sniffed, False
