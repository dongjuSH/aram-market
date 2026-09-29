// 로그인 고객의 서버 장바구니 API 호출

import { request } from './user-auth.js'

// 내 장바구니 조회(현재 상품명·가격·이미지 포함)
export function getCart() {
  return request('/api/cart', { method: 'GET' })
}

// 상품 담기(이미 있으면 수량 합산)
export function addCartItem(productId, quantity = 1) {
  return request('/api/cart/items', { body: { product_id: productId, quantity } })
}

// 담긴 상품 수량 변경
export function setCartItemQuantity(productId, quantity) {
  return request(`/api/cart/items/${productId}`, { method: 'PUT', body: { quantity } })
}

// 선택 상품 삭제
export function removeCartItems(productIds) {
  return request('/api/cart/items', { method: 'DELETE', body: { product_ids: productIds } })
}

// 비로그인으로 담은 상품을 로그인 직후 계정 장바구니에 합치기
export function mergeCart(items) {
  return request('/api/cart/merge', { body: { items: items.map((item) => ({ product_id: item.id, quantity: item.quantity })) } })
}
