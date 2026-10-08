# 주문 환불(토스 결제 취소)·고객 취소 요청·관리자 승인/거절·환불 보정과 기존 결제 흐름 회귀 테스트(DB·네트워크 없이)

import os
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ADMIN_MFA_REQUIRED", "false")

import httpx  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

from backend.core.errors import api_error  # noqa: E402
from backend.domain.orders.models.orders import Order  # noqa: E402
from backend.domain.orders.schemas.orders import (  # noqa: E402
    AdminRefundRequest,
    CancelRejectRequest,
    CustomerRefundRequest,
    DeliveryStatusRequest,
    OrderConfirmRequest,
)
from backend.domain.orders.services.orders import OrderService  # noqa: E402
from backend.domain.orders.services.refunds import (  # noqa: E402
    OrderRefundService,
    RefundCandidate,
    RefundGatewayCheck,
    cancel_reason_text,
    check_refund_with_gateway,
    is_final_refund_rejection,
    latest_done_cancel,
    payment_not_refunded,
    refund_idempotency_key,
    refund_matches,
)

ORDER_NUMBER = "ARAM-20261001-AAAAAAAAAAAA"
SERVICE_MODULE = "backend.domain.orders.services.refunds"


def make_order(**overrides) -> Order:
    values = dict(
        id=1,
        order_number=ORDER_NUMBER,
        user_id=7,
        status="paid",
        order_name="상품",
        total_amount=12000,
        from_cart=False,
        payment_key="pk_1",
        delivery_status="paid",
        refund_attempt_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    values.update(overrides)
    return Order(**values)


def canceled_payment(order: Order, **overrides) -> dict:
    return {
        "status": "CANCELED",
        "orderId": order.order_number,
        "paymentKey": order.payment_key,
        "totalAmount": order.total_amount,
        "balanceAmount": 0,
        "cancels": [
            {"cancelAmount": order.total_amount, "cancelStatus": "DONE", "canceledAt": "2026-10-07T10:00:00+09:00", "transactionKey": "tx_1"}
        ],
        **overrides,
    }


def done_payment(order: Order, **overrides) -> dict:
    return {
        "status": "DONE",
        "orderId": order.order_number,
        "paymentKey": order.payment_key,
        "totalAmount": order.total_amount,
        "balanceAmount": order.total_amount,
        "cancels": None,
        **overrides,
    }


def gateway_error(http_status: int, code: str | None) -> HTTPException:
    return api_error(400, "REFUND_FAILED", "결제사 오류", gateway_code=code, gateway_status=http_status)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def all(self):
        return []

    def scalars(self):
        return self


# 주문 한 건만 돌려주고 커밋 시점의 상태를 기록하는 메모리 DB(지정한 순번의 커밋을 실패시킬 수 있음)
class FakeDb:
    def __init__(self, order, fail_commit_at: int | None = None):
        self.order = order
        self.commits = []
        self.rollbacks = 0
        self.statements = []
        self.fail_commit_at = fail_commit_at

    async def execute(self, statement, _params=None):
        self.statements.append(statement)
        return FakeResult(self.order)

    async def commit(self):
        if self.fail_commit_at is not None and len(self.commits) + 1 == self.fail_commit_at:
            self.commits.append("FAILED")
            raise RuntimeError("commit failed")
        order = self.order
        self.commits.append((order.status, order.cancel_request_status) if order is not None else None)

    async def rollback(self):
        self.rollbacks += 1


def make_service(order, fail_commit_at=None) -> tuple[OrderRefundService, FakeDb]:
    db = FakeDb(order, fail_commit_at)
    service = OrderRefundService.__new__(OrderRefundService)
    service.db = db
    service.user_service = SimpleNamespace(_get_user_from_access_token=AsyncMock(return_value=SimpleNamespace(id=7)))
    service.admin_service = SimpleNamespace(get_authenticated_admin=AsyncMock())
    service._order_payload = AsyncMock(side_effect=lambda o: {"order_id": o.order_number, "status": o.status})
    service._admin_payloads = AsyncMock(side_effect=lambda orders: [{"order_id": o.order_number, "status": o.status} for o in orders])
    return service, db


def customer_reason(code="change_of_mind", detail=""):
    return CustomerRefundRequest(reason_code=code, reason_detail=detail)


# 결제사 취소·조회를 바꿔 끼우고 서비스 호출 결과(또는 HTTP 오류)를 돌려줌
async def run(call, cancel_effect=None, lookup_effect=None):
    cancel = AsyncMock(**(cancel_effect or {"return_value": {}}))
    lookup = AsyncMock(**(lookup_effect or {"return_value": None}))
    with patch(f"{SERVICE_MODULE}.toss.cancel_payment", cancel), patch(f"{SERVICE_MODULE}.toss.get_payment", lookup):
        try:
            result = await call()
        except HTTPException as error:
            result = error
    return result, cancel, lookup


# 토스 결제 취소 API 호출 결과 매핑(MockTransport, 네트워크 없음)
class TossCancelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from backend.core.config import settings

        original = settings.toss_secret_key
        object.__setattr__(settings, "toss_secret_key", "test_sk_dummy")
        self.addCleanup(object.__setattr__, settings, "toss_secret_key", original)

    def patched(self, handler):
        real = httpx.AsyncClient
        return patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    async def cancel(self, handler):
        from backend.domain.orders.services import toss

        with self.patched(handler):
            return await toss.cancel_payment("pk/1", "ARAM-1-refund-1", "고객: 단순 변심", 12000)

    async def test_request_shape_and_success(self):
        import json

        seen = {}

        def handler(request):
            seen["path"] = request.url.raw_path.decode()
            seen["key"] = request.headers.get("Idempotency-Key")
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"status": "CANCELED"})

        self.assertEqual((await self.cancel(handler))["status"], "CANCELED")
        self.assertEqual(seen["path"], "/v1/payments/pk%2F1/cancel")  # 결제키는 경로에 안전하게 인코딩
        self.assertEqual(seen["key"], "ARAM-1-refund-1")
        self.assertEqual(seen["body"], {"cancelReason": "고객: 단순 변심", "cancelAmount": 12000})

    async def test_error_and_broken_responses(self):
        with self.assertRaises(HTTPException) as raised:
            await self.cancel(lambda request: httpx.Response(403, json={"code": "NOT_CANCELABLE_PAYMENT", "message": "취소 할 수 없는 결제 입니다."}))
        detail = raised.exception.detail
        self.assertEqual((detail["code"], detail["gateway_code"], detail["gateway_status"]), ("REFUND_FAILED", "NOT_CANCELABLE_PAYMENT", 403))
        self.assertEqual(detail["message"], "취소 할 수 없는 결제 입니다.")

        for body in (b"{broken", b"[1, 2]"):
            with self.subTest(body=body), self.assertRaises(HTTPException) as raised:
                await self.cancel(lambda request, body=body: httpx.Response(200, content=body))
            self.assertEqual(raised.exception.detail["code"], "REFUND_RESPONSE_INVALID")

        with self.assertRaises(HTTPException) as raised:
            await self.cancel(lambda request: httpx.Response(500, content=b"oops"))
        self.assertEqual((raised.exception.detail["gateway_code"], raised.exception.detail["gateway_status"]), (None, 500))

        def timeout(request):
            raise httpx.ReadTimeout("timeout")

        with self.assertRaises(HTTPException) as raised:
            await self.cancel(timeout)
        self.assertEqual(raised.exception.detail["code"], "REFUND_GATEWAY_UNAVAILABLE")

    async def test_missing_secret_key(self):
        from backend.core.config import settings

        object.__setattr__(settings, "toss_secret_key", "")
        with self.assertRaises(HTTPException) as raised:
            await self.cancel(lambda request: httpx.Response(200, json={}))
        self.assertEqual(raised.exception.detail["code"], "PAYMENT_NOT_CONFIGURED")


