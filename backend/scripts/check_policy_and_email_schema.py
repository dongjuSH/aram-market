# 약관 동의 이력·이메일 인증 스키마를 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine


# 컬럼 존재 여부, 미인증·동의 이력 없는 회원 수를 출력
async def run() -> None:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'users'"
                    )
                )
            ).scalars().all()
        )
        has_table = bool(
            (
                await connection.execute(
                    text("SELECT to_regclass('public.user_policy_consents') IS NOT NULL")
                )
            ).scalar_one()
        )
        print("users_columns_ok=" + str({"email_verified_at", "email_verification_sent_at"} <= columns).lower())
        print("consent_table=" + str(has_table).lower())
        if not has_table or "email_verified_at" not in columns:
            return
        unverified = (await connection.execute(text("SELECT COUNT(*) FROM users WHERE email_verified_at IS NULL"))).scalar_one()
        missing = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM users u WHERE NOT EXISTS ("
                    "SELECT 1 FROM user_policy_consents c WHERE c.user_id = u.id AND c.policy_type = 'service')"
                )
            )
        ).scalar_one()
        print(f"unverified_users={unverified}")
        print(f"users_without_service_consent={missing}")


if __name__ == "__main__":
    asyncio.run(run())
