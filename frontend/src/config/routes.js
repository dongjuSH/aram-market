// 고객 공개 경로와 환경변수 기반 관리자 전용 경로 정의

const configuredAdminPath = String(import.meta.env.VITE_ADMIN_BASE_PATH || '').trim()

if (!configuredAdminPath.startsWith('/') || configuredAdminPath.length < 12) {
  throw new Error('VITE_ADMIN_BASE_PATH는 /로 시작하는 12자 이상의 비공개 경로여야 합니다.')
}

export const CUSTOMER_PRODUCTS_PATH = '/'
export const CUSTOMER_PRODUCT_DETAIL_PREFIX = '/products/'

// 변경되지 않는 내부 상품 ID를 사용하는 고객 상세 경로 생성
export function getCustomerProductDetailPath(productId) {
  return `${CUSTOMER_PRODUCT_DETAIL_PREFIX}${productId}`
}

// 양의 정수 상품 ID가 포함된 고객 상세 경로 확인
export function isCustomerProductDetailPath(path) {
  return /^\/products\/[1-9]\d*$/.test(path)
}
export const CART_PATH = '/cart'
export const WISHLIST_PATH = '/wishlist'
export const CHECKOUT_PATH = '/checkout'
export const PAYMENT_SUCCESS_PATH = '/payment/success'
export const PAYMENT_FAIL_PATH = '/payment/fail'
const USER_BASE_PATH = '/user'
export const USER_LOGIN_PATH = `${USER_BASE_PATH}/login`
export const USER_SIGNUP_PATH = `${USER_BASE_PATH}/signup`
export const USER_RESET_PASSWORD_PATH = `${USER_BASE_PATH}/reset-password`
export const USER_VERIFY_EMAIL_PATH = `${USER_BASE_PATH}/verify-email`
export const USER_UNLOCK_PATH = `${USER_BASE_PATH}/unlock`
export const USER_MY_PAGE_PATH = USER_BASE_PATH
export const USER_ORDERS_PATH = `${USER_BASE_PATH}/orders`
export const USER_SUPPORTED_PATHS = new Set([
  USER_LOGIN_PATH,
  USER_SIGNUP_PATH,
  USER_RESET_PASSWORD_PATH,
  USER_VERIFY_EMAIL_PATH,
  USER_UNLOCK_PATH,
  USER_MY_PAGE_PATH,
  USER_ORDERS_PATH,
])

// 로그인 뒤 돌아갈 화면을 외부 주소·로그인 계열 화면이 아닌 고객 화면으로 제한(장바구니 포함)
export function getSafeRedirectPath(next) {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) return CUSTOMER_PRODUCTS_PATH
  const url = new URL(next, window.location.origin)
  if (url.origin !== window.location.origin) return CUSTOMER_PRODUCTS_PATH
  const allowed = url.pathname === CUSTOMER_PRODUCTS_PATH || isCustomerProductDetailPath(url.pathname) || url.pathname === USER_MY_PAGE_PATH || url.pathname === USER_ORDERS_PATH || url.pathname === CART_PATH || url.pathname === WISHLIST_PATH
  return allowed ? `${url.pathname}${url.search}` : CUSTOMER_PRODUCTS_PATH
}

// 현재 화면으로 돌아오도록 next를 붙인 로그인 경로 생성
export function getLoginPath(next) {
  const safeNext = getSafeRedirectPath(next)
  return safeNext === CUSTOMER_PRODUCTS_PATH ? USER_LOGIN_PATH : `${USER_LOGIN_PATH}?next=${encodeURIComponent(safeNext)}`
}
export const ADMIN_BASE_PATH = configuredAdminPath.replace(/\/$/, '')
export const ADMIN_LOGIN_PATH = `${ADMIN_BASE_PATH}/login`
export const ADMIN_PRODUCTS_PATH = `${ADMIN_BASE_PATH}/products`
export const ADMIN_INQUIRIES_PATH = `${ADMIN_BASE_PATH}/inquiries`
export const ADMIN_ORDERS_PATH = `${ADMIN_BASE_PATH}/orders`
export const ADMIN_PRODUCT_CREATE_PATH = `${ADMIN_PRODUCTS_PATH}/new`
export const ADMIN_PRODUCT_EDIT_PATH = `${ADMIN_PRODUCTS_PATH}/edit`

export const ADMIN_SUPPORTED_PATHS = new Set([
  ADMIN_LOGIN_PATH,
  ADMIN_PRODUCTS_PATH,
  ADMIN_INQUIRIES_PATH,
  ADMIN_ORDERS_PATH,
  ADMIN_PRODUCT_CREATE_PATH,
  ADMIN_PRODUCT_EDIT_PATH,
])
