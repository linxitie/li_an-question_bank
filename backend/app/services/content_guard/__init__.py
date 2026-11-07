"""内容安全知识库服务入口（敏感词自生长 KB）。

对外只暴露四个动作：
- guard_text：论坛/资料/昵称等写路径的统一审核闸门
- check_text：只检测、不落判定（资料导入等只读预检）
- seed_defaults：幂等种入政策、词条、变体与图谱边
- reload_engine：人工改库后主动刷新 DFA

设计约束见 docs/superpowers/specs/论坛敏感词自生长知识库_v1.md。
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from . import audit, catalog, engine, graph, judgments, normalizer, obsidian, proposals, reconcile, redteam, stats

logger = logging.getLogger(__name__)

__all__ = [
    "guard_text",
    "check_text",
    "seed_defaults",
    "reload_engine",
    "audit",
    "catalog",
    "engine",
    "graph",
    "judgments",
    "normalizer",
    "obsidian",
    "proposals",
    "reconcile",
    "redteam",
    "stats",
]

_READY: dict[str, tuple[bool, float]] = {}


def _tables_ready(db: Session) -> bool:
    """缓存建表检查；未建表时按旧版过滤器降级，避免论坛 500。"""
    try:
        bind = db.get_bind()
        url = str(bind.engine.url) if hasattr(bind, "engine") else str(bind.url)
    except Exception:  # noqa: BLE001
        url = "unknown"
    cached = _READY.get(url)
    now = time.time()
    if cached and (cached[0] or now - cached[1] < 30):
        return cached[0]
    try:
        ready = inspect(db.get_bind()).has_table("cg_term")
    except Exception:  # noqa: BLE001
        ready = False
    _READY[url] = (ready, now)
    return ready


def _legacy_result(text: str) -> dict:
    from ..sensitive_words import SensitiveLevel, sensitive_filter

    result = sensitive_filter.detect(text or "")
    level = result.get("level")
    decision = {"blocked": "block", "masked": "mask", "reviewed": "review"}.get(level, "pass")
    return {
        **result,
        "hits": [],
        "policy_ids": [],
        "policy_clauses": [],
        "evidence": [{"step": "decision", "decision": decision, "reason": "旧版过滤器降级"}],
        "confidence": 0.9 if level == "blocked" else (0.8 if level == "masked" else 0.6),
        "decision": decision,
        "judgment_id": None,
        "task_id": None,
        "engine_source": "legacy",
        "degraded": True,
    }


_DECISION_RANK = {"pass": 0, "review": 1, "mask": 2, "block": 3}
_LEVEL_BY_DECISION = {"review": "reviewed", "mask": "masked", "block": "blocked"}


def guard_text(
    db: Session,
    text: str,
    *,
    scene: str = "forum_post",
    source_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """审核闸门。返回字段与旧 sensitive_filter.detect 兼容，并新增 decision/evidence。

    2026-11-06 需求：**命中即打码，不做语境放行**。
    - 词库命中后只有 block / mask / review 三种出口，任何分支都不得降成 pass；
    - review 级词条同样进入遮罩区间（发布侧统一按 masked_text 落库），人工任务保留；
    - 链接四层：白名单放行 / 短链与黑名单 block / 普通外链打码送审。
    """
    enabled = os.environ.get("CONTENT_GUARD_ENABLED", "true").strip().lower()
    if enabled in ("false", "0", "off"):
        return _legacy_result(text)

    ready = _tables_ready(db)
    raw = text or ""
    should_persist = bool(persist and ready)

    # 1) 词库判定（先不落库，最终结论确定后只落一条）
    result = judgments.guard_text(
        db, raw, scene=scene, source_id=source_id, user_id=user_id, persist=False
    )
    base_decision = result.get("decision") or "pass"
    decision = base_decision
    reason = "命中词库"
    evidence = list(result.get("evidence") or [])

    # 2) 命中即打码：blocked/masked/reviewed 三种命中全部进入遮罩区间
    masked = _mask_all_hits(raw, result)

    # 3) 政策层（vault ruleset）：只升不降；只对实际命中的词条打码
    policy_terms: list[str] = []
    if _policy_enabled():
        bucket, policy_terms, policy_ids = _policy_signal(raw, scene)
        if bucket in ("hold", "mask", "block"):
            policy_decision = "review" if bucket == "block" else "mask"
            if _DECISION_RANK[policy_decision] > _DECISION_RANK[decision]:
                decision = policy_decision
                reason = f"政策规则集命中（{bucket}）"
            result["policy_ids"] = _merge_ids(result.get("policy_ids"), policy_ids)
            evidence.append(
                {"step": "policy_ruleset", "decision": policy_decision,
                 "terms": list(policy_terms[:5])}
            )
    masked = _apply_terms(masked, policy_terms)

    # 4) 链接四层
    link = _link_signal(raw)
    if link["decision"] == "block":
        decision = "block"
        reason = link["reason"]
        result["words"] = _merge_words(result.get("words"), link["words"])
        evidence.append({"step": "link", "decision": "block", "reason": link["reason"]})
    elif link["decision"] == "mask":
        masked = _apply_urls(masked, link["urls"])
        if decision != "block":
            decision = "review"
            reason = link["reason"]
        result["words"] = _merge_words(result.get("words"), link["words"])
        evidence.append({"step": "link", "decision": "review", "reason": link["reason"]})

    # 4.5) 命中即打码可发布：blocked 级词条降级为 mask（链接拦截除外）
    if base_decision == "block" and link["decision"] != "block" and _block_as_mask():
        decision = "mask"
        reason = "命中 blocked 级词条，按配置降级为打码发布"
        evidence.append(
            {"step": "policy_switch", "decision": "mask", "reason": "MODERATION_BLOCK_AS_MASK=1"}
        )

    # 5) 收口：结论 / 等级 / 被打码文本 / 证据链
    if decision != base_decision:
        evidence = [item for item in evidence if item.get("step") != "decision"]
        evidence.append({"step": "decision", "decision": decision, "reason": reason})
    result["evidence"] = evidence

    if decision == "pass":
        result.update(
            {"decision": "pass", "level": None, "hit": False,
             "masked_text": raw, "judgment_id": None, "task_id": None}
        )
    else:
        result.update(
            {"decision": decision, "level": _LEVEL_BY_DECISION[decision],
             "hit": True, "masked_text": masked}
        )
        if not result.get("confidence"):
            result["confidence"] = 0.9 if link["decision"] else 0.85
        if should_persist:
            judgments.persist_result(
                db, raw, result, scene=scene, source_id=source_id, user_id=user_id
            )
        else:
            result["judgment_id"] = None
            result["task_id"] = None

    result.pop("_policies", None)
    if not ready:
        result["degraded"] = True
        result["degraded_reason"] = "cg_* 表未就绪，已降级为旧版词库"
    return result


def check_text(db: Session, text: str, *, scene: str = "precheck") -> dict:
    return guard_text(db, text, scene=scene, persist=False)


def seed_defaults(db: Session, actor: str = "system") -> dict:
    """幂等初始化；返回本次新增数量。已有人工改动不会被覆盖。"""
    policies = catalog.seed_policies(db)
    seeded = catalog.seed_terms(db, actor=actor)
    created = policies or seeded["terms"] or seeded["variants"]
    if created:
        # 只有真正新增内容才推进版本号，避免每次启动都制造一个空版本
        version = engine.bump_version(db)
        audit.record(
            db,
            "catalog.seed",
            actor=actor,
            actor_role="system",
            target_type="catalog",
            target_id="default",
            after={"policies": policies, **seeded, "engine_version": version},
        )
    else:
        version = max(0, engine.read_version(db))
    engine.reset_engine()
    return {
        "policies": policies,
        "terms": seeded["terms"],
        "variants": seeded["variants"],
        "engine_version": version,
    }


def reload_engine(db: Session, *, actor: str = "system") -> dict:
    version = engine.bump_version(db)
    engine.reset_engine()
    audit.record(
        db,
        "engine.reload",
        actor=actor,
        actor_role="system",
        target_type="engine",
        target_id=str(version),
        after={"version": version},
    )
    return {"engine_version": version}

# ===== 知识库规则集接入（2026-11-05）=====
# 发帖链路 = 词库(cg_term) + vault 政策卡编译产物(ruleset)
# 只把 bucket 转成"打码/送审"，绝不自动删除；block 档也只送审（人工确认后才处置）。
_POLICY_RULESET = {"hash": None, "ruleset": None, "checked_at": 0.0}


def _policy_enabled() -> bool:
    return os.environ.get("MODERATION_POLICY_FIRST", "1").strip().lower() not in (
        "0", "false", "off"
    )


def _block_as_mask() -> bool:
    """2026-11-07 用户决策：命中即打码可发布，blocked 级词条也降级为 mask。

    默认开启（MODERATION_BLOCK_AS_MASK=1）；设 0 可恢复“违规内容直接拦截”。
    链接黑名单/短链的 block 不受此开关影响（属安全拦截，不是言论分级）。
    """
    return os.environ.get("MODERATION_BLOCK_AS_MASK", "1").strip().lower() not in (
        "0", "false", "off"
    )


# ===== 链接四层（2026-11-06）=====
# L1 白名单放行 / L2 短链拦截 / L3 黑名单拦截 / L4 普通外链打码送审
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"'，。；：！？、（）【】\[\]]+")
_BARE_DOMAIN_RE = re.compile(
    r"(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|cn|net|org|top|xyz|cc|tv|info|biz|io|me|vip|club|site|online|link|shop|app|dev)"
    r"\b(?:/[^\s<>\"'，。；：！？、（）【】\[\]]*)?"
)
_SHORT_HOSTS = frozenset({
    "t.cn", "bit.ly", "dwz.cn", "url.cn", "tinyurl.com", "b23.tv", "suo.im", "s.id",
    "is.gd", "v.gd", "ow.ly", "cutt.ly", "rebrand.ly", "tt.vg", "126.am",
})
_BLACK_HOSTS = frozenset({
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "hentai.com",
    "91porn.com", "sehuatang.com", "eyny.com", "caoliu.com", "javbus.com",
    "avbebe.com", "mumuys.com",
})
_WHITELIST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})
_WHITELIST_SUFFIXES = (".gov.cn", ".edu.cn")
_URL_TRAIL = ".,;:!?)]}。，；：！？、）》】"


def _host_of(url: str) -> str:
    host = str(url or "").strip().lower()
    host = re.sub(r"^[a-z]+://", "", host)
    host = host.split("/")[0].split("?")[0].split("#")[0].split("@")[-1]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _match_host(host: str, table) -> bool:
    return any(host == item or host.endswith("." + item) for item in table)


def _link_signal(text: str) -> dict:
    """链接四层。返回 dict(decision, urls, words, reason)；无链接时 decision=None。"""
    empty = {"decision": None, "urls": [], "words": [], "reason": ""}
    raw = text or ""
    found = _URL_RE.findall(raw) or _BARE_DOMAIN_RE.findall(raw)
    if not found:
        return empty
    seen: set[str] = set()
    urls: list[str] = []
    for item in found:
        url = str(item).rstrip(_URL_TRAIL)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    hosts = [(url, _host_of(url)) for url in urls]
    for url, host in hosts:
        if _match_host(host, _SHORT_HOSTS):
            return {"decision": "block", "urls": [], "words": ["短链"],
                    "reason": f"命中短链域名：{host}"}
        if _match_host(host, _BLACK_HOSTS):
            return {"decision": "block", "urls": [], "words": ["外链"],
                    "reason": f"命中外链黑名单：{host}"}
    external = [url for url, host in hosts
                if host not in _WHITELIST_HOSTS
                and not any(host.endswith(suffix) for suffix in _WHITELIST_SUFFIXES)]
    if not external:
        return empty
    return {"decision": "mask", "urls": external, "words": ["外链"],
            "reason": "普通外部链接，打码送审"}


def _mask_all_hits(raw: str, result: dict) -> str:
    """把词库命中的**全部区间**（含 reviewed 级、含同一词条的多次出现）写回原文。"""
    index = result.get("index") or []
    if not index:
        return raw
    spans = list(result.get("redact_spans") or [])
    if not spans:
        for hit in result.get("hits") or []:
            try:
                spans.append((int(hit.get("start")), int(hit.get("end"))))
            except (TypeError, ValueError):
                continue
    if not spans:
        return raw
    return normalizer.mask_original(raw, spans, index)


def _apply_terms(text: str, terms) -> str:
    out = text or ""
    for term in sorted({str(t) for t in (terms or []) if t}, key=len, reverse=True):
        if len(term) >= 2 and term in out:
            out = out.replace(term, "*" * len(term))
    return out


def _apply_urls(text: str, urls) -> str:
    out = text or ""
    for url in urls or []:
        if url and url in out:
            out = out.replace(url, "http://****")
    return out


def _merge_ids(left, right) -> list:
    merged: list = []
    for item in list(left or []) + list(right or []):
        if item not in merged:
            merged.append(item)
    return merged


def _merge_words(left, right) -> list:
    return _merge_ids(left, right)


def _get_ruleset():
    """懒加载 vault ruleset；vault 不可用时返回 None（降级为纯词库）。"""
    import time as _time

    from ...core.config import settings

    vault = str(getattr(settings, "MODERATION_VAULT_DIR", "") or "")
    if not vault:
        return None
    now = _time.time()
    if _POLICY_RULESET["ruleset"] is not None and now - _POLICY_RULESET["checked_at"] < 300:
        return _POLICY_RULESET["ruleset"]
    try:
        from .. import policy_compiler as pc

        lib = pc.load_library(vault)
        rs = pc.compile_ruleset(lib, vault_dir=vault)
        _POLICY_RULESET.update({"hash": rs.get("hash"), "ruleset": rs, "checked_at": now})
        return rs
    except Exception:  # noqa: BLE001
        _POLICY_RULESET["checked_at"] = now
        return None


def _policy_signal(text: str, scene: str):
    """返回 (bucket, hit_terms, policy_ids)；无则 (None, [], [])。

    只取触发结论的那条规则实际命中的词条，不再遍历全词表：
    遍历全词表会把"就是"这类泛词、甚至整句测试文本打掉（打码位置错乱的根因）。
    """
    rs = _get_ruleset()
    if not rs:
        return None, [], []
    from .. import policy_compiler as pc

    scope = "forum.post" if scene.startswith("forum_post") else "forum.comment"
    try:
        sig = pc.score_text(text or "", rs, scope=scope, enforce_block=False)
    except Exception:  # noqa: BLE001
        return None, [], []
    bucket = sig.get("bucket")
    if bucket not in ("hold", "mask", "block"):
        return None, [], []
    hits = sig.get("hits") or []
    terms: list[str] = []
    top_id = hits[0].get("id") if hits else None
    top_rule = next(
        (rule for rule in (rs.get("rules") or []) if rule.get("id") == top_id), None
    )
    if top_rule:
        for name, lexicon_terms in (top_rule.get("lexicon_terms") or {}).items():
            for term in lexicon_terms:
                value = str(term or "").strip()
                if len(value) >= 2 and value in (text or "") and value not in terms:
                    terms.append(value)
        for item in (top_rule.get("match") or {}).get("any") or []:
            if not isinstance(item, dict):
                continue
            operator, value = item.get("operator"), item.get("value")
            if operator in ("keyword_all", "keyword_any") and isinstance(value, list):
                for word in value:
                    word = str(word or "").strip()
                    if len(word) >= 2 and word in (text or "") and word not in terms:
                        terms.append(word)
            elif operator == "regex":
                try:
                    matched = re.search(str(value), text or "")
                except re.error:
                    matched = None
                if matched and matched.group(0) and matched.group(0) not in terms:
                    terms.append(matched.group(0))
    terms.sort(key=len, reverse=True)
    ids = [h.get("id") for h in hits]
    return bucket, terms, ids

