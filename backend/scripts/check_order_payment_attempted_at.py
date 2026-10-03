# 결제 승인 시도 시각 컬럼·인덱스와 결제키가 있는 주문의 시각 누락 여부를 확인하는 읽기 전용 스크립트

import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine


# 컬럼·인덱스가 없거나 결제키가 있는데 시도 시각이 빈 주문이 있으면 종료 코드 1(배포 차단용)
async def run() -> int:
    async with engine.connect() as connection:
        column_exists = (
            await connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'orders' AND column_name = 'payment_attempted_at')"
                )
            )
        ).scalar_one()
        index_exists = (
            await connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'orders' AND indexname = 'ix_orders_payment_attempted_at')"
                )
            )
        ).scalar_one()
        missing_attempt_time: int | str = "not_checked"  # 컬럼이 없으면 확인할 수 없음
        if column_exists:
            missing_attempt_time = (
                await connection.execute(
                    text("SELECT COUNT(*) FROM orders WHERE payment_key IS NOT NULL AND payment_attempted_at IS NULL")
                )
            ).scalar_one()
        print(f"payment_attempted_at_column={str(bool(column_exists)).lower()}")
        print(f"payment_attempted_at_index={str(bool(index_exists)).lower()}")
        print(f"payment_keys_without_attempt_time={missing_attempt_time}")
    await engine.dispose()
    ok = bool(column_exists) and bool(index_exists) and missing_attempt_time == 0
    print("payment_attempted_at_ok=" + str(ok).lower())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
