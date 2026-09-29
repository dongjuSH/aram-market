# 후기·문의 테이블과 저장 건수를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 테이블 존재 여부와 행 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        for table in ("product_reviews", "product_inquiries"):
            exists = bool((await connection.execute(text(f"SELECT to_regclass('public.{table}') IS NOT NULL"))).scalar_one())
            count = (await connection.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one() if exists else 0
            print(f"{table}: exists={str(exists).lower()} rows={count}")


if __name__ == "__main__":
    asyncio.run(run())
