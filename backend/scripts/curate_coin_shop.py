"""金币商城商品整理（2026-11-05）。

用户要求：
1. 学生端只保留「头像框 / 称号 / 文具 / 习题册」四类，并新增「警大文创」；
2. 价格适当上涨（任务奖励金币偏多，需提高兑换门槛）。

幂等：按商品名匹配，重复执行结果一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import ShopProduct  # noqa: E402

# 保留的分类（学生端可见）
KEEP_CATEGORIES = {"限定称号", "专属头像框", "文具", "习题册", "警大文创"}

# 分类归并：旧分类 → 新分类
CATEGORY_MAP = {
    "教辅书籍": "习题册",
    "实物定制": "文具",
}

# 保留商品的涨价幅度（约 +40%，向上取整到 10）
PRICE_MULTIPLIER = 1.4
ROUND_TO = 10

# 新增警大文创（实物，走 manual 交付）
NEW_PRODUCTS = [
    ("警徽钥匙扣", "警大文创", 800, 8.0, 5.0, "small", "P1", 200),
    ("警大文创笔记本", "警大文创", 1200, 12.0, 8.0, "small", "P1", 150),
    ("警大文创帆布袋", "警大文创", 2400, 24.0, 15.0, "mid", "P1", 100),
    ("警校徽章套装", "警大文创", 3200, 32.0, 20.0, "mid", "P2", 80),
    ("警大纪念笔筒", "警大文创", 1800, 18.0, 11.0, "small", "P2", 100),
]

# 明确下架的（保留列表之外的其它品类）
DELIST_CATEGORIES = {"视频会员", "权益券", "题库会员", "电商卡", "数码配件", "虚拟道具"}


def raise_price(price: int) -> int:
    if not price:
        return price
    raw = price * PRICE_MULTIPLIER
    return int(-(-raw // ROUND_TO) * ROUND_TO)


def main() -> None:
    db = SessionLocal()
    kept, delisted, created = 0, 0, 0
    try:
        products = db.query(ShopProduct).all()

        # 1) 分类归并
        for p in products:
            new_cat = CATEGORY_MAP.get(p.category or "")
            if new_cat and p.category != new_cat:
                p.category = new_cat

        # 2) 保留的涨价，其余下架
        for p in products:
            if (p.category or "") in KEEP_CATEGORIES:
                raised = raise_price(p.coin_price or 0)
                if raised != (p.coin_price or 0):
                    p.coin_price = raised
                p.status = "on_sale"
                kept += 1
            elif (p.category or "") in DELIST_CATEGORIES:
                p.status = "off_shelf"
                delisted += 1
            else:
                # 未识别分类：保守下架，避免误上架
                p.status = "off_shelf"
                delisted += 1

        # 3) 新增警大文创
        for name, category, coin, cash, cost, tier, priority, stock in NEW_PRODUCTS:
            exists = db.query(ShopProduct).filter(ShopProduct.name == name).first()
            if exists:
                exists.category = category
                exists.status = "on_sale"
                continue
            db.add(
                ShopProduct(
                    name=name,
                    category=category,
                    product_type="physical",
                    coin_price=coin,
                    cash_price=cash,
                    stock=stock,
                    description=f"警大文创：{name}（参考价 {cash} 元，金币价 {coin}）",
                    deliverable_type="manual",
                    status="on_sale",
                    tier=tier,
                    cost_estimate=cost,
                    shelf_priority=priority,
                    min_stock_alert=5,
                )
            )
            created += 1

        db.commit()

        print(f"保留并涨价 {kept} 个，下架 {delisted} 个，新增警大文创 {created} 个")
        print("=== 当前学生端在售商品 ===")
        for p in (
            db.query(ShopProduct)
            .filter(ShopProduct.status == "on_sale")
            .order_by(ShopProduct.category.asc(), ShopProduct.coin_price.asc())
            .all()
        ):
            print(f"  [{p.category}] {p.name:<20} {p.coin_price:>6} 币")
    finally:
        db.close()


if __name__ == "__main__":
    main()
