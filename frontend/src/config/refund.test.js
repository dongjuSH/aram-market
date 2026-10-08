// 주문 카드의 취소·환불 상태 배지와 고객·관리자 동작 판정 테스트

import assert from 'node:assert/strict'
import test from 'node:test'

import { canAdminRefund, getCancelBadge, getCustomerCancelAction, getReasonText, isRefundPending } from './refund.js'

const order = (overrides = {}) => ({ status: 'paid', delivery_status: 'paid', cancel_request: null, ...overrides })

test('고객은 결제완료면 즉시 취소, 상품준비중이면 요청이 없을 때만 취소 요청을 할 수 있다', () => {
  assert.equal(getCustomerCancelAction(order()), 'refund')
  assert.equal(getCustomerCancelAction(order({ delivery_status: 'preparing' })), 'request')
  assert.equal(getCustomerCancelAction(order({ delivery_status: 'preparing', cancel_request: { status: 'requested' } })), null)
  assert.equal(getCustomerCancelAction(order({ delivery_status: 'preparing', cancel_request: { status: 'rejected' } })), null) // 재요청 불가
  for (const delivery of ['shipping', 'delivered']) assert.equal(getCustomerCancelAction(order({ delivery_status: delivery })), null)
  for (const status of ['refunding', 'refunded']) assert.equal(getCustomerCancelAction(order({ status })), null)
})

test('관리자는 결제완료·상품준비중 결제 완료 주문만 직접 환불할 수 있다', () => {
  assert.equal(canAdminRefund(order()), true)
  assert.equal(canAdminRefund(order({ delivery_status: 'preparing' })), true)
  assert.equal(canAdminRefund(order({ delivery_status: 'shipping' })), false)
  assert.equal(canAdminRefund(order({ status: 'refunding' })), false)
})

test('환불 상태가 취소 요청 상태보다 먼저 표시된다', () => {
  assert.equal(getCancelBadge(order()), null)
  assert.equal(getCancelBadge(order({ cancel_request: { status: 'requested' } })).label, '취소 요청 중')
  assert.equal(getCancelBadge(order({ cancel_request: { status: 'rejected' } })).label, '취소 거절')
  assert.equal(getCancelBadge(order({ status: 'refunding', cancel_request: { status: 'approved' } })).label, '환불 확인 중')
  assert.equal(getCancelBadge(order({ status: 'refunded', cancel_request: { status: 'approved' } })).label, '환불 완료')
})

test('사유 문구와 결과 확인 중 오류 구분', () => {
  assert.equal(getReasonText('out_of_stock', ''), '품절·재고 부족')
  assert.equal(getReasonText('other', '주소 변경'), '주소 변경')
  assert.equal(isRefundPending({ code: 'REFUND_CONFIRMATION_PENDING' }), true)
  assert.equal(isRefundPending({ code: 'REFUND_IN_PROGRESS' }), true)
  assert.equal(isRefundPending({ code: 'REFUND_FAILED' }), false)
})
