# 인증 관리자의 전역 상품 조회·등록·수정·삭제 HTTP 엔드포인트

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from backend.domain.products.schemas.products import EditorImageUploadRequest, ProductCreateRequest, ProductUpdateRequest
from backend.domain.products.services.products import ProductService
from backend.core.dependencies import require_admin_token
from backend.core.errors import api_error
from backend.domain.admins.services.admins import AdminAccountService
from backend.core.validators import MAX_DB_ID


router = APIRouter(prefix="/admin/products", tags=["admin-products"])


# 확장 가능한 활성 상품 카테고리 조회
@router.get("/categories")
async def list_categories(
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.list_categories()


# 상품명·상품코드 검색과 페이지 크기별 전역 상품 목록 조회
@router.get("")
async def list_products(
    keyword: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10),
    product_status: str = Query(default="active", alias="status"),
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    if page_size not in {10, 50, 100}:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_PAGE_SIZE", "페이지당 상품 수는 10, 50, 100 중에서 선택해 주세요.")
    if product_status not in {"active", "deleted"}:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_PRODUCT_STATUS", "상품 상태가 올바르지 않습니다.")
    await admin_service.get_authenticated_admin(token)
    return await product_service.list_products(keyword, page, page_size, product_status)


# 신규 관리자 상품 등록
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreateRequest,
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.create_product(request)


# 상품 상세내용 편집기 이미지 Storage 업로드
@router.post("/editor-images", status_code=status.HTTP_201_CREATED)
async def upload_editor_image(
    request: EditorImageUploadRequest,
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.upload_editor_image(request)


# 상품 저장 전 등록·수정 화면을 취소한 경우 해당 편집 세션의 임시 이미지 정리
@router.delete("/editor-image-drafts/{upload_session_id}")
async def cleanup_editor_image_draft(
    upload_session_id: UUID,
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.cleanup_editor_draft(str(upload_session_id))


# 선택한 카테고리의 관련 상품 후보 조회
@router.get("/related-candidates")
async def list_related_candidates(
    category_id: int = Query(gt=0),
    exclude_id: int | None = Query(default=None, gt=0),
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.related_candidates(category_id, exclude_id)


# 단일 전역 상품과 관련 상품 후보 조회
@router.get("/{product_id}")
async def get_product(
    product_id: Annotated[int, Path(gt=0, le=MAX_DB_ID)],
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.get_product(product_id)


# 기존 관리자 상품 수정
@router.put("/{product_id}")
async def update_product(
    product_id: Annotated[int, Path(gt=0, le=MAX_DB_ID)],
    request: ProductUpdateRequest,
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.update_product(product_id, request)


# 전역 상품 소프트 삭제
@router.delete("/{product_id}")
async def delete_product(
    product_id: Annotated[int, Path(gt=0, le=MAX_DB_ID)],
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.delete_product(product_id)


# 삭제 상품을 충돌 검증 후 미노출 상태로 복원
@router.post("/{product_id}/restore")
async def restore_product(
    product_id: Annotated[int, Path(gt=0, le=MAX_DB_ID)],
    token: str = Depends(require_admin_token),
    admin_service: AdminAccountService = Depends(AdminAccountService),
    product_service: ProductService = Depends(ProductService),
):
    await admin_service.get_authenticated_admin(token)
    return await product_service.restore_product(product_id)
