"""Obsidian 人机协同界面：知识投影导出 + 审阅回写。

Obsidian 不是生产库：这里只导出可重建的 Markdown 投影，回写走
"待审队列 → 人工勾选 → 受控导入"，Agent 永远没有直接删除权。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...models.content_guard import (
    CgAuditEvent,
    CgCase,
    CgJudgment,
    CgPolicy,
    CgProposal,
    CgTask,
    CgTerm,
    CgVariant,
)
from . import graph, judgments, proposals, stats
from ..obsidian_sync import parse_note

MANIFEST_REL = "99-系统/导出清单.json"
_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n]+')


class VaultNotConfigured(RuntimeError):
    pass


def default_vault() -> Path:
    configured = os.environ.get("CONTENT_GUARD_VAULT", "").strip()
    if configured:
        return Path(configured).expanduser()
    root = Path(__file__).resolve().parents[4]
    return root / "docs" / "knowledge-vault" / "敏感词治理"


def _safe_path(vault: Path, *parts: str) -> Path:
    root = vault.resolve()
    target = root.joinpath(*parts).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes vault: {target}")
    return target


def _safe_name(name: str, limit: int = 60) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", name or "").strip().strip(".")
    return (cleaned or "untitled")[:limit]


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_manifest(vault: Path) -> dict[str, str]:
    path = _safe_path(vault, *MANIFEST_REL.split("/"))
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return {str(k): str(v) for k, v in loaded.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_if_changed(
    vault: Path,
    rel: str,
    content: str,
    manifest: dict[str, str],
    dry_run: bool,
    counters: dict[str, int],
) -> None:
    digest = _digest(content)
    target = _safe_path(vault, *rel.split("/"))
    if manifest.get(rel) == digest and target.exists():
        counters["skipped"] += 1
        return
    counters["written"] += 1
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    manifest[rel] = digest


def _write_once(
    vault: Path, rel: str, content: str, dry_run: bool, counters: dict[str, int]
) -> None:
    """待审文件只写一次：人工可能已在文件里写了备注，重导绝不覆盖。"""
    target = _safe_path(vault, *rel.split("/"))
    if target.exists():
        counters["skipped"] += 1
        return
    counters["written"] += 1
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)


def _term_note(db: Session, term: CgTerm) -> str:
    policy = (
        db.query(CgPolicy).filter(CgPolicy.clause_id == term.policy_clause_id).first()
        if term.policy_clause_id
        else None
    )
    variants = db.query(CgVariant).filter(CgVariant.term_id == term.term_id).all()
    variant_lines = [f"- {v.variant}（{v.kind}，{v.status}）" for v in variants] or ["- 暂无变体"]
    policy_line = f"[[{policy.code}|{policy.code} {policy.title}]]" if policy else "未绑定条款"
    return "\n".join(
        [
            "---",
            "type: sensitive_term",
            f"term_id: {term.term_id}",
            f"level: {term.level}",
            f"category: {term.category}",
            f"status: {term.status}",
            f"confidence: {term.confidence}",
            f"hit_count: {term.hit_count}",
            f"false_positive_count: {term.false_positive_count}",
            f"policy: {policy.code if policy else ''}",
            "---",
            "",
            f"# {term.term}",
            "",
            f"- 违规域：{term.category}",
            f"- 等级：{term.level}",
            f"- 状态：{term.status}",
            f"- 置信度：{term.confidence}",
            f"- 政策条款：{policy_line}",
            f"- 命中 / 阻断 / 打码 / 研判：{term.hit_count} / {term.block_count} / {term.mask_count} / {term.review_count}",
            f"- 误判次数：{term.false_positive_count}",
            "",
            "## 变体",
            *variant_lines,
            "",
            "## 备注",
            term.note or "",
            "",
        ]
    )


def _policy_note(policy: CgPolicy) -> str:
    return "\n".join(
        [
            "---",
            "type: sensitive_policy",
            f"clause_id: {policy.clause_id}",
            f"code: {policy.code}",
            f"category: {policy.category}",
            f"level: {policy.level}",
            f"priority: {policy.priority}",
            "---",
            "",
            f"# {policy.code} {policy.title}",
            "",
            f"- 违规域：{policy.category}",
            f"- 默认等级：{policy.level}",
            f"- 严重度：{policy.severity}",
            f"- 仲裁优先级：{policy.priority}",
            f"- 法律/制度依据：{policy.legal_basis or '未填写'}",
            "",
            "## 条款正文",
            policy.content or "",
            "",
        ]
    )


def _case_note(case: CgCase) -> str:
    return "\n".join(
        [
            "---",
            "type: sensitive_case",
            f"case_id: {case.case_id}",
            f"judgment_id: {case.judgment_id}",
            f"verdict: {case.verdict}",
            f"level: {case.level}",
            f"category: {case.category}",
            "---",
            "",
            f"# 案例 {case.case_id}：{case.title}",
            "",
            f"- 结论：{case.verdict}",
            f"- 关联判定：{case.judgment_id}",
            f"- 标签：{', '.join(case.tags or [])}",
            "",
            "## 叙述",
            case.narrative or "",
            "",
        ]
    )


def _proposal_note(proposal: CgProposal) -> str:
    return "\n".join(
        [
            "---",
            "type: content_guard_proposal",
            f"proposal_id: {proposal.proposal_id}",
            f"kind: {proposal.kind}",
            "status: pending",
            f"proposer: {proposal.proposer}",
            f"created_at: {proposal.created_at.isoformat(timespec='seconds') if proposal.created_at else ''}",
            "---",
            "",
            f"# 提案 {proposal.proposal_id}：{proposal.title}",
            "",
            "## 变更内容",
            "~~~json",
            json.dumps(proposal.payload, ensure_ascii=False, indent=2),
            "~~~",
            "",
            "## 证据",
            "~~~json",
            json.dumps(proposal.evidence, ensure_ascii=False, indent=2),
            "~~~",
            "",
            "## 审阅（勾选一项后执行受控导入）",
            "- [ ] 通过",
            "- [ ] 拒绝",
            "- 备注：",
            "",
        ]
    )


def _task_note(db: Session, task: CgTask, judgment: CgJudgment) -> str:
    return "\n".join(
        [
            "---",
            "type: content_guard_task",
            f"task_id: {task.task_id}",
            f"judgment_id: {judgment.judgment_id}",
            "status: pending",
            f"priority: {task.priority}",
            f"created_at: {task.created_at.isoformat(timespec='seconds') if task.created_at else ''}",
            "---",
            "",
            f"# 判定 {judgment.judgment_id} 待复核",
            "",
            f"- 场景：{judgment.scene} / 来源 {judgment.source_id}",
            f"- 等级：{judgment.level}，置信度：{judgment.confidence}",
            f"- 脱敏摘要：{judgment.content_snippet}",
            f"- 命中：{', '.join(h.get('term', '') for h in (judgment.hits or []))}",
            "",
            "## 证据链",
            "~~~json",
            json.dumps(judgment.evidence, ensure_ascii=False, indent=2),
            "~~~",
            "",
            "## 复核（勾选一项）",
            "- [ ] 确认违规",
            "- [ ] 误判",
            "- 备注：",
            "",
        ]
    )


def _overview_note(db: Session) -> str:
    data = stats.overview(db)
    trend = stats.trend(db, 14)
    rows = ["| 日期 | 总数 | 阻断 | 打码 | 研判 | 误判 |", "|---|---|---|---|---|---|"]
    for item in trend:
        rows.append(
            f"| {item['date']} | {item['total']} | {item['blocked']} | "
            f"{item['masked']} | {item['reviewed']} | {item['false_positive']} |"
        )
    top = stats.top_terms(db, 10)
    top_rows = ["| 词条 | 等级 | 命中 | 误判 |", "|---|---|---|---|"]
    for item in top:
        top_rows.append(
            f"| [[{item['term_id']}-{_safe_name(item['term'])}|{item['term']}]] | "
            f"{item['level']} | {item['hit_count']} | {item['false_positive_count']} |"
        )
    return "\n".join(
        [
            "# 敏感词治理工作台",
            "",
            f"> 生成时间：{datetime.now().isoformat(timespec='seconds')}｜引擎版本：{data['engine_version']}",
            "",
            "## 词库规模",
            f"- 词条 {data['terms']['total']}（{data['terms']['by_level']}）",
            f"- 变体 {data['variants']}｜案例 {data['cases']}｜审计事件 {data['audit_events']}",
            f"- 待复核判定 {data['pending_tasks']}｜待审提案 {data['pending_proposals']}",
            f"- 红队未拦截样本 {data['redteam_undetected']}",
            "",
            "## 近 14 天趋势",
            *rows,
            "",
            "## 高频词条",
            *top_rows,
            "",
        ]
    )


def export_all(db: Session, vault: Optional[Path] = None, dry_run: bool = False) -> dict:
    vault = Path(vault).expanduser() if vault else default_vault()
    if not vault.exists():
        vault.mkdir(parents=True, exist_ok=True)
    if not vault.is_dir():
        return {"ok": False, "error": "vault_not_dir", "vault": str(vault)}

    manifest = _load_manifest(vault)
    counters = {"written": 0, "skipped": 0}
    for folder in (
        "00-待审队列/提案",
        "00-待审队列/判定",
        "01-词条",
        "02-政策",
        "03-案例",
        "04-图谱",
        "05-审计日志",
        "07-归档",
        "09-工作台",
    ):
        _safe_path(vault, *folder.split("/")).mkdir(parents=True, exist_ok=True)

    readme = "\n".join(
        [
            "# 敏感词治理知识库",
            "",
            "本目录由 content_guard 自动投影生成，事实源是 SQLite 的 cg_* 表。",
            "",
            "## 目录",
            "- 00-待审队列/提案：AI/红队/主动学习提交的知识变更，人工勾选后执行导入",
            "- 00-待审队列/判定：中低置信度审核结果，人工确认或判误判",
            "- 01-词条 / 02-政策 / 03-案例：只读投影",
            "- 04-图谱：Mermaid 全景图",
            "- 05-审计日志：追加式哈希链审计的只读视图",
            "- 09-工作台：看板与趋势",
            "",
            "## 审阅流程",
            "1. 打开待审文件，勾选「通过」「拒绝」「确认违规」「误判」之一；",
            "2. 在管理端执行 POST /api/v1/admin/content-guard/obsidian/import；",
            "3. 已处理文件移动到 07-归档，变更写入数据库并追加审计事件。",
            "",
            "Agent 只有读取与提案权限，没有直接删除词条的路径。",
            "",
        ]
    )
    _write_if_changed(vault, "README.md", readme, manifest, dry_run, counters)
    queue_readme = "\n".join(
        [
            "# 待审队列使用说明",
            "",
            "1. 每个文件只勾选一项：通过 / 拒绝（提案），确认违规 / 误判（判定）；",
            "2. 可在「备注：」后补充理由，导入时写入 review_note；",
            "3. 执行 POST /api/v1/admin/content-guard/obsidian/import；",
            "4. 已处理文件移动到 07-归档/YYYY-MM，未勾选的文件保持不动。",
            "",
            "文件只写一次，重新导出不会覆盖你写下的备注。",
            "",
        ]
    )
    _write_if_changed(
        vault, "00-待审队列/README.md", queue_readme, manifest, dry_run, counters
    )
    _write_if_changed(vault, "09-工作台/概览.md", _overview_note(db), manifest, dry_run, counters)

    terms = db.query(CgTerm).order_by(CgTerm.term_id).all()
    for term in terms:
        rel = f"01-词条/{term.term_id}-{_safe_name(term.term)}.md"
        _write_if_changed(vault, rel, _term_note(db, term), manifest, dry_run, counters)

    for policy in db.query(CgPolicy).order_by(CgPolicy.clause_id).all():
        rel = f"02-政策/{_safe_name(policy.code)}.md"
        _write_if_changed(vault, rel, _policy_note(policy), manifest, dry_run, counters)

    for case in db.query(CgCase).order_by(CgCase.case_id).all():
        rel = f"03-案例/{case.case_id}-{_safe_name(case.title)}.md"
        _write_if_changed(vault, rel, _case_note(case), manifest, dry_run, counters)

    mermaid = graph.mermaid(db, limit=60)
    overview = graph.overview(db)
    graph_note = "\n".join(
        [
            "# 知识图谱全景",
            "",
            "~~~mermaid",
            mermaid,
            "~~~",
            "",
            "## 关系统计",
            "~~~json",
            json.dumps(overview, ensure_ascii=False, indent=2),
            "~~~",
            "",
        ]
    )
    _write_if_changed(vault, "04-图谱/全景.md", graph_note, manifest, dry_run, counters)

    events = db.query(CgAuditEvent).order_by(desc(CgAuditEvent.event_id)).limit(200).all()
    audit_lines = ["# 最近审计事件", "", "| 时间 | 动作 | 对象 | 哈希 |", "|---|---|---|---|"]
    for event in events:
        audit_lines.append(
            f"| {event.ts.isoformat(timespec='seconds') if event.ts else ''} | {event.action} | "
            f"{event.target_type}:{event.target_id} | {str(event.hash)[:12]}… |"
        )
    _write_if_changed(
        vault, "05-审计日志/最近事件.md", "\n".join(audit_lines), manifest, dry_run, counters
    )

    pending_proposals = (
        db.query(CgProposal)
        .filter(CgProposal.status == "pending")
        .order_by(CgProposal.proposal_id)
        .all()
    )
    for proposal in pending_proposals:
        _write_once(
            vault,
            f"00-待审队列/提案/proposal-{proposal.proposal_id}.md",
            _proposal_note(proposal),
            dry_run,
            counters,
        )

    pending_tasks = (
        db.query(CgTask).filter(CgTask.state == "pending").order_by(CgTask.task_id).all()
    )
    for task in pending_tasks:
        judgment = (
            db.query(CgJudgment).filter(CgJudgment.judgment_id == task.judgment_id).first()
        )
        if not judgment:
            continue
        _write_once(
            vault,
            f"00-待审队列/判定/task-{task.task_id}.md",
            _task_note(db, task, judgment),
            dry_run,
            counters,
        )

    if not dry_run:
        manifest_path = _safe_path(vault, *MANIFEST_REL.split("/"))
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return {
        "ok": True,
        "vault": str(vault.resolve()),
        "written": counters["written"],
        "skipped": counters["skipped"],
        "terms": len(terms),
        "pending_proposals": len(pending_proposals),
        "pending_tasks": len(pending_tasks),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }


_CHECKBOXES = {
    "通过": "approve",
    "拒绝": "reject",
    "确认违规": "confirm",
    "误判": "reject",
}


def _checked_actions(body: str) -> list[str]:
    actions = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        if len(stripped) < 6 or stripped[3].lower() != "x":
            continue
        for label, action in _CHECKBOXES.items():
            if label in stripped:
                actions.append(action)
                break
    return actions


def _move_to_archive(vault: Path, path: Path) -> None:
    target_dir = _safe_path(vault, "07-归档", datetime.now().strftime("%Y-%m"))
    target_dir.mkdir(parents=True, exist_ok=True)
    path.replace(target_dir / path.name)


def import_reviews(
    db: Session,
    vault: Optional[Path] = None,
    *,
    dry_run: bool = False,
    reviewer_id: Optional[int] = None,
) -> dict:
    vault = Path(vault).expanduser() if vault else default_vault()
    if not vault.exists() or not vault.is_dir():
        return {"ok": False, "error": "vault_not_found", "vault": str(vault)}
    report: dict[str, Any] = {
        "ok": True,
        "processed": 0,
        "skipped": 0,
        "errors": [],
        "vault": str(vault.resolve()),
    }
    for folder, handler in (
        ("00-待审队列/提案", "proposal"),
        ("00-待审队列/判定", "task"),
    ):
        base = _safe_path(vault, *folder.split("/"))
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.md")):
            fields, body = parse_note(path.read_text(encoding="utf-8"))
            actions = _checked_actions(body)
            if len(actions) != 1:
                report["skipped"] += 1
                continue
            action = actions[0]
            identifier = (
                fields.get("proposal_id") if handler == "proposal" else fields.get("judgment_id")
            )
            try:
                identifier = int(str(identifier))
            except (TypeError, ValueError):
                report["errors"].append(f"{path.name}: 缺少标识")
                continue
            if dry_run:
                report["processed"] += 1
                continue
            try:
                if handler == "proposal":
                    if action == "approve":
                        proposals.approve_proposal(
                            db, identifier, reviewer_id=reviewer_id, note="Obsidian 审阅通过"
                        )
                    else:
                        proposals.reject_proposal(
                            db, identifier, reviewer_id=reviewer_id, note="Obsidian 审阅拒绝"
                        )
                else:
                    judgments.override_judgment(
                        db,
                        identifier,
                        action="confirm" if action == "confirm" else "reject",
                        reviewer_id=reviewer_id,
                        reason="Obsidian 复核",
                    )
                db.commit()
            except Exception as exc:  # noqa: BLE001 —— 单文件失败不阻断其余
                db.rollback()
                report["errors"].append(f"{path.name}: {exc}")
                continue
            _move_to_archive(vault, path)
            report["processed"] += 1
    return report


def check_vault(db: Session, vault: Optional[Path] = None) -> dict:
    vault = Path(vault).expanduser() if vault else default_vault()
    if not vault.exists():
        # 未导出过不是异常：投影目录默认按需创建，缺目录不参与对账
        return {"configured": False, "vault": str(vault), "issues": []}
    manifest = _load_manifest(vault)
    issues = []
    for rel, digest in manifest.items():
        if rel.startswith("00-待审队列/"):
            continue
        target = _safe_path(vault, *rel.split("/"))
        if not target.is_file():
            issues.append(f"投影缺失: {rel}")
        elif _digest(target.read_text(encoding="utf-8")) != digest:
            issues.append(f"投影被手改: {rel}")
    return {
        "configured": True,
        "vault": str(vault.resolve()),
        "files": len(manifest),
        "issues": issues,
    }
