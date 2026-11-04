"""F5 健康快照：graph 段开关、可用性与最近对账。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.foundation import config as cfg
from app.foundation import health
from app.foundation.stores.graph import GraphHealth


class _FakeStore:
    def __init__(self, ok=True):
        self._ok = ok

    def health(self):
        return GraphHealth(
            backend="local", ok=self._ok, degraded=not self._ok,
            detail="fake",
        )


def test_graph_disabled(db_session, monkeypatch):
    monkeypatch.setattr(cfg, "GRAPH_STORE_ENABLED", False)
    snap = health.snapshot(db_session.bind)
    assert snap["graph"] == {"enabled": False}


def test_graph_ok_and_reconcile(db_session, monkeypatch):
    monkeypatch.setattr(cfg, "GRAPH_STORE_ENABLED", True)
    monkeypatch.setattr(cfg, "GRAPH_BACKEND", "local")
    import app.foundation.stores.graph as graph_store

    monkeypatch.setattr(graph_store, "build_graph_store", lambda: _FakeStore())
    db_session.execute(
        text(
            """INSERT INTO foundation_reconcile_run
                   (run_id, scope, mode, started_at, finished_at, checked, drifted,
                    repaired, report_path, status)
               VALUES ('r1', 'graph', 'full', :t, :t, 10, 0, 0, '', 'ok')"""
        ),
        {"t": datetime.now(timezone.utc).isoformat()},
    )
    db_session.commit()

    section = health.snapshot(db_session.bind)["graph"]
    assert section["enabled"] is True
    assert section["ok"] is True
    assert section["degraded"] is False
    assert section["last_reconcile_at"]
    assert section["drift"] is False


def test_graph_degraded_never_raises(db_session, monkeypatch):
    monkeypatch.setattr(cfg, "GRAPH_STORE_ENABLED", True)
    monkeypatch.setattr(cfg, "GRAPH_BACKEND", "local")
    import app.foundation.stores.graph as graph_store

    monkeypatch.setattr(graph_store, "build_graph_store", lambda: _FakeStore(False))
    section = health.snapshot(db_session.bind)["graph"]
    assert section["ok"] is False
    assert section["degraded"] is True
