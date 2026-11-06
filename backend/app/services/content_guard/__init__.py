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


def guard_text(
    db: Session,
    text: str,
    *,
    scene: str = "forum_post",
    source_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """审核闸门。返回字段与旧 sensitive_filter.detect 兼容，并新增 decision/evidence。"""
    enabled = os.environ.get("CONTENT_GUARD_ENABLED", "true").strip().lower()
    if enabled in ("false", "0", "off"):
        return _legacy_result(text)
    ready = _tables_ready(db)
    # 政策优先（2026-11-05）：vault 规则集若给出结论则优先；给出 allow 时放行自嘲/对题吐槽
    policy_bucket, policy_masked, policy_ids = (None, None, [])
    if os.environ.get("MODERATION_POLICY_FIRST", "1").strip().lower() not in ("0", "false", "off"):
        policy_bucket, policy_masked, policy_ids = _policy_signal(text or "", scene)
        if policy_bucket in ("hold", "mask", "block"):
            decision = "review" if policy_bucket == "block" else "mask"
            return {
                **_legacy_result(text),
                "decision": decision,
                "level": "reviewed" if policy_bucket == "block" else "masked",
                "hit": True,
                "masked_text": policy_masked if decision == "mask" else None,
                "words": [],
                "policy_ids": policy_ids,
                "source": "policy_ruleset",
            }

    result = judgments.guard_text(
        db,
        text,
        scene=scene,
        source_id=source_id,
        user_id=user_id,
        persist=persist and ready,
    )

    # 新闻/科普/求助语境：reviewed 档降为放行（不误删、也不占用人工）
    if result.get("decision") == "review" and NEWS_EDU.search(text or ""):
        result.update({"decision": "pass", "level": None, "source": "context_news_edu"})
        return result

    if (
        policy_bucket is None
        and result.get("decision") == "mask"
        and _SELF_REF.search(text or "")
        and not _OTHER_REF.search(text or "")
        and os.environ.get("MODERATION_POLICY_FIRST", "1").strip().lower() not in ("0", "false", "off")
    ):
        result.update({"decision": "pass", "level": None, "masked_text": None,
                       "hit": False, "source": "policy_first_self_ref"})
        return result

    # 词库明确放行时，再看知识库规则集（政策卡逻辑：对象约束/自嘲降权等）
    if result.get("decision") == "pass":
        bucket, masked_text, policy_ids = _policy_signal(text or "", scene)
        if bucket:
            decision = "review" if bucket == "block" else "mask"
            result.update(
                {
                    "decision": decision,
                    "level": "reviewed" if bucket == "block" else "masked",
                    "hit": bool(masked_text and masked_text != text),
                    "masked_text": masked_text,
                    "policy_ids": policy_ids,
                    "source": "policy_ruleset",
                }
            )
            if decision == "mask":
                result["words"] = [w for w in (result.get("words") or [])]
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
_SELF_REF = __import__("re").compile(r"(我|自己|本人|俺)")
NEWS_EDU = __import__("re").compile(
    r"(警方通报|据.{0,6}报道|官方通报|新闻|通告|如何防范|防骗|反诈|警惕|举报|求助|法律|司法解释)"
)
_OTHER_REF = __import__("re").compile(r"(@|你|您|他|她|楼主|同学|老师|这位|那人|这货|家伙)")


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
    """返回 (bucket, masked_text, policy_ids)；无则 (None, None, [])。"""
    rs = _get_ruleset()
    if not rs:
        return None, None, []
    from .. import policy_compiler as pc

    scope = "forum.post" if scene.startswith("forum_post") else "forum.comment"
    try:
        sig = pc.score_text(text, rs, scope=scope, enforce_block=False)
    except Exception:  # noqa: BLE001
        return None, None, []
    bucket = sig.get("bucket")
    if bucket not in ("hold", "mask", "block"):
        return None, None, []
    # 打码：把命中的词表词条替换为 *
    masked = text
    for name, terms in (rs.get("lexicons") or {}).items():
        for term in terms:
            if term and term in masked:
                masked = masked.replace(term, "*" * len(term))
    ids = [h.get("id") for h in (sig.get("hits") or [])]
    return bucket, masked, ids

