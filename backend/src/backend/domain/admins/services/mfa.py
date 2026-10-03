# 관리자 TOTP 2단계 인증: 비밀값 생성·암호화, Google Authenticator 등록 주소, 코드·복구 코드 검증

import base64
import hashlib
import hmac
import re
import secrets
import time

import pyotp
from cryptography.fernet import Fernet

from backend.core.config import settings


TOTP_ISSUER = "Aram Market"  # 인증 앱에 표시되는 서비스 이름(일부 앱의 한글 깨짐을 피해 영문)
TOTP_INTERVAL = 30  # Google Authenticator 기본값(30초, 6자리, SHA1)
TOTP_VALID_WINDOW = 1  # 휴대폰·서버 시계 차이를 고려해 앞뒤 30초까지 허용
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 헷갈리는 0·O·1·I 제외
TOTP_CODE_PATTERN = re.compile(r"^\d{6}$")


# 서버 비밀키에서 파생한 암호화 키(AUTH_SECRET_KEY를 바꾸면 2단계 인증을 다시 등록해야 함)
def _fernet() -> Fernet:
    digest = hashlib.sha256(f"admin-mfa-secret|{settings.auth_secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


# 160비트 무작위 Base32 비밀값 생성
def generate_secret() -> str:
    return pyotp.random_base32(32)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


# 복호화 실패(키 변경·값 손상)는 cryptography.fernet.InvalidToken 예외
def decrypt_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


# 인증 앱 QR 코드에 담을 otpauth:// 등록 주소
def provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.TOTP(secret, interval=TOTP_INTERVAL).provisioning_uri(name=account_name, issuer_name=TOTP_ISSUER)


# 6자리 코드가 현재 앞뒤 허용 범위 안의 어느 30초 단계와 일치하는지 반환(불일치면 None)
def matching_step(secret: str, code: str, now: float | None = None) -> int | None:
    if not TOTP_CODE_PATTERN.match(code):
        return None
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    current = int((time.time() if now is None else now) // TOTP_INTERVAL)
    for step in range(current - TOTP_VALID_WINDOW, current + TOTP_VALID_WINDOW + 1):
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


# 공백·하이픈을 지우고 대문자로 맞춘 복구 코드
def normalize_recovery_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code).upper()


# 화면에 보여 줄 XXXX-XXXX 형식 복구 코드 목록(40비트, 서버에는 해시만 저장)
def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(8))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


# DB만 유출돼도 대입으로 찾기 어렵도록 서버 비밀키 HMAC으로 해시
def hash_recovery_code(code: str) -> str:
    return hmac.new(
        settings.auth_secret_key.encode(), f"admin-recovery|{normalize_recovery_code(code)}".encode(), hashlib.sha256
    ).hexdigest()
