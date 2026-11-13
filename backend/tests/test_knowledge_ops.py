"""知识运营接口与政策编译器测试（M0 影子期）。

为什么用静态 fixture 库而不是 tmp_path：
- 编译器要能独立验证，且测试不应依赖开发者本机 vault；
- 用 tests/fixtures/policy_vault 这类只读样例，任何环境（含受限沙箱）都能跑，
  样例文件同时充当「政策卡格式」的活文档。
"""
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.policy_compiler import (
    bucket_for,
    compile_ruleset,
    load_library,
    score_text,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD_VAULT = FIXTURES / "policy_vault"
BAD_VAULT = FIXTURES / "policy_vault_bad"


@pytest.fixture
def vault(monkeypatch):
    monkeypatch.setattr(settings, "MODERATION_VAULT_DIR", str(GOOD_VAULT))
    monkeypatch.setattr(settings, "MODERATION_VAULT_WRITE", False)
    monkeypatch.setattr(settings, "MODERATION_ENFORCE_BLOCK", False)
    return GOOD_VAULT


def _block_ruleset():
    """造一条必然命中 block 的规则，用于验证「未开强制阻断时降级为 mask」。"""
    return {
        "rules": [
            {
                "id": "P-99-001",
                "domain": "99-测试",
                "title": "测试必封",
                "severity": "critical",
                "action": "A3 隐藏",
                "version": 1,
                "scope": ["forum.comment"],
                "match": {"any": [{"regex": "必封"}], "all": []},
                "context_modifiers": [],
                "thresholds": {
                    "allow": "< 0.10",
                    "hold": "0.10 - 0.30",
                    "mask": "0.30 - 0.50",
                    "block": ">= 0.50",
                },
            }
        ]
    }


class TestCompiler:
    def test_loads_active_policy(self):
        library = load_library(str(GOOD_VAULT))
        assert library.error_count == 0
        assert [p.id for p in library.policies] == ["P-01-001"]
        assert library.policies[0].severity == "high"

    def test_unknown_operator_is_error(self):
        library = load_library(str(BAD_VAULT))
        codes = {i.code for i in library.issues}
        assert "match_operator_unknown" in codes
        assert library.policies == []

    def test_hash_is_stable(self):
        first = compile_ruleset(load_library(str(GOOD_VAULT)))["hash"]
        second = compile_ruleset(load_library(str(GOOD_VAULT)))["hash"]
        assert first == second
        assert len(first) == 64

    def test_score_hits_and_buckets(self):
        ruleset = compile_ruleset(load_library(str(GOOD_VAULT)))
        scored = score_text("绝对稳过，包你上岸", ruleset)
        assert scored["hits"][0]["id"] == "P-01-001"
        assert scored["bucket"] == "hold"
        assert scored["score"] == pytest.approx(0.68, abs=1e-6)

    def test_block_downgraded_without_enforce(self):
        ruleset = _block_ruleset()
        assert bucket_for(0.99, {"block": ">= 0.92", "mask": "0.80 - 0.92"}) == "block"
        assert score_text("必封", ruleset, enforce_block=True)["bucket"] == "block"
        assert score_text("必封", ruleset, enforce_block=False)["bucket"] == "mask"


class TestKnowledgeOpsApi:
    def test_summary(self, client, admin_headers, vault):
        resp = client.get("/api/admin/knowledge-ops/summary", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["compiled"] == 1
        assert data["error_count"] == 0
        assert len(data["hash"]) == 64
        assert data["flags"]["vault_write"] is False

    def test_policies_list_and_detail(self, client, admin_headers, vault):
        resp = client.get("/api/admin/knowledge-ops/policies", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        detail = client.get("/api/admin/knowledge-ops/policies/P-01-001", headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["policy_dsl"]["scope"] == "forum.comment"
        missing = client.get("/api/admin/knowledge-ops/policies/P-99-999", headers=admin_headers)
        assert missing.status_code == 404

    def test_preview(self, client, admin_headers, vault):
        resp = client.post(
            "/api/admin/knowledge-ops/preview",
            json={"text": "绝对稳过，包你上岸", "scope": "forum.comment"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["hits"][0]["id"] == "P-01-001"
        assert data["bucket"] == "hold"

    def test_compile_dry_run_writes_nothing(self, client, admin_headers, vault):
        resp = client.post(
            "/api/admin/knowledge-ops/compile", json={"dry_run": True}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["written_to"] is None
        assert not (GOOD_VAULT / "AI舆情审核知识库" / "产出").exists()

    def test_compile_publish_requires_flag(self, client, admin_headers, vault):
        resp = client.post(
            "/api/admin/knowledge-ops/compile", json={"dry_run": False}, headers=admin_headers
        )
        assert resp.status_code == 403

    def test_summary_503_when_vault_missing(self, client, admin_headers, monkeypatch):
        monkeypatch.setattr(settings, "MODERATION_VAULT_DIR", str(FIXTURES / "no_such_vault"))
        resp = client.get("/api/admin/knowledge-ops/summary", headers=admin_headers)
        assert resp.status_code == 503

    def test_requires_admin(self, client, auth_headers):
        resp = client.get("/api/admin/knowledge-ops/summary", headers=auth_headers)
        assert resp.status_code in (401, 403)
