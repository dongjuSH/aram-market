# 주문 환불·취소 요청 상태와 컬럼(031)을 기존 DB에 적용(재실행 안전, 적용 전 주문 상태별 건수 출력)

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "031_order_refunds.sql"


# 세미콜론 기준으로 마이그레이션 SQL을 한 문장씩 실행(주석 줄 제외)
async def run() -> None:
    statements = [
        statement.strip()
        for statement in "\n".join(
            line for line in MIGRATION_FILE.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("--")
        ).split(";")
        if statement.strip()
    ]
    async with engine.begin() as connection:
        rows = (await connection.execute(text("SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY status"))).all()
        print("orders_by_status_before=" + ", ".join(f"{status}:{count}" for status, count in rows))
        for statement in statements:
            await connection.execute(text(statement))
    await engine.dispose()
    print("order refund migration applied")


if __name__ == "__main__":
    asyncio.run(run())
