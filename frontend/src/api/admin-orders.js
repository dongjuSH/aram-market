// 관리자 주문 목록·배송 상태 변경 API 호출

import { request } from './auth.js'

// 결제 완료 주문 목록(배송 상태 필터 선택)
export function getAdminOrders({ deliveryStatus = '', page = 1 } = {}) {
  const query = new URLSearchParams({ page: String(page), page_size: '10' })
  if (deliveryStatus) query.set('delivery_status', deliveryStatus)
  return request(`/api/admin/orders?${query}`, { method: 'GET' })
}

// 배송 상태를 다음 단계로 변경
export function updateDeliveryStatus(orderId, status) {
  return request(`/api/admin/orders/${orderId}/delivery-status`, { method: 'PUT', body: { status } })
}
