# 고객용 공개 상품 목록·상세 HTTP 엔드포인트

from fastapi import APIRouter, Depends, Query

from backend.domain.products.services.products import ProductService


router = APIRouter(prefix="/products", tags=["customer-products"])


# 고객 화면용 활성 카테고리 조회
@router.get("/categories")
async def list_catalog_categories(product_service: ProductService = Depends(ProductService)):
    return await product_service.list_categories()


# 고객 화면용 노출 상품 검색·카테고리·페이지 조회
@router.get("")
async def list_catalog_products(
    keyword: str = Query(default="", max_length=100),
    category_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    product_service: ProductService = Depends(ProductService),
):
    return await product_service.list_catalog_products(keyword, category_id, page, page_size)


# 고객 화면용 단일 노출 상품과 관련 상품 조회
@router.get("/{product_id}")
async def get_catalog_product(product_id: int, product_service: ProductService = Depends(ProductService)):
    return await product_service.get_catalog_product(product_id)
