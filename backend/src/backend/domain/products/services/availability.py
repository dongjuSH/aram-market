# 고객이 담기·찜·후기·문의 대상으로 삼을 수 있는 판매 중 상품인지 확인하는 공통 규칙

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.errors import api_error
from backend.domain.products.models.products import Product, ProductCategory


# 판매 중(활성·노출·활성 카테고리) 상품이 아니면 404 오류
async def require_available_product(db: AsyncSession, product_id: int) -> None:
    available = (
        await db.execute(
            select(Product.id)
            .join(ProductCategory, ProductCategory.id == Product.category_id)
            .where(
                Product.id == product_id,
                Product.status == "active",
                Product.visible.is_(True),
                ProductCategory.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if available is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_AVAILABLE", "판매 중이지 않은 상품입니다.")
