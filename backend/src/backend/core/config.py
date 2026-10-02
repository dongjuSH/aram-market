# 애플리케이션 전역 환경변수 설정 객체

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # 실행 위치와 무관한 backend/.env 경로
load_dotenv(dotenv_path=ENV_FILE, override=False)  # 이미 있는 환경변수(배포 플랫폼 설정)가 .env 값보다 우선


FRONTEND_URL_DEFAULT = os.getenv("FRONTEND_URL", "http://localhost:5173")  # 쿠키 Secure 기본값 판단용 화면 주소


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
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))  # 접근 토큰 유효시간(만료 시 리프레시 토큰으로 재발급)
    admin_access_token_expire_minutes: int = int(os.getenv("ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))  # 관리자 접근 토큰 유효시간(만료 시 리프레시 토큰으로 재발급)
    admin_refresh_token_expire_hours: int = int(os.getenv("ADMIN_REFRESH_TOKEN_EXPIRE_HOURS", "12"))  # 관리자 로그인 유지 최대시간(고객보다 짧게)
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))  # 리프레시 토큰 유효기간(로그인 유지 최대기간)
    refresh_reuse_grace_seconds: int = int(os.getenv("REFRESH_REUSE_GRACE_SECONDS", "10"))  # 동시 탭 재발급 경합을 탈취로 오인하지 않는 유예시간
    unlock_token_expire_minutes: int = int(os.getenv("UNLOCK_TOKEN_EXPIRE_MINUTES", "60"))  # 잠금 해제 링크 시간
    password_reset_token_expire_minutes: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))  # 재설정 링크 시간
    email_verification_token_expire_minutes: int = int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "1440"))  # 인증 링크 시간, 미인증 계정 보관시간
    email_verification_resend_seconds: int = int(os.getenv("EMAIL_VERIFICATION_RESEND_SECONDS", "60"))  # 인증 메일 재발송 최소 간격
    auth_cookie_secure: bool = _as_bool(os.getenv("AUTH_COOKIE_SECURE"), FRONTEND_URL_DEFAULT.startswith("https://"))  # HTTPS 화면이면 Secure 쿠키
    auth_cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()  # lax, strict, none 중 하나
    toss_secret_key: str = os.getenv("TOSS_SECRET_KEY", "")  # 토스페이먼츠 시크릿 키(테스트는 test_sk_ 로 시작, 서버 전용)
    toss_api_base: str = os.getenv("TOSS_API_BASE", "https://api.tosspayments.com").rstrip("/")  # 결제 승인 API 주소
    trusted_proxy_ips: tuple[str, ...] = tuple(item.strip() for item in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if item.strip())  # X-Forwarded-For를 신뢰할 리버스 프록시 IP·대역(쉼표 구분, 비우면 직접 접속 IP만 사용)
    withdrawal_grace_days: int = int(os.getenv("WITHDRAWAL_GRACE_DAYS", "7"))  # 탈퇴 취소 가능 기간
    withdrawal_retention_days: int = int(os.getenv("WITHDRAWAL_RETENTION_DAYS", "0"))  # 유예 후 추가 보관기간
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")  # 리디렉션용 화면 주소
    cors_origins: tuple[str, ...] = tuple(
        item.strip().rstrip("/") for item in os.getenv("CORS_ORIGINS", FRONTEND_URL_DEFAULT).split(",") if item.strip()
    )  # 브라우저 교차 출처 요청을 허용할 화면 주소(쉼표 구분, 기본은 FRONTEND_URL 하나)
    api_docs_enabled: bool = _as_bool(os.getenv("API_DOCS_ENABLED"), not FRONTEND_URL_DEFAULT.startswith("https://"))  # /docs·/redoc·/openapi.json 공개 여부(https 화면이면 기본 끔)
    smtp_host: str = os.getenv("SMTP_HOST", "")  # 메일 공급자의 SMTP 호스트
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))  # STARTTLS 587, SSL 465
    smtp_username: str = os.getenv("SMTP_USERNAME", "")  # SMTP 인증 계정
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")  # SMTP 앱 비밀번호
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")  # 발신 허용 이메일
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "아람 마켓")  # 메일에 표시할 아람 마켓 발신자명
    smtp_use_tls: bool = _as_bool(os.getenv("SMTP_USE_TLS"), True)  # 465가 아닌 포트의 STARTTLS 여부
    supabase_url: str = os.getenv("SUPABASE_URL", "")  # Storage REST API 프로젝트 주소
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")  # 서버 전용 Storage 관리 키
    supabase_storage_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET", "product-images")  # 공개 상품 이미지 버킷

    # 보안 및 탈퇴 정책에 위험한 환경변수 값 차단
    def __post_init__(self) -> None:
        if len(self.auth_secret_key.strip()) < 32:
            raise ValueError("AUTH_SECRET_KEY는 32자 이상의 무작위 문자열이어야 합니다.")
        if self.auth_cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE는 lax, strict, none 중 하나여야 합니다.")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SAMESITE=none은 AUTH_COOKIE_SECURE=true와 함께 사용해야 합니다.")
        if self.email_verification_token_expire_minutes < 1 or self.email_verification_resend_seconds < 0:
            raise ValueError("이메일 인증 시간 설정은 양수여야 합니다.")
        if min(self.access_token_expire_minutes, self.admin_access_token_expire_minutes, self.refresh_token_expire_days, self.admin_refresh_token_expire_hours) < 1:
            raise ValueError("토큰 유효시간 설정은 1 이상이어야 합니다.")
        if self.withdrawal_grace_days < 1:
            raise ValueError("WITHDRAWAL_GRACE_DAYS는 1일 이상이어야 합니다.")
        if self.withdrawal_retention_days < 0:
            raise ValueError("WITHDRAWAL_RETENTION_DAYS는 0일 이상이어야 합니다.")


settings = Settings()

if not settings.database_url:
    raise ValueError("DATABASE_URL이 .env 파일에 설정되지 않았습니다.")
