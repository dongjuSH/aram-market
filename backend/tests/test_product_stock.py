# 상품 재고 차감·복구(결제 승인 직전 차감, 미결제 확정·환불 완료 복구)와 재고 확인 API 규칙 테스트(DB·네트워크 없이)

import os
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ADMIN_MFA_REQUIRED", "false")

from fastapi import HTTPException  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

from backend.core.errors import api_error  # noqa: E402
from backend.domain.orders.models.orders import Order  # noqa: E402
from backend.domain.orders.schemas.orders import OrderConfirmRequest  # noqa: E402
from backend.domain.orders.services.orders import OrderService  # noqa: E402
from backend.domain.orders.services.refunds import OrderRefundService  # noqa: E402
from backend.domain.orders.services.stock import release_stock, reserve_stock  # noqa: E402
from backend.domain.products.services.availability import out_of_stock_error  # noqa: E402

ORDER_NUMBER = "ARAM-20261008-AAAAAAAAAAAA"
ORDERS_MODULE = "backend.domain.orders.services.orders"


class FakeRows:
    rowcount = 0

    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


# 주문·주문 상품·상품 재고를 메모리에 두고 SQL 종류에 맞는 결과를 돌려주는 DB(재고 UPDATE는 실제로 반영)
class StockDb:
    def __init__(self, order=None, lines=(), stocks=None, products=()):
        self.order = order
        self.lines = list(lines)  # (product_id, product_name, quantity)
        self.stocks = dict(stocks or {})
        self.products = list(products)
        self.sql = []
        self.commits = []
        self.rollbacks = 0

    async def execute(self, statement, _params=None):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.sql.append(sql)
        if sql.startswith("UPDATE products"):
            params = compiled.params
            product_id = next(value for key, value in params.items() if key.startswith("id_"))
            quantity = next(value for key, value in params.items() if key.startswith("stock_"))
            self.stocks[product_id] += -quantity if "stock - " in sql else quantity
            return FakeRows([])
        if "FROM order_items" in sql:
            return FakeRows(self.lines)
        if "FROM products JOIN product_categories" in sql:
            return FakeRows(self.products)
        if "FROM products" in sql:
            return FakeRows(sorted(self.stocks.items()))
        if "FROM orders" in sql:
            return FakeRows([self.order] if self.order is not None else [])
        return FakeRows([])

    async def commit(self):
        self.commits.append((self.order.status, self.order.stock_status, dict(self.stocks)) if self.order else dict(self.stocks))

    async def rollback(self):
        self.rollbacks += 1

    def lock_sql(self):
        return [sql for sql in self.sql if sql.startswith("SELECT products.id, products.stock")]


