# 주문 생성·결제 승인·주문 내역 비즈니스 규칙(가격은 항상 서버 상품 가격 기준)

import calendar
import hashlib
import hmac
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, delete, func, or_, select
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
from backend.core.validators import MAX_ORDER_PAYMENT_AMOUNT, MIN_CARD_PAYMENT_AMOUNT
from backend.domain.users.services.users import UserService

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_FAILED = "failed"
UNPAID_STATUSES = (STATUS_PENDING, STATUS_FAILED)  # 결제가 확정되지 않은 주문(결제 보정·미결제 정리 대상)
# 고객·관리자 주문 목록에 보이는 거래 기록(결제 완료, 환불 확인 중, 환불 완료)
SETTLED_STATUSES = (STATUS_PAID, "refunding", "refunded")
TOSS_UNPAID_STATUSES = {"ABORTED", "EXPIRED", "CANCELED"}  # 결제사 조회 결과 돈이 남아 있지 않은 상태(미결제·만료·전액 취소)
TOSS_NOT_FINAL_STATUSES = {"READY", "IN_PROGRESS"}  # 아직 승인 전 단계(시간이 지나면 만료로 바뀌므로 다음 주기에 다시 확인)
# 4xx여도 결제가 이미 승인됐거나 처리 중일 수 있어 실패로 확정하면 안 되는 토스 오류 코드
TOSS_UNCERTAIN_CODES = {
    "IDEMPOTENT_REQUEST_PROCESSING",  # 같은 멱등 키의 첫 요청이 아직 처리 중
    "ALREADY_PROCESSING_REQUEST",  # 승인 API가 돌려주는 "이미 처리 중" 오류
    "ALREADY_PROCESSED_PAYMENT",  # 이미 승인된 결제(첫 응답을 받지 못한 경우)
    "ALREADY_COMPLETED_PAYMENT",  # 완료된 결제를 다시 처리한 경우
    "PROVIDER_ERROR",
    "FAILED_PAYMENT_INTERNAL_SYSTEM_PROCESSING",
    "FAILED_INTERNAL_SYSTEM_PROCESSING",
    "UNKNOWN_PAYMENT_ERROR",
}
RECONCILE_AFTER = timedelta(minutes=10)  # 승인 요청 후 이 시간이 지나도 결과가 저장되지 않은 주문을 결제사에 조회
NOT_FOUND_FINAL_AFTER = timedelta(days=1)  # 조회 404는 승인 직후 일시 상태일 수 있어 승인 시도 하루 뒤부터만 미결제로 확정
DELIVERY_FLOW = ("paid", "preparing", "shipping", "delivered")  # 결제완료 → 상품준비중 → 배송중 → 배송완료
ORDER_PERIOD_MONTHS = (3, 6, 12)  # 고객 주문 목록 조회 기간(개월)
ORDER_HISTORY_MONTHS = 60  # 날짜 직접 지정으로 조회할 수 있는 최대 과거(5년, 전자상거래법 거래기록 보관기간)
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


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


# 토스 승인 오류가 "결제되지 않았음"이 확실한 거절인지(409·429·5xx·처리 중 코드는 결과를 알 수 없음)
def is_definitive_rejection(detail: dict) -> bool:
    gateway_status = detail.get("gateway_status")
    gateway_code = detail.get("gateway_code")
    return (
        isinstance(gateway_status, int)
        and 400 <= gateway_status < 500
        and gateway_status not in (409, 429)
        and bool(gateway_code)  # 오류 코드조차 읽지 못한 응답(깨진 본문 등)은 결과를 알 수 없음
        and gateway_code not in TOSS_UNCERTAIN_CODES
    )


# 결제사 결과가 이 주문의 승인 완료와 정확히 일치하는지(상태·주문번호·결제키·금액 모두 확인)
def payment_matches(order: Order, payment: dict | None, payment_key: str) -> bool:
    if not payment or payment.get("status") != "DONE":
        return False
    try:
        amount = int(payment.get("totalAmount", -1))
    except (TypeError, ValueError):
        return False
    return payment.get("orderId") == order.order_number and payment.get("paymentKey") == payment_key and amount == order.total_amount


