# 단일 관리자 로그인과 인증 확인 HTTP 엔드포인트

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.domain.admins.schemas.admins import SignInRequest
from backend.domain.admins.services.admins import AdminAccountService, api_error


router = APIRouter(prefix="/admins", tags=["admins"])  # main.py에서 공통 /api 접두사 적용
bearer_scheme = HTTPBearer(auto_error=False)  # 누락 토큰에 공통 오류 형식을 적용하도록 자동 오류 비활성화


# 관리자 API 공통 Bearer 접근 토큰 검증
def access_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise api_error(status.HTTP_401_UNAUTHORIZED, "MISSING_ACCESS_TOKEN", "로그인이 필요합니다.")
    return credentials.credentials


# 고정 아이디 admin과 비밀번호 로그인
@router.post("/signin", status_code=status.HTTP_200_OK)
async def signin(
    request: SignInRequest,
    http_request: Request,
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    client_ip = http_request.client.host if http_request.client else "unknown"  # 전달 헤더가 아닌 직접 접속 IP 사용
    return await admin_service.signin(request, client_ip)


# 관리자 접근 토큰 유효성 확인
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user(
    token: str = Depends(access_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
):
    return await admin_service.get_current_user(token)