def make_order(**overrides) -> Order:
    values = dict(
        id=1,
        order_number=ORDER_NUMBER,
        user_id=7,
        status="pending",
        order_name="상품",
        total_amount=19800,
        from_cart=False,
        payment_key=None,
        payment_attempted_at=None,
        refund_attempt_count=0,
        stock_status=None,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    values.update(overrides)
    return Order(**values)


def order_service(db) -> OrderService:
    service = OrderService.__new__(OrderService)
    service.db = db
    service.user_service = SimpleNamespace(_get_user_from_access_token=AsyncMock(return_value=SimpleNamespace(id=7, nickname="n", email="e")))
    service._order_payload = AsyncMock(side_effect=lambda order: {"order_id": order.order_number, "status": order.status})
    return service


def done_payment(order, payment_key="pk_1"):
    return {"status": "DONE", "orderId": order.order_number, "paymentKey": payment_key, "totalAmount": order.total_amount,
            "method": "카드", "approvedAt": "2026-10-08T10:00:00+09:00"}


# 공통 차감·복구 함수: 조건부·전부 아니면 전무·id 순서 잠금·한 번만 복구
class StockFunctionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reserve_deducts_all_lines_and_locks_products_in_id_order(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2), (3, "크림", 1)], stocks={3: 5, 16: 2})
        self.assertEqual(await reserve_stock(db, order), [])
        self.assertEqual(db.stocks, {3: 4, 16: 0})
        self.assertEqual(order.stock_status, "reserved")
        lock = db.lock_sql()[0]
        self.assertIn("ORDER BY products.id", lock)
        self.assertIn("FOR UPDATE", lock)
        updates = [sql for sql in db.sql if sql.startswith("UPDATE products")]
        self.assertEqual(len(updates), 2)

    async def test_reserve_changes_nothing_when_any_line_is_short(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 3), (3, "크림", 1)], stocks={3: 5, 16: 2})
        shortages = await reserve_stock(db, order)
        self.assertEqual(shortages, [{"product_id": 16, "name": "립밤", "available": 2}])
        self.assertEqual(db.stocks, {3: 5, 16: 2})
        self.assertIsNone(order.stock_status)
        self.assertFalse([sql for sql in db.sql if sql.startswith("UPDATE")])

    async def test_reserve_treats_deleted_product_row_and_missing_row_as_shortage(self):
        order = make_order()
        db = StockDb(order, lines=[(None, "삭제된 상품", 1), (9, "없는 상품", 1)], stocks={})
        shortages = await reserve_stock(db, order)
        self.assertEqual(
            shortages, [{"product_id": None, "name": "삭제된 상품", "available": 0}, {"product_id": 9, "name": "없는 상품", "available": 0}]
        )
        self.assertIsNone(order.stock_status)

    async def test_same_product_lines_are_summed(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 1), (16, "립밤", 1)], stocks={16: 1})
        self.assertEqual((await reserve_stock(db, order))[0]["available"], 1)

    async def test_release_restores_once_and_ignores_unreserved_orders(self):
        order = make_order(stock_status="reserved")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        self.assertTrue(await release_stock(db, order))
        self.assertFalse(await release_stock(db, order))  # 두 번째 호출은 아무것도 하지 않음
        self.assertEqual((db.stocks, order.stock_status), ({16: 2}, "released"))
        for state in (None, "released", "shortage"):
            other = make_order(stock_status=state)
            other_db = StockDb(other, lines=[(16, "립밤", 2)], stocks={16: 0})
            self.assertFalse(await release_stock(other_db, other))
            self.assertEqual((other_db.stocks, other_db.sql), ({16: 0}, []))

    async def test_release_skips_deleted_product_lines(self):
        order = make_order(stock_status="reserved")
        db = StockDb(order, lines=[(None, "삭제된 상품", 1), (3, "크림", 1)], stocks={3: 0})
        with self.assertLogs("backend.domain.orders.services.stock", "WARNING"):
            self.assertTrue(await release_stock(db, order))
        self.assertEqual(db.stocks, {3: 1})

    def test_out_of_stock_error_messages(self):
        sold_out = out_of_stock_error([{"product_id": 16, "name": "립밤", "available": 0}]).detail
        self.assertEqual((sold_out["code"], sold_out["message"]), ("OUT_OF_STOCK", "'립밤' 상품이 품절되었습니다."))
        self.assertEqual(sold_out["stock_shortages"][0]["available"], 0)
        low = out_of_stock_error([{"product_id": 16, "name": "립밤", "available": 1}, {"product_id": 3, "name": "크림", "available": 0}])
        self.assertEqual(low.status_code, 409)
        self.assertEqual(low.detail["message"], "'립밤' 상품은 1개 남아 있습니다. 외 1개 상품의 재고가 부족합니다.")


