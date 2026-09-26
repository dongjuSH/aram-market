# 비밀번호 보안·입력 검증·로그인 잠금·회원가입 중복 오류 테스트

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from backend.core.config import Settings
from backend.core.security import create_token, decode_token, hash_password, verify_password
from backend.domain.users.models.users import User
from backend.domain.users.schemas.users import (
    CancelWithdrawalRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    FindUsernameRequest,
    PasswordResetEmailRequest,
    SignInRequest,
    SignUpRequest,
)
from backend.domain.users.services.users import UserService
from pydantic import ValidationError


# 인증 비밀키 환경설정 검증 테스트
class ConfigTests(unittest.TestCase):
    # 32자 미만 인증 비밀키의 서버 설정 생성 차단
    def test_rejects_auth_secret_shorter_than_32_characters(self):
        with self.assertRaisesRegex(ValueError, "AUTH_SECRET_KEY"):
            Settings(database_url="postgresql+asyncpg://test", auth_secret_key="x" * 31)


class SecurityTests(unittest.TestCase):
    def test_password_is_hashed_and_verified(self):
        password_hash = hash_password("Valid!Password1")
        self.assertNotEqual(password_hash, "Valid!Password1")
        self.assertTrue(verify_password("Valid!Password1", password_hash))
        self.assertFalse(verify_password("Wrong!Password1", password_hash))

    def test_signed_token_round_trip(self):
        token = create_token(17, "access", 5)
        payload = decode_token(token, "access")
        self.assertEqual(payload["sub"], 17)

        with self.assertRaises(ValueError):
            decode_token(token, "unlock")


