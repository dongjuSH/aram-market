# 회원 이름·휴대폰 컬럼과 입력 현황을 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine

NEEDED_COLUMNS = {"name", "phone"}


# 컬럼 존재 여부와 이름·휴대폰이 비어 있는 회원 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users'")
                )
            )
            .scalars()
            .all()
        )
        print("profile_columns_ok=" + str(NEEDED_COLUMNS <= columns).lower())
        if not NEEDED_COLUMNS <= columns:
            return
        missing = (await connection.execute(text("SELECT COUNT(*) FROM users WHERE name IS NULL OR phone IS NULL"))).scalar_one()
        print(f"users_without_name_or_phone={missing}")


if __name__ == "__main__":
    asyncio.run(run())