# 결제 승인 직전 차감과 승인 결과별 복구
class ConfirmStockTests(unittest.IsolatedAsyncioTestCase):
    async def confirm(self, db, confirm_effect, lookup_effect=None, payment_key="pk_1"):
        service = order_service(db)
        request = OrderConfirmRequest(payment_key=payment_key, order_id=db.order.order_number, amount=db.order.total_amount)
        confirm = AsyncMock(**confirm_effect)
        with patch(f"{ORDERS_MODULE}.toss.confirm_payment", confirm), \
                patch(f"{ORDERS_MODULE}.toss.get_payment", AsyncMock(**(lookup_effect or {"return_value": None}))):
            try:
                return await service.confirm_payment("token", request), confirm
            except HTTPException as error:
                return error, confirm

    async def test_out_of_stock_does_not_call_gateway_or_save_payment_key(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 1})
        result, confirm = await self.confirm(db, {"return_value": done_payment(order)})
        self.assertEqual((result.status_code, result.detail["code"]), (409, "OUT_OF_STOCK"))
        self.assertEqual(result.detail["stock_shortages"], [{"product_id": 16, "name": "립밤", "available": 1}])
        confirm.assert_not_awaited()
        self.assertEqual((order.status, order.payment_key, order.stock_status), ("failed", None, None))
        self.assertEqual(db.stocks, {16: 1})

    async def test_second_concurrent_buyer_of_last_units_is_rejected(self):
        stocks = {16: 2}
        first, second = make_order(id=1), make_order(id=2, order_number="ARAM-20261008-BBBBBBBBBBBB")
        first_db = StockDb(first, lines=[(16, "립밤", 2)], stocks=stocks)
        result, _ = await self.confirm(first_db, {"return_value": done_payment(first)})
        self.assertEqual(result["status"], "paid")
        second_db = StockDb(second, lines=[(16, "립밤", 2)], stocks=first_db.stocks)  # 첫 주문 커밋 후 재고(행 잠금으로 순서대로 처리)
        result, confirm = await self.confirm(second_db, {"return_value": done_payment(second)})
        self.assertEqual(result.detail["code"], "OUT_OF_STOCK")
        confirm.assert_not_awaited()
        self.assertEqual(second_db.stocks, {16: 0})

    async def test_reservation_is_committed_with_payment_key_before_gateway_call(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        result, _ = await self.confirm(db, {"return_value": done_payment(order)})
        self.assertEqual(result["status"], "paid")
        self.assertEqual(db.commits[0], ("pending", "reserved", {16: 0}))
        self.assertEqual(order.payment_key, "pk_1")

    async def test_retry_and_already_paid_do_not_deduct_twice(self):
        order = make_order(payment_key="pk_1", payment_attempted_at=datetime.now(timezone.utc), stock_status="reserved")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        result, _ = await self.confirm(db, {"return_value": done_payment(order)})
        self.assertEqual(result["status"], "paid")
        self.assertEqual((db.stocks, db.lock_sql()), ({16: 0}, []))
        result, confirm = await self.confirm(db, {"return_value": done_payment(order)})  # 결과 화면 새로고침
        confirm.assert_not_awaited()
        self.assertEqual(db.stocks, {16: 0})

    async def test_definitive_rejection_releases_stock_in_the_same_commit(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        rejection = api_error(400, "PAYMENT_FAILED", "카드 거절", gateway_code="REJECT_CARD_COMPANY", gateway_status=400)
        result, _ = await self.confirm(db, {"side_effect": rejection})
        self.assertEqual(result.detail["code"], "PAYMENT_FAILED")
        self.assertEqual(db.commits[-1], ("failed", "released", {16: 2}))
        self.assertEqual(order.payment_key, "pk_1")  # 정리 작업이 결제사에서 한 번 더 확인

    async def test_rejection_is_skipped_when_order_changed_during_gateway_call(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        rejection = api_error(400, "PAYMENT_FAILED", "카드 거절", gateway_code="REJECT_CARD_COMPANY", gateway_status=400)

        async def reconciled_meanwhile(*_args):
            order.payment_key = "pk_other"  # 승인 호출 동안 다른 작업이 주문을 바꾼 경우
            raise rejection

        result, _ = await self.confirm(db, {"side_effect": reconciled_meanwhile})
        self.assertEqual(result.detail["code"], "PAYMENT_FAILED")
        self.assertEqual((order.status, order.stock_status, db.stocks), ("pending", "reserved", {16: 0}))

    async def test_uncertain_result_keeps_stock_reserved(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        uncertain = api_error(400, "PAYMENT_FAILED", "처리 중", gateway_code="ALREADY_PROCESSING_REQUEST", gateway_status=400)
        result, _ = await self.confirm(db, {"side_effect": uncertain})
        self.assertEqual(result.detail["code"], "PAYMENT_CONFIRMATION_PENDING")
        self.assertEqual((order.status, order.stock_status, db.stocks), ("pending", "reserved", {16: 0}))

    async def test_amount_mismatch_after_earlier_attempt_keeps_reservation(self):
        # 앞선 요청이 결제키·재고를 커밋하고 승인을 기다리는 동안 같은 결제키·잘못된 금액이 들어온 경우(Codex P1)
        order = make_order(payment_key="pk_1", payment_attempted_at=datetime.now(timezone.utc), stock_status="reserved")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        service = order_service(db)
        request = OrderConfirmRequest(payment_key="pk_1", order_id=order.order_number, amount=order.total_amount + 100)
        with patch(f"{ORDERS_MODULE}.toss.confirm_payment", AsyncMock()) as confirm, self.assertRaises(HTTPException) as raised:
            await service.confirm_payment("token", request)
        self.assertEqual(raised.exception.detail["code"], "PAYMENT_CONFIRMATION_PENDING")
        confirm.assert_not_awaited()
        self.assertEqual((order.status, order.payment_key, order.stock_status, db.stocks), ("pending", "pk_1", "reserved", {16: 0}))
        self.assertEqual(db.lock_sql(), [])

    async def test_amount_mismatch_before_any_attempt_fails_without_stock_change(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        request = OrderConfirmRequest(payment_key="pk_1", order_id=order.order_number, amount=order.total_amount + 100)
        with self.assertRaises(HTTPException) as raised:
            await order_service(db).confirm_payment("token", request)
        self.assertEqual(raised.exception.detail["code"], "AMOUNT_MISMATCH")
        self.assertEqual((order.status, order.payment_key, order.stock_status, db.stocks), ("failed", None, None, {16: 2}))

    async def test_out_of_stock_with_earlier_payment_key_stays_pending_for_reconcile(self):
        # 033 이전에 결제키가 저장된 pending 주문: 앞선 승인 결과를 모르므로 failed로 확정하지 않음
        order = make_order(payment_key="pk_1", payment_attempted_at=datetime.now(timezone.utc))
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 1})
        result, confirm = await self.confirm(db, {"return_value": done_payment(order)})
        # "결제 안 됨"(OUT_OF_STOCK)이 아니라 결과 확인 중으로 안내해야 고객이 다시 주문해 중복 결제하지 않음(Codex 2회차 P1)
        self.assertEqual((result.status_code, result.detail["code"]), (503, "PAYMENT_CONFIRMATION_PENDING"))
        confirm.assert_not_awaited()
        self.assertEqual((order.status, order.payment_key, order.stock_status, db.stocks), ("pending", "pk_1", None, {16: 1}))

    async def test_payment_not_configured_reverts_first_attempt_and_releases_stock(self):
        # 결제사에 보내기 전 실패라 결제되지 않음이 확실: 재고가 묶이지 않도록 되돌림(Codex 2회차 P2)
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        result, _ = await self.confirm(db, {"side_effect": api_error(503, "PAYMENT_NOT_CONFIGURED", "설정 없음")})
        self.assertEqual(result.detail["code"], "PAYMENT_NOT_CONFIGURED")
        self.assertEqual(
            (order.status, order.payment_key, order.payment_attempted_at, order.stock_status, db.stocks), ("failed", None, None, "released", {16: 2})
        )

    async def test_payment_not_configured_keeps_earlier_attempt(self):
        # 앞선 승인 요청(결제키)이 있던 주문은 그 결과를 모르므로 건드리지 않고 결제 확인 중으로 안내
        attempted = datetime.now(timezone.utc) - timedelta(minutes=1)
        order = make_order(payment_key="pk_1", payment_attempted_at=attempted, stock_status="reserved")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        result, _ = await self.confirm(db, {"side_effect": api_error(503, "PAYMENT_NOT_CONFIGURED", "설정 없음")})
        self.assertEqual((result.status_code, result.detail["code"]), (503, "PAYMENT_CONFIRMATION_PENDING"))
        self.assertEqual((order.status, order.payment_key, order.stock_status, db.stocks), ("pending", "pk_1", "reserved", {16: 0}))

    async def test_payment_not_configured_revert_failure_is_logged(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        original_commit = db.commit
        calls = 0

        async def fail_second_commit():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("connection lost")
            await original_commit()

        db.commit = fail_second_commit
        with self.assertLogs(ORDERS_MODULE, "ERROR"):
            result, _ = await self.confirm(db, {"side_effect": api_error(503, "PAYMENT_NOT_CONFIGURED", "설정 없음")})
        self.assertEqual(result.detail["code"], "PAYMENT_NOT_CONFIGURED")
        self.assertEqual(db.rollbacks, 1)


# 결제 보정 작업과 결제 완료 반영의 재고 처리
class PaymentLookupStockTests(unittest.IsolatedAsyncioTestCase):
    async def test_unpaid_results_release_stock_once(self):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        for payment in ({"status": "EXPIRED"}, {"status": "ABORTED"}, {"status": "CANCELED"}, None):
            order = make_order(payment_key="pk_1", payment_attempted_at=old, stock_status="reserved")
            db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
            await order_service(db).apply_payment_lookup(1, "pk_1", payment)
            self.assertEqual((order.status, order.payment_key, order.stock_status, db.stocks), ("failed", None, "released", {16: 2}))

    async def test_not_final_results_keep_stock(self):
        recent = datetime.now(timezone.utc) - timedelta(minutes=20)
        for payment in ({"status": "IN_PROGRESS"}, None):
            order = make_order(payment_key="pk_1", payment_attempted_at=recent, stock_status="reserved")
            db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
            with self.assertNoLogs("backend.domain.orders.services.orders", "ERROR"):
                await order_service(db).apply_payment_lookup(1, "pk_1", payment)
            self.assertEqual((order.stock_status, db.stocks), ("reserved", {16: 0}))

    async def test_done_lookup_keeps_existing_reservation(self):
        order = make_order(payment_key="pk_1", stock_status="reserved")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        await order_service(db).apply_payment_lookup(1, "pk_1", done_payment(order))
        self.assertEqual((order.status, order.stock_status, db.stocks, db.lock_sql()), ("paid", "reserved", {16: 0}, []))

    async def test_late_paid_recovery_reserves_again_when_stock_remains(self):
        order = make_order(status="failed", payment_key="pk_1", stock_status="released")
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 5})
        await order_service(db).apply_payment_lookup(1, "pk_1", done_payment(order))
        self.assertEqual((order.status, order.stock_status, db.stocks), ("paid", "reserved", {16: 3}))

    async def test_late_paid_recovery_without_stock_records_shortage(self):
        for state in ("released", None):  # None: 033 이전에 결제키가 저장된 pending 주문
            order = make_order(status="failed" if state else "pending", payment_key="pk_1", stock_status=state)
            db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 1})
            with self.assertLogs(ORDERS_MODULE, "ERROR"):
                await order_service(db).apply_payment_lookup(1, "pk_1", done_payment(order))
            self.assertEqual((order.status, order.stock_status, db.stocks), ("paid", "shortage", {16: 1}))

    async def test_purge_never_deletes_reserved_unpaid_orders(self):
        db = StockDb()
        await order_service(db).purge_unpaid_orders(commit=False)
        self.assertIn("orders.stock_status IS NULL OR orders.stock_status !=", db.sql[0])


