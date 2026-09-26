# 탈퇴 유예 종료 및 보관기간 만료 계정 처리용 일일 배치

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update

from backend.core.config import settings
from backend.core.database import async_session
from backend.domain.users.models.users import User
from backend.domain.users.services.users import STATUS_PENDING_DELETION, STATUS_WITHDRAWN


# 유예 종료 계정 상태 전환 및 추가 보관기간 경과 행 삭제
async def run() -> None:
    now = datetime.now(timezone.utc)
    grace_cutoff = now - timedelta(days=settings.withdrawal_grace_days)
    retention_cutoff = now - timedelta(
        days=settings.withdrawal_grace_days + settings.withdrawal_retention_days
    )

    async with async_session() as session:
        completed = await session.execute(
            update(User)
            .where(
                User.status == STATUS_PENDING_DELETION,
                User.withdrawn_at <= grace_cutoff,
            )
            .values(status=STATUS_WITHDRAWN)
        )
        purged = await session.execute(
            delete(User).where(
                User.status == STATUS_WITHDRAWN,
                User.withdrawn_at <= retention_cutoff,
            )
        )
        await session.commit()

    print(
        f"withdrawal_completed={completed.rowcount or 0}, "
        f"retention_purged={purged.rowcount or 0}"
    )


if __name__ == "__main__":
    asyncio.run(run())