# 오류 분류·결과 일치 판정·사유 문구·입력 검증
class RefundRuleTests(unittest.TestCase):
    # "최종 거절 응답"인지만 판정한다(되돌리기는 조회로 취소가 전혀 없음을 함께 확인해야 함: 서비스 테스트에서 검증)
    def test_final_rejection_classification(self):
        cases = {
            (400, "INVALID_REQUEST"): True,
            (400, "REFUND_REJECTED"): True,
            (400, "PROVIDER_ERROR"): False,  # Codex 3회차: 토스 문서상 일시 오류(잠시 후 재시도)
            (403, "NOT_AVAILABLE_BANK"): False,  # 은행 서비스 시간 아님(일시)
            (400, "SOME_NEW_UNKNOWN_CODE"): False,  # 허용 목록에 없는 신규 코드는 최종으로 보지 않음
            (500, "NOT_CANCELABLE_PAYMENT"): False,  # 허용 코드여도 4xx일 때만
            (401, "UNAUTHORIZED_KEY"): True,
            (403, "NOT_CANCELABLE_PAYMENT"): True,  # 이미 취소된 결제에서도 나므로(토스 FAQ) 단독으로는 되돌리지 않음
            (403, "NOT_CANCELABLE_AMOUNT"): True,
            (400, "ALREADY_CANCELED_PAYMENT"): False,
            (400, "ALREADY_REFUND_PAYMENT"): False,
            (403, "FORBIDDEN_CONSECUTIVE_REQUEST"): False,
            (404, "NOT_FOUND_PAYMENT"): False,
            (404, "INVALID_REQUEST"): False,  # 허용 코드여도 404는 결과 불확정
            (409, "IDEMPOTENT_REQUEST_PROCESSING"): False,
            (409, "NOT_CANCELABLE_PAYMENT"): False,
            (429, "TOO_MANY_REQUESTS"): False,
            (429, "REFUND_REJECTED"): False,
            (500, "FAILED_INTERNAL_SYSTEM_PROCESSING"): False,
            (400, None): False,
        }
        for (http_status, code), expected in cases.items():
            with self.subTest(status=http_status, code=code):
                self.assertIs(is_final_refund_rejection({"gateway_status": http_status, "gateway_code": code}), expected)
        self.assertFalse(is_final_refund_rejection({}))

    def test_refund_matches_requires_full_cancel_of_this_order(self):
        order = make_order()
        self.assertTrue(refund_matches(order, canceled_payment(order)))
        mismatches = [
            None,
            canceled_payment(order, status="PARTIAL_CANCELED"),
            canceled_payment(order, orderId="ARAM-OTHER"),
            canceled_payment(order, paymentKey="pk_other"),
            canceled_payment(order, balanceAmount=1000),
            canceled_payment(order, balanceAmount=None),
            canceled_payment(order, cancels=[{"cancelAmount": 11000, "cancelStatus": "DONE"}]),
            canceled_payment(order, cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}]),
            canceled_payment(order, cancels=[]),
            canceled_payment(order, cancels="broken"),
        ]
        for payment in mismatches:
            with self.subTest(payment=payment):
                self.assertFalse(refund_matches(order, payment))
        # 여러 번에 나눠 취소됐어도 합계가 결제 금액이면 전액 취소
        split = [{"cancelAmount": 2000, "cancelStatus": "DONE"}, {"cancelAmount": 10000, "cancelStatus": "DONE"}]
        self.assertTrue(refund_matches(order, canceled_payment(order, cancels=split)))

    def test_payment_not_refunded_only_for_untouched_done_payment(self):
        order = make_order()
        self.assertTrue(payment_not_refunded(order, done_payment(order)))
        self.assertTrue(payment_not_refunded(order, done_payment(order, cancels=[])))
        for payment in (
            None,
            canceled_payment(order),
            done_payment(order, balanceAmount=1000),
            done_payment(order, cancels=[{"cancelAmount": 1000, "cancelStatus": "DONE"}]),
            done_payment(order, cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}]),  # 진행 중인 취소도 미환불로 보지 않음
            done_payment(order, cancels="broken"),
            done_payment(order, paymentKey="pk_other"),
            done_payment(order, status="PARTIAL_CANCELED"),
        ):
            with self.subTest(payment=payment):
                self.assertFalse(payment_not_refunded(order, payment))

    # Codex 재검수 P2: cancels 배열 순서는 문서에 정해져 있지 않으므로 마지막 거래 키 또는 가장 늦은 취소 시각을 사용
    def test_latest_cancel_does_not_depend_on_array_order(self):
        old = {"cancelAmount": 2000, "cancelStatus": "DONE", "canceledAt": "2026-10-01T10:00:00+09:00", "transactionKey": "tx_old"}
        new = {"cancelAmount": 10000, "cancelStatus": "DONE", "canceledAt": "2026-10-07T10:00:00+09:00", "transactionKey": "tx_new"}
        failed = {"cancelAmount": 12000, "cancelStatus": "ABORTED", "canceledAt": "2026-10-09T10:00:00+09:00", "transactionKey": "tx_x"}
        self.assertEqual(latest_done_cancel({"cancels": [new, old]})["transactionKey"], "tx_new")
        self.assertEqual(latest_done_cancel({"cancels": [old, new, failed]})["transactionKey"], "tx_new")  # 완료된 취소만
        self.assertEqual(latest_done_cancel({"cancels": [old, new], "lastTransactionKey": "tx_old"})["transactionKey"], "tx_old")
        self.assertEqual(latest_done_cancel({"cancels": [{**old, "canceledAt": "broken"}, new]})["transactionKey"], "tx_new")
        self.assertEqual(latest_done_cancel({"cancels": []}), {})

    def test_reason_text_and_idempotency_key(self):
        self.assertEqual(cancel_reason_text("customer", "change_of_mind", None), "고객: 단순 변심")
        self.assertEqual(cancel_reason_text("admin", "other", "포장 파손"), "관리자: 기타 - 포장 파손")
        self.assertLessEqual(len(cancel_reason_text("admin", "other", "가" * 300)), 200)  # 토스 cancelReason 최대 200자
        self.assertEqual(refund_idempotency_key(ORDER_NUMBER, 2), f"{ORDER_NUMBER}-refund-2")

    def test_policies_v1_2_describe_refund_rules(self):
        from backend.domain.users.services.policies import CURRENT_POLICIES

        service, privacy = CURRENT_POLICIES["service"], CURRENT_POLICIES["privacy"]
        self.assertEqual((service.version, privacy.version), ("1.2", "1.2"))  # 본문을 바꾸면 버전도 올림(032 동의 이력과 같은 값)
        for phrase in ("[주문 취소와 환불]", "주문당 1회", "배송중·배송완료 단계의 주문은 취소·환불할 수 없습니다."):
            self.assertIn(phrase, service.content)
        self.assertIn("취소 요청·환불 사유", privacy.content)
        self.assertIn("취소·환불 기록", privacy.content)

    def test_reason_schemas(self):
        self.assertEqual(customer_reason("change_of_mind", "무시됨").reason_detail, "")  # 기타가 아니면 입력 내용 저장 안 함
        self.assertEqual(customer_reason("other", "  색상 변경 ").reason_detail, "색상 변경")
        for code, detail in (("other", ""), ("other", "   "), ("other", "가" * 101), ("customer_request", ""), ("unknown", "")):
            with self.subTest(code=code, detail=detail), self.assertRaises(ValidationError):
                CustomerRefundRequest(reason_code=code, reason_detail=detail)
        self.assertEqual(AdminRefundRequest(reason_code="out_of_stock").reason_code, "out_of_stock")
        with self.assertRaises(ValidationError):
            AdminRefundRequest(reason_code="change_of_mind")  # 고객 사유 코드는 관리자 요청에서 거부
        self.assertEqual(CancelRejectRequest(reason=" 이미 출고 준비 완료 ").reason, "이미 출고 준비 완료")
        for reason in ("", "   ", "가" * 201):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                CancelRejectRequest(reason=reason)


