# 로그인 고객 찜 목록 조회·추가·해제 비즈니스 규칙

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.products.models.products import Product, ProductCategory
from backend.domain.products.services.availability import require_available_product
from backend.domain.products.services.storage import product_storage
from backend.domain.users.services.users import UserService
from backend.domain.wishlists.models.wishlists import WishlistItem


# 고객 찜 서비스(인증은 고객 접근 토큰 검증을 그대로 사용)
class WishlistService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)

    async def _user_id(self, token: str) -> int:
        return (await self.user_service._get_user_from_access_token(token)).id

    # 찜한 상품을 현재 상품명·가격·이미지와 함께 최근 순으로 반환(판매 종료 상품은 제외)
    async def _payload(self, user_id: int) -> dict:
        rows = (
            await self.db.execute(
                select(WishlistItem, Product, ProductCategory.name)
                .join(Product, Product.id == WishlistItem.product_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .where(
                    WishlistItem.user_id == user_id,
                    Product.status == "active",
                    Product.visible.is_(True),
                    ProductCategory.is_active.is_(True),
                )
                .order_by(WishlistItem.created_at.desc(), WishlistItem.id.desc())
            )
        ).all()
        return {
            "items": [
                {
                    "id": product.id,
                    "name": product.name,
                    "category": category_name,
                    "price": product.price,
                    "image_url": product_storage.public_url(product.image_path),
                    "image_description": product.image_description or "",
                }
                for _, product, category_name in rows
            ]
        }

    async def get_wishlist(self, token: str) -> dict:
        return await self._payload(await self._user_id(token))

    # 판매 중인 상품만 찜할 수 있고, 이미 찜한 상품은 그대로 둠(멱등)
    async def add_item(self, token: str, product_id: int) -> dict:
        user_id = await self._user_id(token)
        await require_available_product(self.db, product_id)
        await self.db.execute(
            insert(WishlistItem).values(user_id=user_id, product_id=product_id).on_conflict_do_nothing(constraint="uq_wishlist_items_user_product")
        )
        await self.db.commit()
        return await self._payload(user_id)

    async def remove_item(self, token: str, product_id: int) -> dict:
        user_id = await self._user_id(token)
        await self.db.execute(delete(WishlistItem).where(WishlistItem.user_id == user_id, WishlistItem.product_id == product_id))
        await self.db.commit()
        return await self._payload(user_id)
