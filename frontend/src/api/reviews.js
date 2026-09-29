// 상품 후기 조회·작성·수정·삭제 API 호출

import { request } from './user-auth.js'

// 후기 목록과 평점 요약(비로그인도 조회 가능)
export function getReviews(productId, page = 1) {
  return request(`/api/products/${productId}/reviews?page=${page}&page_size=5`, { method: 'GET' })
}

// 내가 이 상품에 후기를 쓸 수 있는지(구매 여부·작성 여부) 확인
export function getReviewEligibility(productId) {
  return request(`/api/products/${productId}/reviews/eligibility`, { method: 'GET' })
}

export function createReview(productId, { rating, content }) {
  return request(`/api/products/${productId}/reviews`, { body: { rating, content } })
}

export function updateReview(reviewId, { rating, content }) {
  return request(`/api/reviews/${reviewId}`, { method: 'PUT', body: { rating, content } })
}

export function deleteReview(reviewId) {
  return request(`/api/reviews/${reviewId}`, { method: 'DELETE' })
}
