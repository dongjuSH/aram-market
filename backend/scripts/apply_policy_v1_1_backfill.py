# 약관 v1.1 시행에 맞춰 기존 활성 회원의 서비스·개인정보 동의 이력을 추가(재실행 안전)

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "027_policy_v1_1_backfill.sql"


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
    print("policy v1.1 consent backfill applied")


if __name__ == "__main__":
    asyncio.run(run())
