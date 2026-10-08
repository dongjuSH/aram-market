# 주문 전액 환불(토스 결제 취소)·고객 취소 요청·관리자 승인/거절과 환불 결과 보정 규칙

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import select

from backend.core.errors import api_error
from backend.domain.orders.models.orders import Order
from backend.domain.orders.schemas.orders import (
    AdminRefundRequest,
    CancelRejectRequest,
    CustomerRefundRequest,
    REFUND_REASON_LABELS,
)
from backend.domain.orders.services import toss
from backend.domain.orders.services.orders import STATUS_PAID, OrderService
from backend.domain.orders.services.stock import release_stock

logger = logging.getLogger(__name__)

STATUS_REFUNDING = "refunding"  # 결제사 취소 요청을 보냈거나 보내는 중(결과 확정 전)
STATUS_REFUNDED = "refunded"
CANCEL_REQUESTED = "requested"
CANCEL_APPROVED = "approved"
CANCEL_REJECTED = "rejected"
ADMIN_REFUNDABLE_DELIVERY = ("paid", "preparing")  # 배송중 이후는 환불하지 않음
REFUND_RECONCILE_AFTER = timedelta(minutes=10)  # 환불 시작 후 이 시간이 지나도 결과가 저장되지 않은 주문을 결제사에 다시 확인
# 이만큼 지나도 결과를 확정하지 못하면 같은 멱등 키 재전송을 멈추고 조회만 하며 ERROR 로그로 수동 확인 요청
# (토스 멱등 키는 처음 사용한 날부터 15일만 유효해 그 뒤의 같은 키 재전송은 첫 응답 재생을 보장하지 않으므로 충분히 이른 기준)
REFUND_MANUAL_REVIEW_AFTER = timedelta(days=1)

# "이 취소 요청은 처리되지 않았다"고 볼 수 있는 토스 결제 취소 오류 코드(명시한 것만 허용, 목록에 없는 신규 코드는 최종으로 보지 않음)
# 근거: https://docs.tosspayments.com/reference/error-codes (결제 취소). 제외한 것: 일시 오류(PROVIDER_ERROR "잠시 후 다시 시도",
# NOT_AVAILABLE_BANK 은행 서비스 시간 아님), 이미 취소·처리 중일 수 있는 것(ALREADY_CANCELED_PAYMENT·ALREADY_REFUND_PAYMENT·
# FORBIDDEN_CONSECUTIVE_REQUEST·IDEMPOTENT_REQUEST_PROCESSING), 404·429·5xx 전부
TOSS_REFUND_FINAL_REJECTION_CODES = {
    "INVALID_REQUEST",
    "INVALID_REFUND_ACCOUNT_INFO",
    "INVALID_REFUND_ACCOUNT_NUMBER",
    "INVALID_BANK",
    "EXCEED_CANCEL_AMOUNT_DISCOUNT_AMOUNT",
    "NOT_MATCHES_REFUNDABLE_AMOUNT",
    "REFUND_REJECTED",
    "FORBIDDEN_BANK_REFUND_REQUEST",
    "UNAUTHORIZED_KEY",
    "INCORRECT_BASIC_AUTH_FORMAT",
    "FORBIDDEN_REQUEST",
    "NOT_CANCELABLE_AMOUNT",
    "NOT_CANCELABLE_PAYMENT",
    "NOT_CANCELABLE_PAYMENT_FOR_DORMANT_USER",
    "EXCEED_MAX_REFUND_DUE",
    "EXCEED_CANCEL_LIMIT",
    "NOT_ALLOWED_PARTIAL_REFUND",
    "NOT_ALLOWED_PARTIAL_REFUND_WAITING_DEPOSIT",
}
TOSS_REFUND_FINAL_REJECTION_STATUSES = {400, 401, 403}


