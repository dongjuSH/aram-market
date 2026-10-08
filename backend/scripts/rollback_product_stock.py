# 상품 재고(033) 되돌리기: 코드를 먼저 되돌린 뒤 실행. 재고를 차감·복구한 주문 기록이 있으면 --force 없이는 중단

import argparse
import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine

ROLLBACK_STATEMENTS = (
    "ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_stock_status",
    "ALTER TABLE orders DROP COLUMN IF EXISTS stock_status",
    "ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_stock_nonnegative",
    "ALTER TABLE products DROP COLUMN IF EXISTS stock",
)


# 재고 상태가 기록된 주문 수를 출력하고, 있으면 --force일 때만 한 트랜잭션으로 컬럼을 제거(재고 수량도 함께 사라짐)
async def run(force: bool) -> int:
    async with engine.begin() as connection:
        has_column = (
            await connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'orders' AND column_name = 'stock_status')"
                )
            )
        ).scalar_one()
        stock_rows = 0
        if has_column:
            stock_rows = (await connection.execute(text("SELECT COUNT(*) FROM orders WHERE stock_status IS NOT NULL"))).scalar_one()
        print(f"orders_with_stock_status={stock_rows}")
        if stock_rows and not force:
            await connection.rollback()
        else:
            for statement in ROLLBACK_STATEMENTS:
                await connection.execute(text(statement))
    await engine.dispose()
    if stock_rows and not force:
        print("rollback aborted: orders have stock records (rerun with --force to drop them)")
        return 1
    print("product stock migration rolled back")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="상품 재고(033) 되돌리기")
    parser.add_argument("--force", action="store_true", help="재고 기록이 있는 주문이 있어도 컬럼 제거")
    sys.exit(asyncio.run(run(parser.parse_args().force)))
