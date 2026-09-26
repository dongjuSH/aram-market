# 실제 Supabase 세션 기반 미가입 아이디 로그인 응답 점검

import asyncio

from fastapi import HTTPException

from backend.core.database import async_session
from backend.domain.users.schemas.users import SignInRequest
from backend.domain.users.services.users import UserService


# 실제 DB 세션 기반 미가입 아이디 오류 응답 확인
async def run() -> None:
    async with async_session() as session:
        service = UserService(session)
        try:
            await service.signin(
                SignInRequest(
                    username="missing_user_123",
                    password="Password!1",
                )
            )
        except HTTPException as error:
            assert error.status_code == 401
            assert error.detail["code"] == "INVALID_CREDENTIALS"
            assert "아이디 또는 비밀번호" in error.detail["message"]
        else:
            raise AssertionError("없는 아이디 로그인이 거부되지 않았습니다.")

    print("unknown-user response verified")


if __name__ == "__main__":
    asyncio.run(run())