# 고객 즉시 환불
class CustomerRefundTests(unittest.IsolatedAsyncioTestCase):
    async def test_refund_marks_refunding_before_gateway_and_refunded_after(self):
        order = make_order()
        service, db = make_service(order)
        result, cancel, lookup = await run(
            lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()), {"return_value": canceled_payment(order)}
        )
        self.assertEqual(result["status"], "refunded")
        self.assertEqual(db.commits, [("refunding", None), ("refunded", None)])  # 결제사 호출 전에 환불 확인 중을 커밋
        cancel.assert_awaited_once_with("pk_1", f"{ORDER_NUMBER}-refund-1", "고객: 단순 변심", 12000)
        lookup.assert_not_awaited()
        self.assertEqual((order.refund_actor, order.refund_reason_code, order.refund_delivery_status), ("customer", "change_of_mind", "paid"))
        self.assertEqual(order.refunded_at, datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(order.refund_transaction_key, "tx_1")

    async def test_state_checks_block_refund_without_gateway_call(self):
        cases = (
            (dict(delivery_status="preparing"), "ORDER_STATUS_CHANGED"),  # 그 사이 상품준비중이 되면 취소 요청으로 안내
            (dict(delivery_status="shipping"), "ORDER_NOT_REFUNDABLE"),
            (dict(delivery_status="delivered"), "ORDER_NOT_REFUNDABLE"),
            (dict(status="refunding"), "REFUND_IN_PROGRESS"),  # 같은 환불 재전송·동시 요청
            (dict(status="pending"), "ORDER_NOT_FOUND"),
            (dict(status="failed"), "ORDER_NOT_FOUND"),
        )
        for overrides, code in cases:
            with self.subTest(overrides=overrides):
                order = make_order(**overrides)
                service, _ = make_service(order)
                result, cancel, _ = await run(lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()))
                self.assertEqual(result.detail["code"], code)
                cancel.assert_not_awaited()

        service, _ = make_service(None)  # 남의 주문·없는 주문
        result, _, _ = await run(lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()))
        self.assertEqual(result.detail["code"], "ORDER_NOT_FOUND")

    async def test_already_refunded_returns_current_order(self):
        order = make_order(status="refunded", refund_attempt_count=1)
        service, _ = make_service(order)
        result, cancel, _ = await run(lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()))
        self.assertEqual(result["status"], "refunded")
        cancel.assert_not_awaited()

    async def test_final_rejection_reverts_only_when_lookup_shows_no_cancel(self):
        order = make_order()
        service, db = make_service(order)
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            result, _, lookup = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"side_effect": gateway_error(403, "NOT_CANCELABLE_PAYMENT")},
                {"return_value": done_payment(order)},
            )
        self.assertEqual(result.detail["code"], "REFUND_FAILED")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(db.commits, [("refunding", None), ("paid", None)])
        self.assertEqual(order.refund_failure_message, "결제사 오류")
        lookup.assert_awaited_once_with("pk_1")  # 되돌리기 전에 반드시 조회

        # 되돌린 뒤 다시 환불하면 새 멱등 키(시도 2)를 사용
        result, cancel, _ = await run(
            lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()), {"return_value": canceled_payment(order)}
        )
        self.assertEqual(result["status"], "refunded")
        self.assertEqual(cancel.await_args.args[1], f"{ORDER_NUMBER}-refund-2")
        self.assertIsNone(order.refund_failure_message)

    async def test_temporary_or_unknown_rejection_stays_refunding_even_without_cancel(self):
        # Codex 3회차: 일시 오류·알 수 없는 4xx는 조회상 취소가 없어도 되돌리지 않음(새 멱등 키 재시도 방지)
        for code in ("PROVIDER_ERROR", "NOT_AVAILABLE_BANK", "SOME_NEW_UNKNOWN_CODE"):
            with self.subTest(code=code):
                order = make_order()
                service, db = make_service(order)
                result, _, _ = await run(
                    lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                    {"side_effect": gateway_error(400, code)},
                    {"return_value": done_payment(order)},
                )
                self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")
                self.assertEqual(db.commits, [("refunding", None)])

    async def test_final_rejection_of_already_canceled_payment_is_not_reverted(self):
        # Codex P1: NOT_CANCELABLE_PAYMENT·NOT_CANCELABLE_AMOUNT는 이미 취소된 결제에서도 나므로 조회 결과를 따른다
        for code in ("NOT_CANCELABLE_PAYMENT", "NOT_CANCELABLE_AMOUNT"):
            with self.subTest(code=code):
                order = make_order()
                service, _ = make_service(order)
                result, _, _ = await run(
                    lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                    {"side_effect": gateway_error(403, code)},
                    {"return_value": canceled_payment(order)},
                )
                self.assertEqual(result["status"], "refunded")

        cases = (
            {"return_value": done_payment(make_order(), cancels=[{"cancelAmount": 2000, "cancelStatus": "DONE"}], balanceAmount=10000)},
            {"return_value": done_payment(make_order(), cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}])},
            {"return_value": None},
            {"side_effect": RuntimeError("lookup down")},
        )
        for lookup_effect in cases:
            with self.subTest(lookup=lookup_effect):
                order = make_order()
                service, db = make_service(order)
                with self.assertLogs(SERVICE_MODULE, "WARNING") if "side_effect" in lookup_effect else nullcontext():
                    result, _, _ = await run(
                        lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                        {"side_effect": gateway_error(403, "NOT_CANCELABLE_AMOUNT")},
                        lookup_effect,
                    )
                self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")  # 확인할 수 없으면 되돌리지 않음
                self.assertEqual(order.status, "refunding")
                self.assertEqual(db.commits, [("refunding", None)])

    async def test_uncertain_errors_are_settled_by_lookup(self):
        errors = (
            gateway_error(400, "ALREADY_CANCELED_PAYMENT"),
            gateway_error(409, "IDEMPOTENT_REQUEST_PROCESSING"),
            gateway_error(429, "TOO_MANY_REQUESTS"),
            gateway_error(500, "FAILED_INTERNAL_SYSTEM_PROCESSING"),
            gateway_error(400, None),
            api_error(502, "REFUND_GATEWAY_UNAVAILABLE", "연결 실패"),
            api_error(502, "REFUND_RESPONSE_INVALID", "깨진 응답"),
        )
        for error in errors:
            with self.subTest(error=error.detail):
                order = make_order()
                service, _ = make_service(order)
                result, _, lookup = await run(
                    lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                    {"side_effect": error},
                    {"return_value": canceled_payment(order)},
                )
                self.assertEqual(result["status"], "refunded")
                lookup.assert_awaited_once_with("pk_1")

    async def test_unknown_result_stays_refunding(self):
        for lookup_effect in ({"return_value": None}, {"side_effect": RuntimeError("down")}):
            with self.subTest(lookup=lookup_effect):
                order = make_order()
                service, db = make_service(order)
                with self.assertLogs(SERVICE_MODULE, "WARNING") if "side_effect" in lookup_effect else nullcontext():
                    result, _, _ = await run(
                        lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                        {"side_effect": gateway_error(500, "COMMON_ERROR")},
                        lookup_effect,
                    )
                self.assertEqual((result.status_code, result.detail["code"]), (503, "REFUND_CONFIRMATION_PENDING"))
                self.assertEqual(order.status, "refunding")
                self.assertEqual(db.commits, [("refunding", None)])

        # 조회 결과가 아직 취소 전(DONE)이어도 바로 되돌리지 않고 보정 작업에 맡김(결제사가 처리 중일 수 있음)
        order = make_order()
        service, _ = make_service(order)
        result, _, _ = await run(
            lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
            {"side_effect": gateway_error(500, "COMMON_ERROR")},
            {"return_value": done_payment(order)},
        )
        self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")
        self.assertEqual(order.status, "refunding")

    async def test_mismatched_or_unexpected_responses_are_not_trusted(self):
        order = make_order()
        service, _ = make_service(order)
        with self.assertLogs(SERVICE_MODULE, "ERROR"):
            result, _, lookup = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"return_value": canceled_payment(order, balanceAmount=500)},
                {"return_value": canceled_payment(order, balanceAmount=500)},
            )
        self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")
        self.assertEqual(order.status, "refunding")
        lookup.assert_awaited_once()  # 성공 응답이 주문과 다르면 조회로 다시 확인, 그래도 다르면 수동 확인(ERROR)

        order = make_order()
        service, _ = make_service(order)
        with self.assertLogs(SERVICE_MODULE, "ERROR"):
            result, _, lookup = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"return_value": {"status": "DONE"}},  # 200이지만 취소 결과가 아닌 응답
                {"return_value": canceled_payment(order)},
            )
        self.assertEqual(result["status"], "refunded")
        lookup.assert_awaited_once()

        order = make_order()
        service, _ = make_service(order)
        with self.assertLogs(SERVICE_MODULE, "ERROR"):
            result, _, lookup = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"side_effect": ValueError("unexpected")},
                {"return_value": canceled_payment(order)},
            )
        self.assertEqual(result["status"], "refunded")
        lookup.assert_awaited_once()

    async def test_local_commit_failure_after_gateway_success_reports_pending(self):
        order = make_order()
        service, db = make_service(order, fail_commit_at=2)
        with self.assertLogs(SERVICE_MODULE, "ERROR"):
            result, _, _ = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()), {"return_value": canceled_payment(order)}
            )
        self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")
        self.assertEqual(db.rollbacks, 1)

    async def test_local_commit_failure_after_final_rejection_reports_pending(self):
        order = make_order()
        service, db = make_service(order, fail_commit_at=2)
        with self.assertLogs(SERVICE_MODULE, "ERROR"):
            result, _, _ = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"side_effect": gateway_error(403, "NOT_CANCELABLE_PAYMENT")},
                {"return_value": done_payment(order)},
            )
        self.assertEqual((result.status_code, result.detail["code"]), (503, "REFUND_CONFIRMATION_PENDING"))
        self.assertEqual(db.commits, [("refunding", None), "FAILED"])
        self.assertEqual(db.rollbacks, 1)

    async def test_missing_payment_configuration_reverts(self):
        order = make_order()
        service, db = make_service(order)
        result, _, _ = await run(
            lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
            {"side_effect": api_error(503, "PAYMENT_NOT_CONFIGURED", "설정 없음")},
        )
        self.assertEqual(result.detail["code"], "PAYMENT_NOT_CONFIGURED")
        self.assertEqual(db.commits[-1], ("paid", None))

    async def test_revert_skips_when_another_attempt_took_over(self):
        order = make_order()
        service, db = make_service(order)

        async def cancel_after_other_attempt(*_args):
            order.refund_attempt_count = 5  # 응답을 기다리는 동안 다른 시도가 시작됨
            raise gateway_error(400, "INVALID_REQUEST")

        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            result, _, _ = await run(
                lambda service=service: service.customer_refund("token", ORDER_NUMBER, customer_reason()),
                {"side_effect": cancel_after_other_attempt},
                {"return_value": done_payment(order)},
            )
        self.assertEqual(result.detail["code"], "REFUND_CONFIRMATION_PENDING")
        self.assertEqual(order.status, "refunding")  # 다른 시도의 상태를 덮어쓰지 않음


