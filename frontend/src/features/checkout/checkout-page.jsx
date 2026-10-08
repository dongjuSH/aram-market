// 주문 상품 확인과 배송지 선택(주소록) 또는 새 배송지 입력 후 결제창을 여는 주문서 화면

import { useEffect, useState } from 'react'
import { getAddresses } from '../../api/addresses.js'
import { getCatalogAvailability } from '../../api/products.js'
import AddressFields from '../../components/user/address-fields.jsx'
import { EMPTY_ADDRESS, validateAddress } from '../../config/address.js'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import { CART_PATH, CUSTOMER_PRODUCTS_PATH, getCustomerProductDetailPath } from '../../config/routes.js'
import { stockProblem } from '../../config/stock.js'
import { loadCheckoutDraft, saveCheckoutDraft, startCheckout } from './checkout.js'

// 주소록 항목을 주문 배송지 형식으로 변환
function toShipping(address, deliveryMemo) {
  return {
    recipientName: address.recipient_name,
    recipientPhone: address.recipient_phone,
    postcode: address.postcode,
    address: address.address,
    addressDetail: address.address_detail,
    noAddressDetail: !address.address_detail,
    deliveryMemo,
  }
}

// 배송지 선택·입력 후 주문 생성과 결제창 호출
function CheckoutPage({ onNavigate }) {
  const [draft] = useState(loadCheckoutDraft)
  const [book, setBook] = useState(null) // { addresses, max_addresses } (불러오는 중이면 null)
  const [mode, setMode] = useState('saved') // saved: 주소록에서 선택, new: 새 배송지 입력
  const [selectedId, setSelectedId] = useState(null)
  const [isPickerOpen, setIsPickerOpen] = useState(false)
  const [newAddress, setNewAddress] = useState(() => draft?.newAddress ?? EMPTY_ADDRESS)
  const [saveToBook, setSaveToBook] = useState(() => draft?.saveToBook ?? true) // 결제 성공 후 새 배송지를 주소록에 저장할지
  const [label, setLabel] = useState(() => draft?.label ?? '')
  const [memo, setMemo] = useState(() => draft?.memo ?? '')
  const [message, setMessage] = useState('')
  const [isPaying, setIsPaying] = useState(false)
  const [availability, setAvailability] = useState({}) // 상품 id → { on_sale, stock }: 주문서를 연 시점·재고 부족 응답 기준 최신 재고

  // 주문서를 열 때 판매 여부·재고를 다시 확인(장바구니에 담은 뒤 품절될 수 있음). 실패해도 서버가 주문 생성·승인에서 다시 확인
  useEffect(() => {
    if (!draft) return
    let isMounted = true
    getCatalogAvailability(draft.items.map((item) => item.id))
      .then((result) => {
        if (isMounted) setAvailability(Object.fromEntries(result.items.map((item) => [item.id, item])))
      })
      .catch(() => {})
    return () => {
      isMounted = false
    }
  }, [draft])

  // 주소록을 불러와 처음 선택을 정함: 이전 입력(결제 취소 후 복귀) → 기본 배송지 → 새 배송지 입력
  useEffect(() => {
    if (!draft) return
    let isMounted = true
    getAddresses()
      .then((addressBook) => {
        if (!isMounted) return
        setBook(addressBook)
        const saved = addressBook.addresses
        const previous = saved.find((address) => address.id === draft.addressId)
        if (previous) {
          setSelectedId(previous.id)
          return
        }
        if (draft.newAddress || saved.length === 0) {
          setMode('new')
          if (!draft.label && saved.length === 0) setLabel('집')
          return
        }
        setSelectedId(saved[0].id) // 기본 배송지가 목록 맨 앞
      })
      .catch((error) => {
        if (!isMounted) return
        setBook({ addresses: [], max_addresses: 10 })
        setMode('new')
        setMessage(error.message)
      })
    return () => {
      isMounted = false
    }
  }, [draft])

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
  const stockProblems = Object.fromEntries(
    draft.items.map((item) => [item.id, availability[item.id] ? stockProblem({ ...item, ...availability[item.id], quantity: item.quantity }) : null]),
  )
  const hasStockProblem = Object.values(stockProblems).some(Boolean)
  const addresses = book?.addresses ?? []
  const selected = addresses.find((address) => address.id === selectedId)
  const isBookFull = book ? addresses.length >= book.max_addresses : false
  const canSaveToBook = mode === 'new' && !isBookFull

  const pickAddress = (addressId) => {
    setMode('saved')
    setSelectedId(addressId)
    setIsPickerOpen(false)
    setMessage('')
  }

  const startNewAddress = () => {
    setMode('new')
    setIsPickerOpen(false)
    setMessage('')
  }

  // 입력 확인 후 주문 생성·결제창 호출(결제 취소·실패로 돌아와도 선택·입력이 유지되도록 초안에 남김)
  async function handleSubmit(event) {
    event.preventDefault()
    let shipping
    if (mode === 'saved' && selected) {
      shipping = toShipping(selected, memo.trim())
      // 우편번호·상세 주소 필수화 이전에 저장한 배송지는 주문 전에 보완 안내
      if (validateAddress(shipping)) {
        setMessage('선택한 배송지에 우편번호나 상세 주소가 없어요. 마이 페이지 배송지 관리에서 수정하거나 새 배송지를 입력해 주세요.')
        return
      }
    } else {
      const validationMessage = validateAddress(newAddress) || (canSaveToBook && saveToBook && !label.trim() ? '배송지 명칭을 입력해 주세요. (예: 집, 회사)' : '')
      if (validationMessage) {
        setMessage(validationMessage)
        return
      }
      shipping = { ...newAddress, deliveryMemo: memo.trim() }
    }
    setIsPaying(true)
    setMessage('')
    saveCheckoutDraft({
      ...draft,
      addressId: mode === 'saved' ? selected.id : null,
      newAddress: mode === 'new' ? newAddress : null,
      saveToBook: mode === 'new' && canSaveToBook && saveToBook,
      label: label.trim(),
      memo,
    })
    try {
      const result = await startCheckout(draft.items, draft.fromCart, shipping)
      if (result.canceled) setMessage('결제를 취소했습니다. 배송지를 확인하고 다시 결제할 수 있어요.')
    } catch (error) {
      const shortages = error.code === 'OUT_OF_STOCK' ? (error.data?.stock_shortages ?? []).filter((item) => item.product_id) : []
      if (shortages.length) {
        // 서버가 알려 준 남은 수량으로 상품 줄 안내를 갱신(결제창은 열리지 않음, 아래 재고 안내가 대신 표시됨)
        setAvailability((current) => ({
          ...current,
          ...Object.fromEntries(shortages.map((item) => [item.product_id, { on_sale: true, stock: item.available }])),
        }))
      } else {
        setMessage(error.message)
      }
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
                      {stockProblems[item.id] && <p className="stock-note stock-note--error">{stockProblems[item.id]}</p>}
                    </div>
                    <em>{(item.price * item.quantity).toLocaleString('ko-KR')}원</em>
                  </li>
                ))}
              </ul>
            </section>

            <section className="checkout-section" aria-labelledby="checkout-shipping-title">
              <div className="checkout-section__heading">
                <h2 id="checkout-shipping-title">배송지</h2>
                {book && addresses.length > 0 && (
                  <button type="button" onClick={() => setIsPickerOpen((open) => !open)} aria-expanded={isPickerOpen}>
                    {isPickerOpen ? '닫기' : '배송지 변경'}
                  </button>
                )}
              </div>

              {!book && <p className="checkout-section__note" role="status">배송지를 불러오고 있습니다.</p>}

              {book && isPickerOpen && (
                <ul className="checkout-addresses" role="radiogroup" aria-label="배송지 선택">
                  {addresses.map((address) => (
                    <li key={address.id}>
                      <button type="button" role="radio" aria-checked={mode === 'saved' && selectedId === address.id} className={mode === 'saved' && selectedId === address.id ? 'is-selected' : ''} onClick={() => pickAddress(address.id)}>
                        <strong>{address.label}{address.is_default && <em>기본 배송지</em>}</strong>
                        <span>{address.recipient_name} · {address.recipient_phone}</span>
                        <span>{address.postcode ? `[${address.postcode}] ` : ''}{address.address} {address.address_detail}</span>
                      </button>
                    </li>
                  ))}
                  <li>
                    <button type="button" role="radio" aria-checked={mode === 'new'} className={`checkout-addresses__new${mode === 'new' ? ' is-selected' : ''}`} onClick={startNewAddress}>
                      + 새 배송지 입력
                    </button>
                  </li>
                </ul>
              )}

              {book && !isPickerOpen && mode === 'saved' && selected && (
                <div className="checkout-address-card">
                  <strong>{selected.label}{selected.is_default && <em>기본 배송지</em>}</strong>
                  <span>{selected.recipient_name} · {selected.recipient_phone}</span>
                  <span>{selected.postcode ? `[${selected.postcode}] ` : ''}{selected.address} {selected.address_detail}</span>
                </div>
              )}

              {book && mode === 'new' && !isPickerOpen && (
                <>
                  <AddressFields values={newAddress} onChange={(name, value) => setNewAddress((values) => ({ ...values, [name]: value }))} />
                  {isBookFull ? (
                    <p className="checkout-section__note">주소록이 가득 차서(최대 {book.max_addresses}개) 이 배송지는 저장되지 않아요. 마이 페이지에서 사용하지 않는 배송지를 삭제하면 저장할 수 있어요.</p>
                  ) : (
                    <>
                      <label className="checkout-save-default">
                        <input type="checkbox" checked={saveToBook} onChange={(event) => setSaveToBook(event.target.checked)} />
                        <span>
                          이 배송지를 주소록에 저장
                          <small>결제가 완료되면 마이 페이지 배송지 관리에 추가되어 다음 주문에서 바로 고를 수 있어요. 기존 배송지는 바뀌지 않아요.</small>
                        </span>
                      </label>
                      {saveToBook && (
                        <label>
                          <span>배송지 명칭</span>
                          <input value={label} maxLength={20} placeholder="예: 집, 회사" onChange={(event) => setLabel(event.target.value)} />
                        </label>
                      )}
                    </>
                  )}
                </>
              )}

              {book && (
                <label>
                  <span>배송 요청사항 (선택)</span>
                  <input value={memo} maxLength={200} placeholder="예: 문 앞에 놓아 주세요" onChange={(event) => setMemo(event.target.value)} />
                </label>
              )}
            </section>
            {hasStockProblem && (
              <p className="checkout-error" role="alert">
                품절되었거나 재고가 부족한 상품이 있어 결제할 수 없어요. 이전으로 돌아가 수량을 줄이거나 상품을 빼 주세요.
              </p>
            )}
            {message && <p className="checkout-error" role="alert">{message}</p>}
            <div className="checkout-actions">
              <button type="button" onClick={() => onNavigate(draft.fromCart ? CART_PATH : getCustomerProductDetailPath(draft.items[0].id))}>이전으로</button>
              <button className="is-primary" type="submit" disabled={isPaying || !book || hasStockProblem}>{isPaying ? '결제창을 여는 중...' : `${totalPrice.toLocaleString('ko-KR')}원 결제하기`}</button>
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
