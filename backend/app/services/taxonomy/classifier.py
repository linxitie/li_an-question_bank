# -*- coding: utf-8 -*-
"""考点（level=2）分类打分器。

设计要点：
- 规则全部来自 exam_points.yaml，不允许在本模块硬编码考点名，便于运营改词表。
- 有知识点时只在该知识点（sub_category）的考点集合内打分，天然消除跨知识点误判；
  知识点为空（导入未分类）时按科目放宽到该科目全部考点，避免整批落「其他」。
- 题干与选项一起参与打分：公专/判断推理的区分度常藏在选项里（如"有期徒刑/拘役/管制"）。
- 输入文本先去掉 [IMAGE:...] 标记与 HTML 标签：图片标记对语义判断是噪声。
- 题尾（设问句）重复计分：同一份材料可挂多个设问，设问才是分类依据。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

RULES_PATH = Path(__file__).with_name("exam_points.yaml")

# 与 questionRender.js 的 [IMAGE:hash_seq_idx] 标记保持一致
_IMAGE_MARK_RE = re.compile(r"\[IMAGE:[^\]]*\]")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\u3000]+")

# 题尾取多少字作为「设问区」；公专题干平均 91 字，120 足够覆盖设问句
_TAIL_CHARS = 120

# 长度越长越具区分度：单字词极易误命中，因此只给 1 分
_WEIGHT_LEN4 = 3
_WEIGHT_LEN3 = 2
# 中文双字词多为实义名词（合同/侵权/拘留/盘查），是有效区分信号；
# 单字才当噪声处理，否则民法、刑法类题目永远凑不到阈值。
_WEIGHT_LEN2 = 2
_WEIGHT_SHORT = 1

AUTO_SCORE = 6
AUTO_MARGIN = 2
REVIEW_SCORE = 3


_OPTION_JSON_RE = re.compile(r'"value"\s*:\s*"([^"]*)"')


def options_to_text(options: Any) -> str:
    """把 options 列还原成可读文本。

    question_bank.options 存的是 JSON 字符串（且为 ASCII 转义、含 key/value），
    直接拼进打分文本会得到 \u5c06 这种转义串，导致选项全不命中；
    这里解析出 value 并连同 key 一起拼接。
    """
    if not options:
        return ""
    if isinstance(options, (list, dict)):
        data: Any = options
    else:
        raw = str(options).strip()
        if not raw:
            return ""
        try:
            data = json.loads(raw)
        except Exception:
            # 不是合法 JSON：可能是纯文本选项，兜底做转义解码
            return _OPTION_JSON_RE.sub(lambda m: m.group(1), raw).replace("\\n", " ")
    parts: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                k = str(item.get("key") or "").strip()
                v = str(item.get("value") or "").strip()
                if v:
                    parts.append(f"{k}.{v}" if k else v)
            elif item:
                parts.append(str(item))
    elif isinstance(data, dict):
        for k, v in data.items():
            if v:
                parts.append(f"{k}.{v}")
    return " ".join(parts)


def normalize_text(text: Optional[str]) -> str:
    """清掉图片标记/HTML/多余空白，保留全部正文。"""
    if not text:
        return ""
    s = _IMAGE_MARK_RE.sub(" ", text)
    s = _TAG_RE.sub(" ", s)
    s = s.replace("\r", "\n")
    s = _WS_RE.sub(" ", s)
    return s.strip()


@lru_cache(maxsize=1)
def _load_rules_bundle() -> Dict[str, Any]:
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    rules: Dict[int, List[Dict[str, Any]]] = {}
    for sc_id, block in (data.get("sub_categories") or {}).items():
        points = []
        for p in block.get("points") or []:
            points.append({
                "point_id": int(p["id"]),
                "name": p.get("name") or "",
                "keywords": [str(k) for k in (p.get("keywords") or [])],
                "patterns": [re.compile(x) for x in (p.get("patterns") or [])],
                "exclude": [str(k) for k in (p.get("exclude") or [])],
            })
        rules[int(sc_id)] = points
    subjects: Dict[int, List[int]] = {}
    for sid, scs in (data.get("subjects") or {}).items():
        subjects[int(sid)] = [int(x) for x in scs]
    return {"rules": rules, "subjects": subjects}


def load_rules() -> Dict[int, List[Dict[str, Any]]]:
    """返回 {sub_category_id: [考点规则, ...]}。"""
    return _load_rules_bundle()["rules"]


def load_subject_map() -> Dict[int, List[int]]:
    """返回 {subject_id: [sub_category_id, ...]}。"""
    return _load_rules_bundle()["subjects"]


def _candidates(sub_category_id: Optional[int], subject_id: Optional[int]) -> List[Dict[str, Any]]:
    bundle = _load_rules_bundle()
    rules = bundle["rules"]
    if sub_category_id:
        hit = rules.get(int(sub_category_id))
        if hit:
            return hit
    if subject_id:
        out: List[Dict[str, Any]] = []
        for sc in bundle["subjects"].get(int(subject_id), []):
            out.extend(rules.get(sc) or [])
        if out:
            return out
    # 两者都缺失：全量打分只用于排查，正常入库不应走到这里
    all_rules: List[Dict[str, Any]] = []
    for sc in sorted(rules):
        all_rules.extend(rules[sc])
    return all_rules


def _keyword_weight(kw: str) -> int:
    if len(kw) >= 4:
        return _WEIGHT_LEN4
    if len(kw) == 3:
        return _WEIGHT_LEN3
    if len(kw) == 2:
        return _WEIGHT_LEN2
    return _WEIGHT_SHORT


def _score_one(rule: Dict[str, Any], body: str, tail: str,
               context: str = "", ctx_cap: int = 3) -> Dict[str, Any]:
    hits: List[str] = []
    score = 0
    for kw in rule["keywords"]:
        if not kw:
            continue
        w = _keyword_weight(kw)
        if kw in body:
            score += w
            hits.append(kw)
        # 设问句里出现，说明这就是本题考点，再算一遍
        if kw in tail:
            score += w
    for pat in rule["patterns"]:
        if pat.search(body):
            score += _WEIGHT_LEN4
            hits.append(pat.pattern)
    # 复合题子题：题干只有「正确的做法是：」，情境在 question_groups.shared_content。
    # 材料常同时服务多道子题，信号弱且易串味，因此每条命中只算 1 分且总分封顶 3。
    ctx_score = 0
    if context:
        for kw in rule["keywords"]:
            if kw and kw in context:
                ctx_score += 1
                hits.append("材料:" + kw)
        for pat in rule["patterns"]:
            if pat.search(context):
                ctx_score += 1
        score += min(ctx_score, ctx_cap)
    for kw in rule["exclude"]:
        if kw and kw in body:
            return {"point_id": rule["point_id"], "name": rule["name"],
                    "score": 0, "hits": [], "excluded": True}
    return {"point_id": rule["point_id"], "name": rule["name"],
            "score": score, "hits": hits, "excluded": False}


_EMPTY = {"point_id": None, "name": None, "score": 0, "tier": "unmatched",
          "second_score": 0, "margin": 0, "hits": []}


@lru_cache(maxsize=1)
def _point_sc_map() -> Dict[int, int]:
    """考点 → 所属知识点（sub_category）。

    跨知识点纠正需要知道「命中的考点挂在哪个知识点下」，
    否则无法判断这道题是否被标错了知识点。
    """
    out: Dict[int, int] = {}
    for sc_id, points in _load_rules_bundle()["rules"].items():
        for p in points:
            out[int(p["point_id"])] = int(sc_id)
    return out


def point_sc_index() -> Dict[int, int]:
    return dict(_point_sc_map())


def expected_sub_category(point_id: Optional[int]) -> Optional[int]:
    """考点对应的知识点 ID；未知考点返回 None。"""
    if not point_id:
        return None
    return _point_sc_map().get(int(point_id))


def _texts(question_text: str, options_text: Optional[str],
           context_text: Optional[str]) -> Optional[Dict[str, Any]]:
    stem = normalize_text(question_text)
    opts = normalize_text(options_to_text(options_text))
    body = (stem + "\n" + opts) if opts else stem
    if not body:
        return None
    tail = stem[-_TAIL_CHARS:] if stem else body[-_TAIL_CHARS:]
    ctx = normalize_text(context_text)[:4000] if context_text else ""
    # 情境分析子题（题干只有「正确的做法是：」，二十来个字）本身不含情境，
    # 材料才是题干；此时放宽材料权重上限，但仍低于「题干+选项」的合成分。
    ctx_cap = 6 if (ctx and len(stem) < 40) else 3
    return {"stem": stem, "body": body, "tail": tail, "ctx": ctx, "ctx_cap": ctx_cap}


def _rank(rules: List[Dict[str, Any]], parts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    scored = [_score_one(r, parts["body"], parts["tail"], parts["ctx"], parts["ctx_cap"])
              for r in rules]
    scored.sort(key=lambda x: (-x["score"], x["point_id"]))
    best = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0
    if best["score"] <= 0:
        return None
    margin = best["score"] - second
    if best["score"] >= AUTO_SCORE and margin >= AUTO_MARGIN:
        tier = "auto"
    elif best["score"] >= REVIEW_SCORE:
        tier = "review"
    else:
        tier = "unmatched"
    return {"point_id": best["point_id"], "name": best["name"], "score": best["score"],
            "tier": tier, "second_score": second, "margin": margin,
            "hits": best["hits"][:8]}


def classify(question_text: str,
             sub_category_id: Optional[int],
             options_text: Optional[str] = None,
             subject_id: Optional[int] = None,
             context_text: Optional[str] = None) -> Dict[str, Any]:
    """给一道题打分，返回最佳考点与置信档位。

    返回 {point_id, name, score, tier, second_score, margin, hits}；
    tier ∈ auto（可直接落库）/ review（进人工复核队列）/ unmatched（保留收容）。
    """
    rules = _candidates(sub_category_id, subject_id)
    parts = _texts(question_text, options_text, context_text)
    if not rules or not parts:
        return dict(_EMPTY)
    return _rank(rules, parts) or dict(_EMPTY)


def classify_cross(question_text: str,
                   subject_id: Optional[int],
                   current_sub_category_id: Optional[int] = None,
                   options_text: Optional[str] = None,
                   context_text: Optional[str] = None) -> Dict[str, Any]:
    """跨知识点打分（v8.1 跨知识点纠正用）。

    与 classify 的区别：候选集是整个科目的 91 个考点，不按题目现有知识点收缩。
    用途是识别「知识点本身就标错了」的题——导入时按试卷大题贴标签，
    会把图形推理贴成言语理解、把微生物发酵贴成判断推理，此时按标签收缩只会
    在错误的知识点里挑一个错得最像的考点。

    返回在 classify 的字段上追加：
    - sc_id      ：命中考点所属知识点
    - old_sc_id  ：传入的当前知识点
    - sc_changed ：两者不一致时 True（需同步纠正知识点）
    """
    bundle = _load_rules_bundle()
    rules: List[Dict[str, Any]] = []
    scs = bundle["subjects"].get(int(subject_id)) if subject_id else None
    for sc in (scs or sorted(bundle["rules"])):
        rules.extend(bundle["rules"].get(sc) or [])
    parts = _texts(question_text, options_text, context_text)
    res = _rank(rules, parts) if (rules and parts) else None
    if not res:
        out = dict(_EMPTY)
        out.update({"sc_id": None, "old_sc_id": current_sub_category_id, "sc_changed": False})
        return out
    sc_id = _point_sc_map().get(int(res["point_id"]))
    res["sc_id"] = sc_id
    res["old_sc_id"] = current_sub_category_id
    res["sc_changed"] = bool(sc_id and int(sc_id) != int(current_sub_category_id or 0))
    return res
