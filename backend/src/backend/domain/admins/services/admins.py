# 단일 관리자 로그인·IP 제한·토큰 검증 비즈니스 규칙

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.errors import api_error
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import (
    create_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from backend.domain.admins.models.admins import AdminAccount, AdminRefreshToken
from cryptography.fernet import InvalidToken

from backend.domain.admins.schemas.admins import MfaVerifyRequest, SignInRequest
from backend.domain.admins.services.mfa import decrypt_secret, hash_recovery_code, matching_step
from backend.domain.admins.services.rate_limit import LoginRateLimiter, admin_login_limiter


logger = logging.getLogger(__name__)  # 비밀번호를 제외한 관리자 인증 이상 징후 기록
DUMMY_PASSWORD_HASH = hash_password("Dummy!Password1")  # 아이디 존재 여부 응답시간 차이 완화용 해시
MFA_PENDING_MINUTES = 5  # 비밀번호 확인 후 2단계 인증 코드를 입력할 수 있는 시간


# 2단계 인증 대기 시간이 지났거나 대기 정보가 맞지 않을 때의 공통 오류
def mfa_session_expired_error() -> HTTPException:
    return api_error(status.HTTP_401_UNAUTHORIZED, "MFA_SESSION_EXPIRED", "인증 시간이 지났습니다. 아이디와 비밀번호부터 다시 로그인해 주세요.")


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

        has_enabled_at = admin.mfa_enabled_at is not None
        has_secret = bool(admin.mfa_secret_encrypted)
        if has_enabled_at and has_secret:
            # 비밀번호만으로는 실패 기록을 초기화하지 않음(비밀번호를 아는 공격자가 코드 대입 제한을 풀지 못하게)
            mfa_token = create_token(admin.id, "admin_mfa_pending", MFA_PENDING_MINUTES, {"ver": admin.auth_version})
            return {"message": "인증 앱의 6자리 코드를 입력해 주세요.", "mfa_required": True, "mfa_token": mfa_token}
        if has_enabled_at != has_secret or settings.admin_mfa_required:
            # 일부만 설정된 상태이거나 운영(필수)에서 미등록이면 비밀번호만으로 들여보내지 않음(fail-closed)
            logger.error("admin MFA is required but not fully enrolled; run scripts/setup_admin_mfa.py")
            raise api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "ADMIN_MFA_NOT_CONFIGURED",
                "관리자 2단계 인증이 설정되지 않아 로그인할 수 없습니다. 서버에서 등록 스크립트를 실행해 주세요.",
            )

        logger.warning("admin signed in without MFA (ADMIN_MFA_REQUIRED=false); run scripts/setup_admin_mfa.py to enroll")
        self.limiter.reset(client_ip, request.username)
        return await self._login_response(admin)

    # 비밀번호 확인 후 받은 대기 토큰과 인증 앱 코드(또는 1회용 복구 코드)로 로그인 완료
    async def verify_mfa(self, mfa_token: str | None, request: MfaVerifyRequest, client_ip: str) -> dict:
        retry_after = self.limiter.retry_after(client_ip, "admin")
        if retry_after:
            raise rate_limit_error(retry_after)
        try:
            payload = decode_token(mfa_token or "", "admin_mfa_pending")
        except ValueError as error:
            raise mfa_session_expired_error() from error

        # 같은 코드를 동시에 두 번 제출해도 한 번만 통과하도록 관리자 행을 잠금
        admin = (
            await self.db.execute(select(AdminAccount).where(AdminAccount.id == payload["sub"]).with_for_update())
        ).scalar_one_or_none()
        if not admin or not admin.is_active or payload.get("ver") != admin.auth_version or not admin.mfa_secret_encrypted:
            raise mfa_session_expired_error()

        if not self._consume_mfa_code(admin, request.code):
            self._raise_login_failure(
                client_ip,
                "admin",
                api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_MFA_CODE", "인증 코드가 올바르지 않습니다. 인증 앱의 현재 코드를 입력해 주세요."),
            )

        self.limiter.reset(client_ip, "admin")
        return await self._login_response(admin)  # 마지막 사용 단계·복구 코드 변경도 함께 커밋

    # 인증 앱 코드는 이전에 쓴 단계보다 새 단계만, 복구 코드는 목록에 있으면 한 번만 통과
    def _consume_mfa_code(self, admin: AdminAccount, code: str) -> bool:
        normalized = code.strip()
        try:
            secret = decrypt_secret(admin.mfa_secret_encrypted)
        except InvalidToken as error:
            logger.error("admin MFA secret cannot be decrypted (AUTH_SECRET_KEY changed?); re-enroll with setup_admin_mfa.py")
            raise api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE, "MFA_UNAVAILABLE", "2단계 인증 설정을 확인할 수 없습니다. 관리 스크립트로 다시 등록해 주세요."
            ) from error
        step = matching_step(secret, normalized)
        if step is not None:
            if admin.mfa_last_used_step is not None and step <= admin.mfa_last_used_step:
                return False  # 이미 사용한 코드(또는 더 이전 코드) 재사용
            admin.mfa_last_used_step = step
            return True
        code_hash = hash_recovery_code(normalized)
        remaining = list(admin.mfa_recovery_code_hashes or [])
        if code_hash in remaining:
            remaining.remove(code_hash)
            admin.mfa_recovery_code_hashes = remaining
            logger.warning("admin signed in with a recovery code remaining=%s", len(remaining))
            return True
        return False

    # 로그인 실패 기록과 다중 IP 공격 징후를 남긴 뒤 공통 인증 오류 반환
    def _raise_login_failure(self, client_ip: str, username: str, error: HTTPException | None = None) -> None:
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
        raise error or invalid_credentials_error()

    # 관리자 접근 토큰과 새 세션(family)의 리프레시 토큰 발급
    async def _login_response(self, admin: AdminAccount) -> dict:
        tokens = await self._issue_tokens(admin, str(uuid.uuid4()))
        return {"message": "로그인을 성공하였습니다.", **tokens, "user": {"id": admin.id, "username": admin.username}}

    # 관리자 전용 용도와 인증 버전을 포함한 접근 토큰 생성, 리프레시 토큰은 해시만 저장
    async def _issue_tokens(self, admin: AdminAccount, family_id: str) -> dict:
        refresh_token = generate_refresh_token()
        self.db.add(
            AdminRefreshToken(
                admin_id=admin.id,
                family_id=family_id,
                token_hash=hash_refresh_token(refresh_token),
                auth_version=admin.auth_version,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.admin_refresh_token_expire_hours),
            )
        )
        await self.db.commit()
        access_token = create_token(
            admin.id,
            "admin_access",
            settings.admin_access_token_expire_minutes,
            {"ver": admin.auth_version, "sid": family_id},  # sid로 서버가 로그인 세션 폐기 여부를 즉시 확인
        )
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    # 해시로 리프레시 토큰 행 조회(재발급 때는 행을 잠가 여러 창의 동시 재발급이 한 번씩 차례로 처리되게 함)
    async def _get_refresh_row(self, token_hash: str, lock: bool = False) -> AdminRefreshToken | None:
        query = select(AdminRefreshToken).where(AdminRefreshToken.token_hash == token_hash)
        if lock:
            query = query.with_for_update()
        return (await self.db.execute(query)).scalar_one_or_none()

    # 접근 토큰의 sid에 해당하는 로그인 세션이 폐기·만료되지 않았는지 확인
    async def _is_session_alive(self, session_id: str) -> bool:
        row = (
            await self.db.execute(
                select(AdminRefreshToken.id)
                .where(
                    AdminRefreshToken.family_id == session_id,
                    AdminRefreshToken.revoked_at.is_(None),
                    AdminRefreshToken.expires_at > datetime.now(timezone.utc),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    # 같은 로그인 세션(family)의 남은 토큰 전체 폐기
    async def _revoke_family(self, family_id: str) -> None:
        await self.db.execute(
            update(AdminRefreshToken)
            .where(AdminRefreshToken.family_id == family_id, AdminRefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # 리프레시 토큰을 검증·회전해 새 토큰 발급(폐기된 토큰 재사용 시 세션 전체 폐기)
    async def refresh_session(self, refresh_token: str) -> dict:
        invalid = api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "로그인이 만료되었습니다. 다시 로그인해 주세요.")
        row = await self._get_refresh_row(hash_refresh_token(refresh_token), lock=True)
        if not row:
            raise invalid

        now = datetime.now(timezone.utc)
        revoked_at = row.revoked_at if row.revoked_at is None or row.revoked_at.tzinfo else row.revoked_at.replace(tzinfo=timezone.utc)
        if revoked_at:
            # 다른 탭의 동시 재발급으로 방금 회전된 토큰은 탈취로 보지 않고 거부만 함
            if now - revoked_at > timedelta(seconds=settings.refresh_reuse_grace_seconds):
                await self._revoke_family(row.family_id)
                await self.db.commit()
                raise invalid
            raise api_error(status.HTTP_401_UNAUTHORIZED, "REFRESH_IN_PROGRESS", "다른 화면에서 로그인 갱신이 진행되었습니다. 다시 시도해 주세요.")

        expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        admin = await self.db.get(AdminAccount, row.admin_id)
        if expires_at <= now or not admin or not admin.is_active or row.auth_version != admin.auth_version:
            await self._revoke_family(row.family_id)
            await self.db.commit()
            raise invalid

        row.revoked_at = now  # 사용한 토큰은 폐기하고 같은 family의 새 토큰으로 교체
        tokens = await self._issue_tokens(admin, row.family_id)
        return {"message": "로그인이 갱신되었습니다.", **tokens, "user": {"id": admin.id, "username": admin.username}}

    # 로그아웃 시 해당 로그인 세션의 리프레시 토큰 폐기(없거나 이미 폐기여도 성공)
    async def revoke_refresh_session(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        row = await self._get_refresh_row(hash_refresh_token(refresh_token))
        if row:
            await self._revoke_family(row.family_id)
            await self.db.commit()

    # 만료된 지 하루 지난 리프레시 토큰 행 정리
    async def purge_expired_refresh_tokens(self, commit: bool = True) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        result = await self.db.execute(delete(AdminRefreshToken).where(AdminRefreshToken.expires_at < cutoff))
        if commit:
            await self.db.commit()
        return result.rowcount or 0

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
        if (
            not admin
            or not admin.is_active
            or payload.get("ver") != admin.auth_version
            or not payload.get("sid")
            or not await self._is_session_alive(payload["sid"])
        ):
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", "로그인이 만료되었습니다.")
        return admin
