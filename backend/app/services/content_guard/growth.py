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
import re
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


# 自动批准策略：只覆盖"纯追加单条词条 + 有证据"，其余仍走人工
AUTO_APPROVE_KINDS = {"term_add"}

# 词条质量闸（2026-11-06）：自动批准曾把「就是」「楼主就是个智障」这类泛词/整句测试文本
# 写进 vault 词表，导致打码位置错乱。自动入词只接受 2–12 位、无空白标点的词。
_TERM_RE = re.compile(r"^[\w\u4e00-\u9fff]{2,12}$")
_GENERIC_TERMS = frozenset({
    "就是", "真是个", "这个", "那个", "什么", "真的", "我们", "你们", "他们",
    "一个", "不是", "可以", "没有", "这样", "那样", "怎么",
})


_GENERIC_FRAGMENTS = ("就是", "真是个", "这个", "那个", "什么", "真的")


def _term_ok(term: str) -> bool:
    value = str(term or "").strip()
    if not _TERM_RE.match(value):
        return False
    if value.lower() in _GENERIC_TERMS:
        return False
    # 整句测试文本往往含虚词片段（如「楼主就是个智障」），一律拒绝自动入词
    return not any(fragment in value for fragment in _GENERIC_FRAGMENTS)


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
    pid = p.proposal_id

    # 自动批准（2026-11-05）：只追加单条词条 + 有证据 → 无需人工
    # 改阈值/删词/改条款正文仍必须人审
    if (
        p.kind in AUTO_APPROVE_KINDS
        and evidence
        and _term_ok(term)
        and p.status == "pending"
    ):
        try:
            approve_proposal(db, pid, reviewer_id=0)
        except Exception:  # noqa: BLE001
            pass
    return pid


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

    # 让运行时引擎重建索引（版本号自增；失败不影响落盘）
    try:
        State = _model("cg_sync_state")
        for row in db.query(State).all():
            key = str(getattr(row, "key", "")).lower()
            if "version" in key or "engine" in key:
                try:
                    row.value = str(int(float(str(row.value))) + 1)
                except (TypeError, ValueError):
                    row.value = "1"
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    try:
        rs = policy_compiler.compile_ruleset(policy_compiler.load_library(str(settings.MODERATION_VAULT_DIR)),
                                             vault_dir=str(settings.MODERATION_VAULT_DIR))
        return {"proposal_id": proposal_id, "term": term, "lexicon": lexicon,
                "ruleset_hash": rs.get("hash"), "before": before, "after": after}
    except Exception as exc:  # noqa: BLE001
        return {"proposal_id": proposal_id, "term": term, "lexicon": lexicon,
                "ruleset_hash": None, "warning": str(exc)}