# 토스 취소 오류가 "이 요청은 처리되지 않았다"는 최종 응답인지(공식 표의 HTTP 상태와 위 허용 목록 코드일 때만)
# 최종 응답이어도 NOT_CANCELABLE_PAYMENT처럼 "이미 취소됨"을 뜻할 수 있으므로(토스 FAQ) 되돌리기 전에는 반드시
# 결제사 조회로 취소가 전혀 없는 승인 완료인지 함께 확인한다(payment_not_refunded). 그 밖의 오류는 환불 확인 중으로 두고
# 새 멱등 키로 재시도하지 않는다(토스 멱등키 안내: 오류 원인을 확인하지 않고 키를 바꿔 재시도하는 것은 위험)
def is_final_refund_rejection(detail: dict) -> bool:
    gateway_status = detail.get("gateway_status")
    return (
        isinstance(gateway_status, int)
        and gateway_status in TOSS_REFUND_FINAL_REJECTION_STATUSES
        and detail.get("gateway_code") in TOSS_REFUND_FINAL_REJECTION_CODES
    )


# 결과 판정에 필요한 주문 값(DB 모델 Order와 보정 작업용 RefundCandidate 모두 해당)
class RefundTarget(Protocol):
    order_number: str
    payment_key: str | None
    total_amount: int


# 보정 작업이 잠금 없이 결제사에 확인할 때 쓰는 환불 확인 중 주문 값(멱등 키·취소 사유를 처음 요청과 똑같이 다시 만들 수 있음)
@dataclass(frozen=True)
class RefundCandidate:
    order_id: int
    order_number: str
    payment_key: str
    total_amount: int
    attempt: int
    cancel_reason: str
    attempted_at: datetime | None


# 보정 작업의 결제사 확인 결과: 조회 결과, (취소가 전혀 없을 때만) 같은 멱등 키로 다시 보낸 취소의 응답 또는 오류,
# 재전송이 최종 거절이면 그 뒤에 다시 조회한 최신 결과(되돌리기 판단용), 수동 확인 기준이 지나 재전송을 건너뛰었는지
@dataclass(frozen=True)
class RefundGatewayCheck:
    payment: dict | None
    resend_result: dict | None = None
    resend_error: dict | None = None
    payment_after_resend: dict | None = None
    resend_skipped: bool = False


# 환불을 시작한 뒤 수동 확인 기준(하루)이 지났는지
def is_past_manual_review(attempted_at: datetime | None, now: datetime | None = None) -> bool:
    if attempted_at is None:
        return False
    if attempted_at.tzinfo is None:
        attempted_at = attempted_at.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - attempted_at >= REFUND_MANUAL_REVIEW_AFTER


