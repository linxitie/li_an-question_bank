"""题组图片落盘通道 — 把 shared_content 里的 [IMAGE:...] 占位符变成可访问的 <img>。

为什么需要这个模块（J-1-1）
--------------------------
`text_parser` 从 docx 抽图时，会把每张图以「扁平文件名」暂存到
``app/static/questions/{marker}.png``，并在正文里留下 ``[IMAGE:{marker}]``。

题目侧一直有 ``_extract_and_save_images()`` 兜底：把占位符换成真正的
``<img>`` 并写库。但**题组（question_groups）从来没有这条通道**，于是：

  1. 申论「给定材料」的图永远留在占位符状态；
  2. 前端渲染时退化成 ``/static/question-groups/{marker}.png``，而该路径
     既没挂载也没文件 —— 稳定裂图。

实测（导入修复 Wave 0 取证）：21 个题组里 **9 个含 10 个占位符**，
``shared_content_images`` 列 **全为空**，这 10 张图在磁盘上 **一张都没有**。

与题目侧的路径隔离（硬性要求）
------------------------------
题目图落 ``static/questions/{qid}/``，题组图落 ``static/question-groups/{gid}/``。
两者**物理隔离**，绝不复用同一目录 —— 否则 224 道存量含图题会与题组互相覆盖。

与题目侧的一个关键差异
----------------------
``_extract_and_save_images()`` 消费掉暂存图后会 ``os.remove(src_file)``。
题组**不做删除**：材料块与题块可能引用同一 marker（同一份卷里同一张图
既出现在材料又出现在题目），删了就让对方裂图。题组只复制、不删源。
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import List, Optional, Tuple

from ...core.config import settings

logger = logging.getLogger(__name__)

# 单图大小上限，与 question_import.MAX_IMAGE_SIZE 保持一致（10MB）
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# 占位符格式：[a-f0-9]+_\d+_\d+（uuid_行号_序号）或 \d+_\d+（行号_序号）
# 字符集本身即天然防目录穿越：'/'、'.' 都不在集合内，'../../evil' 永不匹配。
_MARKER_RE = re.compile(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]')

# backend/ 目录：app/services/question_ingest/images.py -> 上溯三级
_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# docx 抽图的扁平暂存目录（与 _extract_and_save_images 的 static_img_dir 同源）
_STAGING_DIR = os.path.join(_BACKEND_DIR, 'app', 'static', 'questions')

# 题组图片根目录 + 对外 URL 前缀（必须与 main.py 的挂载一致）
GROUP_IMG_ROOT = os.path.join(_BACKEND_DIR, 'app', 'static', 'question-groups')
GROUP_URL_PREFIX = '/static/question-groups'


def _is_irrelevant(img_data: bytes) -> bool:
    """实锤无关图（二维码 / 推广黑名单）才拦，与题目侧判定标准一致。

    复用 image_filters.classify_image —— 导入侧与存量清理脚本同源，
    避免两边判定漂移。异常时放行，绝不因检测器故障阻塞导入。
    """
    try:
        from ..image_filters import classify_image
        decision, reason = classify_image(img_data)
        if decision == 'block':
            logger.debug('[group-images] 拦截无关图片(%s)', reason)
            return True
        if decision == 'suspect':
            logger.info('[group-images] 疑似无关图片放行待人工复核(%s)', reason)
    except Exception:
        pass
    return False


def _compress_and_store(img_data: bytes, img_dir: str, idx: int) -> Tuple[str, str]:
    """压缩后按内容 md5 命名落盘，相同图天然去重。返回 (绝对路径, 文件名)。

    压缩失败不阻塞导入：原样落盘（沿用题目侧行为）。
    """
    ext = 'png'
    if settings.IMAGE_COMPRESSION_ENABLED:
        try:
            from ..image_service import compress_image
            img_data, ext = compress_image(
                img_data,
                max_side=settings.IMAGE_MAX_SIDE,
                quality=settings.IMAGE_QUALITY,
            )
        except Exception:
            pass  # 压缩异常则原样落盘
    md5 = hashlib.md5(img_data).hexdigest()[:8]
    filename = f'img_{idx}_{md5}.{ext}'
    filepath = os.path.join(img_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(img_data)
    return filepath, filename


def save_images_for_group(
    text: str,
    group_id: int,
    staging_dir: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """把题组 shared_content 里的 [IMAGE:...] 换成 <img>，图片落到题组专属目录。

    :param text:含占位符的原始文本
    :param group_id:题组主键（question_groups.id，注意不是 group_id）
    :param staging_dir:docx 抽图的扁平暂存目录，默认 app/static/questions
    :returns:(新文本, 图片 URL 列表)。找不到源图的占位符会被**清除**，
              避免前端渲染出裂图 —— 与题目侧 question_import.py:1904-1912 同策略。
    """
    if not text or not isinstance(text, str) or '[IMAGE:' not in text:
        return text, []

    gid = int(group_id)
    img_dir = os.path.join(GROUP_IMG_ROOT, str(gid))
    os.makedirs(img_dir, exist_ok=True)
    staging = staging_dir or _STAGING_DIR

    markers = _MARKER_RE.findall(text)
    if not markers:
        return text, []

    urls: List[str] = []
    new_text = text
    for idx, marker in enumerate(markers):
        try:
            # uuid_行_序号 同时尝试 行_序号（与题目侧 possible_names 同策略）
            possible = [f'{marker}.png']
            parts = marker.split('_')
            if len(parts) == 3:
                possible.append(f'{parts[1]}_{parts[2]}.png')

            src_file = None
            for name in possible:
                candidate = os.path.join(staging, name)
                # 双保险：basename + 绝对路径仍需落在 staging 内
                if os.path.isfile(candidate) and \
                        os.path.abspath(candidate).startswith(os.path.abspath(staging) + os.sep):
                    src_file = candidate
                    break

            token = f'[IMAGE:{marker}]'
            if not src_file:
                logger.debug('[group-images] 题组%d 图源未找到，剔除占位符: %s', gid, marker)
                new_text = new_text.replace(token, '')
                continue

            img_data = open(src_file, 'rb').read()
            if len(img_data) > MAX_IMAGE_SIZE:
                logger.warning('[group-images] 题组%d %s 超过 %d 字节，剔除',
                               gid, marker, MAX_IMAGE_SIZE)
                new_text = new_text.replace(token, '')
                continue
            if _is_irrelevant(img_data):
                new_text = new_text.replace(token, '')
                continue

            _dst, filename = _compress_and_store(img_data, img_dir, idx)
            rel_url = f'{GROUP_URL_PREFIX}/{gid}/{filename}'

            # 落盘后再确认文件确实在题组目录内（防穿越兜底）
            if not os.path.abspath(os.path.join(img_dir, filename)).startswith(
                    os.path.abspath(GROUP_IMG_ROOT) + os.sep):
                logger.warning('[group-images] 题组%d 落盘路径越界，跳过: %s', gid, filename)
                new_text = new_text.replace(token, '')
                continue

            new_text = new_text.replace(
                token, f'<img src="{rel_url}" class="q-img" loading="lazy" />')
            urls.append(rel_url)
            logger.debug('[group-images] 题组%d 保存图片: %s', gid, rel_url)
            # 刻意不删除 staging 源文件：材料块与题块可能共用同一 marker
        except Exception as e:
            logger.warning('[group-images] 题组%d 图片 %s 处理失败: %s', gid, marker, e)
            continue

    return new_text, urls