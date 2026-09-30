# 배송지 주소록 테이블·기본 배송지 제약과 회원 주소 컬럼 제거 여부를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 테이블·인덱스 존재, 기본 배송지 중복, 회원 주소 컬럼 잔존 여부 출력
async def run() -> None:
    async with engine.connect() as connection:
        has_table = bool((await connection.execute(text("SELECT to_regclass('public.user_addresses') IS NOT NULL"))).scalar_one())
        print("addresses_table=" + str(has_table).lower())
        stale = (
            await connection.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users' AND column_name IN ('postcode', 'address', 'address_detail')")
            )
        ).scalars().all()
        print("users_address_columns_removed=" + str(not stale).lower())
        if not has_table:
            return
        total = (await connection.execute(text("SELECT COUNT(*) FROM user_addresses"))).scalar_one()
        duplicated_default = (
            await connection.execute(text("SELECT COUNT(*) FROM (SELECT user_id FROM user_addresses WHERE is_default GROUP BY user_id HAVING COUNT(*) > 1) AS d"))
        ).scalar_one()
        over_limit = (
            await connection.execute(text("SELECT COUNT(*) FROM (SELECT user_id FROM user_addresses GROUP BY user_id HAVING COUNT(*) > 10) AS o"))
        ).scalar_one()
        print(f"addresses={total} users_with_multiple_defaults={duplicated_default} users_over_limit={over_limit}")


if __name__ == "__main__":
    asyncio.run(run())
