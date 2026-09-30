# 모든 라우터가 공통으로 쓰는 인증 쿠키 이름과 접근 토큰 의존성

from fastapi import Cookie, status

from backend.core.errors import api_error

USER_ACCESS_COOKIE = "user_access_token"  # 고객 접근 토큰 HttpOnly 쿠키 이름
ADMIN_ACCESS_COOKIE = "admin_access_token"  # 관리자 접근 토큰 HttpOnly 쿠키 이름


# 로그인 고객 전용 API: 쿠키의 접근 토큰이 없으면 401
def require_user_token(token: str | None = Cookie(default=None, alias=USER_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 관리자 전용 API: 쿠키의 접근 토큰이 없으면 401
def require_admin_token(token: str | None = Cookie(default=None, alias=ADMIN_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 비로그인도 볼 수 있는 API에서 로그인 고객이면 토큰을 전달(없으면 None)
def optional_user_token(token: str | None = Cookie(default=None, alias=USER_ACCESS_COOKIE)) -> str | None:
    return token
