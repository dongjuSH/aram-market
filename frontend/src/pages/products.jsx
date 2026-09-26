// 로그인 후 상품관리 UI 및 비밀번호 변경·회원 탈퇴·로그아웃 기능

import { useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import DeleteAccountModal from '../components/auth/delete-account-modal.jsx'
import ProductPagination from '../components/products/product-pagination.jsx'
import ProductSearch from '../components/products/product-search.jsx'
import ProductTable from '../components/products/product-table.jsx'

// 계정 메뉴용 잠금·탈퇴·로그아웃 선 아이콘
function AccountActionIcon({ type }) {
  if (type === 'password') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="10" width="14" height="10" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" />
      </svg>
    )
  }
  if (type === 'delete') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" />
    </svg>
  )
}

// 상품관리 UI 및 로그인 사용자 계정 메뉴 상태 관리
function ProductsPage({ onNavigate }) {
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('currentUser')) || {}
    } catch {
      return {}
    }
  })
  const isPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1'
  const [isCheckingSession, setIsCheckingSession] = useState(!isPreview)

  // 상품 화면 진입 시 서버에서 토큰 유효성을 확인하고 만료 세션 차단
  useEffect(() => {
    if (isPreview) return undefined

    let isMounted = true
    getCurrentUser()
      .then((result) => {
        if (!isMounted) return
        setUser(result.user)
        sessionStorage.setItem('currentUser', JSON.stringify(result.user))
      })
      .catch(() => {
        if (!isMounted) return
        sessionStorage.removeItem('accessToken')
        sessionStorage.removeItem('currentUser')
        sessionStorage.setItem('authNotice', '로그인이 만료되었습니다. 다시 로그인해 주세요.')
        onNavigate('/login', { replace: true })
      })
      .finally(() => {
        if (isMounted) setIsCheckingSession(false)
      })

    return () => {
      isMounted = false
    }
  }, [isPreview, onNavigate])

  // 브라우저 세션 인증정보 제거 및 로그인 화면 이동
  const logout = () => {
    sessionStorage.removeItem('accessToken')
    sessionStorage.removeItem('currentUser')
    onNavigate('/login', { replace: true })
  }

  // 탈퇴 접수 안내 전달 및 현재 세션 종료
  const finishAccountDeletion = (message) => {
    sessionStorage.setItem('authNotice', message)
    logout()
  }

  if (isCheckingSession) {
    return (
      <main className="products-page products-page--loading">
        <p>로그인 정보를 확인하고 있습니다.</p>
      </main>
    )
  }

  return (
    <main className="products-page">
      <header className="products-header">
        <div className="products-user">
          <span className="products-user__avatar" aria-hidden="true">{user.nickname?.charAt(0) || '관'}</span>
          <p><strong>{user.nickname || '관리자'}</strong>님, 로그인되었습니다.</p>
        </div>
        <nav className="account-actions" aria-label="계정 메뉴">
          <button type="button" onClick={() => onNavigate('/change-password')}>
            <AccountActionIcon type="password" />
            <span>비밀번호 변경</span>
          </button>
          <button className="account-actions__danger" type="button" onClick={() => setShowDeleteAccount(true)}>
            <AccountActionIcon type="delete" />
            <span>회원 탈퇴</span>
          </button>
          <button className="account-actions__logout" type="button" onClick={logout}>
            <AccountActionIcon type="logout" />
            <span>로그아웃</span>
          </button>
        </nav>
      </header>

      <section className="product-content" aria-labelledby="product-list-title">
        <div className="product-toolbar">
          <div>
            <h1 id="product-list-title">상품 목록</h1>
            <p>상품 정보와 노출 상태를 관리합니다.</p>
          </div>
          <ProductSearch />
        </div>
        <ProductTable />
        <ProductPagination />
      </section>

      <DeleteAccountModal
        key={showDeleteAccount ? 'delete-open' : 'delete-closed'}
        isOpen={showDeleteAccount}
        onClose={() => setShowDeleteAccount(false)}
        onDeleted={finishAccountDeletion}
      />
    </main>
  )
}

export default ProductsPage
