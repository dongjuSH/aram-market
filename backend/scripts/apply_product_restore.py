# 상품 복원 감사 로그 제약조건 적용

import asyncio

from sqlalchemy import text

from backend.core.database import engine


async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE product_audit_logs DROP CONSTRAINT IF EXISTS ck_product_audit_logs_action")
        )
        await connection.execute(
            text(
                "ALTER TABLE product_audit_logs ADD CONSTRAINT ck_product_audit_logs_action "
                "CHECK (action IN ('created', 'updated', 'deleted', 'restored'))"
            )
        )
    await engine.dispose()
    print("product restore audit constraint applied")


if __name__ == "__main__":
    asyncio.run(run())
