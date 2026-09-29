# 관리자 리프레시 토큰 테이블을 기존 DB에 적용

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "018_admin_refresh_tokens.sql"


# 세미콜론 기준으로 마이그레이션 SQL을 한 문장씩 실행(주석 줄 제외)
async def run() -> None:
    statements = [
        statement.strip()
        for statement in "\n".join(
            line for line in MIGRATION_FILE.read_text(encoding="utf-8").splitlines() if not line.startswith("--")
        ).split(";")
        if statement.strip()
    ]
    async with engine.begin() as connection:
        for statement in statements:
            await connection.execute(text(statement))
    print("admin refresh tokens migration applied")


if __name__ == "__main__":
    asyncio.run(run())
