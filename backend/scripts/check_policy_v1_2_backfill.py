# 이메일 인증을 마친 active 회원이 모두 service·privacy v1.2 동의 이력을 가졌는지 확인하는 읽기 전용 스크립트(누락 시 종료 코드 1)

import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine
from backend.domain.users.services.policies import CURRENT_POLICIES, POLICY_PRIVACY, POLICY_SERVICE


# 현재 시행 버전(1.2) 동의 이력이 빠진 활성 회원 수를 약관 종류별로 출력
async def run() -> int:
    missing: dict[str, int] = {}
    async with engine.connect() as connection:
        for policy_type in (POLICY_SERVICE, POLICY_PRIVACY):
            missing[policy_type] = (
                await connection.execute(
                    text(
                        "SELECT COUNT(*) FROM users AS u WHERE u.status = 'active' AND u.email_verified_at IS NOT NULL "
                        "AND NOT EXISTS (SELECT 1 FROM user_policy_consents AS c WHERE c.user_id = u.id "
                        "AND c.policy_type = :policy_type AND c.policy_version = :version AND c.agreed)"
                    ),
                    {"policy_type": policy_type, "version": "1.2"},
                )
            ).scalar_one()
    await engine.dispose()
    versions_ok = all(CURRENT_POLICIES[policy_type].version == "1.2" for policy_type in (POLICY_SERVICE, POLICY_PRIVACY))
    for policy_type, count in missing.items():
        print(f"{policy_type}_v1_2_missing_active_users={count}")
    print(f"current_policy_versions_are_1_2={str(versions_ok).lower()}")
    ok = versions_ok and not any(missing.values())
    print("policy_v1_2_backfill_ok=" + str(ok).lower())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
