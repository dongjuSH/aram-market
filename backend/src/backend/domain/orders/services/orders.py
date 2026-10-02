# 주문 생성·결제 승인·주문 내역 비즈니스 규칙(가격은 항상 서버 상품 가격 기준)

import calendar
import hashlib
import hmac
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.domain.admins.services.admins import AdminAccountService
from backend.domain.carts.models.carts import CartItem
from backend.domain.orders.models.orders import Order, OrderItem
from backend.domain.orders.schemas.orders import DeliveryStatusRequest, OrderConfirmRequest, OrderCreateRequest
from backend.domain.orders.services import toss
from backend.domain.products.models.products import Product, ProductCategory
from backend.domain.products.services.storage import product_storage
from backend.domain.users.models.users import User
from backend.core.errors import api_error
from backend.domain.users.services.users import UserService

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_FAILED = "failed"
DELIVERY_FLOW = ("paid", "preparing", "shipping", "delivered")  # 결제완료 → 상품준비중 → 배송중 → 배송완료
ORDER_PERIOD_MONTHS = (3, 6, 12)  # 고객 주문 목록 조회 기간(개월)
ORDER_HISTORY_MONTHS = 60  # 날짜 직접 지정으로 조회할 수 있는 최대 과거(5년, 전자상거래법 거래기록 보관기간)
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


# 오늘(한국 시간)에서 N개월 전 같은 날 0시(그 달에 같은 날이 없으면 말일), 예: 5월 31일의 3개월 전은 2월 말일
def months_ago_start(months: int, now: datetime | None = None) -> datetime:
    today = (now or datetime.now(timezone.utc)).astimezone(KOREA_TIMEZONE).date()
    month_index = today.year * 12 + today.month - 1 - months
    year, month = divmod(month_index, 12)
    day = min(today.day, calendar.monthrange(year, month + 1)[1])
    return datetime(year, month + 1, day, tzinfo=KOREA_TIMEZONE)


# 조회 기간(개월 버튼 또는 시작일~종료일 직접 지정)을 결제 시각 범위 [이상, 미만)로 변환, 둘 다 없으면 전체 기간
def order_period_range(
    months: int | None, start_date: date | None, end_date: date | None, now: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    if months is not None:
        if start_date or end_date or months not in ORDER_PERIOD_MONTHS:
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_ORDER_PERIOD", "조회 기간은 3개월·6개월·1년 중에서 선택해 주세요.")
        return months_ago_start(months, now), None
    if start_date is None and end_date is None:
        return None, None
    if start_date is None or end_date is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_ORDER_DATE_RANGE", "조회 시작일과 종료일을 모두 선택해 주세요.")
    today = (now or datetime.now(timezone.utc)).astimezone(KOREA_TIMEZONE).date()
    earliest = months_ago_start(ORDER_HISTORY_MONTHS, now).date()
    if start_date > end_date:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_ORDER_DATE_RANGE", "조회 시작일이 종료일보다 늦을 수 없습니다.")
    if start_date < earliest or end_date > today:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_ORDER_DATE_RANGE",
            f"조회 기간은 최근 5년({earliest:%Y.%m.%d}~{today:%Y.%m.%d}) 안에서 선택해 주세요.",
        )
    lower = datetime.combine(start_date, datetime.min.time(), tzinfo=KOREA_TIMEZONE)
    upper = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=KOREA_TIMEZONE)  # 종료일 하루 전체 포함
    return lower, upper


