"""金币购 M1.5（2026-11-05）：卡密交付 / 人工处理 / 防"扣币无交付"。

核心断言：
- 无交付方式（none）或卡密不足时，**扣币前就拒绝**，余额不变；
- code 类商品兑换后能拿到卡密，且卡密状态从 available → assigned；
- manual 类商品兑换单为 pending，可被管理员标记发货；
- 「我的兑换」接口能返回交付物（这是用户"兑换完在哪看"的答案）。
"""
from __future__ import annotations

from app.models.models import CoinExchange, ShopCode, ShopProduct


def _product(db, *, name, coin=200, dtype="code", stock=-1, price_in_tier="small"):
    p = ShopProduct(
        name=name,
        category="测试",
        product_type="virtual",
        coin_price=coin,
        stock=stock,
        status="on_sale",
        tier=price_in_tier,
        deliverable_type=dtype,
        shelf_priority="P1",
        min_stock_alert=5,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _codes(db, product_id, values):
    for v in values:
        db.add(ShopCode(product_id=product_id, code=v, status="available"))
    db.commit()


def test_exchange_rejected_when_deliverable_missing(client, db_session, auth_headers, test_user):
    """交付方式为 none：必须拒绝且不扣币（旧逻辑会扣币但不发货）。"""
    product = _product(db_session, name="无交付商品", coin=100, dtype="none")
    test_user.total_coins = 500
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "none-1"},
        headers=auth_headers,
    )
    assert res.status_code == 400, res.text
    assert "交付" in res.json()["detail"]

    db_session.refresh(test_user)
    assert test_user.total_coins == 500, "被拒绝的兑换不能扣币"
    assert db_session.query(CoinExchange).filter(CoinExchange.request_id == "none-1").count() == 0


def test_exchange_rejected_when_code_pool_empty(client, db_session, auth_headers, test_user):
    product = _product(db_session, name="卡密耗尽商品", coin=100, dtype="code")
    test_user.total_coins = 500
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "code-empty-1"},
        headers=auth_headers,
    )
    assert res.status_code == 400, res.text
    assert "卡密" in res.json()["detail"]
    db_session.refresh(test_user)
    assert test_user.total_coins == 500


def test_exchange_code_product_delivers_code(client, db_session, auth_headers, test_user):
    product = _product(db_session, name="视频会员日卡测试", coin=100, dtype="code")
    _codes(db_session, product.id, ["TEST-A", "TEST-B"])
    test_user.total_coins = 500
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "code-ok-1"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["delivered_code"] == "TEST-A", "按最早入库发放"
    assert body["status"] == "completed"

    db_session.refresh(test_user)
    assert test_user.total_coins == 400

    used = db_session.query(ShopCode).filter(ShopCode.code == "TEST-A").first()
    assert used.status == "assigned"
    assert used.exchange_id == body["exchange_id"]
    assert used.assigned_user_id == test_user.user_id

    # 第二条码仍可用
    left = db_session.query(ShopCode).filter(ShopCode.code == "TEST-B").first()
    assert left.status == "available"


def test_exchange_manual_product_is_pending(client, db_session, auth_headers, test_user):
    product = _product(db_session, name="实物商品测试", coin=100, dtype="manual")
    test_user.total_coins = 500
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "manual-1"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["delivered_code"] is None
    assert "待人工" in body["message"] or "待发货" in body["message"]

    order = db_session.query(CoinExchange).filter(CoinExchange.id == body["exchange_id"]).first()
    assert order.status == "pending"


def test_my_exchanges_returns_deliverable(client, db_session, auth_headers, test_user):
    product = _product(db_session, name="我的兑换展示测试", coin=100, dtype="code")
    _codes(db_session, product.id, ["SHOW-CODE-1"])
    test_user.total_coins = 500
    db_session.commit()

    client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "show-1"},
        headers=auth_headers,
    )

    res = client.get("/api/shop/exchange/mine", headers=auth_headers)
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    target = next(i for i in items if i["product_name"] == "我的兑换展示测试")
    assert target["delivered_code"] == "SHOW-CODE-1"
    assert target["status_text"] == "已交付"
    assert target["deliverable_type"] == "code"


def test_admin_import_codes_and_stats(client, db_session, admin_headers):
    product = _product(db_session, name="批量导入测试", coin=100, dtype="code")

    res = client.post(
        f"/api/admin/shop/products/{product.id}/codes",
        json={"codes": ["IMP-1", "IMP-2", "IMP-1", "  "], "batch_no": "B1"},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["imported"] == 2
    assert body["skipped"] == 2
    assert body["available"] == 2

    stats = client.get(f"/api/admin/shop/products/{product.id}/codes/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert stats.json()["available"] == 2


def test_admin_pending_orders_and_ship(client, db_session, auth_headers, admin_headers, test_user):
    product = _product(db_session, name="待发货订单测试", coin=100, dtype="manual")
    test_user.total_coins = 500
    db_session.commit()

    body = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "ship-1"},
        headers=auth_headers,
    ).json()

    pending = client.get("/api/admin/shop/orders?status=pending", headers=admin_headers)
    assert pending.status_code == 200, pending.text
    ids = [i["id"] for i in pending.json()["items"]]
    assert body["exchange_id"] in ids

    ship = client.post(f"/api/admin/shop/orders/{body['exchange_id']}/ship", headers=admin_headers)
    assert ship.status_code == 200, ship.text
    assert ship.json()["status"] == "completed"

    order = db_session.query(CoinExchange).filter(CoinExchange.id == body["exchange_id"]).first()
    assert order.status == "completed"
    assert order.shipped_at is not None
