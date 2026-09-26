# SQLAlchemy 모델 기준 누락 DB 테이블 최초 생성

import asyncio

from backend.core.database import Base, engine
from backend.domain.users.models.users import User  # noqa: F401 - 테이블 메타데이터 등록


# SQLAlchemy 모델 메타데이터 기준 누락 테이블 생성
async def run() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    print("database tables initialized")


if __name__ == "__main__":
    asyncio.run(run())
