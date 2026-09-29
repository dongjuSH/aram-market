// 회원정보·수신 동의·계정 관리·향후 주문 내역 UI를 제공하는 마이 페이지

import { useEffect, useState } from 'react'
import { getOrders } from '../../api/orders.js'
import { addToCart, toggleWishlist, useShopping } from '../cart/shopping-store.js'
import { DELIVERY_STEPS, getDeliveryLabel } from '../../config/delivery.js'
import { getCustomerProductDetailPath } from '../../config/routes.js'
import { clearStoredUser, getCurrentUser, getStoredUser, signOut, storeUser, updateMarketingConsent } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import ChangePasswordModal from './change-password-modal.jsx'
import DeleteAccountModal from './delete-account-modal.jsx'


function UserMyPage({ onNavigate }) {
  const [user, setUser] = useState(getStoredUser)
  const [isLoading, setIsLoading] = useState(true)
  const [isSavingMarketing, setIsSavingMarketing] = useState(false)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [orders, setOrders] = useState([])
  const [isOrdersLoading, setIsOrdersLoading] = useState(true)
  const { wishlistItems } = useShopping()

  useEffect(() => {
    let isMounted = true
    getCurrentUser()
      .then((result) => {
        if (!isMounted) return
        setUser(result.user)
        storeUser(result.user)
      })
      .catch(() => {
        if (!isMounted) return
        clearStoredUser()
        sessionStorage.setItem('authNotice', '로그인이 만료되었습니다. 다시 로그인해 주세요.')
        onNavigate('/user/login', { replace: true })
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [onNavigate])

  // 결제 완료된 주문 내역 조회(실패해도 마이 페이지의 다른 영역은 그대로 사용)
  useEffect(() => {
    let isMounted = true
    getOrders()
      .then((result) => {
        if (isMounted) setOrders(result.orders)
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setIsOrdersLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [])

  // 헤더의 찜 목록 아이콘으로 들어오면(?section=wishlist) 찜한 상품 구역으로 스크롤
  useEffect(() => {
    if (isLoading || new URLSearchParams(window.location.search).get('section') !== 'wishlist') return
    document.getElementById('wishlist-section')?.scrollIntoView({ block: 'start' })
  }, [isLoading])

  const logout = async () => {
    await signOut()
    onNavigate('/', { replace: true })
  }

  const changeMarketingConsent = async (event) => {
    const nextValue = event.target.checked
    setIsSavingMarketing(true)
    try {
      const result = await updateMarketingConsent(nextValue)
      setUser(result.user)
      storeUser(result.user)
      setNotice(nextValue ? '마케팅 정보 수신에 동의했습니다.' : '마케팅 정보 수신 동의를 철회했습니다.')
    } catch (error) {
      setNotice(error.message)
    } finally {
      setIsSavingMarketing(false)
    }
  }

  const finishPasswordChange = (message) => {
    clearStoredUser() // 서버가 비밀번호 변경·탈퇴 응답에서 인증 쿠키를 이미 삭제함
    sessionStorage.setItem('authNotice', message)
    onNavigate('/user/login', { replace: true })
  }

  const finishAccountDeletion = (message) => {
    clearStoredUser() // 서버가 비밀번호 변경·탈퇴 응답에서 인증 쿠키를 이미 삭제함
    sessionStorage.setItem('authNotice', message)
    onNavigate('/user/login', { replace: true })
  }

  return (
    <CustomerAccountShell onNavigate={onNavigate} className="customer-account-page--my">
      {isLoading ? (
        <p className="catalog-notice" role="status">회원 정보를 불러오고 있습니다.</p>
      ) : (
        <div className="my-page-shell">
          <section className="my-page-hero" aria-labelledby="my-page-title">
            <div>
              <p>MY ARAM</p>
              <h1 id="my-page-title">{user?.nickname || '회원'}님의 마이 페이지</h1>
              <span>회원정보와 주문 내역을 한곳에서 관리하세요.</span>
            </div>
            <button type="button" onClick={logout}>로그아웃</button>
          </section>

          <div className="my-page-grid">
            <section className="my-page-card my-page-profile" aria-labelledby="profile-title">
              <div className="my-page-card__heading">
                <div>
                  <p>ACCOUNT</p>
                  <h2 id="profile-title">회원정보</h2>
                </div>
                <span className="my-page-profile__avatar" aria-hidden="true">{(user?.nickname || '아').slice(0, 1)}</span>
              </div>
              <dl>
                <div><dt>아이디</dt><dd>{user?.username}</dd></div>
                <div><dt>닉네임</dt><dd>{user?.nickname}</dd></div>
                <div><dt>이메일</dt><dd>{user?.email}</dd></div>
              </dl>
            </section>

            <section className="my-page-card" aria-labelledby="preferences-title">
              <div className="my-page-card__heading">
                <div>
                  <p>PREFERENCES</p>
                  <h2 id="preferences-title">수신 설정</h2>
                </div>
              </div>
              <label className="my-page-switch">
                <span>
                  <strong>[선택] 마케팅 정보 수신 동의</strong>
                  <small>신상품, 혜택 및 이벤트 안내를 이메일로 받아봅니다.</small>
                </span>
                <input type="checkbox" role="switch" checked={Boolean(user?.marketing_consent)} onChange={changeMarketingConsent} disabled={isSavingMarketing} />
              </label>
            </section>
          </div>

          <section id="wishlist-section" className="my-page-card my-wishlist" aria-labelledby="wishlist-title">
            <div className="my-page-card__heading">
              <div>
                <p>WISHLIST</p>
                <h2 id="wishlist-title">찜한 상품 <span className="my-page-count">{wishlistItems.length}</span></h2>
              </div>
            </div>
            {wishlistItems.length === 0 ? (
              <div className="my-empty">
                <strong>찜한 상품이 없어요</strong>
                <span>상품 상세 화면의 ♡ 버튼으로 마음에 드는 상품을 모아 보세요.</span>
                <button type="button" onClick={() => onNavigate('/')}>상품 보러 가기</button>
              </div>
            ) : (
              <ul className="my-wishlist__grid">
                {wishlistItems.map((item) => (
                  <li key={item.id} className="my-wishlist__item">
                    <button className="my-wishlist__image" type="button" aria-label={`${item.name} 상세 보기`} onClick={() => onNavigate(getCustomerProductDetailPath(item.id))}>
                      {item.image_url ? <img src={item.image_url} alt={item.image_description || item.name} /> : <span>NO IMAGE</span>}
                    </button>
                    <span className="my-wishlist__category">{item.category}</span>
                    <button className="my-wishlist__name" type="button" onClick={() => onNavigate(getCustomerProductDetailPath(item.id))}>{item.name}</button>
                    <strong>{item.price.toLocaleString('ko-KR')}원</strong>
                    <div className="my-wishlist__actions">
                      <button type="button" onClick={() => addToCart(item)}>장바구니 담기</button>
                      <button type="button" onClick={() => toggleWishlist(item)}>찜 해제</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="my-page-card my-orders" aria-labelledby="orders-title">
            <div className="my-page-card__heading">
              <div>
                <p>ORDERS</p>
                <h2 id="orders-title">주문한 제품</h2>
              </div>
            </div>
            {isOrdersLoading ? (
              <p className="my-orders__note" role="status">주문 내역을 불러오고 있습니다.</p>
            ) : orders.length === 0 ? (
              <div className="my-empty">
                <strong>주문 내역이 없어요</strong>
                <span>결제가 완료된 주문이 여기에 표시됩니다.</span>
              </div>
            ) : (
              <ul className="my-orders__list">
                {orders.map((order) => (
                  <li key={order.order_id} className="my-orders__order">
                    <div className="my-orders__meta">
                      <strong>{new Date(order.paid_at || order.created_at).toLocaleDateString('ko-KR')} 결제</strong>
                      <span>주문번호 {order.order_id}</span>
                    </div>
                    <ol className="delivery-steps" aria-label={`배송 상태: ${getDeliveryLabel(order.delivery_status)}`}>
                      {DELIVERY_STEPS.map((step, index) => (
                        <li key={step.key} className={index <= DELIVERY_STEPS.findIndex((item) => item.key === order.delivery_status) ? 'is-done' : ''} aria-current={step.key === order.delivery_status ? 'step' : undefined}>
                          {step.label}
                        </li>
                      ))}
                    </ol>
                    {order.items.map((item, index) => (
                      <div key={`${order.order_id}-${index}`} className="my-orders__item">
                        {item.image_url ? <img src={item.image_url} alt="" /> : <span className="my-orders__noimage" aria-hidden="true" />}
                        <div>
                          <strong>{item.name}</strong>
                          <span>{item.unit_price.toLocaleString('ko-KR')}원 · {item.quantity}개</span>
                        </div>
                      </div>
                    ))}
                    {order.shipping && (
                      <p className="my-orders__address">
                        <strong>{order.shipping.recipient_name}</strong> · {order.shipping.recipient_phone}<br />
                        {order.shipping.postcode ? `[${order.shipping.postcode}] ` : ''}{order.shipping.address} {order.shipping.address_detail}
                        {order.shipping.delivery_memo && <><br />요청사항: {order.shipping.delivery_memo}</>}
                      </p>
                    )}
                    <div className="my-orders__total">
                      <span>결제 금액</span>
                      <strong>{order.total_amount.toLocaleString('ko-KR')}원</strong>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="my-page-card my-account-actions" aria-labelledby="account-actions-title">
            <div className="my-page-card__heading">
              <div>
                <p>SECURITY</p>
                <h2 id="account-actions-title">계정 관리</h2>
              </div>
            </div>
            <div className="my-account-actions__buttons">
              <button type="button" onClick={() => setIsPasswordModalOpen(true)}>비밀번호 변경</button>
              <button className="is-danger" type="button" onClick={() => setIsDeleteModalOpen(true)}>회원 탈퇴</button>
            </div>
          </section>
        </div>
      )}

      <ChangePasswordModal key={isPasswordModalOpen ? 'password-open' : 'password-closed'} isOpen={isPasswordModalOpen} onClose={() => setIsPasswordModalOpen(false)} onChanged={finishPasswordChange} />
      <DeleteAccountModal key={isDeleteModalOpen ? 'delete-open' : 'delete-closed'} isOpen={isDeleteModalOpen} onClose={() => setIsDeleteModalOpen(false)} onDeleted={finishAccountDeletion} />
      <Modal isOpen={Boolean(notice)} message={notice} onClose={() => setNotice('')} />
    </CustomerAccountShell>
  )
}

export default UserMyPage
