// 결제 승인 API 오류를 실제 실패와 아직 결과를 확인 중인 상태로 구분

export function paymentErrorState(error) {
  if (error?.code === 'PAYMENT_CONFIRMATION_PENDING') {
    return {
      status: 'pending',
      message: '결제 결과를 확인하고 있습니다. 결과가 확정될 때까지 같은 상품을 다시 주문하지 마세요.',
    }
  }
  if (error?.code === 'OUT_OF_STOCK') {
    // 결제 승인 직전 재고 차감에 실패: 결제사 승인을 요청하지 않았으므로 결제되지 않음
    return { status: 'failed', message: `${error.message} 결제는 진행되지 않았어요. 장바구니에서 수량을 확인한 뒤 다시 주문해 주세요.` }
  }
  return { status: 'failed', message: error?.message || '결제를 확인하지 못했습니다.' }
}
