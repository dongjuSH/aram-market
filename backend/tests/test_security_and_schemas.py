# 관리자·사용자 인증 토큰 분리와 IP 로그인 제한 규칙 테스트

import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from string import Template

os.environ.setdefault("ADMIN_MFA_REQUIRED", "false")  # 테스트는 .env와 무관하게 MFA 미등록 관리자 로그인 허용(필수 동작은 개별 테스트에서 켬)

from fastapi import HTTPException, Response  # noqa: E402
from backend.core.security import (
    hash_refresh_token,
    clear_auth_cookie,
    create_token,
    decode_token,
    hash_password,
    set_auth_cookie,
    verify_password,
)
from backend.domain.admins.models.admins import AdminAccount, AdminRefreshToken
from backend.domain.admins.schemas.admins import SignInRequest, validate_password
from backend.domain.admins.services.admins import AdminAccountService
from backend.domain.admins.services.rate_limit import LoginRateLimiter
from backend.domain.users.models.users import User, UserRefreshToken
from backend.domain.users.schemas.users import (
    ChangePasswordRequest,
    PasswordResetConfirmRequest,
    SignInRequest as UserSignInRequest,
    SignUpRequest,
    VerifyEmailRequest,
)
from backend.domain.users.services.policies import CURRENT_POLICIES
from backend.domain.users.services.users import UserService


EMAIL_TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "src" / "backend" / "domain" / "users" / "templates"


# SQLAlchemy 단일 결과 인터페이스를 흉내 내는 인증 서비스 테스트 결과
class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    # 요청 제한 조회(시도 횟수·가장 오래된 시각): 기록 없음
    def one(self):
        return (0, None)


# 관리자 서비스가 사용하는 조회·커밋 기능만 제공하는 메모리 DB
class FakeDatabase:
    def __init__(self, admin: AdminAccount | None):
        self.admin = admin
        self.commit_count = 0
        self.added = []

    def add(self, row):
        self.added.append(row)

    async def execute(self, _query, _params=None):
        return FakeResult(self.admin)

    async def rollback(self):
        pass

    async def get(self, _model, admin_id):
        return self.admin if self.admin and self.admin.id == admin_id else None

    async def commit(self):
        self.commit_count += 1


# 비밀번호 해시와 서명 토큰의 기본 보안 동작 검증
class SecurityTests(unittest.TestCase):
    def test_password_hash_does_not_store_plaintext(self):
        encoded = hash_password("Password!1")
        self.assertNotIn("Password!1", encoded)
        self.assertTrue(verify_password("Password!1", encoded))
        self.assertFalse(verify_password("Wrong!123", encoded))

    def test_token_type_is_strictly_checked(self):
        token = create_token(1, "admin_access", 5, {"ver": 0})
        self.assertEqual(decode_token(token, "admin_access")["sub"], 1)
        with self.assertRaises(ValueError):
            decode_token(token, "user_access")


class EmailTemplateTests(unittest.TestCase):
    def test_aram_market_email_templates_render_all_variables(self):
        template_values = {
            "account_unlock.html": {
                "nickname": "아람이",
                "username": "aram_user",
                "unlock_url": "https://example.com/unlock",
                "expire_minutes": 60,
            },
            "password_reset.html": {
                "nickname": "아람이",
                "username": "aram_user",
                "reset_url": "https://example.com/reset",
                "expire_minutes": 30,
            },
            "email_verification.html": {
                "nickname": "아람이",
                "verify_url": "https://example.com/verify",
                "expire_hours": 24,
            },
            "username_reminder.html": {
                "nickname": "아람이",
                "username": "aram_user",
                "login_url": "https://example.com/login",
            },
        }

        for filename, values in template_values.items():
            with self.subTest(filename=filename):
                source = (EMAIL_TEMPLATE_DIRECTORY / filename).read_text(encoding="utf-8")
                rendered = Template(source).substitute(values)
                self.assertIn("아람 마켓", rendered)
                self.assertIn("#00734a", rendered)


