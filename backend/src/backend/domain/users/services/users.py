# 회원가입·로그인·계정 복구·잠금·탈퇴 생명주기 비즈니스 규칙

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import create_token, decode_token, hash_password, is_password_hash, verify_password
from backend.domain.users.models.users import User
from backend.domain.users.schemas.users import (
    CancelWithdrawalRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    FindUsernameRequest,
    PasswordResetConfirmRequest,
    PasswordResetEmailRequest,
    SignInRequest,
    SignUpRequest,
)
from backend.domain.users.services.email import (
    send_account_unlock_email,
    send_password_reset_email,
    send_username_reminder_email,
)

logger = logging.getLogger(__name__)  # 사용자에게 노출하지 않는 메일 오류 기록
LOCK_DURATION = timedelta(hours=1)  # 비밀번호 5회 실패 후 계정 잠금시간
MAX_LOGIN_FAILURES = 5  # 잠금 처리를 시작하는 연속 실패 횟수
STATUS_ACTIVE = "active"  # 정상 이용 계정
STATUS_PENDING_DELETION = "pending_deletion"  # 7일 탈퇴 취소 유예 계정
STATUS_WITHDRAWN = "withdrawn"  # 유예 종료 후 Cron 삭제 대상 계정
DUMMY_PASSWORD_HASH = hash_password("Dummy!Password1")  # 미가입 아이디 응답시간 차이 완화용 해시


# 프런트 오류 구분용 공통 오류 형식 생성
def api_error(status_code: int, code: str, message: str, **metadata) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, **metadata},
    )


# 계정 존재·잠금·실패 횟수를 노출하지 않는 공통 로그인 실패 오류
def invalid_credentials_error() -> HTTPException:
    return api_error(
        status.HTTP_401_UNAUTHORIZED,
        "INVALID_CREDENTIALS",
        "아이디 또는 비밀번호가 일치하지 않습니다. 반복 오류 시 계정이 잠길 수 있습니다.",
    )