# 환불 완료 반영(_mark_refunded) 시 재고 복구
class RefundStockTests(unittest.IsolatedAsyncioTestCase):
    def refund_service(self, db) -> OrderRefundService:
        service = OrderRefundService.__new__(OrderRefundService)
        service.db = db
        return service

    def canceled(self):
        return {"status": "CANCELED", "cancels": [{"cancelStatus": "DONE", "transactionKey": "tx", "canceledAt": "2026-10-08T11:00:00+09:00"}]}

    async def test_refund_completion_releases_stock_once(self):
        order = make_order(status="refunding", payment_key="pk_1", stock_status="reserved", refund_attempt_count=1)
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
        service = self.refund_service(db)
        await service._mark_refunded(order, self.canceled())
        await service._mark_refunded(order, self.canceled())  # 다른 경로가 다시 반영해도 한 번만 복구
        self.assertEqual((order.status, order.stock_status, db.stocks), ("refunded", "released", {16: 2}))

    async def test_orders_without_reservation_are_not_restored(self):
        for state in (None, "shortage"):
            order = make_order(status="refunding", payment_key="pk_1", stock_status=state, refund_attempt_count=1)
            db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 0})
            await self.refund_service(db)._mark_refunded(order, self.canceled())
            self.assertEqual((order.status, order.stock_status, db.stocks), ("refunded", state, {16: 0}))

    def test_revert_to_paid_does_not_touch_stock(self):
        order = make_order(status="refunding", stock_status="reserved", refund_attempt_count=1)
        OrderRefundService._apply_revert(order, "거절")
        self.assertEqual((order.status, order.stock_status), ("paid", "reserved"))


