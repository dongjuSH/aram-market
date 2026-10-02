# 회원 이름·휴대폰 컬럼을 제거(값이 남아 있는 회원이 있으면 데이터 보호를 위해 중단)

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "028_drop_user_profile_fields.sql"


# 컬럼이 남아 있으면 저장된 값이 없는지 먼저 확인한 뒤 마이그레이션 SQL 실행
async def run() -> None:
    statements = [
        statement.strip()
        for statement in "\n".join(
            line for line in MIGRATION_FILE.read_text(encoding="utf-8").splitlines() if not line.startswith("--")
        ).split(";")
        if statement.strip()
    ]
    async with engine.begin() as connection:
        columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'users' AND column_name IN ('name', 'phone')"
                    )
                )
            ).scalars()
        )
        if columns:
            conditions = " OR ".join(f"{column} IS NOT NULL" for column in sorted(columns))
            filled = (await connection.execute(text(f"SELECT COUNT(*) FROM users WHERE {conditions}"))).scalar_one()
            if filled:
                raise SystemExit(f"이름·휴대폰이 저장된 회원 {filled}명이 있어 중단합니다. 데이터를 먼저 확인하세요.")
        for statement in statements:
            await connection.execute(text(statement))
    print("drop user profile fields migration applied")


if __name__ == "__main__":
    asyncio.run(run())
