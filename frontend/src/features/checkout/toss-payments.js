// 토스페이먼츠 결제창 SDK를 불러와 서버가 만든 주문으로 결제를 요청

import { PAYMENT_FAIL_PATH, PAYMENT_SUCCESS_PATH } from '../../config/routes.js'

const SDK_URL = 'https://js.tosspayments.com/v2/standard'
const CLIENT_KEY = import.meta.env.VITE_TOSS_CLIENT_KEY // 공개 클라이언트 키(테스트는 test_ck_ 로 시작)

let sdkPromise = null

// 결제 SDK 스크립트를 한 번만 불러옴
function loadSdk() {
  if (window.TossPayments) return Promise.resolve(window.TossPayments)
  sdkPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SDK_URL
    script.onload = () => resolve(window.TossPayments)
    script.onerror = () => {
      sdkPromise = null
      reject(new Error('결제 모듈을 불러오지 못했습니다. 네트워크를 확인한 뒤 다시 시도해 주세요.'))
    }
    document.head.appendChild(script)
  })
  return sdkPromise
}

// 결제창 열기: 금액·주문번호는 서버 응답 값만 사용하며, 결제 후 성공·실패 URL로 이동
export async function requestPayment(order) {
  if (!CLIENT_KEY) throw new Error('결제 설정이 완료되지 않았습니다. 관리자에게 문의해 주세요.')
  const TossPayments = await loadSdk()
  const payment = TossPayments(CLIENT_KEY).payment({ customerKey: order.customer_key })
  try {
    await payment.requestPayment({
      method: 'CARD',
      amount: { currency: 'KRW', value: order.amount },
      orderId: order.order_id,
      orderName: order.order_name,
      successUrl: `${window.location.origin}${PAYMENT_SUCCESS_PATH}`,
      failUrl: `${window.location.origin}${PAYMENT_FAIL_PATH}`,
      customerEmail: order.customer_email,
      customerName: order.customer_name,
    })
  } catch (error) {
    // 사용자가 결제창을 닫은 경우는 오류가 아니라 취소로 처리
    if (error?.code === 'USER_CANCEL') return { canceled: true }
    throw new Error(error?.message || '결제창을 열지 못했습니다.')
  }
  return { canceled: false }
}
