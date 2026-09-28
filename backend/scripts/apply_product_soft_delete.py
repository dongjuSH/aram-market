# 기존 상품 테이블에 소프트 삭제 컬럼과 활성 상품 부분 고유 인덱스 적용

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 반복 실행 가능한 상품 소프트 삭제 마이그레이션
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'"))
        await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))

        duplicate_code = (
            await connection.execute(
                text(
                    "SELECT user_id, code FROM products WHERE status = 'active' "
                    "GROUP BY user_id, code HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
        ).first()
        duplicate_order = (
            await connection.execute(
                text(
                    "SELECT user_id, display_order FROM products WHERE status = 'active' "
                    "GROUP BY user_id, display_order HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
        ).first()
        if duplicate_code or duplicate_order:
            raise RuntimeError("활성 상품의 중복 상품코드 또는 노출순서를 먼저 정리해 주세요.")

        await connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS uq_products_user_code"))
        await connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS uq_products_user_display_order"))
        await connection.execute(text("DROP INDEX IF EXISTS uq_products_user_code"))
        await connection.execute(text("DROP INDEX IF EXISTS uq_products_user_display_order"))
        await connection.execute(
            text(
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_status') THEN "
                "ALTER TABLE products ADD CONSTRAINT ck_products_status CHECK (status IN ('active', 'deleted')); "
                "END IF; END $$"
            )
        )
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_status ON products(status)"))
        await connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_code "
                "ON products(user_id, code) WHERE status = 'active'"
            )
        )
        await connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_user_display_order "
                "ON products(user_id, display_order) WHERE status = 'active'"
            )
        )

    print("product soft-delete migration applied")


if __name__ == "__main__":
    asyncio.run(run())
