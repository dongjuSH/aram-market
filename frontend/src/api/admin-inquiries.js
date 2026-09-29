// 관리자 상품 문의 목록·답변 API 호출

import { request } from './auth.js'

// 문의 목록(답변 대기만 보기 선택)
export function getAdminInquiries({ unanswered = false, page = 1 } = {}) {
  return request(`/api/admin/inquiries?unanswered=${unanswered}&page=${page}&page_size=10`, { method: 'GET' })
}

// 답변 등록·수정
export function answerInquiry(inquiryId, answer) {
  return request(`/api/admin/inquiries/${inquiryId}/answer`, { method: 'PUT', body: { answer } })
}
