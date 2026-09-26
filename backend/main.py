# FastAPI 앱, CORS, DB 생명주기 및 도메인 라우터 조립

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 터미널·VS Code 실행 방식에 따른 import 차이 방지용 backend/src 경로 추가
BACKEND_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = BACKEND_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.database import Base, engine
from backend.domain.users.models.users import User
from backend.domain.users.routers.users import router as user_router


# 서버 시작 시 누락 테이블 생성 및 종료 시 DB 엔진 정리
@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app  # FastAPI 생명주기 시그니처 유지용 인자
    async with engine.begin() as conn:
        # Supabase에 누락된 users 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


# FastAPI 인스턴스 생성
app = FastAPI(
    title="로그인, 회원가입 페이지",
    description="로그인, 회원가입 구현 페이지입니다.",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# CORS 및 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            settings.frontend_url.rstrip("/"),
        }
    ),
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST 등 모든 요청 방식 허용
    allow_headers=["*"],  # 모든 통신 헤더 허용
)


# 서버 실행 상태 확인용 기본 헬스 체크 엔드포인트
@app.get("/")
def read_root():
    return {"message": "hello world"}


# 라우터 등록
# 모든 도메인 라우터의 공통 API 접두사
app.include_router(user_router, prefix="/api")
