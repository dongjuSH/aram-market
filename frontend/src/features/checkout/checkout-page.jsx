// 주문 상품 확인과 배송지 입력 후 결제창을 여는 주문서 화면

import { useState } from 'react'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import { CART_PATH, CUSTOMER_PRODUCTS_PATH } from '../../config/routes.js'
import { loadCheckoutDraft, saveCheckoutDraft, startCheckout } from './checkout.js'

const EMPTY_SHIPPING = { recipientName: '', recipientPhone: '', postcode: '', address: '', addressDetail: '', deliveryMemo: '' }

// 서버 검증과 같은 기준의 입력 확인(첫 오류 문구 반환)
function validateShipping(shipping) {
  if (shipping.recipientName.trim().length < 2) return '받는 분 이름을 2자 이상 입력해 주세요.'
  if (!/^01[016789]\d{7,8}$/.test(shipping.recipientPhone.replace(/\D/g, ''))) return '휴대폰 번호를 010-1234-5678 형식으로 입력해 주세요.'
  if (shipping.address.trim().length < 5) return '주소를 5자 이상 입력해 주세요.'
  return ''
}

// 배송지 입력 후 주문 생성과 결제창 호출
function CheckoutPage({ onNavigate }) {
  const [draft] = useState(loadCheckoutDraft)
  const [shipping, setShipping] = useState(() => draft?.shipping ?? EMPTY_SHIPPING)
  const [message, setMessage] = useState('')
  const [isPaying, setIsPaying] = useState(false)

  const updateField = (event) => {
    const { name, value } = event.target
    setShipping((current) => ({ ...current, [name]: value }))
  }

  if (!draft) {
    return (
      <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--checkout">
        <section className="checkout-panel">
          <h1>주문할 상품이 없어요</h1>
          <p>상품 상세나 장바구니에서 주문을 시작해 주세요.</p>
          <button className="primary-button" type="button" onClick={() => onNavigate(CUSTOMER_PRODUCTS_PATH)}>상품 보러 가기</button>
        </section>
      </CustomerAccountShell>
    )
  }

  const totalPrice = draft.items.reduce((sum, item) => sum + item.price * item.quantity, 0)

  // 입력 확인 → 배송지를 초안에 남긴 뒤 주문 생성·결제창 호출(결제 취소·실패로 돌아와도 입력이 유지됨)
  async function handleSubmit(event) {
    event.preventDefault()
    const validationMessage = validateShipping(shipping)
    if (validationMessage) {
      setMessage(validationMessage)
      return
    }
    setIsPaying(true)
    setMessage('')
    saveCheckoutDraft({ ...draft, shipping })
    try {
      const result = await startCheckout(draft.items, draft.fromCart, shipping)
      if (result.canceled) setMessage('결제를 취소했습니다. 배송지를 확인하고 다시 결제할 수 있어요.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsPaying(false)
    }
  }

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--checkout">
      <div className="checkout-shell">
        <h1>주문서</h1>
        <div className="checkout-layout">
          <form className="checkout-form" onSubmit={handleSubmit} noValidate>
            <section className="checkout-section" aria-labelledby="checkout-items-title">
              <h2 id="checkout-items-title">주문 상품 ({draft.items.length})</h2>
              <ul className="checkout-items">
                {draft.items.map((item) => (
                  <li key={item.id}>
                    {item.image_url ? <img src={item.image_url} alt="" /> : <span className="checkout-items__noimage" aria-hidden="true" />}
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.price.toLocaleString('ko-KR')}원 · {item.quantity}개</span>
                    </div>
                    <em>{(item.price * item.quantity).toLocaleString('ko-KR')}원</em>
                  </li>
                ))}
              </ul>
            </section>

            <section className="checkout-section" aria-labelledby="checkout-shipping-title">
              <h2 id="checkout-shipping-title">배송지</h2>
              <label>
                <span>받는 분</span>
                <input name="recipientName" value={shipping.recipientName} maxLength={30} autoComplete="name" onChange={updateField} />
              </label>
              <label>
                <span>휴대폰 번호</span>
                <input name="recipientPhone" value={shipping.recipientPhone} maxLength={20} inputMode="tel" autoComplete="tel" placeholder="010-1234-5678" onChange={updateField} />
              </label>
              <label>
                <span>우편번호 (선택)</span>
                <input name="postcode" value={shipping.postcode} maxLength={10} autoComplete="postal-code" onChange={updateField} />
              </label>
              <label>
                <span>주소</span>
                <input name="address" value={shipping.address} maxLength={200} autoComplete="street-address" onChange={updateField} />
              </label>
              <label>
                <span>상세 주소 (선택)</span>
                <input name="addressDetail" value={shipping.addressDetail} maxLength={100} onChange={updateField} />
              </label>
              <label>
                <span>배송 요청사항 (선택)</span>
                <input name="deliveryMemo" value={shipping.deliveryMemo} maxLength={200} placeholder="예: 문 앞에 놓아 주세요" onChange={updateField} />
              </label>
            </section>
            {message && <p className="checkout-error" role="alert">{message}</p>}
            <div className="checkout-actions">
              <button type="button" onClick={() => onNavigate(draft.fromCart ? CART_PATH : CUSTOMER_PRODUCTS_PATH)}>이전으로</button>
              <button className="is-primary" type="submit" disabled={isPaying}>{isPaying ? '결제창을 여는 중...' : `${totalPrice.toLocaleString('ko-KR')}원 결제하기`}</button>
            </div>
          </form>

          <aside className="checkout-summary" aria-label="결제 금액">
            <h2>결제 금액</h2>
            <dl>
              <div><dt>상품금액</dt><dd>{totalPrice.toLocaleString('ko-KR')}원</dd></div>
              <div><dt>배송비</dt><dd>무료</dd></div>
            </dl>
            <div className="checkout-summary__total">
              <span>총 결제금액</span>
              <strong>{totalPrice.toLocaleString('ko-KR')}<small>원</small></strong>
            </div>
            <p>결제는 토스페이먼츠 테스트 모드로 진행되며 실제 청구되지 않습니다.</p>
          </aside>
        </div>
      </div>
    </CustomerAccountShell>
  )
}

export default CheckoutPage
