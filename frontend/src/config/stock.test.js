// 품절·남은 수량·장바구니/주문서 재고 문제 판정 테스트

import assert from 'node:assert/strict'
import test from 'node:test'

import { isSoldOut, maxPurchasable, purchaseQuantity, stockProblem, stockShortageMessage } from './stock.js'

test('재고 0이면 품절이고 살 수 있는 수량은 재고와 99 중 작은 값이다', () => {
  assert.equal(isSoldOut({ stock: 0 }), true)
  assert.equal(isSoldOut({ stock: 2 }), false)
  assert.equal(isSoldOut({}), false) // 재고 정보가 없는 예전 응답은 막지 않음
  assert.equal(maxPurchasable({ stock: 0 }), 0)
  assert.equal(maxPurchasable({ stock: 2 }), 2)
  assert.equal(maxPurchasable({ stock: 500 }), 99)
  assert.equal(maxPurchasable({}), 99)
})

test('재고 부족 문구는 서버 OUT_OF_STOCK 문구와 같다', () => {
  assert.equal(stockShortageMessage('립밤', 0), "'립밤' 상품이 품절되었습니다.")
  assert.equal(stockShortageMessage('립밤', 2), "'립밤' 상품은 2개 남아 있습니다.")
})

test('장바구니·주문서 상품 줄은 판매 종료·품절·재고 초과일 때만 문제로 본다', () => {
  assert.equal(stockProblem({ on_sale: false, stock: 0, quantity: 1 }), '판매가 종료된 상품입니다.')
  assert.equal(stockProblem({ stock: 0, quantity: 1 }), '품절된 상품입니다.')
  assert.equal(stockProblem({ stock: 2, quantity: 3 }), '2개 남아 있습니다. 수량을 줄여 주세요.')
  assert.equal(stockProblem({ stock: 2, quantity: 2 }), null)
  assert.equal(stockProblem({ quantity: 5 }), null)
})

test('상세 구매 수량은 품절이면 0이고 그 밖에는 1~남은 수량으로 맞춘다', () => {
  assert.equal(purchaseQuantity(1, { stock: 0 }), 0)
  assert.equal(purchaseQuantity(3, { stock: 2 }), 2)
  assert.equal(purchaseQuantity(0, { stock: 2 }), 1)
  assert.equal(purchaseQuantity(5, { stock: 100 }), 5)
})
