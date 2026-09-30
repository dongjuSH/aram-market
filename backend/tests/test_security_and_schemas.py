# 관리자·사용자 인증 토큰 분리와 IP 로그인 제한 규칙 테스트

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template

from fastapi import HTTPException, Response
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


# 관리자 서비스가 사용하는 조회·커밋 기능만 제공하는 메모리 DB
class FakeDatabase:
    def __init__(self, admin: AdminAccount | None):
        self.admin = admin
        self.commit_count = 0
        self.added = []

    def add(self, row):
        self.added.append(row)

    async def execute(self, _query):
        return FakeResult(self.admin)

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
        token = create_token(user.id, "user_password_reset", 5, {"ver": user.auth_version})

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
    async def _get_refresh_row(self, token_hash):
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
    async def _get_refresh_row(self, token_hash):
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
    async def test_only_client_failures_are_recorded(self):
        from unittest.mock import AsyncMock, patch

        from backend.core import rate_limit

        async def failing(code, status_code):
            raise HTTPException(status_code=status_code, detail={"code": code, "message": "x"})

        with patch.object(rate_limit, "check_limit", AsyncMock()), patch.object(rate_limit, "record_attempt", AsyncMock()) as record:
            with self.assertRaises(HTTPException):
                await rate_limit.guard_failures(None, "n", "1.1.1.1", 5, 60, lambda: failing("INVALID_REFRESH_TOKEN", 401))
            self.assertEqual(record.await_count, 1)
            with self.assertRaises(HTTPException):
                await rate_limit.guard_failures(None, "n", "1.1.1.1", 5, 60, lambda: failing("REFRESH_IN_PROGRESS", 401))
            self.assertEqual(record.await_count, 1)
            self.assertEqual(await rate_limit.guard_failures(None, "n", "1.1.1.1", 5, 60, AsyncMock(return_value="ok")), "ok")
            self.assertEqual(record.await_count, 1)


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


# 배송지 입력 검증과 배송 상태 진행 순서 검증
class ShippingRulesTests(unittest.TestCase):
    def valid(self, **overrides):
        values = dict(recipient_name="홍길동", recipient_phone="01012345678", address="서울특별시 마포구 아람로 12")
        values.update(overrides)
        return values

    def test_phone_is_normalized_to_hyphen_format(self):
        from backend.domain.orders.schemas.orders import ShippingAddress

        self.assertEqual(ShippingAddress(**self.valid()).recipient_phone, "010-1234-5678")
        self.assertEqual(ShippingAddress(**self.valid(recipient_phone="010 123 4567")).recipient_phone, "010-123-4567")

    def test_invalid_shipping_input_is_rejected(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import ShippingAddress

        for invalid in ({"recipient_phone": "123"}, {"recipient_name": "김"}, {"address": "서울"}):
            with self.assertRaises(ValidationError):
                ShippingAddress(**self.valid(**invalid))

    def test_order_creation_requires_shipping_and_delivery_status_is_limited(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import DeliveryStatusRequest, OrderCreateRequest

        with self.assertRaises(ValidationError):
            OrderCreateRequest(items=[{"product_id": 1, "quantity": 1}])
        self.assertEqual(DeliveryStatusRequest(status="shipping").status, "shipping")
        with self.assertRaises(ValidationError):
            DeliveryStatusRequest(status="paid")  # 되돌리기·임의 상태는 요청 자체가 불가

    def test_delivery_flow_order(self):
        from backend.domain.orders.services.orders import DELIVERY_FLOW

        self.assertEqual(DELIVERY_FLOW, ("paid", "preparing", "shipping", "delivered"))


# 회원정보 수정·이메일 변경 입력 검증
class ProfileRulesTests(unittest.TestCase):
    def valid(self, **overrides):
        values = dict(nickname="아람이", name="홍길동", phone="010-1234-5678")
        values.update(overrides)
        return values

    def test_profile_normalizes_name_and_phone(self):
        from backend.domain.users.schemas.users import UpdateProfileRequest

        request = UpdateProfileRequest(**self.valid(phone="01012345678"))
        self.assertEqual(request.phone, "010-1234-5678")
        self.assertEqual(request.nickname, "아람이")

    def test_profile_rejects_bad_nickname_phone_and_name(self):
        from pydantic import ValidationError

        from backend.domain.users.schemas.users import UpdateProfileRequest

        for invalid in ({"nickname": "a"}, {"phone": "123"}, {"name": "김"}):
            with self.assertRaises(ValidationError):
                UpdateProfileRequest(**self.valid(**invalid))

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
        values = dict(label=" 집 ", recipient_name="홍길동", recipient_phone="01012345678", address="서울특별시 마포구 아람로 12")
        values.update(overrides)
        return values

    def test_address_request_normalizes_fields_and_defaults(self):
        from backend.domain.users.schemas.users import AddressRequest

        request = AddressRequest(**self.valid(postcode=" 04001 "))
        self.assertEqual((request.label, request.recipient_phone, request.postcode, request.is_default), ("집", "010-1234-5678", "04001", False))

    def test_address_request_rejects_invalid_values(self):
        from pydantic import ValidationError

        from backend.domain.users.schemas.users import AddressRequest

        for invalid in ({"label": "  "}, {"label": "가" * 21}, {"recipient_phone": "123"}, {"recipient_name": "김"}, {"address": "서울"}):
            with self.assertRaises(ValidationError):
                AddressRequest(**self.valid(**invalid))

    def test_order_shipping_shares_address_validation(self):
        from pydantic import ValidationError

        from backend.domain.orders.schemas.orders import ShippingAddress

        shipping = ShippingAddress(recipient_name="홍길동", recipient_phone="01012345678", address="서울특별시 마포구 아람로 12", delivery_memo=" 문 앞 ")
        self.assertEqual((shipping.recipient_phone, shipping.delivery_memo), ("010-1234-5678", "문 앞"))
        with self.assertRaises(ValidationError):
            ShippingAddress(recipient_name="홍길동", recipient_phone="1", address="서울특별시 마포구 아람로 12")
