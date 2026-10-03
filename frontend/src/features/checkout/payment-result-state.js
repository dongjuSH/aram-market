// 결제 승인 API 오류를 실제 실패와 아직 결과를 확인 중인 상태로 구분

export function paymentErrorState(error) {
  if (error?.code === 'PAYMENT_CONFIRMATION_PENDING') {
    return {
      status: 'pending',
      message: '결제 결과를 확인하고 있습니다. 결과가 확정될 때까지 같은 상품을 다시 주문하지 마세요.',
    }
  }
  return { status: 'failed', message: error?.message || '결제를 확인하지 못했습니다.' }
}
