"""跨层对账：发现"词条/判定/图谱/审计/投影"之间的不一致。

不自动修复：每个问题生成 consistency 提案，由人工确认处理策略，
避免"某一次自动修复把误判固化"。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models.content_guard import CgEdge, CgJudgment, CgTask, CgTerm, CgVariant
from . import audit, obsidian, proposals


def run(
    db: Session,
    *,
    create_proposals: bool = True,
    vault=None,
) -> dict:
    issues: list[dict] = []

    def add(code: str, key: str, detail: str, severity: str = "warn") -> None:
        issues.append({"code": code, "key": key, "detail": detail, "severity": severity})

    active_terms = db.query(CgTerm).filter(CgTerm.status == "active").all()
    term_ids = {t.term_id for t in active_terms}
    for term in active_terms:
        if not term.policy_clause_id:
            add("term_without_policy", str(term.term_id), f"词条「{term.term}」未绑定政策条款")
        if not term.normalized:
            add("term_empty_normalized", str(term.term_id), f"词条「{term.term}」归一化键为空", "error")

    for variant in db.query(CgVariant).filter(CgVariant.status == "active").all():
        if variant.term_id not in term_ids:
            add("orphan_variant", str(variant.variant_id), f"变体「{variant.variant}」指向不存在/停用词条")

    for task in db.query(CgTask).filter(CgTask.state == "pending").all():
        exists = (
            db.query(CgJudgment)
            .filter(CgJudgment.judgment_id == task.judgment_id)
            .first()
        )
        if not exists:
            add("orphan_task", str(task.task_id), f"任务 {task.task_id} 的判定已不存在")

    for judgment in (
        db.query(CgJudgment).order_by(CgJudgment.judgment_id.desc()).limit(500).all()
    ):
        for hit in judgment.hits or []:
            term_id = hit.get("term_id")
            if term_id and term_id not in term_ids:
                add(
                    "judgment_missing_term",
                    f"{judgment.judgment_id}:{term_id}",
                    f"判定 {judgment.judgment_id} 引用的词条 {term_id} 已停用/删除",
                )

    for edge in db.query(CgEdge).order_by(CgEdge.edge_id.desc()).limit(500).all():
        if edge.src_type == "term" and str(edge.src_id).isdigit():
            if int(edge.src_id) not in term_ids:
                add("dangling_edge", str(edge.edge_id), f"边 {edge.edge_id} 的起点词条不存在")

    chain = audit.verify_chain(db)
    if not chain["ok"]:
        add("audit_chain_broken", str(chain.get("broken_at")), chain.get("detail", ""), "error")

    try:
        vault_report = obsidian.check_vault(db, vault)
    except Exception as exc:  # noqa: BLE001 —— 投影不可用不影响数据库对账
        vault_report = {"configured": False, "issues": [str(exc)]}
    for item in vault_report.get("issues", [])[:20]:
        add("vault_projection", item, item)

    created = []
    if create_proposals:
        for issue in issues:
            proposal = proposals.create_proposal(
                db,
                kind="consistency",
                title=f"一致性异常：{issue['code']}",
                payload=issue,
                evidence=[{"source": "reconcile"}],
                proposer="system",
                dedupe_key=f"reconcile:{issue['code']}:{issue['key']}",
            )
            if proposal and proposal.status == "pending":
                created.append(proposal.proposal_id)

    return {
        "ok": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
        "proposals": sorted(set(created)),
        "vault": vault_report,
    }
