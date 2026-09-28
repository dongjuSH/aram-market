# 기존 계정을 제거하고 단일 관리자 전용 DB 구조로 변경하는 마이그레이션 실행

import asyncio
from pathlib import Path

from backend.core.database import engine


MIGRATION_PATH = Path(__file__).resolve().parent.parent / "migrations" / "008_single_admin_account.sql"


# 하나의 트랜잭션으로 단일 관리자 마이그레이션 적용
async def run() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    async with engine.connect() as connection:
        raw_connection = await connection.get_raw_connection()
        await raw_connection.driver_connection.execute(sql)
    await engine.dispose()
    print("single-admin migration applied; admin_accounts is empty")


if __name__ == "__main__":
    asyncio.run(run())
