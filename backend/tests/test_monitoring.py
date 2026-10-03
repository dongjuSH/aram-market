# Sentry 전송 필터 테스트: 5xx·ERROR 로그만 보내고 4xx·WARNING·요청 본문·쿠키는 보내지 않음(가짜 전송기 사용, 외부 전송 없음)

import logging
import os
import sys
import unittest
from pathlib import Path

import httpx
import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.transport import Transport

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SENTRY_DSN"] = ""  # 실제 DSN으로 초기화되지 않게 함

from backend.core import monitoring  # noqa: E402
from backend.core.errors import api_error  # noqa: E402


# 네트워크로 보내지 않고 이벤트를 모으는 전송기
class CapturingTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


class SentryFilterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = CapturingTransport()
        original_init = sentry_sdk.init

        # 실제 설정(init_sentry)을 그대로 쓰되 DSN은 가짜, 전송기는 수집용으로 바꿔 끼움
        def init_with_capture(**options):
            return original_init(**{**options, "dsn": "https://public@example.invalid/1", "transport": self.transport})

        sentry_sdk.init = init_with_capture
        object.__setattr__(monitoring.settings, "sentry_dsn", "https://public@example.invalid/1")
        try:
            self.assertTrue(monitoring.init_sentry())
        finally:
            sentry_sdk.init = original_init
            object.__setattr__(monitoring.settings, "sentry_dsn", "")

        app = FastAPI()

        @app.post("/boom")
        async def boom(body: dict):
            raise RuntimeError("unexpected failure")

        @app.get("/mail-fail")
        async def mail_fail(token: str = ""):
            # SMTPRecipientsRefused처럼 예외 문자열에 수신 주소가 들어가는 경우와 로그 메시지에 토큰이 섞인 경우
            # 실제 데이터처럼 실행 중에 값을 만듦(소스 코드 줄에 값이 없어야 이벤트에 붙는 소스 문맥과 구분됨)
            address = "victim" + "@" + "example.com"
            logging.getLogger("backend.mail").error("mail failed for %s token=%s", address, token)
            raise RuntimeError(str({address: (550, b"rejected")}))

        @app.get("/not-found")
        async def not_found():
            raise api_error(404, "NOT_FOUND", "없음")

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        sentry_sdk.get_client().close()
        sentry_sdk.init()  # DSN 없는 상태로 되돌림

    def flush(self):
        sentry_sdk.flush()
        return self.transport.events

    async def test_server_error_is_sent_without_body_or_cookies(self):
        await self.client.post("/boom", json={"password": "Secret!123"}, cookies={"admin_access_token": "tok"})
        events = self.flush()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["exception"]["values"][-1]["type"], "RuntimeError")
        dumped = str(events[0])
        self.assertNotIn("Secret!123", dumped)  # 요청 본문·지역 변수 미전송
        self.assertNotIn("admin_access_token", dumped)  # 쿠키 미전송

    async def test_client_errors_and_warnings_are_not_sent_but_error_logs_are(self):
        await self.client.get("/not-found")
        logging.getLogger("backend.test").warning("just a warning")
        self.assertEqual(self.flush(), [])
        logging.getLogger("backend.test").error("pending order needs manual review")
        events = self.flush()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["level"], "error")

    async def test_tokens_emails_and_query_strings_are_scrubbed_from_whole_event(self):
        jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlc2lnbmF0dXJl"
        await self.client.get(
            f"/mail-fail?token={jwt_like}&paymentKey=tgen_20261002ABCDEFGHIJKLMNOPQRSTUVWX",
            headers={"Referer": f"http://localhost:5173/user/reset-password?token={jwt_like}"},
        )
        events = self.flush()
        self.assertEqual(len(events), 2)  # ERROR 로그 1건 + 500 예외 1건
        dumped = str(events)
        for secret in ("victim@example.com", jwt_like, "tgen_20261002ABCDEFGHIJKLMNOPQRSTUVWX", "reset-password?token"):
            self.assertNotIn(secret, dumped)
        request = next(event["request"] for event in events if "request" in event)
        self.assertFalse(request["url"].endswith("?"))
        self.assertNotIn("query_string", request)
        self.assertNotIn("referer", {key.lower() for key in request.get("headers", {})})

    def test_disabled_without_dsn(self):
        self.assertFalse(monitoring.init_sentry())


if __name__ == "__main__":
    unittest.main()