# 고객 취소 요청(상품준비중, 주문당 1회)
class CancelRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_is_saved_once(self):
        order = make_order(delivery_status="preparing")
        service, db = make_service(order)
        result, cancel, _ = await run(lambda service=service: service.customer_cancel_request("token", ORDER_NUMBER, customer_reason("other", "주소 변경")))
        self.assertEqual(result["status"], "paid")
        self.assertEqual(db.commits, [("paid", "requested")])
        self.assertEqual((order.cancel_request_reason_code, order.cancel_request_reason_detail), ("other", "주소 변경"))
        self.assertIsNotNone(order.cancel_requested_at)
        cancel.assert_not_awaited()

        first_requested_at = order.cancel_requested_at
        await run(lambda service=service: service.customer_cancel_request("token", ORDER_NUMBER, customer_reason("reorder")))
        self.assertEqual((order.cancel_request_reason_code, order.cancel_requested_at), ("other", first_requested_at))  # 재전송은 덮어쓰지 않음

    async def test_invalid_states(self):
        cases = (
            (dict(delivery_status="preparing", cancel_request_status="rejected"), "CANCEL_REQUEST_REJECTED"),
            (dict(delivery_status="paid"), "ORDER_STATUS_CHANGED"),
            (dict(delivery_status="shipping"), "ORDER_NOT_REFUNDABLE"),
            (dict(delivery_status="preparing", status="refunding", cancel_request_status="approved"), "REFUND_IN_PROGRESS"),
            (dict(delivery_status="preparing", status="refunded", cancel_request_status="approved"), "ORDER_NOT_REFUNDABLE"),
        )
        for overrides, code in cases:
            with self.subTest(overrides=overrides):
                service, _ = make_service(make_order(**overrides))
                result, _, _ = await run(lambda service=service: service.customer_cancel_request("token", ORDER_NUMBER, customer_reason()))
                self.assertEqual(result.detail["code"], code)


