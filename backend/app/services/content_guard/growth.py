"""自生长闭环（B）：judgment → case → proposal → 写 vault 词表 + cg_term → 重编译 → 审计。

设计约束（对齐知识库铁律）：
- 只追加，不删除既有知识；
- AI 只生成提案，写入需要人审（status=approved 才落盘）；
- 每次落盘写 cg_audit_event（before/after hash）；
- 词表写 vault（人读机读同源）+ cg_term（运行时立即生效）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from ...core.config import settings
from ...models import content_guard as cg
from .. import policy_compiler


def _model(name: str):
    return next(c for c in vars(cg).values() if getattr(c, "__tablename__", "") == name)


def _vault_sub() -> Path:
    return Path(str(settings.MODERATION_VAULT_DIR)) / policy_compiler.DEFAULT_SUBVAULT


def sediment_case(db: Session, judgment_id: int) -> Optional[int]:
    """研判 → 案例（幂等：同一 judgment 只沉淀一次）。"""
    Case, Judgment = _model("cg_case"), _model("cg_judgment")
    if db.query(Case).filter(Case.judgment_id == judgment_id).first():
        return None
    j = db.query(Judgment).filter(Judgment.judgment_id == judgment_id).first()
    if not j:
        return None
    case = Case(
        judgment_id=judgment_id,
        title=f"研判 #{judgment_id} 沉淀",
        category=(j.hits or [{}])[0].get("category") if isinstance(j.hits, list) and j.hits else "未分类",
        level=j.level or "reviewed",
        verdict="correct" if j.decision in ("block", "mask") else "false_positive",
        narrative=f"decision={j.decision} confidence={j.confidence} snippet={j.content_snippet}",
        tags="auto",
        source="auto",
        created_by="system",
    )
    db.add(case)
    db.commit()
    return case.case_id


def propose_term(db: Session, term: str, lexicon: str = "insult_zh_v1", evidence: dict | None = None) -> int:
    """生成"新增词条"提案（不直接写盘）。"""
    Proposal = _model("cg_proposal")
    dedupe = hashlib.sha256(f"term:{lexicon}:{term}".encode()).hexdigest()[:32]
    existing = db.query(Proposal).filter(Proposal.dedupe_key == dedupe).first()
    if existing:
        return existing.proposal_id
    p = Proposal(
        kind="term_add",
        title=f"新增词条：{term} → {lexicon}",
        payload=json.dumps({"term": term, "lexicon": lexicon}, ensure_ascii=False),
        evidence=json.dumps(evidence or {}, ensure_ascii=False),
        proposer="knowledge_ops_agent",
        status="pending",
        dedupe_key=dedupe,
    )
    db.add(p)
    db.commit()
    return p.proposal_id


def approve_proposal(db: Session, proposal_id: int, reviewer_id: int = 1) -> dict:
    """人审通过 → 写入 vault 词表 + cg_term + 审计 + 重编译（返回新 ruleset hash）。"""
    Proposal, Audit = _model("cg_proposal"), _model("cg_audit_event")
    p = db.query(Proposal).filter(Proposal.proposal_id == proposal_id).first()
    if not p:
        raise ValueError("提案不存在")
    payload = json.loads(p.payload or "{}")
    term, lexicon = payload.get("term"), payload.get("lexicon") or "insult_zh_v1"
    if not term:
        raise ValueError("提案缺少 term")

    sub = _vault_sub()
    lex_file = sub / "模型与规则" / "词表" / f"{lexicon}.yaml"
    lex_file.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if lex_file.exists():
        data = yaml.safe_load(lex_file.read_text(encoding="utf-8")) or {}
    terms = sorted(set(data.get("terms") or []) | {term})
    before = hashlib.sha256(json.dumps(data.get("terms") or [], ensure_ascii=False).encode()).hexdigest()[:16]
    lex_file.write_text(
        yaml.safe_dump({"name": lexicon, "terms": terms}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    after = hashlib.sha256(json.dumps(terms, ensure_ascii=False).encode()).hexdigest()[:16]

    # 运行时词库（立即生效）
    Term = _model("cg_term")
    if not db.query(Term).filter((Term.normalized == term) | (Term.term == term)).first():
        db.add(Term(term=term, normalized=term, level="masked", category="脏话粗口",
                    weight=1.0, confidence=0.8, status="active", source=f"proposal:{proposal_id}"))

    p.status = "approved"
    p.reviewer_id = reviewer_id
    p.review_note = f"human approved; vault {lexicon} {before}->{after}"
    db.add(Audit(hash=after, actor=f"user:{reviewer_id}", actor_role="knowledge_admin", action="proposal_apply",
                 target_type="proposal", target_id=str(proposal_id), before_hash=before, after_hash=after,
                 payload=json.dumps({"term": term, "lexicon": lexicon}, ensure_ascii=False)))
    db.commit()

    try:
        rs = policy_compiler.compile_ruleset(policy_compiler.load_library(str(settings.MODERATION_VAULT_DIR)),
                                             vault_dir=str(settings.MODERATION_VAULT_DIR))
        return {"proposal_id": proposal_id, "term": term, "lexicon": lexicon,
                "ruleset_hash": rs.get("hash"), "before": before, "after": after}
    except Exception as exc:  # noqa: BLE001
        return {"proposal_id": proposal_id, "term": term, "lexicon": lexicon,
                "ruleset_hash": None, "warning": str(exc)}