def _parse_time(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# 결제사 결과의 완료된 취소 기록(cancelStatus=DONE)
def _done_cancels(payment: dict) -> list[dict]:
    cancels = payment.get("cancels")
    if not isinstance(cancels, list):
        return []
    return [cancel for cancel in cancels if isinstance(cancel, dict) and cancel.get("cancelStatus") == "DONE"]


# 결제사 결과가 이 주문의 전액 취소 완료와 정확히 일치하는지(상태·주문번호·결제키·잔액 0·취소 합계 = 결제 금액)
def refund_matches(order: RefundTarget, payment: dict | None) -> bool:
    if not payment or payment.get("status") != "CANCELED" or not order.payment_key:
        return False
    if payment.get("orderId") != order.order_number or payment.get("paymentKey") != order.payment_key:
        return False
    if _int_or_none(payment.get("balanceAmount")) != 0:
        return False
    canceled = [_int_or_none(cancel.get("cancelAmount")) for cancel in _done_cancels(payment)]
    return bool(canceled) and None not in canceled and sum(canceled) == order.total_amount


# 결제사 결과가 "취소 기록이 하나도 없는 승인 완료"인지(진행 중인 취소 기록이 있어도 아님). 되돌리기의 필요조건
def payment_not_refunded(order: RefundTarget, payment: dict | None) -> bool:
    if not payment or payment.get("status") != "DONE":
        return False
    if payment.get("orderId") != order.order_number or payment.get("paymentKey") != order.payment_key:
        return False
    cancels = payment.get("cancels")
    return (
        _int_or_none(payment.get("totalAmount")) == order.total_amount
        and _int_or_none(payment.get("balanceAmount")) == order.total_amount
        and (cancels is None or cancels == [])
    )


# 가장 최근의 완료된 취소 기록(cancels 배열 순서는 문서에 정해져 있지 않으므로 마지막 거래 키 lastTransactionKey가 가리키는
# 취소를 우선하고, 없으면 canceledAt이 가장 늦은 취소)
def latest_done_cancel(payment: dict) -> dict:
    cancels = _done_cancels(payment)
    last_key = payment.get("lastTransactionKey")
    for cancel in cancels:
        if last_key and cancel.get("transactionKey") == last_key:
            return cancel
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return max(cancels, key=lambda cancel: _parse_time(cancel.get("canceledAt")) or oldest, default={})


# 결제사에 보내는 취소 사유(최대 200자): "고객: 단순 변심", "관리자: 기타 - 직접 입력"
def cancel_reason_text(actor: str, reason_code: str, reason_detail: str | None) -> str:
    label = REFUND_REASON_LABELS.get(reason_code, reason_code)
    text = f"{'고객' if actor == 'customer' else '관리자'}: {label}"
    if reason_detail:
        text += f" - {reason_detail}"
    return text[:200]


# 환불 멱등 키: 같은 키는 첫 응답을 그대로 돌려주므로 시도마다 번호를 올려 새 키 사용(최대 300자)
def refund_idempotency_key(order_number: str, attempt: int) -> str:
    return f"{order_number}-refund-{attempt}"


# 고객·관리자 환불과 취소 요청 처리(주문 직렬화·인증은 주문 서비스 기능을 그대로 사용)
class OrderRefundService(OrderService):
    # 고객: 결제완료 주문 즉시 환불(본인 주문만, 상품준비중이 됐으면 취소 요청으로 안내)
    async def customer_refund(self, token: str, order_number: str, request: CustomerRefundRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        order = await self._lock_order(order_number, user_id=user.id)
        if order.status == STATUS_REFUNDED:
            return await self._current_payload(order)
        self._ensure_not_refunding(order)
        if order.status != STATUS_PAID or order.delivery_status not in ADMIN_REFUNDABLE_DELIVERY:
            raise self._not_refundable_error()
        if order.delivery_status != "paid":
            raise api_error(
                status.HTTP_409_CONFLICT,
                "ORDER_STATUS_CHANGED",
                "상품 준비가 시작되어 바로 취소할 수 없습니다. 화면을 새로 고친 뒤 취소 요청을 해 주세요.",
            )
        return await self._refund(order, "customer", request.reason_code, request.reason_detail)

    # 고객: 상품준비중 주문 취소 요청(주문당 1회, 거절되면 다시 요청할 수 없음)
    async def customer_cancel_request(self, token: str, order_number: str, request: CustomerRefundRequest) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        order = await self._lock_order(order_number, user_id=user.id)
        if order.cancel_request_status == CANCEL_REQUESTED and order.status == STATUS_PAID:
            return await self._current_payload(order)  # 같은 요청 재전송
        if order.cancel_request_status == CANCEL_REJECTED:
            raise api_error(status.HTTP_409_CONFLICT, "CANCEL_REQUEST_REJECTED", "취소 요청이 거절된 주문은 다시 요청할 수 없습니다.")
        self._ensure_not_refunding(order)
        if order.status != STATUS_PAID or order.delivery_status not in ADMIN_REFUNDABLE_DELIVERY or order.cancel_request_status:
            raise self._not_refundable_error()
        if order.delivery_status == "paid":
            raise api_error(
                status.HTTP_409_CONFLICT,
                "ORDER_STATUS_CHANGED",
                "결제완료 주문은 취소 요청 없이 바로 취소할 수 있습니다. 화면을 새로 고친 뒤 다시 시도해 주세요.",
            )
        order.cancel_request_status = CANCEL_REQUESTED
        order.cancel_requested_at = datetime.now(timezone.utc)
        order.cancel_request_reason_code = request.reason_code
        order.cancel_request_reason_detail = request.reason_detail or None
        return await self._current_payload(order)

    # 관리자: 결제완료·상품준비중 주문 직접 환불(대기 중인 고객 취소 요청은 승인으로 처리)
    async def admin_refund(self, admin_token: str, order_number: str, request: AdminRefundRequest) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        order = await self._lock_order(order_number)
        if order.status == STATUS_REFUNDED:
            return await self._admin_payload(order)
        self._ensure_not_refunding(order)
        if order.status != STATUS_PAID or order.delivery_status not in ADMIN_REFUNDABLE_DELIVERY:
            raise self._not_refundable_error()
        await self._refund(order, "admin", request.reason_code, request.reason_detail)
        return await self._admin_payload_by_number(order_number)

    # 관리자: 고객 취소 요청 승인(요청한 고객을 환불 주체로, 고객이 고른 사유로 환불)
    async def admin_approve_cancel(self, admin_token: str, order_number: str) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        order = await self._lock_order(order_number)
        if order.status == STATUS_REFUNDED and order.cancel_request_status == CANCEL_APPROVED:
            return await self._admin_payload(order)  # 같은 승인 재전송
        self._ensure_not_refunding(order)
        if order.status != STATUS_PAID or order.cancel_request_status != CANCEL_REQUESTED:
            raise self._cancel_request_not_pending_error()
        await self._refund(order, "customer", order.cancel_request_reason_code or "other", order.cancel_request_reason_detail)
        return await self._admin_payload_by_number(order_number)

    # 관리자: 고객 취소 요청 거절(사유 필수, 주문은 상품준비중 그대로)
    async def admin_reject_cancel(self, admin_token: str, order_number: str, request: CancelRejectRequest) -> dict:
        await self.admin_service.get_authenticated_admin(admin_token)
        order = await self._lock_order(order_number)
        if order.status != STATUS_PAID or order.cancel_request_status != CANCEL_REQUESTED:
            raise self._cancel_request_not_pending_error()
        order.cancel_request_status = CANCEL_REJECTED
        order.cancel_rejected_at = datetime.now(timezone.utc)
        order.cancel_reject_reason = request.reason
        return await self._admin_payload(order)

    # 주문 행을 잠가 조회(고객은 본인 주문만, 없으면 404)
    async def _lock_order(self, order_number: str, user_id: int | None = None) -> Order:
        query = select(Order).where(Order.order_number == order_number)
        if user_id is not None:
            query = query.where(Order.user_id == user_id)
        order = (await self.db.execute(query.with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if order is None or order.status not in (STATUS_PAID, STATUS_REFUNDING, STATUS_REFUNDED):
            if order is not None:
                await self.db.commit()  # 잠금 해제
            raise api_error(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
        return order

    # 지금 상태를 커밋하고 고객 화면용 주문을 반환
    async def _current_payload(self, order: Order) -> dict:
        payload = await self._order_payload(order)
        await self.db.commit()
        return payload

    async def _admin_payload(self, order: Order) -> dict:
        payload = (await self._admin_payloads([order]))[0]
        await self.db.commit()
        return payload

    async def _admin_payload_by_number(self, order_number: str) -> dict:
        order = (
            await self.db.execute(select(Order).where(Order.order_number == order_number).execution_options(populate_existing=True))
        ).scalar_one()
        return await self._admin_payload(order)

    def _ensure_not_refunding(self, order: Order) -> None:
        if order.status == STATUS_REFUNDING:
            raise api_error(status.HTTP_409_CONFLICT, "REFUND_IN_PROGRESS", "환불을 처리하고 있습니다. 잠시 후 주문 상태를 확인해 주세요.")

    @staticmethod
    def _not_refundable_error() -> HTTPException:
        return api_error(status.HTTP_409_CONFLICT, "ORDER_NOT_REFUNDABLE", "배송이 시작되었거나 취소할 수 없는 주문입니다.")

    @staticmethod
    def _cancel_request_not_pending_error() -> HTTPException:
        return api_error(status.HTTP_409_CONFLICT, "CANCEL_REQUEST_NOT_PENDING", "처리할 취소 요청이 없습니다. 화면을 새로 고쳐 주세요.")

    @staticmethod
    def _refund_pending_error() -> HTTPException:
        return api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "REFUND_CONFIRMATION_PENDING",
            "환불 결과를 확인하고 있습니다. 잠시 후 주문 내역에서 다시 확인해 주세요.",
        )

    # 환불 실행: ① 잠근 주문을 환불 확인 중으로 바꿔 커밋(다른 환불·배송 변경 차단) ② 잠금 없이 결제사 취소
    # ③ 결과를 다시 잠가 반영. 결과를 알 수 없으면 실패로 확정하지 않고 조회, 그래도 모르면 보정 작업에 맡김
    async def _refund(self, order: Order, actor: str, reason_code: str, reason_detail: str | None) -> dict:
        if not order.payment_key:
            logger.error("paid order has no payment key order=%s", order.order_number)
            raise self._not_refundable_error()
        order.status = STATUS_REFUNDING
        order.refund_actor = actor
        order.refund_reason_code = reason_code
        order.refund_reason_detail = reason_detail or None
        order.refund_attempt_count = (order.refund_attempt_count or 0) + 1
        order.refund_attempted_at = datetime.now(timezone.utc)
        order.refund_failure_message = None
        order.refund_delivery_status = order.delivery_status
        if order.cancel_request_status == CANCEL_REQUESTED:
            order.cancel_request_status = CANCEL_APPROVED
        order_id, order_number, payment_key = order.id, order.order_number, order.payment_key
        attempt, amount = order.refund_attempt_count, order.total_amount
        await self.db.commit()

        try:
            result = await toss.cancel_payment(
                payment_key,
                refund_idempotency_key(order_number, attempt),
                cancel_reason_text(actor, reason_code, reason_detail),
                amount,
            )
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {}
            if detail.get("code") == "PAYMENT_NOT_CONFIGURED":
                # 결제사에 요청을 보내기 전에 멈춘 경우라 바로 되돌려도 안전
                await self._revert_refund(order_id, attempt, "결제 설정이 완료되지 않아 환불하지 못했습니다.")
                raise
            return await self._settle_refund_error(order, order_id, attempt, detail)
        except Exception:
            logger.exception("unexpected error during refund order=%s", order_number)
            return await self._settle_refund_error(order, order_id, attempt, {})

        if not refund_matches(order, result):
            # 성공 응답이어도 전액 취소·주문 정보가 맞지 않으면 믿지 않고 결제사 조회로 다시 확인
            logger.error("refund response does not match order order=%s status=%s", order_number, result.get("status"))
            return await self._settle_refund_error(order, order_id, attempt, {})
        return await self._finalize_refund(order_id, result)

    # 취소 요청이 오류였거나 결과를 믿을 수 없을 때 결제사에 바로 조회해 판정
    # 전액 취소 완료 → 반영, 최종 거절 응답 + 취소 기록이 전혀 없는 승인 완료 → 결제완료로 되돌리고 400,
    # 그 밖(조회 실패·처리 중·5xx·진행 중 취소 등) → 환불 확인 중으로 두고 503(보정 작업이 같은 멱등 키로 다시 확인)
    async def _settle_refund_error(self, order: RefundTarget, order_id: int, attempt: int, detail: dict) -> dict:
        try:
            payment = await toss.get_payment(order.payment_key)
        except Exception:
            logger.warning("payment lookup after refund error failed order_id=%s", order_id, exc_info=True)
            payment = None
        if payment is not None and payment.get("status") == "CANCELED":
            return await self._finalize_refund(order_id, payment)
        if detail.get("code") == "REFUND_FAILED" and is_final_refund_rejection(detail) and payment_not_refunded(order, payment):
            message = str(detail.get("message") or "환불 처리에 실패했습니다.")
            if not await self._revert_refund(order_id, attempt, message):
                # 결제사 거절은 확정됐어도 로컬 주문을 paid로 되돌리지 못했으면 화면에 확정 실패로 알리지 않음
                logger.warning("refund rejection could not be persisted order=%s", order.order_number)
                raise self._refund_pending_error()
            logger.warning("refund rejected order=%s code=%s", order.order_number, detail.get("gateway_code"))
            raise api_error(status.HTTP_400_BAD_REQUEST, "REFUND_FAILED", message)
        raise self._refund_pending_error()

    # 결제사가 전액 취소를 확인한 뒤 주문을 다시 잠가 반영하고, 커밋까지 끝난 경우에만 성공 응답
    async def _finalize_refund(self, order_id: int, payment: dict) -> dict:
        try:
            order = (
                await self.db.execute(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
            ).scalar_one_or_none()
            if order is None or not refund_matches(order, payment):
                logger.error("refund result does not match order order_id=%s status=%s", order_id, (payment or {}).get("status"))
                await self.db.rollback()
                raise self._refund_pending_error()
            if order.status in (STATUS_PAID, STATUS_REFUNDING):
                await self._mark_refunded(order, payment)
            payload = await self._order_payload(order)
            await self.db.commit()
            return payload
        except HTTPException:
            raise
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.error("refund settlement rollback failed order_id=%s", order_id, exc_info=True)
            logger.error("confirmed refund could not be persisted order_id=%s", order_id, exc_info=True)
            raise self._refund_pending_error() from error

    # 환불 완료 처리: 상태·취소 시각·취소 거래 키 기록과 재고 복구(환불 완료 반영의 유일한 지점, 같은 커밋에서 복구하므로
    # 커밋이 실패하면 복구도 함께 취소되고 보정 작업이 다시 이곳을 거친다. 차감하지 않은 033 이전 주문·shortage는 복구하지 않음)
    async def _mark_refunded(self, order: Order, payment: dict) -> None:
        if order.status == STATUS_PAID:
            logger.warning("refund confirmed after order was reverted to paid order=%s", order.order_number)
        latest = latest_done_cancel(payment)
        order.status = STATUS_REFUNDED
        order.refund_failure_message = None
        order.refund_transaction_key = str(latest.get("transactionKey") or "")[:64] or None
        order.refunded_at = _parse_time(latest.get("canceledAt")) or datetime.now(timezone.utc)
        if order.cancel_request_status == CANCEL_REQUESTED:
            order.cancel_request_status = CANCEL_APPROVED
        await release_stock(self.db, order)

    # 확정 거절·미반영 확인 시 환불 확인 중 주문을 결제완료로 되돌림(같은 시도일 때만, 승인한 취소 요청은 다시 대기로)
    async def _revert_refund(self, order_id: int, attempt: int, message: str) -> bool:
        try:
            order = (
                await self.db.execute(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
            ).scalar_one_or_none()
            if order is not None and order.status == STATUS_REFUNDING and order.refund_attempt_count == attempt:
                self._apply_revert(order, message)
                reverted = True
            else:
                # 다른 작업이 이미 같은 시도를 paid로 되돌린 경우만 확정 실패로 응답해도 됨
                reverted = order is not None and order.status == STATUS_PAID and order.refund_attempt_count == attempt
            await self.db.commit()
            return reverted
        except Exception:
            # 되돌리지 못해도 환불 확인 중으로 남아 보정 작업이 결제사 조회 후 되돌린다
            logger.error("refund revert failed order_id=%s", order_id, exc_info=True)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return False

    @staticmethod
    def _apply_revert(order: Order, message: str) -> None:
        order.status = STATUS_PAID
        order.refund_failure_message = message[:300]
        if order.cancel_request_status == CANCEL_APPROVED:
            order.cancel_request_status = CANCEL_REQUESTED

    # 보정 대상: 환불을 시작한 지 10분이 지났는데 결과가 저장되지 않은 주문(잠금 없음)
    async def refund_reconcile_candidates(self, now: datetime | None = None) -> list[RefundCandidate]:
        cutoff = (now or datetime.now(timezone.utc)) - REFUND_RECONCILE_AFTER
        orders = (
            await self.db.execute(
                select(Order).where(
                    Order.status == STATUS_REFUNDING,
                    Order.payment_key.is_not(None),
                    Order.refund_attempted_at < cutoff,
                )
            )
        ).scalars().all()
        return [
            RefundCandidate(
                order_id=order.id,
                order_number=order.order_number,
                payment_key=order.payment_key,
                total_amount=order.total_amount,
                attempt=order.refund_attempt_count,
                cancel_reason=cancel_reason_text(order.refund_actor or "admin", order.refund_reason_code or "other", order.refund_reason_detail),
                attempted_at=order.refund_attempted_at,
            )
            for order in orders
        ]

    # 결제사 확인 결과를 주문 한 건에 짧은 트랜잭션으로 반영(조회 중 상태·결제키·시도 횟수가 바뀌었으면 건너뜀). 판정:
    # 어느 조회·응답에서든 전액 취소 확인 → 환불 완료 /
    # 같은 키 재요청이 최종 거절이고 그 **뒤에** 다시 조회한 결과도 취소 기록이 전혀 없는 승인 완료 → 결제완료로 되돌림 /
    # 하루가 지나 재전송을 멈춘 경우 → 유지 + ERROR(수동 확인) / 취소 없음 + 처리 중·5xx·조회 실패 → 유지(다음 주기) /
    # 부분·진행 중 취소·결제 없음·불일치 → 유지 + ERROR(수동 확인)
    async def apply_refund_lookup(self, candidate: RefundCandidate, check: RefundGatewayCheck) -> None:
        order = (
            await self.db.execute(
                select(Order).where(Order.id == candidate.order_id).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if (
            order is None
            or order.status != STATUS_REFUNDING
            or order.payment_key != candidate.payment_key
            or order.refund_attempt_count != candidate.attempt
        ):
            await self.db.commit()
            return
        payments = (check.payment, check.resend_result, check.payment_after_resend)
        matched = next((payment for payment in payments if refund_matches(order, payment)), None)
        resend_error = check.resend_error or {}
        if matched is not None:
            await self._mark_refunded(order, matched)
            logger.warning("unconfirmed refund recovered as refunded order=%s", order.order_number)
        elif (
            resend_error.get("code") == "REFUND_FAILED"
            and is_final_refund_rejection(resend_error)
            and payment_not_refunded(order, check.payment_after_resend)
        ):
            # 같은 멱등 키는 처음 요청의 응답을 그대로 돌려주므로 처음 요청이 거절된 것이고, 거절 뒤 조회로도 취소가 없음을 확인함
            self._apply_revert(order, str(resend_error.get("message") or "환불 처리에 실패했습니다."))
            logger.warning("unconfirmed refund was rejected by gateway; reverted to paid order=%s", order.order_number)
        elif check.resend_skipped:
            logger.error("refund still unresolved after a day; needs manual review order=%s", order.order_number)
        elif payment_not_refunded(order, check.payment):
            logger.warning("refund result still pending at gateway order=%s", order.order_number)
        else:
            logger.error(
                "unconfirmed refund needs manual review order=%s status=%s", order.order_number, (check.payment or {}).get("status")
            )
        await self.db.commit()


# 보정 작업의 외부 호출(DB 트랜잭션 밖): 결제사 조회 후, 취소 기록이 전혀 없으면 처음과 같은 멱등 키·본문으로 취소를 다시 보내
# 처음 요청의 결과를 회수한다(처음 요청이 결제사에 닿지 않았다면 이때 처리됨). 재전송이 최종 거절이면 되돌리기 판단을 위해
# 한 번 더 조회한다(두 호출 사이에 취소됐을 수 있음, 조회 실패는 되돌리지 않음). 환불 시작 후 하루가 지나면 재전송하지 않고
# 조회만 한다(토스 멱등 키 15일 유효). 첫 조회 실패는 예외로 알려 다음 주기에 재시도
async def check_refund_with_gateway(candidate: RefundCandidate, now: datetime | None = None) -> RefundGatewayCheck:
    payment = await toss.get_payment(candidate.payment_key)
    if refund_matches(candidate, payment) or not payment_not_refunded(candidate, payment):
        return RefundGatewayCheck(payment=payment)
    if is_past_manual_review(candidate.attempted_at, now):
        return RefundGatewayCheck(payment=payment, resend_skipped=True)
    try:
        result = await toss.cancel_payment(
            candidate.payment_key,
            refund_idempotency_key(candidate.order_number, candidate.attempt),
            candidate.cancel_reason,
            candidate.total_amount,
        )
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        if not (detail.get("code") == "REFUND_FAILED" and is_final_refund_rejection(detail)):
            return RefundGatewayCheck(payment=payment, resend_error=detail)
        try:
            latest = await toss.get_payment(candidate.payment_key)
        except Exception:
            logger.warning("payment lookup after refund resend failed order=%s", candidate.order_number, exc_info=True)
            latest = None
        return RefundGatewayCheck(payment=payment, resend_error=detail, payment_after_resend=latest)
    except Exception:
        logger.warning("refund resend failed order=%s", candidate.order_number, exc_info=True)
        return RefundGatewayCheck(payment=payment, resend_error={})
    return RefundGatewayCheck(payment=payment, resend_result=result)
