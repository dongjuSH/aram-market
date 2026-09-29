# SQLAlchemy 모델 기준 누락 DB 테이블 최초 생성

import asyncio

from backend.core.database import Base, engine
from backend.domain.products.models.products import Product, ProductAuditLog, ProductCategory, ProductRelation  # noqa: F401 - 상품 메타데이터 등록
from backend.domain.admins.models.admins import AdminAccount, AdminRefreshToken  # noqa: F401 - 테이블 메타데이터 등록
from backend.domain.carts.models.carts import CartItem  # noqa: F401 - 장바구니 메타데이터 등록
from backend.core.rate_limit import RateLimitEvent  # noqa: F401 - 요청 제한 메타데이터 등록
from backend.domain.orders.models.orders import Order, OrderItem  # noqa: F401 - 주문 메타데이터 등록
from backend.domain.wishlists.models.wishlists import WishlistItem  # noqa: F401 - 찜 메타데이터 등록
from backend.domain.inquiries.models.inquiries import ProductInquiry  # noqa: F401 - 문의 메타데이터 등록
from backend.domain.reviews.models.reviews import ProductReview  # noqa: F401 - 후기 메타데이터 등록
from backend.domain.users.models.users import User, UserPolicyConsent, UserRefreshToken  # noqa: F401 - 고객 계정·약관 동의·리프레시 토큰 메타데이터 등록


# SQLAlchemy 모델 메타데이터 기준 누락 테이블 생성
async def run() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    print("database tables initialized")


if __name__ == "__main__":
    asyncio.run(run())
