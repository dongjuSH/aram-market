# 약관 v1.2 시행에 맞춰 기존 활성 회원의 service·privacy v1.2 동의 이력을 추가(032, 재실행 안전)

import asyncio
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "032_policy_v1_2_backfill.sql"


# 주석 줄을 뺀 INSERT 한 문장을 실행하고 추가된 행 수를 출력
async def run() -> None:
    statement = "\n".join(
        line for line in MIGRATION_FILE.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("--")
    ).strip().rstrip(";")
    async with engine.begin() as connection:
        result = await connection.execute(text(statement))
    await engine.dispose()
    print(f"policy v1.2 consents inserted={result.rowcount}")


if __name__ == "__main__":
    asyncio.run(run())
