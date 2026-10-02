# 회원 이름·휴대폰 컬럼이 제거됐는지 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# users 테이블에 name·phone 컬럼이 남아 있는지 출력
async def run() -> None:
    async with engine.connect() as connection:
        remaining = (
            await connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'users' AND column_name IN ('name', 'phone')"
                )
            )
        ).scalars().all()
        print("users_name_phone_removed=" + str(not remaining).lower())


if __name__ == "__main__":
    asyncio.run(run())
