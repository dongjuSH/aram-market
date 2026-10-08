# 로그인 고객 장바구니 조회·담기·수량 변경·삭제·병합 비즈니스 규칙

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.carts.models.carts import CartItem
from backend.domain.carts.schemas.carts import MAX_QUANTITY, CartAddRequest, CartMergeRequest, CartRemoveRequest
from backend.domain.products.models.products import Product, ProductCategory
from backend.domain.products.services.availability import out_of_stock_error, require_available_product
from backend.domain.products.services.storage import product_storage
from backend.core.errors import api_error
from backend.domain.users.services.users import UserService


# 고객 장바구니 서비스(인증은 고객 접근 토큰 검증을 그대로 사용)
class CartService:
    # 요청 범위의 비동기 DB 세션 주입
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)

    # 접근 토큰이 유효한 고객 번호 반환
    async def _user_id(self, token: str) -> int:
        return (await self.user_service._get_user_from_access_token(token)).id

    # 담긴 상품을 현재 상품명·가격·이미지와 함께 반환(판매 종료 상품은 제외)
    async def _cart_payload(self, user_id: int) -> dict:
        rows = (
            await self.db.execute(
                select(CartItem, Product, ProductCategory.name)
                .join(Product, Product.id == CartItem.product_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .where(
                    CartItem.user_id == user_id,
                    Product.status == "active",
                    Product.visible.is_(True),
                    ProductCategory.is_active.is_(True),
                )
                .order_by(CartItem.created_at, CartItem.id)
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
                    "quantity": item.quantity,
                    "stock": product.stock,
                }
                for item, product, category_name in rows
            ]
        }

    # 동시 요청에도 안전하도록 DB upsert로 수량 합산(최대 99, CHECK 제약 위반 방지를 위해 LEAST 사용)
    async def _upsert(self, user_id: int, product_id: int, quantity: int) -> None:
        statement = insert(CartItem).values(user_id=user_id, product_id=product_id, quantity=quantity)
        await self.db.execute(
            statement.on_conflict_do_update(
                constraint="uq_cart_items_user_product",
                set_={"quantity": func.least(MAX_QUANTITY, statement.excluded.quantity + CartItem.quantity), "updated_at": func.now()},
            ).returning(CartItem.id)
        )

    # 이미 담긴 수량(없으면 0)
    async def _current_quantity(self, user_id: int, product_id: int) -> int:
        quantity = (
            await self.db.execute(select(CartItem.quantity).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
        ).scalar_one_or_none()
        return quantity or 0

    async def get_cart(self, token: str) -> dict:
        return await self._cart_payload(await self._user_id(token))

    # 담긴 수량과 합쳐 재고를 넘으면 409 OUT_OF_STOCK(장바구니는 재고를 잡아 두지 않으므로 최종 확인은 결제 승인 직전 차감)
    async def add_item(self, token: str, request: CartAddRequest) -> dict:
        user_id = await self._user_id(token)
        name, stock = await require_available_product(self.db, request.product_id)
        if await self._current_quantity(user_id, request.product_id) + request.quantity > stock:
            raise out_of_stock_error([{"product_id": request.product_id, "name": name, "available": stock}])
        await self._upsert(user_id, request.product_id, request.quantity)
        await self.db.commit()
        return await self._cart_payload(user_id)

    # 수량 늘리기만 재고로 제한(재고가 줄어 이미 초과한 줄도 줄이는 것은 항상 허용)
    async def set_quantity(self, token: str, product_id: int, quantity: int) -> dict:
        user_id = await self._user_id(token)
        current = await self._current_quantity(user_id, product_id)
        if current and quantity > current:
            product = (await self.db.execute(select(Product.name, Product.stock).where(Product.id == product_id))).one_or_none()
            if product is not None and quantity > product.stock:
                raise out_of_stock_error([{"product_id": product_id, "name": product.name, "available": product.stock}])
        result = await self.db.execute(
            update(CartItem)
            .where(CartItem.user_id == user_id, CartItem.product_id == product_id)
            .values(quantity=quantity, updated_at=func.now())
        )
        if result.rowcount == 0:
            raise api_error(status.HTTP_404_NOT_FOUND, "CART_ITEM_NOT_FOUND", "장바구니에 없는 상품입니다.")
        await self.db.commit()
        return await self._cart_payload(user_id)

    async def remove_items(self, token: str, request: CartRemoveRequest) -> dict:
        user_id = await self._user_id(token)
        await self.db.execute(delete(CartItem).where(CartItem.user_id == user_id, CartItem.product_id.in_(request.product_ids)))
        await self.db.commit()
        return await self._cart_payload(user_id)

    # 비로그인으로 담은 상품을 합치며 판매 중이지 않거나 품절인 상품은 건너뛰고, 합친 수량이 재고를 넘으면 재고만큼으로 줄임
    # 건너뛰거나 줄인 상품은 adjusted로 알려 화면이 안내한다(병합은 로그인 직후 자동 실행이라 오류로 막지 않음)
    async def merge(self, token: str, request: CartMergeRequest) -> dict:
        user_id = await self._user_id(token)
        merged: dict[int, int] = {}
        for item in request.items:
            merged[item.product_id] = min(MAX_QUANTITY, merged.get(item.product_id, 0) + item.quantity)
        adjusted: list[dict] = []
        for product_id, quantity in merged.items():
            try:
                name, stock = await require_available_product(self.db, product_id)
            except HTTPException:  # 판매 중이 아닌 상품은 건너뜀
                continue
            current = await self._current_quantity(user_id, product_id)
            target = min(MAX_QUANTITY, current + quantity)
            if target > stock:
                adjusted.append({"product_id": product_id, "name": name, "available": stock})
                target = max(stock, current)  # 이미 담긴 수량은 줄이지 않고 새로 합치는 양만 재고까지로 제한(품절이면 그대로)
                if target == current:
                    continue
            statement = insert(CartItem).values(user_id=user_id, product_id=product_id, quantity=target)
            await self.db.execute(
                statement.on_conflict_do_update(
                    constraint="uq_cart_items_user_product",
                    set_={"quantity": statement.excluded.quantity, "updated_at": func.now()},
                )
            )
        await self.db.commit()
        return {**await self._cart_payload(user_id), "adjusted": adjusted}

