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
export const USER_BASE_PATH = '/user'
export const USER_LOGIN_PATH = `${USER_BASE_PATH}/login`
export const USER_SIGNUP_PATH = `${USER_BASE_PATH}/signup`
export const USER_RESET_PASSWORD_PATH = `${USER_BASE_PATH}/reset-password`
export const USER_MY_PAGE_PATH = USER_BASE_PATH
export const USER_SUPPORTED_PATHS = new Set([
  USER_LOGIN_PATH,
  USER_SIGNUP_PATH,
  USER_RESET_PASSWORD_PATH,
  USER_MY_PAGE_PATH,
])
export const ADMIN_BASE_PATH = configuredAdminPath.replace(/\/$/, '')
export const ADMIN_LOGIN_PATH = `${ADMIN_BASE_PATH}/login`
export const ADMIN_PRODUCTS_PATH = `${ADMIN_BASE_PATH}/products`
export const ADMIN_PRODUCT_CREATE_PATH = `${ADMIN_PRODUCTS_PATH}/new`
export const ADMIN_PRODUCT_EDIT_PATH = `${ADMIN_PRODUCTS_PATH}/edit`

export const ADMIN_SUPPORTED_PATHS = new Set([
  ADMIN_LOGIN_PATH,
  ADMIN_PRODUCTS_PATH,
  ADMIN_PRODUCT_CREATE_PATH,
  ADMIN_PRODUCT_EDIT_PATH,
])
