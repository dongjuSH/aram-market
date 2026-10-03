# 앱 조립(라우터 import)과 인증 필요 경로·ID 범위 검증을 DB 없이 확인하는 HTTP 수준 테스트

import os
import re
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SENTRY_DSN"] = ""  # 테스트 중 실제 Sentry로 오류를 보내지 않음(.env보다 우선)
os.environ.setdefault("ADMIN_MFA_REQUIRED", "false")

import main  # noqa: E402  (backend/main.py: 모든 라우터를 import해 문법·import 오류를 잡는다)
from backend.core.database import get_db  # noqa: E402


PUBLIC_PREFIXES = (
    "/api/products",
    "/api/users/policies",
)
# 쿠키 없이도 접근할 수 있어야 하는 로그인·토큰·메일 계열 경로
OPEN_PATHS = {
    "/api/admins/signin",
    "/api/admins/signin/mfa",
    "/api/admins/signout",
    "/api/admins/token/refresh",
    "/api/users/signup",
    "/api/users/signin",
    "/api/users/signout",
    "/api/users/token/refresh",
    "/api/users/email-verification/confirm",
    "/api/users/email-verification/resend",
    "/api/users/email-change/confirm",
    "/api/users/find-username",
    "/api/users/password-reset/request",
    "/api/users/password-reset/confirm",
    "/api/users/unlock",
    "/api/users/withdrawal/cancel",
}


