// 상품 재고 표시·수량 제한 공통 규칙(품절·N개 남음, 서버 OUT_OF_STOCK 오류와 같은 문구)

export const MAX_QUANTITY = 99 // 상품당 최대 담기·구매 수량(서버 장바구니·주문과 같음)
export const MAX_PRODUCT_STOCK = 1_000_000 // 관리자가 입력할 수 있는 재고 상한(서버와 같음)

// 재고 정보가 없는 상품(재고 도입 전 응답)은 제한하지 않음
function hasStock(product) {
  return Number.isInteger(product?.stock)
}

export function isSoldOut(product) {
  return hasStock(product) && product.stock <= 0
}

// 한 번에 담거나 살 수 있는 최대 수량(재고와 99 중 작은 값, 품절이면 0)
export function maxPurchasable(product) {
  return hasStock(product) ? Math.max(0, Math.min(MAX_QUANTITY, product.stock)) : MAX_QUANTITY
}

// 상세 화면에 보일 구매 수량: 품절이면 0, 아니면 고른 수량을 1~최대 구매 수량으로 맞춤(다시 불러온 재고가 줄어든 경우 포함)
export function purchaseQuantity(selected, product) {
  const limit = maxPurchasable(product)
  return limit === 0 ? 0 : Math.max(1, Math.min(selected, limit))
}

// 재고 부족 안내 문구(서버 stock_shortage_message와 같은 형식)
export function stockShortageMessage(name, available) {
  return available <= 0 ? `'${name}' 상품이 품절되었습니다.` : `'${name}' 상품은 ${available}개 남아 있습니다.`
}

// 장바구니·주문서 상품 줄의 재고 문제(없으면 null): 판매 종료·품절·재고보다 많은 수량
export function stockProblem(item) {
  if (item.on_sale === false) return '판매가 종료된 상품입니다.'
  if (!hasStock(item)) return null
  if (item.stock <= 0) return '품절된 상품입니다.'
  if (item.quantity > item.stock) return `${item.stock}개 남아 있습니다. 수량을 줄여 주세요.`
  return null
}