# 관리자와 고객 입력값 규칙 검증
class SchemaTests(unittest.TestCase):
    def test_admin_signin_normalizes_username(self):
        request = SignInRequest(username=" ADMIN ", password="Password!1")
        self.assertEqual(request.username, "admin")

    def test_admin_management_script_rejects_weak_password(self):
        with self.assertRaises(ValueError):
            validate_password("password")

    def test_user_signup_schema_normalizes_email_and_defaults_marketing_consent(self):
        request = SignUpRequest(
            username="customer_user",
            password="Password!1",
            password_confirm="Password!1",
            nickname="사용자1",
            email="USER@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        self.assertEqual(request.email, "user@example.com")
        self.assertFalse(request.marketing_consent)

    def test_user_signup_schema_rejects_password_confirm_mismatch(self):
        with self.assertRaises(ValueError) as raised:
            SignUpRequest(
                username="customer_user",
                password="Password!1",
                password_confirm="Password!2",
                nickname="사용자1",
                email="user@example.com",
                service_policy=True,
                privacy_policy=True,
            )
        self.assertIn("일치하지 않습니다", str(raised.exception))


# 단일 관리자 로그인·IP 제한·토큰 권한 규칙 검증
class AdminServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 1_000.0
        self.limiter = LoginRateLimiter(clock=lambda: self.now)
        self.admin = AdminAccount(
            id=1,
            username="admin",
            password_hash=hash_password("Password!1"),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            auth_version=0,
        )
        self.database = FakeDatabase(self.admin)
        self.service = AdminAccountService(self.database)
        self.service.limiter = self.limiter

    async def test_valid_admin_login_issues_admin_token(self):
        result = await self.service.signin(
            SignInRequest(username="admin", password="Password!1"),
            "127.0.0.1",
        )
        payload = decode_token(result["access_token"], "admin_access")
        self.assertEqual(payload["sub"], self.admin.id)
        self.assertEqual(result["user"], {"id": 1, "username": "admin"})

    async def test_unknown_account_uses_generic_error(self):
        service = AdminAccountService(FakeDatabase(None))
        service.limiter = self.limiter
        with self.assertRaises(HTTPException) as raised:
            await service.signin(
                SignInRequest(username="not-admin", password="Password!1"),
                "127.0.0.1",
            )
        self.assertEqual(raised.exception.detail["code"], "INVALID_CREDENTIALS")

    async def test_fifth_password_failure_limits_only_client_for_thirty_seconds(self):
        errors = []
        for _ in range(5):
            with self.assertRaises(HTTPException) as raised:
                await self.service.signin(
                    SignInRequest(username="admin", password="Wrong!123"),
                    "127.0.0.1",
                )
            errors.append(raised.exception)

        self.assertTrue(all(error.status_code == 401 for error in errors[:4]))
        self.assertEqual(errors[4].status_code, 429)
        self.assertEqual(errors[4].detail["retry_after"], 30)
        self.assertEqual(errors[4].headers["Retry-After"], "30")

        result = await self.service.signin(
            SignInRequest(username="admin", password="Password!1"),
            "127.0.0.2",
        )
        self.assertEqual(result["user"]["username"], "admin")

    async def test_repeated_failures_increase_client_wait_time(self):
        for _ in range(5):
            with self.assertRaises(HTTPException):
                await self.service.signin(
                    SignInRequest(username="admin", password="Wrong!123"),
                    "127.0.0.1",
                )
        self.now += 30
        with self.assertRaises(HTTPException) as sixth:
            await self.service.signin(
                SignInRequest(username="admin", password="Wrong!123"),
                "127.0.0.1",
            )
        self.assertEqual(sixth.exception.detail["retry_after"], 60)

        self.now += 60
        with self.assertRaises(HTTPException) as seventh:
            await self.service.signin(
                SignInRequest(username="admin", password="Wrong!123"),
                "127.0.0.1",
            )
        self.assertEqual(seventh.exception.detail["retry_after"], 300)

    async def test_successful_login_resets_client_failure_history(self):
        for _ in range(4):
            with self.assertRaises(HTTPException):
                await self.service.signin(
                    SignInRequest(username="admin", password="Wrong!123"),
                    "127.0.0.1",
                )
        await self.service.signin(
            SignInRequest(username="admin", password="Password!1"),
            "127.0.0.1",
        )
        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(
                SignInRequest(username="admin", password="Wrong!123"),
                "127.0.0.1",
            )
        self.assertEqual(raised.exception.status_code, 401)

    async def test_user_token_cannot_authenticate_admin_api(self):
        token = create_token(self.admin.id, "user_access", 5, {"ver": self.admin.auth_version})
        with self.assertRaises(HTTPException) as raised:
            await self.service.get_authenticated_admin(token)
        self.assertEqual(raised.exception.detail["code"], "INVALID_ACCESS_TOKEN")


class UserServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_change_password_rejects_current_password_reuse(self):
        user = User(
            id=7,
            username="customer_user",
            password_hash=hash_password("CurrentPassword!1"),
            nickname="사용자1",
            email="user@example.com",
            is_active=True,
            status="active",
            auth_version=0,
            service_policy=True,
            privacy_policy=True,
            marketing_consent=False,
        )
        service = UserService(FakeDatabase(user))
        token = create_token(user.id, "user_access", 5, {"ver": user.auth_version, "sid": "session-1"})

        with self.assertRaises(HTTPException) as raised:
            await service.change_password(
                token,
                ChangePasswordRequest(
                    current_password="CurrentPassword!1",
                    new_password="CurrentPassword!1",
                ),
            )

        self.assertEqual(raised.exception.detail["code"], "PASSWORD_UNCHANGED")

    async def test_password_reset_rejects_current_password_reuse(self):
        user = User(
            id=8,
            username="reset_user",
            password_hash=hash_password("CurrentPassword!1"),
            nickname="사용자2",
            email="reset@example.com",
            is_active=True,
            status="active",
            auth_version=0,
            service_policy=True,
            privacy_policy=True,
            marketing_consent=False,
        )
        service = UserService(FakeDatabase(user))
        token = create_token(user.id, "user_password_reset", 5, {"ver": user.auth_version, "email": user.email})

        with self.assertRaises(HTTPException) as raised:
            await service.reset_password(
                PasswordResetConfirmRequest(
                    token=token,
                    new_password="CurrentPassword!1",
                )
            )

        self.assertEqual(raised.exception.detail["code"], "PASSWORD_UNCHANGED")

# 이메일 인증·약관 버전·쿠키 발급 규칙 검증
class EmailVerificationAndPolicyTests(unittest.IsolatedAsyncioTestCase):
    def make_user(self, **overrides):
        values = dict(
            id=9,
            username="verify_user",
            password_hash=hash_password("CurrentPassword!1"),
            nickname="사용자3",
            email="verify@example.com",
            is_active=True,
            status="active",
            auth_version=0,
            service_policy=True,
            privacy_policy=True,
            marketing_consent=False,
            login_fail_count=0,
            email_verified_at=None,
        )
        values.update(overrides)
        return User(**values)

    async def test_unverified_user_cannot_sign_in_with_correct_password(self):
        service = UserService(FakeDatabase(self.make_user()))
        with self.assertRaises(HTTPException) as raised:
            await service.signin(UserSignInRequest(username="verify_user", password="CurrentPassword!1"))
        self.assertEqual(raised.exception.detail["code"], "EMAIL_NOT_VERIFIED")

    async def test_verified_user_signin_returns_access_token_for_router_cookie(self):
        user = self.make_user(email_verified_at=datetime.now(timezone.utc))
        service = UserService(FakeDatabase(user))
        result = await service.signin(UserSignInRequest(username="verify_user", password="CurrentPassword!1"))
        self.assertEqual(decode_token(result["access_token"], "user_access")["sub"], user.id)
        self.assertTrue(result["refresh_token"])

    async def test_signin_locks_user_row_before_updating_failure_count(self):
        user = self.make_user(email_verified_at=datetime.now(timezone.utc))
        statements = []

        class Database(FakeDatabase):
            async def execute(self, query, params=None):
                statements.append(query)
                return await super().execute(query, params)

        with self.assertRaises(HTTPException):
            await UserService(Database(user)).signin(UserSignInRequest(username="verify_user", password="WrongPassword!1"))
        self.assertIsNotNone(statements[0]._for_update_arg)

    async def test_email_verification_token_marks_user_verified_and_is_idempotent(self):
        user = self.make_user()
        database = FakeDatabase(user)
        service = UserService(database)
        token = create_token(user.id, "user_email_verify", 5, {"email": user.email})

        await service.verify_email(VerifyEmailRequest(token=token))
        verified_at = user.email_verified_at
        self.assertIsNotNone(verified_at)
        await service.verify_email(VerifyEmailRequest(token=token))
        self.assertEqual(user.email_verified_at, verified_at)

    async def test_email_verification_rejects_other_token_type_and_changed_email(self):
        user = self.make_user()
        service = UserService(FakeDatabase(user))
        wrong_type = create_token(user.id, "user_access", 5, {"email": user.email})
        wrong_email = create_token(user.id, "user_email_verify", 5, {"email": "other@example.com"})
        for token in (wrong_type, wrong_email):
            with self.assertRaises(HTTPException) as raised:
                await service.verify_email(VerifyEmailRequest(token=token))
            self.assertEqual(raised.exception.detail["code"], "INVALID_VERIFICATION_TOKEN")
        self.assertIsNone(user.email_verified_at)

    def test_signup_requires_current_policy_versions(self):
        service = UserService(FakeDatabase(None))
        base = dict(
            username="customer_user",
            password="Password!1",
            password_confirm="Password!1",
            nickname="사용자1",
            email="user@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        current = {key: policy.version for key, policy in CURRENT_POLICIES.items()}
        service._validate_policy_versions(SignUpRequest(**base, policy_versions=current))

        stale = {**current, "privacy": "0.9"}
        with self.assertRaises(HTTPException) as raised:
            service._validate_policy_versions(SignUpRequest(**base, policy_versions=stale))
        self.assertEqual(raised.exception.detail["code"], "POLICY_VERSION_MISMATCH")

        # 마케팅 미동의 시 마케팅 버전은 요구하지 않음
        without_marketing = {key: value for key, value in current.items() if key != "marketing"}
        service._validate_policy_versions(SignUpRequest(**base, policy_versions=without_marketing))
        with self.assertRaises(HTTPException):
            service._validate_policy_versions(SignUpRequest(**base, marketing_consent=True, policy_versions=without_marketing))

    def test_auth_cookie_is_http_only_scoped_and_clearable(self):
        response = Response()
        set_auth_cookie(response, "user_access_token", "token-value")
        header = response.headers["set-cookie"].lower()
        self.assertIn("httponly", header)
        self.assertIn("samesite=lax", header)
        self.assertIn("path=/api", header)

        session_response = Response()
        set_auth_cookie(session_response, "user_refresh_token", "token-value", session_only=True)
        self.assertNotIn("max-age", session_response.headers["set-cookie"].lower())

        cleared = Response()
        clear_auth_cookie(cleared, "user_access_token")
        self.assertIn("max-age=0", cleared.headers["set-cookie"].lower())


if __name__ == "__main__":
    unittest.main()


# 리프레시 토큰 행을 메모리에 보관하는 인증 서비스용 DB(조회·폐기 메서드는 서비스 헬퍼를 재정의해 대체)
class RefreshFakeDatabase(FakeDatabase):
    def __init__(self, user: User):
        super().__init__(None)
        self.user = user
        self.rows: list[UserRefreshToken] = []

    def add(self, row):
        self.rows.append(row)

    async def execute(self, _query):
        return FakeResult(self.user)

    async def get(self, _model, user_id):
        return self.user if self.user.id == user_id else None


# 메모리 DB의 토큰 행을 직접 다루도록 조회·폐기 헬퍼만 바꾼 서비스
class RefreshTestService(UserService):
    async def _get_refresh_row(self, token_hash, lock=False):
        return next((row for row in self.db.rows if row.token_hash == token_hash), None)

    async def _revoke_family(self, family_id):
        for row in self.db.rows:
            if row.family_id == family_id and row.revoked_at is None:
                row.revoked_at = datetime.now(timezone.utc)


# 로그인 시 리프레시 토큰 발급과 회전·재사용 탐지·만료·버전 불일치 검증
class RefreshTokenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user = User(
            id=21,
            username="refresh_user",
            password_hash=hash_password("CurrentPassword!1"),
            nickname="사용자4",
            email="refresh@example.com",
            is_active=True,
            status="active",
            auth_version=0,
            service_policy=True,
            privacy_policy=True,
            marketing_consent=False,
            login_fail_count=0,
            email_verified_at=datetime.now(timezone.utc),
        )
        self.database = RefreshFakeDatabase(self.user)
        self.service = RefreshTestService(self.database)
        self.login = await self.service.signin(UserSignInRequest(username="refresh_user", password="CurrentPassword!1"))

    async def test_signin_issues_access_and_hashed_refresh_token(self):
        self.assertEqual(decode_token(self.login["access_token"], "user_access")["sub"], self.user.id)
        self.assertEqual(len(self.database.rows), 1)
        self.assertEqual(self.database.rows[0].token_hash, hash_refresh_token(self.login["refresh_token"]))
        self.assertNotEqual(self.database.rows[0].token_hash, self.login["refresh_token"])

    async def test_refresh_rotates_token_and_keeps_family(self):
        refreshed = await self.service.refresh_session(self.login["refresh_token"])
        self.assertNotEqual(refreshed["refresh_token"], self.login["refresh_token"])
        self.assertEqual(decode_token(refreshed["access_token"], "user_access")["sub"], self.user.id)
        old, new = self.database.rows
        self.assertIsNotNone(old.revoked_at)
        self.assertIsNone(new.revoked_at)
        self.assertEqual(old.family_id, new.family_id)

    async def test_unknown_refresh_token_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.refresh_session("not-a-real-token")
        self.assertEqual(raised.exception.detail["code"], "INVALID_REFRESH_TOKEN")

    async def test_reused_rotated_token_after_grace_revokes_whole_family(self):
        refreshed = await self.service.refresh_session(self.login["refresh_token"])
        self.database.rows[0].revoked_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])
        self.assertTrue(all(row.revoked_at is not None for row in self.database.rows))
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(refreshed["refresh_token"])

    async def test_rotated_token_reused_within_grace_does_not_revoke_new_token(self):
        await self.service.refresh_session(self.login["refresh_token"])
        with self.assertRaises(HTTPException) as raised:
            await self.service.refresh_session(self.login["refresh_token"])
        self.assertEqual(raised.exception.detail["code"], "REFRESH_IN_PROGRESS")
        self.assertIsNone(self.database.rows[1].revoked_at)

    async def test_expired_refresh_token_is_rejected(self):
        self.database.rows[0].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaises(HTTPException) as raised:
            await self.service.refresh_session(self.login["refresh_token"])
        self.assertEqual(raised.exception.detail["code"], "INVALID_REFRESH_TOKEN")

    async def test_password_change_invalidates_existing_refresh_token(self):
        self.user.auth_version += 1
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])

    async def test_signout_revokes_refresh_session(self):
        await self.service.revoke_refresh_session(self.login["refresh_token"])
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])


# 관리자 리프레시 토큰 행을 메모리에 보관하는 DB와 서비스
class AdminRefreshFakeDatabase(FakeDatabase):
    def __init__(self, admin: AdminAccount):
        super().__init__(admin)
        self.rows: list[AdminRefreshToken] = []

    def add(self, row):
        self.rows.append(row)


class AdminRefreshTestService(AdminAccountService):
    async def _get_refresh_row(self, token_hash, lock=False):
        return next((row for row in self.db.rows if row.token_hash == token_hash), None)

    async def _revoke_family(self, family_id):
        for row in self.db.rows:
            if row.family_id == family_id and row.revoked_at is None:
                row.revoked_at = datetime.now(timezone.utc)


