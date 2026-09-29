// 담아 둔 상품의 수량 변경·선택 삭제와 주문 금액을 보여주는 고객 장바구니 페이지

import { useMemo, useState } from 'react'
import { getStoredUser } from '../../api/user-auth.js'
import CatalogFooter from '../../components/products/catalog-footer.jsx'
import CatalogHeader from '../../components/products/catalog-header.jsx'
import { saveCheckoutDraft } from '../checkout/checkout.js'
import { CART_PATH, CHECKOUT_PATH, CUSTOMER_PRODUCTS_PATH, getCustomerProductDetailPath, getLoginPath } from '../../config/routes.js'
import { MAX_QUANTITY, removeFromCart, updateCartQuantity, useShopping } from './shopping-store.js'

// 선택 상품 기준 금액을 계산하는 장바구니 화면
function CartPage({ onNavigate }) {
  const { items, isLoading } = useShopping()
  // 선택 해제한 상품만 기억해 두면 새로 담긴 상품은 자동으로 선택됨
  const [excludedIds, setExcludedIds] = useState(() => new Set())
  const isLoggedIn = Boolean(getStoredUser())

  const selectedItems = useMemo(() => items.filter((item) => !excludedIds.has(item.id)), [items, excludedIds])
  const totalPrice = selectedItems.reduce((sum, item) => sum + item.price * item.quantity, 0)
  const isAllSelected = items.length > 0 && selectedItems.length === items.length

  function toggleItem(productId) {
    setExcludedIds((current) => {
      const next = new Set(current)
      if (next.has(productId)) next.delete(productId)
      else next.add(productId)
      return next
    })
  }

  // 로그인 확인 후 선택 상품을 주문서(배송지 입력)로 넘김
  function handleOrder() {
    if (!getStoredUser()) {
      onNavigate(getLoginPath(CART_PATH))
      return
    }
    saveCheckoutDraft({ items: selectedItems, fromCart: true })
    onNavigate(CHECKOUT_PATH)
  }

  return (
    <div className="catalog-page cart-page">
      <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
      <CatalogHeader onNavigate={onNavigate} />
      <main id="catalog-main" className="cart-shell" tabIndex="-1">
        <header className="cart-heading">
          <p>SHOPPING CART</p>
          <h1>장바구니 <span>{items.length}</span></h1>
        </header>

        {!isLoggedIn && (
          <div className="cart-login-banner">
            <p>
              <strong>로그인하고 주문해 보세요.</strong>
              <span>로그인하지 않으면 새로고침 시 장바구니가 초기화됩니다. 로그인하면 담은 상품이 계정에 보관돼요.</span>
            </p>
            <button type="button" onClick={() => onNavigate(getLoginPath(CART_PATH))}>로그인</button>
          </div>
        )}

        {isLoading && items.length === 0 ? (
          <p className="catalog-notice" role="status">장바구니를 불러오고 있습니다.</p>
        ) : items.length === 0 ? (
          <div className="cart-empty">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 5h2.4l1.5 9.2a2 2 0 0 0 2 1.7h8.2a2 2 0 0 0 2-1.6L20.4 8H6" />
              <circle cx="9.5" cy="19.2" r="1.3" />
              <circle cx="17" cy="19.2" r="1.3" />
            </svg>
            <strong>장바구니에 담긴 상품이 없어요</strong>
            <span>마음에 드는 상품을 담아 보세요.</span>
            <button type="button" onClick={() => onNavigate(CUSTOMER_PRODUCTS_PATH)}>상품 보러 가기</button>
          </div>
        ) : (
          <div className="cart-layout">
            <section className="cart-list" aria-label="장바구니 상품">
              <div className="cart-list__toolbar">
                <label className="cart-check">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={() => setExcludedIds(isAllSelected ? new Set(items.map((item) => item.id)) : new Set())}
                  />
                  <span>전체 선택 ({selectedItems.length}/{items.length})</span>
                </label>
                <button type="button" disabled={!selectedItems.length} onClick={() => removeFromCart(selectedItems.map((item) => item.id))}>선택 삭제</button>
              </div>

              <ul>
                {items.map((item) => (
                  <li key={item.id} className="cart-item">
                    <label className="cart-check cart-check--item">
                      <input type="checkbox" checked={!excludedIds.has(item.id)} onChange={() => toggleItem(item.id)} aria-label={`${item.name} 선택`} />
                    </label>
                    <button className="cart-item__image" type="button" aria-label={`${item.name} 상세 보기`} onClick={() => onNavigate(getCustomerProductDetailPath(item.id))}>
                      {item.image_url ? <img src={item.image_url} alt={item.image_description || item.name} /> : <span>NO IMAGE</span>}
                    </button>
                    <div className="cart-item__info">
                      <span>{item.category}</span>
                      <button type="button" onClick={() => onNavigate(getCustomerProductDetailPath(item.id))}>{item.name}</button>
                      <em>{item.price.toLocaleString('ko-KR')}원</em>
                    </div>
                    <div className="catalog-quantity" role="group" aria-label={`${item.name} 수량`}>
                      <button type="button" aria-label="수량 줄이기" disabled={item.quantity <= 1} onClick={() => updateCartQuantity(item.id, item.quantity - 1)}>−</button>
                      <output>{item.quantity}</output>
                      <button type="button" aria-label="수량 늘리기" disabled={item.quantity >= MAX_QUANTITY} onClick={() => updateCartQuantity(item.id, item.quantity + 1)}>+</button>
                    </div>
                    <strong className="cart-item__total">{(item.price * item.quantity).toLocaleString('ko-KR')}원</strong>
                    <button className="cart-item__remove" type="button" aria-label={`${item.name} 삭제`} onClick={() => removeFromCart([item.id])}>
                      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            <aside className="cart-summary" aria-label="주문 금액">
              <h2>주문 금액</h2>
              <dl>
                <div><dt>선택 상품</dt><dd>{selectedItems.length}개</dd></div>
                <div><dt>상품금액</dt><dd>{totalPrice.toLocaleString('ko-KR')}원</dd></div>
              </dl>
              <div className="cart-summary__total">
                <span>결제 예정 금액</span>
                <strong>{totalPrice.toLocaleString('ko-KR')}<small>원</small></strong>
              </div>
              <button className="cart-summary__order" type="button" disabled={!selectedItems.length} onClick={handleOrder}>
                {selectedItems.length ? `${selectedItems.length}개 상품 주문하기` : '상품을 선택해 주세요'}
              </button>
            </aside>
          </div>
        )}
      </main>
      <CatalogFooter />
    </div>
  )
}

export default CartPage
