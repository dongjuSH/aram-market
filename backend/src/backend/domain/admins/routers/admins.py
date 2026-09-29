# 단일 관리자 로그인과 인증 확인 HTTP 엔드포인트

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from backend.core.client_ip import get_client_ip
from backend.core.config import settings
from backend.core.problems import problem_response
from backend.core.rate_limit import guard_failures
from backend.core.security import clear_auth_cookie, set_auth_cookie
from backend.domain.admins.schemas.admins import SignInRequest
from backend.domain.admins.services.admins import AdminAccountService, api_error


router = APIRouter(prefix="/admins", tags=["admins"])  # main.py에서 공통 /api 접두사 적용
ADMIN_ACCESS_COOKIE = "admin_access_token"  # 관리자 접근 토큰 HttpOnly 쿠키 이름
ADMIN_REFRESH_COOKIE = "admin_refresh_token"  # 관리자 리프레시 토큰 HttpOnly 쿠키 이름
ADMIN_REFRESH_COOKIE_PATH = "/api/admins"  # 재발급·로그아웃 등 관리자 인증 API에만 전송


# 접근·리프레시 쿠키 발급(토큰은 응답 본문에서 제거)
def issue_login_cookies(response: Response, result: dict) -> dict:
    set_auth_cookie(
        response,
        ADMIN_ACCESS_COOKIE,
        result.pop("access_token"),
        max_age=settings.admin_access_token_expire_minutes * 60,
    )
    set_auth_cookie(
        response,
        ADMIN_REFRESH_COOKIE,
        result.pop("refresh_token"),
        max_age=settings.admin_refresh_token_expire_hours * 60 * 60,
        path=ADMIN_REFRESH_COOKIE_PATH,
    )
    result.pop("token_type", None)
    return result


# 접근·리프레시 쿠키를 모두 삭제
def clear_login_cookies(response: Response) -> None:
    clear_auth_cookie(response, ADMIN_ACCESS_COOKIE)
    clear_auth_cookie(response, ADMIN_REFRESH_COOKIE, path=ADMIN_REFRESH_COOKIE_PATH)


# 관리자 API 공통 HttpOnly 쿠키 접근 토큰 검증
def access_token(token: str | None = Cookie(default=None, alias=ADMIN_ACCESS_COOKIE)) -> str:
    if not token:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return token


# 고정 아이디 admin과 비밀번호 로그인
@router.post("/signin", status_code=status.HTTP_200_OK)
async def signin(
    request: SignInRequest,
    http_request: Request,
    response: Response,
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    client_ip = get_client_ip(http_request)  # 신뢰 프록시가 전달한 X-Forwarded-For만 사용
    result = await admin_service.signin(request, client_ip)
    return issue_login_cookies(response, result)


# 서버의 로그인 세션(리프레시 토큰)을 폐기하고 관리자 인증 쿠키 삭제
@router.post("/signout", status_code=status.HTTP_200_OK)
async def signout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=ADMIN_REFRESH_COOKIE),
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    await admin_service.revoke_refresh_session(refresh_token)
    clear_login_cookies(response)
    return {"message": "로그아웃되었습니다."}


# 리프레시 토큰으로 접근·리프레시 토큰 재발급(실패 시 쿠키 삭제)
@router.post("/token/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
    http_request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=ADMIN_REFRESH_COOKIE),
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    try:
        if not refresh_token:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "로그인이 만료되었습니다. 다시 로그인해 주세요.")
        result = await guard_failures(
            admin_service.db,
            "admin-token-fail-ip",
            get_client_ip(http_request),
            30,
            15 * 60,
            lambda: admin_service.refresh_session(refresh_token),
        )
        return issue_login_cookies(response, result)
    except HTTPException as error:
        failure = problem_response(error.status_code, error.detail, http_request, dict(error.headers or {}))
        # 동시 탭 경합·요청 제한 초과에서는 다른 탭이 방금 받은 새 쿠키를 지우지 않음
        if error.detail.get("code") not in {"REFRESH_IN_PROGRESS", "RATE_LIMITED"}:
            clear_login_cookies(failure)
        return failure


# 관리자 접근 토큰 유효성 확인
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user(
    token: str = Depends(access_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    return await admin_service.get_current_user(token)
