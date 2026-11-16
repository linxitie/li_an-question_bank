"""我的装扮（2026-11-05）：称号/头像框的拥有与佩戴。

- 未拥有的不能戴（403）；
- 佩戴称号会写 sys_user.title 并 Unique equipped 只留一个；
- 可取消佩戴（置空）；
- 头像框只能戴自己兑换过的。
"""
from __future__ import annotations

import pytest

from app.models.models import CoinExchange, ShopProduct, SysUser, Title, UserTitle


def _title(db, name="砺安之星"):
    t = Title(title_code=f"t_{name}", name=name, unlock_level=1)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_equip_title_requires_ownership(client, db_session, auth_headers, test_user):
    t = _title(db_session, "未拥有称号")
    res = client.post(
        "/api/user/decoration/equip-title",
        json={"title_id": t.title_id},
        headers=auth_headers,
    )
    assert res.status_code == 403, res.text


def test_equip_and_unequip_title(client, db_session, auth_headers, test_user):
    t1 = _title(db_session, "称号甲")
    t2 = _title(db_session, "称号乙")
    db_session.add(UserTitle(user_id=test_user.user_id, title_id=t1.title_id, equipped=0))
    db_session.add(UserTitle(user_id=test_user.user_id, title_id=t2.title_id, equipped=0))
    db_session.commit()

    res = client.post(
        "/api/user/decoration/equip-title",
        json={"title_id": t1.title_id},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["current_title"] == "称号甲"

    # 换戴乙：甲的 equipped 应被清掉
    client.post(
        "/api/user/decoration/equip-title",
        json={"title_id": t2.title_id},
        headers=auth_headers,
    )
    db_session.expire_all()
    rows = db_session.query(UserTitle).filter(UserTitle.user_id == test_user.user_id).all()
    equipped = [r.title_id for r in rows if r.equipped == 1]
    assert equipped == [t2.title_id]

    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).first()
    assert user.title == "称号乙"

    # 取消佩戴
    off = client.post(
        "/api/user/decoration/equip-title",
        json={"title_id": None},
        headers=auth_headers,
    )
    assert off.status_code == 200
    db_session.expire_all()
    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).first()
    assert user.title is None


def test_equip_frame_requires_ownership(client, db_session, auth_headers, test_user):
    res = client.post(
        "/api/user/decoration/equip-frame",
        json={"frame": "not-owned-frame"},
        headers=auth_headers,
    )
    assert res.status_code == 403, res.text


def test_equip_frame_from_exchange(client, db_session, auth_headers, test_user):
    product = ShopProduct(
        name="限定头像框（测试）",
        category="专属头像框",
        product_type="virtual",
        coin_price=100,
        deliverable_type="avatar_frame",
        deliverable_payload={"frame": "limited_30d"},
        status="on_sale",
        tier="small",
    )
    db_session.add(product)
    db_session.commit()
    db_session.add(
        CoinExchange(
            user_id=test_user.user_id,
            product_id=product.id,
            product_name=product.name,
            product_type="virtual",
            coin_cost=100,
            status="completed",
            deliverable_type="avatar_frame",
            deliverable_payload={"frame": "limited_30d"},
            request_id="test-frame-1",
        )
    )
    db_session.commit()

    mine = client.get("/api/user/decoration/mine", headers=auth_headers)
    assert mine.status_code == 200, mine.text
    frames = mine.json()["frames"]
    assert any(f["frame"] == "limited_30d" for f in frames)

    res = client.post(
        "/api/user/decoration/equip-frame",
        json={"frame": "limited_30d"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).first()
    assert user.avatar_frame == "limited_30d"

    off = client.post(
        "/api/user/decoration/equip-frame",
        json={"frame": None},
        headers=auth_headers,
    )
    assert off.status_code == 200
    db_session.expire_all()
    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).first()
    assert user.avatar_frame is None
