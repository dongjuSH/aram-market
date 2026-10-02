# 로그인 고객 주문 생성·결제 승인·주문 내역과 관리자 배송 관리 HTTP 엔드포인트

from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request, status

from backend.core.dependencies import require_admin_token, require_user_token
from backend.core.client_ip import get_client_ip
from backend.core.rate_limit import enforce_limit
from backend.domain.orders.schemas.orders import DeliveryStatusRequest, OrderConfirmRequest, OrderCreateRequest
from backend.domain.orders.services.orders import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])  # main.py에서 공통 /api 접두사 적용
admin_router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])  # 관리자 주문·배송 관리


# 내 결제 완료 주문 목록(조회 기간 3·6·12개월 또는 최근 5년 안의 시작일~종료일, 생략하면 전체 기간 최신순)
@router.get("", status_code=status.HTTP_200_OK)
async def list_orders(
    months: int | None = Query(default=None),  # 3·6·12만 허용(서비스에서 검증)
    start_date: date | None = Query(default=None, alias="from"),  # YYYY-MM-DD, to와 함께 사용
    end_date: date | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=20),
    token: str = Depends(require_user_token),
    service: OrderService = Depends(OrderService),
):
    return await service.list_orders(token, months, start_date, end_date, page, page_size)


# 주문 생성(배송지 포함, 결제창에 넘길 주문번호·금액 반환), 무분별한 pending 주문 생성을 IP당 시간당 30회로 제한
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderCreateRequest,
    http_request: Request,
    token: str = Depends(require_user_token),
    service: OrderService = Depends(OrderService),
):
    await enforce_limit(service.db, "order-create-ip", get_client_ip(http_request), 30, 60 * 60)
    return await service.create_order(token, request)


# 결제창 성공 후 서버 승인
@router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm_payment(
    request: OrderConfirmRequest,
    token: str = Depends(require_user_token),
    service: OrderService = Depends(OrderService),
):
    return await service.confirm_payment(token, request)


# 관리자: 결제 완료 주문 목록(배송 상태 필터)
@admin_router.get("", status_code=status.HTTP_200_OK)
async def admin_list_orders(
    delivery_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    token: str = Depends(require_admin_token),
    service: OrderService = Depends(OrderService),
):
    return await service.admin_list(token, delivery_status, page, page_size)


# 관리자: 배송 상태를 다음 단계로 변경
@admin_router.put("/{order_number}/delivery-status", status_code=status.HTTP_200_OK)
async def admin_update_delivery_status(
    request: DeliveryStatusRequest,
    order_number: str = Path(min_length=6, max_length=64),
    token: str = Depends(require_admin_token),
    service: OrderService = Depends(OrderService),
):
    return await service.admin_update_delivery(token, order_number, request)
