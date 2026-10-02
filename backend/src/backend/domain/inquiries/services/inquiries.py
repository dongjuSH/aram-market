# 상품 문의 조회·작성·삭제와 관리자 답변 규칙(문의는 로그인 고객 누구나 작성)

from datetime import datetime, timezone

from fastapi import Depends, status
from sqlalchemy import delete, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.admins.services.admins import AdminAccountService
from backend.domain.inquiries.models.inquiries import ProductInquiry
from backend.domain.inquiries.schemas.inquiries import InquiryAnswerRequest, InquiryRequest
from backend.domain.products.models.products import Product
from backend.domain.products.services.availability import require_available_product
from backend.domain.reviews.services.reviews import mask_nickname
from backend.domain.users.models.users import User
from backend.core.errors import api_error
from backend.domain.users.services.users import UserService

SECRET_PLACEHOLDER = "비밀글입니다."


# LIKE 특수문자(%, _, 역슬래시)를 글자 그대로 찾도록 이스케이프
def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# 관리자 문의 검색 조건: 상품명·문의 내용·작성자 닉네임 중 하나라도 포함하면 일치(빈 검색어는 전체)
def admin_search_condition(keyword: str):
    normalized = keyword.strip()
    if not normalized:
        return true()
    pattern = f"%{escape_like(normalized)}%"
    return or_(
        ProductInquiry.content.ilike(pattern, escape="\\"),
        Product.name.ilike(pattern, escape="\\"),
        User.nickname.ilike(pattern, escape="\\"),
    )


# 상품 문의 서비스
class InquiryService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)
        self.admin_service = AdminAccountService(db)

    async def _optional_user_id(self, token: str | None) -> int | None:
        if not token:
            return None
        try:
            return (await self.user_service._get_user_from_access_token(token)).id
        except Exception:
            return None

    # 고객 화면용 직렬화: 비밀글은 작성자 본인에게만 내용과 답변을 보여줌
    @staticmethod
    def _public_item(inquiry: ProductInquiry, nickname: str | None, viewer_id: int | None) -> dict:
        is_mine = viewer_id is not None and inquiry.user_id == viewer_id
        hidden = inquiry.is_secret and not is_mine
        return {
            "id": inquiry.id,
            "content": SECRET_PLACEHOLDER if hidden else inquiry.content,
            "is_secret": inquiry.is_secret,
            "is_mine": is_mine,
            "author": mask_nickname(nickname),
            "created_at": inquiry.created_at.isoformat(),
            "is_answered": inquiry.answer is not None,
            "answer": None if hidden else inquiry.answer,
            "answered_at": None if hidden or inquiry.answered_at is None else inquiry.answered_at.isoformat(),
        }

    async def list_inquiries(self, product_id: int, page: int, page_size: int, token: str | None) -> dict:
        await require_available_product(self.db, product_id)
        viewer_id = await self._optional_user_id(token)
        total = (await self.db.execute(select(func.count()).where(ProductInquiry.product_id == product_id))).scalar_one()
        rows = (
            await self.db.execute(
                select(ProductInquiry, User.nickname)
                .outerjoin(User, User.id == ProductInquiry.user_id)
                .where(ProductInquiry.product_id == product_id)
                .order_by(ProductInquiry.created_at.desc(), ProductInquiry.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return {"items": [self._public_item(inquiry, nickname, viewer_id) for inquiry, nickname in rows], "total": total, "page": page}

    async def create_inquiry(self, product_id: int, token: str, request: InquiryRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        await require_available_product(self.db, product_id)
        inquiry = ProductInquiry(product_id=product_id, user_id=user.id, content=request.content, is_secret=request.is_secret)
        self.db.add(inquiry)
        await self.db.commit()
        return self._public_item(inquiry, user.nickname, user.id)

    # 본인 문의만 삭제(남의 문의는 존재 여부를 드러내지 않도록 404)
    async def delete_inquiry(self, inquiry_id: int, token: str) -> dict:
        user_id = (await self.user_service._get_user_from_access_token(token)).id
        inquiry = await self.db.get(ProductInquiry, inquiry_id)
        if inquiry is None or inquiry.user_id != user_id:
            raise api_error(status.HTTP_404_NOT_FOUND, "INQUIRY_NOT_FOUND", "문의를 찾을 수 없습니다.")
        await self.db.execute(delete(ProductInquiry).where(ProductInquiry.id == inquiry.id))
        await self.db.commit()
        return {"message": "문의를 삭제했습니다."}

    # 관리자용 문의 목록: 답변 대기(오래된 순)·답변 완료(최근 답변 순)와 상품명·내용·닉네임 검색, 탭별 건수
    async def admin_list(self, admin_token: str, inquiry_status: str, keyword: str, page: int, page_size: int) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        is_pending = ProductInquiry.answer.is_(None)
        search = admin_search_condition(keyword)

        def joined(query):
            return query.outerjoin(User, User.id == ProductInquiry.user_id).outerjoin(Product, Product.id == ProductInquiry.product_id).where(search)

        pending_count, answered_count = (
            await self.db.execute(
                joined(
                    select(
                        func.count().filter(is_pending),
                        func.count().filter(ProductInquiry.answer.is_not(None)),
                    ).select_from(ProductInquiry)
                )
            )
        ).one()
        if inquiry_status == "pending":
            condition = is_pending
            order = (ProductInquiry.created_at.asc(), ProductInquiry.id.asc())
            total = pending_count
        else:
            condition = ProductInquiry.answer.is_not(None)
            order = (ProductInquiry.answered_at.desc(), ProductInquiry.id.desc())
            total = answered_count
        rows = (
            await self.db.execute(
                joined(select(ProductInquiry, User.nickname, Product.name))
                .where(condition)
                .order_by(*order)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return {
            "items": [
                {
                    "id": inquiry.id,
                    "product_id": inquiry.product_id,
                    "product_name": product_name,
                    "author": nickname or "탈퇴한 회원",
                    "content": inquiry.content,
                    "is_secret": inquiry.is_secret,
                    "answer": inquiry.answer,
                    "answered_at": inquiry.answered_at.isoformat() if inquiry.answered_at else None,
                    "created_at": inquiry.created_at.isoformat(),
                }
                for inquiry, nickname, product_name in rows
            ],
            "total": total,
            "counts": {"pending": pending_count, "answered": answered_count},
            "page": page,
        }

    # 관리자 답변 등록·수정
    async def admin_answer(self, admin_token: str, inquiry_id: int, request: InquiryAnswerRequest) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        inquiry = await self.db.get(ProductInquiry, inquiry_id)
        if inquiry is None:
            raise api_error(status.HTTP_404_NOT_FOUND, "INQUIRY_NOT_FOUND", "문의를 찾을 수 없습니다.")
        inquiry.answer = request.answer
        inquiry.answered_at = datetime.now(timezone.utc)
        await self.db.commit()
        return {"id": inquiry.id, "answer": inquiry.answer, "answered_at": inquiry.answered_at.isoformat()}
