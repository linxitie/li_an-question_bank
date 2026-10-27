"""图投影对账（F5）。

期望值由 SoT 重新生成；实际值来自 GraphStore。对账只读，不修复。
抽样用 SoT 递归 CTE 与 GraphStore 遍历比较祖先集合，验证两种查询口径一致。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation import config as cfg
from app.foundation.graph_builder import GraphBuildPlan, build_graph
from app.foundation.stores.graph import (
    LABELS,
    RELS,
    GraphStore,
    GraphStoreError,
    build_graph_store,
)

SCOPE = "graph"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GraphReconcileResult:
    run_id: str
    mode: str = "full"
    checked: int = 0
    drifted: int = 0
    missing: int = 0
    orphan: int = 0
    mismatched: int = 0
    sampled: int = 0
    sample_mismatch: int = 0
    started_at: str = field(default_factory=_now)
    finished_at: str = ""
    status: str = "ok"
    report_path: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scope": SCOPE,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "checked": self.checked,
            "drifted": self.drifted,
            "repaired": 0,
            "report_path": self.report_path,
            "status": self.status,
        }

    def as_json(self) -> dict[str, Any]:
        payload = self.as_row()
        payload.update({
            "missing": self.missing,
            "orphan": self.orphan,
            "mismatched": self.mismatched,
            "sampled": self.sampled,
            "sample_mismatch": self.sample_mismatch,
            "details": self.details,
        })
        return payload


def _write_report(run: GraphReconcileResult) -> str:
    path = cfg.BACKEND_DIR / "data" / "reports" / "reconcile" / f"graph_{run.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.as_json(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(path)


def _sot_ancestors(session: Session, point_id: int, max_depth: int) -> set[int]:
    rows = session.execute(
        text(
            """WITH RECURSIVE ancestors(point_id, parent_id, depth) AS (
                   SELECT point_id, parent_id, 1 FROM knowledge_point
                   WHERE point_id = :point_id
                   UNION ALL
                   SELECT kp.point_id, kp.parent_id, a.depth + 1
                   FROM knowledge_point kp
                   JOIN ancestors a ON kp.point_id = a.parent_id
                   WHERE a.parent_id <> 0 AND a.depth < :max_depth
               )
               SELECT point_id FROM ancestors WHERE point_id <> :point_id"""
        ),
        {"point_id": point_id, "max_depth": max_depth},
    ).all()
    return {int(row[0]) for row in rows}


def _sample_points(plan: GraphBuildPlan, sample: int) -> list[int]:
    ids = sorted(
        int(node.key) for node in plan.nodes if node.label == "KnowledgePoint"
    )
    if sample <= 0 or len(ids) <= sample:
        return ids
    step = len(ids) / sample
    return [ids[min(len(ids) - 1, int(index * step))] for index in range(sample)]


def _node_map(plan: GraphBuildPlan) -> dict[tuple[str, str], dict[str, Any]]:
    return {(node.label, node.key): node.props for node in plan.nodes}


def _edge_map(plan: GraphBuildPlan) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    return {
        (edge.rel, edge.src_label, edge.src_key, edge.dst_label, edge.dst_key): edge.props
        for edge in plan.edges
    }


def inspect(
    session: Session,
    store: GraphStore | None = None,
    *,
    mode: str = "full",
    sample: int = 100,
    limit: int | None = None,
) -> GraphReconcileResult:
    """对账；mode=sample 只比计数和抽样祖先，不做全量 key 差集。"""
    if mode not in ("full", "sample"):
        raise ValueError(f"mode 只支持 full/sample: {mode!r}")
    if store is None:
        store = build_graph_store()
    plan = build_graph(session, limit=limit)
    run = GraphReconcileResult(run_id=uuid.uuid4().hex[:16], mode=mode)
    expected_nodes = _node_map(plan)
    expected_edges = _edge_map(plan)
    run.checked = len(expected_nodes) + len(expected_edges)

    actual_counts: dict[str, Any] = {}
    try:
        actual_counts = store.counts()
        if mode == "full":
            _compare_full(store, run, expected_nodes, expected_edges)
        _compare_sample(session, store, run, plan, sample)
    except GraphStoreError as exc:
        run.status = "warn"
        run.details.append({
            "issue": "graph_store_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        })
    except Exception as exc:  # noqa: BLE001 — 对账不能因单点异常崩溃
        run.status = "warn"
        run.details.append({
            "issue": "reconcile_error",
            "error": f"{type(exc).__name__}: {exc}",
        })

    run.finished_at = _now()
    if run.drifted:
        run.status = "drift"
    run.details.insert(0, {
        "expected_nodes": plan.node_counts(),
        "expected_edges": plan.edge_counts(),
        "actual": actual_counts,
    })
    run.report_path = _write_report(run)
    return run


def _compare_full(
    store: GraphStore,
    run: GraphReconcileResult,
    expected_nodes: dict[tuple[str, str], dict[str, Any]],
    expected_edges: dict[tuple[str, str, str, str, str], dict[str, Any]],
) -> None:
    actual_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for label in LABELS:
        for node in store.iter_nodes(label):
            actual_nodes[(node.label, node.key)] = node.props
    actual_edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for rel in RELS:
        for edge in store.iter_edges(rel):
            actual_edges[
                (edge.rel, edge.src_label, edge.src_key, edge.dst_label, edge.dst_key)
            ] = edge.props

    for key, props in expected_nodes.items():
        if key not in actual_nodes:
            run.missing += 1
            run.drifted += 1
            _detail(run, "missing_node", key)
        elif actual_nodes[key] != props:
            run.mismatched += 1
            run.drifted += 1
            _detail(run, "mismatched_node", key)
    for key in actual_nodes:
        if key not in expected_nodes:
            run.orphan += 1
            run.drifted += 1
            _detail(run, "orphan_node", key)
    for key, props in expected_edges.items():
        if key not in actual_edges:
            run.missing += 1
            run.drifted += 1
            _detail(run, "missing_edge", key)
        elif actual_edges[key] != props:
            run.mismatched += 1
            run.drifted += 1
            _detail(run, "mismatched_edge", key)
    for key in actual_edges:
        if key not in expected_edges:
            run.orphan += 1
            run.drifted += 1
            _detail(run, "orphan_edge", key)


def _compare_sample(
    session: Session,
    store: GraphStore,
    run: GraphReconcileResult,
    plan: GraphBuildPlan,
    sample: int,
) -> None:
    max_depth = max(1, int(cfg.GRAPH_QUERY_MAX_DEPTH))
    for point_id in _sample_points(plan, sample):
        run.sampled += 1
        expected = _sot_ancestors(session, point_id, max_depth)
        actual = {
            int(node["key"])
            for node in store.neighbors(
                "KnowledgePoint", str(point_id), "PREREQUISITE_OF",
                depth=max_depth, direction="in",
            )
            if node.get("label") == "KnowledgePoint"
        }
        if expected != actual:
            run.sample_mismatch += 1
            run.drifted += 1
            _detail(run, "sample_ancestors_mismatch", point_id, {
                "expected": sorted(expected), "actual": sorted(actual),
            })


def _detail(
    run: GraphReconcileResult, issue: str, key: Any, extra: dict[str, Any] | None = None
) -> None:
    if len(run.details) >= 200:
        return
    item = {"issue": issue, "key": key if isinstance(key, (str, int)) else list(key)}
    if extra:
        item.update(extra)
    run.details.append(item)


def record(session: Session, run: GraphReconcileResult) -> None:
    session.execute(
        text(
            """INSERT INTO foundation_reconcile_run
                   (run_id, scope, mode, started_at, finished_at, checked, drifted,
                    repaired, report_path, status)
               VALUES (:run_id, :scope, :mode, :started_at, :finished_at, :checked,
                       :drifted, :repaired, :report_path, :status)"""
        ),
        run.as_row(),
    )
    session.commit()


def latest_run(session: Session) -> dict[str, Any] | None:
    try:
        row = session.execute(
            text(
                """SELECT run_id, started_at, finished_at, checked, drifted,
                          status, report_path
                   FROM foundation_reconcile_run
                   WHERE scope='graph' ORDER BY finished_at DESC LIMIT 1"""
            )
        ).first()
    except Exception:
        return None
    return None if row is None else dict(row._mapping)


def freshness_days(latest: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    if not latest:
        return None
    raw = latest.get("finished_at")
    if not raw:
        return None
    try:
        finished = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if finished.tzinfo is None:
        finished = finished.astimezone()
    moment = now or datetime.now(timezone.utc)
    return max(0.0, (moment - finished).total_seconds() / 86400)