# 주문 생성은 재고를 확인만 하고 차감하지 않음
class CreateOrderStockTests(unittest.IsolatedAsyncioTestCase):
    def request(self, quantity):
        from backend.domain.orders.schemas.orders import OrderCreateRequest

        return OrderCreateRequest.model_validate(
            {
                "items": [{"product_id": 16, "quantity": quantity}],
                "from_cart": False,
                "shipping": {
                    "recipient_name": "홍길동",
                    "recipient_phone": "010-1234-5678",
                    "postcode": "04524",
                    "address": "서울 중구 세종대로 110",
                    "address_detail": "1층",
                },
            }
        )

    async def test_create_order_rejects_quantity_over_stock_without_deducting(self):
        product = SimpleNamespace(id=16, name="립밤", price=9900, stock=2, image_path="p.jpg")
        db = StockDb(products=[product])
        db.add = lambda _row: self.fail("주문을 만들면 안 됨")
        with self.assertRaises(HTTPException) as raised:
            await order_service(db).create_order("token", self.request(3))
        self.assertEqual(raised.exception.detail["code"], "OUT_OF_STOCK")
        self.assertEqual(raised.exception.detail["stock_shortages"], [{"product_id": 16, "name": "립밤", "available": 2}])
        self.assertEqual(product.stock, 2)


