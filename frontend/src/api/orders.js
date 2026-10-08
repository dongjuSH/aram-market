// 주문 생성·결제 승인·주문 내역 API 호출

import { request } from './user-auth.js'

// 주문 생성: 가격은 보내지 않고 서버가 계산한 주문번호·금액을 받아 결제창에 사용
export function createOrder(items, fromCart, shipping) {
  return request('/api/orders', {
    body: {
      items: items.map((item) => ({ product_id: item.id, quantity: item.quantity })),
      from_cart: fromCart,
      shipping: {
        recipient_name: shipping.recipientName,
        recipient_phone: shipping.recipientPhone,
        postcode: shipping.postcode,
        address: shipping.address,
        address_detail: shipping.addressDetail,
        no_address_detail: shipping.noAddressDetail,
        delivery_memo: shipping.deliveryMemo,
      },
    },
  })
}

// 결제창 성공 리다이렉트 값으로 서버 승인 요청
export function confirmPayment({ paymentKey, orderId, amount }) {
  return request('/api/orders/confirm', { body: { payment_key: paymentKey, order_id: orderId, amount } })
}

// 결제 완료된 내 주문 내역(months: 3·6·12개월 또는 from·to: YYYY-MM-DD 직접 지정, 생략하면 전체 기간 최신순)
export function getOrders({ months, from, to, page = 1, pageSize = 5 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (months) params.set('months', String(months))
  if (from && to) {
    params.set('from', from)
    params.set('to', to)
  }
  return request(`/api/orders?${params}`, { method: 'GET' })
}

// 결제완료 주문 즉시 취소·환불(사유 코드와 '기타' 입력 내용)
export function refundOrder(orderId, { reasonCode, reasonDetail = '' }) {
  return request(`/api/orders/${encodeURIComponent(orderId)}/refund`, { body: { reason_code: reasonCode, reason_detail: reasonDetail } })
}

// 상품준비중 주문 취소 요청(판매자 승인 후 환불, 주문당 1회)
export function requestOrderCancel(orderId, { reasonCode, reasonDetail = '' }) {
  return request(`/api/orders/${encodeURIComponent(orderId)}/cancel-request`, { body: { reason_code: reasonCode, reason_detail: reasonDetail } })
}