# 인증 쿠키가 필요한 경로를 OpenAPI 정의에서 골라 쿠키 없이 호출
class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # 인증·입력 검증 단계에서 끝나는 요청만 보내므로 실제 DB에 연결하지 않는 가짜 세션을 쓴다
        async def fake_db():
            yield None

        main.app.dependency_overrides[get_db] = fake_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")

    async def asyncTearDown(self):
        main.app.dependency_overrides.pop(get_db, None)
        await self.client.aclose()

    # 공개 경로가 아닌 모든 API가 쿠키 없이 401을 돌려주는지 확인(새 경로의 인증 누락 방지)
    async def test_protected_routes_reject_requests_without_cookie(self):
        spec = main.app.openapi()
        checked = 0
        for path, operations in spec["paths"].items():
            if not path.startswith("/api") or path in OPEN_PATHS:
                continue
            for method in operations:
                is_public_read = method == "get" and path.startswith(PUBLIC_PREFIXES) and not path.endswith("/eligibility")
                if is_public_read:
                    continue
                url = re.sub(r"\{[^}]+\}", "1", path)
                response = await self.client.request(method.upper(), url, json={})
                self.assertEqual(response.status_code, 401, f"{method.upper()} {path}")
                checked += 1
        self.assertGreater(checked, 30)

    # PostgreSQL integer 범위를 넘는 번호가 500이 아닌 422로 거부되는지 확인
    async def test_oversized_ids_are_rejected_as_validation_errors(self):
        for url in ("/api/products/99999999999999999999", "/api/products/0", "/api/products/1/reviews/eligibility"):
            response = await self.client.get(url)
            self.assertIn(response.status_code, {401, 422}, url)
        response = await self.client.get("/api/products/2147483648")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "VALIDATION_ERROR")

    # 관리자 상품 목록의 잘못된 조회 조건이 NameError 대신 구조화된 오류가 되도록 함수를 직접 확인
    async def test_admin_product_list_rejects_invalid_filters(self):
        from fastapi import HTTPException

        from backend.domain.products.routers.products import list_products

        class Admin:
            async def get_authenticated_admin(self, token):
                return None

        with self.assertRaises(HTTPException) as raised:
            await list_products(keyword="", page=1, page_size=7, product_status="active", token="t", admin_service=Admin(), product_service=None)
        self.assertEqual(raised.exception.status_code, 422)
        with self.assertRaises(HTTPException) as raised:
            await list_products(keyword="", page=1, page_size=10, product_status="bad", token="t", admin_service=Admin(), product_service=None)
        self.assertEqual(raised.exception.status_code, 422)

    # 헬스 체크는 DB 조회 성공 시 200, 실패 시 503 DATABASE_UNAVAILABLE
    async def test_health_check_reports_database_state(self):
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        class Session:
            def __init__(self, fail):
                self.fail = fail

            async def execute(self, statement):
                if self.fail:
                    raise ConnectionError("db down")

        def fake_session_factory(fail):
            @asynccontextmanager
            async def factory():
                yield Session(fail)

            return factory

        with patch.object(main, "async_session", fake_session_factory(False)):
            response = await self.client.get("/api/health")
        self.assertEqual((response.status_code, response.json()), (200, {"status": "ok"}))
        with patch.object(main, "async_session", fake_session_factory(True)), self.assertLogs("main", "ERROR"):
            response = await self.client.get("/api/health")
        self.assertEqual((response.status_code, response.json()["code"]), (503, "DATABASE_UNAVAILABLE"))

    # 검색어의 %·_·역슬래시는 와일드카드가 아닌 글자 그대로 찾도록 이스케이프
    def test_escape_like_treats_wildcards_as_literal_text(self):
        from backend.core.validators import escape_like

        self.assertEqual(escape_like("100%_a\\b"), "100\\%\\_a\\\\b")
        self.assertEqual(escape_like("텀블러"), "텀블러")

    # 관리자 2단계 인증 HTTP 흐름: 비밀번호 후에는 대기 쿠키만, 코드 확인 후 로그인 쿠키 발급·대기 쿠키 삭제
    async def test_admin_mfa_flow_uses_httponly_pending_cookie(self):
        from datetime import datetime, timezone

        import pyotp

        from backend.core.security import hash_password
        from backend.domain.admins.models.admins import AdminAccount
        from backend.domain.admins.services.admins import AdminAccountService
        from backend.domain.admins.services.mfa import encrypt_secret, generate_secret
        from backend.domain.admins.services.rate_limit import LoginRateLimiter

        secret = generate_secret()
        admin = AdminAccount(
            id=1, username="admin", password_hash=hash_password("Password!1"), created_at=datetime.now(timezone.utc),
            is_active=True, auth_version=0, mfa_secret_encrypted=encrypt_secret(secret),
            mfa_enabled_at=datetime.now(timezone.utc), mfa_last_used_step=None, mfa_recovery_code_hashes=[],
        )

        class Result:
            def scalar_one_or_none(self):
                return admin

        class Db:
            def add(self, row):
                pass

            async def execute(self, statement):
                return Result()

            async def commit(self):
                pass

        service = AdminAccountService(Db())
        service.limiter = LoginRateLimiter()
        main.app.dependency_overrides[AdminAccountService] = lambda: service
        self.addCleanup(main.app.dependency_overrides.pop, AdminAccountService, None)

        response = await self.client.post("/api/admins/signin", json={"username": "admin", "password": "Password!1"})
        self.assertEqual(response.json()["mfa_required"], True)
        self.assertNotIn("mfa_token", response.json())
        set_cookie = response.headers.get_list("set-cookie")
        self.assertEqual(len(set_cookie), 1)
        self.assertIn("admin_mfa_token=", set_cookie[0])
        self.assertIn("HttpOnly", set_cookie[0])
        self.assertIn("Path=/api/admins", set_cookie[0])

        pending = set_cookie[0].split(";")[0].split("=", 1)[1]
        response = await self.client.post(
            "/api/admins/signin/mfa", json={"code": pyotp.TOTP(secret).now()}, cookies={"admin_mfa_token": pending}
        )
        self.assertEqual(response.status_code, 200)
        cookies = " ".join(response.headers.get_list("set-cookie"))
        self.assertIn("admin_access_token=", cookies)
        self.assertIn("admin_refresh_token=", cookies)
        self.assertIn('admin_mfa_token=""', cookies)  # 대기 쿠키 삭제

        response = await self.client.post("/api/admins/signin/mfa", json={"code": "123456"})
        self.assertEqual((response.status_code, response.json()["code"]), (401, "MFA_SESSION_EXPIRED"))


if __name__ == "__main__":
    unittest.main()
