// 주문 초안(주문할 상품) 보관과 주문 생성(서버가 금액 계산) 후 결제창을 여는 구매 진행 함수

import { createOrder } from '../../api/orders.js'
import { createAddress } from '../../api/addresses.js'
import { requestPayment } from './toss-payments.js'

const DRAFT_KEY = 'aramMarketCheckoutDraft' // 탭을 닫으면 사라지는 sessionStorage에 보관

// 구매하기·주문하기 버튼에서 주문 화면으로 넘길 상품 저장(items: 상품 표시 정보와 수량, fromCart: 장바구니 주문 여부)
export function saveCheckoutDraft(draft) {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  } catch {
    // 저장소 사용 불가 시 주문 화면이 빈 상태로 안내됨
  }
}

// 주문 화면에서 초안 조회(없거나 손상되면 null)
export function loadCheckoutDraft() {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null')
    return draft && Array.isArray(draft.items) && draft.items.length > 0 ? draft : null
  } catch {
    return null
  }
}

// 결제 성공 후 초안 제거
export function clearCheckoutDraft() {
  try {
    sessionStorage.removeItem(DRAFT_KEY)
  } catch {
    // 저장소 사용 불가 시 무시
  }
}

// 결제 성공 후 주문서에서 입력한 새 배송지를 주소록에 추가(첫 배송지는 서버가 기본 배송지로 지정). 성공 여부만 반환
export async function saveNewAddress({ label, newAddress }) {
  try {
    await createAddress({ label, ...newAddress, isDefault: false })
    return true
  } catch {
    return false
  }
}

// 배송지와 함께 주문을 만들고 결제창을 염(금액은 서버가 상품 가격으로 계산)
export async function startCheckout(items, fromCart, shipping) {
  const order = await createOrder(items, fromCart, shipping)
  return requestPayment(order)
}
