// 상품 관리 화면의 단일 관리자 정보와 계정 작업 공통 헤더

import { signOut } from '../../api/auth.js'
import { ADMIN_INQUIRIES_PATH, ADMIN_LOGIN_PATH, ADMIN_ORDERS_PATH, ADMIN_PRODUCTS_PATH, CUSTOMER_PRODUCTS_PATH } from '../../config/routes.js'


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


// 관리 화면 이동 메뉴(현재 화면을 제외한 나머지만 표시)
const ADMIN_MENU = [
  { key: 'products', label: '상품 관리', path: ADMIN_PRODUCTS_PATH },
  { key: 'orders', label: '주문 관리', path: ADMIN_ORDERS_PATH },
  { key: 'inquiries', label: '문의 관리', path: ADMIN_INQUIRIES_PATH },
]


// 관리 화면 공통 계정 메뉴: current는 지금 보고 있는 관리 화면(products, orders, inquiries)
function AdminHeader({ user, onNavigate, current = 'products' }) {
  const openCustomerSite = () => {
    window.open(CUSTOMER_PRODUCTS_PATH, '_blank', 'noopener,noreferrer')
  }

  const logout = async () => {
    await signOut()
    onNavigate(ADMIN_LOGIN_PATH, { replace: true })
  }

  return (
    <header className="products-header">
      <div className="products-user">
        <span className="products-user__avatar" aria-hidden="true">관</span>
        <p><strong>{user.username || 'admin'}</strong> 관리자</p>
      </div>
      <nav className="account-actions" aria-label="관리자 메뉴">
        {ADMIN_MENU.filter((menu) => menu.key !== current).map((menu) => (
          <button key={menu.key} className="account-actions__site" type="button" onClick={() => onNavigate(menu.path)}>
            <span>{menu.label}</span>
          </button>
        ))}
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
