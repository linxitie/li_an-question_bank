"""头像框到期（2026-11-05）测试。

- 带 days 的兑换：到期时间 = 交付时间 + days
- 到期后：mine 标记 expired、不能佩戴、已佩戴的自动摘除
- 无 days 的视为永久
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.models import CoinExchange, ShopProduct, SysUser
from app.services import decoration_expiry


def _frame_exchange(db, user_id, frame="limited_30d", days=30, delivered_days_ago=0, request_id="r1"):
    product = db.query(ShopProduct).filter(ShopProduct.name == "限定头像框（测试）").first()
    if not product:
        product = ShopProduct(
            name="限定头像框（测试）",
            category="专属头像框",
            product_type="virtual",
            coin_price=100,
            deliverable_type="avatar_frame",
            deliverable_payload={"frame": frame, "days": days} if days else {"frame": frame},
            status="on_sale",
            tier="small",
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    payload = {"frame": frame}
    if days:
        payload["days"] = days
    db.add(
        CoinExchange(
            user_id=user_id,
            product_id=product.id,
            product_name=product.name,
            product_type="virtual",
            coin_cost=100,
            status="completed",
            deliverable_type="avatar_frame",
            deliverable_payload=payload,
            request_id=request_id,
            delivered_at=datetime.now() - timedelta(days=delivered_days_ago),
            created_at=datetime.now() - timedelta(days=delivered_days_ago),
        )
    )
    db.commit()


def test_expiry_computed_from_delivery_time(db_session, test_user):
    _frame_exchange(db_session, test_user.user_id, days=30, delivered_days_ago=10)
    expiries = decoration_expiry.frame_expiries(db_session, test_user.user_id)
    expire_at = expiries["limited_30d"]
    assert expire_at is not None
    left = (expire_at - datetime.now()).days
    assert 19 <= left <= 20  # 30 - 10 天


def test_permanent_frame_never_expires(db_session, test_user):
    _frame_exchange(db_session, test_user.user_id, frame="gold_badge", days=None, request_id="r2")
    expiries = decoration_expiry.frame_expiries(db_session, test_user.user_id)
    assert expiries["gold_badge"] is None


def test_expired_frame_not_equippable(client, db_session, auth_headers, test_user):
    _frame_exchange(db_session, test_user.user_id, days=30, delivered_days_ago=31)

    mine = client.get("/api/user/decoration/mine", headers=auth_headers)
    assert mine.status_code == 200, mine.text
    frames = {f["frame"]: f for f in mine.json()["frames"]}
    assert frames["limited_30d"]["expired"] is True

    res = client.post(
        "/api/user/decoration/equip-frame",
        json={"frame": "limited_30d"},
        headers=auth_headers,
    )
    assert res.status_code == 400, res.text
    assert "过期" in res.json()["detail"]


def test_equipped_frame_auto_removed(client, db_session, auth_headers, test_user):
    _frame_exchange(db_session, test_user.user_id, days=30, delivered_days_ago=31)
    test_user.avatar_frame = "limited_30d"
    db_session.commit()

    mine = client.get("/api/user/decoration/mine", headers=auth_headers)
    assert mine.status_code == 200
    assert mine.json()["current_frame"] is None

    db_session.refresh(test_user)
    assert test_user.avatar_frame is None


def test_valid_frame_still_equippable(client, db_session, auth_headers, test_user):
    _frame_exchange(db_session, test_user.user_id, days=30, delivered_days_ago=5)
    res = client.post(
        "/api/user/decoration/equip-frame",
        json={"frame": "limited_30d"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text

    mine = client.get("/api/user/decoration/mine", headers=auth_headers)
    frame = {f["frame"]: f for f in mine.json()["frames"]}["limited_30d"]
    assert frame["expired"] is False
    assert frame["days_left"] >= 24


def test_expire_all_sweeps_equipped(db_session, test_user):
    _frame_exchange(db_session, test_user.user_id, days=30, delivered_days_ago=40)
    test_user.avatar_frame = "limited_30d"
    db_session.commit()

    report = decoration_expiry.expire_all(db_session)
    assert report["removed"] >= 1
    db_session.refresh(test_user)
    assert test_user.avatar_frame is None
