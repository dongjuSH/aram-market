// 관리자 상품 문의 목록·답변 API 호출

import { request } from './auth.js'

// 문의 목록(status: pending 답변 대기·answered 답변 완료, q: 상품명·내용·닉네임 검색)
export function getAdminInquiries({ status = 'pending', q = '', page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ status, q, page: String(page), page_size: String(pageSize) })
  return request(`/api/admin/inquiries?${params}`, { method: 'GET' })
}

// 답변 등록·수정
export function answerInquiry(inquiryId, answer) {
  return request(`/api/admin/inquiries/${inquiryId}/answer`, { method: 'PUT', body: { answer } })
}
