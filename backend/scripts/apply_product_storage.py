# 기존 상품 테이블의 Storage 경로 컬럼과 노출순서 고유 제약 적용

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 반복 실행 가능한 상품 Storage·노출순서 마이그레이션
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_path VARCHAR(500)"))
        await connection.execute(text("ALTER TABLE products ALTER COLUMN image_data DROP NOT NULL"))

        duplicate_order = (
            await connection.execute(
                text(
                    "SELECT user_id, display_order FROM products "
                    "GROUP BY user_id, display_order HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
        ).first()
        if duplicate_order:
            raise RuntimeError("사용자별 중복 노출순서를 먼저 정리한 뒤 마이그레이션을 다시 실행해 주세요.")

        constraint_exists = (
            await connection.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = 'uq_products_user_display_order'")
            )
        ).scalar_one_or_none()
        if not constraint_exists:
            await connection.execute(
                text(
                    "ALTER TABLE products ADD CONSTRAINT uq_products_user_display_order "
                    "UNIQUE (user_id, display_order)"
                )
            )

    print("product storage and display-order migration applied")


if __name__ == "__main__":
    asyncio.run(run())
