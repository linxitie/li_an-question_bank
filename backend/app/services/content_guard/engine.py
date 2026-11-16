"""DFA 词库引擎：从数据库编译，支持热加载与多进程版本感知。

事实源是 cg_term / cg_variant 两张表；本模块只做内存索引。
数据库不可用或词库为空时回退到 services.sensitive_words 的内置词表，
保证论坛审核在迁移期不会出现"库空即全放行"。
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...models.content_guard import CgPolicy, CgSyncState, CgTerm, CgVariant
from ..sensitive_words import SENSITIVE_WORDS
from . import normalizer

logger = logging.getLogger(__name__)

LEVEL_PRIORITY = {"blocked": 3, "masked": 2, "reviewed": 1}
ENGINE_STATE_KEY = "engine_version"

_CATEGORY_DEFAULT_POLICY = {
    "political": "PG-01",
    "violence": "PG-02",
    "porn": "PG-03",
    "gambling": "PG-04",
    "drug": "PG-05",
    "exam_fraud": "PG-06",
    "abuse": "PG-07",
    "ad": "PG-08",
    "social_ethics": "PG-09",
    "culture": "PG-10",
    "other": "PG-99",
}

LEGACY_LEVEL_CONFIDENCE = {"blocked": 0.95, "masked": 0.85, "reviewed": 0.6}
LEGACY_CATEGORY = {
    "blocked": "political",
    "masked": "abuse",
    "reviewed": "exam_fraud",
}


@dataclass
class _Entry:
    term_id: Optional[int]
    term: str
    level: str
    category: str
    confidence: float
    policy_ids: list[int] = field(default_factory=list)
    variant_id: Optional[int] = None
    variant_kind: Optional[str] = None


@dataclass
class GuardEngine:
    version: int
    source: str
    dfa: dict[str, Any]
    term_count: int
    variant_count: int
    category_policy: dict[str, list[int]]
    built_at: float = field(default_factory=time.time)

    def _search(self, text: str) -> list[tuple[str, int, int, _Entry]]:
        """返回 (命中串, 起点, 终点, 词条)；同一位置取最长匹配。"""
        found: list[tuple[str, int, int, _Entry]] = []
        if not text:
            return found
        n = len(text)
        for i in range(n):
            node = self.dfa
            j = i
            last: Optional[tuple[int, _Entry]] = None
            while j < n and text[j] in node:
                node = node[text[j]]
                j += 1
                entries = node.get("__end__")
                if entries:
                    last = (j, entries[0])
            if last is not None:
                end, entry = last
                found.append((text[i:end], i, end, entry))
        return found

    def detect(self, text: str) -> dict:
        raw = (text or "")[:20000]
        compacted, index = normalizer.compact(raw)
        if not compacted:
            return _empty_result(self, raw)

        matches = self._search(compacted)
        if not matches:
            return _empty_result(self, raw)

        hits: list[dict] = []
        spans: list[tuple[int, int]] = []
        redact_spans: list[tuple[int, int]] = []
        seen: set[tuple[Optional[int], str]] = set()
        max_level: Optional[str] = None
        policy_ids: list[int] = []
        words: list[str] = []

        for matched, start, end, entry in matches:
            # 同一词条的多次出现都要打码；统计/证据只保留一条。
            # reviewed 级只研判不改写原文，因此不进遮罩区间。
            redact_spans.append((start, end))
            if entry.level in ("blocked", "masked"):
                spans.append((start, end))
            key = (entry.term_id, entry.term)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "term_id": entry.term_id,
                    "term": entry.term,
                    "word": matched,
                    "level": entry.level,
                    "category": entry.category,
                    "confidence": entry.confidence,
                    "policy_ids": list(entry.policy_ids),
                    "variant_id": entry.variant_id,
                    "variant_kind": entry.variant_kind,
                    "start": start,
                    "end": end,
                }
            )
            if entry.term not in words:
                words.append(entry.term)
            if max_level is None or LEVEL_PRIORITY.get(entry.level, 0) > LEVEL_PRIORITY.get(
                max_level, 0
            ):
                max_level = entry.level
            for pid in entry.policy_ids:
                if pid not in policy_ids:
                    policy_ids.append(pid)

        # 命中词没有显式条款时，按类别回落到默认政策
        if not policy_ids:
            for hit in hits:
                for pid in self.category_policy.get(hit["category"], []):
                    if pid not in policy_ids:
                        policy_ids.append(pid)

        return {
            "has_sensitive": True,
            "level": max_level,
            "words": words,
            "hits": hits,
            "spans": spans,
            "redact_spans": redact_spans,
            "policy_ids": policy_ids,
            "masked_text": normalizer.mask_original(raw, spans, index),
            "snippet": normalizer.snippet(raw, redact_spans, index),
            "compact": compacted,
            "index": index,
            "engine_version": self.version,
            "engine_source": self.source,
        }


def _empty_result(engine: GuardEngine, raw: str) -> dict:
    return {
        "has_sensitive": False,
        "level": None,
        "words": [],
        "hits": [],
        "spans": [],
        "redact_spans": [],
        "policy_ids": [],
        "masked_text": raw,
        "snippet": " ".join(raw.split())[:200],
        "compact": "",
        "index": [],
        "engine_version": engine.version,
        "engine_source": engine.source,
    }


def _legacy_engine() -> GuardEngine:
    dfa: dict[str, Any] = {}
    count = 0
    for level, words in SENSITIVE_WORDS.items():
        for word in words:
            norm = normalizer.normalize(word)
            if not norm:
                continue
            node = dfa
            for ch in norm:
                node = node.setdefault(ch, {})
            node["__end__"] = [
                _Entry(
                    term_id=None,
                    term=word,
                    level=level,
                    category=LEGACY_CATEGORY.get(level, "other"),
                    confidence=LEGACY_LEVEL_CONFIDENCE.get(level, 0.6),
                )
            ]
            count += 1
    return GuardEngine(
        version=-1,
        source="legacy",
        dfa=dfa,
        term_count=count,
        variant_count=0,
        category_policy={},
    )


def _build_from_db(db: Session) -> Optional[GuardEngine]:
    terms = db.query(CgTerm).filter(CgTerm.status == "active").all()
    if not terms:
        return None

    policy_rows = db.query(CgPolicy).filter(CgPolicy.status == "active").all()
    policies_by_id = {p.clause_id: p for p in policy_rows}
    category_policy: dict[str, list[int]] = {}
    for policy in policy_rows:
        category_policy.setdefault(policy.category, []).append(policy.clause_id)
    # 类别内按优先级排序，仲裁时先拿到高优先级条款
    for ids in category_policy.values():
        ids.sort(key=lambda pid: -(policies_by_id[pid].priority or 0))

    term_by_id = {t.term_id: t for t in terms}
    dfa: dict[str, Any] = {}
    count = 0

    def add_entry(norm: str, entry: _Entry) -> None:
        nonlocal count
        if not norm:
            return
        node = dfa
        for ch in norm:
            node = node.setdefault(ch, {})
        bucket = node.setdefault("__end__", [])
        bucket.append(entry)
        count += 1

    for term in terms:
        pid = term.policy_clause_id
        pids = [pid] if pid else list(category_policy.get(term.category, []))[:1]
        add_entry(
            term.normalized or normalizer.normalize(term.term),
            _Entry(
                term_id=term.term_id,
                term=term.term,
                level=term.level,
                category=term.category,
                confidence=float(term.confidence or term.weight or 0.8),
                policy_ids=pids,
            ),
        )

    variants = db.query(CgVariant).filter(CgVariant.status == "active").all()
    variant_count = 0
    for variant in variants:
        parent = term_by_id.get(variant.term_id)
        if parent is None:
            continue
        pid = parent.policy_clause_id
        pids = [pid] if pid else list(category_policy.get(parent.category, []))[:1]
        add_entry(
            variant.normalized or normalizer.normalize(variant.variant),
            _Entry(
                term_id=parent.term_id,
                term=parent.term,
                level=parent.level,
                category=parent.category,
                confidence=float(parent.confidence or 0.8),
                policy_ids=pids,
                variant_id=variant.variant_id,
                variant_kind=variant.kind,
            ),
        )
        variant_count += 1

    return GuardEngine(
        version=0,
        source="db",
        dfa=dfa,
        term_count=count,
        variant_count=variant_count,
        category_policy=category_policy,
    )


_CACHE: dict[str, Any] = {"version": None, "engine": None}
_LOCK = threading.RLock()
_LEGACY: Optional[GuardEngine] = None


def _legacy() -> GuardEngine:
    global _LEGACY
    with _LOCK:
        if _LEGACY is None:
            _LEGACY = _legacy_engine()
        return _LEGACY


def read_version(db: Session) -> int:
    try:
        row = db.query(CgSyncState).filter(CgSyncState.key == ENGINE_STATE_KEY).first()
        if not row or not isinstance(row.value, dict):
            return 0
        return int(row.value.get("version", 0) or 0)
    except Exception:  # noqa: BLE001 —— 表未建/库不可用时回退
        return -1


def bump_version(db: Session) -> int:
    """词库变更后调用；只改状态行，由调用方 commit。"""
    try:
        row = db.query(CgSyncState).filter(CgSyncState.key == ENGINE_STATE_KEY).first()
        current = 0
        if row and isinstance(row.value, dict):
            current = int(row.value.get("version", 0) or 0)
        current += 1
        if row is None:
            row = CgSyncState(key=ENGINE_STATE_KEY, value={"version": current})
            db.add(row)
        else:
            row.value = {"version": current}
        return current
    except Exception as exc:  # noqa: BLE001
        logger.warning("敏感词引擎版本自增失败: %s", exc)
        return -1


def get_engine(db: Optional[Session] = None) -> GuardEngine:
    """按库内版本号取引擎；版本未变直接复用缓存。"""
    if db is None:
        return _legacy()
    version = read_version(db)
    if version < 0:
        return _legacy()
    with _LOCK:
        cached = _CACHE.get("engine")
        if cached is not None and _CACHE.get("version") == version:
            return cached
    built = _build_from_db(db)
    if built is None:
        return _legacy()
    built.version = version
    with _LOCK:
        _CACHE["version"] = version
        _CACHE["engine"] = built
    logger.info(
        "敏感词引擎已编译: version=%s terms=%s variants=%s",
        version,
        built.term_count,
        built.variant_count,
    )
    return built


def reset_engine() -> None:
    """测试或显式重载时使用。"""
    with _LOCK:
        _CACHE["version"] = None
        _CACHE["engine"] = None
