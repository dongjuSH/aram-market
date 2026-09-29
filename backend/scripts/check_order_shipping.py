# 주문 배송지·배송 상태 컬럼과 상태 분포를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine

NEEDED_COLUMNS = {
    "recipient_name",
    "recipient_phone",
    "postcode",
    "address",
    "address_detail",
    "delivery_memo",
    "delivery_status",
    "shipped_at",
    "delivered_at",
}


# 컬럼 존재 여부와 배송 상태별 결제 완료 주문 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'orders'")
                )
            )
            .scalars()
            .all()
        )
        print("shipping_columns_ok=" + str(NEEDED_COLUMNS <= columns).lower())
        if "delivery_status" not in columns:
            return
        rows = (await connection.execute(text("SELECT delivery_status, COUNT(*) FROM orders WHERE status = 'paid' GROUP BY delivery_status"))).all()
        print("paid_orders_by_delivery_status=" + str({status: count for status, count in rows}))


if __name__ == "__main__":
    asyncio.run(run())
