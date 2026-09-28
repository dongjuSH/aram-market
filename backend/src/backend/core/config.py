# 애플리케이션 전역 환경변수 설정 객체

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # 실행 위치와 무관한 backend/.env 경로
load_dotenv(dotenv_path=ENV_FILE, override=True)


# 환경변수의 대표적인 참·거짓 문자열을 bool 값으로 변환
def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


# DB·인증·탈퇴·메일 환경변수 설정 모델
@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")  # SQLAlchemy 비동기 DB 연결 주소
    auth_secret_key: str = os.getenv("AUTH_SECRET_KEY", "development-only-change-me")  # 토큰 서명 비밀키
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))  # 로그인 유지시간
    unlock_token_expire_minutes: int = int(os.getenv("UNLOCK_TOKEN_EXPIRE_MINUTES", "60"))  # 잠금 해제 링크 시간
    password_reset_token_expire_minutes: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))  # 재설정 링크 시간
    withdrawal_grace_days: int = int(os.getenv("WITHDRAWAL_GRACE_DAYS", "7"))  # 탈퇴 취소 가능 기간
    withdrawal_retention_days: int = int(os.getenv("WITHDRAWAL_RETENTION_DAYS", "0"))  # 유예 후 추가 보관기간
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000")  # 메일 링크용 API 주소
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")  # 리디렉션용 화면 주소
    smtp_host: str = os.getenv("SMTP_HOST", "")  # 메일 공급자의 SMTP 호스트
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))  # STARTTLS 587, SSL 465
    smtp_username: str = os.getenv("SMTP_USERNAME", "")  # SMTP 인증 계정
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")  # SMTP 앱 비밀번호
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")  # 발신 허용 이메일
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "Product Management")  # 메일 발신자 표시명
    smtp_use_tls: bool = _as_bool(os.getenv("SMTP_USE_TLS"), True)  # 465가 아닌 포트의 STARTTLS 여부
    supabase_url: str = os.getenv("SUPABASE_URL", "")  # Storage REST API 프로젝트 주소
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")  # 서버 전용 Storage 관리 키
    supabase_storage_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET", "product-images")  # 공개 상품 이미지 버킷

    # 보안 및 탈퇴 정책에 위험한 환경변수 값 차단
    def __post_init__(self) -> None:
        if len(self.auth_secret_key.strip()) < 32:
            raise ValueError("AUTH_SECRET_KEY는 32자 이상의 무작위 문자열이어야 합니다.")
        if self.withdrawal_grace_days < 1:
            raise ValueError("WITHDRAWAL_GRACE_DAYS는 1일 이상이어야 합니다.")
        if self.withdrawal_retention_days < 0:
            raise ValueError("WITHDRAWAL_RETENTION_DAYS는 0일 이상이어야 합니다.")


settings = Settings()

if not settings.database_url:
    raise ValueError("DATABASE_URL이 .env 파일에 설정되지 않았습니다.")
