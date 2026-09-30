// 고객 상품 URL과 관리자 전용 URL을 분리하는 클라이언트 라우팅

import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import AdminLoginPage from './pages/admin-login.jsx'
import AdminInquiriesPage from './pages/admin-inquiries.jsx'
import AdminOrdersPage from './pages/admin-orders.jsx'
import AdminProductsPage from './pages/admin-products.jsx'
import ProductDetailPage from './pages/product-detail.jsx'
import ProductsPage from './pages/products.jsx'
import CartPage from './features/cart/cart-page.jsx'
import WishlistPage from './features/wishlist/wishlist-page.jsx'
import CheckoutPage from './features/checkout/checkout-page.jsx'
import { PaymentFailPage, PaymentSuccessPage } from './features/checkout/payment-result.jsx'
import UserLoginPage from './features/user-auth/login.jsx'
import UserMyPage from './features/user-auth/my-page.jsx'
import UserResetPasswordPage from './features/user-auth/reset-password.jsx'
import UserSignupPage from './features/user-auth/signup.jsx'
import UserUnlockAccountPage from './features/user-auth/unlock-account.jsx'
import UserVerifyEmailPage from './features/user-auth/verify-email.jsx'
import { getStoredUser } from './api/user-auth.js'
import {
  ADMIN_BASE_PATH,
  ADMIN_INQUIRIES_PATH,
  ADMIN_LOGIN_PATH,
  ADMIN_ORDERS_PATH,
  ADMIN_PRODUCT_CREATE_PATH,
  ADMIN_PRODUCT_EDIT_PATH,
  ADMIN_PRODUCTS_PATH,
  ADMIN_SUPPORTED_PATHS,
  CART_PATH,
  CHECKOUT_PATH,
  CUSTOMER_PRODUCTS_PATH,
  PAYMENT_FAIL_PATH,
  PAYMENT_SUCCESS_PATH,
  getCustomerProductDetailPath,
  getLoginPath,
  isCustomerProductDetailPath,
  USER_LOGIN_PATH,
  USER_MY_PAGE_PATH,
  USER_RESET_PASSWORD_PATH,
  USER_SIGNUP_PATH,
  USER_SUPPORTED_PATHS,
  USER_UNLOCK_PATH,
  USER_VERIFY_EMAIL_PATH,
  WISHLIST_PATH,
} from './config/routes.js'

const SUPPORTED_PATHS = new Set([
  CUSTOMER_PRODUCTS_PATH,
  CART_PATH,
  CHECKOUT_PATH,
  WISHLIST_PATH,
  PAYMENT_SUCCESS_PATH,
  PAYMENT_FAIL_PATH,
  ...USER_SUPPORTED_PATHS,
  ...ADMIN_SUPPORTED_PATHS,
])
const AdminProductFormPage = lazy(() => import('./pages/admin-product-form.jsx'))

// 지원 경로 정규화 및 로그인 표식 기반 화면 접근 확인(실제 인증은 서버가 쿠키로 검증)
function getCurrentRoute() {
  const currentPath = window.location.pathname
  if (currentPath === '/products') return CUSTOMER_PRODUCTS_PATH
  if (currentPath === '/products/detail') {
    const legacyProductId = Number(new URLSearchParams(window.location.search).get('id'))
    return Number.isInteger(legacyProductId) && legacyProductId > 0
      ? getCustomerProductDetailPath(legacyProductId)
      : CUSTOMER_PRODUCTS_PATH
  }
  if (isCustomerProductDetailPath(currentPath)) return currentPath
  const requiresAdmin = currentPath.startsWith(`${ADMIN_BASE_PATH}/`) && currentPath !== ADMIN_LOGIN_PATH
  if (requiresAdmin && !sessionStorage.getItem('adminCurrentUser')) return ADMIN_LOGIN_PATH
  if (currentPath === USER_MY_PAGE_PATH && !getStoredUser()) return getLoginPath(`${USER_MY_PAGE_PATH}${window.location.search}`)
  if (currentPath === WISHLIST_PATH && !getStoredUser()) return getLoginPath(WISHLIST_PATH)
  if ((currentPath === PAYMENT_SUCCESS_PATH || currentPath === CHECKOUT_PATH) && !getStoredUser()) return getLoginPath(CART_PATH)
  if ((currentPath === USER_LOGIN_PATH || currentPath === USER_SIGNUP_PATH) && getStoredUser()) {
    return USER_MY_PAGE_PATH
  }
  return SUPPORTED_PATHS.has(currentPath)
    ? `${currentPath}${window.location.search}`
    : CUSTOMER_PRODUCTS_PATH
}

