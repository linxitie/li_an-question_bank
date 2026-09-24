"""
图片服务 — 实现 10 层防线确保前端图片 98% 显示率
====================================================

设计理念：先恢复、后兜底、末位移除
  遇到缺失图片时，依次尝试 QuestionImage 表查询、扁平路径兜底、
  源文件重提取、前端多 URL 重试，只有所有恢复手段都失败时才移除（<2%）。

防线分层：
  第4层：后端预检 —— 返回题目时，验证图片文件是否存在，只返回存在的路径
  第5层：多路径兜底 —— 后端检查子目录路径+扁平路径，取第一个存在的
  第7层：QuestionImage表兜底 —— content中图片缺失时，查表找有效路径替换src
  第8层：源文件重提取 —— 图片彻底丢失时，从原始docx重新提取（恢复而非移除）

  第1层（开发代理）、第2层（统一存储）、第3层（导入即时更新）在 proxy.config.ts
  和 question_import.py 中实现。
  第6层（数据迁移）在 scripts/migrate_images.py 中实现。
  第9层（前端智能重试）在前端 exercise.vue 中实现。
  第10层（图片健康巡检）在 scripts/image_health_check.py 中实现。
"""
import logging
import os
import re
import shutil
from typing import List, Optional

logger = logging.getLogger(__name__)

# 静态图片根目录：backend/app/static/questions/
_CURRENT_FILE = os.path.abspath(__file__)  # backend/app/services/image_service.py
_SERVICES_DIR = os.path.dirname(_CURRENT_FILE)  # backend/app/services/
_APP_DIR = os.path.dirname(_SERVICES_DIR)  # backend/app/
STATIC_IMG_ROOT = os.path.join(_APP_DIR, 'static', 'questions')  # backend/app/static/questions/

# 兼容别名：迁移脚本和巡检脚本中使用 STATIC_DIR 名称导入
STATIC_DIR = STATIC_IMG_ROOT

# <img src="..."> 标签正则
_IMG_TAG_RE = re.compile(
    r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE
)


def _resolve_abs_path(rel_path: str) -> str:
    """将 /static/questions/xxx 形式的相对 URL 转为文件系统绝对路径"""
    if not rel_path:
        return ''
    # 去除 query string
    path = rel_path.split('?')[0]
    # 统一路径前缀
    prefix = '/static/questions/'
    if path.startswith(prefix):
        rel = path[len(prefix):]
    elif path.startswith('static/questions/'):
        rel = path[len('static/questions/'):]
    else:
        return ''
    # 防路径遍历
    rel = rel.replace('\\', '/').lstrip('/')
    if '..' in rel:
        return ''
    return os.path.join(STATIC_IMG_ROOT, rel)


def verify_image_exists(rel_path: str) -> bool:
    """检查图片文件是否存在（第4层预检）"""
    abs_path = _resolve_abs_path(rel_path)
    if not abs_path:
        return False
    return os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0


def _find_image_in_subdir(question_id: int, marker: str = None) -> Optional[str]:
    """在 question_id 子目录中查找图片（第5层兜底）
    如果提供 marker，优先匹配包含 marker 的文件；
    否则返回该目录下第一个有效图片。
    返回相对 URL 路径，如 /static/questions/123/img_docx_0_abc.png
    """
    subdir = os.path.join(STATIC_IMG_ROOT, str(question_id))
    if not os.path.isdir(subdir):
        return None

    candidates = []
    try:
        for fname in os.listdir(subdir):
            fpath = os.path.join(subdir, fname)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                if marker:
                    # 尝试匹配 marker 相关的文件
                    if marker in fname:
                        candidates.insert(0, fname)  # 优先匹配
                    else:
                        candidates.append(fname)
                else:
                    candidates.append(fname)
    except OSError:
        return None

    if not candidates:
        return None

    # 取第一个候选
    return f'/static/questions/{question_id}/{candidates[0]}'


def _find_in_question_image_table(question_id: int, db) -> Optional[str]:
    """从 QuestionImage 表查找有效图片路径（第7层兜底）
    返回第一个文件存在的图片路径，若都无效则返回 None。
    """
    if db is None:
        return None
    try:
        from ..models.models import QuestionImage
        rows = db.query(QuestionImage).filter(
            QuestionImage.question_id == question_id
        ).order_by(QuestionImage.image_order).all()
        for row in rows:
            if row.image_path and verify_image_exists(row.image_path):
                return row.image_path
    except Exception as e:
        logger.warning(f"[image_service] QuestionImage 表查询失败 qid={question_id}: {e}")
    return None


