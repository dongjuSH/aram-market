# 고객 가입·인증·계정 복구·비밀번호 변경·탈퇴 HTTP 엔드포인트

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings
from backend.domain.users.schemas.users import (
    CancelWithdrawalRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    FindUsernameRequest,
    MarketingConsentRequest,
    PasswordResetConfirmRequest,
    PasswordResetEmailRequest,
    SignInRequest,
    SignUpRequest,
)
from backend.domain.users.services.users import UserService, api_error

# 사용자 계정 리소스 경로 전용 라우터이며 공통 /api 접두사 적용
router = APIRouter(prefix="/users", tags=["users"])
bearer_scheme = HTTPBearer(auto_error=False)  # 인증 API의 Bearer 토큰 직접 검증용 자동 오류 비활성화


# 사용자 API 공통 Bearer 접근 토큰 검증
def access_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return credentials.credentials


# 신규 회원 생성
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest, user_service: UserService = Depends(UserService)):
    return await user_service.signup(request)


# 아이디 및 비밀번호 로그인
@router.post("/signin", status_code=status.HTTP_200_OK)
async def signin(request: SignInRequest, user_service: UserService = Depends(UserService)):
    return await user_service.signin(request)


# 가입 이메일 기반 아이디 안내 메일 요청
@router.post("/find-username", status_code=status.HTTP_200_OK)
async def find_username(request: FindUsernameRequest, user_service: UserService = Depends(UserService)):
    return await user_service.find_username(request)


# 아이디·이메일 확인 후 비밀번호 재설정 메일 발송
@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request: PasswordResetEmailRequest,
    user_service: UserService = Depends(UserService),
):
    return await user_service.request_password_reset(request)


# 이메일 발급 토큰을 사용한 새 비밀번호 저장
@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    user_service: UserService = Depends(UserService),
):
    return await user_service.reset_password(request)


# 이메일 링크 기반 계정 잠금 해제 및 로그인 화면 이동
@router.get("/unlock", include_in_schema=False)
async def unlock_account(token: str, user_service: UserService = Depends(UserService)):
    unlock_status = "success"
    try:
        await user_service.unlock_account(token)
    except HTTPException:
        unlock_status = "failed"

    query = urlencode({"unlock": unlock_status})
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/user/login?{query}")


# 현재 계정을 탈퇴 대기 상태로 전환
@router.delete("/me", status_code=status.HTTP_200_OK)
async def request_account_deletion(
    request: DeleteAccountRequest,
    token: str = Depends(access_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.request_account_deletion(token, request)


# 로그인 토큰 유효성 확인 및 현재 사용자 정보 조회
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user(
    token: str = Depends(access_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.get_current_user(token)


# 로그인 사용자의 현재 비밀번호 확인 후 새 비밀번호 저장
@router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    token: str = Depends(access_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.change_password(token, request)


# 로그인 사용자의 선택 마케팅 수신 동의 저장
@router.put("/me/marketing-consent", status_code=status.HTTP_200_OK)
async def update_marketing_consent(
    request: MarketingConsentRequest,
    token: str = Depends(access_token),
    user_service: UserService = Depends(UserService),
):
    return await user_service.update_marketing_consent(token, request)


# 7일 유예기간 내 탈퇴 취소 및 로그인 상태 복구
@router.post("/withdrawal/cancel", status_code=status.HTTP_200_OK)
async def cancel_withdrawal(
    request: CancelWithdrawalRequest,
    user_service: UserService = Depends(UserService),
):
    return await user_service.cancel_withdrawal(request)