// 브라우저 주소와 현재 React 화면을 동기화하는 최상위 컴포넌트
function App() {
  const [route, setRoute] = useState(getCurrentRoute)
  const path = route.split('?')[0]

  useEffect(() => {
    const browserRoute = `${window.location.pathname}${window.location.search}`
    if (browserRoute !== route) window.history.replaceState({}, '', route)
    const handlePopState = () => setRoute(getCurrentRoute())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [route])

  // History API 기반 새로고침 없는 페이지 이동
  const navigate = useCallback((nextPath, options = {}) => {
    const method = options.replace ? 'replaceState' : 'pushState'
    const nextUrl = new URL(nextPath, window.location.origin)
    window.history[method]({}, '', `${nextUrl.pathname}${nextUrl.search}`)
    setRoute(`${nextUrl.pathname}${nextUrl.search}`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  if (isCustomerProductDetailPath(path)) return <ProductDetailPage key={route} onNavigate={navigate} />
  if (path === CUSTOMER_PRODUCTS_PATH) return <ProductsPage onNavigate={navigate} />
  if (path === PAYMENT_SUCCESS_PATH) return <PaymentSuccessPage onNavigate={navigate} />
  if (path === PAYMENT_FAIL_PATH) return <PaymentFailPage onNavigate={navigate} />
  if (path === WISHLIST_PATH) return <WishlistPage onNavigate={navigate} />
  if (path === CHECKOUT_PATH) return <CheckoutPage onNavigate={navigate} />
  if (path === CART_PATH) return <CartPage onNavigate={navigate} />
  if (path === USER_LOGIN_PATH) return <UserLoginPage onNavigate={navigate} />
  if (path === USER_SIGNUP_PATH) return <UserSignupPage onNavigate={navigate} />
  if (path === USER_RESET_PASSWORD_PATH) return <UserResetPasswordPage onNavigate={navigate} />
  if (path === USER_UNLOCK_PATH) return <UserUnlockAccountPage onNavigate={navigate} />
  if (path === USER_VERIFY_EMAIL_PATH) return <UserVerifyEmailPage onNavigate={navigate} />
  if (path === USER_MY_PAGE_PATH) return <UserMyPage onNavigate={navigate} />
  if (path === ADMIN_PRODUCT_CREATE_PATH || path === ADMIN_PRODUCT_EDIT_PATH) {
    return (
      <Suspense fallback={<main className="products-page products-page--loading"><p>상품 편집기를 불러오고 있습니다.</p></main>}>
        <AdminProductFormPage mode={path === ADMIN_PRODUCT_EDIT_PATH ? 'edit' : 'create'} onNavigate={navigate} />
      </Suspense>
    )
  }
  if (path === ADMIN_ORDERS_PATH) return <AdminOrdersPage onNavigate={navigate} />
  if (path === ADMIN_INQUIRIES_PATH) return <AdminInquiriesPage onNavigate={navigate} />
  if (path === ADMIN_PRODUCTS_PATH) return <AdminProductsPage onNavigate={navigate} />
  if (path === ADMIN_LOGIN_PATH) return <AdminLoginPage onNavigate={navigate} />
  return <ProductsPage onNavigate={navigate} />
}

export default App