def _extract_marker_from_src(src: str) -> Optional[str]:
    """从 src 路径中提取图片 marker，用于匹配子目录磁盘文件名。

    兼容磁盘实际命名（img_docx_{idx}_{md5} / img_{idx}_{md5}）与
    历史占位符扁平命名（uuid_qn_seq / qn_seq）：
      - img_docx_0_5661de6d.png → 提取 md5 段 "5661de6d"（子目录文件名含此 md5）
      - abc12345_1_0.png        → 提取 "abc12345_1_0"
      - 1_0.png                 → 提取 "1_0"
    """
    if not src:
        return None
    basename = os.path.basename(src.split('?')[0])
    # 去除扩展名
    name_without_ext = os.path.splitext(basename)[0]
    # 1) 磁盘实际命名 img_docx_{idx}_{md5} / img_{idx}_{md5} → 提取 md5（子串匹配文件名）
    m = re.match(r'^img_docx_\d+_([a-f0-9]{6,})$', name_without_ext, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.match(r'^img_\d+_([a-f0-9]{6,})$', name_without_ext, re.IGNORECASE)
    if m:
        return m.group(1)
    # 2) 历史占位符扁平命名 uuid_qn_seq 或 qn_seq
    m = re.match(r'^([a-f0-9]+_\d+_\d+|\d+_\d+)$', name_without_ext, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def sanitize_content_images(content: str, question_id: int = None, db=None) -> str:
    """清理 question_content 中的图片标签：先恢复、后兜底、末位移除

    恢复优先级（确保98%显示率，而非静默隐藏）：
      1. src 路径有效 → 保留
      2. 子目录路径兜底 → 替换 src（第5层）
      3. QuestionImage 表查询 → 替换 src（第7层）
      4. 全部失败 → 移除标签（<2% 极端情况）

    Args:
        content: 题目内容文本
        question_id: 题目ID（用于子目录和 QuestionImage 表查询）
        db: 数据库会话（用于 QuestionImage 表查询）

    Returns:
        清理后的内容文本
    """
    if not content or not isinstance(content, str):
        return content or ''

    def _replace_img(match):
        full_tag = match.group(0)
        src = match.group(1)

        # 1. 检查当前 src 是否有效
        if verify_image_exists(src):
            return full_tag  # 保留原标签

        # 2. 子目录路径兜底（第5层）
        if question_id:
            marker = _extract_marker_from_src(src)
            recovered = _find_image_in_subdir(question_id, marker)
            if recovered:
                logger.debug(f"[image_service] 第5层兜底成功: {src} -> {recovered}")
                return full_tag.replace(src, recovered)

        # 3. QuestionImage 表兜底（第7层）
        if question_id and db is not None:
            recovered = _find_in_question_image_table(question_id, db)
            if recovered:
                logger.debug(f"[image_service] 第7层兜底成功: {src} -> {recovered}")
                return full_tag.replace(src, recovered)

        # 4. 全部失败 → 移除标签（<2% 极端情况）
        logger.warning(f"[image_service] 图片恢复失败，移除标签: src={src}, qid={question_id}")
        return ''

    return _IMG_TAG_RE.sub(_replace_img, content)


def sanitize_options_images(options, question_id: int = None, db=None):
    """清理选项列表中的图片标签

    支持两种输入格式：
      - List[str]:  ['A. xxx', 'B. <img...>', ...]
      - List[dict]: [{'key': 'A', 'value': 'xxx'}, ...]

    Args:
        options: 选项列表
        question_id: 题目ID
        db: 数据库会话

    Returns:
        清理后的选项列表（保持输入格式不变）
    """
    if not options:
        return options or []
    result = []
    for opt in options:
        if isinstance(opt, dict):
            # dict 格式：{'key': 'A', 'value': 'xxx <img...>'}
            new_opt = dict(opt)
            if 'value' in new_opt:
                new_opt['value'] = sanitize_content_images(
                    str(new_opt['value']), question_id, db
                )
            result.append(new_opt)
        elif isinstance(opt, str):
            result.append(sanitize_content_images(opt, question_id, db))
        else:
            result.append(opt)
    return result


def reextract_image_from_source(question_id: int, db) -> List[str]:
    """从原始 docx 重新提取图片（第8层兜底）

    当图片彻底丢失时，尝试从导入记录中找到原始文件，
    重新提取图片并保存到 question_id 子目录。

    Args:
        question_id: 题目ID
        db: 数据库会话

    Returns:
        重新提取的图片路径列表
    """
    if db is None:
        return []

    try:
        from ..models.models import QuestionImportRecord, QuestionBank
        # 查找该题目的导入记录
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not question:
            return []

        # 查找最近的相关导入记录
        records = db.query(QuestionImportRecord).filter(
            QuestionImportRecord.user_id == question.creator_id
        ).order_by(QuestionImportRecord.import_time.desc()).limit(5).all()

        if not records:
            return []

        # 尝试从 uploads 目录找到原始文件
        uploads_dir = os.path.join(_APP_DIR, 'uploads')
        recovered_paths = []

        for record in records:
            if not record.original_filename:
                continue
            # 在 uploads 目录搜索文件
            for root, dirs, files in os.walk(uploads_dir):
                for fname in files:
                    if record.original_filename in fname:
                        src_file = os.path.join(root, fname)
                        # 重新提取图片（调用 question_import 的提取逻辑）
                        try:
                            with open(src_file, 'rb') as f:
                                buf = f.read()
                            # 根据文件类型提取
                            if fname.lower().endswith('.docx'):
                                from ..api.v1.question_import import _extract_text_from_docx
                                _extract_text_from_docx(buf)  # 提取图片到扁平目录
                                # 然后通过 _extract_and_save_images 保存到子目录
                                from ..api.v1.question_import import _extract_and_save_images
                                images = _extract_and_save_images(
                                    '', question_id, question_obj=question
                                )
                                recovered_paths.extend(images)
                                if recovered_paths:
                                    return recovered_paths
                        except Exception as e:
                            logger.warning(f"[image_service] 第8层重提取失败: {e}")
                            continue

        return recovered_paths
    except Exception as e:
        logger.warning(f"[image_service] 第8层重提取异常 qid={question_id}: {e}")
        return []


def normalize_image_path(path: str, question_id: int = None) -> str:
    """
    将各种格式的图片路径标准化为 /static/questions/{qid}/{filename}
    
    支持的输入格式:
    - /static/questions/42/img_0_abc.png
    - static/questions/42/img_0_abc.png
    - ../static/questions/42/img_0_abc.png
    - /uploads/questions/42/img_0_abc.png
    - [IMAGE:42_0]
    - img_docx_0_abc.png (扁平文件名)
    
    输出格式:
    - /static/questions/42/img_0_abc.png
    
    Args:
        path: 原始图片路径
        question_id: 题目ID（用于占位符转换）
    
    Returns:
        标准化后的路径，无效路径返回空字符串
    """
    if not path:
        return ''
    
    # 1. 去除查询参数
    path = path.split('?')[0]
    
    # 2. 处理 [IMAGE:xxx] 占位符
    image_match = re.match(r'\[(\d+)_(\d+)\]', path)
    if image_match:
        qid = int(image_match.group(1))
        idx = image_match.group(2)
        # 尝试在子目录中查找真实图片
        subdir = os.path.join(STATIC_IMG_ROOT, str(qid))
        if os.path.isdir(subdir):
            for fname in os.listdir(subdir):
                if fname.startswith(f'img_') and fname.endswith(f'_{idx}.'):
                    return f'/static/questions/{qid}/{fname}'
        # 兜底：生成默认路径
        return f'/static/questions/{qid}/img_{idx}.jpg'
    
    # 3. 统一路径分隔符
    path = path.replace('\\', '/')
    
    # 4. 去除多余的 ../ 或 ./
    while '/../' in path or '/./' in path:
        path = path.replace('/../', '/').replace('/./', '/')
    
    # 5. 防路径遍历
    if '..' in path:
        return ''
    
    # 6. 确保以 /static/questions/ 开头
    if path.startswith('/static/questions/'):
        return path
    
    if path.startswith('static/questions/'):
        return '/' + path
    
    # 7. 处理其他前缀（如 /uploads/questions/）
    if '/questions/' in path:
        # 提取 question_id 和 filename
        parts = path.split('/questions/')
        if len(parts) >= 2:
            remaining = parts[1]
            sub_parts = remaining.split('/')
            if len(sub_parts) >= 2:
                qid_part = sub_parts[0]
                filename = sub_parts[1]
                return f'/static/questions/{qid_part}/{filename}'
    
    # 8. 处理扁平文件名（无目录前缀）
    if not path.startswith('/') and question_id:
        return f'/static/questions/{question_id}/{path}'
    
    # 9. 无法识别的格式
    logger.debug(f"[image_service] 无法标准化路径: {path}")
    return ''