# 관리자 로그인 시 리프레시 토큰 발급과 회전·재사용 탐지·비밀번호 재설정 후 무효 검증
class AdminRefreshTokenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin = AdminAccount(
            id=1,
            username="admin",
            password_hash=hash_password("Password!1"),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            auth_version=0,
        )
        self.database = AdminRefreshFakeDatabase(self.admin)
        self.service = AdminRefreshTestService(self.database)
        self.service.limiter = LoginRateLimiter(clock=lambda: 1_000.0)
        self.login = await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")

    async def test_signin_issues_admin_access_and_hashed_refresh_token(self):
        self.assertEqual(decode_token(self.login["access_token"], "admin_access")["sub"], 1)
        self.assertEqual(self.database.rows[0].token_hash, hash_refresh_token(self.login["refresh_token"]))

    async def test_refresh_rotates_and_old_token_is_rejected(self):
        refreshed = await self.service.refresh_session(self.login["refresh_token"])
        self.assertNotEqual(refreshed["refresh_token"], self.login["refresh_token"])
        self.assertEqual(decode_token(refreshed["access_token"], "admin_access")["sub"], 1)
        with self.assertRaises(HTTPException) as raised:
            await self.service.refresh_session(self.login["refresh_token"])
        self.assertEqual(raised.exception.detail["code"], "REFRESH_IN_PROGRESS")

    async def test_reuse_after_grace_revokes_whole_family(self):
        refreshed = await self.service.refresh_session(self.login["refresh_token"])
        self.database.rows[0].revoked_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(refreshed["refresh_token"])

    async def test_password_reset_or_deactivation_invalidates_refresh_token(self):
        self.admin.auth_version += 1
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])

    async def test_inactive_admin_cannot_refresh(self):
        self.admin.is_active = False
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])

    async def test_signout_revokes_session(self):
        await self.service.revoke_refresh_session(self.login["refresh_token"])
        with self.assertRaises(HTTPException):
            await self.service.refresh_session(self.login["refresh_token"])


# 표준 JWT 클레임·알고리즘 고정과 세션(sid) 즉시 폐기 검증
class JwtAndSessionTests(unittest.IsolatedAsyncioTestCase):
    def test_token_is_standard_jwt_with_registered_claims(self):
        import jwt as pyjwt

        token = create_token(7, "user_access", 5, {"ver": 1})
        header = pyjwt.get_unverified_header(token)
        claims = pyjwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        self.assertEqual(header["alg"], "HS256")
        self.assertEqual(claims["aud"], "user_access")
        self.assertEqual(claims["sub"], "7")
        self.assertEqual(claims["iss"], "aram-market")
        self.assertTrue(claims["jti"])
        self.assertEqual(decode_token(token, "user_access")["sub"], 7)

    def test_alg_none_and_tampered_tokens_are_rejected(self):
        import base64
        import json

        token = create_token(7, "user_access", 5)
        header, body, _ = token.split(".")
        forged_header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        with self.assertRaises(ValueError):
            decode_token(f"{forged_header}.{body}.", "user_access")
        with self.assertRaises(ValueError):
            decode_token(f"{header}.{body}.invalidsignature", "user_access")

    def test_expired_token_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_token(create_token(7, "user_access", -1), "user_access")

    async def test_access_token_stops_working_when_session_is_revoked(self):
        user = User(id=31, username="sid_user", password_hash="x", nickname="n", email="s@example.com", is_active=True, status="active", auth_version=0)

        class Service(RefreshTestService):
            alive = True

            async def _is_session_alive(self, session_id):
                return self.alive

        service = Service(RefreshFakeDatabase(user))
        token = create_token(user.id, "user_access", 5, {"ver": 0, "sid": "abc"})
        self.assertEqual((await service.get_current_user(token))["user"]["id"], 31)
        service.alive = False
        with self.assertRaises(HTTPException) as raised:
            await service.get_current_user(token)
        self.assertEqual(raised.exception.detail["code"], "INVALID_ACCESS_TOKEN")
        with self.assertRaises(HTTPException):
            await service.get_current_user(create_token(user.id, "user_access", 5, {"ver": 0}))  # sid 없는 토큰


# 신뢰 프록시가 아닌 접속자가 보낸 X-Forwarded-For 위조를 무시하는지 검증
class ClientIpTests(unittest.TestCase):
    class FakeRequest:
        def __init__(self, peer, forwarded=None):
            from types import SimpleNamespace

            self.client = SimpleNamespace(host=peer)
            self.headers = {"x-forwarded-for": forwarded} if forwarded else {}

    def with_trusted(self, trusted):
        from backend.core.config import settings

        original = settings.trusted_proxy_ips
        object.__setattr__(settings, "trusted_proxy_ips", trusted)
        self.addCleanup(object.__setattr__, settings, "trusted_proxy_ips", original)

    def test_forwarded_header_is_ignored_when_peer_is_not_trusted(self):
        from backend.core.client_ip import get_client_ip

        self.with_trusted(())
        self.assertEqual(get_client_ip(self.FakeRequest("203.0.113.9", "1.2.3.4")), "203.0.113.9")

    def test_forwarded_header_is_used_only_behind_trusted_proxy(self):
        from backend.core.client_ip import get_client_ip

        self.with_trusted(("10.0.0.0/8",))
        self.assertEqual(get_client_ip(self.FakeRequest("10.0.0.5", "198.51.100.7")), "198.51.100.7")
        # 공격자가 앞에 붙인 값이 아니라 프록시가 마지막에 붙인 실제 접속 IP를 사용
        self.assertEqual(get_client_ip(self.FakeRequest("10.0.0.5", "6.6.6.6, 198.51.100.7, 10.0.0.9")), "198.51.100.7")
        self.assertEqual(get_client_ip(self.FakeRequest("10.0.0.5")), "10.0.0.5")


# 요청 제한 초과 오류의 상태코드·Retry-After·안내문 검증
class RateLimitErrorTests(unittest.TestCase):
    def test_rate_limited_error_has_retry_after_and_readable_message(self):
        from backend.core.rate_limit import rate_limited_error

        error = rate_limited_error(125)
        self.assertEqual(error.status_code, 429)
        self.assertEqual(error.headers["Retry-After"], "125")
        self.assertEqual(error.detail["code"], "RATE_LIMITED")
        self.assertIn("3분", error.detail["message"])


# RFC 9457 Problem Details 변환 규칙 검증
class ProblemDetailsTests(unittest.TestCase):
    def test_structured_error_becomes_problem_with_extensions(self):
        from backend.core.problems import build_problem

        problem = build_problem(
            409,
            {"code": "WITHDRAWAL_PENDING", "message": "복구하시겠습니까?", "recovery_token": "abc"},
            "/api/users/signin",
        )
        self.assertEqual(problem["type"], "/problems/withdrawal-pending")
        self.assertEqual(problem["status"], 409)
        self.assertEqual(problem["code"], "WITHDRAWAL_PENDING")
        self.assertEqual(problem["detail"], "복구하시겠습니까?")
        self.assertEqual(problem["recovery_token"], "abc")
        self.assertEqual(problem["instance"], "/api/users/signin")

    def test_plain_string_error_gets_status_based_code(self):
        from backend.core.problems import build_problem

        problem = build_problem(404, "Not Found")
        self.assertEqual(problem["code"], "NOT_FOUND")
        self.assertEqual(problem["detail"], "Not Found")

    def test_validation_messages_are_korean(self):
        from backend.core.problems import _korean_validation_message

        self.assertEqual(_korean_validation_message({"type": "missing"}), "필수 입력 항목입니다.")
        self.assertEqual(_korean_validation_message({"type": "string_too_short", "ctx": {"min_length": 4}}), "4자 이상 입력해 주세요.")
        self.assertEqual(_korean_validation_message({"type": "value_error", "msg": "Value error, 비밀번호가 다릅니다."}), "비밀번호가 다릅니다.")


# 토큰 확인 계열 요청은 4xx 실패만 세고 동시 탭 경합은 세지 않는지 검증
class GuardFailuresTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_failures_keep_the_reserved_attempt(self):
        from unittest.mock import AsyncMock, patch

        from backend.core import rate_limit

        async def failing(code, status_code):
            raise HTTPException(status_code=status_code, detail={"code": code, "message": "x"})

        db = FakeDatabase(None)
        with patch.object(rate_limit, "reserve_attempt", AsyncMock(return_value=7)) as reserve, \
                patch.object(rate_limit, "release_attempt", AsyncMock()) as release:
            with self.assertRaises(HTTPException):
                await rate_limit.guard_failures(db, "n", "1.1.1.1", 5, 60, lambda: failing("INVALID_REFRESH_TOKEN", 401))
            release.assert_not_awaited()  # 실패는 예약 기록을 남김
            with self.assertRaises(HTTPException):
                await rate_limit.guard_failures(db, "n", "1.1.1.1", 5, 60, lambda: failing("REFRESH_IN_PROGRESS", 401))
            self.assertEqual(release.await_count, 1)  # 동시 탭 경합은 지움
            self.assertEqual(await rate_limit.guard_failures(db, "n", "1.1.1.1", 5, 60, AsyncMock(return_value="ok")), "ok")
            self.assertEqual(release.await_count, 2)  # 정상 요청도 지움
            with self.assertRaises(HTTPException):
                await rate_limit.guard_failures(
                    db, "n", "1.1.1.1", 5, 60, lambda: failing("EMAIL_NOT_VERIFIED", 403),
                    is_failure=lambda error: error.detail["code"] == "INVALID_CREDENTIALS",
                )
            self.assertEqual(release.await_count, 3)  # 사용자 지정 기준에서 실패가 아니면 지움
            self.assertEqual(reserve.await_count, 4)

    async def test_reserve_serializes_bucket_before_counting(self):
        from backend.core import rate_limit

        statements = []

        class Db(FakeDatabase):
            async def execute(self, query, params=None):
                statements.append((str(query), params))
                return FakeResult(None)

        await rate_limit.reserve_attempt(Db(None), "password-confirm-user", "41", 5, 900)
        self.assertIn("pg_advisory_xact_lock", statements[0][0])  # 버킷 잠금이 횟수 조회보다 먼저
        self.assertIn("count", statements[1][0].lower())

    async def test_reserve_rejects_when_limit_is_reached(self):
        from backend.core import rate_limit

        class Full(FakeResult):
            def one(self):
                return (5, datetime.now(timezone.utc))

        class Db(FakeDatabase):
            async def execute(self, query, params=None):
                return Full(None)

        db = Db(None)
        with self.assertRaises(HTTPException) as raised:
            await rate_limit.reserve_attempt(db, "n", "v", 5, 900)
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(db.added, [])  # 한도 초과 요청은 기록하지 않음

