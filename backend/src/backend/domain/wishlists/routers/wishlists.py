# 로그인 고객 찜 목록 HTTP 엔드포인트

from fastapi import APIRouter, Depends, Path, status

from backend.core.dependencies import require_user_token
from backend.domain.wishlists.services.wishlists import WishlistService

router = APIRouter(prefix="/wishlist", tags=["wishlist"])  # main.py에서 공통 /api 접두사 적용


# 내 찜 목록 조회
@router.get("", status_code=status.HTTP_200_OK)
async def get_wishlist(token: str = Depends(require_user_token), service: WishlistService = Depends(WishlistService)):
    return await service.get_wishlist(token)


# 상품 찜하기
@router.put("/{product_id}", status_code=status.HTTP_200_OK)
async def add_wishlist_item(
    product_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: WishlistService = Depends(WishlistService),
):
    return await service.add_item(token, product_id)


# 찜 해제
@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def remove_wishlist_item(
    product_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: WishlistService = Depends(WishlistService),
):
    return await service.remove_item(token, product_id)
