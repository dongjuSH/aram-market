# 기존 users 테이블에 선택 마케팅 수신 동의 컬럼 추가

import asyncio

from sqlalchemy import text

from backend.core.database import engine


async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "marketing_consent BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
    print("user marketing consent migration applied")


if __name__ == "__main__":
    asyncio.run(run())
