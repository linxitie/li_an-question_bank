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

import base64
import hashlib
import ipaddress
import logging
import os
import re
import shutil
import socket
from typing import List, Optional, Tuple
from urllib.parse import urlparse

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


# ============================================================
# I-5：题目侧图片提取 / 落盘（pure move 自 api/v1/question_import.py）
#   与上方 save_images_for_group 共处一模块 —— 两者共享同一套
#   占位符协议 [IMAGE:marker]、同一个 MAX_IMAGE_SIZE、同一套压缩策略，
#   只是落盘目录物理隔离（题目 static/questions/{qid}/ vs 题组
#   static/question-groups/{gid}/），绝不复用。
# ============================================================
def _extract_and_save_images(content_text, question_id, upload_dir='static/questions', question_obj=None):
    """
    从题目内容中提取base64或URL图片，保存到磁盘，返回路径列表。
    支持格式: <img src="..."> / [IMAGE:x_y] 占位符 / base64 data URI

    安全措施：路径遍历防护、SSRF检测、图片大小限制(MAX_IMAGE_SIZE)。

    路径一致性：upload_dir='static/questions' 与 main.py 中
    `app.mount('/static/questions', StaticFiles(directory=.../static/questions))` 对应，
    返回的 URL `/static/questions/{qid}/{filename}` 可被前端直接访问。

    即时更新（第3层防线）：传入 question_obj 时，会立即把 question_content
    和 options 中的 [IMAGE:xxx] 占位符替换为最终 <img> 标签，写入数据库，
    避免占位符残留导致前端图片不显示。
    """
    images = []

    # 无关图片检测（问题2-R2/P2-1）：委托共享模块 image_filters 的 classify_image
    # 三级判定（block/suspect/keep），与存量清理脚本使用同一判定标准。
    #   block   → 实锤无关图（QR 解码成功 / 黑名单 md5），导入侧直接跳过
    #   suspect → 疑似无关图（推广横幅/疑似二维码/尺寸启发式），放行但记日志待人工复核
    #   keep    → 正常内容图
    # 关键修复：旧逻辑 `hit != 'qr_likely'` 会把 promo_likely/tiny/extreme_ratio/blank
    # 也拦截，误杀正常图表/警务照片等核心内容；现改为仅拦截 block 级。
    def _is_irrelevant_image(img_data: bytes) -> bool:
        """检测图片是否为实锤无关内容（二维码解码成功 / 推广图黑名单）"""
        from ..image_filters import classify_image as _check
        decision, reason = _check(img_data)
        if decision == 'block':
            logger.debug(f"[images] 拦截无关图片({reason})")
            return True
        if decision == 'suspect':
            logger.info(f"[images] 疑似无关图片放行待人工复核({reason})")
        return False

    # Resolve absolute backend directory for path construction
    _current_file = os.path.abspath(__file__)
    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))
    img_dir = os.path.join(_backend_dir, upload_dir, str(question_id))
    os.makedirs(img_dir, exist_ok=True)

    # Directory where docx-extracted images are staged during parsing
    static_img_dir = os.path.join(_backend_dir, 'static', 'questions')

    # Helper: validate image data size
    def _check_size(data: bytes, label: str) -> bool:
        if len(data) > MAX_IMAGE_SIZE:
            logger.warning(f"[images] {label} 超过大小限制 ({len(data)} > {MAX_IMAGE_SIZE})")
            return False
        return True

    # Helper: validate extension
    def _safe_ext(raw: str, default: str = 'png') -> str:
        ext = (raw or default).lower().split('?')[0]
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            ext = default
        return ext

    # P2-2: 压缩 + 落盘（存储量最小）。压缩后按内容 md5 命名（相同图同名=天然去重）。
    # 返回 (filepath, filename) 或 (None, None)（压缩失败则回退原始字节原样落盘）。
    def _compress_and_store(img_data: bytes, prefix: str, idx: int, fallback_ext: str):
        from ..image_service import compress_image
        ext = _safe_ext(fallback_ext)
        if settings.IMAGE_COMPRESSION_ENABLED:
            try:
                img_data, ext = compress_image(
                    img_data,
                    max_side=settings.IMAGE_MAX_SIDE,
                    quality=settings.IMAGE_QUALITY,
                )
            except Exception:
                pass  # 压缩异常则原样落盘，不阻塞导入
        md5 = hashlib.md5(img_data).hexdigest()[:8]
        filename = f'{prefix}{idx}_{md5}.{ext}'
        filepath = os.path.join(img_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(img_data)
        return filepath, filename

    # 1. Extract <img> tags with src attribute
    img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', content_text or '')
    for idx, src in enumerate(img_tags):
        try:
            filepath = None
            if src.startswith('data:image'):
                # Base64 image — decode then check size
                header, data = src.split(',', 1)
                img_data = base64.b64decode(data)
                if not _check_size(img_data, f'base64图片{idx}'):
                    continue
                # ★ 新增：过滤无关图片（logo/页眉页脚）
                if _is_irrelevant_image(img_data):
                    continue
                # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                filepath, _filename = _compress_and_store(
                    img_data, 'img_', idx, header.split(';')[0].split('/')[-1])
            elif src.startswith('http'):
                # URL image — SSRF protection + size check
                import requests as _req

                parsed = urlparse(src)
                hostname = parsed.hostname
                if not hostname:
                    continue

                # SSRF check: resolve hostname and reject private/localhost IPs
                try:
                    resolved_ip = socket.gethostbyname(hostname)
                    ip_addr = ipaddress.ip_address(resolved_ip)
                    if ip_addr.is_private or ip_addr.is_loopback or ip_addr.is_link_local:
                        logger.warning(f"[images] SSRF blocked: {hostname} -> {resolved_ip}")
                        continue
                except Exception:
                    continue

                try:
                    resp = _req.get(src, timeout=10, stream=True, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if resp.status_code == 200:
                        # Check Content-Length header early if available
                        content_length = resp.headers.get('Content-Length')
                        if content_length and int(content_length) > MAX_IMAGE_SIZE:
                            logger.warning(f"[images] HTTP图片{idx} Content-Length超标: {content_length}")
                            resp.close()
                            continue

                        # Read in chunks, enforcing size limit
                        chunks = []
                        total = 0
                        for chunk in resp.iter_content(chunk_size=8192):
                            chunks.append(chunk)
                            total += len(chunk)
                            if total > MAX_IMAGE_SIZE:
                                logger.warning(f"[images] HTTP图片{idx} 超过大小限制")
                                resp.close()
                                chunks = None
                                break
                        if chunks is None:
                            continue
                        img_data = b''.join(chunks)
                        if not _check_size(img_data, f'HTTP图片{idx}'):
                            continue
                        # ★ 新增：过滤无关图片（logo/页眉页脚）
                        if _is_irrelevant_image(img_data):
                            continue
                        # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                        filepath, _filename = _compress_and_store(
                            img_data, 'img_', idx, src.rsplit('.', 1)[-1] if '.' in src else 'jpg')
                except Exception:
                    continue
            else:
                # Local path — use basename to prevent directory traversal
                safe_name = os.path.basename(src)
                if safe_name:
                    src_path = os.path.join(_backend_dir, 'uploads', safe_name)
                    if os.path.exists(src_path):
                        img_data = open(src_path, 'rb').read()
                        if not _check_size(img_data, f'本地图片{idx}'):
                            continue
                        ext = _safe_ext(safe_name.rsplit('.', 1)[-1])
                        filename = f'img_{idx}.{ext}'
                        filepath = os.path.join(img_dir, filename)
                        shutil.copy2(src_path, filepath)

            if filepath and os.path.exists(filepath):
                rel_path = f'/static/questions/{question_id}/{os.path.basename(filepath)}'
                images.append(rel_path)
                logger.debug(f"[images] 保存图片: {rel_path}")
        except Exception as e:
            logger.warning(f"[images] 图片{idx}保存失败: {e}")
            continue

    # 2. Extract [IMAGE:x_y] or [IMAGE:uuid_x_y] markers (generated by _extract_text_from_docx)
    marker_pattern = re.compile(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]')
    markers = marker_pattern.findall(content_text or '')
    for idx, marker_key in enumerate(markers):
        try:
            # 尝试多个可能的源文件路径
            possible_names = [f'{marker_key}.png']
            # 如果 marker_key 是 uuid_x_y 格式，也尝试 x_y 格式
            parts = marker_key.split('_')
            if len(parts) == 3:
                simple_key = f'{parts[1]}_{parts[2]}'
                possible_names.append(f'{simple_key}.png')

            src_file = None
            for candidate_name in possible_names:
                candidate_path = os.path.join(static_img_dir, candidate_name)
                if os.path.exists(candidate_path):
                    src_file = candidate_path
                    break

            if src_file:
                img_data = open(src_file, 'rb').read()
                if not _check_size(img_data, f'docx图片{marker_key}'):
                    continue
                # ★ 新增：过滤无关图片（logo/页眉页脚）
                if _is_irrelevant_image(img_data):
                    continue
                # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                dst_file, dst_name = _compress_and_store(img_data, 'img_docx_', idx, 'png')
                rel_path = f'/static/questions/{question_id}/{dst_name}'
                images.append(rel_path)
                logger.debug(f"[images] 保存docx图片: {rel_path}")

                # 关键：立即更新 question_content 中的占位符为最终 <img> 标签
                if question_obj is not None:
                    question_obj.question_content = (question_obj.question_content or '').replace(
                        f'[IMAGE:{marker_key}]',
                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                    )
                    # 同时更新 options 中的占位符
                    if hasattr(question_obj, 'options') and question_obj.options:
                        opts = question_obj.options
                        if isinstance(opts, str):
                            try:
                                import json as _json
                                opts_list = _json.loads(opts)
                                for o in opts_list:
                                    if isinstance(o, dict) and 'value' in o:
                                        o['value'] = o['value'].replace(
                                            f'[IMAGE:{marker_key}]',
                                            f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                                        )
                                question_obj.options = _json.dumps(opts_list, ensure_ascii=False)
                            except Exception:
                                pass
                        elif isinstance(opts, list):
                            for o in opts:
                                if isinstance(o, dict) and 'value' in o:
                                    o['value'] = (o['value'] or '').replace(
                                        f'[IMAGE:{marker_key}]',
                                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                                    )

                # ★ 同时回写答案解析：申论答案区大量使用思维导图/答案结构图
                #   （全语料实测 118 份文档有图，绝大多数在答案区）。
                #   旧实现只回写 question_content 与 options，导致答案里的
                #   [IMAGE:xxx] 占位符原样留在库中，前端显示不出图
                #   （用户实测截图里残留 [[IMAGE:f4419932_2_0]]）。
                if question_obj is not None and getattr(question_obj, 'answer_analysis', None):
                    question_obj.answer_analysis = (
                        question_obj.answer_analysis or ''
                    ).replace(
                        f'[IMAGE:{marker_key}]',
                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                    )

                # F-2：**不再删除**扁平暂存文件。此前 os.remove 会在重复导入同一
                # PDF 时（text_cache 命中、返回旧 marker）导致 sanitize 定位失败、
                # 图片全灭。暂存文件改由 cleanup_stale_staged_images 按时间延迟清理。
            else:
                logger.debug(f"[images] docx图片未找到: {marker_key}")
                # 文件不存在，移除占位符避免前端显示 broken image
                if question_obj is not None:
                    question_obj.question_content = (question_obj.question_content or '').replace(
                        f'[IMAGE:{marker_key}]', '')
                    # 答案解析里的同一占位符也必须清掉，否则前端照样显示原始文本
                    if getattr(question_obj, 'answer_analysis', None):
                        question_obj.answer_analysis = (
                            question_obj.answer_analysis or ''
                        ).replace(f'[IMAGE:{marker_key}]', '')
        except Exception as e:
            logger.warning(f"[images] docx图片{idx}({marker_key})保存失败: {e}")
            continue

    return images


