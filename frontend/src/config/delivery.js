// 주문 배송 진행 단계(서버 delivery_status와 같은 순서)와 화면 표시 이름

export const DELIVERY_STEPS = [
  { key: 'paid', label: '결제완료' },
  { key: 'preparing', label: '상품준비중' },
  { key: 'shipping', label: '배송중' },
  { key: 'delivered', label: '배송완료' },
]

// 배송 상태 키를 표시 이름으로 변환
export function getDeliveryLabel(statusKey) {
  return DELIVERY_STEPS.find((step) => step.key === statusKey)?.label ?? statusKey
}
