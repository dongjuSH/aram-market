// 상품 문의 조회·작성·삭제 API 호출

import { request } from './user-auth.js'

// 문의 목록(비밀글은 작성자에게만 내용 공개, 비로그인도 조회 가능)
export function getInquiries(productId, page = 1) {
  return request(`/api/products/${productId}/inquiries?page=${page}&page_size=5`, { method: 'GET' })
}

export function createInquiry(productId, { content, isSecret }) {
  return request(`/api/products/${productId}/inquiries`, { body: { content, is_secret: isSecret } })
}

export function deleteInquiry(inquiryId) {
  return request(`/api/inquiries/${inquiryId}`, { method: 'DELETE' })
}