def cleanup_stale_staged_images(max_age_days: int = 7) -> int:
    """按时间清理暂存扁平图（F-2 配套，挂调度器每天一次）。

    只删除 ``_STAGING_DIR`` 根目录下、命名符合暂存形态（hex_题号_序号.png 或
    题号_序号.png）且 mtime 超过 max_age_days 的文件。绝不触碰 {qid}/ 子目录
    内的正式题目图——那是落库后的唯一副本。

    返回删除文件数；任何异常吞掉并告警（清理失败不阻断任何业务）。
    """
    import time as _time

    # 裸文件名形态（无 [IMAGE:] 包装）：hex_题号_序号 或 题号_序号
    _staged_name_re = re.compile(r'(?:[a-f0-9]+_\d+_\d+|\d+_\d+)')
    removed = 0
    try:
        cutoff = _time.time() - max_age_days * 86400
        if not os.path.isdir(_STAGING_DIR):
            return 0
        for name in os.listdir(_STAGING_DIR):
            path = os.path.join(_STAGING_DIR, name)
            if not os.path.isfile(path) or not name.lower().endswith('.png'):
                continue
            if not _staged_name_re.fullmatch(name[:-4]):
                continue
            if os.path.getmtime(path) > cutoff:
                continue
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
        if removed:
            logger.info(f"[images] 清理暂存图 {removed} 张（>={max_age_days} 天）")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[images] 暂存图清理失败: {e}")
    return removed
