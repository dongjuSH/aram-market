// 관리자용 전역 상품 관리와 고객용 공개 상품 조회 API 호출

import { request } from './auth.js'

// 상품 목록 검색과 페이지 단위 조회
export function getProducts({ keyword = '', page = 1, pageSize = 10, status = 'active' } = {}) {
  const query = new URLSearchParams({ keyword, page: String(page), page_size: String(pageSize), status })
  return request(`/api/admin/products?${query}`, {
    method: 'GET',
  })
}

// 활성 상품 카테고리 조회
export function getProductCategories() {
  return request('/api/admin/products/categories', {
    method: 'GET',
  })
}

// 단일 상품과 관련 상품 후보 조회
export function getProduct(productId) {
  return request(`/api/admin/products/${productId}`, {
    method: 'GET',
  })
}

// 선택 카테고리의 관련 상품 후보 조회
export function getRelatedCandidates(categoryId, excludeId) {
  const query = new URLSearchParams({ category_id: String(categoryId) })
  if (excludeId) query.set('exclude_id', String(excludeId))
  return request(`/api/admin/products/related-candidates?${query}`, {
    method: 'GET',
  })
}

// 신규 상품 등록
export function createProduct(form) {
  return request('/api/admin/products', {
    body: form,
  })
}

// 기존 상품 수정
export function updateProduct(productId, form) {
  return request(`/api/admin/products/${productId}`, {
    method: 'PUT',
    body: form,
  })
}

// 상품 소프트 삭제
export function deleteProduct(productId) {
  return request(`/api/admin/products/${productId}`, {
    method: 'DELETE',
  })
}

// 삭제 상품을 충돌 검증 후 미노출 상태로 복원
export function restoreProduct(productId) {
  return request(`/api/admin/products/${productId}/restore`, {
    method: 'POST',
  })
}

// 상세내용 편집기에 삽입할 이미지 Storage 업로드
export function uploadEditorImage(imageData, categoryId, uploadSessionId, productId) {
  return request('/api/admin/products/editor-images', {
    body: {
      image_data: imageData,
      category_id: categoryId,
      upload_session_id: uploadSessionId,
      ...(productId ? { product_id: productId } : {}),
    },
  })
}

// 저장하지 않고 화면을 벗어날 때 해당 편집 세션의 임시 상세 이미지 제거
export function cleanupEditorImageDraft(uploadSessionId, { keepalive = false } = {}) {
  return request(`/api/admin/products/editor-image-drafts/${uploadSessionId}`, {
    method: 'DELETE',
    keepalive,
  })
}

// 고객 화면용 공개 상품 검색·카테고리·페이지 조회
export function getCatalogProducts({ keyword = '', categoryId = '', page = 1, pageSize = 12 } = {}) {
  const query = new URLSearchParams({ keyword, page: String(page), page_size: String(pageSize) })
  if (categoryId) query.set('category_id', String(categoryId))
  return request(`/api/products?${query}`, { method: 'GET' })
}

// 고객 화면용 공개 카테고리 조회
export function getCatalogCategories() {
  return request('/api/products/categories', { method: 'GET' })
}

// 고객 화면용 공개 상품 상세 조회
export function getCatalogProduct(productId) {
  return request(`/api/products/${productId}`, { method: 'GET' })
}

// 주문서가 결제 전에 상품별 판매 여부·현재 재고를 다시 확인(최대 100개)
export function getCatalogAvailability(productIds) {
  const query = new URLSearchParams(productIds.map((id) => ['ids', String(id)]))
  return request(`/api/products/availability?${query}`, { method: 'GET' })
}