# 관리자 환불·취소 요청 승인/거절과 배송 전환 차단
class AdminRefundTests(unittest.IsolatedAsyncioTestCase):
    def requested_order(self, **overrides):
        return make_order(
            delivery_status="preparing",
            cancel_request_status="requested",
            cancel_requested_at=datetime.now(timezone.utc),
            cancel_request_reason_code="wrong_order",
            **overrides,
        )

    async def test_approve_refunds_with_customer_reason(self):
        order = self.requested_order()
        service, db = make_service(order)
        result, cancel, _ = await run(lambda service=service: service.admin_approve_cancel("admin", ORDER_NUMBER), {"return_value": canceled_payment(order)})
        self.assertEqual(result["status"], "refunded")
        self.assertEqual(db.commits[:2], [("refunding", "approved"), ("refunded", "approved")])
        self.assertEqual(cancel.await_args.args[2], "고객: 주문 실수(수량·상품 잘못 선택)")
        self.assertEqual((order.refund_actor, order.refund_reason_code, order.refund_delivery_status), ("customer", "wrong_order", "preparing"))

        # 같은 승인 재전송은 결제사 호출 없이 현재 주문 반환
        result, cancel, _ = await run(lambda service=service: service.admin_approve_cancel("admin", ORDER_NUMBER))
        self.assertEqual(result["status"], "refunded")
        cancel.assert_not_awaited()

    async def test_failed_approval_returns_request_to_pending(self):
        order = self.requested_order()
        service, _ = make_service(order)
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            result, _, _ = await run(
                lambda service=service: service.admin_approve_cancel("admin", ORDER_NUMBER),
                {"side_effect": gateway_error(400, "REFUND_REJECTED")},
                {"return_value": done_payment(order)},
            )
        self.assertEqual(result.detail["code"], "REFUND_FAILED")
        self.assertEqual((order.status, order.cancel_request_status), ("paid", "requested"))

    async def test_reject_requires_pending_request(self):
        order = self.requested_order()
        service, db = make_service(order)
        result, _, _ = await run(lambda service=service: service.admin_reject_cancel("admin", ORDER_NUMBER, CancelRejectRequest(reason="이미 포장을 마쳤습니다.")))
        self.assertEqual(result["status"], "paid")
        self.assertEqual(db.commits, [("paid", "rejected")])
        self.assertEqual(order.cancel_reject_reason, "이미 포장을 마쳤습니다.")
        self.assertIsNotNone(order.cancel_rejected_at)

        for overrides in (dict(cancel_request_status="rejected"), dict(cancel_request_status=None), dict(status="refunding", cancel_request_status="approved")):
            with self.subTest(overrides=overrides):
                service, _ = make_service(make_order(delivery_status="preparing", **overrides))
                result, _, _ = await run(lambda service=service: service.admin_reject_cancel("admin", ORDER_NUMBER, CancelRejectRequest(reason="사유")))
                self.assertEqual(result.detail["code"], "CANCEL_REQUEST_NOT_PENDING")
                result, _, _ = await run(lambda service=service: service.admin_approve_cancel("admin", ORDER_NUMBER))
                self.assertIn(result.detail["code"], ("CANCEL_REQUEST_NOT_PENDING", "REFUND_IN_PROGRESS"))

    async def test_admin_direct_refund(self):
        order = self.requested_order()
        service, _ = make_service(order)
        result, cancel, _ = await run(
            lambda service=service: service.admin_refund("admin", ORDER_NUMBER, AdminRefundRequest(reason_code="out_of_stock")),
            {"return_value": canceled_payment(order)},
        )
        self.assertEqual(result["status"], "refunded")
        self.assertEqual(order.cancel_request_status, "approved")  # 대기 중 요청은 승인으로 정리
        self.assertEqual(cancel.await_args.args[2], "관리자: 품절·재고 부족")
        self.assertEqual(order.refund_actor, "admin")

        for delivery_status in ("shipping", "delivered"):
            service, _ = make_service(make_order(delivery_status=delivery_status))
            result, cancel, _ = await run(lambda service=service: service.admin_refund("admin", ORDER_NUMBER, AdminRefundRequest(reason_code="customer_request")))
            self.assertEqual(result.detail["code"], "ORDER_NOT_REFUNDABLE")
            cancel.assert_not_awaited()

    async def test_shipping_is_blocked_while_cancel_request_pending(self):
        order = self.requested_order()
        service, db = make_service(order)
        with self.assertRaises(HTTPException) as raised:
            await OrderService.admin_update_delivery(service, "admin", ORDER_NUMBER, DeliveryStatusRequest(status="shipping"))
        self.assertEqual(raised.exception.detail["code"], "CANCEL_REQUEST_PENDING")
        self.assertEqual(order.delivery_status, "preparing")

        order.cancel_request_status = "rejected"  # 거절 뒤에는 배송 진행 가능
        await OrderService.admin_update_delivery(service, "admin", ORDER_NUMBER, DeliveryStatusRequest(status="shipping"))
        self.assertEqual(order.delivery_status, "shipping")

        service, _ = make_service(make_order(delivery_status="paid", cancel_request_status=None))
        await OrderService.admin_update_delivery(service, "admin", ORDER_NUMBER, DeliveryStatusRequest(status="preparing"))

    async def test_delivery_change_only_targets_paid_orders(self):
        service, _ = make_service(None)
        statements = []

        class Db(FakeDb):
            async def execute(self, statement, _params=None):
                statements.append(statement)
                return FakeResult(None)

        service.db = Db(None)
        with self.assertRaises(HTTPException):
            await OrderService.admin_update_delivery(service, "admin", ORDER_NUMBER, DeliveryStatusRequest(status="shipping"))
        sql = str(statements[0].compile(dialect=postgresql.dialect()))
        self.assertIn("orders.status = ", sql)  # 환불 확인 중·환불 완료 주문은 배송 변경 대상이 아님
        self.assertIn("FOR UPDATE", sql)


