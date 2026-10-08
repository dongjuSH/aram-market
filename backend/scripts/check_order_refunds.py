# 주문 환불(031) 컬럼·제약·인덱스 적용 여부를 확인하는 읽기 전용 스크립트(누락 시 종료 코드 1)

import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine

EXPECTED_COLUMNS = (
    "cancel_request_status",
    "cancel_requested_at",
    "cancel_request_reason_code",
    "cancel_request_reason_detail",
    "cancel_rejected_at",
    "cancel_reject_reason",
    "refund_actor",
    "refund_reason_code",
    "refund_reason_detail",
    "refund_attempt_count",
    "refund_attempted_at",
    "refunded_at",
    "refund_transaction_key",
    "refund_failure_message",
    "refund_delivery_status",
)
EXPECTED_CONSTRAINTS = (
    "ck_orders_status",
    "ck_orders_cancel_request_status",
    "ck_orders_cancel_request_reason_code",
    "ck_orders_refund_actor",
    "ck_orders_refund_reason_code",
    "ck_orders_refund_attempt_count",
)
EXPECTED_INDEXES = ("ix_orders_refunding_attempted_at", "ix_orders_cancel_requested")


# 컬럼·제약·인덱스가 모두 있고 주문 상태 제약이 환불 상태를 허용하면 종료 코드 0
async def run() -> int:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'orders'")
                )
            ).scalars()
        )
        constraints = dict(
            (
                await connection.execute(
                    text(
                        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid = 'public.orders'::regclass AND contype = 'c'"
                    )
                )
            ).all()
        )
        indexes = set(
            (
                await connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'orders'"))
            ).scalars()
        )
        status_counts = (await connection.execute(text("SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY status"))).all()
        greatest_ignores_nulls = bool(
            await connection.scalar(
                text(
                    "SELECT GREATEST(NULL::timestamptz, TIMESTAMPTZ '2026-01-01 00:00:00+09') "
                    "= TIMESTAMPTZ '2026-01-01 00:00:00+09'"
                )
            )
        )
    await engine.dispose()

    missing_columns = [name for name in EXPECTED_COLUMNS if name not in columns]
    missing_constraints = [name for name in EXPECTED_CONSTRAINTS if name not in constraints]
    missing_indexes = [name for name in EXPECTED_INDEXES if name not in indexes]
    status_definition = constraints.get("ck_orders_status", "")
    status_allows_refund = "refunding" in status_definition and "refunded" in status_definition
    print("missing_columns=" + (",".join(missing_columns) or "none"))
    print("missing_constraints=" + (",".join(missing_constraints) or "none"))
    print("missing_indexes=" + (",".join(missing_indexes) or "none"))
    print(f"status_allows_refund={str(status_allows_refund).lower()}")
    print(f"greatest_ignores_nulls={str(greatest_ignores_nulls).lower()}")
    print("orders_by_status=" + ", ".join(f"{status}:{count}" for status, count in status_counts))
    ok = not missing_columns and not missing_constraints and not missing_indexes and status_allows_refund and greatest_ignores_nulls
    print("order_refunds_ok=" + str(ok).lower())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
