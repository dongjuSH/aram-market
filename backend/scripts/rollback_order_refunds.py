# 주문 환불(031) 되돌리기: 코드를 먼저 되돌린 뒤 실행. 환불·취소 요청 기록이 하나라도 있으면 거래 기록 보존을 위해 중단

import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine

ROLLBACK_STATEMENTS = (
    "DROP INDEX IF EXISTS ix_orders_refunding_attempted_at",
    "DROP INDEX IF EXISTS ix_orders_cancel_requested",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cancel_request_status",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_cancel_request_reason_code",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_actor",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_reason_code",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_refund_attempt_count",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_request_status",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_requested_at",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_request_reason_code",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_request_reason_detail",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_rejected_at",
    "ALTER TABLE orders DROP COLUMN IF EXISTS cancel_reject_reason",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_actor",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_reason_code",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_reason_detail",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_attempt_count",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_attempted_at",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refunded_at",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_transaction_key",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_failure_message",
    "ALTER TABLE orders DROP COLUMN IF EXISTS refund_delivery_status",
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_status",
    "ALTER TABLE orders ADD CONSTRAINT ck_orders_status CHECK (status IN ('pending', 'paid', 'failed'))",
)


# 환불 상태 주문이나 취소 요청 기록이 남아 있으면 종료 코드 1로 중단, 없으면 한 트랜잭션으로 되돌림
async def run() -> int:
    async with engine.begin() as connection:
        has_columns = (
            await connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'orders' AND column_name = 'cancel_request_status')"
                )
            )
        ).scalar_one()
        refund_rows = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM orders WHERE status IN ('refunding', 'refunded')"
                    + (" OR cancel_request_status IS NOT NULL OR refund_attempt_count > 0" if has_columns else "")
                )
            )
        ).scalar_one()
        if not refund_rows:
            for statement in ROLLBACK_STATEMENTS:
                await connection.execute(text(statement))
    await engine.dispose()
    if refund_rows:
        print(f"rollback aborted: refund_or_cancel_rows={refund_rows}")
        return 1
    print("order refund migration rolled back")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
