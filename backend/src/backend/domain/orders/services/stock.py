# 주문 재고 차감·복구 규칙(주문 행을 잠근 상태에서만 호출해 같은 주문의 재고가 두 번 차감·복구되지 않게 함)

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.orders.models.orders import Order, OrderItem
from backend.domain.products.models.products import Product

logger = logging.getLogger(__name__)

STOCK_RESERVED = "reserved"  # 재고를 차감함
STOCK_RELEASED = "released"  # 차감한 재고를 되돌림
STOCK_SHORTAGE = "shortage"  # 결제가 확정됐지만 재고가 모자라 차감하지 못함(관리자 확인 필요)


# 주문 상품을 상품별 수량으로 모음(상품 행이 삭제돼 product_id가 없는 줄은 이름과 함께 따로 반환)
async def _order_lines(db: AsyncSession, order_id: int) -> tuple[dict[int, int], dict[int, str], list[str]]:
    rows = (
        await db.execute(select(OrderItem.product_id, OrderItem.product_name, OrderItem.quantity).where(OrderItem.order_id == order_id))
    ).all()
    quantities: dict[int, int] = {}
    names: dict[int, str] = {}
    missing: list[str] = []
    for product_id, name, quantity in rows:
        if product_id is None:
            missing.append(name)
            continue
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        names[product_id] = name
    return quantities, names, missing


# 상품 행을 id 오름차순으로 잠가 현재 재고를 읽음(여러 주문이 서로 다른 순서로 잠가 교착되지 않도록 순서 고정)
async def _lock_stocks(db: AsyncSession, product_ids: list[int]) -> dict[int, int]:
    if not product_ids:
        return {}
    rows = (
        await db.execute(select(Product.id, Product.stock).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update())
    ).all()
    return {product_id: stock for product_id, stock in rows}


# 주문의 모든 상품 재고가 충분하면 한꺼번에 차감하고 reserved로 표시, 하나라도 모자라면 아무것도 바꾸지 않고 부족 목록 반환
# 부족 목록 항목: {"product_id", "name", "available"}(상품 행이 없으면 product_id None·available 0)
async def reserve_stock(db: AsyncSession, order: Order) -> list[dict]:
    quantities, names, missing = await _order_lines(db, order.id)
    shortages = [{"product_id": None, "name": name, "available": 0} for name in missing]
    stocks = await _lock_stocks(db, sorted(quantities))
    for product_id in sorted(quantities):
        available = stocks.get(product_id, 0)
        if product_id not in stocks or available < quantities[product_id]:
            shortages.append({"product_id": product_id, "name": names[product_id], "available": max(available, 0)})
    if shortages:
        return shortages
    for product_id in sorted(quantities):
        await db.execute(update(Product).where(Product.id == product_id).values(stock=Product.stock - quantities[product_id]))
    order.stock_status = STOCK_RESERVED
    return []


# 차감한 주문(reserved)만 재고를 되돌리고 released로 표시(그 밖의 상태는 아무것도 하지 않아 여러 번 호출해도 한 번만 복구)
# 상품 행이 삭제된 줄은 되돌릴 대상이 없어 건너뜀. 소프트 삭제·비노출 상품도 행이 있으므로 되돌린다
async def release_stock(db: AsyncSession, order: Order) -> bool:
    if order.stock_status != STOCK_RESERVED:
        return False
    quantities, _, missing = await _order_lines(db, order.id)
    if missing:
        logger.warning("stock release skipped deleted product lines order=%s count=%s", order.order_number, len(missing))
    stocks = await _lock_stocks(db, sorted(quantities))
    for product_id in sorted(quantities):
        if product_id in stocks:
            await db.execute(update(Product).where(Product.id == product_id).values(stock=Product.stock + quantities[product_id]))
    order.stock_status = STOCK_RELEASED
    return True