ProductRow = namedtuple("ProductRow", "name stock")  # SQLAlchemy Row처럼 위치·이름 모두로 읽음


class Rows:
    def __init__(self, rows, rowcount=0):
        self.rows = list(rows)
        self.rowcount = rowcount

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.rows[0]

    def all(self):
        return self.rows


# 장바구니 서비스용 메모리 DB: 판매 중 상품(이름·재고)과 담긴 수량만 흉내 내고 INSERT·UPDATE 문장을 기록
class CartDb:
    def __init__(self, products, cart=None):
        self.products = products  # {product_id: (name, stock)}
        self.cart = dict(cart or {})
        self.writes = []
        self.commits = 0

    async def execute(self, statement, _params=None):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        params = compiled.params
        product_id = next((value for key, value in params.items() if key.startswith(("id_", "product_id"))), None)
        if sql.startswith(("INSERT", "UPDATE")):
            self.writes.append((sql.split()[0], params))
            return Rows([], rowcount=1 if product_id in self.cart or sql.startswith("INSERT") else 0)
        if sql.startswith("SELECT cart_items.quantity"):
            return Rows([self.cart[product_id]] if product_id in self.cart else [])
        if sql.startswith("SELECT products.name, products.stock"):
            return Rows([ProductRow(*self.products[product_id])] if product_id in self.products else [])
        raise AssertionError(sql)

    async def commit(self):
        self.commits += 1


def cart_service(db):
    from backend.domain.carts.services.carts import CartService

    service = CartService.__new__(CartService)
    service.db = db
    service.user_service = SimpleNamespace(_get_user_from_access_token=AsyncMock(return_value=SimpleNamespace(id=7)))
    service._cart_payload = AsyncMock(return_value={"items": []})
    return service


