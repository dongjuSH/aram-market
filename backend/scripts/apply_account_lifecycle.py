# 기존 users 테이블의 탈퇴 생명주기 컬럼·인덱스·상태 제약 추가

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 기존 users 테이블에 탈퇴 상태 컬럼 및 허용값 제약 추가
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'")
        )
        await connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMPTZ")
        )
        await connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0")
        )
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users (status)"))

        constraint_exists = (
            await connection.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_status'")
            )
        ).scalar_one_or_none()
        if not constraint_exists:
            await connection.execute(
                text(
                    "ALTER TABLE users ADD CONSTRAINT ck_users_status "
                    "CHECK (status IN ('active', 'pending_deletion', 'withdrawn'))"
                )
            )

    print("account lifecycle migration applied")


if __name__ == "__main__":
    asyncio.run(run())
