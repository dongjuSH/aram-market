# 활성 회원마다 현재 시행 약관(서비스·개인정보) 동의 이력이 있는지 확인하는 읽기 전용 스크립트

import asyncio

from sqlalchemy import text

from backend.core.database import engine
from backend.domain.users.services.policies import CURRENT_POLICIES, POLICY_PRIVACY, POLICY_SERVICE


# 활성 회원 수, 현재 버전 동의 이력이 없는 활성 회원 수, 버전별 이력 수 출력
async def run() -> None:
    async with engine.connect() as connection:
        active = (await connection.execute(text("SELECT COUNT(*) FROM users WHERE status = 'active' AND email_verified_at IS NOT NULL"))).scalar_one()
        print(f"active_verified_users={active}")
        for policy_type in (POLICY_SERVICE, POLICY_PRIVACY):
            version = CURRENT_POLICIES[policy_type].version
            missing = (
                await connection.execute(
                    text(
                        "SELECT COUNT(*) FROM users AS u WHERE u.status = 'active' AND u.email_verified_at IS NOT NULL "
                        "AND NOT EXISTS (SELECT 1 FROM user_policy_consents AS c WHERE c.user_id = u.id "
                        "AND c.policy_type = :policy_type AND c.policy_version = :version AND c.agreed)"
                    ),
                    {"policy_type": policy_type, "version": version},
                )
            ).scalar_one()
            print(f"{policy_type}_v{version}_missing_active_users={missing}")
        rows = (
            await connection.execute(
                text("SELECT policy_type, policy_version, COUNT(*) FROM user_policy_consents GROUP BY policy_type, policy_version ORDER BY 1, 2")
            )
        ).all()
        for policy_type, version, count in rows:
            print(f"consents {policy_type} v{version}={count}")


if __name__ == "__main__":
    asyncio.run(run())