# 장바구니 담기·수량 변경·병합의 재고 확인(최종 보장은 결제 승인 직전 차감)
class CartStockTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_rejects_sold_out_and_over_stock_including_cart_quantity(self):
        from backend.domain.carts.schemas.carts import CartAddRequest

        for products, cart, quantity, available in (({16: ("립밤", 0)}, {}, 1, 0), ({16: ("립밤", 2)}, {16: 1}, 2, 2)):
            db = CartDb(products, cart)
            with self.assertRaises(HTTPException) as raised:
                await cart_service(db).add_item("t", CartAddRequest(product_id=16, quantity=quantity))
            self.assertEqual(raised.exception.detail["code"], "OUT_OF_STOCK")
            self.assertEqual(raised.exception.detail["stock_shortages"][0]["available"], available)
            self.assertEqual((db.writes, db.commits), ([], 0))
        db = CartDb({16: ("립밤", 2)}, {16: 1})
        await cart_service(db).add_item("t", CartAddRequest(product_id=16, quantity=1))
        self.assertEqual(db.writes[0][0], "INSERT")

    async def test_set_quantity_limits_only_increases(self):
        db = CartDb({16: ("립밤", 2)}, {16: 1})
        with self.assertRaises(HTTPException) as raised:
            await cart_service(db).set_quantity("t", 16, 3)
        self.assertEqual(raised.exception.detail["message"], "'립밤' 상품은 2개 남아 있습니다.")
        await cart_service(db).set_quantity("t", 16, 2)
        db = CartDb({16: ("립밤", 0)}, {16: 5})  # 재고가 줄어 이미 초과한 줄도 줄이기는 허용
        await cart_service(db).set_quantity("t", 16, 3)
        self.assertEqual(db.writes[0][0], "UPDATE")

    async def test_merge_skips_sold_out_and_caps_to_stock_without_lowering_existing(self):
        from backend.domain.carts.schemas.carts import CartMergeRequest

        db = CartDb({16: ("립밤", 2), 3: ("크림", 0), 4: ("토너", 5), 5: ("세럼", 10)}, {4: 6})
        request = CartMergeRequest(items=[
            {"product_id": 16, "quantity": 3}, {"product_id": 3, "quantity": 1}, {"product_id": 4, "quantity": 1}, {"product_id": 5, "quantity": 2},
        ])
        with patch("backend.domain.carts.services.carts.require_available_product",
                   AsyncMock(side_effect=lambda _db, product_id: db.products[product_id])):
            result = await cart_service(db).merge("t", request)
        self.assertEqual(
            result["adjusted"],
            [{"product_id": 16, "name": "립밤", "available": 2}, {"product_id": 3, "name": "크림", "available": 0},
             {"product_id": 4, "name": "토너", "available": 5}],
        )
        written = {params["product_id_m0"] if "product_id_m0" in params else params["product_id"]: params.get("quantity_m0", params.get("quantity"))
                   for _, params in db.writes}
        self.assertEqual(written, {16: 2, 5: 2})  # 품절(3)은 건너뛰고, 이미 재고보다 많이 담긴 토너(4)는 그대로


# 관리자 재고 수정의 동시 변경 감지와 주문서 재고 확인
class AdminStockTests(unittest.IsolatedAsyncioTestCase):
    def product_service(self, current):
        from backend.domain.products.services.products import ProductService

        service = ProductService.__new__(ProductService)
        sql = []

        class Db:
            async def execute(self, statement, _params=None):
                sql.append(str(statement.compile(dialect=postgresql.dialect())))
                return Rows([current])

        service.db = Db()
        return service, sql

    async def test_stock_change_requires_unchanged_base(self):
        from backend.domain.products.models.products import Product

        service, sql = self.product_service(current=98)
        product = Product(id=16, stock=100)
        with self.assertRaises(HTTPException) as raised:
            await service._apply_stock_change(product, 50, 100)  # 화면은 100을 보고 있었는데 그사이 2개 팔림
        self.assertEqual((raised.exception.status_code, raised.exception.detail["code"]), (409, "STOCK_CHANGED"))
        self.assertEqual(raised.exception.detail["current_stock"], 98)
        self.assertEqual(product.stock, 100)
        self.assertIn("FOR UPDATE", sql[0])
        service, _ = self.product_service(current=98)
        self.assertEqual(await service._apply_stock_change(product, 50, 98), 98)
        self.assertEqual(product.stock, 50)

    async def test_catalog_availability_marks_missing_products_not_on_sale(self):
        from backend.domain.products.services.products import ProductService

        service = ProductService.__new__(ProductService)

        class Db:
            async def execute(self, _statement, _params=None):
                return Rows([(16, 2)])

        service.db = Db()
        result = await service.catalog_availability([16, 9, 16])
        self.assertEqual(result["items"], [{"id": 16, "on_sale": True, "stock": 2}, {"id": 9, "on_sale": False, "stock": 0}])


