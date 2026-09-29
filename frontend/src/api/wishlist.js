// 로그인 고객의 서버 찜 목록 API 호출

import { request } from './user-auth.js'

// 내 찜 목록 조회(현재 상품명·가격·이미지 포함)
export function getWishlist() {
  return request('/api/wishlist', { method: 'GET' })
}

// 상품 찜하기
export function addWishlistItem(productId) {
  return request(`/api/wishlist/${productId}`, { method: 'PUT' })
}

// 찜 해제
export function removeWishlistItem(productId) {
  return request(`/api/wishlist/${productId}`, { method: 'DELETE' })
}
