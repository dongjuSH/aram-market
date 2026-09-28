# 관리자·사용자 인증 토큰 분리와 IP 로그인 제한 규칙 테스트

import unittest
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from fastapi import HTTPException
from backend.core.security import create_token, decode_token, hash_password, verify_password
from backend.domain.admins.models.admins import AdminAccount
from backend.domain.admins.schemas.admins import SignInRequest, validate_password
from backend.domain.admins.services.admins import AdminAccountService
from backend.domain.admins.services.rate_limit import LoginRateLimiter
from backend.domain.users.models.users import User
from backend.domain.users.schemas.users import ChangePasswordRequest, PasswordResetConfirmRequest, SignUpRequest
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
            nickname="사용자1",
            email="USER@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        self.assertEqual(request.email, "user@example.com")
        self.assertFalse(request.marketing_consent)


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
        token = create_token(user.id, "user_access", 5, {"ver": user.auth_version})

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

if __name__ == "__main__":
    unittest.main()
