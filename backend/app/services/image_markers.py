r"""题图占位符唯一解析器（M5）。

为什么单独成文件
----------------
同一个 marker 在三个地方被解析：错题详情接口、答题页的图片清洗、导入预览。
历史上三处各写一套正则，导致：

  · 详情接口用 `img_docx_(\d+)_(\d+)_` 从 image_path 反推 key → 真实路径是
    `/static/questions/431/img_0_5661de6d.png`，**永远匹配不到**，image_map 恒为空；
  · 前端用 `\[IMAGE:([a-fA-F0-9]+)_(\d+)\]`（两段式）→ 真实 marker 是三段式
    `[IMAGE:5d739001_79_0]`，匹配不上，裸标记原样显示成文字；
  · 磁盘文件名恰好就是 `{hash}_{seq}_{idx}.png` 平铺在 static/questions/ 下。

故这里定义唯一的解析语义：marker 三段 = (内容哈希, 题号, 图序)，
磁盘路径优先级 `{hash}_{seq}_{idx}.png` → 同 hash 同序 → 同 hash 任意 → 交给
image_service 的多层兜底（子目录 / question_image 表）。
"""
import glob
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

from . import image_service

# 三段式（现行）、两段式（历史存量）都接受；hash 允许 3 位以上，兼容旧 md5 片段
MARKER_RE = re.compile(r"\[IMAGE:([0-9a-fA-F]{3,})[_-](\d+)(?:[_-](\d+))?\]", re.IGNORECASE)


def iter_markers(*texts: Optional[str]) -> List[Tuple[str, str, str, str]]:
    """遍历若干段文本里的全部图片标记，返回 [(整段, hash, seq, idx)]，去重。"""
    seen = set()
    out: List[Tuple[str, str, str, str]] = []
    for text in texts:
        if not text or "[IMAGE:" not in str(text):
            continue
        for m in MARKER_RE.finditer(str(text)):
            full = m.group(0)
            if full in seen:
                continue
            seen.add(full)
            out.append((full, m.group(1).lower(), m.group(2), m.group(3) or "0"))
    return out


def _flat_url(file_name: str) -> str:
    return f"/static/questions/{file_name}"


def resolve(hash_: str, seq: str, idx: str, question_id: Optional[int] = None,
            db=None) -> Optional[str]:
    """把 (hash, seq, idx) 解析成磁盘上真实存在的图片 URL；全部失败返回 None。"""
    hash_ = (hash_ or "").lower()
    root = image_service.STATIC_IMG_ROOT

    # 1) 精确命中：{hash}_{seq}_{idx}.png
    exact = f"{hash_}_{seq}_{idx}"
    for ext in (".png", ".jpg", ".jpeg"):
        if os.path.isfile(os.path.join(root, exact + ext)):
            return _flat_url(exact + ext)
    # 2) 同 hash 段的宽松匹配：先找同 hash 同图序，再退化为同 hash 任意一张。
    #    hash 是图片内容哈希，同 hash 的不同 seq 只是被多道题复用，图是同一张。
    pattern = os.path.join(root, f"{hash_}_*")
    candidates = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    if candidates:
        same_idx = [p for p in candidates if p.rsplit("_", 1)[-1].split(".")[0] == str(idx)]
        chosen = sorted(same_idx or candidates)[0]
        return _flat_url(os.path.basename(chosen))
    # 3) 交给既有 10 层防线（子目录约定 / question_image 表）
    return image_service.resolve_image_marker(
        f"{hash_}_{seq}_{idx}", question_id=question_id, db=db
    )


def build_image_map(*texts: Optional[str], question_id: Optional[int] = None,
                    db=None) -> Dict[str, str]:
    """按文本里出现的标记生成 image_map。

    键同时提供 `hash_seq`（两段）与 `hash_seq_idx`（三段），
    前端无论按哪种键查都能命中；解析失败的键值为空串，由前端渲染缺失占位。
    """
    result: Dict[str, str] = {}
    for _full, h, seq, idx in iter_markers(*texts):
        url = resolve(h, seq, idx, question_id=question_id, db=db) or ""
        result[f"{h}_{seq}"] = url
        result[f"{h}_{seq}_{idx}"] = url
    return result


def describe_images(*texts: Optional[str], question_id: Optional[int] = None,
                    db=None) -> List[Dict[str, object]]:
    """给接口用的结构化图片清单：索引 / 标记 / URL / 是否存在。"""
    items: List[Dict[str, object]] = []
    for order, (full, h, seq, idx) in enumerate(iter_markers(*texts)):
        url = resolve(h, seq, idx, question_id=question_id, db=db)
        items.append({
            "index": order,
            "marker": full,
            "hash": h,
            "seq": seq,
            "idx": idx,
            "url": url or "",
            "exists": bool(url),
        })
    return items


def strip_markers(text: Optional[str]) -> str:
    """去掉标记（用于摘要 / 搜索索引，避免哈希串污染匹配）。"""
    if not text:
        return ""
    return MARKER_RE.sub(" ", str(text))
