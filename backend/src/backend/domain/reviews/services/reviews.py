# 상품 후기 조회·작성·수정·삭제 규칙(후기는 해당 상품을 결제 완료한 고객만 작성)

from datetime import datetime, timedelta, timezone

from fastapi import Depends, status
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.orders.models.orders import Order, OrderItem
from backend.domain.products.services.availability import require_available_product
from backend.domain.reviews.models.reviews import ProductReview
from backend.domain.reviews.schemas.reviews import ReviewRequest
from backend.domain.users.models.users import User
from backend.domain.users.services.users import UserService, api_error


# 닉네임 첫 글자만 보이고 나머지는 가림(예: 홍길동 → 홍**)
def mask_nickname(nickname: str | None) -> str:
    if not nickname:
        return "탈퇴한 회원"
    return nickname[:1] + "*" * max(1, len(nickname) - 1)


# 상품 후기 서비스
class ReviewService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)

    # 로그인 쿠키가 없거나 만료돼도 목록 조회는 가능해야 하므로 실패하면 비로그인으로 취급
    async def _optional_user_id(self, token: str | None) -> int | None:
        if not token:
            return None
        try:
            return (await self.user_service._get_user_from_access_token(token)).id
        except Exception:
            return None

    # 결제 완료 주문에 이 상품이 있는 고객인지 확인
    async def _has_purchased(self, user_id: int, product_id: int) -> bool:
        return bool(
            (
                await self.db.execute(
                    select(
                        exists().where(
                            Order.user_id == user_id,
                            Order.status == "paid",
                            OrderItem.order_id == Order.id,
                            OrderItem.product_id == product_id,
                        )
                    )
                )
            ).scalar()
        )

    async def _existing_review(self, user_id: int, product_id: int) -> ProductReview | None:
        return (
            await self.db.execute(select(ProductReview).where(ProductReview.user_id == user_id, ProductReview.product_id == product_id))
        ).scalar_one_or_none()

    # 후기 개수·평균·최근 6개월 평균
    async def _summary(self, product_id: int) -> dict:
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=183)
        count, average, recent = (
            await self.db.execute(
                select(
                    func.count(),
                    func.avg(ProductReview.rating),
                    func.avg(ProductReview.rating).filter(ProductReview.created_at >= six_months_ago),
                ).where(ProductReview.product_id == product_id)
            )
        ).one()
        return {
            "count": count,
            "average": round(float(average), 1) if average is not None else None,
            "recent_average": round(float(recent), 2) if recent is not None else None,
        }

    @staticmethod
    def _item(review: ProductReview, nickname: str | None, viewer_id: int | None) -> dict:
        return {
            "id": review.id,
            "rating": review.rating,
            "content": review.content,
            "author": mask_nickname(nickname),
            "created_at": review.created_at.isoformat(),
            "is_mine": viewer_id is not None and review.user_id == viewer_id,
        }

    # 후기 목록(최신순)과 요약. 내 후기는 is_mine으로 표시
    async def list_reviews(self, product_id: int, page: int, page_size: int, token: str | None) -> dict:
        await require_available_product(self.db, product_id)
        viewer_id = await self._optional_user_id(token)
        rows = (
            await self.db.execute(
                select(ProductReview, User.nickname)
                .outerjoin(User, User.id == ProductReview.user_id)
                .where(ProductReview.product_id == product_id)
                .order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        summary = await self._summary(product_id)
        return {"summary": summary, "items": [self._item(review, nickname, viewer_id) for review, nickname in rows], "total": summary["count"], "page": page}

    # 내가 이 상품에 후기를 쓸 수 있는지(구매 여부·작성 여부) 안내
    async def eligibility(self, product_id: int, token: str) -> dict:
        user_id = (await self.user_service._get_user_from_access_token(token)).id
        await require_available_product(self.db, product_id)
        existing = await self._existing_review(user_id, product_id)
        if existing:
            return {"can_review": False, "reason": "already_reviewed", "review_id": existing.id, "rating": existing.rating, "content": existing.content}
        purchased = await self._has_purchased(user_id, product_id)
        return {"can_review": purchased, "reason": "ok" if purchased else "not_purchased", "review_id": None}

    async def create_review(self, product_id: int, token: str, request: ReviewRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        await require_available_product(self.db, product_id)
        if not await self._has_purchased(user.id, product_id):
            raise api_error(status.HTTP_403_FORBIDDEN, "REVIEW_NOT_PURCHASED", "상품을 구매한 고객만 후기를 작성할 수 있어요.")
        if await self._existing_review(user.id, product_id):
            raise api_error(status.HTTP_409_CONFLICT, "REVIEW_ALREADY_EXISTS", "이미 이 상품의 후기를 작성했어요. 기존 후기를 수정해 주세요.")
        review = ProductReview(product_id=product_id, user_id=user.id, rating=request.rating, content=request.content)
        self.db.add(review)
        await self.db.commit()
        return self._item(review, user.nickname, user.id)

    # 본인 후기만 수정·삭제할 수 있음(남의 후기는 존재 여부도 드러내지 않도록 404)
    async def _own_review(self, review_id: int, user_id: int) -> ProductReview:
        review = await self.db.get(ProductReview, review_id)
        if review is None or review.user_id != user_id:
            raise api_error(status.HTTP_404_NOT_FOUND, "REVIEW_NOT_FOUND", "후기를 찾을 수 없습니다.")
        return review

    async def update_review(self, review_id: int, token: str, request: ReviewRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        review = await self._own_review(review_id, user.id)
        review.rating = request.rating
        review.content = request.content
        review.updated_at = func.now()
        await self.db.commit()
        await self.db.refresh(review)
        return self._item(review, user.nickname, user.id)

    async def delete_review(self, review_id: int, token: str) -> dict:
        user_id = (await self.user_service._get_user_from_access_token(token)).id
        review = await self._own_review(review_id, user_id)
        await self.db.execute(delete(ProductReview).where(ProductReview.id == review.id))
        await self.db.commit()
        return {"message": "후기를 삭제했습니다."}
