"""管理员商品上下架 + 选项接口的接口级测试（2026-11-05）。

UI 侧已由 e2e 覆盖「在售/已下架分离展示」；这里保证上下架状态真的落库。
"""
from __future__ import annotations

from app.models.models import ShopProduct


def _product(db, name="上下架测试商品", status="on_sale"):
    p = ShopProduct(
        name=name,
        category="文具",
        product_type="physical",
        coin_price=500,
        stock=10,
        status=status,
        deliverable_type="manual",
        tier="small",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_put_status_toggles_shelf(client, db_session, admin_headers):
    p = _product(db_session)

    off = client.put(
        f"/api/admin/shop/products/{p.id}",
        json={"status": "off_shelf"},
        headers=admin_headers,
    )
    assert off.status_code == 200, off.text
    db_session.refresh(p)
    assert p.status == "off_shelf"

    on = client.put(
        f"/api/admin/shop/products/{p.id}",
        json={"status": "on_sale"},
        headers=admin_headers,
    )
    assert on.status_code == 200, on.text
    db_session.refresh(p)
    assert p.status == "on_sale"


def test_admin_list_returns_both_statuses(client, db_session, admin_headers):
    _product(db_session, name="在售测试甲", status="on_sale")
    _product(db_session, name="下架测试乙", status="off_shelf")

    res = client.get("/api/admin/shop/products?page_size=100", headers=admin_headers)
    assert res.status_code == 200, res.text
    statuses = {i["status"] for i in res.json()["items"]}
    assert "on_sale" in statuses
    assert "off_shelf" in statuses


def test_shelf_endpoint_sets_priority(client, db_session, admin_headers):
    p = _product(db_session, name="优先级测试")
    res = client.post(
        f"/api/admin/shop/products/{p.id}/shelf?status=on_sale&shelf_priority=P1",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    db_session.refresh(p)
    assert p.shelf_priority == "P1"
