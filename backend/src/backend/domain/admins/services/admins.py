# 단일 관리자 로그인·IP 제한·토큰 검증 비즈니스 규칙

import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import create_token, decode_token, hash_password, verify_password
from backend.domain.admins.models.admins import AdminAccount
from backend.domain.admins.schemas.admins import SignInRequest
from backend.domain.admins.services.rate_limit import LoginRateLimiter, admin_login_limiter


logger = logging.getLogger(__name__)  # 비밀번호를 제외한 관리자 인증 이상 징후 기록
DUMMY_PASSWORD_HASH = hash_password("Dummy!Password1")  # 아이디 존재 여부 응답시간 차이 완화용 해시


# 프런트 오류 구분용 공통 오류 형식 생성
def api_error(status_code: int, code: str, message: str, **metadata) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **metadata})


# 계정 존재 여부와 IP별 실패 횟수를 노출하지 않는 공통 로그인 실패 오류
def invalid_credentials_error() -> HTTPException:
    return api_error(
        status.HTTP_401_UNAUTHORIZED,
        "INVALID_CREDENTIALS",
        "아이디 또는 비밀번호가 일치하지 않습니다. 반복 오류 시 해당 접속 환경의 로그인이 일시적으로 제한될 수 있습니다.",
    )


# 로그인 제한시간과 Retry-After 헤더를 포함한 429 오류 생성
def rate_limit_error(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "LOGIN_RATE_LIMITED",
            "message": f"로그인 시도가 너무 많습니다. {retry_after}초 후 다시 시도해 주세요.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


# 단일 관리자 로그인과 인증 상태를 처리하는 서비스
class AdminAccountService:
    # 요청 범위의 비동기 DB 세션 주입
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.limiter: LoginRateLimiter = admin_login_limiter  # 배포 시 Redis 구현체로 교체할 제한기

    # 고정 관리자 계정의 비밀번호와 접속 IP 제한 확인 후 접근 토큰 발급
    async def signin(self, request: SignInRequest, client_ip: str) -> dict:
        retry_after = self.limiter.retry_after(client_ip, request.username)
        if retry_after:
            raise rate_limit_error(retry_after)

        admin = (
            await self.db.execute(select(AdminAccount).where(AdminAccount.username == request.username))
        ).scalar_one_or_none()
        if not admin:
            verify_password(request.password, DUMMY_PASSWORD_HASH)
            self._raise_login_failure(client_ip, request.username)

        if not admin.is_active:
            verify_password(request.password, admin.password_hash)
            self._raise_login_failure(client_ip, request.username)

        if not verify_password(request.password, admin.password_hash):
            self._raise_login_failure(client_ip, request.username)

        self.limiter.reset(client_ip, request.username)
        return self._login_response(admin)

    # 로그인 실패 기록과 다중 IP 공격 징후를 남긴 뒤 공통 인증 오류 반환
    def _raise_login_failure(self, client_ip: str, username: str) -> None:
        result = self.limiter.record_failure(client_ip, username)
        logger.warning(
            "admin login failed client=%s pair_failures=%s ip_failures=%s distinct_admin_ips=%s",
            result.client_fingerprint,
            result.pair_failure_count,
            result.ip_failure_count,
            result.distinct_admin_ips,
        )
        if result.distinct_admin_ips >= 3:
            logger.warning("admin login attempted from multiple clients count=%s", result.distinct_admin_ips)
        if result.retry_after:
            raise rate_limit_error(result.retry_after)
        raise invalid_credentials_error()

    # 관리자 전용 용도와 인증 버전을 포함한 접근 토큰 반환
    def _login_response(self, admin: AdminAccount) -> dict:
        access_token = create_token(
            admin.id,
            "admin_access",
            settings.access_token_expire_minutes,
            {"ver": admin.auth_version},
        )
        return {
            "message": "로그인을 성공하였습니다.",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {"id": admin.id, "username": admin.username},
        }

    # 접근 토큰 검증 후 관리자 화면에 필요한 정보 반환
    async def get_current_user(self, token: str) -> dict:
        admin = await self.get_authenticated_admin(token)
        return {"user": {"id": admin.id, "username": admin.username}}

    # 관리자 토큰과 계정 상태를 검증해 다른 관리자 도메인에 모델 제공
    async def get_authenticated_admin(self, token: str) -> AdminAccount:
        try:
            payload = decode_token(token, "admin_access")
        except ValueError as error:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", str(error)) from error

        admin = await self.db.get(AdminAccount, payload["sub"])
        if not admin or not admin.is_active or payload.get("ver") != admin.auth_version:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", "로그인이 만료되었습니다.")
        return admin
