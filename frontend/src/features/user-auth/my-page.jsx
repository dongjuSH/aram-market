// 주문·배송 현황, 회원정보(수신 설정 포함), 배송지 관리, 계정 관리를 제공하는 마이 페이지

import { useEffect, useState } from 'react'
import { getOrders } from '../../api/orders.js'
import { clearStoredUser, getCurrentUser, getStoredUser, storeUser } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import ChangePasswordModal from './change-password-modal.jsx'
import DeleteAccountModal from './delete-account-modal.jsx'
import AddressBook from './address-book.jsx'
import OrderHistory, { RECENT_ORDER_COUNT } from './order-history.jsx'
import ProfileCard from './profile-card.jsx'

// 회원 정보 조회와 각 영역 상태 관리
function UserMyPage({ onNavigate }) {
  const [user, setUser] = useState(getStoredUser)
  const [isLoading, setIsLoading] = useState(true)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [orders, setOrders] = useState([])
  const [orderTotal, setOrderTotal] = useState(0)
  const [isOrdersLoading, setIsOrdersLoading] = useState(true)
  const [ordersVersion, setOrdersVersion] = useState(0) // 주문 취소·취소 요청 후 최근 주문을 다시 불러오기 위한 값

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

  // 최근 결제 완료 주문 조회(실패해도 마이 페이지의 다른 영역은 그대로 사용, 취소 후 다시 조회)
  useEffect(() => {
    let isMounted = true
    getOrders({ pageSize: RECENT_ORDER_COUNT })
      .then((result) => {
        if (!isMounted) return
        setOrders(result.orders)
        setOrderTotal(result.total)
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setIsOrdersLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [ordersVersion])

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
              <span>주문·배송 현황과 회원정보를 한곳에서 관리하세요.</span>
            </div>
          </section>

          <OrderHistory
            orders={orders}
            total={orderTotal}
            isLoading={isOrdersLoading}
            onNavigate={onNavigate}
            onChanged={() => setOrdersVersion((version) => version + 1)}
          />
          <ProfileCard user={user} onUserChange={setUser} onNotice={setNotice} />
          <AddressBook />

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
