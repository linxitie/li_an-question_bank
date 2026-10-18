"""金币商城（E9）模块测试（P2-40 / P2-44）。

覆盖：兑换成功恰好发布一次 ``shop.purchased`` 且载荷含消费额；
余额不足、库存不足、权益发放异常回滚时不发布事件且余额与流水保持一致；
重复 request_id 幂等拒绝且不重复扣币。
"""
import pytest

from app.api.v1.reward import shop as shop_api
from app.models.models import CoinRecord, ShopProduct


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append(
            {
                "user_id": user_id,
                "trigger_type": trigger_type,
                "session": session,
            }
        )
        return True

    monkeypatch.setattr(shop_api, "record_user_action", fake_record)
    return events


@pytest.fixture
def buyer(db_session, test_user):
    test_user.total_coins = 500
    db_session.commit()
    db_session.refresh(test_user)
    return test_user


@pytest.fixture
def product(db_session):
    row = ShopProduct(
        name="限定称号·执法先锋",
        category="限定称号",
        product_type="virtual",
        coin_price=120,
        stock=3,
        image_url="🎖️",
        description="测试商品",
        deliverable_type="none",
        deliverable_payload={},
        status="on_sale",
        sort_order=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _exchange(client, auth_headers, product_id, request_id="req-1"):
    return client.post(
        "/api/shop/exchange",
        headers=auth_headers,
        json={"product_id": product_id, "request_id": request_id},
    )


def test_exchange_success_publishes_once_and_keeps_balance_in_sync(
    client, auth_headers, buyer, product, published, db_session
):
    response = _exchange(client, auth_headers, product.id)

    assert response.status_code == 200
    body = response.json()
    assert body["balance"] == 380
    assert body["coin_cost"] == 120

    shop_events = [e for e in published if e["trigger_type"] == "shop.purchased"]
    assert len(shop_events) == 1
    assert shop_events[0]["session"]["coin_cost"] == 120
    assert shop_events[0]["session"]["balance"] == 380

    db_session.expire_all()
    records = db_session.query(CoinRecord).all()
    assert len(records) == 1
    assert records[0].coin_change == -120
    assert records[0].current_balance == 380
    assert records[0].transaction_type == "SPEND"
    assert records[0].source_type == "SHOP"

    db_session.refresh(buyer)
    assert buyer.total_coins == 380
    assert records[0].current_balance == buyer.total_coins


def test_insufficient_coins_does_not_publish_or_write(
    client, auth_headers, buyer, product, published, db_session
):
    buyer.total_coins = 50
    db_session.commit()

    response = _exchange(client, auth_headers, product.id)

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "金币不足"
    assert published == []
    assert db_session.query(CoinRecord).count() == 0
    db_session.refresh(buyer)
    assert buyer.total_coins == 50


def test_out_of_stock_does_not_publish_or_write(
    client, auth_headers, buyer, product, published, db_session
):
    product.stock = 0
    db_session.commit()

    response = _exchange(client, auth_headers, product.id)

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "商品库存不足"
    assert published == []
    assert db_session.query(CoinRecord).count() == 0
    db_session.refresh(buyer)
    assert buyer.total_coins == 500


def test_delivery_failure_rolls_back_and_does_not_publish(
    client, auth_headers, buyer, product, published, db_session, monkeypatch
):
    def explode(*args, **kwargs):
        raise RuntimeError("权益发放失败")

    monkeypatch.setattr(shop_api.deliverable_service, "deliver", explode)

    response = _exchange(client, auth_headers, product.id)

    assert response.status_code == 500
    assert published == []
    assert db_session.query(CoinRecord).count() == 0
    db_session.refresh(buyer)
    assert buyer.total_coins == 500


def test_duplicate_request_id_rejected_without_double_charge(
    client, auth_headers, buyer, product, published, db_session
):
    first = _exchange(client, auth_headers, product.id, request_id="same-req")
    second = _exchange(client, auth_headers, product.id, request_id="same-req")

    assert first.status_code == 200
    assert second.status_code == 409
    assert len([e for e in published if e["trigger_type"] == "shop.purchased"]) == 1
    assert db_session.query(CoinRecord).count() == 1
    db_session.refresh(buyer)
    assert buyer.total_coins == 380
