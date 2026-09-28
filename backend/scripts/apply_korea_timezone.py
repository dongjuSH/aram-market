# Supabase PostgreSQL의 기본 세션 시간대를 한국 시간으로 설정

import asyncio

from sqlalchemy import text

from backend.core.database import engine


async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "DO $$ BEGIN "
                "EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'Asia/Seoul'); "
                "EXECUTE format('ALTER ROLE %I SET timezone TO %L', current_user, 'Asia/Seoul'); "
                "END $$"
            )
        )
        await connection.execute(text("SET TIME ZONE 'Asia/Seoul'"))
    await engine.dispose()
    print("database timezone set to Asia/Seoul")


if __name__ == "__main__":
    asyncio.run(run())