# DB의 naive/aware datetime을 UTC aware datetime으로 통일
def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# 회원가입·로그인·복구·잠금·탈퇴 사용자 서비스
class UserService:
    # 요청 범위의 비동기 DB 세션 주입
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    # 아이디·닉네임·이메일 중복 확인 후 신규 계정 생성
    async def signup(self, request: SignUpRequest) -> dict:
        query = select(User).where(
            or_(
                User.username == request.username,
                User.nickname == request.nickname,
                User.email == request.email,
            )
        )
        existing_users = (await self.db.execute(query)).scalars().all()

        for user in existing_users:
            if user.username == request.username:
                raise api_error(status.HTTP_409_CONFLICT, "USERNAME_EXISTS", "이미 사용 중인 아이디입니다.")
            if user.nickname == request.nickname:
                raise api_error(status.HTTP_409_CONFLICT, "NICKNAME_EXISTS", "이미 사용 중인 닉네임입니다.")
            if user.email == request.email:
                raise api_error(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 가입된 이메일입니다.")

        new_user = User(
            username=request.username,
            password_hash=hash_password(request.password),
            nickname=request.nickname,
            email=request.email,
            service_policy=request.service_policy,
            privacy_policy=request.privacy_policy,
            status=STATUS_ACTIVE,
            auth_version=0,
        )
        self.db.add(new_user)

        try:
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            # 사전 조회 이후 동시 가입 충돌을 정확한 필드 오류로 변환
            await self._raise_duplicate_signup_error(request, error)

        return {"message": "회원가입이 완료되었습니다."}

    # DB 고유값 충돌을 아이디·닉네임·이메일 오류 코드로 변환
    async def _raise_duplicate_signup_error(
        self,
        request: SignUpRequest,
        original_error: IntegrityError,
    ) -> None:
        conflicts = (
            (
                await self.db.execute(
                    select(User).where(
                        or_(
                            User.username == request.username,
                            User.nickname == request.nickname,
                            User.email == request.email,
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        for user in conflicts:
            if user.username == request.username:
                raise api_error(
                    status.HTTP_409_CONFLICT, "USERNAME_EXISTS", "이미 사용 중인 아이디입니다."
                ) from original_error
            if user.nickname == request.nickname:
                raise api_error(
                    status.HTTP_409_CONFLICT, "NICKNAME_EXISTS", "이미 사용 중인 닉네임입니다."
                ) from original_error
            if user.email == request.email:
                raise api_error(
                    status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 가입된 이메일입니다."
                ) from original_error

        raise api_error(
            status.HTTP_409_CONFLICT,
            "DUPLICATE_ACCOUNT_VALUE",
            "이미 사용 중인 회원정보입니다. 입력값을 다시 확인해 주세요.",
        ) from original_error

    # 비밀번호 오류 횟수·잠금 상태·탈퇴 유예 상태 확인 후 로그인
    async def signin(self, request: SignInRequest) -> dict:
        user = (await self.db.execute(select(User).where(User.username == request.username))).scalar_one_or_none()

        if not user:
            verify_password(request.password, DUMMY_PASSWORD_HASH)
            raise invalid_credentials_error()

        now = datetime.now(timezone.utc)
        withdrawn_at = as_utc(user.withdrawn_at)

        # 올바른 비밀번호를 입력한 사용자에게만 계정 상태 안내
        has_restricted_status = user.status == STATUS_WITHDRAWN or not user.is_active
        if user.status == STATUS_PENDING_DELETION and withdrawn_at:
            has_restricted_status = has_restricted_status or now >= withdrawn_at + timedelta(
                days=settings.withdrawal_grace_days
            )
        if has_restricted_status and not verify_password(request.password, user.password_hash):
            raise invalid_credentials_error()

        if user.status == STATUS_WITHDRAWN:
            raise api_error(status.HTTP_403_FORBIDDEN, "ACCOUNT_WITHDRAWN", "탈퇴한 계정은 로그인할 수 없습니다.")

        if user.status == STATUS_PENDING_DELETION and withdrawn_at:
            grace_end = withdrawn_at + timedelta(days=settings.withdrawal_grace_days)
            if now >= grace_end:
                user.status = STATUS_WITHDRAWN
                await self.db.commit()
                raise api_error(status.HTTP_403_FORBIDDEN, "ACCOUNT_WITHDRAWN", "탈퇴한 계정은 로그인할 수 없습니다.")

        if not user.is_active:
            raise api_error(
                status.HTTP_403_FORBIDDEN,
                "ACCOUNT_DISABLED",
                "사용이 중지된 계정입니다. 관리자에게 문의해 주세요.",
            )

        await self._check_lock_and_password(user, request.password, now)
        user.login_fail_count = 0
        user.locked_until = None

        if user.status == STATUS_PENDING_DELETION and withdrawn_at:
            grace_end = withdrawn_at + timedelta(days=settings.withdrawal_grace_days)
            remaining_days = max(1, (grace_end.date() - now.date()).days)
            recovery_token = create_token(
                user.id,
                "withdrawal_recovery",
                10,
                {"ver": user.auth_version},
            )
            await self.db.commit()
            raise api_error(
                status.HTTP_409_CONFLICT,
                "WITHDRAWAL_PENDING",
                f"회원 탈퇴가 진행 중입니다. {remaining_days}일 이내에 탈퇴를 취소하고 계정을 복구할 수 있습니다. 복구하시겠습니까?",
                recovery_token=recovery_token,
            )

        if not is_password_hash(user.password_hash):
            user.password_hash = hash_password(request.password)  # 기존 평문은 첫 성공 로그인에서 해시로 교체
        await self.db.commit()
        return self._login_response(user)

    # 잠금 만료 갱신 및 비밀번호 오류 횟수 누적
    async def _check_lock_and_password(self, user: User, password: str, now: datetime) -> None:
        locked_until = as_utc(user.locked_until)
        if locked_until and locked_until > now:
            raise invalid_credentials_error()

        if locked_until and locked_until <= now:
            user.locked_until = None
            user.login_fail_count = 0

        if verify_password(password, user.password_hash):
            return

        user.login_fail_count += 1
        if user.login_fail_count >= MAX_LOGIN_FAILURES:
            user.locked_until = now + LOCK_DURATION
            await self.db.commit()
            unlock_token = create_token(user.id, "unlock", settings.unlock_token_expire_minutes)
            try:
                email_sent = await send_account_unlock_email(user, unlock_token)
            except Exception:
                logger.exception("계정 잠금 해제 이메일 발송에 실패했습니다.")
                email_sent = False

            if not email_sent:
                logger.error("잠긴 계정의 해제 이메일이 발송되지 않았습니다. user_id=%s", user.id)
            raise invalid_credentials_error()

        await self.db.commit()
        raise invalid_credentials_error()

    # 현재 인증 버전을 포함한 접근 토큰 및 화면용 회원정보 반환
    def _login_response(self, user: User) -> dict:
        access_token = create_token(
            user.id,
            "access",
            settings.access_token_expire_minutes,
            {"ver": user.auth_version},
        )
        return {
            "message": "로그인을 성공하였습니다.",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
            },
        }

    # 로그인 토큰 검증 후 현재 화면에 필요한 사용자 정보 반환
    async def get_current_user(self, token: str) -> dict:
        user = await self._get_user_from_access_token(token)
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
            }
        }

    # 계정 존재 여부를 숨기고 일치 계정에만 아이디 안내 메일 발송
    async def find_username(self, request: FindUsernameRequest) -> dict:
        user = (
            await self.db.execute(select(User).where(User.email == request.email, User.status != STATUS_WITHDRAWN))
        ).scalar_one_or_none()
        if user:
            try:
                await send_username_reminder_email(user)
            except Exception:
                logger.exception("아이디 안내 이메일 발송에 실패했습니다.")

        return {"message": "입력한 이메일과 일치하는 계정이 있으면 아이디 안내 메일을 보내드립니다."}

    # 아이디·이메일 일치 시 비밀번호 재설정 메일 발송
    async def request_password_reset(self, request: PasswordResetEmailRequest) -> dict:
        user = (
            await self.db.execute(
                select(User).where(
                    User.username == request.username,
                    User.email == request.email,
                    User.status == STATUS_ACTIVE,
                )
            )
        ).scalar_one_or_none()
        generic_message = "입력한 정보와 일치하는 계정이 있으면 비밀번호 재설정 메일을 보내드립니다."
        if not user:
            return {"message": generic_message}

        token = create_token(
            user.id,
            "password_reset",
            settings.password_reset_token_expire_minutes,
            {"ver": user.auth_version},
        )
        try:
            await send_password_reset_email(user, token)
        except Exception:
            logger.exception("비밀번호 재설정 이메일 발송에 실패했습니다.")
        return {"message": generic_message}

    # 메일 링크 단기 토큰 확인 및 새 비밀번호 교체
    async def reset_password(self, request: PasswordResetConfirmRequest) -> dict:
        try:
            payload = decode_token(request.token, "password_reset")
        except ValueError as error:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_RESET_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if not user or payload.get("ver") != user.auth_version or user.status != STATUS_ACTIVE:
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_RESET_TOKEN",
                "유효하지 않거나 이미 사용된 재설정 링크입니다.",
            )

        user.password_hash = hash_password(request.new_password)
        user.auth_version += 1  # 재설정 링크 및 기존 로그인 토큰 동시 무효화
        user.login_fail_count = 0
        user.locked_until = None
        await self.db.commit()
        return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요."}

    # 잠금 해제 메일 토큰 검증 및 로그인 잠금 초기화
    async def unlock_account(self, token: str) -> None:
        try:
            payload = decode_token(token, "unlock")
        except ValueError as error:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_UNLOCK_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if not user:
            raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "존재하지 않는 계정입니다.")

        user.login_fail_count = 0
        user.locked_until = None
        await self.db.commit()

    # 현재 비밀번호 확인 후 새 해시 저장 및 기존 로그인 토큰 무효화
    async def change_password(self, token: str, request: ChangePasswordRequest) -> dict:
        user = await self._get_user_from_access_token(token)
        if not verify_password(request.current_password, user.password_hash):
            raise api_error(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_CURRENT_PASSWORD",
                "현재 비밀번호가 일치하지 않습니다.",
            )
        if verify_password(request.new_password, user.password_hash):
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "PASSWORD_UNCHANGED",
                "새 비밀번호는 현재 비밀번호와 다르게 입력해 주세요.",
            )

        user.password_hash = hash_password(request.new_password)
        user.auth_version += 1
        user.login_fail_count = 0
        user.locked_until = None
        await self.db.commit()
        return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 다시 로그인해 주세요."}

    # 즉시 삭제 대신 7일 복구 가능한 탈퇴 대기 상태로 전환
    async def request_account_deletion(self, token: str, request: DeleteAccountRequest) -> dict:
        user = await self._get_user_from_access_token(token)
        if not verify_password(request.password, user.password_hash):
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_PASSWORD", "비밀번호가 일치하지 않습니다.")

        user.status = STATUS_PENDING_DELETION
        user.withdrawn_at = datetime.now(timezone.utc)
        user.auth_version += 1
        await self.db.commit()
        return {
            "message": f"회원 탈퇴가 접수되었습니다. {settings.withdrawal_grace_days}일 이내 로그인하면 취소할 수 있습니다.",
            "grace_days": settings.withdrawal_grace_days,
        }

    # 탈퇴 유예 로그인에서 발급한 단기 토큰으로 탈퇴 취소
    async def cancel_withdrawal(self, request: CancelWithdrawalRequest) -> dict:
        try:
            payload = decode_token(request.recovery_token, "withdrawal_recovery")
        except ValueError as error:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_RECOVERY_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if not user or user.status != STATUS_PENDING_DELETION or payload.get("ver") != user.auth_version:
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_RECOVERY_TOKEN",
                "탈퇴 취소 요청이 유효하지 않거나 만료되었습니다.",
            )

        user.status = STATUS_ACTIVE
        user.withdrawn_at = None
        user.auth_version += 1
        await self.db.commit()
        return self._login_response(user)

    # 접근 토큰의 서명·용도·인증 버전·계정 상태 검증
    async def _get_user_from_access_token(self, token: str) -> User:
        try:
            payload = decode_token(token, "access")
        except ValueError as error:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if not user or user.status != STATUS_ACTIVE or payload.get("ver") != user.auth_version:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", "로그인이 만료되었습니다.")
        return user
