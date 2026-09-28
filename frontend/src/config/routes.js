// 고객 공개 경로와 환경변수 기반 관리자 전용 경로 정의

const configuredAdminPath = String(import.meta.env.VITE_ADMIN_BASE_PATH || '').trim()

if (!configuredAdminPath.startsWith('/') || configuredAdminPath.length < 12) {
  throw new Error('VITE_ADMIN_BASE_PATH는 /로 시작하는 12자 이상의 비공개 경로여야 합니다.')
}

export const CUSTOMER_PRODUCTS_PATH = '/products'
export const CUSTOMER_PRODUCT_DETAIL_PATH = '/products/detail'
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
