"""Obsidian 词表 → cg_term 自动同步（2026-11-09）。

在 Obsidian 里编辑 <vault>/AI舆情审核知识库/模型与规则/词表/*.yaml，
后台每 10 分钟检测文件变化并导入，命中即打码立即生效。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from ...models.content_guard import CgTerm
from .. import policy_compiler as pc

logger = logging.getLogger(__name__)

_LAST_SIG: Optional[tuple] = None

_CATEGORY_HINTS = {
    "insult": "abuse",
    "abuse": "abuse",
    "porn": "porn",
    "gambl": "gambling",
    "drug": "drug",
    "fraud": "ad",
    "ad_": "ad",
    "political": "political",
}


def _category(lexicon: str) -> str:
    low = lexicon.lower()
    for key, value in _CATEGORY_HINTS.items():
        if key in low:
            return value
    return "other"


def _signature(vault: str) -> tuple:
    root = pc.lexicon_dir(vault)
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            (p.name, p.stat().st_mtime)
            for p in root.glob("*")
            if p.suffix.lower() in (".yaml", ".yml", ".json", ".txt")
        )
    )


def sync_vault_lexicons(db: Session, vault: str) -> dict:
    """把 vault 词表 upsert 进 cg_term，并重载 DFA。"""
    from . import normalizer, reload_engine

    lexicons = pc.load_lexicons(vault)
    created = 0
    updated = 0
    for name, terms in lexicons.items():
        category = _category(name)
        for term in terms:
            word = str(term).strip()
            if not word:
                continue
            norm = normalizer.normalize(word)
            if not norm:
                continue
            row = db.query(CgTerm).filter(CgTerm.normalized == norm).first()
            if row is None:
                db.add(
                    CgTerm(
                        term=word,
                        normalized=norm,
                        level="masked",
                        category=category,
                        weight=0.8,
                        confidence=0.8,
                        status="active",
                        source=f"vault:{name}",
                        created_by=0,
                        note="Obsidian 词表同步",
                    )
                )
                created += 1
            elif row.status != "active":
                row.status = "active"
                updated += 1
    db.commit()
    version = reload_engine(db).get("engine_version")
    return {
        "lexicons": len(lexicons),
        "created": created,
        "updated": updated,
        "engine_version": version,
    }


def sync_if_changed(db: Session, vault: Optional[str] = None) -> dict:
    """文件签名变化时才真正导入；无变化直接返回。"""
    global _LAST_SIG
    from ...core.config import settings

    vault = vault or str(getattr(settings, "MODERATION_VAULT_DIR", "") or "")
    if not vault:
        return {"changed": False, "reason": "MODERATION_VAULT_DIR 未配置"}
    sig = _signature(vault)
    if sig == _LAST_SIG:
        return {"changed": False}
    _LAST_SIG = sig
    report = sync_vault_lexicons(db, vault)
    return {"changed": True, **report}