# 토스페이먼츠 승인 API 호출 결과 매핑 검증(네트워크 없이 MockTransport 사용)
class TossConfirmTests(unittest.IsolatedAsyncioTestCase):
    def use_key(self, key):
        from backend.core.config import settings

        original = settings.toss_secret_key
        object.__setattr__(settings, "toss_secret_key", key)
        self.addCleanup(object.__setattr__, settings, "toss_secret_key", original)

    def patched_client(self, handler):
        import httpx
        from unittest.mock import patch

        real = httpx.AsyncClient
        return patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    async def test_missing_secret_key_reports_payment_not_configured(self):
        from backend.domain.orders.services import toss

        self.use_key("")
        with self.assertRaises(HTTPException) as raised:
            await toss.confirm_payment("pk", "ARAM-20260101-AAAAAAAAAAAA", 1000)
        self.assertEqual(raised.exception.detail["code"], "PAYMENT_NOT_CONFIGURED")

    async def test_success_response_is_returned_and_idempotency_key_sent(self):
        import httpx

        from backend.domain.orders.services import toss

        self.use_key("test_sk_dummy")
        seen = {}

        def handler(request):
            seen["idempotency"] = request.headers.get("Idempotency-Key")
            seen["auth"] = request.headers.get("Authorization", "")[:6]
            return httpx.Response(200, json={"status": "DONE", "totalAmount": 1000})

        with self.patched_client(handler):
            result = await toss.confirm_payment("pk", "ARAM-20260101-AAAAAAAAAAAA", 1000)
        self.assertEqual(result["status"], "DONE")
        self.assertEqual(seen, {"idempotency": "ARAM-20260101-AAAAAAAAAAAA", "auth": "Basic "})

    async def test_gateway_rejection_becomes_payment_failed_with_gateway_message(self):
        import httpx

        from backend.domain.orders.services import toss

        self.use_key("test_sk_dummy")
        handler = lambda request: httpx.Response(400, json={"code": "REJECT_CARD_COMPANY", "message": "카드사에서 거절했습니다."})
        with self.patched_client(handler):
            with self.assertRaises(HTTPException) as raised:
                await toss.confirm_payment("pk", "ARAM-20260101-AAAAAAAAAAAA", 1000)
        self.assertEqual(raised.exception.detail["code"], "PAYMENT_FAILED")
        self.assertEqual(raised.exception.detail["message"], "카드사에서 거절했습니다.")
        self.assertEqual(raised.exception.detail["gateway_code"], "REJECT_CARD_COMPANY")


