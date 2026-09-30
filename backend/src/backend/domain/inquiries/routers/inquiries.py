# 상품 문의 HTTP 엔드포인트(목록은 누구나, 작성·삭제는 로그인 고객, 답변은 관리자)

from fastapi import APIRouter, Depends, Path, Query, Request, status

from backend.core.dependencies import optional_user_token, require_admin_token, require_user_token
from backend.core.client_ip import get_client_ip
from backend.core.rate_limit import enforce_limit
from backend.domain.inquiries.schemas.inquiries import InquiryAnswerRequest, InquiryRequest
from backend.domain.inquiries.services.inquiries import InquiryService

router = APIRouter(tags=["inquiries"])  # main.py에서 공통 /api 접두사 적용


# 상품 문의 목록(비밀글은 작성자에게만 내용 공개)
@router.get("/products/{product_id}/inquiries")
async def list_inquiries(
    product_id: int = Path(gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=20),
    token: str | None = Depends(optional_user_token),
    service: InquiryService = Depends(InquiryService),
):
    return await service.list_inquiries(product_id, page, page_size, token)


# 문의 작성(로그인 고객 누구나)
@router.post("/products/{product_id}/inquiries", status_code=status.HTTP_201_CREATED)
async def create_inquiry(
    request: InquiryRequest,
    http_request: Request,
    product_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: InquiryService = Depends(InquiryService),
):
    await enforce_limit(service.db, "inquiry-write-ip", get_client_ip(http_request), 20, 60 * 60)
    return await service.create_inquiry(product_id, token, request)


# 내 문의 삭제
@router.delete("/inquiries/{inquiry_id}")
async def delete_inquiry(
    inquiry_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: InquiryService = Depends(InquiryService),
):
    return await service.delete_inquiry(inquiry_id, token)


# 관리자: 문의 목록
@router.get("/admin/inquiries")
async def admin_list_inquiries(
    unanswered: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    token: str = Depends(require_admin_token),
    service: InquiryService = Depends(InquiryService),
):
    return await service.admin_list(token, unanswered, page, page_size)


# 관리자: 답변 등록·수정
@router.put("/admin/inquiries/{inquiry_id}/answer")
async def admin_answer_inquiry(
    request: InquiryAnswerRequest,
    inquiry_id: int = Path(gt=0),
    token: str = Depends(require_admin_token),
    service: InquiryService = Depends(InquiryService),
):
    return await service.admin_answer(token, inquiry_id, request)
