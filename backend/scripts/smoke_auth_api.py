# 실제 DB 세션 기반 잘못된 관리자 아이디 로그인 응답 점검

import asyncio

from fastapi import HTTPException

from backend.core.database import async_session
from backend.domain.admins.schemas.admins import SignInRequest
from backend.domain.admins.services.admins import AdminAccountService


# 단일 관리자 외 아이디의 공통 로그인 실패 응답 확인
async def run() -> None:
    async with async_session() as session:
        service = AdminAccountService(session)
        try:
            await service.signin(
                SignInRequest(
                    username="missing_user_123",
                    password="Password!1",
                ),
                "127.0.0.254",
            )
        except HTTPException as error:
            assert error.status_code == 401
            assert error.detail["code"] == "INVALID_CREDENTIALS"
            assert "아이디 또는 비밀번호" in error.detail["message"]
        else:
            raise AssertionError("없는 아이디 로그인이 거부되지 않았습니다.")

    print("unknown-admin response verified")


if __name__ == "__main__":
    asyncio.run(run())
