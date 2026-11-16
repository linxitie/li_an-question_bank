"""金币购 M1（2026-11-04）：金币批次台账 + 分层商品 + 券核销 + 到期清零 + 指标。

覆盖三条不变量：发放建批次、消费 FIFO 扣批次、到期清零写 EXPIRE 流水。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.models import CoinLot, CoinRecord, Coupon, CouponGrant, ShopProduct, SysUser
from app.services import coin_ledger


def _mk_product(db, *, name="测试商品", coin=200, tier="small", stock=-1, category="权益券"):
    # M1.5 起：deliverable_type='none' 的商品会在扣币前被拒绝，
    # 这里的通用测试商品用 manual（待人工处理），避免与交付防线冲突。
    p = ShopProduct(
        name=name,
        category=category,
        product_type="virtual",
        coin_price=coin,
        stock=stock,
        status="on_sale",
        tier=tier,
        cost_estimate=0.2,
        shelf_priority="P1",
        min_stock_alert=5,
        deliverable_type="manual",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _user(db, uid=880001, coins=0):
    u = SysUser(
        user_id=uid,
        user_no=str(uid),
        username=f"u{uid}",
        password="x",
        phone="13800000000",
        user_type="student",
        nickname=f"用户{uid}",
        total_coins=coins,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# --------------------------- 台账 ---------------------------

def test_grant_creates_lot_and_record(db_session):
    u = _user(db_session)
    lot = coin_ledger.grant(db_session, u, 300, source_type="TASK", related_id=1, description="完成任务")
    db_session.commit()

    assert u.total_coins == 300
    assert lot is not None and lot.remaining == 300
    assert lot.expire_at > datetime.now() + timedelta(days=360)

    rec = db_session.query(CoinRecord).filter(CoinRecord.user_id == u.user_id).first()
    assert rec.transaction_type == "GAIN" and rec.coin_change == 300


def test_spend_is_fifo_by_expire_time(db_session):
    u = _user(db_session)
    # 两批：先到期的 100，后到期的 200
    lot_early = coin_ledger.grant(db_session, u, 100, description="早批次")
    lot_late = coin_ledger.grant(db_session, u, 200, description="晚批次")
    lot_early.expire_at = datetime.now() + timedelta(days=10)
    lot_late.expire_at = datetime.now() + timedelta(days=200)
    db_session.commit()

    coin_ledger.spend(db_session, u, 150, description="消费")
    db_session.commit()

    assert u.total_coins == 150
    assert lot_early.remaining == 0, "应先扣最早到期的批次"
    assert lot_late.remaining == 150


def test_spend_tolerates_legacy_coins_without_lots(db_session):
    """历史金币没有批次：消费时应只扣余额，不报错。"""
    u = _user(db_session, coins=500)
    coin_ledger.spend(db_session, u, 200, description="消费历史金币")
    db_session.commit()
    assert u.total_coins == 300
    assert db_session.query(CoinLot).filter(CoinLot.user_id == u.user_id).count() == 0


def test_expire_due_clears_lot_and_writes_expire_record(db_session):
    u = _user(db_session)
    lot = coin_ledger.grant(db_session, u, 200)
    lot.expire_at = datetime.now() - timedelta(days=1)
    db_session.commit()

    report = coin_ledger.expire_due(db_session)
    assert report["lots"] == 1
    assert report["expired_coins"] == 200
    db_session.refresh(u)
    db_session.refresh(lot)
    assert u.total_coins == 0
    assert lot.remaining == 0

    rec = (
        db_session.query(CoinRecord)
        .filter(CoinRecord.user_id == u.user_id, CoinRecord.source_type == "EXPIRY")
        .first()
    )
    assert rec is not None and rec.coin_change == -200
    # 到期用 SPEND + source_type=EXPIRY 表达（transaction_type 列宽只有 5，放不下 EXPIRE）
    assert rec.transaction_type == "SPEND"


def test_expiring_soon_lists_only_window(db_session):
    u = _user(db_session)
    near = coin_ledger.grant(db_session, u, 50)
    far = coin_ledger.grant(db_session, u, 80)
    near.expire_at = datetime.now() + timedelta(days=5)
    far.expire_at = datetime.now() + timedelta(days=100)
    db_session.commit()

    info = coin_ledger.expiring_soon(db_session, u.user_id, days=30)
    assert info["total"] == 50
    assert len(info["items"]) == 1


# --------------------------- 商城接口 ---------------------------

def test_product_list_filters_by_tier(client, db_session):
    _mk_product(db_session, name="小额A", coin=100, tier="small")
    _mk_product(db_session, name="中额B", coin=2000, tier="mid")
    _mk_product(db_session, name="大额C", coin=12000, tier="large")

    res = client.get("/api/shop/products?tier=mid")
    assert res.status_code == 200, res.text
    names = [i["name"] for i in res.json()["items"]]
    assert names == ["中额B"]


def test_quote_returns_usable_coupon_and_final_price(client, db_session, auth_headers, test_user):
    product = _mk_product(db_session, name="月卡", coin=2000, tier="mid")
    coupon = Coupon(
        code="TEST20",
        title="8 折券",
        discount_type="rate",
        discount_value=0.8,
        scope="all",
        scope_value="",
        stock=10,
        status="active",
    )
    db_session.add(coupon)
    db_session.commit()
    db_session.add(CouponGrant(user_id=test_user.user_id, coupon_id=coupon.id, status="unused"))
    db_session.commit()

    res = client.get(f"/api/shop/products/{product.id}/quote", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["coin_price"] == 2000
    assert body["final_coin_price"] == 1600
    assert len(body["usable_coupons"]) == 1
    assert body["cash_channel_available"] is False


def test_exchange_with_coupon_marks_used_and_deducts_discounted_price(
    client, db_session, auth_headers, test_user
):
    product = _mk_product(db_session, name="月卡2", coin=2000, tier="mid")
    coupon = Coupon(
        code="TEST80",
        title="8 折券",
        discount_type="rate",
        discount_value=0.8,
        scope="all",
        scope_value="",
        stock=10,
        status="active",
    )
    db_session.add(coupon)
    db_session.commit()
    grant = CouponGrant(user_id=test_user.user_id, coupon_id=coupon.id, status="unused")
    db_session.add(grant)
    db_session.commit()

    test_user.total_coins = 2000
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "req-coupon-1", "coupon_grant_id": grant.id},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["coin_cost"] == 1600
    assert body["balance"] == 400

    db_session.refresh(grant)
    assert grant.status == "used"
    assert grant.exchange_id == body["exchange_id"]


def test_exchange_duplicate_request_is_rejected(client, db_session, auth_headers, test_user):
    product = _mk_product(db_session, name="重复测试", coin=100)
    test_user.total_coins = 500
    db_session.commit()

    first = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "dup-1"},
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "dup-1"},
        headers=auth_headers,
    )
    assert second.status_code == 409


def test_exchange_decrements_stock(client, db_session, auth_headers, test_user):
    product = _mk_product(db_session, name="限量商品", coin=100, stock=2)
    test_user.total_coins = 1000
    db_session.commit()

    res = client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "stock-1"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    db_session.refresh(product)
    assert product.stock == 1


def test_my_exchanges_lists_records(client, db_session, auth_headers, test_user):
    product = _mk_product(db_session, name="记录测试", coin=100)
    test_user.total_coins = 500
    db_session.commit()
    client.post(
        "/api/shop/exchange",
        json={"product_id": product.id, "request_id": "mine-1"},
        headers=auth_headers,
    )
    res = client.get("/api/shop/exchange/mine", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["total"] >= 1


# --------------------------- 管理端指标 ---------------------------

def test_admin_metrics_reports_economy(client, admin_headers):
    res = client.get("/api/admin/shop/metrics?days=30", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    for key in ("issued", "spent", "redeem_rate", "outstanding", "budget_usage_pct", "flags"):
        assert key in body


def test_admin_stock_alerts_only_low_stock(client, db_session, admin_headers):
    _mk_product(db_session, name="低库存", coin=100, stock=1)
    _mk_product(db_session, name="充足库存", coin=100, stock=999)
    res = client.get("/api/admin/shop/stock-alerts", headers=admin_headers)
    assert res.status_code == 200, res.text
    names = [i["name"] for i in res.json()["items"]]
    assert "低库存" in names
    assert "充足库存" not in names


# --------------------------- 券 ---------------------------

def test_coupon_grant_and_mine(client, db_session, auth_headers, test_user):
    coupon = Coupon(
        code="GRANTME",
        title="立减券",
        discount_type="amount",
        discount_value=5.0,
        scope="all",
        scope_value="",
        stock=5,
        status="active",
    )
    db_session.add(coupon)
    db_session.commit()

    res = client.post("/api/coupons/grant?coupon_code=GRANTME", headers=auth_headers)
    assert res.status_code == 200, res.text

    mine = client.get("/api/coupons/mine", headers=auth_headers)
    assert mine.status_code == 200, mine.text
    items = mine.json()["items"]
    assert any(i["title"] == "立减券" for i in items)
