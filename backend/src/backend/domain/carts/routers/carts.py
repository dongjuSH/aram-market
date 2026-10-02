# 로그인 고객 장바구니 HTTP 엔드포인트

from fastapi import APIRouter, Depends, Path, status

from backend.core.dependencies import require_user_token
from backend.domain.carts.schemas.carts import CartAddRequest, CartMergeRequest, CartQuantityRequest, CartRemoveRequest
from backend.domain.carts.services.carts import CartService
from backend.core.validators import MAX_DB_ID

router = APIRouter(prefix="/cart", tags=["cart"])  # main.py에서 공통 /api 접두사 적용


# 내 장바구니 조회
@router.get("", status_code=status.HTTP_200_OK)
async def get_cart(token: str = Depends(require_user_token), cart_service: CartService = Depends(CartService)):
    return await cart_service.get_cart(token)


# 상품 담기(이미 담긴 상품이면 수량 합산)
@router.post("/items", status_code=status.HTTP_200_OK)
async def add_cart_item(
    request: CartAddRequest,
    token: str = Depends(require_user_token),
    cart_service: CartService = Depends(CartService),
):
    return await cart_service.add_item(token, request)


# 선택한 상품 삭제
@router.delete("/items", status_code=status.HTTP_200_OK)
async def remove_cart_items(
    request: CartRemoveRequest,
    token: str = Depends(require_user_token),
    cart_service: CartService = Depends(CartService),
):
    return await cart_service.remove_items(token, request)


# 담긴 상품 수량 변경
@router.put("/items/{product_id}", status_code=status.HTTP_200_OK)
async def set_cart_item_quantity(
    request: CartQuantityRequest,
    product_id: int = Path(gt=0, le=MAX_DB_ID),
    token: str = Depends(require_user_token),
    cart_service: CartService = Depends(CartService),
):
    return await cart_service.set_quantity(token, product_id, request.quantity)


# 로그인 직후 비로그인 장바구니를 계정 장바구니에 합치기
@router.post("/merge", status_code=status.HTTP_200_OK)
async def merge_cart(
    request: CartMergeRequest,
    token: str = Depends(require_user_token),
    cart_service: CartService = Depends(CartService),
):
    return await cart_service.merge(token, request)
