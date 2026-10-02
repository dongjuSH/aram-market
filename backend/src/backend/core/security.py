# 비밀번호 해시와 표준 JWT 발급·검증

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any

import jwt
from fastapi import Response

from backend.core.config import settings


JWT_ALGORITHM = "HS256"  # 대칭키 HMAC-SHA256 서명
JWT_ISSUER = "aram-market"  # 이 서버가 발급한 토큰임을 나타내는 iss 값
PBKDF2_ITERATIONS = 600_000  # 비밀번호 대입 공격 비용을 높이는 반복 횟수


# 바이트를 URL-safe Base64 문자열로 변환
def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


# 패딩이 생략된 URL-safe Base64 문자열 복원
def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# 무작위 salt와 PBKDF2 반복 연산을 사용한 비밀번호 단방향 해시
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_encode(salt)}${_encode(digest)}"


# 상수시간 PBKDF2 비밀번호 검증(해시 형식이 아닌 저장값은 항상 불일치)
def verify_password(password: str, stored_value: str) -> bool:
    if not stored_value.startswith("pbkdf2_sha256$"):
        return False

    try:
        _, iterations, salt, expected = stored_value.split("$", 3)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            _decode(salt),
            int(iterations),
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(_encode(actual), expected)


# 표준 JWT(HS256) 생성: iss 발급자, aud 토큰 용도, sub 주체, iat/exp 시각, jti 고유번호와 추가 클레임 포함
def create_token(
    subject: int,
    token_type: str,
    expires_minutes: int,
    claims: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload = {
        **(claims or {}),
        "iss": JWT_ISSUER,
        "aud": token_type,
        "sub": str(subject),  # RFC 7519 sub는 문자열
        "iat": now,
        "exp": now + expires_minutes * 60,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


# JWT 서명·알고리즘 고정·발급자·용도(aud)·만료시간 검증 후 payload 반환(sub는 정수로 복원)
def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[JWT_ALGORITHM],  # 서명 알고리즘을 서버가 고정(alg 변조·none 차단)
            audience=expected_type,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
        payload["sub"] = int(payload["sub"])
        return payload
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise ValueError("유효하지 않거나 만료된 인증 정보입니다.") from error


# 무작위 리프레시 토큰 원문 생성(서버에는 해시만 저장)
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


# DB 조회·저장용 리프레시 토큰 SHA-256 해시
def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# JS에서 읽을 수 없는 HttpOnly 인증 쿠키 발급(기본은 접근 토큰 수명·/api 경로, session_only면 브라우저 종료 시 삭제되는 세션 쿠키)
def set_auth_cookie(
    response: Response,
    name: str,
    token: str,
    max_age: int | None = None,
    path: str = "/api",
    session_only: bool = False,
) -> None:
    response.set_cookie(
        name,
        token,
        max_age=None if session_only else (max_age if max_age is not None else settings.access_token_expire_minutes * 60),
        path=path,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


# 발급 때와 같은 속성으로 인증 쿠키 삭제
def clear_auth_cookie(response: Response, name: str, path: str = "/api") -> None:
    response.delete_cookie(
        name,
        path=path,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
