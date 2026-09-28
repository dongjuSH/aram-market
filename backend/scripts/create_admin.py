# 터미널에서 비밀번호를 노출하지 않고 단일 admin 계정을 생성하거나 재설정

import asyncio
from getpass import getpass

from sqlalchemy import select

from backend.core.database import async_session, engine
from backend.core.security import hash_password
from backend.domain.admins.models.admins import AdminAccount
from backend.domain.admins.schemas.admins import validate_password


ADMIN_USERNAME = "admin"  # DB 제약과 일치하는 유일한 관리자 아이디


# 터미널 보안 입력으로 admin 비밀번호를 설정
async def run() -> None:
    password = getpass("admin 비밀번호: ")
    confirmation = getpass("admin 비밀번호 확인: ")
    if password != confirmation:
        raise ValueError("입력한 비밀번호가 일치하지 않습니다.")
    validate_password(password)

    async with async_session() as session:
        accounts = (await session.execute(select(AdminAccount))).scalars().all()
        unexpected_accounts = [account.username for account in accounts if account.username != ADMIN_USERNAME]
        if unexpected_accounts or len(accounts) > 1:
            raise RuntimeError("단일 관리자 마이그레이션을 먼저 적용해 주세요.")

        admin = accounts[0] if accounts else None
        if admin:
            admin.password_hash = hash_password(password)
            admin.is_active = True
            admin.auth_version += 1
            result_message = "admin 계정 비밀번호를 재설정했습니다."
        else:
            session.add(
                AdminAccount(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(password),
                    is_active=True,
                    auth_version=0,
                )
            )
            result_message = "admin 계정을 생성했습니다."
        await session.commit()

    await engine.dispose()
    print(result_message)


if __name__ == "__main__":
    asyncio.run(run())
