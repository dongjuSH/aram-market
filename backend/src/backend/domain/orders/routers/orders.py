# 로그인 고객 주문 생성·결제 승인·주문 내역과 관리자 배송 관리 HTTP 엔드포인트

from fastapi import APIRouter, Cookie, Depends, Path, Query, Request, status

from backend.core.client_ip import get_client_ip
from backend.core.rate_limit import enforce_limit
from backend.domain.orders.schemas.orders import DeliveryStatusRequest, OrderConfirmRequest, OrderCreateRequest
from backend.domain.orders.services.orders import OrderService
from backend.domain.users.services.users import api_error

router = APIRouter(prefix="/orders", tags=["orders"])  # main.py에서 공통 /api 접두사 적용
admin_router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])  # 관리자 주문·배송 관리
USER_ACCESS_COOKIE = "user_access_token"  # 고객 접근 토큰 쿠키 이름
ADMIN_ACCESS_COOKIE = "admin_access_token"  # 관리자 접근 토큰 쿠키 이름


# 주문 API 공통 HttpOnly 쿠키 접근 토큰 확인
def access_token(token: str | None = Cookie(default=None, alias=USER_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 관리자 API의 쿠키 접근 토큰 확인
def admin_token(token: str | None = Cookie(default=None, alias=ADMIN_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 내 결제 완료 주문 목록
@router.get("", status_code=status.HTTP_200_OK)
async def list_orders(token: str = Depends(access_token), service: OrderService = Depends(OrderService)):
    return await service.list_orders(token)


# 주문 생성(배송지 포함, 결제창에 넘길 주문번호·금액 반환), 무분별한 pending 주문 생성을 IP당 시간당 30회로 제한
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderCreateRequest,
    http_request: Request,
    token: str = Depends(access_token),
    service: OrderService = Depends(OrderService),
):
    await enforce_limit(service.db, "order-create-ip", get_client_ip(http_request), 30, 60 * 60)
    return await service.create_order(token, request)


# 결제창 성공 후 서버 승인
@router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm_payment(
    request: OrderConfirmRequest,
    token: str = Depends(access_token),
    service: OrderService = Depends(OrderService),
):
    return await service.confirm_payment(token, request)


# 관리자: 결제 완료 주문 목록(배송 상태 필터)
@admin_router.get("", status_code=status.HTTP_200_OK)
async def admin_list_orders(
    delivery_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    token: str = Depends(admin_token),
    service: OrderService = Depends(OrderService),
):
    return await service.admin_list(token, delivery_status, page, page_size)


# 관리자: 배송 상태를 다음 단계로 변경
@admin_router.put("/{order_number}/delivery-status", status_code=status.HTTP_200_OK)
async def admin_update_delivery_status(
    request: DeliveryStatusRequest,
    order_number: str = Path(min_length=6, max_length=64),
    token: str = Depends(admin_token),
    service: OrderService = Depends(OrderService),
):
    return await service.admin_update_delivery(token, order_number, request)
