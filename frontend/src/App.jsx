// 인증 URL 및 로그인 후 상품 조회 화면의 클라이언트 라우팅

import { useEffect, useState } from 'react'
import ChangePasswordPage from './pages/change-password.jsx'
import LoginPage from './pages/login.jsx'
import ProductsPage from './pages/products.jsx'
import ResetPasswordPage from './pages/reset-password.jsx'
import SignupPage from './pages/signup.jsx'

const LOGIN_PATH = '/login' // 인증되지 않은 사용자의 기본 진입 경로
const SIGNUP_PATH = '/signup' // 회원가입 화면 경로
const PRODUCTS_PATH = '/products' // 로그인 후 상품관리 화면 경로
const RESET_PASSWORD_PATH = '/reset-password' // 이메일 링크의 비밀번호 재설정 경로
const CHANGE_PASSWORD_PATH = '/change-password' // 로그인 사용자의 비밀번호 변경 경로
const SUPPORTED_PATHS = new Set([LOGIN_PATH, SIGNUP_PATH, PRODUCTS_PATH, RESET_PASSWORD_PATH, CHANGE_PASSWORD_PATH]) // 허용된 SPA 경로

// 지원 페이지 주소 정규화 및 상품 화면 로그인 토큰 확인
function getCurrentPath() {
  const currentPath = window.location.pathname
  // 개발 중 데이터 생성 없이 상품 화면을 확인하는 /products?preview=1 경로
  const isDevelopmentPreview = import.meta.env.DEV
    && new URLSearchParams(window.location.search).get('preview') === '1'
  const requiresLogin = currentPath === PRODUCTS_PATH || currentPath === CHANGE_PASSWORD_PATH
  if (requiresLogin && !sessionStorage.getItem('accessToken') && !isDevelopmentPreview) return LOGIN_PATH
  return SUPPORTED_PATHS.has(currentPath) ? currentPath : LOGIN_PATH
}

// 브라우저 주소와 현재 React 화면을 동기화하는 최상위 컴포넌트
function App() {
  const [path, setPath] = useState(getCurrentPath)

  useEffect(() => {
    if (window.location.pathname !== path) {
      window.history.replaceState({}, '', path)
    }

    const handlePopState = () => setPath(getCurrentPath())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [path])

  // History API 기반 새로고침 없는 페이지 이동
  const navigate = (nextPath, options = {}) => {
    const method = options.replace ? 'replaceState' : 'pushState'
    window.history[method]({}, '', nextPath)
    setPath(nextPath)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (path === SIGNUP_PATH) return <SignupPage onNavigate={navigate} />
  if (path === RESET_PASSWORD_PATH) return <ResetPasswordPage onNavigate={navigate} />
  if (path === CHANGE_PASSWORD_PATH) return <ChangePasswordPage onNavigate={navigate} />
  if (path === PRODUCTS_PATH) return <ProductsPage onNavigate={navigate} />
  return <LoginPage onNavigate={navigate} />
}

export default App
