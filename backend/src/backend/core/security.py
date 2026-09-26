# 비밀번호 해시 및 만료·위변조 검증용 서명 토큰

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from backend.core.config import settings


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


# 저장 문자열의 PBKDF2 해시 형식 확인
def is_password_hash(value: str) -> bool:
    return value.startswith("pbkdf2_sha256$")


# 상수시간 비밀번호 검증 및 기존 평문 값의 첫 성공 로그인 호환
def verify_password(password: str, stored_value: str) -> bool:
    if not is_password_hash(stored_value):
        # 기존 학습용 평문 데이터의 1회성 호환 및 로그인 성공 시 해시 교체
        return hmac.compare_digest(password, stored_value)

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


# 용도·만료시간·추가 클레임을 포함한 HMAC 서명 토큰 생성
def create_token(
    subject: int,
    token_type: str,
    expires_minutes: int,
    claims: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_minutes * 60,
        **(claims or {}),
    }
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        settings.auth_secret_key.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_encode(signature)}"


# 토큰 서명·용도·만료시간 검증 및 payload 반환
def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.auth_secret_key.encode(),
            encoded_payload.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_encode(expected_signature), encoded_signature):
            raise ValueError

        payload = json.loads(_decode(encoded_payload))
        if payload.get("type") != expected_type or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError
        payload["sub"] = int(payload["sub"])
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("유효하지 않거나 만료된 인증 정보입니다.") from error
