// 주문 취소·환불 사유 목록(서버 schemas/orders.py와 같은 코드)과 주문 카드의 취소 상태·가능한 동작 판정

export const CUSTOMER_REFUND_REASONS = [
  { code: 'change_of_mind', label: '단순 변심' },
  { code: 'wrong_order', label: '주문 실수(수량·상품 잘못 선택)' },
  { code: 'delivery_delay', label: '배송 지연' },
  { code: 'reorder', label: '다른 상품으로 재주문' },
  { code: 'other', label: '기타' },
]

export const ADMIN_REFUND_REASONS = [
  { code: 'customer_request', label: '고객 요청' },
  { code: 'out_of_stock', label: '품절·재고 부족' },
  { code: 'undeliverable', label: '배송 불가' },
  { code: 'other', label: '기타' },
]

export const REASON_DETAIL_MAX_LENGTH = 100 // '기타' 직접 입력(서버와 같은 한도)
export const REJECT_REASON_MAX_LENGTH = 200 // 관리자 거절 사유(서버와 같은 한도)

const REASON_LABELS = Object.fromEntries([...CUSTOMER_REFUND_REASONS, ...ADMIN_REFUND_REASONS].map((reason) => [reason.code, reason.label]))

// 사유 코드와 '기타' 입력 내용을 화면 문구로(기타는 입력 내용만 보여 줌)
export function getReasonText(code, detail) {
  if (code === 'other' && detail) return detail
  return REASON_LABELS[code] ?? code ?? ''
}

// 주문 카드에 붙일 취소·환불 상태 배지(해당 없으면 null)
export function getCancelBadge(order) {
  if (order.status === 'refunded') return { key: 'refunded', label: '환불 완료' }
  if (order.status === 'refunding') return { key: 'refunding', label: '환불 확인 중' }
  if (order.cancel_request?.status === 'requested') return { key: 'requested', label: '취소 요청 중' }
  if (order.cancel_request?.status === 'rejected') return { key: 'rejected', label: '취소 거절' }
  return null
}

// 고객이 할 수 있는 동작: 결제완료는 즉시 취소, 상품준비중은 취소 요청(주문당 1회), 그 밖에는 없음
export function getCustomerCancelAction(order) {
  if (order.status !== 'paid') return null
  if (order.delivery_status === 'paid') return 'refund'
  if (order.delivery_status === 'preparing' && !order.cancel_request) return 'request'
  return null
}

// 관리자가 직접 환불할 수 있는 주문(결제완료·상품준비중)
export function canAdminRefund(order) {
  return order.status === 'paid' && ['paid', 'preparing'].includes(order.delivery_status)
}

// 환불을 접수했지만 결제사 결과를 아직 확인하지 못한 오류(실패가 아니므로 다시 누르지 않게 안내)
export function isRefundPending(error) {
  return error?.code === 'REFUND_CONFIRMATION_PENDING' || error?.code === 'REFUND_IN_PROGRESS'
}
