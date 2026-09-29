# 찜 목록과 주문 테이블을 기존 DB에 적용

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILES = [
    Path(__file__).resolve().parents[1] / "migrations" / "021_wishlist_items.sql",
    Path(__file__).resolve().parents[1] / "migrations" / "022_orders.sql",
]


# 세미콜론 기준으로 마이그레이션 SQL을 한 문장씩 실행(주석 줄 제외)
async def run() -> None:
    async with engine.begin() as connection:
        for migration_file in MIGRATION_FILES:
            statements = [
                statement.strip()
                for statement in "\n".join(
                    line for line in migration_file.read_text(encoding="utf-8").splitlines() if not line.startswith("--")
                ).split(";")
                if statement.strip()
            ]
            for statement in statements:
                await connection.execute(text(statement))
    print("wishlist and orders migrations applied")


if __name__ == "__main__":
    asyncio.run(run())
