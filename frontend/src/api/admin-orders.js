// 관리자 주문 목록·배송 상태 변경·환불·취소 요청 처리 API 호출

import { request } from './auth.js'

// 주문 목록(배송 상태 필터 또는 view: cancel_requested·refunded 탭)
export function getAdminOrders({ deliveryStatus = '', view = '', page = 1 } = {}) {
  const query = new URLSearchParams({ page: String(page), page_size: '10' })
  if (deliveryStatus) query.set('delivery_status', deliveryStatus)
  if (view) query.set('view', view)
  return request(`/api/admin/orders?${query}`, { method: 'GET' })
}

// 배송 상태를 다음 단계로 변경
export function updateDeliveryStatus(orderId, status) {
  return request(`/api/admin/orders/${orderId}/delivery-status`, { method: 'PUT', body: { status } })
}

// 결제완료·상품준비중 주문 직접 환불
export function refundAdminOrder(orderId, { reasonCode, reasonDetail = '' }) {
  return request(`/api/admin/orders/${encodeURIComponent(orderId)}/refund`, { body: { reason_code: reasonCode, reason_detail: reasonDetail } })
}

// 고객 취소 요청 승인(환불)
export function approveCancelRequest(orderId) {
  return request(`/api/admin/orders/${encodeURIComponent(orderId)}/cancel-request/approve`, { method: 'POST' })
}

// 고객 취소 요청 거절(사유 필수)
export function rejectCancelRequest(orderId, reason) {
  return request(`/api/admin/orders/${encodeURIComponent(orderId)}/cancel-request/reject`, { body: { reason } })
}
