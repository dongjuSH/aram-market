# 고객 회원가입·로그인·계정 복구·잠금·탈퇴 비즈니스 규칙

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
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
    is_password_hash,
    verify_password,
)
from backend.domain.users.models.users import User, UserPolicyConsent, UserRefreshToken
from backend.domain.users.schemas.users import (
    CancelWithdrawalRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailChangeRequest,
    FindUsernameRequest,
    MarketingConsentRequest,
    PasswordResetConfirmRequest,
    PasswordResetEmailRequest,
    ResendVerificationRequest,
    SignInRequest,
    SignUpRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from backend.domain.users.services.policies import CURRENT_POLICIES, POLICY_MARKETING, POLICY_PRIVACY, POLICY_SERVICE
from backend.domain.users.services.email import (
    send_account_unlock_email,
    send_email_change_email,
    send_email_verification_email,
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


# 사용자 가입·로그인·복구·잠금·탈퇴 서비스
class UserService:
    # 요청 범위의 비동기 DB 세션 주입
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    # 탈퇴 유예기간과 추가 보관기간이 모두 끝난 계정을 실제 DB에서 삭제
    async def purge_expired_accounts(self, now: datetime | None = None, commit: bool = True) -> int:
        purge_before = (now or datetime.now(timezone.utc)) - timedelta(
            days=settings.withdrawal_grace_days + settings.withdrawal_retention_days
        )
        deleted_ids = (
            await self.db.execute(
                delete(User)
                .where(
                    User.status.in_((STATUS_PENDING_DELETION, STATUS_WITHDRAWN)),
                    User.withdrawn_at.is_not(None),
                    User.withdrawn_at <= purge_before,
                )
                .returning(User.id)
            )
        ).scalars().all()
        if commit:
            await self.db.commit()
        if deleted_ids:
            logger.info("expired user accounts purged count=%s", len(deleted_ids))
        return len(deleted_ids) + await self.purge_unverified_accounts(now, commit)

    # 인증 링크 유효시간이 지나도록 이메일을 확인하지 않은 가입 계정을 삭제해 아이디·이메일 선점 방지
    async def purge_unverified_accounts(self, now: datetime | None = None, commit: bool = True) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=settings.email_verification_token_expire_minutes)
        deleted_ids = (
            await self.db.execute(
                delete(User)
                .where(User.email_verified_at.is_(None), User.created_at <= cutoff)
                .returning(User.id)
            )
        ).scalars().all()
        if commit:
            await self.db.commit()
        if deleted_ids:
            logger.info("unverified user accounts purged count=%s", len(deleted_ids))
        return len(deleted_ids)

    # 회원가입 화면에 표시할 현재 시행 약관 목록
    def list_policies(self) -> dict:
        return {
            "policies": [
                {
                    "type": policy.policy_type,
                    "title": policy.title,
                    "version": policy.version,
                    "required": policy.required,
                    "content": policy.content,
                }
                for policy in CURRENT_POLICIES.values()
            ]
        }

    # 화면이 동의한 약관 버전이 현재 시행 버전과 같은지 확인
    def _validate_policy_versions(self, request: SignUpRequest) -> None:
        for policy in CURRENT_POLICIES.values():
            if not policy.required and not request.marketing_consent:
                continue
            if request.policy_versions.get(policy.policy_type) != policy.version:
                raise api_error(
                    status.HTTP_409_CONFLICT,
                    "POLICY_VERSION_MISMATCH",
                    "약관이 변경되었습니다. 화면을 새로고침한 뒤 최신 약관에 동의해 주세요.",
                )

    # 인증 메일 발송 후 재발송 제한용 발송 시각 저장
    async def _send_verification_email(self, user: User) -> bool:
        token = create_token(
            user.id,
            "user_email_verify",
            settings.email_verification_token_expire_minutes,
            {"email": user.email},
        )
        try:
            email_sent = await send_email_verification_email(user, token)
        except Exception:
            logger.exception("이메일 인증 메일 발송에 실패했습니다.")
            return False
        if email_sent:
            user.email_verification_sent_at = datetime.now(timezone.utc)
            await self.db.commit()
        return email_sent

    # 인증 링크의 서명 토큰으로 이메일 소유를 확인(이미 인증된 링크도 성공 처리)
    async def verify_email(self, request: VerifyEmailRequest) -> dict:
        invalid_error = api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_VERIFICATION_TOKEN",
            "유효하지 않거나 만료된 인증 링크입니다. 로그인 화면에서 인증 메일을 다시 요청해 주세요.",
        )
        try:
            payload = decode_token(request.token, "user_email_verify")
        except ValueError as error:
            raise invalid_error from error

        user = await self.db.get(User, payload["sub"])
        if not user or user.email != payload.get("email") or user.status == STATUS_WITHDRAWN:
            raise invalid_error

        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
        return {"message": "이메일 인증이 완료되었습니다. 로그인해 주세요."}

    # 계정 존재 여부를 숨기고 미인증 계정에만 최소 간격을 지켜 인증 메일 재발송
    async def resend_verification(self, request: ResendVerificationRequest) -> dict:
        user = (
            await self.db.execute(
                select(User).where(
                    User.email == request.email,
                    User.email_verified_at.is_(None),
                    User.status == STATUS_ACTIVE,
                )
            )
        ).scalar_one_or_none()
        if user:
            sent_at = as_utc(user.email_verification_sent_at)
            interval = timedelta(seconds=settings.email_verification_resend_seconds)
            if not sent_at or datetime.now(timezone.utc) - sent_at >= interval:
                await self._send_verification_email(user)
        return {"message": "인증이 필요한 계정이 있으면 인증 메일을 다시 보내드립니다."}

    # 약관 동의·철회 이력 1건 추가(시각은 DB 기준)
    def _record_consent(self, user_id: int, policy_type: str, agreed: bool) -> None:
        self.db.add(
            UserPolicyConsent(
                user_id=user_id,
                policy_type=policy_type,
                policy_version=CURRENT_POLICIES[policy_type].version,
                agreed=agreed,
            )
        )

    # 아이디·닉네임·이메일 중복 확인 후 신규 계정 생성
    async def signup(self, request: SignUpRequest) -> dict:
        self._validate_policy_versions(request)
        await self.purge_unverified_accounts()  # 만료된 미인증 계정이 아이디·이메일을 점유하지 않도록 정리
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
            marketing_consent=request.marketing_consent,
            status=STATUS_ACTIVE,
            auth_version=0,
        )
        self.db.add(new_user)

        try:
            await self.db.flush()  # 동의 이력에 필요한 회원 번호 확보
            self._record_consent(new_user.id, POLICY_SERVICE, True)
            self._record_consent(new_user.id, POLICY_PRIVACY, True)
            self._record_consent(new_user.id, POLICY_MARKETING, request.marketing_consent)
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            # 사전 조회 이후 동시 가입 충돌을 정확한 필드 오류로 변환
            await self._raise_duplicate_signup_error(request, error)

        email_sent = await self._send_verification_email(new_user)
        return {
            "message": "회원가입이 완료되었습니다. 이메일로 발송된 인증 링크를 확인해 주세요.",
            "email_verification_sent": email_sent,
        }

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
        user = (
            await self.db.execute(select(User).where(User.username == request.username))
        ).scalar_one_or_none()

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

        # 비밀번호가 맞은 사용자에게만 이메일 인증 필요 상태 안내
        if user.email_verified_at is None:
            await self.db.commit()
            raise api_error(
                status.HTTP_403_FORBIDDEN,
                "EMAIL_NOT_VERIFIED",
                "이메일 인증이 필요합니다. 가입한 이메일로 발송된 인증 링크를 확인해 주세요.",
                email=user.email,
            )

        if user.status == STATUS_PENDING_DELETION and withdrawn_at:
            grace_end = withdrawn_at + timedelta(days=settings.withdrawal_grace_days)
            remaining_days = max(1, (grace_end.date() - now.date()).days)
            recovery_token = create_token(
                user.id,
                "user_withdrawal_recovery",
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
        return await self._login_response(user)

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
            unlock_token = create_token(user.id, "user_unlock", settings.unlock_token_expire_minutes)
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

    # 접근 토큰과 새 세션(family)의 리프레시 토큰을 발급하고 화면용 회원정보 반환
    async def _login_response(self, user: User) -> dict:
        tokens = await self._issue_tokens(user, str(uuid.uuid4()))
        return {"message": "로그인을 성공하였습니다.", **tokens, "user": self._user_payload(user)}

    # 화면(마이 페이지·주문서 자동 입력)에 필요한 회원정보
    def _user_payload(self, user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "marketing_consent": user.marketing_consent,
            "name": user.name,
            "phone": user.phone,
        }

    # 인증 버전을 담은 접근 토큰 생성과 리프레시 토큰(해시만 저장) 발급
    async def _issue_tokens(self, user: User, family_id: str) -> dict:
        refresh_token = generate_refresh_token()
        self.db.add(
            UserRefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_refresh_token(refresh_token),
                auth_version=user.auth_version,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            )
        )
        await self.db.commit()
        access_token = create_token(
            user.id,
            "user_access",
            settings.access_token_expire_minutes,
            {"ver": user.auth_version, "sid": family_id},  # sid로 서버가 로그인 세션 폐기 여부를 즉시 확인
        )
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    # 해시로 리프레시 토큰 행 조회
    async def _get_refresh_row(self, token_hash: str) -> UserRefreshToken | None:
        return (
            await self.db.execute(select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash))
        ).scalar_one_or_none()

    # 접근 토큰의 sid에 해당하는 로그인 세션이 폐기·만료되지 않았는지 확인
    async def _is_session_alive(self, session_id: str) -> bool:
        row = (
            await self.db.execute(
                select(UserRefreshToken.id)
                .where(
                    UserRefreshToken.family_id == session_id,
                    UserRefreshToken.revoked_at.is_(None),
                    UserRefreshToken.expires_at > datetime.now(timezone.utc),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    # 같은 로그인 세션(family)의 남은 토큰 전체 폐기
    async def _revoke_family(self, family_id: str) -> None:
        await self.db.execute(
            update(UserRefreshToken)
            .where(UserRefreshToken.family_id == family_id, UserRefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # 회원의 모든 로그인 세션 폐기(비밀번호 변경·재설정·탈퇴)
    async def _revoke_user_sessions(self, user_id: int) -> None:
        await self.db.execute(
            update(UserRefreshToken)
            .where(UserRefreshToken.user_id == user_id, UserRefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # 리프레시 토큰을 검증·회전해 새 접근·리프레시 토큰 발급(폐기된 토큰 재사용 시 세션 전체 폐기)
    async def refresh_session(self, refresh_token: str) -> dict:
        invalid = api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "로그인이 만료되었습니다. 다시 로그인해 주세요.")
        row = await self._get_refresh_row(hash_refresh_token(refresh_token))
        if not row:
            raise invalid

        now = datetime.now(timezone.utc)
        revoked_at = as_utc(row.revoked_at)
        if revoked_at:
            # 다른 탭의 동시 재발급으로 방금 회전된 토큰은 탈취로 보지 않고 거부만 함
            if now - revoked_at > timedelta(seconds=settings.refresh_reuse_grace_seconds):
                await self._revoke_family(row.family_id)
                await self.db.commit()
                raise invalid
            raise api_error(status.HTTP_401_UNAUTHORIZED, "REFRESH_IN_PROGRESS", "다른 화면에서 로그인 갱신이 진행되었습니다. 다시 시도해 주세요.")

        user = await self.db.get(User, row.user_id)
        if (
            as_utc(row.expires_at) <= now
            or not user
            or user.status != STATUS_ACTIVE
            or not user.is_active
            or row.auth_version != user.auth_version
        ):
            await self._revoke_family(row.family_id)
            await self.db.commit()
            raise invalid

        row.revoked_at = now  # 사용한 토큰은 즉시 폐기하고 같은 family의 새 토큰으로 교체
        tokens = await self._issue_tokens(user, row.family_id)
        return {"message": "로그인이 갱신되었습니다.", **tokens, "user": self._user_payload(user)}

    # 로그아웃 시 해당 로그인 세션의 리프레시 토큰 폐기(없거나 이미 폐기여도 성공)
    async def revoke_refresh_session(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        row = await self._get_refresh_row(hash_refresh_token(refresh_token))
        if row:
            await self._revoke_family(row.family_id)
            await self.db.commit()

    # 만료된 지 하루 지난 리프레시 토큰 행 정리
    async def purge_expired_refresh_tokens(self, now: datetime | None = None, commit: bool = True) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=1)
        result = await self.db.execute(delete(UserRefreshToken).where(UserRefreshToken.expires_at < cutoff))
        if commit:
            await self.db.commit()
        return result.rowcount or 0

    # 로그인 토큰 검증 후 현재 화면에 필요한 사용자 정보 반환
    async def get_current_user(self, token: str) -> dict:
        user = await self._get_user_from_access_token(token)
        return {"user": self._user_payload(user)}

    # 마이 페이지에서 선택 마케팅 수신 동의 상태 변경
    async def update_marketing_consent(self, token: str, request: MarketingConsentRequest) -> dict:
        user = await self._get_user_from_access_token(token)
        if user.marketing_consent != request.marketing_consent:
            user.marketing_consent = request.marketing_consent
            self._record_consent(user.id, POLICY_MARKETING, request.marketing_consent)
        await self.db.commit()
        return {
            "message": "마케팅 수신 동의 상태가 변경되었습니다.",
            "user": self._user_payload(user),
        }

    # 닉네임·이름·휴대폰 수정(닉네임은 중복 불가)
    async def update_profile(self, token: str, request: UpdateProfileRequest) -> dict:
        user = await self._get_user_from_access_token(token)
        if request.nickname != user.nickname:
            taken = (
                await self.db.execute(select(User.id).where(User.nickname == request.nickname, User.id != user.id))
            ).scalar_one_or_none()
            if taken is not None:
                raise api_error(status.HTTP_409_CONFLICT, "NICKNAME_EXISTS", "이미 사용 중인 닉네임입니다.")
        user.nickname = request.nickname
        user.name = request.name
        user.phone = request.phone
        try:
            await self.db.commit()
        except IntegrityError as error:  # 조회 이후 동시 변경으로 닉네임이 겹친 경우
            await self.db.rollback()
            raise api_error(status.HTTP_409_CONFLICT, "NICKNAME_EXISTS", "이미 사용 중인 닉네임입니다.") from error
        return {"message": "회원정보가 저장되었습니다.", "user": self._user_payload(user)}

    # 현재 비밀번호 확인 후 새 이메일로 확인 메일 발송(이메일은 링크 확인 전까지 바뀌지 않음)
    async def request_email_change(self, token: str, request: EmailChangeRequest) -> dict:
        user = await self._get_user_from_access_token(token)
        if not verify_password(request.password, user.password_hash):
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_PASSWORD", "비밀번호가 일치하지 않습니다.")
        if request.new_email == user.email:
            raise api_error(status.HTTP_400_BAD_REQUEST, "EMAIL_UNCHANGED", "현재 사용 중인 이메일과 다른 주소를 입력해 주세요.")
        taken = (await self.db.execute(select(User.id).where(User.email == request.new_email))).scalar_one_or_none()
        if taken is not None:
            raise api_error(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 가입된 이메일입니다.")

        email_token = create_token(
            user.id,
            "user_email_change",
            settings.email_verification_token_expire_minutes,
            {"new_email": request.new_email, "ver": user.auth_version},
        )
        try:
            sent = await send_email_change_email(user, request.new_email, email_token)
        except Exception:
            logger.exception("이메일 변경 확인 메일 발송에 실패했습니다.")
            sent = False
        if not sent:
            raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "EMAIL_SEND_FAILED", "확인 메일을 보내지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return {"message": f"{request.new_email} 주소로 확인 메일을 보냈습니다. 메일의 링크를 눌러야 이메일이 변경됩니다."}

    # 확인 메일의 링크 토큰으로 이메일 변경을 완료(이미 변경된 링크는 성공 처리)
    async def confirm_email_change(self, request: VerifyEmailRequest) -> dict:
        invalid_error = api_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_EMAIL_CHANGE_TOKEN",
            "유효하지 않거나 만료된 링크입니다. 마이 페이지에서 이메일 변경을 다시 요청해 주세요.",
        )
        try:
            payload = decode_token(request.token, "user_email_change")
        except ValueError as error:
            raise invalid_error from error

        user = await self.db.get(User, payload["sub"])
        new_email = payload.get("new_email")
        if not user or user.status != STATUS_ACTIVE or payload.get("ver") != user.auth_version or not new_email:
            raise invalid_error
        if user.email == new_email:
            return {"message": "이메일이 변경되었습니다."}
        taken = (await self.db.execute(select(User.id).where(User.email == new_email, User.id != user.id))).scalar_one_or_none()
        if taken is not None:
            raise api_error(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 다른 계정에서 사용 중인 이메일입니다.")
        user.email = new_email
        user.email_verified_at = datetime.now(timezone.utc)
        try:
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            raise api_error(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 다른 계정에서 사용 중인 이메일입니다.") from error
        return {"message": "이메일이 변경되었습니다."}

    # 계정 존재 여부를 숨기고 일치 계정에만 아이디 안내 메일 발송
    async def find_username(self, request: FindUsernameRequest) -> dict:
        user = (
            await self.db.execute(
                select(User).where(
                    User.email == request.email,
                    User.email_verified_at.is_not(None),
                    User.status != STATUS_WITHDRAWN,
                )
            )
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
                    User.email_verified_at.is_not(None),
                    User.status == STATUS_ACTIVE,
                )
            )
        ).scalar_one_or_none()
        generic_message = "입력한 정보와 일치하는 계정이 있으면 비밀번호 재설정 메일을 보내드립니다."
        if not user:
            return {"message": generic_message}

        token = create_token(
            user.id,
            "user_password_reset",
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
            payload = decode_token(request.token, "user_password_reset")
        except ValueError as error:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_RESET_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if not user or payload.get("ver") != user.auth_version or user.status != STATUS_ACTIVE:
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_RESET_TOKEN",
                "유효하지 않거나 이미 사용된 재설정 링크입니다.",
            )

        if verify_password(request.new_password, user.password_hash):
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "PASSWORD_UNCHANGED",
                "새 비밀번호는 현재 비밀번호와 다르게 입력해 주세요.",
            )

        user.password_hash = hash_password(request.new_password)
        user.auth_version += 1  # 재설정 링크 및 기존 로그인 토큰 동시 무효화
        user.login_fail_count = 0
        user.locked_until = None
        await self._revoke_user_sessions(user.id)
        await self.db.commit()
        return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요."}

    # 잠금 해제 메일 토큰 검증 및 로그인 잠금 초기화
    async def unlock_account(self, token: str) -> None:
        try:
            payload = decode_token(token, "user_unlock")
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
        await self._revoke_user_sessions(user.id)
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
        await self._revoke_user_sessions(user.id)
        await self.db.commit()
        return {
            "message": f"회원 탈퇴가 접수되었습니다. {settings.withdrawal_grace_days}일 이내 로그인하면 취소할 수 있습니다.",
            "grace_days": settings.withdrawal_grace_days,
        }

    # 탈퇴 유예 로그인에서 발급한 단기 토큰으로 탈퇴 취소
    async def cancel_withdrawal(self, request: CancelWithdrawalRequest) -> dict:
        try:
            payload = decode_token(request.recovery_token, "user_withdrawal_recovery")
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
        return await self._login_response(user)

    # 접근 토큰의 서명·용도·인증 버전·계정 상태·로그인 세션(sid) 검증
    async def _get_user_from_access_token(self, token: str) -> User:
        try:
            payload = decode_token(token, "user_access")
        except ValueError as error:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", str(error)) from error

        user = await self.db.get(User, payload["sub"])
        if (
            not user
            or user.status != STATUS_ACTIVE
            or payload.get("ver") != user.auth_version
            or not payload.get("sid")
            or not await self._is_session_alive(payload["sid"])
        ):
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_ACCESS_TOKEN", "로그인이 만료되었습니다.")
        return user
