import assert from 'node:assert/strict'
import test from 'node:test'

import { paymentErrorState } from './payment-result-state.js'

test('승인 결과 불확정 오류는 결제 실패가 아닌 확인 중 상태로 표시한다', () => {
  const state = paymentErrorState({ code: 'PAYMENT_CONFIRMATION_PENDING', message: 'server message' })
  assert.equal(state.status, 'pending')
  assert.match(state.message, /다시 주문하지 마세요/)
})

test('확정 오류는 실패 상태와 서버 안내를 유지한다', () => {
  assert.deepEqual(paymentErrorState({ code: 'PAYMENT_FAILED', message: '카드 거절' }), {
    status: 'failed',
    message: '카드 거절',
  })
})

test('승인 직전 재고 부족은 결제되지 않은 실패로 안내한다', () => {
  const state = paymentErrorState({ code: 'OUT_OF_STOCK', message: "'립밤' 상품이 품절되었습니다." })
  assert.equal(state.status, 'failed')
  assert.match(state.message, /^'립밤' 상품이 품절되었습니다\. 결제는 진행되지 않았어요/)
})
