# 고객 가입·인증·계정 복구·비밀번호 변경·탈퇴 HTTP 엔드포인트

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from backend.core.client_ip import get_client_ip
from backend.core.dependencies import USER_ACCESS_COOKIE, require_user_token
from backend.core.errors import api_error
from backend.core.problems import problem_response
from backend.core.rate_limit import enforce_limit, guard_failures
from backend.core.security import clear_auth_cookie, set_auth_cookie
from backend.domain.users.schemas.users import (
    CancelWithdrawalRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailChangeRequest,
    FindUsernameRequest,
    MarketingConsentRequest,
    PasswordResetConfirmRequest,
    PasswordResetEmailRequest,
    ResendVerificationRequest,
    SignInRequest,
    SignUpRequest,
    UnlockAccountRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from backend.domain.users.services.users import UserService

# 사용자 계정 리소스 경로 전용 라우터이며 공통 /api 접두사 적용
router = APIRouter(prefix="/users", tags=["users"])
USER_REFRESH_COOKIE = "user_refresh_token"  # 고객 리프레시 토큰 HttpOnly 쿠키 이름
USER_REFRESH_COOKIE_PATH = "/api/users"  # 재발급·로그아웃 등 고객 인증 API에만 전송


# 서비스 로그인 결과의 토큰을 응답 본문에서 빼 HttpOnly 쿠키로만 전달
def issue_login_cookie(response: Response, result: dict) -> dict:
    set_auth_cookie(response, USER_ACCESS_COOKIE, result.pop("access_token"))
    set_auth_cookie(
        response,
        USER_REFRESH_COOKIE,
        result.pop("refresh_token"),
        session_only=True,  # 브라우저를 닫으면 로그인 해제(서버의 최대 유지기간은 REFRESH_TOKEN_EXPIRE_DAYS)
        path=USER_REFRESH_COOKIE_PATH,
    )
    result.pop("token_type", None)
    return result


# 접근·리프레시 쿠키를 모두 삭제
def clear_login_cookies(response: Response) -> None:
    clear_auth_cookie(response, USER_ACCESS_COOKIE)
    clear_auth_cookie(response, USER_REFRESH_COOKIE, path=USER_REFRESH_COOKIE_PATH)


TOKEN_FAILURE_LIMIT = (30, 15 * 60)  # 토큰 확인 계열 API는 접속 IP당 15분에 실패 30회까지 허용


# 토큰을 확인하는 요청을 접속 IP당 실패 횟수 기준으로 제한해 실행
async def guarded_token_action(user_service: UserService, http_request: Request, action):
    return await guard_failures(user_service.db, "token-fail-ip", get_client_ip(http_request), *TOKEN_FAILURE_LIMIT, action)


# 메일을 발송할 수 있는 요청의 접속 IP당(시간당 15회)·대상 이메일당(시간당 5회) 횟수 제한
async def limit_mail_request(user_service: UserService, http_request: Request, target_email: str) -> None:
    await enforce_limit(user_service.db, "mail-ip", get_client_ip(http_request), 15, 60 * 60)
    await enforce_limit(user_service.db, "mail-target", target_email, 5, 60 * 60)


# 회원가입 화면용 현재 시행 약관 조회
@router.get("/policies", status_code=status.HTTP_200_OK)
async def list_policies(user_service: UserService = Depends(UserService)):
    return user_service.list_policies()


# 이메일 인증 링크의 토큰 확인
@router.post("/email-verification/confirm", status_code=status.HTTP_200_OK)
async def confirm_email_verification(
    request: VerifyEmailRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    return await guarded_token_action(user_service, http_request, lambda: user_service.verify_email(request))


# 미인증 계정의 인증 메일 재발송
@router.post("/email-verification/resend", status_code=status.HTTP_200_OK)
async def resend_email_verification(
    request: ResendVerificationRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    await limit_mail_request(user_service, http_request, request.email)
    return await user_service.resend_verification(request)


# 서버의 로그인 세션(리프레시 토큰)을 폐기하고 인증 쿠키 삭제
@router.post("/signout", status_code=status.HTTP_200_OK)
async def signout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=USER_REFRESH_COOKIE),
    user_service: UserService = Depends(UserService),
):
    await user_service.revoke_refresh_session(refresh_token)
    clear_login_cookies(response)
    return {"message": "로그아웃되었습니다."}


# 리프레시 토큰으로 접근·리프레시 토큰 재발급(실패 시 쿠키 삭제)
@router.post("/token/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
    http_request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=USER_REFRESH_COOKIE),
    user_service: UserService = Depends(UserService),
):
    try:
        if not refresh_token:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "로그인이 만료되었습니다. 다시 로그인해 주세요.")
        result = await guarded_token_action(user_service, http_request, lambda: user_service.refresh_session(refresh_token))
        return issue_login_cookie(response, result)
    except HTTPException as error:
        failure = problem_response(error.status_code, error.detail, http_request, dict(error.headers or {}))
        # 동시 탭 경합·요청 제한 초과에서는 다른 탭이 방금 받은 새 쿠키를 지우지 않음
        if error.detail.get("code") not in {"REFRESH_IN_PROGRESS", "RATE_LIMITED"}:
            clear_login_cookies(failure)
        return failure


