# 인증 마이그레이션 및 충돌 가능 데이터 확인용 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# users 컬럼·중복·제약·인덱스 및 탈퇴 Cron 등록 상태 조회
async def run() -> None:
    async with engine.connect() as connection:
        columns = (
            await connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'users' "
                    "ORDER BY ordinal_position"
                )
            )
        ).scalars().all()
        row_count = (await connection.execute(text("SELECT COUNT(*) FROM users"))).scalar_one()
        duplicate_emails = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1"
                    ") duplicates"
                )
            )
        ).scalar_one()
        duplicate_nicknames = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "SELECT nickname FROM users WHERE nickname IS NOT NULL "
                    "GROUP BY nickname HAVING COUNT(*) > 1"
                    ") duplicates"
                )
            )
        ).scalar_one()
        constraints = (
            await connection.execute(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_schema = 'public' AND table_name = 'users' "
                    "ORDER BY constraint_name"
                )
            )
        ).scalars().all()
        indexes = (
            await connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'users' "
                    "ORDER BY indexname"
                )
            )
        ).scalars().all()
        cron_jobs = (
            await connection.execute(
                text(
                    "SELECT jobname || '|' || schedule || '|active=' || active FROM cron.job "
                    "WHERE jobname = 'purge-withdrawn-users-midnight-kst'"
                )
            )
        ).scalars().all()

    print("columns=" + ",".join(columns))
    print(f"row_count={row_count}")
    print(f"duplicate_email_groups={duplicate_emails}")
    print(f"duplicate_nickname_groups={duplicate_nicknames}")
    print("constraints=" + ",".join(constraints))
    print("indexes=" + ",".join(indexes))
    print("cron_jobs=" + ",".join(cron_jobs))


if __name__ == "__main__":
    asyncio.run(run())
