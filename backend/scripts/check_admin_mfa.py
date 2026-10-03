# 관리자 2단계 인증 컬럼과 등록 상태를 확인하는 읽기 전용 스크립트(비밀값은 출력하지 않음)

import asyncio

from sqlalchemy import text

from backend.core.database import engine

MFA_COLUMNS = {"mfa_secret_encrypted", "mfa_enabled_at", "mfa_last_used_step", "mfa_recovery_code_hashes"}


# 컬럼 존재 여부와 관리자별 등록 여부·남은 복구 코드 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'admin_accounts'")
                )
            ).scalars()
        )
        print("mfa_columns_ok=" + str(MFA_COLUMNS <= columns).lower())
        if not MFA_COLUMNS <= columns:
            return
        rows = (
            await connection.execute(
                text(
                    "SELECT username, mfa_enabled_at IS NOT NULL, jsonb_array_length(mfa_recovery_code_hashes) "
                    "FROM admin_accounts ORDER BY id"
                )
            )
        ).all()
        for username, enabled, remaining in rows:
            print(f"{username} mfa_enabled={str(enabled).lower()} recovery_codes_remaining={remaining}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
