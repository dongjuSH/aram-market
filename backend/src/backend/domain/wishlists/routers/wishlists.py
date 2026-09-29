# 로그인 고객 찜 목록 HTTP 엔드포인트

from fastapi import APIRouter, Cookie, Depends, Path, status

from backend.domain.users.services.users import api_error
from backend.domain.wishlists.services.wishlists import WishlistService

router = APIRouter(prefix="/wishlist", tags=["wishlist"])  # main.py에서 공통 /api 접두사 적용
USER_ACCESS_COOKIE = "user_access_token"  # 고객 접근 토큰 쿠키 이름


# 찜 API 공통 HttpOnly 쿠키 접근 토큰 확인
def access_token(token: str | None = Cookie(default=None, alias=USER_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 내 찜 목록 조회
@router.get("", status_code=status.HTTP_200_OK)
async def get_wishlist(token: str = Depends(access_token), service: WishlistService = Depends(WishlistService)):
    return await service.get_wishlist(token)


# 상품 찜하기
@router.put("/{product_id}", status_code=status.HTTP_200_OK)
async def add_wishlist_item(
    product_id: int = Path(gt=0),
    token: str = Depends(access_token),
    service: WishlistService = Depends(WishlistService),
):
    return await service.add_item(token, product_id)


# 찜 해제
@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def remove_wishlist_item(
    product_id: int = Path(gt=0),
    token: str = Depends(access_token),
    service: WishlistService = Depends(WishlistService),
):
    return await service.remove_item(token, product_id)
