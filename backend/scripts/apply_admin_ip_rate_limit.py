# 관리자 계정 잠금 컬럼을 제거하는 IP 제한 전환 마이그레이션 실행

import asyncio
from pathlib import Path

from backend.core.database import engine


MIGRATION_PATH = Path(__file__).resolve().parent.parent / "migrations" / "009_admin_ip_rate_limit.sql"


# 하나의 트랜잭션으로 관리자 IP 제한 전환 마이그레이션 적용
async def run() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    async with engine.connect() as connection:
        raw_connection = await connection.get_raw_connection()
        await raw_connection.driver_connection.execute(sql)
    await engine.dispose()
    print("admin IP rate-limit migration applied")


if __name__ == "__main__":
    asyncio.run(run())