# 고객 주문·결제 서비스(인증은 고객 접근 토큰 검증을 그대로 사용)
class OrderService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)
        self.admin_service = AdminAccountService(db)

    # 결제사에 넘기는 고객 식별키: 회원번호를 그대로 쓰지 않고 서버 비밀키로 만든 추측 불가능한 값
    @staticmethod
    def customer_key(user_id: int) -> str:
        return hmac.new(settings.auth_secret_key.encode(), f"toss-customer|{user_id}".encode(), hashlib.sha256).hexdigest()[:32]

    # 결제사 요구 형식(영숫자·-·_ 6~64자)의 추측하기 어려운 주문번호
    @staticmethod
    def _new_order_number() -> str:
        return f"ARAM-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(6).upper()}"

    # 주문 상품이 판매 중인지 확인하고 현재 가격·이름으로 금액을 계산해 pending 주문 생성
    async def create_order(self, token: str, request: OrderCreateRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        quantities: dict[int, int] = {}
        for line in request.items:
            quantities[line.product_id] = min(99, quantities.get(line.product_id, 0) + line.quantity)

        rows = (
            await self.db.execute(
                select(Product)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .where(
                    Product.id.in_(quantities),
                    Product.status == "active",
                    Product.visible.is_(True),
                    ProductCategory.is_active.is_(True),
                )
            )
        ).scalars().all()
        products = {product.id: product for product in rows}
        unavailable = [product_id for product_id in quantities if product_id not in products]
        if unavailable:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "PRODUCT_NOT_AVAILABLE",
                "판매가 종료되었거나 주문할 수 없는 상품이 포함되어 있습니다. 장바구니를 확인해 주세요.",
                product_ids=unavailable,
            )

        ordered = [(products[product_id], quantity) for product_id, quantity in quantities.items()]
        total = sum(product.price * quantity for product, quantity in ordered)
        first_name = ordered[0][0].name
        order_name = first_name if len(ordered) == 1 else f"{first_name} 외 {len(ordered) - 1}건"
        order = Order(
            order_number=self._new_order_number(),
            user_id=user.id,
            status=STATUS_PENDING,
            order_name=order_name[:100],
            total_amount=total,
            from_cart=request.from_cart,
            recipient_name=request.shipping.recipient_name,
            recipient_phone=request.shipping.recipient_phone,
            postcode=request.shipping.postcode or None,
            address=request.shipping.address,
            address_detail=request.shipping.address_detail or None,
            delivery_memo=request.shipping.delivery_memo or None,
        )
        self.db.add(order)
        await self.db.flush()
        for product, quantity in ordered:
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    image_url=product_storage.public_url(product.image_path),
                    unit_price=product.price,
                    quantity=quantity,
                )
            )
        await self.db.commit()
        return {
            "order_id": order.order_number,
            "order_name": order.order_name,
            "amount": order.total_amount,
            "customer_key": self.customer_key(user.id),
            "customer_name": user.nickname,
            "customer_email": user.email,
        }

    # 결제창 성공 후 서버에서 금액을 대조하고 결제사에 승인을 요청(중복 호출은 이미 승인된 주문을 그대로 반환)
    async def confirm_payment(self, token: str, request: OrderConfirmRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        order = (
            await self.db.execute(
                select(Order).where(Order.order_number == request.order_id, Order.user_id == user.id).with_for_update()
            )
        ).scalar_one_or_none()
        if order is None:
            raise api_error(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")

        if order.status == STATUS_PAID:
            if order.payment_key == request.payment_key:
                return await self._order_payload(order)
            raise api_error(status.HTTP_409_CONFLICT, "ORDER_ALREADY_PAID", "이미 결제가 완료된 주문입니다.")
        if order.status != STATUS_PENDING:
            raise api_error(status.HTTP_409_CONFLICT, "ORDER_NOT_PAYABLE", "결제할 수 없는 주문입니다. 다시 주문해 주세요.")

        if order.total_amount != request.amount:
            order.status = STATUS_FAILED
            order.failure_message = "결제 금액이 주문 금액과 일치하지 않습니다."
            await self.db.commit()
            raise api_error(status.HTTP_400_BAD_REQUEST, "AMOUNT_MISMATCH", "결제 금액이 주문 금액과 일치하지 않아 결제를 취소했습니다.")

        try:
            result = await toss.confirm_payment(request.payment_key, order.order_number, order.total_amount)
        except Exception as error:
            detail = getattr(error, "detail", None)
            if isinstance(detail, dict) and detail.get("code") == "PAYMENT_FAILED":
                order.status = STATUS_FAILED
                order.failure_message = str(detail.get("message"))[:300]
                await self.db.commit()
            raise

        if result.get("status") != "DONE" or int(result.get("totalAmount", -1)) != order.total_amount:
            order.status = STATUS_FAILED
            order.failure_message = "결제 승인 결과가 주문과 일치하지 않습니다."
            await self.db.commit()
            raise api_error(status.HTTP_400_BAD_REQUEST, "PAYMENT_FAILED", "결제 승인 결과를 확인할 수 없습니다. 결제사에 문의해 주세요.")

        order.status = STATUS_PAID
        order.payment_key = request.payment_key
        order.payment_method = str(result.get("method") or "")[:40] or None
        order.paid_at = datetime.now(timezone.utc)
        if order.from_cart:
            product_ids = (await self.db.execute(select(OrderItem.product_id).where(OrderItem.order_id == order.id))).scalars().all()
            await self.db.execute(delete(CartItem).where(CartItem.user_id == user.id, CartItem.product_id.in_(product_ids)))
        await self.db.commit()
        return await self._order_payload(order)

    # 주문 화면용 직렬화(주문 상품은 한 번의 쿼리로 모아 조회해 주문 수만큼 쿼리가 늘어나지 않게 함)
    async def _order_payloads(self, orders: list[Order]) -> list[dict]:
        items_by_order: dict[int, list[OrderItem]] = {order.id: [] for order in orders}
        if orders:
            rows = (
                await self.db.execute(select(OrderItem).where(OrderItem.order_id.in_(items_by_order)).order_by(OrderItem.id))
            ).scalars()
            for item in rows:
                items_by_order[item.order_id].append(item)
        return [
            {
                "order_id": order.order_number,
                "status": order.status,
                "order_name": order.order_name,
                "total_amount": order.total_amount,
                "payment_method": order.payment_method,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "delivery_status": order.delivery_status,
                "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
                "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
                "shipping": {
                    "recipient_name": order.recipient_name,
                    "recipient_phone": order.recipient_phone,
                    "postcode": order.postcode,
                    "address": order.address,
                    "address_detail": order.address_detail,
                    "delivery_memo": order.delivery_memo,
                }
                if order.address
                else None,
                "items": [
                    {
                        "product_id": item.product_id,
                        "name": item.product_name,
                        "image_url": item.image_url,
                        "unit_price": item.unit_price,
                        "quantity": item.quantity,
                    }
                    for item in items_by_order[order.id]
                ],
            }
            for order in orders
        ]

    async def _order_payload(self, order: Order) -> dict:
        return (await self._order_payloads([order]))[0]

    # 결제가 완료된 내 주문을 최신순으로 페이지 단위 반환(기간 버튼 또는 직접 지정한 날짜 안의 결제만)
    async def list_orders(
        self, token: str, months: int | None, start_date: date | None, end_date: date | None, page: int, page_size: int
    ) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        lower, upper = order_period_range(months, start_date, end_date)
        conditions = [Order.user_id == user.id, Order.status == STATUS_PAID]
        if lower is not None:
            conditions.append(Order.paid_at >= lower)
        if upper is not None:
            conditions.append(Order.paid_at < upper)
        total = (await self.db.execute(select(func.count()).select_from(Order).where(*conditions))).scalar_one()
        orders = (
            await self.db.execute(
                select(Order)
                .where(*conditions)
                .order_by(Order.paid_at.desc(), Order.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).scalars().all()
        return {"orders": await self._order_payloads(list(orders)), "total": total, "page": page}

    # 관리자용 결제 완료 주문 목록(배송 상태 필터, 구매자 닉네임 포함)
    async def admin_list(self, admin_token: str, delivery_status: str | None, page: int, page_size: int) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        conditions = [Order.status == STATUS_PAID]
        if delivery_status in DELIVERY_FLOW:
            conditions.append(Order.delivery_status == delivery_status)
        total = (await self.db.execute(select(func.count()).select_from(Order).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(
                select(Order, User.nickname)
                .outerjoin(User, User.id == Order.user_id)
                .where(*conditions)
                .order_by(Order.paid_at.desc(), Order.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        payloads = await self._order_payloads([order for order, _ in rows])
        orders = [{**payload, "buyer": nickname or "탈퇴한 회원"} for payload, (_, nickname) in zip(payloads, rows)]
        return {"orders": orders, "total": total, "page": page}

    # 배송 상태를 한 단계씩만 앞으로 변경(건너뛰기·되돌리기 불가)
    async def admin_update_delivery(self, admin_token: str, order_number: str, request: DeliveryStatusRequest) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        order = (
            await self.db.execute(select(Order).where(Order.order_number == order_number, Order.status == STATUS_PAID).with_for_update())
        ).scalar_one_or_none()
        if order is None:
            raise api_error(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "결제 완료된 주문을 찾을 수 없습니다.")
        if DELIVERY_FLOW.index(request.status) != DELIVERY_FLOW.index(order.delivery_status) + 1:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "INVALID_DELIVERY_TRANSITION",
                "배송 상태는 결제완료 → 상품준비중 → 배송중 → 배송완료 순서로 한 단계씩만 변경할 수 있습니다.",
            )
        order.delivery_status = request.status
        now = datetime.now(timezone.utc)
        if request.status == "shipping":
            order.shipped_at = now
        if request.status == "delivered":
            order.delivered_at = now
        await self.db.commit()
        return await self._order_payload(order)

    # 결제하지 않고 하루가 지난 주문(pending·failed)을 정리
    async def purge_unpaid_orders(self, commit: bool = True) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        result = await self.db.execute(delete(Order).where(Order.status != STATUS_PAID, Order.created_at < cutoff))
        if commit:
            await self.db.commit()
        return result.rowcount or 0

    # 거래기록 보관기간(전자상거래법 5년)이 지난 결제 완료 주문을 삭제(주문 상품은 CASCADE로 함께 삭제)
    # 기준은 고객이 날짜 지정으로 조회할 수 있는 가장 이른 날(한국 시간 5년 전 같은 날 0시)과 같다
    async def purge_expired_orders(self, now: datetime | None = None, commit: bool = True) -> int:
        cutoff = months_ago_start(ORDER_HISTORY_MONTHS, now)
        result = await self.db.execute(delete(Order).where(Order.status == STATUS_PAID, Order.paid_at < cutoff))
        if commit:
            await self.db.commit()
        if result.rowcount:
            logger.info("expired paid orders purged count=%s", result.rowcount)
        return result.rowcount or 0
