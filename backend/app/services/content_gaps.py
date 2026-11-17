# -*- coding: utf-8 -*-
"""内容缺口体检（v9 M7）。

为什么需要它
------------
用户会在后期手工导入题本，但题本本身可能缺图、缺横线、缺选项、缺答案、
缺解析、缺材料。这些问题在导入成功的返回值里完全看不到（导入只看"题数"），
等到学生在错题集里打开才发现，修复成本高、体验差。

这里把六类缺口定义成可枚举、可定位的检查项，供三处复用：
  1. 导入确认（/api/import/confirm）完成后自动对本批题目跑一次，随响应返回；
  2. 教师端「内容修复中心」按类型分组列出，点击直达该题；
  3. 学生端错题集/详情页显示缺口标签，避免"看起来是空的"。

判定原则：**宁可漏报不误报**。缺图片必须真的解析不到磁盘文件才算；
横线只在题干确实提到"横线/划线/空白处"却没有占位符时才算，避免把正常题干算成缺口。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from . import image_markers

# 缺口类型 → 中文名（前端/报告共用，避免两处各写一份）
KINDS: Dict[str, str] = {
    "missing_image": "配图缺失",
    "missing_blank": "横线缺失",
    "missing_option": "选项缺失",
    "missing_answer": "答案缺失",
    "missing_analysis": "解析缺失",
    "missing_material": "材料缺失",
}

# 题干提到横线/划线 → 应该有占位符
_BLANK_MENTION = re.compile(r"横线|划线|空白处|下划线")
# 占位符：连续下划线 / 全角下划线 / 空括号 / 空方括号
_BLANK_PLACEHOLDER = re.compile(r"_{2,}|＿{2,}|（\s{2,}）|\(\s{2,}\)|【\s*】|\[\s*\]")
# 复合题材料引用
_MATERIAL_MENTION = re.compile(
    r"给定资料|根据资料|根据材料|阅读以下材料|以下材料|材料[一二三四五六七八九十\d]|阅读材料"
)
# 选项占位文本（题库原始内容缺失，用户后期手工补）
_OPTION_PLACEHOLDER = re.compile(r"^\s*[（(]?\s*(待补充|略|无|暂无)\s*[）)]?\s*$|图中的\s*[A-D]\s*选项")
# 存量脏数据：题干里被当文本渲染的 <img> 标签
_IMG_SRC = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)

import os as _os


def _static_exists(url: str, question_id: Optional[int] = None) -> bool:
    """判断一个 /static/questions/... 路径在磁盘上是否真的存在。

    真实布局是平铺（backend/app/static/questions/{hash}_{seq}_{idx}.png），
    但 image_path 列写的是子目录形式（.../{qid}/xxx.png），故两种都要试。
    """
    if not url:
        return False
    from . import image_service

    root = image_service.STATIC_IMG_ROOT
    name = url.replace("\\", "/").rsplit("/", 1)[-1]
    if not name:
        return False
    candidates = []
    if question_id:
        candidates.append(_os.path.join(root, str(question_id), name))
    candidates.append(_os.path.join(root, name))
    return any(_os.path.isfile(c) for c in candidates)
_ANSWER_LETTER = re.compile(r"^\s*[A-Da-d](\s*[,，、]\s*[A-Da-d])*\s*$")


def parse_options(raw: Any) -> List[Dict[str, str]]:
    """options 列兼容 JSON 字符串 / list / dict 三种历史写法。"""
    data = raw
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return []
    out: List[Dict[str, str]] = []
    if isinstance(data, dict):
        data = [{"key": k, "value": v} for k, v in data.items()]
    if isinstance(data, list):
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                key = str(item.get("key") or item.get("label") or chr(65 + idx))
                value = str(item.get("value") or item.get("text") or item.get("content") or "")
            else:
                key = chr(65 + idx)
                value = str(item or "")
            out.append({"key": key.strip(), "value": value.strip()})
    return out


def _option_texts(options: Iterable[Dict[str, str]]) -> List[str]:
    return [o.get("value") or "" for o in options]


def check_question(q, group=None, image_cache: Optional[Dict[str, bool]] = None,
                   image_rows: Optional[List[str]] = None) -> Dict[str, Any]:
    """单题六类缺口检查。

    q: QuestionBank 行；group: 该题关联的 QuestionGroup（可为 None）；
    返回 {"question_id", "kinds": [...], "details": {kind: 说明}, "missing_images": [...]}。
    """
    cache = image_cache if image_cache is not None else {}
    kinds: List[str] = []
    details: Dict[str, str] = {}

    content = str(getattr(q, "question_content", "") or "")
    options = parse_options(getattr(q, "options", None))
    answer = str(getattr(q, "answer", "") or "").strip()
    analysis = str(getattr(q, "answer_analysis", "") or "").strip()
    requirements = str(getattr(q, "requirements", "") or "")
    group_id = getattr(q, "group_id", None)

    # 1) 配图：marker 解析不到磁盘文件
    marker_texts = [content, requirements] + _option_texts(options)
    missing_images: List[str] = []
    for full, hash_, seq, idx in image_markers.iter_markers(*marker_texts):
        key = f"{hash_}_{seq}_{idx}"
        if key not in cache:
            try:
                cache[key] = bool(
                    image_markers.resolve(hash_, seq, idx,
                                          question_id=getattr(q, "question_id", None))
                )
            except Exception:
                cache[key] = True  # 解析异常不当缺口，避免误报
        if not cache[key]:
            missing_images.append(full)
    # 1b) 存量 <img src> 与 question_image 表：marker 之外的两条图片来源
    for src in _IMG_SRC.findall(content):
        key = "src:" + src
        if key not in cache:
            cache[key] = _static_exists(src, getattr(q, "question_id", None))
        if not cache[key]:
            missing_images.append(f"<img {src}>")
    for path in image_rows or []:
        key = "row:" + str(path)
        if key not in cache:
            cache[key] = _static_exists(str(path), getattr(q, "question_id", None))
        if not cache[key]:
            missing_images.append(str(path))

    if missing_images:
        kinds.append("missing_image")
        details["missing_image"] = f"{len(missing_images)} 张图解析不到文件：{'、'.join(missing_images[:3])}"

    # 2) 横线：提到却无占位符
    if _BLANK_MENTION.search(content) and not _BLANK_PLACEHOLDER.search(content):
        kinds.append("missing_blank")
        details["missing_blank"] = "题干提到横线/划线，但没有 ____ 占位符"

    # 3) 选项：占位文本、数量不足、或答案是字母却没有选项
    placeholder_opts = [o["key"] for o in options if _OPTION_PLACEHOLDER.search(o["value"] or "")]
    if placeholder_opts:
        kinds.append("missing_option")
        details["missing_option"] = f"选项 {','.join(placeholder_opts)} 为占位文本"
    elif len(options) == 0 and _ANSWER_LETTER.match(answer):
        kinds.append("missing_option")
        details["missing_option"] = f"答案为 {answer} 但没有任何选项"
    elif 0 < len([o for o in options if o["value"]]) < 2:
        kinds.append("missing_option")
        details["missing_option"] = "有效选项少于 2 个"

    # 4) 答案
    if not answer:
        kinds.append("missing_answer")
        details["missing_answer"] = "answer 为空"

    # 5) 解析
    if len(analysis) < 10:
        kinds.append("missing_analysis")
        details["missing_analysis"] = "answer_analysis 为空或过短"

    # 6) 材料：复合题缺材料，或题干引用了材料却没挂题组
    if group_id:
        material = str(getattr(group, "shared_content", "") or "") if group is not None else ""
        if len(material.strip()) < 10:
            kinds.append("missing_material")
            details["missing_material"] = (
                "题组材料缺失" if group is not None else f"题组 {group_id} 不存在"
            )
    elif _MATERIAL_MENTION.search(content):
        kinds.append("missing_material")
        details["missing_material"] = "题干引用了给定资料/材料，但未关联题组"

    return {
        "question_id": getattr(q, "question_id", None),
        "kinds": kinds,
        "details": details,
        "missing_images": missing_images,
    }


def scan_questions(db, questions: Iterable[Any]) -> Dict[str, Any]:
    """对一批题目做体检，返回 summary + 逐题明细。

    材料按 group_id 批量取，避免每题一次查询（申论题组材料往往上万字）。
    """
    from ..models.models import QuestionGroup, QuestionImage

    rows = list(questions)
    group_ids = {getattr(q, "group_id", None) for q in rows if getattr(q, "group_id", None)}
    groups: Dict[int, Any] = {}
    if group_ids:
        for g in db.query(QuestionGroup).filter(QuestionGroup.id.in_(group_ids)).all():
            groups[g.id] = g

    # question_image 一次性取回：按题分组，避免每题一次查询
    id_list = [getattr(q, "question_id", None) for q in rows]
    id_list = [int(i) for i in id_list if i]
    img_map: Dict[int, List[str]] = {}
    if id_list:
        for img in (db.query(QuestionImage)
                      .filter(QuestionImage.question_id.in_(id_list))
                      .all()):
            if getattr(img, "image_path", None):
                img_map.setdefault(int(img.question_id), []).append(str(img.image_path))

    cache: Dict[str, bool] = {}
    items: List[Dict[str, Any]] = []
    counter = {k: 0 for k in KINDS}
    for q in rows:
        res = check_question(
            q,
            group=groups.get(getattr(q, "group_id", None)),
            image_cache=cache,
            image_rows=img_map.get(int(getattr(q, "question_id", 0) or 0)),
        )
        if res["kinds"]:
            for k in res["kinds"]:
                counter[k] = counter.get(k, 0) + 1
            items.append(res)

    return {
        "scanned": len(rows),
        "gap_questions": len(items),
        "by_kind": counter,
        "kind_labels": KINDS,
        "items": items,
    }


def scan_ids(db, question_ids: List[int]) -> Dict[str, Any]:
    """按题目 ID 体检（导入确认后调用）。"""
    from ..models.models import QuestionBank

    if not question_ids:
        return {"scanned": 0, "gap_questions": 0, "by_kind": {k: 0 for k in KINDS},
                "kind_labels": KINDS, "items": []}
    rows = (
        db.query(QuestionBank)
        .filter(QuestionBank.question_id.in_(question_ids))
        .all()
    )
    return scan_questions(db, rows)


def scan_query(db, subject_id: Optional[int] = None, kind: Optional[str] = None,
               page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """按科目全库体检并分页返回某一类缺口（教师端「内容修复中心」用）。

    全库扫描 3750 题约需数百毫秒（图片解析有进程内缓存），故不做额外缓存表；
    避免引入"扫描结果过期"的一致性问题。
    """
    from ..models.models import QuestionBank

    query = db.query(QuestionBank)
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    result = scan_questions(db, query.all())

    wanted = [kind] if kind else [k for k in KINDS if result["by_kind"].get(k)]
    detail_map = {it["question_id"]: it for it in result["items"]}
    ids = [
        qid for it in result["items"] for qid in [it["question_id"]]
        if kind is None or kind in it["kinds"]
    ]
    total = len(ids)
    start = max(0, (page - 1) * page_size)
    page_ids = ids[start:start + page_size]
    rows = (
        db.query(QuestionBank).filter(QuestionBank.question_id.in_(page_ids)).all()
        if page_ids else []
    )
    by_id = {r.question_id: r for r in rows}

    questions = []
    for qid in page_ids:
        q = by_id.get(qid)
        if not q:
            continue
        detail = detail_map.get(qid, {"kinds": [], "details": {}})
        questions.append({
            "question_id": qid,
            "subject_id": q.subject_id,
            "snippet": (str(q.question_content or "")[:80]),
            "year": q.year,
            "kinds": detail["kinds"],
            "details": detail["details"],
            "quality_score": getattr(q, "quality_score", None),
        })

    return {
        "scanned": result["scanned"],
        "gap_questions": result["gap_questions"],
        "by_kind": result["by_kind"],
        "kind_labels": KINDS,
        "kinds_in_scope": wanted,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": questions,
    }