# 확정 거절 반영 커밋이 실패해도 거절 안내는 그대로 돌려주고 주문은 보정 작업 대상으로 남음
class RejectionCommitFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejection_commit_failure_still_reports_rejection(self):
        order = make_order()
        db = StockDb(order, lines=[(16, "립밤", 2)], stocks={16: 2})
        original_commit = db.commit
        calls = 0

        async def fail_second_commit():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("connection lost")
            await original_commit()

        db.commit = fail_second_commit
        rejection = api_error(400, "PAYMENT_FAILED", "카드 거절", gateway_code="REJECT_CARD_COMPANY", gateway_status=400)
        service = order_service(db)
        request = OrderConfirmRequest(payment_key="pk_1", order_id=order.order_number, amount=order.total_amount)
        with patch(f"{ORDERS_MODULE}.toss.confirm_payment", AsyncMock(side_effect=rejection)), \
                self.assertLogs(ORDERS_MODULE, "ERROR"), self.assertRaises(HTTPException) as raised:
            await service.confirm_payment("token", request)
        self.assertEqual(raised.exception.detail["code"], "PAYMENT_FAILED")
        self.assertEqual(db.rollbacks, 1)


# 033 적용 스크립트가 DO 블록 안의 세미콜론에서 문장을 자르지 않고, 초기값은 컬럼을 처음 만들 때만 채우는지
class StockMigrationScriptTests(unittest.TestCase):
    def test_split_keeps_do_block_whole(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "apply_product_stock.py"
        spec = importlib.util.spec_from_file_location("apply_product_stock", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        statements = module.split_statements(module.MIGRATION_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(statements), 12)
        block = statements[0]
        self.assertTrue(block.startswith("DO $$") and block.endswith("$$"))
        self.assertIn("IF NOT EXISTS", block)
        self.assertIn("ADD COLUMN stock INTEGER NOT NULL DEFAULT 100;", block)
        self.assertIn("UPDATE products SET stock = 2 WHERE id = 16 AND name = '데일리 무향 립밤 4g';", block)
        self.assertIn("ALTER COLUMN stock SET DEFAULT 0;", block)
        self.assertTrue(any("ALTER COLUMN stock SET NOT NULL" in statement for statement in statements))
        self.assertTrue(any("CHECK (stock >= 0)" in statement for statement in statements))


# 033 확인 스크립트가 이름만이 아니라 컬럼·CHECK 정의까지 검사하는지(Codex P2)
class StockCheckScriptTests(unittest.TestCase):
    def load(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "check_product_stock.py"
        spec = importlib.util.spec_from_file_location("check_product_stock", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def good(self):
        definitions = {
            ("products", "stock"): {"data_type": "integer", "is_nullable": "NO", "column_default": "0", "character_maximum_length": None},
            ("orders", "stock_status"): {
                "data_type": "character varying", "is_nullable": "YES", "column_default": None, "character_maximum_length": 20,
            },
        }
        constraints = {
            "ck_products_stock_nonnegative": "CHECK ((stock >= 0))",
            "ck_orders_stock_status": "CHECK (((stock_status IS NULL) OR ((stock_status)::text = ANY ((ARRAY['reserved'::character varying, "
            "'released'::character varying, 'shortage'::character varying])::text[]))))",
        }
        return definitions, constraints

    def test_expected_definitions_pass(self):
        module = self.load()
        self.assertEqual(module.definition_problems(*self.good()), ([], [], []))
        definitions, constraints = self.good()
        definitions[("products", "stock")]["column_default"] = "'0'::integer"
        self.assertEqual(module.definition_problems(definitions, constraints), ([], [], []))

    def test_wrong_column_or_check_definitions_fail(self):
        module = self.load()
        for key, field, value in (
            (("products", "stock"), "is_nullable", "YES"),
            (("products", "stock"), "column_default", "100"),
            (("products", "stock"), "data_type", "bigint"),
            (("orders", "stock_status"), "character_maximum_length", 10),
        ):
            definitions, constraints = self.good()
            definitions[key][field] = value
            self.assertEqual(len(module.definition_problems(definitions, constraints)[0]), 1, (key, field))
        definitions, constraints = self.good()
        constraints["ck_products_stock_nonnegative"] = "CHECK ((stock >= -1))"
        del constraints["ck_orders_stock_status"]
        _, missing, wrong = module.definition_problems(definitions, constraints)
        self.assertEqual((missing, wrong), (["ck_orders_stock_status"], ["ck_products_stock_nonnegative"]))
