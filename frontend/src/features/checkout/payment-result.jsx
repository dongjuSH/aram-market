// 결제창에서 돌아온 뒤 서버 승인 결과(성공) 또는 실패 사유를 보여주는 화면

import { useEffect, useRef, useState } from 'react'
import { confirmPayment } from '../../api/orders.js'
import { clearCheckoutDraft, loadCheckoutDraft, saveNewAddress } from './checkout.js'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import { CHECKOUT_PATH, CUSTOMER_PRODUCTS_PATH, USER_MY_PAGE_PATH } from '../../config/routes.js'

// 결제 성공 리다이렉트: 금액 조작을 막기 위해 서버가 결제사에 승인을 요청한 뒤 결과를 표시
export function PaymentSuccessPage({ onNavigate }) {
  const params = new URLSearchParams(window.location.search)
  const paymentKey = params.get('paymentKey') || ''
  const orderId = params.get('orderId') || ''
  const amount = Number(params.get('amount'))
  const isValid = Boolean(paymentKey && orderId && Number.isInteger(amount) && amount > 0)
  const [state, setState] = useState(isValid ? { status: 'loading' } : { status: 'failed', message: '결제 정보가 올바르지 않습니다.' })
  const requestedRef = useRef(false) // 개발 모드 이중 실행에도 승인 요청은 한 번만

  useEffect(() => {
    if (!isValid || requestedRef.current) return
    requestedRef.current = true
    confirmPayment({ paymentKey, orderId, amount })
      .then(async (order) => {
        // 주문서에서 '주소록에 저장'을 선택한 새 배송지는 결제 성공 후에만 저장(실패해도 결제 결과에는 영향 없음)
        const draft = loadCheckoutDraft()
        const addressSaved = draft?.saveToBook && draft.newAddress ? await saveNewAddress(draft) : null
        clearCheckoutDraft() // 결제가 끝났으니 주문 초안(배송지 포함)을 지움
        setState({ status: 'success', order, addressSaved })
      })
      .catch((error) => setState({ status: 'failed', message: error.message }))
  }, [isValid, paymentKey, orderId, amount])

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth">
      <section className="auth-panel auth-panel--login" aria-labelledby="payment-title">
        <header className="auth-header">
          <p className="auth-eyebrow">PAYMENT</p>
          <h1 id="payment-title">
            {state.status === 'loading' && '결제 확인 중'}
            {state.status === 'success' && '결제가 완료되었습니다'}
            {state.status === 'failed' && '결제에 실패했습니다'}
          </h1>
          <p className="auth-description" role="status">
            {state.status === 'loading' && '결제 결과를 확인하고 있습니다. 창을 닫지 말아 주세요.'}
            {state.status === 'failed' && state.message}
          </p>
        </header>
        {state.status === 'success' && (
          <dl className="payment-summary">
            <div><dt>주문번호</dt><dd>{state.order.order_id}</dd></div>
            <div><dt>주문 상품</dt><dd>{state.order.order_name}</dd></div>
            <div><dt>결제 금액</dt><dd>{state.order.total_amount.toLocaleString('ko-KR')}원</dd></div>
            {state.addressSaved !== null && state.addressSaved !== undefined && (
              <div><dt>주소록</dt><dd>{state.addressSaved ? '배송지를 주소록에 저장했어요' : '주소록에 저장하지 못했어요. 마이 페이지에서 추가할 수 있어요'}</dd></div>
            )}
          </dl>
        )}
        {state.status !== 'loading' && (
          <div className="signup-actions">
            <button className="primary-button" type="button" onClick={() => onNavigate(state.status === 'success' ? USER_MY_PAGE_PATH : CUSTOMER_PRODUCTS_PATH, { replace: true })}>
              {state.status === 'success' ? '주문 내역 보기' : '쇼핑 계속하기'}
            </button>
          </div>
        )}
      </section>
    </CustomerAccountShell>
  )
}

// 결제사 실패 코드별 안내(주소의 message는 누구나 바꿔 넣을 수 있어 화면에 그대로 쓰지 않음)
const PAYMENT_FAIL_MESSAGES = {
  PAY_PROCESS_CANCELED: '결제를 취소했습니다. 주문서에서 다시 결제할 수 있어요.',
  PAY_PROCESS_ABORTED: '결제가 중단되었습니다. 잠시 후 다시 시도해 주세요.',
  REJECT_CARD_COMPANY: '카드사에서 결제를 거절했습니다. 카드 정보를 확인하거나 다른 카드를 이용해 주세요.',
}
const DEFAULT_PAYMENT_FAIL_MESSAGE = '결제가 완료되지 않았습니다. 다시 시도하거나 다른 결제 수단을 이용해 주세요.'

// 결제 실패·취소 리다이렉트: 결제사 오류 코드에 맞는 고정 문구와 (형식이 올바르면) 코드만 표시
export function PaymentFailPage({ onNavigate }) {
  const code = new URLSearchParams(window.location.search).get('code') || ''
  const safeCode = /^[A-Z0-9_]{1,60}$/.test(code) ? code : ''
  const message = PAYMENT_FAIL_MESSAGES[safeCode] || DEFAULT_PAYMENT_FAIL_MESSAGE
  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--auth">
      <section className="auth-panel auth-panel--login" aria-labelledby="payment-fail-title">
        <header className="auth-header">
          <p className="auth-eyebrow">PAYMENT</p>
          <h1 id="payment-fail-title">결제에 실패했습니다</h1>
          <p className="auth-description" role="alert">{message}</p>
          {safeCode && <p className="auth-description">오류 코드: {safeCode}</p>}
        </header>
        <div className="signup-actions">
          <button className="primary-button" type="button" onClick={() => onNavigate(CHECKOUT_PATH, { replace: true })}>주문서로 돌아가기</button>
        </div>
      </section>
    </CustomerAccountShell>
  )
}
