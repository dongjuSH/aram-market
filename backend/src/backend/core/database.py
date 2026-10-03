# 비동기 SQLAlchemy 엔진 및 요청별 DB 세션

from uuid import uuid4

from sqlalchemy import make_url, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


DATABASE_URL = make_url(settings.database_url)
# Supabase 트랜잭션 풀러(6543)는 요청마다 다른 DB 연결을 돌려 쓰므로 asyncpg의 prepared statement 캐시를 끄고
# 문장 이름을 매번 새로 만들어 "prepared statement does not exist/already exists" 오류를 막는다(세션 풀러 5432는 그대로)
USES_TRANSACTION_POOLER = DATABASE_URL.port == 6543
CONNECT_ARGS: dict = {"server_settings": {"timezone": "Asia/Seoul"}}
# 세션 풀러(5432)·직접 연결: 장기 실행 서버 1대 기준 앱 연결 풀 크기를 명시(최대 10개)
POOL_OPTIONS: dict = {"pool_size": 5, "max_overflow": 5, "pool_pre_ping": True, "pool_recycle": 300}
if USES_TRANSACTION_POOLER:
    DATABASE_URL = DATABASE_URL.update_query_dict({"prepared_statement_cache_size": "0"})
    CONNECT_ARGS |= {"statement_cache_size": 0, "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__"}
    # 연결 재사용은 Supavisor가 맡으므로 앱은 연결을 쥐고 있지 않음(자동 확장 시 인스턴스마다 풀이 쌓여 한도에 걸리는 것 방지, Supabase 권장)
    POOL_OPTIONS = {"poolclass": NullPool}

engine = create_async_engine(  # 애플리케이션 공용 비동기 DB 연결
    DATABASE_URL,
    echo=False,
    connect_args=CONNECT_ARGS,
    **POOL_OPTIONS,
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
            # Supabase Pooler가 서버 기본값을 초기화해도 요청 트랜잭션은 한국 시간대를 사용
            await session.execute(text("SET TIME ZONE 'Asia/Seoul'"))
            yield session
        finally:
            await session.close()