def candidate_for(order, attempt=1, payment_key="pk_1", attempted_ago=timedelta(hours=1)) -> RefundCandidate:
    return RefundCandidate(
        order_id=order.id,
        order_number=order.order_number,
        payment_key=payment_key,
        total_amount=order.total_amount,
        attempt=attempt,
        cancel_reason="고객: 단순 변심",
        attempted_at=datetime.now(timezone.utc) - attempted_ago,
    )


# 환불 보정 작업과 기존 결제 보정·정리 작업 회귀
class RefundReconcileTests(unittest.IsolatedAsyncioTestCase):
    async def apply(self, order, check, attempt=1, payment_key="pk_1"):
        service, db = make_service(order)
        await service.apply_refund_lookup(candidate_for(order, attempt, payment_key), check)
        return db

    def refunding_order(self, attempted_ago=timedelta(hours=1), **overrides):
        return make_order(status="refunding", refund_attempt_count=1, refund_attempted_at=datetime.now(timezone.utc) - attempted_ago, **overrides)

    async def test_confirmed_cancel_is_applied(self):
        order = self.refunding_order(cancel_request_status="approved")
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            await self.apply(order, RefundGatewayCheck(payment=canceled_payment(order)))
        self.assertEqual((order.status, order.cancel_request_status), ("refunded", "approved"))

        # 처음 요청이 결제사에 닿지 않아 같은 멱등 키 재요청에서 처리된 경우
        order = self.refunding_order()
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_result=canceled_payment(order)))
        self.assertEqual(order.status, "refunded")

        # 재전송 거절 뒤 다시 조회했더니 그 사이 취소된 경우
        order = self.refunding_order()
        check = RefundGatewayCheck(
            payment=done_payment(order),
            resend_error=gateway_error(403, "NOT_CANCELABLE_PAYMENT").detail,
            payment_after_resend=canceled_payment(order),
        )
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            await self.apply(order, check)
        self.assertEqual(order.status, "refunded")

    async def test_revert_requires_final_rejection_and_fresh_lookup_without_cancel(self):
        order = self.refunding_order(cancel_request_status="approved")
        final = gateway_error(403, "NOT_CANCELABLE_PAYMENT").detail
        check = RefundGatewayCheck(payment=done_payment(order), resend_error=final, payment_after_resend=done_payment(order))
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            await self.apply(order, check)
        self.assertEqual((order.status, order.cancel_request_status), ("paid", "requested"))
        self.assertEqual(order.refund_failure_message, "결제사 오류")

        # Codex 재검수 P1: 재전송 전 조회값만으로는 되돌리지 않음(재전송 뒤 조회 실패·진행 중 취소면 유지)
        for after in (None, done_payment(order, cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}])):
            with self.subTest(after=after):
                order = self.refunding_order()
                with self.assertLogs(SERVICE_MODULE, "WARNING"):
                    await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=final, payment_after_resend=after))
                self.assertEqual(order.status, "refunding")

    async def test_unresolved_refund_is_never_reverted_by_time_alone(self):
        # Codex P1: 결제사가 아직 처리 중이면 10분이 지나도 결제완료로 되돌리지 않음(늦게 끝난 취소를 놓치지 않도록)
        order = self.refunding_order()
        provider_error = gateway_error(400, "PROVIDER_ERROR").detail  # 일시 오류는 재조회로 취소가 없어도 유지
        with self.assertLogs(SERVICE_MODULE, "WARNING"):
            await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=provider_error, payment_after_resend=done_payment(order)))
        self.assertEqual(order.status, "refunding")

        pending_errors = (
            gateway_error(409, "IDEMPOTENT_REQUEST_PROCESSING").detail,
            gateway_error(500, "FAILED_INTERNAL_SYSTEM_PROCESSING").detail,
            gateway_error(400, "ALREADY_CANCELED_PAYMENT").detail,
            api_error(502, "REFUND_GATEWAY_UNAVAILABLE", "연결 실패").detail,
            {},
            None,
        )
        for resend_error in pending_errors:
            with self.subTest(resend_error=resend_error):
                order = self.refunding_order()
                with self.assertLogs(SERVICE_MODULE, "WARNING"):
                    await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=resend_error))
                self.assertEqual(order.status, "refunding")

        order = self.refunding_order(attempted_ago=timedelta(days=2))
        with self.assertLogs(SERVICE_MODULE, "ERROR"):  # 하루가 지나 재전송을 멈춘 주문은 수동 확인 요청
            await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_skipped=True))
        self.assertEqual(order.status, "refunding")

    async def test_unexpected_gateway_states_need_manual_review(self):
        order = make_order()
        for payment in (
            None,
            {"status": "PARTIAL_CANCELED"},
            done_payment(order, balanceAmount=100),
            done_payment(order, cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}]),  # Codex P2
        ):
            with self.subTest(payment=payment):
                order = self.refunding_order()
                with self.assertLogs(SERVICE_MODULE, "ERROR"):
                    await self.apply(order, RefundGatewayCheck(payment=payment, resend_error=gateway_error(403, "NOT_CANCELABLE_PAYMENT").detail))
                self.assertEqual(order.status, "refunding")

    async def test_stale_lookup_is_ignored(self):
        final = gateway_error(400, "INVALID_REQUEST").detail
        order = self.refunding_order()
        await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=final), attempt=2)  # 조회 중 새 시도가 시작됨
        self.assertEqual(order.status, "refunding")
        order = self.refunding_order()
        await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=final), payment_key="pk_other")
        self.assertEqual(order.status, "refunding")
        for status in ("paid", "refunded"):
            order = make_order(status=status, refund_attempt_count=1)
            await self.apply(order, RefundGatewayCheck(payment=done_payment(order), resend_error=final))
            self.assertEqual(order.status, status)

    async def test_gateway_check_resends_with_same_key_only_when_untouched(self):
        order = make_order()
        candidate = candidate_for(order, attempt=3)
        with patch(f"{SERVICE_MODULE}.toss.get_payment", AsyncMock(return_value=done_payment(order))), \
                patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock(return_value=canceled_payment(order))) as cancel:
            check = await check_refund_with_gateway(candidate)
        cancel.assert_awaited_once_with("pk_1", f"{ORDER_NUMBER}-refund-3", "고객: 단순 변심", 12000)  # 처음과 같은 키·본문
        self.assertEqual(check.resend_result["status"], "CANCELED")

        # 재전송이 최종 거절이면 그 뒤에 한 번 더 조회(두 번째 조회 실패는 None으로 두어 되돌리지 않게 함)
        lookups = AsyncMock(side_effect=[done_payment(order), canceled_payment(order)])
        with patch(f"{SERVICE_MODULE}.toss.get_payment", lookups), \
                patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock(side_effect=gateway_error(403, "NOT_CANCELABLE_PAYMENT"))):
            check = await check_refund_with_gateway(candidate)
        self.assertEqual(check.resend_error["gateway_code"], "NOT_CANCELABLE_PAYMENT")
        self.assertEqual(check.payment_after_resend["status"], "CANCELED")
        self.assertEqual(lookups.await_count, 2)

        with patch(f"{SERVICE_MODULE}.toss.get_payment", AsyncMock(side_effect=[done_payment(order), RuntimeError("down")])), \
                patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock(side_effect=gateway_error(403, "NOT_CANCELABLE_PAYMENT"))), \
                self.assertLogs(SERVICE_MODULE, "WARNING"):
            check = await check_refund_with_gateway(candidate)
        self.assertIsNone(check.payment_after_resend)

        # 처리 중(409) 같은 최종이 아닌 응답은 다시 조회하지 않음
        lookups = AsyncMock(return_value=done_payment(order))
        with patch(f"{SERVICE_MODULE}.toss.get_payment", lookups), \
                patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock(side_effect=gateway_error(409, "IDEMPOTENT_REQUEST_PROCESSING"))):
            check = await check_refund_with_gateway(candidate)
        self.assertEqual(lookups.await_count, 1)
        self.assertIsNone(check.payment_after_resend)

        # Codex 재검수 P2: 하루가 지나면 재전송하지 않고 조회만(토스 멱등 키 15일 유효)
        with patch(f"{SERVICE_MODULE}.toss.get_payment", AsyncMock(return_value=done_payment(order))), \
                patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock()) as cancel:
            check = await check_refund_with_gateway(candidate_for(order, attempt=3, attempted_ago=timedelta(days=2)))
        cancel.assert_not_awaited()
        self.assertTrue(check.resend_skipped)

        for payment in (canceled_payment(order), done_payment(order, cancels=[{"cancelAmount": 12000, "cancelStatus": "IN_PROGRESS"}]), None):
            with self.subTest(payment=payment), patch(f"{SERVICE_MODULE}.toss.get_payment", AsyncMock(return_value=payment)), \
                    patch(f"{SERVICE_MODULE}.toss.cancel_payment", AsyncMock()) as cancel:
                check = await check_refund_with_gateway(candidate)
            cancel.assert_not_awaited()  # 취소 기록이 있거나 결제가 없으면 다시 보내지 않음
            self.assertIsNone(check.resend_error)

        with patch(f"{SERVICE_MODULE}.toss.get_payment", AsyncMock(side_effect=RuntimeError("down"))), self.assertRaises(RuntimeError):
            await check_refund_with_gateway(candidate)  # 조회 실패는 다음 주기에 재시도

    async def test_candidates_query(self):
        attempted_at = datetime(2026, 10, 8, 1, 0, tzinfo=timezone.utc)
        order = make_order(
            status="refunding", refund_attempt_count=2, refund_actor="admin", refund_reason_code="out_of_stock", refund_attempted_at=attempted_at
        )
        service, db = make_service(None)

        class Rows(FakeResult):
            def all(self):
                return [order]

        async def execute(statement, _params=None):
            db.statements.append(statement)
            return Rows(None)

        db.execute = execute
        candidates = await service.refund_reconcile_candidates()
        self.assertEqual(candidates, [RefundCandidate(1, ORDER_NUMBER, "pk_1", 12000, 2, "관리자: 품절·재고 부족", attempted_at)])
        sql = str(db.statements[0].compile(dialect=postgresql.dialect()))
        self.assertIn("orders.status = ", sql)
        self.assertIn("refund_attempted_at <", sql)
        self.assertIn("payment_key IS NOT NULL", sql)

    async def test_payment_reconcile_ignores_refunded_orders(self):
        # 환불 주문의 결제사 상태 CANCELED를 미결제로 오판해 결제키를 지우면 안 됨
        for status in ("refunding", "refunded", "paid"):
            order = make_order(status=status, refund_attempt_count=1)
            service, _ = make_service(order)
            await OrderService.apply_payment_lookup(service, order.id, "pk_1", canceled_payment(order))
            self.assertEqual((order.status, order.payment_key), (status, "pk_1"))

    async def test_cleanup_and_list_queries_use_explicit_statuses(self):
        service, db = make_service(None)

        class CountResult(FakeResult):
            rowcount = 0

        async def execute(statement, _params=None):
            db.statements.append(statement)
            return CountResult(0)

        db.execute = execute
        await OrderService.purge_unpaid_orders(service, commit=False)
        params = db.statements[-1].compile().params
        self.assertIn(["pending", "failed"], params.values())  # 환불 주문은 결제키와 무관하게 미결제 정리 대상이 아님

        # Codex P1: 환불 완료 주문은 결제 시각이 아니라 환불 시각부터 5년 보관
        await OrderService.purge_expired_orders(service, commit=False)
        sql = str(db.statements[-1].compile(dialect=postgresql.dialect()))
        # Codex 3회차: 결제 완료 주문도 최근에 생긴 취소 요청·거절·환불 시도·배송 기록까지 5년 보관(가장 최근 시각 기준)
        self.assertIn("greatest(", sql)
        for column in ("paid_at", "shipped_at", "delivered_at", "cancel_requested_at", "cancel_rejected_at", "refund_attempted_at", "refunded_at"):
            self.assertIn(f"orders.{column}", sql)
        self.assertIn("orders.paid_at IS NOT NULL", sql)
        self.assertIn("orders.refunded_at IS NOT NULL", sql)
        params = db.statements[-1].compile().params.values()
        self.assertIn("paid", params)
        self.assertIn("refunded", params)

        await OrderService.list_orders(service, "token", None, None, None, 1, 5)
        params = db.statements[-1].compile().params
        self.assertIn(["paid", "refunding", "refunded"], params.values())

        service._admin_payloads = AsyncMock(return_value=[])
        for view, expected in (("cancel_requested", "requested"), ("refunded", ["refunding", "refunded"])):
            with self.subTest(view=view):
                await OrderService.admin_list(service, "admin", None, 1, 10, view)
                self.assertIn(expected, db.statements[-1].compile().params.values())
        await OrderService.admin_list(service, "admin", "paid", 1, 10)
        params = db.statements[-1].compile().params.values()
        self.assertIn("paid", params)

    async def test_payment_result_refresh_after_refund_returns_order(self):
        order = make_order(status="refunded", refund_attempt_count=1)
        service, _ = make_service(order)
        request = OrderConfirmRequest(payment_key="pk_1", order_id=ORDER_NUMBER, amount=12000)
        with patch("backend.domain.orders.services.orders.toss.confirm_payment", AsyncMock()) as confirm:
            result = await OrderService.confirm_payment(service, "token", request)
        self.assertEqual(result["status"], "refunded")
        confirm.assert_not_awaited()

        with self.assertRaises(HTTPException) as raised:
            await OrderService.confirm_payment(service, "token", OrderConfirmRequest(payment_key="pk_x", order_id=ORDER_NUMBER, amount=12000))
        self.assertEqual(raised.exception.detail["code"], "ORDER_NOT_PAYABLE")


if __name__ == "__main__":
    unittest.main()
