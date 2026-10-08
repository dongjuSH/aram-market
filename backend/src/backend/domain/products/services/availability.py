# 고객이 담기·찜·후기·문의 대상으로 삼을 수 있는 판매 중 상품인지와 재고 부족 오류를 만드는 공통 규칙

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.errors import api_error
from backend.domain.products.models.products import Product, ProductCategory


# 판매 중(활성·노출·활성 카테고리) 상품이 아니면 404 오류, 판매 중이면 현재 재고 반환(재고 확인용 읽기, 잠금 없음)
async def require_available_product(db: AsyncSession, product_id: int) -> tuple[str, int]:
    row = (
        await db.execute(
            select(Product.name, Product.stock)
            .join(ProductCategory, ProductCategory.id == Product.category_id)
            .where(
                Product.id == product_id,
                Product.status == "active",
                Product.visible.is_(True),
                ProductCategory.is_active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_AVAILABLE", "판매 중이지 않은 상품입니다.")
    return row[0], row[1]


# 상품 하나의 재고 부족 안내 문구(0개면 품절, 아니면 남은 수량)
def stock_shortage_message(name: str, available: int) -> str:
    if available <= 0:
        return f"'{name}' 상품이 품절되었습니다."
    return f"'{name}' 상품은 {available}개 남아 있습니다."


# 재고 부족 409 OUT_OF_STOCK(장바구니·주문 생성·결제 승인 공통). stock_shortages는 [{"product_id", "name", "available"}]
def out_of_stock_error(shortages: list[dict]) -> HTTPException:
    first = shortages[0]
    message = stock_shortage_message(first["name"], first["available"])
    if len(shortages) > 1:
        message += f" 외 {len(shortages) - 1}개 상품의 재고가 부족합니다."
    return api_error(status.HTTP_409_CONFLICT, "OUT_OF_STOCK", message, stock_shortages=shortages)
