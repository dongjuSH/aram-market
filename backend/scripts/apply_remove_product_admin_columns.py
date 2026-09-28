# 단일 관리자 상품 테이블의 중복 관리자 참조 컬럼 제거

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 반복 실행 가능한 상품 관리자 참조 제거 마이그레이션
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE products "
                "DROP CONSTRAINT IF EXISTS products_created_by_admin_id_fkey, "
                "DROP CONSTRAINT IF EXISTS products_updated_by_admin_id_fkey"
            )
        )
        await connection.execute(text("DROP INDEX IF EXISTS ix_products_created_by_admin_id"))
        await connection.execute(text("DROP INDEX IF EXISTS ix_products_updated_by_admin_id"))
        await connection.execute(
            text(
                "ALTER TABLE products "
                "DROP COLUMN IF EXISTS created_by_admin_id, "
                "DROP COLUMN IF EXISTS updated_by_admin_id"
            )
        )

    print("product admin reference columns removed")


if __name__ == "__main__":
    asyncio.run(run())
