# 상품 후기 HTTP 엔드포인트(목록은 누구나, 작성·수정·삭제는 로그인 고객)

from fastapi import APIRouter, Depends, Path, Query, Request, status

from backend.core.dependencies import optional_user_token, require_user_token
from backend.core.client_ip import get_client_ip
from backend.core.rate_limit import enforce_limit
from backend.domain.reviews.schemas.reviews import ReviewRequest
from backend.domain.reviews.services.reviews import ReviewService
from backend.core.validators import MAX_DB_ID

router = APIRouter(tags=["reviews"])  # main.py에서 공통 /api 접두사 적용


# 후기 목록과 평점 요약
@router.get("/products/{product_id}/reviews")
async def list_reviews(
    product_id: int = Path(gt=0, le=MAX_DB_ID),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=20),
    token: str | None = Depends(optional_user_token),
    service: ReviewService = Depends(ReviewService),
):
    return await service.list_reviews(product_id, page, page_size, token)


# 내가 이 상품의 후기를 작성할 수 있는지 확인
@router.get("/products/{product_id}/reviews/eligibility")
async def review_eligibility(
    product_id: int = Path(gt=0, le=MAX_DB_ID),
    token: str = Depends(require_user_token),
    service: ReviewService = Depends(ReviewService),
):
    return await service.eligibility(product_id, token)


# 후기 작성(구매 고객만)
@router.post("/products/{product_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_review(
    request: ReviewRequest,
    http_request: Request,
    product_id: int = Path(gt=0, le=MAX_DB_ID),
    token: str = Depends(require_user_token),
    service: ReviewService = Depends(ReviewService),
):
    await enforce_limit(service.db, "review-write-ip", get_client_ip(http_request), 20, 60 * 60)
    return await service.create_review(product_id, token, request)


# 내 후기 수정
@router.put("/reviews/{review_id}")
async def update_review(
    request: ReviewRequest,
    review_id: int = Path(gt=0, le=MAX_DB_ID),
    token: str = Depends(require_user_token),
    service: ReviewService = Depends(ReviewService),
):
    return await service.update_review(review_id, token, request)


# 내 후기 삭제
@router.delete("/reviews/{review_id}")
async def delete_review(
    review_id: int = Path(gt=0, le=MAX_DB_ID),
    token: str = Depends(require_user_token),
    service: ReviewService = Depends(ReviewService),
):
    return await service.delete_review(review_id, token)
