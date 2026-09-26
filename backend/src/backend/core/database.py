# 비동기 SQLAlchemy 엔진 및 요청별 DB 세션

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


engine = create_async_engine(  # 애플리케이션 공용 비동기 DB 연결 풀
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session = async_sessionmaker(  # 요청별 세션 객체 생성 팩토리
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 이후 응답 작성용 모델 값 유지
)


# 모든 SQLAlchemy 테이블 모델의 공통 선언형 기반 클래스
class Base(DeclarativeBase):
    pass


# FastAPI 요청별 독립 비동기 DB 세션 생성 및 종료
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
