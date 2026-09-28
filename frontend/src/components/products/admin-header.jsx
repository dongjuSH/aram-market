// 상품 관리 화면의 단일 관리자 정보와 계정 작업 공통 헤더

import { ADMIN_LOGIN_PATH, CUSTOMER_PRODUCTS_PATH } from '../../config/routes.js'


// 고객용 상품 사이트 이동 아이콘
function SiteIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
    </svg>
  )
}


// 계정 메뉴용 로그아웃 선 아이콘
function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" />
    </svg>
  )
}


// 상품 목록과 등록·수정 페이지에서 동일한 계정 메뉴 제공
function AdminHeader({ user, onNavigate }) {
  const openCustomerSite = () => {
    window.open(CUSTOMER_PRODUCTS_PATH, '_blank', 'noopener,noreferrer')
  }

  const logout = () => {
    sessionStorage.removeItem('adminAccessToken')
    sessionStorage.removeItem('adminCurrentUser')
    onNavigate(ADMIN_LOGIN_PATH, { replace: true })
  }

  return (
    <header className="products-header">
      <div className="products-user">
        <span className="products-user__avatar" aria-hidden="true">관</span>
        <p><strong>{user.username || 'admin'}</strong> 관리자</p>
      </div>
      <nav className="account-actions" aria-label="관리자 메뉴">
        <button className="account-actions__site" type="button" onClick={openCustomerSite}>
          <SiteIcon />
          <span>사이트로 바로가기</span>
        </button>
        <button className="account-actions__logout" type="button" onClick={logout}>
          <LogoutIcon />
          <span>로그아웃</span>
        </button>
      </nav>
    </header>
  )
}

export default AdminHeader
