# FastAPI 앱, CORS, DB 생명주기 및 도메인 라우터 조립

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 터미널·VS Code 실행 방식에 따른 import 차이 방지용 backend/src 경로 추가
BACKEND_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = BACKEND_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from backend.core.config import settings
from backend.core.database import Base, async_session, engine
from backend.core.problems import http_exception_handler, unhandled_exception_handler, validation_exception_handler
from backend.core.rate_limit import RateLimitEvent, purge_rate_limit_events  # noqa: F401 - 요청 제한 테이블 메타데이터 등록
from backend.domain.products.models.products import Product, ProductAuditLog, ProductCategory, ProductRelation
from backend.domain.admins.models.admins import AdminAccount, AdminRefreshToken  # noqa: F401 - 관리자 리프레시 토큰 메타데이터 등록
from backend.domain.admins.routers.admins import router as admin_router
from backend.domain.admins.services.admins import AdminAccountService
from backend.domain.inquiries.models.inquiries import ProductInquiry  # noqa: F401 - 문의 테이블 메타데이터 등록
from backend.domain.inquiries.routers.inquiries import router as inquiry_router
from backend.domain.reviews.models.reviews import ProductReview  # noqa: F401 - 후기 테이블 메타데이터 등록
from backend.domain.reviews.routers.reviews import router as review_router
from backend.domain.orders.models.orders import Order, OrderItem  # noqa: F401 - 주문 테이블 메타데이터 등록
from backend.domain.orders.routers.orders import admin_router as admin_order_router, router as order_router
from backend.domain.orders.services.orders import OrderService
from backend.domain.wishlists.models.wishlists import WishlistItem  # noqa: F401 - 찜 테이블 메타데이터 등록
from backend.domain.wishlists.routers.wishlists import router as wishlist_router
from backend.domain.carts.models.carts import CartItem  # noqa: F401 - 장바구니 테이블 메타데이터 등록
from backend.domain.carts.routers.carts import router as cart_router
from backend.domain.users.models.users import User, UserPolicyConsent, UserRefreshToken  # noqa: F401 - 약관 동의·리프레시 토큰 테이블 메타데이터 등록
from backend.domain.users.routers.users import router as user_router
from backend.domain.users.services.users import UserService
from backend.domain.products.routers.catalog import router as catalog_router
from backend.domain.products.routers.products import router as admin_product_router
from backend.domain.products.services.storage import product_storage


DEFAULT_PRODUCT_CATEGORIES = (
    ("food", "식품"),
    ("fashion", "패션·의류"),
    ("beauty", "뷰티"),
    ("digital", "디지털·가전"),
    ("home", "생활·주방"),
    ("furniture", "가구·인테리어"),
    ("sports", "스포츠·레저"),
    ("kids", "유아·완구"),
    ("books", "도서·교육"),
    ("pet", "반려동물"),
)

logger = logging.getLogger(__name__)
USER_PURGE_INTERVAL_SECONDS = 60 * 60


# 서버가 여러 대여도 한 번에 하나만 정리하도록 Postgres advisory lock에 쓰는 고정 번호
CLEANUP_LOCK_KEY = 7_204_531_001


# 정리 작업 1회: 잠금을 얻은 서버만 만료 계정·토큰·요청 기록을 한 트랜잭션으로 삭제(못 얻으면 다른 서버가 실행 중이므로 건너뜀)
async def run_cleanup_once() -> None:
    async with async_session() as session:
        # 트랜잭션이 끝나면 자동 해제되는 잠금이라 Supabase Pooler(트랜잭션 모드)에서도 안전
        locked = (await session.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": CLEANUP_LOCK_KEY})).scalar_one()
        if not locked:
            return
        user_service = UserService(session)
        await user_service.purge_expired_accounts(commit=False)
        await user_service.purge_expired_refresh_tokens(commit=False)
        await AdminAccountService(session).purge_expired_refresh_tokens(commit=False)
        await purge_rate_limit_events(session, commit=False)
        await OrderService(session).purge_unpaid_orders(commit=False)
        await session.commit()


# 서버가 켜져 있는 동안 매시간 정리 작업 실행
async def purge_expired_user_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await run_cleanup_once()
        except Exception:
            logger.exception("periodic cleanup failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=USER_PURGE_INTERVAL_SECONDS)
        except TimeoutError:
            pass


# 서버 시작 시 누락 테이블 생성 및 종료 시 DB 엔진 정리
@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app  # FastAPI 생명주기 시그니처 유지용 인자
    async with engine.begin() as conn:
        # Supabase에 누락된 관리자 계정·상품 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        existing_codes = set((await session.execute(select(ProductCategory.code))).scalars().all())
        for sort_order, (code, name) in enumerate(DEFAULT_PRODUCT_CATEGORIES, start=1):
            if code not in existing_codes:
                session.add(ProductCategory(code=code, name=name, sort_order=sort_order, is_active=True))
        await session.commit()
    await product_storage.ensure_bucket()
    purge_stop_event = asyncio.Event()
    purge_task = asyncio.create_task(purge_expired_user_loop(purge_stop_event))
    try:
        yield
    finally:
        purge_stop_event.set()
        await purge_task
        await engine.dispose()


# FastAPI 인스턴스 생성
app = FastAPI(
    title="상품 관리 관리자 API",
    description="단일 관리자 상품 관리와 고객용 공개 상품 조회 API입니다.",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# 모든 오류 응답을 RFC 9457 Problem Details 형식으로 통일
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# CORS 및 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            settings.frontend_url.rstrip("/"),
        }
    ),
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST 등 모든 요청 방식 허용
    allow_headers=["*"],  # 모든 통신 헤더 허용
)


# 서버 실행 상태 확인용 기본 헬스 체크 엔드포인트
@app.get("/")
def read_root():
    return {"message": "hello world"}


# 라우터 등록
# 모든 도메인 라우터의 공통 API 접두사
app.include_router(admin_router, prefix="/api")
app.include_router(admin_product_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(cart_router, prefix="/api")
app.include_router(wishlist_router, prefix="/api")
app.include_router(order_router, prefix="/api")
app.include_router(admin_order_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(inquiry_router, prefix="/api")