# 신규 회원 생성
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest, http_request: Request, user_service: UserService = Depends(UserService)):
    await enforce_limit(user_service.db, "signup-ip", get_client_ip(http_request), 10, 60 * 60)
    await limit_mail_request(user_service, http_request, request.email)
    return await user_service.signup(request)


# 아이디 및 비밀번호 로그인
@router.post("/signin", status_code=status.HTTP_200_OK)
async def signin(
    request: SignInRequest,
    http_request: Request,
    response: Response,
    user_service: UserService = Depends(UserService),
):
    # 아이디·비밀번호 오류만 접속 IP당 15분 20회까지 셈(공용 IP 사용자를 고려한 넉넉한 한도, 동시 요청도 한도 안에서만 통과)
    result = await guard_failures(
        user_service.db,
        "login-fail-ip",
        get_client_ip(http_request),
        20,
        15 * 60,
        lambda: user_service.signin(request),
        is_failure=lambda error: isinstance(error.detail, dict) and error.detail.get("code") == "INVALID_CREDENTIALS",
    )
    return issue_login_cookie(response, result)


# 가입 이메일 기반 아이디 안내 메일 요청
@router.post("/find-username", status_code=status.HTTP_200_OK)
async def find_username(request: FindUsernameRequest, http_request: Request, user_service: UserService = Depends(UserService)):
    await limit_mail_request(user_service, http_request, request.email)
    return await user_service.find_username(request)


# 아이디·이메일 확인 후 비밀번호 재설정 메일 발송
@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request: PasswordResetEmailRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    await limit_mail_request(user_service, http_request, request.email)
    return await user_service.request_password_reset(request)


# 이메일 발급 토큰을 사용한 새 비밀번호 저장
@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    return await guarded_token_action(user_service, http_request, lambda: user_service.reset_password(request))


# 메일 링크의 화면에서 확인 버튼을 눌렀을 때만 계정 잠금 해제(GET 링크 미리열기로 해제되지 않도록 POST)
@router.post("/unlock", status_code=status.HTTP_200_OK)
async def unlock_account(
    request: UnlockAccountRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    await guarded_token_action(user_service, http_request, lambda: user_service.unlock_account(request.token))
    return {"message": "계정 잠금이 해제되었습니다. 다시 로그인해 주세요."}


# 현재 계정을 탈퇴 대기 상태로 전환
@router.delete("/me", status_code=status.HTTP_200_OK)
async def request_account_deletion(
    request: DeleteAccountRequest,
    response: Response,
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    result = await user_service.request_account_deletion(token, request)
    clear_login_cookies(response)
    return result


# 로그인 토큰 유효성 확인 및 현재 사용자 정보 조회
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user(
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.get_current_user(token)


# 로그인 사용자의 현재 비밀번호 확인 후 새 비밀번호 저장
@router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    response: Response,
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    result = await user_service.change_password(token, request)
    clear_login_cookies(response)  # auth_version 증가로 기존 토큰은 이미 무효
    return result


# 로그인 사용자의 선택 마케팅 수신 동의 저장
@router.put("/me/marketing-consent", status_code=status.HTTP_200_OK)
async def update_marketing_consent(
    request: MarketingConsentRequest,
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.update_marketing_consent(token, request)


# 7일 유예기간 내 탈퇴 취소 및 로그인 상태 복구
@router.post("/withdrawal/cancel", status_code=status.HTTP_200_OK)
async def cancel_withdrawal(
    request: CancelWithdrawalRequest,
    http_request: Request,
    response: Response,
    user_service: UserService = Depends(UserService),
):
    result = await guarded_token_action(user_service, http_request, lambda: user_service.cancel_withdrawal(request))
    return issue_login_cookie(response, result)


# 닉네임 수정
@router.put("/me/profile", status_code=status.HTTP_200_OK)
async def update_profile(
    request: UpdateProfileRequest,
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.update_profile(token, request)


# 이메일 변경 요청(비밀번호 확인 후 새 이메일로 확인 메일 발송, 메일 발송 제한 적용)
@router.post("/me/email-change", status_code=status.HTTP_200_OK)
async def request_email_change(
    request: EmailChangeRequest,
    http_request: Request,
    token: str = Depends(require_user_token),
    user_service: UserService = Depends(UserService),
):
    await limit_mail_request(user_service, http_request, request.new_email)
    return await user_service.request_email_change(token, request)


# 새 이메일로 받은 확인 링크의 토큰으로 이메일 변경 완료
@router.post("/email-change/confirm", status_code=status.HTTP_200_OK)
async def confirm_email_change(
    request: VerifyEmailRequest,
    http_request: Request,
    user_service: UserService = Depends(UserService),
):
    return await guarded_token_action(user_service, http_request, lambda: user_service.confirm_email_change(request))
