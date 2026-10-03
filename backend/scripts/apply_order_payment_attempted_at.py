# 결제 승인 시도 시각 컬럼을 기존 DB에 적용(재실행 안전)

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "030_order_payment_attempted_at.sql"


# 세미콜론 기준으로 마이그레이션 SQL을 한 문장씩 실행(주석 줄 제외)
async def run() -> None:
    statements = [
        statement.strip()
        for statement in "\n".join(
            line for line in MIGRATION_FILE.read_text(encoding="utf-8").splitlines() if not line.startswith("--")
        ).split(";")
        if statement.strip()
    ]
    async with engine.begin() as connection:
        for statement in statements:
            await connection.execute(text(statement))
    print("order payment attempt migration applied")


if __name__ == "__main__":
    asyncio.run(run())
