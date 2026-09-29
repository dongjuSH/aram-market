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
        delivery_memo: shipping.deliveryMemo,
      },
    },
  })
}

// 결제창 성공 리다이렉트 값으로 서버 승인 요청
export function confirmPayment({ paymentKey, orderId, amount }) {
  return request('/api/orders/confirm', { body: { payment_key: paymentKey, order_id: orderId, amount } })
}

// 결제 완료된 내 주문 내역
export function getOrders() {
  return request('/api/orders', { method: 'GET' })
}
