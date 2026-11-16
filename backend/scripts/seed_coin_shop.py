"""金币购 M1 商品池种子（幂等）。

对应《金币购体系_设计方案_v1》§2.3 的 16 个 SKU + 补足小额的 4 个零成本虚拟品（D2）。

幂等策略：按 `name` 判重，已存在则**只补缺失字段**（tier/cost_estimate/shelf_priority），
不覆盖价格与库存——避免把运营手动调过价打回原值。

用法：
    cd backend && python -m scripts.seed_coin_shop
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import Coupon, ShopProduct  # noqa: E402

# (名称, 分类, 类型, 金币价, 现金参考价, 成本估算, 区间, 优先级, 库存, 权益类型, 权益参数)
PRODUCTS = [
    # ---------- 小额 0~500 ----------
    # M1.5：虚拟卡类用 code（兑换时发卡密）；实物与需运营开通的用 manual（兑换单 pending）
    ("错题本导出券（PDF）", "权益券", "virtual", 200, 2.0, 0.2, "small", "P1", -1, "manual", None),
    ("单套真题解锁券", "权益券", "virtual", 300, 3.0, 0.3, "small", "P1", -1, "manual", None),
    ("视频会员日卡", "视频会员", "virtual", 400, 4.0, 3.0, "small", "P1", 200, "code", None),
    ("限定头像框（30天）", "专属头像框", "virtual", 150, 1.5, 0.0, "small", "P2", -1, "avatar_frame", {"frame": "limited_30d", "days": 30}),
    ("文具小件（中性笔×1）", "文具", "physical", 500, 4.0, 2.4, "small", "P2", 100, "manual", None),
    # D2：补足小额的 4 个零成本虚拟品
    ("学习之星称号（7天）", "限定称号", "virtual", 120, 1.2, 0.0, "small", "P2", -1, "manual", None),
    ("表情包皮肤·激励版", "虚拟道具", "virtual", 80, 0.8, 0.0, "small", "P3", -1, "manual", None),
    ("免签到卡×1", "虚拟道具", "virtual", 100, 1.0, 0.0, "small", "P2", -1, "manual", None),
    ("双倍经验卡（1天）", "虚拟道具", "virtual", 250, 2.5, 0.0, "small", "P2", -1, "manual", None),
    # ---------- 中额 500~5000 ----------
    ("题库月卡", "题库会员", "virtual", 2000, 20.0, 2.0, "mid", "P1", -1, "manual", None),
    ("视频会员周卡", "视频会员", "virtual", 1200, 12.0, 9.6, "mid", "P1", 100, "code", None),
    ("联考教辅（单册）", "教辅书籍", "physical", 4500, 36.0, 25.0, "mid", "P1", 50, "manual", None),
    ("文具套装", "文具", "physical", 3750, 30.0, 21.0, "mid", "P2", 50, "manual", None),
    ("电商卡 30 元", "电商卡", "virtual", 3900, 30.0, 28.5, "mid", "P2", 50, "code", None),
    ("错题本精装打印", "实物定制", "physical", 3125, 25.0, 18.0, "mid", "P3", 30, "manual", None),
    # ---------- 大额 5000+ ----------
    ("题库年卡", "题库会员", "virtual", 12000, 120.0, 12.0, "large", "P1", -1, "manual", None),
    ("教辅全套（6册）", "教辅书籍", "physical", 22500, 180.0, 126.0, "large", "P1", 20, "manual", None),
    ("题库两年卡", "题库会员", "virtual", 20000, 200.0, 20.0, "large", "P2", -1, "manual", None),
    ("电商卡 100 元", "电商卡", "virtual", 13000, 100.0, 95.0, "large", "P2", 20, "code", None),
    ("数码配件（无线鼠标）", "数码配件", "physical", 15000, 120.0, 84.0, "large", "P3", 10, "manual", None),
]

# 券模板：C 类场景任务与"到期兜底"使用
COUPONS = [
    ("MONTH_CARD_20OFF", "题库月卡 8 折券", "rate", 0.8, "product", "", 500, 0),
    ("STATIONERY_10OFF", "文具套装 9 折券", "rate", 0.9, "category", "文具", 500, 0),
    ("ANY_5OFF", "全场满 1000 币减 5 元券", "amount", 5.0, "all", "", 1000, 0),
]


def main() -> None:
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for (name, category, ptype, coin, cash, cost, tier, priority, stock, d_type, d_payload) in PRODUCTS:
            existing = db.query(ShopProduct).filter(ShopProduct.name == name).first()
            if existing:
                # 只补缺失的分层字段，不动价格/库存（运营可能已调过）
                changed = False
                if getattr(existing, "tier", None) != tier:
                    existing.tier = tier
                    changed = True
                if getattr(existing, "cost_estimate", None) is None:
                    existing.cost_estimate = cost
                    changed = True
                if getattr(existing, "shelf_priority", None) in (None, "", "P3") and priority != "P3":
                    existing.shelf_priority = priority
                    changed = True
                # M1.5：把历史 'none' 的错误交付方式修正为真实类型（否则兑换会被拒绝）
                if (existing.deliverable_type or "none").strip() == "none" and d_type != "none":
                    existing.deliverable_type = d_type
                    existing.deliverable_payload = d_payload
                    changed = True
                if changed:
                    updated += 1
                continue

            db.add(
                ShopProduct(
                    name=name,
                    category=category,
                    product_type=ptype,
                    coin_price=coin,
                    cash_price=cash,
                    stock=stock,
                    description=f"金币购 M1 商品：{name}（参考价 {cash} 元，金币价 {coin}）",
                    deliverable_type=d_type,
                    deliverable_payload=d_payload,
                    status="on_sale",
                    tier=tier,
                    cost_estimate=cost,
                    shelf_priority=priority,
                    min_stock_alert=5,
                )
            )
            created += 1

        for (code, title, dtype, dvalue, scope, scope_value, stock, coin_only) in COUPONS:
            if db.query(Coupon).filter(Coupon.code == code).first():
                continue
            db.add(
                Coupon(
                    code=code,
                    title=title,
                    discount_type=dtype,
                    discount_value=dvalue,
                    scope=scope,
                    scope_value=scope_value,
                    coin_only=coin_only,
                    stock=stock,
                    status="active",
                )
            )

        db.commit()
        total = db.query(ShopProduct).count()
        coupons = db.query(Coupon).count()
        print(f"商品：新增 {created} / 补字段 {updated} / 当前共 {total}")
        print(f"券模板：当前共 {coupons}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
