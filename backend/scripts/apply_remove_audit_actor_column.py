# 단일 관리자 감사 로그의 중복 작업자 참조 컬럼 제거

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 반복 실행 가능한 감사 로그 작업자 참조 제거 마이그레이션
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE product_audit_logs "
                "DROP CONSTRAINT IF EXISTS product_audit_logs_actor_admin_id_fkey"
            )
        )
        await connection.execute(text("DROP INDEX IF EXISTS ix_product_audit_logs_actor_admin_id"))
        await connection.execute(text("ALTER TABLE product_audit_logs DROP COLUMN IF EXISTS actor_admin_id"))

    print("product audit actor column removed")


if __name__ == "__main__":
    asyncio.run(run())
