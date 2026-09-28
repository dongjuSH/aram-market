// 회원정보·수신 동의·계정 관리·향후 주문 내역 UI를 제공하는 마이 페이지

import { useEffect, useState } from 'react'
import { getCurrentUser, updateMarketingConsent } from '../../api/user-auth.js'
import Modal from '../../components/common/modal.jsx'
import CustomerAccountShell from '../../components/user/customer-account-shell.jsx'
import ChangePasswordModal from './change-password-modal.jsx'
import DeleteAccountModal from './delete-account-modal.jsx'


function readSavedUser() {
  try {
    return JSON.parse(sessionStorage.getItem('userCurrentUser') || 'null')
  } catch {
    return null
  }
}


function UserMyPage({ onNavigate }) {
  const [user, setUser] = useState(readSavedUser)
  const [isLoading, setIsLoading] = useState(true)
  const [isSavingMarketing, setIsSavingMarketing] = useState(false)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let isMounted = true
    getCurrentUser()
      .then((result) => {
        if (!isMounted) return
        setUser(result.user)
        sessionStorage.setItem('userCurrentUser', JSON.stringify(result.user))
      })
      .catch(() => {
        if (!isMounted) return
        sessionStorage.removeItem('userAccessToken')
        sessionStorage.removeItem('userCurrentUser')
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

  const logout = () => {
    sessionStorage.removeItem('userAccessToken')
    sessionStorage.removeItem('userCurrentUser')
    onNavigate('/', { replace: true })
  }

  const changeMarketingConsent = async (event) => {
    const nextValue = event.target.checked
    setIsSavingMarketing(true)
    try {
      const result = await updateMarketingConsent(nextValue)
      setUser(result.user)
      sessionStorage.setItem('userCurrentUser', JSON.stringify(result.user))
      setNotice(nextValue ? '마케팅 정보 수신에 동의했습니다.' : '마케팅 정보 수신 동의를 철회했습니다.')
    } catch (error) {
      setNotice(error.message)
    } finally {
      setIsSavingMarketing(false)
    }
  }

  const finishPasswordChange = (message) => {
    sessionStorage.removeItem('userAccessToken')
    sessionStorage.removeItem('userCurrentUser')
    sessionStorage.setItem('authNotice', message)
    onNavigate('/user/login', { replace: true })
  }

  const finishAccountDeletion = (message) => {
    sessionStorage.removeItem('userAccessToken')
    sessionStorage.removeItem('userCurrentUser')
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

          <section className="my-page-card my-orders" aria-labelledby="orders-title">
            <div className="my-page-card__heading">
              <div>
                <p>ORDERS</p>
                <h2 id="orders-title">주문한 제품</h2>
              </div>
              <span className="my-page-badge">UI 준비 완료</span>
            </div>
            <div className="my-order-preview">
              <div className="my-order-preview__image" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M5 8h14l-1 12H6L5 8Z"/><path d="M9 9V6a3 3 0 0 1 6 0v3"/></svg>
              </div>
              <div>
                <span>상품 상세 페이지 주문 연동 예정</span>
                <strong>주문한 상품명이 표시됩니다.</strong>
                <p>주문번호 · 주문일자 · 수량 · 결제금액</p>
              </div>
              <span className="my-order-preview__status">배송 상태</span>
            </div>
            <p className="my-orders__note">현재는 주문 내역 UI만 구성되어 있으며, 상품 상세 페이지 주문 기능 구현 시 실제 데이터가 연결됩니다.</p>
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
