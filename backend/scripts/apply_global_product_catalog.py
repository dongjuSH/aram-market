# 기존 관리자별 상품을 등록·수정자 감사정보가 있는 전역 상품 카탈로그로 전환

import asyncio

from sqlalchemy import text

from backend.core.database import engine


async def run() -> None:
    async with engine.begin() as connection:
        duplicate_code = (
            await connection.execute(
                text(
                    "SELECT code FROM products WHERE status = 'active' "
                    "GROUP BY code HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
        ).first()
        duplicate_order = (
            await connection.execute(
                text(
                    "SELECT display_order FROM products WHERE status = 'active' "
                    "GROUP BY display_order HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
        ).first()
        if duplicate_code or duplicate_order:
            raise RuntimeError("전체 활성 상품의 중복 상품코드 또는 노출순서를 먼저 정리해 주세요.")

        await connection.execute(
            text(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'products' AND column_name = 'user_id') "
                "AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'products' AND column_name = 'created_by_user_id') THEN "
                "ALTER TABLE products RENAME COLUMN user_id TO created_by_user_id; "
                "END IF; END $$"
            )
        )
        await connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS updated_by_user_id INTEGER"))
        await connection.execute(text("UPDATE products SET updated_by_user_id = created_by_user_id WHERE updated_by_user_id IS NULL"))
        await connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_user_id_fkey"))
        await connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_created_by_user_id_fkey"))
        await connection.execute(text("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_updated_by_user_id_fkey"))
        await connection.execute(text("ALTER TABLE products ALTER COLUMN created_by_user_id DROP NOT NULL"))
        await connection.execute(
            text(
                "ALTER TABLE products ADD CONSTRAINT products_created_by_user_id_fkey "
                "FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL"
            )
        )
        await connection.execute(
            text(
                "ALTER TABLE products ADD CONSTRAINT products_updated_by_user_id_fkey "
                "FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL"
            )
        )
        await connection.execute(text("DROP INDEX IF EXISTS ix_products_user_id"))
        await connection.execute(text("DROP INDEX IF EXISTS uq_products_active_user_code"))
        await connection.execute(text("DROP INDEX IF EXISTS uq_products_active_user_display_order"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_created_by_user_id ON products(created_by_user_id)"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_updated_by_user_id ON products(updated_by_user_id)"))
        await connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_code ON products(code) WHERE status = 'active'")
        )
        await connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_active_display_order "
                "ON products(display_order) WHERE status = 'active'"
            )
        )

    print("global product catalog migration applied")


if __name__ == "__main__":
    asyncio.run(run())
