// 고객 상품 URL과 관리자 전용 URL을 분리하는 클라이언트 라우팅

import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import AdminLoginPage from './pages/admin-login.jsx'
import AdminProductsPage from './pages/admin-products.jsx'
import ProductDetailPage from './pages/product-detail.jsx'
import ProductsPage from './pages/products.jsx'
import UserLoginPage from './features/user-auth/login.jsx'
import UserMyPage from './features/user-auth/my-page.jsx'
import UserResetPasswordPage from './features/user-auth/reset-password.jsx'
import UserSignupPage from './features/user-auth/signup.jsx'
import {
  ADMIN_BASE_PATH,
  ADMIN_LOGIN_PATH,
  ADMIN_PRODUCT_CREATE_PATH,
  ADMIN_PRODUCT_EDIT_PATH,
  ADMIN_PRODUCTS_PATH,
  ADMIN_SUPPORTED_PATHS,
  CUSTOMER_PRODUCTS_PATH,
  getCustomerProductDetailPath,
  isCustomerProductDetailPath,
  USER_LOGIN_PATH,
  USER_MY_PAGE_PATH,
  USER_RESET_PASSWORD_PATH,
  USER_SIGNUP_PATH,
  USER_SUPPORTED_PATHS,
} from './config/routes.js'

const SUPPORTED_PATHS = new Set([
  CUSTOMER_PRODUCTS_PATH,
  ...USER_SUPPORTED_PATHS,
  ...ADMIN_SUPPORTED_PATHS,
])
const AdminProductFormPage = lazy(() => import('./pages/admin-product-form.jsx'))

// 지원 경로 정규화 및 관리자 화면의 로그인 토큰 확인
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
  if (requiresAdmin && !sessionStorage.getItem('adminAccessToken')) return ADMIN_LOGIN_PATH
  if (currentPath === USER_MY_PAGE_PATH && !sessionStorage.getItem('userAccessToken')) return USER_LOGIN_PATH
  if ((currentPath === USER_LOGIN_PATH || currentPath === USER_SIGNUP_PATH) && sessionStorage.getItem('userAccessToken')) {
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
  if (path === USER_LOGIN_PATH) return <UserLoginPage onNavigate={navigate} />
  if (path === USER_SIGNUP_PATH) return <UserSignupPage onNavigate={navigate} />
  if (path === USER_RESET_PASSWORD_PATH) return <UserResetPasswordPage onNavigate={navigate} />
  if (path === USER_MY_PAGE_PATH) return <UserMyPage onNavigate={navigate} />
  if (path === ADMIN_PRODUCT_CREATE_PATH || path === ADMIN_PRODUCT_EDIT_PATH) {
    return (
      <Suspense fallback={<main className="products-page products-page--loading"><p>상품 편집기를 불러오고 있습니다.</p></main>}>
        <AdminProductFormPage mode={path === ADMIN_PRODUCT_EDIT_PATH ? 'edit' : 'create'} onNavigate={navigate} />
      </Suspense>
    )
  }
  if (path === ADMIN_PRODUCTS_PATH) return <AdminProductsPage onNavigate={navigate} />
  return <AdminLoginPage onNavigate={navigate} />
}

export default App
