# -*- coding: utf-8 -*-
"""管理列表搜索（keyword）集成测试。

覆盖真接口全链路：管理员鉴权 → 建 2 张带唯一标记的卡 → 用 keyword 搜索命中 → 清理。

⚠️ **2026-11-08 修正（数据污染事故）**：本文件原来自己 `TestClient(app)` 且**没有**
套用 `conftest.py` 的 `get_db` 覆盖，于是测试直接读写**真实库** `data/question_bank.db`。
实测留下 4 条 `搜索专用-判断推理-ZZxxxx` / `搜索专用-职业素养-ZZxxxx`（status=-1，进了回收站）。
现在统一改用 conftest 的 `client` / `admin_headers` 夹具（内存库），**不再碰真实库**。
"""
import uuid

import pytest


def _mk_card(client, headers, title, tag):
    resp = client.post("/api/materials/admin", json={
        "subject": "xingce",
        "type": "card",
        "title": title,
        "card_front": f"正面-{tag}",
        "card_back": f"背面-{tag}",
        "category": "知觉速度与准确性",
        "publish": False,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture()
def tagged_cards(client, admin_headers):
    """建 2 张标题带唯一标记的卡（内存库），测试结束软删。"""
    tag = "ZZ" + uuid.uuid4().hex[:8]
    ids = [
        _mk_card(client, admin_headers, f"搜索专用-判断推理-{tag}", tag),
        _mk_card(client, admin_headers, f"搜索专用-职业素养-{tag}", tag),
    ]
    yield tag, ids
    for mid in ids:
        client.delete(f"/api/materials/admin/{mid}", headers=admin_headers)


class TestAdminListSearch:
    def test_keyword_hits_only_matching(self, client, admin_headers, tagged_cards):
        tag, ids = tagged_cards
        r = client.get("/api/materials/admin/list",
                       params={"keyword": tag, "page_size": 100},
                       headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        got = [i["id"] for i in data["items"]]
        assert sorted(got) == sorted(ids), f"应只命中新建的 2 张卡，实际 {got}"
        assert data["total"] == 2

    def test_keyword_by_category(self, client, admin_headers, tagged_cards):
        """分类也应参与匹配（实现为 title OR category LIKE）"""
        tag, _ = tagged_cards
        r = client.get("/api/materials/admin/list",
                       params={"keyword": "知觉速度与准确性", "page_size": 100},
                       headers=admin_headers)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert any(tag in (i.get("title") or "") for i in items), "分类匹配结果里应含刚建的卡"

    def test_keyword_no_match_returns_empty(self, client, admin_headers):
        r = client.get("/api/materials/admin/list",
                       params={"keyword": "ZZ绝不可能命中" + uuid.uuid4().hex},
                       headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_empty_keyword_returns_more_than_zero(self, client, admin_headers, tagged_cards):
        r = client.get("/api/materials/admin/list", params={"keyword": ""},
                       headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["total"] > 0, "空关键词不应过滤掉全部结果"

    def test_student_forbidden(self, client, auth_headers):
        """权限：非管理员访问管理列表应 403（不再用真实账号登录，避免碰真库）"""
        r = client.get("/api/materials/admin/list", params={"keyword": "x"},
                       headers=auth_headers)
        assert r.status_code == 403, r.text
