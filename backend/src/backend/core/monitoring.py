# Sentry 오류 수집 설정: 고칠 필요가 있는 서버 오류(5xx·ERROR 로그)만 보내고 개인정보·요청 본문은 보내지 않음

import asyncio
import logging
import re
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from fastapi import HTTPException
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import ClientDisconnect

from backend.core.config import settings


SERVER_ERROR_STATUS_CODES = set(range(500, 600))  # 4xx는 정상적인 안내 응답이라 보내지 않음
IGNORED_EXCEPTIONS = (asyncio.CancelledError, ClientDisconnect)  # 사용자가 요청 도중 창을 닫은 경우 등


EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# JWT(메일 링크 토큰)와 길이가 긴 무작위 값(결제키·리프레시 토큰 등)
TOKEN_PATTERN = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+|\b[A-Za-z0-9_-]{32,}\b")
REMOVED_HEADERS = {"referer", "cookie", "authorization", "x-forwarded-for", "x-real-ip"}


# 문자열 속 이메일·토큰을 가림
def scrub_text(value: str) -> str:
    return TOKEN_PATTERN.sub("[Filtered]", EMAIL_PATTERN.sub("[Filtered email]", value))


# 주소의 쿼리·해시(메일 링크 토큰, 결제키가 실릴 수 있음)를 지움
def strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


# 이벤트의 요청 정보·예외 메시지·로그 메시지·흐름 기록에서 개인정보와 토큰을 지움
def scrub_event(event: dict) -> dict:
    request = event.get("request")
    if isinstance(request, dict):
        if isinstance(request.get("url"), str):
            request["url"] = strip_query(request["url"])
        request.pop("query_string", None)
        request.pop("cookies", None)
        request.pop("data", None)
        if isinstance(request.get("headers"), dict):
            request["headers"] = {key: value for key, value in request["headers"].items() if key.lower() not in REMOVED_HEADERS}
    for value in (event.get("exception") or {}).get("values") or []:
        if isinstance(value.get("value"), str):
            value["value"] = scrub_text(value["value"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if isinstance(logentry.get(key), str):
                logentry[key] = scrub_text(logentry[key])
        logentry.pop("params", None)
    if isinstance(event.get("message"), str):
        event["message"] = scrub_text(event["message"])
    breadcrumbs = event.get("breadcrumbs")
    for crumb in (breadcrumbs.get("values") if isinstance(breadcrumbs, dict) else breadcrumbs) or []:
        if isinstance(crumb.get("message"), str):
            crumb["message"] = scrub_text(crumb["message"])
        crumb.pop("data", None)
    return event


# 전송 직전 마지막 필터: 4xx HTTP 예외와 연결 끊김은 버리고, 나머지는 개인정보·토큰을 지운 뒤 전송
def before_send(event: dict, hint: dict) -> dict | None:
    exc_info = hint.get("exc_info")
    if exc_info:
        error = exc_info[1]
        if isinstance(error, IGNORED_EXCEPTIONS):
            return None
        if isinstance(error, (HTTPException, StarletteHTTPException)) and error.status_code < 500:
            return None
    return scrub_event(event)


# SENTRY_DSN이 있을 때만 Sentry를 켬(테스트·DSN 없는 로컬에서는 아무것도 보내지 않음)
def init_sentry() -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=settings.sentry_release or None,
        send_default_pii=False,  # IP·쿠키·사용자 정보 미전송
        max_request_body_size="never",  # 로그인·회원가입 본문(비밀번호·이메일)이 오류 정보에 실리지 않게 함
        include_local_variables=False,  # 스택의 지역 변수(요청 본문·쿠키·토큰이 담길 수 있음) 미전송
        traces_sample_rate=0,  # 성능 추적 미사용(무료 한도 절약)
        integrations=[
            StarletteIntegration(failed_request_status_codes=SERVER_ERROR_STATUS_CODES),
            FastApiIntegration(failed_request_status_codes=SERVER_ERROR_STATUS_CODES),
            # INFO 이상은 오류 직전 흐름(breadcrumb)으로만 남기고, ERROR 이상 로그만 이슈로 보냄
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=before_send,
    )
    return True