# 현재 제공하는 카드 결제 범위를 벗어난 주문은 결제창을 열기 전에 거부
def ensure_supported_order_amount(total: int) -> None:
    if not MIN_CARD_PAYMENT_AMOUNT <= total <= MAX_ORDER_PAYMENT_AMOUNT:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "ORDER_AMOUNT_NOT_SUPPORTED",
            f"주문 금액은 {MIN_CARD_PAYMENT_AMOUNT:,}원 이상 {MAX_ORDER_PAYMENT_AMOUNT:,}원 이하만 결제할 수 있습니다.",
        )


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
        ensure_supported_order_amount(total)
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
                try:
                    payload = await self._order_payload(order)
                    await self.db.commit()  # 조회 중 유지한 주문 행 잠금 해제
                    return payload
                except Exception as error:
                    await self._rollback_payment_settlement(order.order_number)
                    raise self._payment_confirmation_pending_error() from error
            raise api_error(status.HTTP_409_CONFLICT, "ORDER_ALREADY_PAID", "이미 결제가 완료된 주문입니다.")
        if order.status in SETTLED_STATUSES and order.payment_key == request.payment_key:
            # 결제 후 환불된 주문의 결제 결과 화면을 새로고침한 경우: 다시 승인하지 않고 현재 주문을 그대로 보여 줌
            payload = await self._order_payload(order)
            await self.db.commit()
            return payload
        if order.status != STATUS_PENDING:
            raise api_error(status.HTTP_409_CONFLICT, "ORDER_NOT_PAYABLE", "결제할 수 없는 주문입니다. 다시 주문해 주세요.")
        if order.payment_key and order.payment_key != request.payment_key:
            raise api_error(status.HTTP_409_CONFLICT, "PAYMENT_KEY_MISMATCH", "이미 다른 결제로 승인 요청된 주문입니다.")

        if order.total_amount != request.amount:
            order.status = STATUS_FAILED
            order.failure_message = "결제 금액이 주문 금액과 일치하지 않습니다."
            await self.db.commit()
            raise api_error(status.HTTP_400_BAD_REQUEST, "AMOUNT_MISMATCH", "결제 금액이 주문 금액과 일치하지 않아 결제를 취소했습니다.")

        # 승인 응답을 받기 전에 끊겨도 정리 작업이 결제사에 조회할 수 있도록 결제키를 먼저 저장하고,
        # 결제사 응답(최대 15초)을 기다리는 동안 주문 행 잠금을 쥐고 있지 않도록 여기서 커밋(재시도여도 커밋)
        # 동시에 같은 승인 요청이 와도 결제사는 주문번호 멱등 키로 한 번만 승인한다
        if order.payment_key is None:
            order.payment_key = request.payment_key
            order.payment_attempted_at = datetime.now(timezone.utc)
        elif order.payment_attempted_at is None:
            # 030 적용 전 저장된 결제키나 배포 전후 경계 요청도 주문 생성 시각으로 즉시 정리하지 않도록 보정
            order.payment_attempted_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            result = await toss.confirm_payment(request.payment_key, order.order_number, order.total_amount)
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {}
            if detail.get("code") == "PAYMENT_NOT_CONFIGURED":
                raise
            if detail.get("code") == "PAYMENT_FAILED" and is_definitive_rejection(detail):
                # 카드 거절 등 확정 실패만 failed(결제키는 남겨 정리 작업이 결제사에서 한 번 더 확인한 뒤 삭제)
                order.status = STATUS_FAILED
                order.failure_message = str(detail.get("message"))[:300]
                await self.db.commit()
                raise
            # 처리 중·이미 처리됨·5xx·연결 실패 등 결과를 알 수 없으면 실패로 확정하지 않고 바로 조회해 확인
            return await self._settle_uncertain_payment(order, request.payment_key)
        except Exception:
            # 예상하지 못한 오류도 승인 여부를 알 수 없으므로 실패 화면 대신 결제사 조회로 확인
            logger.exception("unexpected error during payment confirm order=%s", order.order_number)
            return await self._settle_uncertain_payment(order, request.payment_key)

        if not payment_matches(order, result, request.payment_key):
            logger.error("payment confirm response does not match order order=%s status=%s", order.order_number, result.get("status"))
            return await self._settle_uncertain_payment(order, request.payment_key)

        return await self._finalize_confirmed_payment(order.id, request.payment_key, result)

    # 승인 결과를 알 수 없을 때 결제사에 바로 조회: 승인됐으면 완료 처리, 아니면 pending으로 두고 정리 작업이 다시 확인
    async def _settle_uncertain_payment(self, order: Order, payment_key: str) -> dict:
        try:
            payment = await toss.get_payment(payment_key)
        except Exception:
            logger.warning("payment lookup after uncertain confirm failed order=%s", order.order_number, exc_info=True)
            payment = None
        if payment_matches(order, payment, payment_key):
            return await self._finalize_confirmed_payment(order.id, payment_key, payment)
        raise self._payment_confirmation_pending_error()

    # 결제사가 승인 완료를 확인한 뒤 주문을 다시 잠가 최신 상태에 반영하고, 커밋까지 끝난 경우에만 성공 응답
    async def _finalize_confirmed_payment(self, order_id: int, payment_key: str, payment: dict) -> dict:
        order_number = str(payment.get("orderId") or order_id)
        try:
            order = (
                await self.db.execute(
                    select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if order is None or not payment_matches(order, payment, payment_key):
                raise RuntimeError("confirmed payment no longer matches the order")
            order_number = order.order_number
            if order.status not in (STATUS_PENDING, STATUS_FAILED, STATUS_PAID):
                raise RuntimeError("confirmed payment has an unsupported local order status")
            if order.payment_key not in (None, payment_key):
                raise RuntimeError("confirmed payment key conflicts with the current order")

            # 외부 호출 중 정리 작업이 결제키를 비웠더라도 승인 결과와 주문 정보가 모두 일치하면 복원
            order.payment_key = payment_key
            if order.payment_attempted_at is None:
                order.payment_attempted_at = datetime.now(timezone.utc)
            if order.status != STATUS_PAID:
                await self._mark_paid(order, payment)
            payload = await self._order_payload(order)
            await self.db.commit()
            return payload
        except Exception as error:
            await self._rollback_payment_settlement(order_number)
            raise self._payment_confirmation_pending_error() from error

    # 승인 완료의 로컬 반영 실패는 결제 실패로 표시하지 않고 Sentry 기록 후 정리 작업·재확인 대상으로 남김
    async def _rollback_payment_settlement(self, order_number: str) -> None:
        try:
            await self.db.rollback()
        except Exception:
            logger.error("payment settlement rollback failed order=%s", order_number, exc_info=True)
        logger.error("confirmed payment could not be persisted order=%s", order_number, exc_info=True)

    @staticmethod
    def _payment_confirmation_pending_error() -> HTTPException:
        return api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PAYMENT_CONFIRMATION_PENDING",
            "결제 결과를 확인하고 있습니다. 잠시 후 이 화면에서 다시 확인해 주세요. 결과가 확정될 때까지 다시 주문하지 마세요.",
        )

    # 결제 완료 처리: 상태·결제 수단·승인 시각 기록, 장바구니 주문이면 해당 상품을 장바구니에서 제거
    async def _mark_paid(self, order: Order, payment: dict) -> None:
        order.status = STATUS_PAID
        order.failure_message = None
        order.payment_method = str(payment.get("method") or "")[:40] or None
        try:
            order.paid_at = datetime.fromisoformat(str(payment["approvedAt"]))
        except (KeyError, ValueError):
            order.paid_at = datetime.now(timezone.utc)
        if order.from_cart and order.user_id is not None:
            product_ids = (await self.db.execute(select(OrderItem.product_id).where(OrderItem.order_id == order.id))).scalars().all()
            await self.db.execute(delete(CartItem).where(CartItem.user_id == order.user_id, CartItem.product_id.in_(product_ids)))

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
                "cancel_request": {
                    "status": order.cancel_request_status,
                    "requested_at": _iso(order.cancel_requested_at),
                    "reason_code": order.cancel_request_reason_code,
                    "reason_detail": order.cancel_request_reason_detail,
                    "rejected_at": _iso(order.cancel_rejected_at),
                    "reject_reason": order.cancel_reject_reason,
                }
                if order.cancel_request_status
                else None,
                "refund": {
                    "actor": order.refund_actor,
                    "reason_code": order.refund_reason_code,
                    "reason_detail": order.refund_reason_detail,
                    "attempted_at": _iso(order.refund_attempted_at),
                    "refunded_at": _iso(order.refunded_at),
                    "failure_message": order.refund_failure_message,
                }
                if order.refund_attempt_count
                else None,
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

    # 관리자 화면용 직렬화(구매자 닉네임 포함, 탈퇴로 회원이 없으면 '탈퇴한 회원')
    async def _admin_payloads(self, orders: list[Order]) -> list[dict]:
        user_ids = {order.user_id for order in orders if order.user_id is not None}
        nicknames = {}
        if user_ids:
            nicknames = dict((await self.db.execute(select(User.id, User.nickname).where(User.id.in_(user_ids)))).all())
        payloads = await self._order_payloads(orders)
        return [
            {**payload, "buyer": nicknames.get(order.user_id) or "탈퇴한 회원"}
            for payload, order in zip(payloads, orders, strict=True)
        ]

    # 결제가 완료된 내 주문(환불 확인 중·환불 완료 포함)을 최신순으로 페이지 단위 반환(기간 버튼 또는 직접 지정한 날짜 안의 결제만)
    async def list_orders(
        self, token: str, months: int | None, start_date: date | None, end_date: date | None, page: int, page_size: int
    ) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        lower, upper = order_period_range(months, start_date, end_date)
        conditions = [Order.user_id == user.id, Order.status.in_(SETTLED_STATUSES)]
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

    # 관리자용 주문 목록(구매자 닉네임 포함). 전체는 결제 완료·환불 주문, 배송 단계 탭은 결제 완료 주문만,
    # 취소 요청 탭은 대기 중인 요청(오래된 요청부터), 환불 탭은 환불 확인 중·완료 주문
    async def admin_list(
        self, admin_token: str, delivery_status: str | None, page: int, page_size: int, view: str | None = None
    ) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        conditions = [Order.status.in_(SETTLED_STATUSES)]
        order_by = (Order.paid_at.desc(), Order.id.desc())
        if view == "cancel_requested":
            conditions = [Order.status == STATUS_PAID, Order.cancel_request_status == "requested"]
            order_by = (Order.cancel_requested_at.asc(), Order.id.asc())
        elif view == "refunded":
            conditions = [Order.status.in_(("refunding", "refunded"))]
            order_by = (Order.refund_attempted_at.desc(), Order.id.desc())
        elif delivery_status in DELIVERY_FLOW:
            conditions = [Order.status == STATUS_PAID, Order.delivery_status == delivery_status]
        total = (await self.db.execute(select(func.count()).select_from(Order).where(*conditions))).scalar_one()
        orders = (
            await self.db.execute(select(Order).where(*conditions).order_by(*order_by).limit(page_size).offset((page - 1) * page_size))
        ).scalars().all()
        return {"orders": await self._admin_payloads(list(orders)), "total": total, "page": page}

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
        if request.status == "shipping" and order.cancel_request_status == "requested":
            raise api_error(
                status.HTTP_409_CONFLICT,
                "CANCEL_REQUEST_PENDING",
                "고객의 취소 요청을 먼저 승인하거나 거절해야 배송중으로 변경할 수 있습니다.",
            )
        order.delivery_status = request.status
        now = datetime.now(timezone.utc)
        if request.status == "shipping":
            order.shipped_at = now
        if request.status == "delivered":
            order.delivered_at = now
        payload = (await self._admin_payloads([order]))[0]
        await self.db.commit()
        return payload

    # 결제사 확인이 필요한 주문(승인 요청 후 10분이 지났는데 결제키가 남은 pending·failed)의 번호와 결제키(짧은 조회만, 잠금 없음)
    async def reconcile_candidates(self, now: datetime | None = None) -> list[tuple[int, str]]:
        cutoff = (now or datetime.now(timezone.utc)) - RECONCILE_AFTER
        rows = (
            await self.db.execute(
                select(Order.id, Order.payment_key).where(
                    Order.status.in_(UNPAID_STATUSES),
                    Order.payment_key.is_not(None),
                    Order.payment_attempted_at.is_not(None),
                    Order.payment_attempted_at < cutoff,
                )
            )
        ).all()
        return [(order_id, payment_key) for order_id, payment_key in rows]

    # 결제사 조회 결과를 주문 한 건에 짧은 트랜잭션으로 반영(조회 중 다른 요청이 바꿨으면 건너뜀)
    # 승인 완료면 paid, 미결제·만료·전액 취소·결제 없음이면 failed로 두고 결제키를 지워 삭제 대상으로, 그 밖의 상태는 남겨 둠
    async def apply_payment_lookup(self, order_id: int, payment_key: str, payment: dict | None) -> None:
        order = (await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())).scalar_one_or_none()
        # 결제 완료·환불 주문은 건드리지 않음(환불 주문의 결제사 상태 CANCELED를 미결제로 오판하지 않도록)
        if order is None or order.status not in UNPAID_STATUSES or order.payment_key != payment_key:
            await self.db.commit()
            return
        payment_status = (payment or {}).get("status")
        if payment_matches(order, payment, payment_key):
            await self._mark_paid(order, payment)
            logger.warning("unconfirmed order recovered as paid order=%s", order.order_number)
        elif payment_status in TOSS_UNPAID_STATUSES:
            order.status = STATUS_FAILED
            order.failure_message = f"결제사 확인 결과 미결제({payment_status})"
            order.payment_key = None  # 돈이 남아 있지 않음을 확인했으므로 일반 미결제 주문처럼 하루 뒤 삭제
        elif payment is None:
            attempted_at = order.payment_attempted_at
            if attempted_at is not None and attempted_at.tzinfo is None:
                attempted_at = attempted_at.replace(tzinfo=timezone.utc)
            if attempted_at is not None and datetime.now(timezone.utc) - attempted_at >= NOT_FOUND_FINAL_AFTER:
                order.status = STATUS_FAILED
                order.failure_message = "결제사 확인 결과 미결제(NOT_FOUND)"
                order.payment_key = None
            else:
                # 승인 직후 조회에는 아직 결제가 보이지 않을 수 있으므로 결제키를 보존해 다음 주기에 다시 확인
                logger.warning("unconfirmed order not found yet; keeping payment key order=%s", order.order_number)
        elif payment_status not in TOSS_NOT_FINAL_STATUSES:
            logger.error("unconfirmed order needs manual review order=%s status=%s", order.order_number, payment_status)
        await self.db.commit()

    # 결제하지 않고 하루가 지난 주문을 정리(결제키가 남은 주문은 결제사에서 미결제를 확인해 결제키를 지운 뒤에만 삭제)
    async def purge_unpaid_orders(self, commit: bool = True) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        result = await self.db.execute(
            delete(Order).where(Order.status.in_(UNPAID_STATUSES), Order.created_at < cutoff, Order.payment_key.is_(None))
        )
        if commit:
            await self.db.commit()
        return result.rowcount or 0

    # 거래기록 보관기간(전자상거래법 5년)이 지난 결제 완료·환불 완료 주문을 삭제(주문 상품은 CASCADE로 함께 삭제)
    # 기준은 결제·배송·취소 요청/거절·환불 시도/완료 중 가장 최근 시각(오래된 주문에 최근 생긴 취소·환불 기록이 일찍 지워지지 않도록,
    # PostgreSQL GREATEST는 NULL을 무시). 결제 시각이 없는 결제 완료, 환불 시각이 없는 환불 완료, 환불 확인 중은 지우지 않는다
    # 기준일은 고객이 날짜 지정으로 조회할 수 있는 가장 이른 날(한국 시간 5년 전 같은 날 0시)과 같다
    async def purge_expired_orders(self, now: datetime | None = None, commit: bool = True) -> int:
        cutoff = months_ago_start(ORDER_HISTORY_MONTHS, now)
        last_activity = func.greatest(
            Order.paid_at,
            Order.shipped_at,
            Order.delivered_at,
            Order.cancel_requested_at,
            Order.cancel_rejected_at,
            Order.refund_attempted_at,
            Order.refunded_at,
        )
        result = await self.db.execute(
            delete(Order).where(
                or_(
                    and_(Order.status == STATUS_PAID, Order.paid_at.is_not(None)),
                    and_(Order.status == "refunded", Order.refunded_at.is_not(None)),
                ),
                last_activity < cutoff,
            )
        )
        if commit:
            await self.db.commit()
        if result.rowcount:
            logger.info("expired paid and refunded orders purged count=%s", result.rowcount)
        return result.rowcount or 0