class SignUpSchemaTests(unittest.TestCase):
    def test_accepts_typical_signup_values(self):
        request = SignUpRequest(
            username="user_123",
            password="Valid!Password1",
            nickname="사용자1",
            email="user@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        self.assertEqual(request.username, "user_123")

    def test_rejects_invalid_values_and_missing_consent(self):
        with self.assertRaises(ValidationError):
            SignUpRequest(
                username="한글아이디",
                password="password-only",
                nickname="사용자1",
                email="invalid-email",
                service_policy=False,
                privacy_policy=False,
            )


class FakeResult:
    def __init__(self, user, users=None):
        self.user = user
        self.users = users if users is not None else ([] if user is None else [user])

    def scalar_one_or_none(self):
        return self.user

    def scalars(self):
        return self

    def all(self):
        return self.users


class FakeDatabase:
    def __init__(self, user):
        self.user = user
        self.commit_count = 0

    async def execute(self, _query):
        return FakeResult(self.user)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        pass

    async def get(self, _model, _identifier):
        return self.user

    def add(self, _user):
        pass


class SignInLockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user = User(
            id=1,
            username="login_user",
            password_hash=hash_password("Valid!Password1"),
            nickname="로그인사용자",
            email="login@example.com",
            is_active=True,
            login_fail_count=0,
            locked_until=None,
            service_policy=True,
            privacy_policy=True,
            status="active",
            auth_version=0,
        )
        self.database = FakeDatabase(self.user)
        self.service = UserService(self.database)

    async def test_login_failures_do_not_expose_attempt_count(self):
        request = SignInRequest(username="login_user", password="Wrong!Password1")

        with self.assertRaises(HTTPException):
            await self.service.signin(request)

        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(request)

        self.assertEqual(raised.exception.detail["code"], "INVALID_CREDENTIALS")
        self.assertNotIn("2회", raised.exception.detail["message"])

    async def test_fifth_failure_locks_for_one_hour(self):
        request = SignInRequest(username="login_user", password="Wrong!Password1")

        with patch(
            "backend.domain.users.services.users.send_account_unlock_email",
            new=AsyncMock(return_value=True),
        ):
            for _attempt in range(4):
                with self.assertRaises(HTTPException):
                    await self.service.signin(request)

            with self.assertRaises(HTTPException) as raised:
                await self.service.signin(request)

        self.assertEqual(raised.exception.detail["code"], "INVALID_CREDENTIALS")
        self.assertEqual(self.user.login_fail_count, 5)
        self.assertIsNotNone(self.user.locked_until)

    async def test_withdrawal_grace_login_returns_recovery_prompt(self):
        self.user.status = "pending_deletion"
        self.user.withdrawn_at = datetime.now(timezone.utc) - timedelta(days=2)
        request = SignInRequest(username="login_user", password="Valid!Password1")

        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(request)

        self.assertEqual(raised.exception.detail["code"], "WITHDRAWAL_PENDING")
        self.assertIn("recovery_token", raised.exception.detail)

    async def test_withdrawal_account_wrong_password_does_not_reveal_status(self):
        self.user.status = "pending_deletion"
        self.user.withdrawn_at = datetime.now(timezone.utc) - timedelta(days=2)

        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(SignInRequest(username="login_user", password="Wrong!Password1"))

        self.assertEqual(raised.exception.detail["code"], "INVALID_CREDENTIALS")
        self.assertNotIn("탈퇴", raised.exception.detail["message"])

    async def test_expired_withdrawal_grace_blocks_login(self):
        self.user.status = "pending_deletion"
        self.user.withdrawn_at = datetime.now(timezone.utc) - timedelta(days=8)
        request = SignInRequest(username="login_user", password="Valid!Password1")

        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(request)

        self.assertEqual(raised.exception.detail["code"], "ACCOUNT_WITHDRAWN")
        self.assertEqual(self.user.status, "withdrawn")

    async def test_wrong_deletion_password_returns_field_error(self):
        token = create_token(self.user.id, "access", 5, {"ver": self.user.auth_version})
        request = DeleteAccountRequest(password="Wrong!Password1", confirmation="회원 탈퇴")

        with self.assertRaises(HTTPException) as raised:
            await self.service.request_account_deletion(token, request)

        self.assertEqual(raised.exception.detail["code"], "INVALID_PASSWORD")
        self.assertEqual(raised.exception.detail["message"], "비밀번호가 일치하지 않습니다.")

    async def test_withdrawal_request_and_cancel_restore_account(self):
        access_token = create_token(self.user.id, "access", 5, {"ver": self.user.auth_version})
        await self.service.request_account_deletion(
            access_token,
            DeleteAccountRequest(password="Valid!Password1", confirmation="회원 탈퇴"),
        )
        self.assertEqual(self.user.status, "pending_deletion")

        with self.assertRaises(HTTPException) as raised:
            await self.service.signin(SignInRequest(username="login_user", password="Valid!Password1"))

        recovery_token = raised.exception.detail["recovery_token"]
        result = await self.service.cancel_withdrawal(CancelWithdrawalRequest(recovery_token=recovery_token))
        self.assertEqual(self.user.status, "active")
        self.assertIsNone(self.user.withdrawn_at)
        self.assertIn("access_token", result)

    async def test_authenticated_password_change_invalidates_old_token(self):
        access_token = create_token(self.user.id, "access", 5, {"ver": self.user.auth_version})

        with self.assertRaises(HTTPException) as raised:
            await self.service.change_password(
                access_token,
                ChangePasswordRequest(current_password="Wrong!Password1", new_password="Changed!Password2"),
            )
        self.assertEqual(raised.exception.detail["code"], "INVALID_CURRENT_PASSWORD")

        result = await self.service.change_password(
            access_token,
            ChangePasswordRequest(current_password="Valid!Password1", new_password="Changed!Password2"),
        )
        self.assertIn("비밀번호가 변경", result["message"])
        self.assertTrue(verify_password("Changed!Password2", self.user.password_hash))
        self.assertEqual(self.user.auth_version, 1)

        with self.assertRaises(HTTPException) as raised:
            await self.service.get_current_user(access_token)
        self.assertEqual(raised.exception.detail["code"], "INVALID_ACCESS_TOKEN")

    async def test_current_user_returns_safe_profile(self):
        access_token = create_token(self.user.id, "access", 5, {"ver": self.user.auth_version})

        result = await self.service.get_current_user(access_token)

        self.assertEqual(result["user"]["username"], "login_user")
        self.assertNotIn("password_hash", result["user"])


class UserErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_username_returns_generic_message(self):
        service = UserService(FakeDatabase(None))
        request = SignInRequest(username="missing_user", password="Password!1")

        with self.assertRaises(HTTPException) as raised:
            await service.signin(request)

        self.assertEqual(raised.exception.detail["code"], "INVALID_CREDENTIALS")
        self.assertIn("아이디 또는 비밀번호", raised.exception.detail["message"])

    async def test_duplicate_username_and_email_have_field_codes(self):
        existing = User(
            id=2,
            username="duplicate_user",
            password_hash=hash_password("Password!1"),
            nickname="기존닉네임",
            email="duplicate@example.com",
            is_active=True,
            login_fail_count=0,
            status="active",
            auth_version=0,
            service_policy=True,
            privacy_policy=True,
        )
        service = UserService(FakeDatabase(existing))

        duplicate_username = SignUpRequest(
            username="duplicate_user",
            password="Password!1",
            nickname="새닉네임",
            email="new@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        with self.assertRaises(HTTPException) as username_error:
            await service.signup(duplicate_username)
        self.assertEqual(username_error.exception.detail["code"], "USERNAME_EXISTS")

        duplicate_email = SignUpRequest(
            username="new_user",
            password="Password!1",
            nickname="새닉네임",
            email="duplicate@example.com",
            service_policy=True,
            privacy_policy=True,
        )
        with self.assertRaises(HTTPException) as email_error:
            await service.signup(duplicate_email)
        self.assertEqual(email_error.exception.detail["code"], "EMAIL_EXISTS")

    async def test_account_recovery_does_not_reveal_account_existence(self):
        service = UserService(FakeDatabase(None))

        username_result = await service.find_username(
            FindUsernameRequest(email="missing@example.com")
        )
        password_result = await service.request_password_reset(
            PasswordResetEmailRequest(username="missing_user", email="missing@example.com")
        )

        self.assertIn("계정이 있으면", username_result["message"])
        self.assertIn("계정이 있으면", password_result["message"])


if __name__ == "__main__":
    unittest.main()