# 후기·문의 입력 검증과 작성자 표시 규칙 검증
class FeedbackRulesTests(unittest.TestCase):
    def test_review_requires_rating_range_and_minimum_content(self):
        from pydantic import ValidationError

        from backend.domain.reviews.schemas.reviews import ReviewRequest

        self.assertEqual(ReviewRequest(rating=5, content="  충분히 긴 후기 내용입니다.  ").content, "충분히 긴 후기 내용입니다.")
        for invalid in ({"rating": 0, "content": "충분히 긴 후기 내용입니다."}, {"rating": 6, "content": "충분히 긴 후기 내용입니다."}, {"rating": 5, "content": "짧아요"}):
            with self.assertRaises(ValidationError):
                ReviewRequest(**invalid)

    def test_inquiry_requires_minimum_content_and_defaults_to_public(self):
        from pydantic import ValidationError

        from backend.domain.inquiries.schemas.inquiries import InquiryRequest

        self.assertFalse(InquiryRequest(content="배송 문의합니다").is_secret)
        with self.assertRaises(ValidationError):
            InquiryRequest(content="짧음")

    def test_author_is_masked_and_withdrawn_member_is_labeled(self):
        from backend.domain.reviews.services.reviews import mask_nickname

        self.assertEqual(mask_nickname("홍길동"), "홍**")
        self.assertEqual(mask_nickname("김철"), "김*")
        self.assertEqual(mask_nickname(None), "탈퇴한 회원")

    def test_secret_inquiry_hides_content_and_answer_from_others(self):
        from types import SimpleNamespace

        from backend.domain.inquiries.services.inquiries import SECRET_PLACEHOLDER, InquiryService

        inquiry = SimpleNamespace(
            id=1,
            user_id=7,
            content="개인 사정이 담긴 문의",
            is_secret=True,
            answer="비공개 답변",
            answered_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        stranger = InquiryService._public_item(inquiry, "작성자", 8)
        owner = InquiryService._public_item(inquiry, "작성자", 7)
        self.assertEqual(stranger["content"], SECRET_PLACEHOLDER)
        self.assertIsNone(stranger["answer"])
        self.assertTrue(stranger["is_answered"])
        self.assertEqual(owner["content"], "개인 사정이 담긴 문의")
        self.assertEqual(owner["answer"], "비공개 답변")

    def test_admin_inquiry_search_escapes_like_wildcards(self):
        from sqlalchemy.dialects import postgresql

        from backend.domain.inquiries.services.inquiries import admin_search_condition, escape_like

        self.assertEqual(escape_like("50%_할인\\"), "50\\%\\_할인\\\\")
        self.assertEqual(str(admin_search_condition("   ").compile(dialect=postgresql.dialect())), "true")
        compiled = admin_search_condition(" 배송 ").compile(dialect=postgresql.dialect())
        self.assertIn("product_inquiries.content ILIKE", str(compiled))
        self.assertIn("products.name ILIKE", str(compiled))
        self.assertIn("users.nickname ILIKE", str(compiled))
        self.assertEqual(set(compiled.params.values()), {"%배송%"})

    def test_admin_inquiry_list_accepts_only_known_status(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.core.dependencies import require_admin_token
        from backend.domain.inquiries.routers.inquiries import router
        from backend.domain.inquiries.services.inquiries import InquiryService

        calls = []

        class FakeService:
            async def admin_list(self, token, inquiry_status, keyword, page, page_size):
                calls.append((inquiry_status, keyword, page, page_size))
                return {"items": [], "total": 0, "counts": {"pending": 0, "answered": 0}, "page": page}

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[require_admin_token] = lambda: "token"
        app.dependency_overrides[InquiryService] = FakeService
        client = TestClient(app)
        self.assertEqual(client.get("/api/admin/inquiries").status_code, 200)
        self.assertEqual(client.get("/api/admin/inquiries?status=answered&q=배송&page=2").status_code, 200)
        self.assertEqual(calls, [("pending", "", 1, 20), ("answered", "배송", 2, 20)])
        self.assertEqual(client.get("/api/admin/inquiries?status=all").status_code, 422)


# 배송지 입력 검증과 배송 상태 진행 순서 검증
class ShippingRulesTests(unittest.TestCase):
    def valid(self, **overrides):
        values = dict(recipient_name="홍길동", recipient_phone="01012345678", postcode="04001", address="서울특별시 마포구 아람로 12", address_detail="101동 1001호")
        values.update(overrides)
        return values

    def test_phone_is_normalized_to_hyphen_format(self):
        from backend.domain.orders.schemas.orders import ShippingAddress

        self.assertEqual(ShippingAddress(**self.valid()).recipient_phone, "010-1234-5678")
        self.assertEqual(ShippingAddress(**self.valid(recipient_phone="010 123 4567")).recipient_phone, "010-123-4567")

    def test_invalid_shipping_input_is_rejected(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import ShippingAddress

        for invalid in ({"recipient_phone": "123"}, {"recipient_name": "김"}, {"address": "서울"}, {"postcode": ""}, {"postcode": "1234"}, {"address_detail": " "}):
            with self.assertRaises(ValidationError):
                ShippingAddress(**self.valid(**invalid))

    def test_no_address_detail_allows_empty_detail(self):
        from backend.domain.orders.schemas.orders import ShippingAddress

        self.assertEqual(ShippingAddress(**self.valid(address_detail="", no_address_detail=True)).address_detail, "")
        # 없음을 고르면 함께 보낸 상세 주소는 무시
        self.assertEqual(ShippingAddress(**self.valid(no_address_detail=True)).address_detail, "")

    def test_order_creation_requires_shipping_and_delivery_status_is_limited(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import DeliveryStatusRequest, OrderCreateRequest

        with self.assertRaises(ValidationError):
            OrderCreateRequest(items=[{"product_id": 1, "quantity": 1}])
        self.assertEqual(DeliveryStatusRequest(status="shipping").status, "shipping")
        with self.assertRaises(ValidationError):
            DeliveryStatusRequest(status="paid")  # 되돌리기·임의 상태는 요청 자체가 불가

    def test_order_total_is_rejected_before_opening_payment_window(self):
        from backend.domain.orders.services.orders import ensure_supported_order_amount

        for amount in (0, 99, 2_147_483_648):
            with self.subTest(amount=amount), self.assertRaises(HTTPException) as raised:
                ensure_supported_order_amount(amount)
            self.assertEqual(raised.exception.detail["code"], "ORDER_AMOUNT_NOT_SUPPORTED")
        ensure_supported_order_amount(100)
        ensure_supported_order_amount(2_147_483_647)

    def test_delivery_flow_order(self):
        from backend.domain.orders.services.orders import DELIVERY_FLOW

        self.assertEqual(DELIVERY_FLOW, ("paid", "preparing", "shipping", "delivered"))

    def test_order_list_accepts_period_from_query_string(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.core.dependencies import require_user_token
        from backend.domain.orders.routers.orders import router
        from backend.domain.orders.services.orders import OrderService

        calls = []

        class StubService:
            async def list_orders(self, token, months, start_date, end_date, page, page_size):
                calls.append((months, start_date, end_date, page, page_size))
                return {"orders": [], "total": 0, "page": page}

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[require_user_token] = lambda: "token"
        app.dependency_overrides[OrderService] = StubService
        client = TestClient(app)
        # 주소의 문자열 "3"이 정수로 변환돼 서비스까지 전달되어야 함(Literal 선언 시 422로 거부되던 문제)
        self.assertEqual(client.get("/api/orders?months=3&page=2&page_size=5").status_code, 200)
        self.assertEqual(client.get("/api/orders").status_code, 200)
        self.assertEqual(client.get("/api/orders?from=2025-01-01&to=2025-06-30").status_code, 200)
        self.assertEqual(
            calls,
            [(3, None, None, 2, 5), (None, None, None, 1, 5), (None, date(2025, 1, 1), date(2025, 6, 30), 1, 5)],
        )
        self.assertEqual(client.get("/api/orders?page_size=21").status_code, 422)
        self.assertEqual(client.get("/api/orders?from=2025-13-01&to=2025-06-30").status_code, 422)

    def test_order_date_range_is_limited_to_recent_five_years(self):
        from backend.domain.orders.services.orders import KOREA_TIMEZONE, order_period_range

        now = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)  # 한국 시간 2026-10-01
        # 종료일 하루 전체를 포함하도록 다음 날 0시 미만으로 변환
        self.assertEqual(
            order_period_range(None, date(2021, 10, 1), date(2026, 10, 1), now),
            (datetime(2021, 10, 1, tzinfo=KOREA_TIMEZONE), datetime(2026, 10, 2, tzinfo=KOREA_TIMEZONE)),
        )
        self.assertEqual(order_period_range(3, None, None, now), (datetime(2026, 7, 1, tzinfo=KOREA_TIMEZONE), None))
        self.assertEqual(order_period_range(None, None, None, now), (None, None))
        invalid_cases = [
            (None, date(2021, 9, 30), date(2026, 1, 1)),  # 5년보다 이전
            (None, date(2026, 1, 1), date(2026, 10, 2)),  # 미래
            (None, date(2026, 5, 1), date(2026, 4, 1)),  # 시작일 > 종료일
            (None, date(2026, 5, 1), None),  # 한쪽만 지정
            (3, date(2026, 5, 1), date(2026, 6, 1)),  # 기간 버튼과 날짜를 함께 지정
            (4, None, None),
        ]
        for months, start, end in invalid_cases:
            with self.assertRaises(HTTPException) as caught:
                order_period_range(months, start, end, now)
            self.assertEqual(caught.exception.status_code, 422)

    def test_expired_paid_orders_are_purged_after_five_years(self):
        import asyncio

        from backend.domain.orders.services.orders import KOREA_TIMEZONE, OrderService

        captured = []

        class FakeDb:
            async def execute(self, statement):
                captured.append(statement)
                return type("Result", (), {"rowcount": 2})()

        service = OrderService.__new__(OrderService)
        service.db = FakeDb()
        now = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)  # 한국 시간 2026-10-01
        self.assertEqual(asyncio.run(service.purge_expired_orders(now, commit=False)), 2)
        params = captured[0].compile().params
        # 결제 완료는 결제 시각, 환불 완료는 환불 시각이 고객 조회 가능 범위(5년 전 같은 날 0시)보다 이전이면 삭제(환불 확인 중은 제외)
        self.assertIn("paid", params.values())
        self.assertIn("refunded", params.values())
        self.assertIn(datetime(2021, 10, 1, tzinfo=KOREA_TIMEZONE), params.values())

    def test_order_period_starts_at_korean_midnight_months_ago(self):
        from backend.domain.orders.services.orders import KOREA_TIMEZONE, months_ago_start

        # 한국 시간 2026-10-01 08:00(UTC 전날 23:00) 기준 3개월 전은 7월 1일 0시
        now = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)
        self.assertEqual(months_ago_start(3, now), datetime(2026, 7, 1, tzinfo=KOREA_TIMEZONE))
        self.assertEqual(months_ago_start(12, now), datetime(2025, 10, 1, tzinfo=KOREA_TIMEZONE))
        # 같은 날이 없는 달은 말일로 맞추고 해를 넘겨 계산
        self.assertEqual(months_ago_start(3, datetime(2026, 5, 31, 3, tzinfo=timezone.utc)), datetime(2026, 2, 28, tzinfo=KOREA_TIMEZONE))
        self.assertEqual(months_ago_start(6, datetime(2026, 2, 15, 3, tzinfo=timezone.utc)), datetime(2025, 8, 15, tzinfo=KOREA_TIMEZONE))


# 회원정보 수정·이메일 변경 입력 검증
class ProfileRulesTests(unittest.TestCase):
    def test_profile_accepts_only_nickname(self):
        from backend.domain.users.models.users import User
        from backend.domain.users.schemas.users import UpdateProfileRequest

        request = UpdateProfileRequest(nickname=" 아람이 ", name="홍길동", phone="010-1234-5678")
        self.assertEqual(request.model_dump(), {"nickname": "아람이"})  # 이름·휴대폰은 받지 않음(주소록에서 관리)
        self.assertFalse({"name", "phone"} & set(User.__table__.columns.keys()))

    def test_profile_rejects_bad_nickname(self):
        from pydantic import ValidationError

        from backend.domain.users.schemas.users import UpdateProfileRequest

        for invalid in ("a", "닉네임이열한글자입니다다", "공 백"):
            with self.assertRaises(ValidationError):
                UpdateProfileRequest(nickname=invalid)

    def test_email_change_request_normalizes_email(self):
        from backend.domain.users.schemas.users import EmailChangeRequest

        self.assertEqual(EmailChangeRequest(new_email=" New@Example.COM ", password="x").new_email, "new@example.com")

    def test_email_change_token_is_bound_to_purpose(self):
        token = create_token(5, "user_email_change", 5, {"new_email": "new@example.com", "ver": 0})
        self.assertEqual(decode_token(token, "user_email_change")["new_email"], "new@example.com")
        with self.assertRaises(ValueError):
            decode_token(token, "user_email_verify")


# 주소록 입력 검증과 주문 배송지가 같은 공통 검증을 쓰는지 확인
class AddressBookRulesTests(unittest.TestCase):
    def valid(self, **overrides):
        values = dict(label=" 집 ", recipient_name="홍길동", recipient_phone="01012345678", postcode="04001", address="서울특별시 마포구 아람로 12", address_detail="101동 1001호")
        values.update(overrides)
        return values

    def test_address_request_normalizes_fields_and_defaults(self):
        from backend.domain.users.schemas.users import AddressRequest

        request = AddressRequest(**self.valid(postcode=" 04001 "))
        self.assertEqual((request.label, request.recipient_phone, request.postcode, request.is_default), ("집", "010-1234-5678", "04001", False))

    def test_address_request_rejects_invalid_values(self):
        from pydantic import ValidationError

        from backend.domain.users.schemas.users import AddressRequest

        for invalid in ({"label": "  "}, {"label": "가" * 21}, {"recipient_phone": "123"}, {"recipient_name": "김"}, {"address": "서울"}, {"postcode": "abcde"}, {"address_detail": ""}):
            with self.assertRaises(ValidationError):
                AddressRequest(**self.valid(**invalid))

    def test_order_shipping_shares_address_validation(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import ShippingAddress

        shipping = ShippingAddress(recipient_name="홍길동", recipient_phone="01012345678", postcode="04001", address="서울특별시 마포구 아람로 12", no_address_detail=True, delivery_memo=" 문 앞 ")
        self.assertEqual((shipping.recipient_phone, shipping.delivery_memo), ("010-1234-5678", "문 앞"))
        with self.assertRaises(ValidationError):
            ShippingAddress(recipient_name="홍길동", recipient_phone="1", postcode="04001", address="서울특별시 마포구 아람로 12", no_address_detail=True)


# 2단계 보강: 비밀번호 확인 실패 제한(B1)·보안 알림(B2)·재설정 링크 이메일 고정(B3)·잠금 해제 링크 1회용(B4)
class AccountSecurityHardeningTests(unittest.IsolatedAsyncioTestCase):
    def make_user(self, **overrides):
        values = dict(
            id=41,
            username="secure_user",
            password_hash=hash_password("CurrentPassword!1"),
            nickname="보안사용자",
            email="secure@example.com",
            is_active=True,
            status="active",
            auth_version=0,
            login_fail_count=0,
            service_policy=True,
            privacy_policy=True,
            marketing_consent=False,
        )
        values.update(overrides)
        return User(**values)

    def patch_notice(self):
        from unittest.mock import AsyncMock, patch

        sender = AsyncMock(return_value=True)
        patcher = patch("backend.domain.users.services.users.send_security_notice_email", sender)
        patcher.start()
        self.addCleanup(patcher.stop)
        return sender

    def access_token(self, user):
        return create_token(user.id, "user_access", 5, {"ver": user.auth_version, "sid": "session-1"})

    async def test_wrong_current_password_is_recorded_and_limit_blocks(self):
        from unittest.mock import AsyncMock, patch

        user = self.make_user()
        service = UserService(FakeDatabase(user))
        reserve = AsyncMock(return_value=9)
        release = AsyncMock()
        with patch("backend.domain.users.services.users.reserve_attempt", reserve), patch("backend.domain.users.services.users.release_attempt", release):
            with self.assertRaises(HTTPException) as raised:
                await service.change_password(
                    self.access_token(user), ChangePasswordRequest(current_password="WrongPassword!1", new_password="NewPassword!1")
                )
        self.assertEqual(raised.exception.detail["code"], "INVALID_CURRENT_PASSWORD")
        reserve.assert_awaited_once_with(service.db, "password-confirm-user", "41", 5, 900)
        release.assert_not_awaited()  # 틀린 비밀번호는 기록을 남김

        from backend.core.rate_limit import rate_limited_error

        blocked = AsyncMock(side_effect=rate_limited_error(600))
        with patch("backend.domain.users.services.users.reserve_attempt", blocked):
            with self.assertRaises(HTTPException) as raised:
                await service.change_password(
                    self.access_token(user), ChangePasswordRequest(current_password="CurrentPassword!1", new_password="NewPassword!1")
                )
        self.assertEqual(raised.exception.status_code, 429)
        self.assertTrue(verify_password("CurrentPassword!1", user.password_hash))  # 제한 중에는 변경되지 않음

    async def test_password_change_sends_security_notice_to_current_email(self):
        sender = self.patch_notice()
        user = self.make_user()
        await UserService(FakeDatabase(user)).change_password(
            self.access_token(user), ChangePasswordRequest(current_password="CurrentPassword!1", new_password="NewPassword!1")
        )
        self.assertEqual(sender.await_args.args[1], "secure@example.com")

    async def test_email_change_notifies_previous_address_with_masked_new_email(self):
        sender = self.patch_notice()
        user = self.make_user()
        token = create_token(
            user.id, "user_email_change", 5, {"new_email": "newaddr@example.com", "current_email": "secure@example.com", "ver": 0}
        )

        class Database(FakeDatabase):
            async def execute(self, query):
                is_lock = getattr(query, "_for_update_arg", None) is not None
                return FakeResult(self.admin if is_lock else None)  # 회원 잠금 조회는 회원, 이메일 중복 조회는 없음

        await UserService(Database(user)).confirm_email_change(VerifyEmailRequest(token=token))
        self.assertEqual(user.email, "newaddr@example.com")
        to_email, title, message_text = sender.await_args.args[1:]
        self.assertEqual(to_email, "secure@example.com")
        self.assertIn("ne*****@example.com", message_text)

    async def test_reset_link_sent_to_previous_email_is_rejected(self):
        user = self.make_user(email="changed@example.com")
        token = create_token(user.id, "user_password_reset", 5, {"ver": 0, "email": "old@example.com"})
        with self.assertRaises(HTTPException) as raised:
            await UserService(FakeDatabase(user)).reset_password(PasswordResetConfirmRequest(token=token, new_password="NewPassword!1"))
        self.assertEqual(raised.exception.detail["code"], "INVALID_RESET_TOKEN")

    async def test_unlock_link_works_once_for_the_current_lock(self):
        locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
        user = self.make_user(login_fail_count=5, locked_until=locked_until)
        service = UserService(FakeDatabase(user))
        token = create_token(user.id, "user_unlock", 5, {"lock": int(locked_until.timestamp())})

        await service.unlock_account(token)
        self.assertIsNone(user.locked_until)
        self.assertEqual(user.login_fail_count, 0)
        with self.assertRaises(HTTPException) as raised:
            await service.unlock_account(token)  # 같은 링크 재사용
        self.assertEqual(raised.exception.detail["code"], "INVALID_UNLOCK_TOKEN")

        user.locked_until = locked_until + timedelta(hours=2)  # 다시 잠겼을 때 이전 잠금의 링크는 무효
        with self.assertRaises(HTTPException):
            await service.unlock_account(token)


# 결제 승인 누락 보정(A5)과 불확정 오류 처리: 결제키 선저장, 확정 거절만 실패, 불확정은 즉시 조회, 정리 작업은 주문별 반영
class PaymentReconciliationTests(unittest.IsolatedAsyncioTestCase):
    def make_order(self, **overrides):
        from backend.domain.orders.models.orders import Order

        values = dict(
            id=1,
            order_number="ARAM-20261001-AAAAAAAAAAAA",
            user_id=7,
            status="pending",
            order_name="상품",
            total_amount=12000,
            from_cart=False,
            payment_key=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        values.update(overrides)
        return Order(**values)

    def done_payment(self, order, payment_key="pk_1", **overrides):
        return {"status": "DONE", "orderId": order.order_number, "paymentKey": payment_key, "totalAmount": order.total_amount,
                "method": "카드", "approvedAt": "2026-10-01T10:00:00+09:00", **overrides}

    def service_for(self, order):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from backend.domain.orders.services.orders import OrderService

        commits = []

        class Db:
            async def execute(self, _statement):
                return FakeResult(order)

            async def commit(self):
                commits.append((order.status, order.payment_key))

            async def rollback(self):
                pass

        service = OrderService.__new__(OrderService)
        service.db = Db()
        service.user_service = SimpleNamespace(_get_user_from_access_token=AsyncMock(return_value=SimpleNamespace(id=7)))
        service._order_payload = AsyncMock(return_value={"order_id": order.order_number})
        return service, commits

    async def confirm(self, order, confirm_effect, lookup_effect=None, payment_key="pk_1"):
        from unittest.mock import AsyncMock, patch

        from backend.domain.orders.schemas.orders import OrderConfirmRequest

        service, commits = self.service_for(order)
        request = OrderConfirmRequest(payment_key=payment_key, order_id=order.order_number, amount=order.total_amount)
        with patch("backend.domain.orders.services.orders.toss.confirm_payment", AsyncMock(**confirm_effect)), \
                patch("backend.domain.orders.services.orders.toss.get_payment", AsyncMock(**(lookup_effect or {"return_value": None}))) as lookup:
            try:
                return await service.confirm_payment("token", request), commits, lookup
            except HTTPException as error:
                return error, commits, lookup

    def gateway_error(self, http_status, code):
        from backend.core.errors import api_error

        return api_error(400, "PAYMENT_FAILED", "결제사 오류", gateway_code=code, gateway_status=http_status)

    async def test_payment_key_is_saved_before_gateway_call(self):
        from backend.core.errors import api_error

        order = self.make_order()
        result, commits, _ = await self.confirm(order, {"side_effect": api_error(502, "PAYMENT_GATEWAY_UNAVAILABLE", "연결 실패")})
        self.assertEqual(commits[0], ("pending", "pk_1"))  # 결제사 호출 전에 결제키 저장
        self.assertIsNotNone(order.payment_attempted_at)
        self.assertEqual(result.detail["code"], "PAYMENT_CONFIRMATION_PENDING")
        self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))

        result, _, _ = await self.confirm(order, {"return_value": {}}, payment_key="pk_other")
        self.assertEqual(result.detail["code"], "PAYMENT_KEY_MISMATCH")

    async def test_idempotent_processing_or_lost_response_is_settled_by_lookup(self):
        for http_status, code in (
            (409, "IDEMPOTENT_REQUEST_PROCESSING"),
            (400, "ALREADY_PROCESSING_REQUEST"),
            (400, "ALREADY_PROCESSED_PAYMENT"),
            (500, "FAILED_INTERNAL_SYSTEM_PROCESSING"),
            (429, "TOO_MANY_REQUESTS"),
        ):
            order = self.make_order()
            result, _, lookup = await self.confirm(order, {"side_effect": self.gateway_error(http_status, code)}, {"return_value": self.done_payment(order)})
            self.assertEqual(order.status, "paid", code)  # 실제 승인됐으면 완료 처리
            lookup.assert_awaited_once()

            order = self.make_order()
            result, _, _ = await self.confirm(order, {"side_effect": self.gateway_error(http_status, code)}, {"return_value": {"status": "IN_PROGRESS"}})
            self.assertEqual(result.detail["code"], "PAYMENT_CONFIRMATION_PENDING", code)
            self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))  # 실패로 확정하지 않음

    async def test_broken_success_body_or_missing_code_is_uncertain_not_failed(self):
        import httpx
        from unittest.mock import AsyncMock, patch

        from backend.core.config import settings
        from backend.domain.orders.schemas.orders import OrderConfirmRequest
        from backend.domain.orders.services import toss

        original = settings.toss_secret_key
        object.__setattr__(settings, "toss_secret_key", "test_sk_dummy")
        self.addCleanup(object.__setattr__, settings, "toss_secret_key", original)
        real = httpx.AsyncClient
        bodies = (
            (200, b"{not json", "application/json"),  # 깨진 JSON
            (200, b"[1, 2]", "application/json"),  # 배열
            (400, b"<html>bad gateway</html>", "text/html"),  # 코드 없는 4xx
        )
        for status_code, body, content_type in bodies:
            order = self.make_order()
            service, _ = self.service_for(order)
            handler = lambda request, code=status_code, content=body, kind=content_type: httpx.Response(
                code, content=content, headers={"content-type": kind}
            )
            request = OrderConfirmRequest(payment_key="pk_1", order_id=order.order_number, amount=order.total_amount)
            with patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda handler=handler, **kw: real(transport=httpx.MockTransport(handler), **kw)), \
                    patch("backend.domain.orders.services.orders.toss.get_payment", AsyncMock(return_value=None)):
                with self.assertRaises(HTTPException) as raised:
                    await service.confirm_payment("token", request)
            self.assertEqual(raised.exception.detail["code"], "PAYMENT_CONFIRMATION_PENDING", body)
            self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))

        # 필드가 빠진 200 응답도 승인 확인 전까지는 실패가 아님
        order = self.make_order()
        result, _, _ = await self.confirm(order, {"return_value": {"status": "DONE"}})
        self.assertEqual(result.detail["code"], "PAYMENT_CONFIRMATION_PENDING")

        # 결제 조회 응답이 깨져도 예외(정리 작업이 다음 주기에 재시도)
        handler = lambda request: httpx.Response(200, content=b"oops", headers={"content-type": "application/json"})
        with patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
            with self.assertRaises(RuntimeError):
                await toss.get_payment("pk_1")

    async def test_unexpected_error_during_confirm_is_uncertain(self):
        order = self.make_order()
        with self.assertLogs("backend.domain.orders.services.orders", "ERROR"):
            result, _, lookup = await self.confirm(order, {"side_effect": ValueError("decode")}, {"return_value": self.done_payment(order)})
        self.assertEqual(order.status, "paid")  # 조회로 승인 확인되면 완료
        lookup.assert_awaited_once()

    async def test_paid_gateway_result_with_database_failure_stays_pending(self):
        from unittest.mock import AsyncMock, patch

        from backend.domain.orders.schemas.orders import OrderConfirmRequest

        for route in ("confirm", "lookup"):
            order = self.make_order()
            service, _ = self.service_for(order)
            commit_count = 0

            async def fail_final_commit():
                nonlocal commit_count
                commit_count += 1
                if commit_count == 2:
                    raise RuntimeError("database connection lost after payment approval")

            service.db.commit = fail_final_commit
            payment = self.done_payment(order)
            confirm_effect = (
                {"return_value": payment}
                if route == "confirm"
                else {"side_effect": self.gateway_error(500, "COMMON_ERROR")}
            )
            request = OrderConfirmRequest(payment_key="pk_1", order_id=order.order_number, amount=order.total_amount)
            with patch("backend.domain.orders.services.orders.toss.confirm_payment", AsyncMock(**confirm_effect)), \
                    patch("backend.domain.orders.services.orders.toss.get_payment", AsyncMock(return_value=payment)):
                with self.assertLogs("backend.domain.orders.services.orders", "ERROR"), self.assertRaises(HTTPException) as raised:
                    await service.confirm_payment("token", request)
            self.assertEqual(raised.exception.detail["code"], "PAYMENT_CONFIRMATION_PENDING")

    def test_confirmation_amount_uses_supported_card_payment_range(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import OrderConfirmRequest

        for amount in (0, 99, 2_147_483_648):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                OrderConfirmRequest(payment_key="pk_1", order_id="ARAM-20261001-AAAAAAAAAAAA", amount=amount)

    async def test_definitive_rejection_marks_failed_but_keeps_key_for_recheck(self):
        order = self.make_order()
        result, _, lookup = await self.confirm(order, {"side_effect": self.gateway_error(400, "REJECT_CARD_COMPANY")})
        self.assertEqual(result.detail["code"], "PAYMENT_FAILED")
        self.assertEqual((order.status, order.payment_key), ("failed", "pk_1"))
        lookup.assert_not_awaited()

    async def test_success_response_must_match_order_key_and_amount(self):
        order = self.make_order()
        mismatched = self.done_payment(order, paymentKey="pk_someone_else")
        with self.assertLogs("backend.domain.orders.services.orders", "ERROR"):
            result, _, lookup = await self.confirm(order, {"return_value": mismatched}, {"return_value": None})
        self.assertEqual(result.detail["code"], "PAYMENT_CONFIRMATION_PENDING")
        self.assertEqual(order.status, "pending")
        lookup.assert_awaited_once()

        order = self.make_order()
        await self.confirm(order, {"return_value": self.done_payment(order)})
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.paid_at, datetime(2026, 10, 1, 1, 0, tzinfo=timezone.utc))

    async def apply(self, order, payment):
        service, commits = self.service_for(order)
        await service.apply_payment_lookup(order.id, "pk_1", payment)
        return commits

    async def test_lookup_result_is_applied_per_order(self):
        old_attempt = datetime.now(timezone.utc) - timedelta(days=2)
        order = self.make_order(payment_key="pk_1", payment_attempted_at=old_attempt, status="failed", failure_message="이전 오류")
        await self.apply(order, self.done_payment(order))
        self.assertEqual(order.status, "paid")
        self.assertIsNone(order.failure_message)

        for payment in ({"status": "EXPIRED"}, {"status": "CANCELED"}, None):
            order = self.make_order(payment_key="pk_1", payment_attempted_at=old_attempt, status="failed")
            await self.apply(order, payment)
            self.assertEqual((order.status, order.payment_key), ("failed", None))  # 미결제 확인 후에만 삭제 대상

        recent_attempt = datetime.now(timezone.utc) - timedelta(minutes=20)
        order = self.make_order(payment_key="pk_1", payment_attempted_at=recent_attempt)
        with self.assertLogs("backend.domain.orders.services.orders", "WARNING"):
            await self.apply(order, None)
        self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))  # 첫 404는 결제키를 보존해 재확인

        order = self.make_order(payment_key="pk_1")
        await self.apply(order, {"status": "READY"})
        self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))  # 아직 진행 중이면 다음 주기에 재확인

        order = self.make_order(payment_key="pk_1")
        with self.assertLogs("backend.domain.orders.services.orders", "ERROR"):
            await self.apply(order, {"status": "PARTIAL_CANCELED"})
        self.assertEqual((order.status, order.payment_key), ("pending", "pk_1"))

        order = self.make_order(payment_key="pk_newer", status="pending")
        await self.apply(order, {"status": "EXPIRED"})  # 조회 중 다른 결제키로 바뀐 주문은 건드리지 않음
        self.assertEqual((order.status, order.payment_key), ("pending", "pk_newer"))

    async def test_cleanup_deletes_only_orders_without_payment_key(self):
        from sqlalchemy.dialects import postgresql

        from backend.domain.orders.services.orders import OrderService

        statements = []

        class Db:
            async def execute(self, statement):
                statements.append(statement)
                return type("R", (), {"rowcount": 0, "all": lambda self: []})()

        service = OrderService.__new__(OrderService)
        service.db = Db()
        await service.purge_unpaid_orders(commit=False)
        self.assertIn("payment_key IS NULL", str(statements[0].compile(dialect=postgresql.dialect())))
        await service.reconcile_candidates()
        sql = str(statements[1].compile(dialect=postgresql.dialect()))
        self.assertIn("payment_key IS NOT NULL", sql)
        self.assertIn("payment_attempted_at", sql)
        self.assertIn("status IN", sql)  # pending과 확정 거절된 failed 모두 결제사에서 한 번 더 확인

    async def test_toss_payment_lookup_maps_not_found_and_errors(self):
        import httpx
        from unittest.mock import patch

        from backend.core.config import settings
        from backend.domain.orders.services import toss

        original = settings.toss_secret_key
        object.__setattr__(settings, "toss_secret_key", "test_sk_dummy")
        self.addCleanup(object.__setattr__, settings, "toss_secret_key", original)
        real = httpx.AsyncClient
        for status_code, expected in ((200, {"status": "DONE"}), (404, None)):
            handler = lambda request, code=status_code: httpx.Response(code, json={"status": "DONE"})
            with patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda handler=handler, **kw: real(transport=httpx.MockTransport(handler), **kw)):
                self.assertEqual(await toss.get_payment("pk/1"), expected)
        handler = lambda request: httpx.Response(500, json={})
        with patch("backend.domain.orders.services.toss.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
            with self.assertRaises(RuntimeError):
                await toss.get_payment("pk_1")

# 여러 창에서 동시에 재발급할 때 리프레시 토큰 행을 잠가 차례로 처리하는지 확인
class RefreshRowLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_lookup_locks_row_but_signout_does_not(self):
        statements = []

        class Db:
            async def execute(self, statement):
                statements.append(statement)
                return FakeResult(None)

        for service in (UserService(Db()), AdminAccountService(Db())):
            statements.clear()
            with self.assertRaises(HTTPException):
                await service.refresh_session("unknown-token")
            self.assertIsNotNone(statements[0]._for_update_arg)
            statements.clear()
            await service.revoke_refresh_session("unknown-token")
            self.assertIsNone(statements[0]._for_update_arg)


# 관리자 TOTP 2단계 인증: 비밀값 암호화·QR 등록 주소·코드 재사용 방지·복구 코드·로그인 2단계 흐름
class AdminMfaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import pyotp

        from backend.domain.admins.services.mfa import encrypt_secret, generate_secret, hash_recovery_code

        self.pyotp = pyotp
        self.secret = generate_secret()
        self.admin = AdminAccount(
            id=1,
            username="admin",
            password_hash=hash_password("Password!1"),
            created_at=datetime.now(timezone.utc),
            is_active=True,
            auth_version=3,
            mfa_secret_encrypted=encrypt_secret(self.secret),
            mfa_enabled_at=datetime.now(timezone.utc),
            mfa_last_used_step=None,
            mfa_recovery_code_hashes=[hash_recovery_code("ABCD-EFGH")],
        )
        self.service = AdminAccountService(FakeDatabase(self.admin))
        self.service.limiter = LoginRateLimiter(clock=lambda: 1_000.0)

    def current_code(self):
        return self.pyotp.TOTP(self.secret).now()

    async def pending_token(self):
        result = await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")
        self.assertEqual(result["mfa_required"], True)
        self.assertNotIn("access_token", result)  # 비밀번호만으로는 로그인 토큰을 주지 않음
        return result["mfa_token"]

    def test_secret_is_encrypted_and_uri_works_with_authenticator_apps(self):
        from urllib.parse import parse_qs, urlparse

        from backend.domain.admins.services.mfa import decrypt_secret, provisioning_uri

        self.assertNotIn(self.secret, self.admin.mfa_secret_encrypted)
        self.assertEqual(decrypt_secret(self.admin.mfa_secret_encrypted), self.secret)
        uri = urlparse(provisioning_uri(self.secret, "admin"))
        self.assertEqual((uri.scheme, uri.netloc), ("otpauth", "totp"))
        self.assertEqual(parse_qs(uri.query)["secret"], [self.secret])
        self.assertEqual(parse_qs(uri.query)["issuer"], ["Aram Market"])

    def test_code_matches_within_one_step_window_only(self):
        from backend.domain.admins.services.mfa import matching_step

        now = 1_800_000_000.0
        totp = self.pyotp.TOTP(self.secret)
        step = int(now // 30)
        self.assertEqual(matching_step(self.secret, totp.at(now), now), step)
        self.assertEqual(matching_step(self.secret, totp.at(now - 30), now), step - 1)
        self.assertIsNone(matching_step(self.secret, totp.at(now - 90), now))
        self.assertIsNone(matching_step(self.secret, "12ab56", now))

    def test_recovery_codes_are_formatted_and_hash_ignores_case_and_hyphen(self):
        from backend.domain.admins.services.mfa import generate_recovery_codes, hash_recovery_code

        codes = generate_recovery_codes()
        self.assertEqual(len(set(codes)), 10)
        self.assertTrue(all(len(code) == 9 and code[4] == "-" for code in codes))
        self.assertEqual(hash_recovery_code("abcd efgh"), hash_recovery_code("ABCD-EFGH"))

    async def test_valid_code_completes_login_and_same_code_cannot_be_reused(self):
        from backend.domain.admins.schemas.admins import MfaVerifyRequest

        token = await self.pending_token()
        code = self.current_code()
        result = await self.service.verify_mfa(token, MfaVerifyRequest(code=code), "127.0.0.1")
        self.assertEqual(decode_token(result["access_token"], "admin_access")["sub"], 1)
        self.assertIsNotNone(self.admin.mfa_last_used_step)
        with self.assertRaises(HTTPException) as raised:
            await self.service.verify_mfa(token, MfaVerifyRequest(code=code), "127.0.0.1")
        self.assertEqual(raised.exception.detail["code"], "INVALID_MFA_CODE")

    async def test_recovery_code_works_once(self):
        from backend.domain.admins.schemas.admins import MfaVerifyRequest

        token = await self.pending_token()
        await self.service.verify_mfa(token, MfaVerifyRequest(code="abcd-efgh"), "127.0.0.1")
        self.assertEqual(self.admin.mfa_recovery_code_hashes, [])
        with self.assertRaises(HTTPException):
            await self.service.verify_mfa(token, MfaVerifyRequest(code="ABCD-EFGH"), "127.0.0.1")

    async def test_wrong_codes_are_rate_limited_and_password_success_does_not_reset(self):
        from backend.domain.admins.schemas.admins import MfaVerifyRequest

        token = await self.pending_token()
        codes = []
        for _ in range(5):
            with self.assertRaises(HTTPException) as raised:
                await self.service.verify_mfa(token, MfaVerifyRequest(code="000000"), "127.0.0.1")
            codes.append(raised.exception.detail["code"])
        self.assertEqual(codes[:4], ["INVALID_MFA_CODE"] * 4)
        self.assertEqual(codes[4], "LOGIN_RATE_LIMITED")
        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")
        self.assertEqual(raised.exception.detail["code"], "LOGIN_RATE_LIMITED")

    async def test_expired_or_stale_pending_token_requires_restart(self):
        from backend.domain.admins.schemas.admins import MfaVerifyRequest

        for token in (None, "garbage", create_token(1, "admin_mfa_pending", 5, {"ver": 2}), create_token(1, "admin_access", 5, {"ver": 3})):
            with self.assertRaises(HTTPException) as raised:
                await self.service.verify_mfa(token, MfaVerifyRequest(code=self.current_code()), "127.0.0.1")
            self.assertEqual(raised.exception.detail["code"], "MFA_SESSION_EXPIRED")

    async def test_mfa_required_or_partial_setup_blocks_password_only_login(self):
        from backend.core.config import settings

        self.admin.mfa_enabled_at = None
        self.admin.mfa_secret_encrypted = None
        original = settings.admin_mfa_required
        object.__setattr__(settings, "admin_mfa_required", True)
        self.addCleanup(object.__setattr__, settings, "admin_mfa_required", original)
        with self.assertLogs("backend.domain.admins.services.admins", "ERROR"), self.assertRaises(HTTPException) as raised:
            await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")
        self.assertEqual((raised.exception.status_code, raised.exception.detail["code"]), (503, "ADMIN_MFA_NOT_CONFIGURED"))

        object.__setattr__(settings, "admin_mfa_required", False)
        self.admin.mfa_enabled_at = datetime.now(timezone.utc)  # 등록 시각만 있고 비밀값이 없는 부분 상태
        with self.assertLogs("backend.domain.admins.services.admins", "ERROR"), self.assertRaises(HTTPException) as raised:
            await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")
        self.assertEqual(raised.exception.detail["code"], "ADMIN_MFA_NOT_CONFIGURED")

    async def test_admin_without_mfa_still_logs_in_with_password(self):
        from backend.core.config import settings

        original = settings.admin_mfa_required
        object.__setattr__(settings, "admin_mfa_required", False)  # 로컬 개발에서만 명시적으로 허용
        self.addCleanup(object.__setattr__, settings, "admin_mfa_required", original)
        self.admin.mfa_enabled_at = None
        self.admin.mfa_secret_encrypted = None
        with self.assertLogs("backend.domain.admins.services.admins", "WARNING"):
            result = await self.service.signin(SignInRequest(username="admin", password="Password!1"), "127.0.0.1")
        self.assertIn("access_token", result)


# 메일 링크 토큰으로 계정을 바꾸는 요청은 회원 행을 잠그고, 오래된 이메일 변경 링크는 다른 변경이 끝나면 무효
class TokenFlowLockTests(unittest.IsolatedAsyncioTestCase):
    def make_user(self):
        return User(
            id=51, username="lock_user", password_hash=hash_password("CurrentPassword!1"), nickname="잠금", email="first@example.com",
            is_active=True, status="active", auth_version=0, login_fail_count=0, service_policy=True, privacy_policy=True,
            marketing_consent=False,
        )

    def database(self, user, statements):
        class Db(FakeDatabase):
            async def execute(self, query):
                statements.append(query)
                is_lock = getattr(query, "_for_update_arg", None) is not None
                return FakeResult(self.admin if is_lock else None)

        return Db(user)

    async def test_token_flows_lock_user_row(self):
        from unittest.mock import AsyncMock, patch

        from backend.domain.users.schemas.users import CancelWithdrawalRequest

        user = self.make_user()
        statements = []
        service = UserService(self.database(user, statements))
        with patch("backend.domain.users.services.users.send_security_notice_email", AsyncMock(return_value=True)):
            reset = create_token(51, "user_password_reset", 5, {"ver": 0, "email": "first@example.com"})
            await service.reset_password(PasswordResetConfirmRequest(token=reset, new_password="NewPassword!1"))
            self.assertIsNotNone(statements[0]._for_update_arg)

            with self.assertRaises(HTTPException) as raised:  # 같은 링크 두 번째 사용(auth_version 증가)은 거부
                await service.reset_password(PasswordResetConfirmRequest(token=reset, new_password="OtherPassword!1"))
            self.assertEqual(raised.exception.detail["code"], "INVALID_RESET_TOKEN")

        for call in (
            lambda: service.unlock_account(create_token(51, "user_unlock", 5, {"lock": 0})),
            lambda: service.cancel_withdrawal(CancelWithdrawalRequest(recovery_token=create_token(51, "user_withdrawal_recovery", 5, {"ver": 1}))),
        ):
            statements.clear()
            with self.assertRaises(HTTPException):
                await call()
            self.assertIsNotNone(statements[0]._for_update_arg)

    async def test_old_email_change_link_is_invalid_after_another_change(self):
        from unittest.mock import AsyncMock, patch

        user = self.make_user()
        service = UserService(self.database(user, []))
        first = create_token(51, "user_email_change", 5, {"new_email": "second@example.com", "current_email": "first@example.com", "ver": 0})
        stale = create_token(51, "user_email_change", 5, {"new_email": "attacker@example.com", "current_email": "first@example.com", "ver": 0})
        with patch("backend.domain.users.services.users.send_security_notice_email", AsyncMock(return_value=True)):
            await service.confirm_email_change(VerifyEmailRequest(token=first))
            self.assertEqual(user.email, "second@example.com")
            with self.assertRaises(HTTPException) as raised:
                await service.confirm_email_change(VerifyEmailRequest(token=stale))
        self.assertEqual(raised.exception.detail["code"], "INVALID_EMAIL_CHANGE_TOKEN")
        self.assertEqual(user.email, "second@example.com")


# 로그인 상태의 비밀번호 변경·탈퇴는 회원 행을 잠근 뒤 최신 값으로 다시 확인(동시 요청의 lost update 방지)
class PasswordChangeLockTests(unittest.IsolatedAsyncioTestCase):
    def make_user(self, **overrides):
        values = dict(
            id=61, username="change_user", password_hash=hash_password("CurrentPassword!1"), nickname="변경", email="change@example.com",
            is_active=True, status="active", auth_version=0, login_fail_count=0, service_policy=True, privacy_policy=True,
            marketing_consent=False,
        )
        values.update(overrides)
        return User(**values)

    def service(self, token_user, locked_user):
        from unittest.mock import AsyncMock, patch

        events = []

        class Db(FakeDatabase):
            async def execute(self, query, params=None):
                if getattr(query, "_for_update_arg", None) is not None:
                    events.append("lock")
                    return FakeResult(locked_user)
                return FakeResult(token_user)

            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

        for name, mock in (("reserve_attempt", AsyncMock(return_value=3)), ("release_attempt", AsyncMock()), ("discard_attempt", AsyncMock()),
                           ("send_security_notice_email", AsyncMock(return_value=True))):
            patcher = patch(f"backend.domain.users.services.users.{name}", mock)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        return UserService(Db(token_user)), events

    def token(self, user):
        return create_token(user.id, "user_access", 5, {"ver": user.auth_version, "sid": "session-1"})

    async def test_change_uses_locked_latest_row_and_commits_once(self):
        user = self.make_user()
        locked = self.make_user()  # 잠금 시점에 다시 읽은 최신 행
        service, events = self.service(user, locked)
        await service.change_password(self.token(user), ChangePasswordRequest(current_password="CurrentPassword!1", new_password="NewPassword!1"))
        self.assertEqual(events[0], "lock")
        self.assertTrue(verify_password("NewPassword!1", locked.password_hash))  # 잠근 최신 행에 반영
        self.assertEqual(locked.auth_version, 1)
        self.discard_attempt.assert_awaited_once()  # 성공 시도 기록은 변경과 같은 커밋으로 삭제
        self.release_attempt.assert_not_awaited()

    async def test_second_concurrent_change_is_rejected_after_first_commits(self):
        user = self.make_user()
        already_changed = self.make_user(auth_version=1, password_hash=hash_password("FirstWinner!1"))
        service, events = self.service(user, already_changed)
        with self.assertRaises(HTTPException) as raised:
            await service.change_password(self.token(user), ChangePasswordRequest(current_password="CurrentPassword!1", new_password="Overwrite!1"))
        self.assertEqual(raised.exception.detail["code"], "INVALID_ACCESS_TOKEN")
        self.assertTrue(verify_password("FirstWinner!1", already_changed.password_hash))  # 앞선 변경을 덮어쓰지 않음
        self.assertIn("rollback", events)
        self.release_attempt.assert_awaited_once()  # 비밀번호 실패가 아니므로 시도 기록 삭제

    async def test_deletion_also_locks_and_wrong_password_keeps_attempt(self):
        from backend.domain.users.schemas.users import DeleteAccountRequest

        user = self.make_user()
        locked = self.make_user()
        service, events = self.service(user, locked)
        with self.assertRaises(HTTPException) as raised:
            await service.request_account_deletion(self.token(user), DeleteAccountRequest(password="WrongPassword!1", confirmation="회원 탈퇴"))
        self.assertEqual(raised.exception.detail["code"], "INVALID_PASSWORD")
        self.assertEqual(events, ["lock"])
        self.discard_attempt.assert_not_awaited()  # 틀린 비밀번호는 실패로 남김
        await service.request_account_deletion(self.token(user), DeleteAccountRequest(password="CurrentPassword!1", confirmation="회원 탈퇴"))
        self.assertEqual(locked.status, "pending_deletion")
