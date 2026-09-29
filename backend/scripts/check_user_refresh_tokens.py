# 리프레시 토큰 테이블과 현재 저장 건수를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 테이블 존재 여부와 전체·미폐기 토큰 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        has_table = bool((await connection.execute(text("SELECT to_regclass('public.user_refresh_tokens') IS NOT NULL"))).scalar_one())
        print("refresh_table=" + str(has_table).lower())
        if not has_table:
            return
        total = (await connection.execute(text("SELECT COUNT(*) FROM user_refresh_tokens"))).scalar_one()
        active = (
            await connection.execute(
                text("SELECT COUNT(*) FROM user_refresh_tokens WHERE revoked_at IS NULL AND expires_at > NOW()")
            )
        ).scalar_one()
        print(f"refresh_tokens_total={total} active={active}")


if __name__ == "__main__":
    asyncio.run(run())
