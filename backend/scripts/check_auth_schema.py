# 단일 관리자 테이블 구조와 계정 수를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


EXPECTED_COLUMNS = {
    "id",
    "username",
    "password",
    "created_at",
    "is_active",
    "auth_version",
}


# 관리자 컬럼·제약조건·아이디·계정 수 점검
async def run() -> None:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'admin_accounts'"
                    )
                )
            ).scalars().all()
        )
        accounts = (
            await connection.execute(
                text("SELECT id, username, is_active FROM public.admin_accounts ORDER BY id")
            )
        ).mappings().all()
        constraints = (
            await connection.execute(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_schema = 'public' AND table_name = 'admin_accounts' "
                    "ORDER BY constraint_name"
                )
            )
        ).scalars().all()

    print("columns=" + ",".join(sorted(columns)))
    print("columns_match=" + str(columns == EXPECTED_COLUMNS).lower())
    print(f"account_count={len(accounts)}")
    for account in accounts:
        print(f"id={account['id']} username={account['username']} active={account['is_active']}")
    print("constraints=" + ",".join(constraints))


if __name__ == "__main__":
    asyncio.run(run())
